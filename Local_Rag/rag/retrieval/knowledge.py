"""A source-backed research map, separate from the legacy NLP/citation graph.

Topic links mean explicit mentions, never causation. Findings live in a separate
table and must carry an exact source quote. The library and old graph are inputs,
not migration targets. All request-time queries use the compact derived index.
"""

from __future__ import annotations

import fcntl
import hashlib
import itertools
import json
import math
import re
import sqlite3
import time
import unicodedata
from collections import Counter, defaultdict
from contextlib import closing, contextmanager
from functools import lru_cache
from pathlib import Path

from config import DATA_DIR, DB_PATH

from retrieval.knowledge_topics import CATEGORY_COLORS, TOPICS

KNOWLEDGE_DB_PATH = DATA_DIR / "knowledge.db"
VERSION = "research-map-v1"
TOPIC_BY_ID = {
    row[0]: {"id": row[0], "name": row[1], "category": row[2], "aliases": row[3]}
    for row in TOPICS
}
DDL = """
CREATE TABLE IF NOT EXISTS kg_papers (
 paper_id TEXT PRIMARY KEY, title TEXT NOT NULL, authors TEXT NOT NULL, year INTEGER,
 citation_key TEXT NOT NULL, doi TEXT NOT NULL, abstract TEXT NOT NULL,
 fingerprint TEXT NOT NULL, chunk_count INTEGER NOT NULL, indexed_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS kg_mentions (
 topic_id TEXT NOT NULL, paper_id TEXT NOT NULL REFERENCES kg_papers ON DELETE CASCADE,
 chunk_id TEXT NOT NULL, section_name TEXT NOT NULL, page_start INTEGER, page_end INTEGER,
 quote TEXT NOT NULL, strength REAL NOT NULL,
 PRIMARY KEY(topic_id,paper_id,chunk_id)
);
CREATE INDEX IF NOT EXISTS kg_mentions_paper ON kg_mentions(paper_id,topic_id);
CREATE TABLE IF NOT EXISTS kg_claims (
 claim_id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES kg_papers ON DELETE CASCADE,
 chunk_id TEXT NOT NULL, source TEXT NOT NULL, target TEXT NOT NULL,
 source_key TEXT NOT NULL, target_key TEXT NOT NULL, relation TEXT NOT NULL,
 quote TEXT NOT NULL, conditions TEXT NOT NULL, section_name TEXT NOT NULL,
 page_start INTEGER, page_end INTEGER, model TEXT NOT NULL, text_hash TEXT NOT NULL,
 created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS kg_claims_paper ON kg_claims(paper_id,chunk_id);
CREATE INDEX IF NOT EXISTS kg_claims_pair ON kg_claims(source_key,target_key,relation);
CREATE TABLE IF NOT EXISTS kg_attempts (
 chunk_id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES kg_papers ON DELETE CASCADE,
 text_hash TEXT NOT NULL, model TEXT NOT NULL, status TEXT NOT NULL, checked_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS kg_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def connect(*, write=False):
    path = Path(KNOWLEDGE_DB_PATH)
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(DDL)
    else:
        conn = sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5
        )
    conn.row_factory = sqlite3.Row
    return conn


def source_connection():
    conn = sqlite3.connect(
        Path(DB_PATH).resolve().as_uri() + "?mode=ro", uri=True, timeout=10
    )
    conn.row_factory = sqlite3.Row
    return conn


def source_signature():
    if not Path(DB_PATH).exists():
        return ""
    result = []
    for path in (Path(DB_PATH), Path(str(DB_PATH) + "-wal")):
        try:
            stat = path.stat()
            result.append((stat.st_mtime_ns, stat.st_size) if stat.st_size else None)
        except FileNotFoundError:
            result.append(None)
    return _content_signature(str(Path(DB_PATH).resolve()), tuple(result))


@lru_cache(maxsize=8)
def _content_signature(path, file_state):
    # Hash relevant source rows, not SQLite bookkeeping, vectors or unrelated
    # citation settings. File timestamps only invalidate this bounded cache.
    digest = hashlib.sha256(json.dumps([VERSION, TOPICS], sort_keys=True).encode())
    with closing(
        sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True, timeout=10)
    ) as conn:
        conn.execute("BEGIN")
        queries = [
            "SELECT paper_id,title,authors,year,doi,abstract FROM papers ORDER BY paper_id",
            "SELECT chunk_id,paper_id,section_name,page_start,page_end,position,text FROM chunks ORDER BY chunk_id",
        ]
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='citation_catalog'"
        ).fetchone():
            queries.append(
                "SELECT paper_id,citation_key FROM citation_catalog ORDER BY paper_id,citation_key"
            )
        for sql in queries:
            for row in conn.execute(sql):
                digest.update(
                    json.dumps(
                        tuple(row), ensure_ascii=False, separators=(",", ":")
                    ).encode()
                )
                digest.update(b"\n")
    return digest.hexdigest()


@contextmanager
def writer_lock():
    path = Path(KNOWLEDGE_DB_PATH).with_suffix(".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                "The research map is already being updated. Try again when it finishes."
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def normalize(value):
    value = unicodedata.normalize("NFKC", value or "").casefold()
    value = re.sub(r"[‐‑‒–—−]", "-", value)
    return re.sub(r"\s+", " ", value).strip()


def _alias_expression(value):
    return (
        re.escape(normalize(value)).replace(r"\ ", r"[\s-]+").replace(r"\-", r"[\s-]+")
    )


_ALIAS_TOPICS = defaultdict(set)
for _topic in TOPICS:
    for _alias in [*_topic[3], _topic[1]]:
        _ALIAS_TOPICS[_alias_expression(_alias)].add(_topic[0])
_MATCHER = re.compile(
    r"(?<!\w)(?:" + "|".join(sorted(_ALIAS_TOPICS, key=len, reverse=True)) + r")(?!\w)"
)
_ALIAS_MATCHERS = [
    (re.compile(r"^(?:" + pattern + r")$"), ids)
    for pattern, ids in _ALIAS_TOPICS.items()
]


def topic_matches(text):
    text = normalize(text)
    found = {}
    for match in _MATCHER.finditer(text):
        for pattern, ids in _ALIAS_MATCHERS:
            if pattern.fullmatch(match.group()):
                for topic_id in ids:
                    found.setdefault(topic_id, match.start())
                break
    return found


def _section_score(section):
    section = normalize(section)
    if re.search(r"reference|bibliograph|acknowledg", section):
        return 0
    if re.search(r"result|discussion|conclusion|finding", section):
        return 4
    if re.search(r"method|experiment|material", section):
        return 3
    return 1


def _snippet(text, position, size=650):
    # Position is in normalized text; excerpts themselves retain source spelling.
    clean = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "")).strip()
    start = max(0, position - 170)
    end = min(len(clean), start + size)
    if start:
        start = clean.find(" ", start, start + 40) + 1 or start
    return clean[start:end]


def build_index(paper_ids=None, progress=None):
    """Incrementally refresh topic evidence; commit each complete paper atomically.

    A full pass removes deleted papers. Text/metadata changes invalidate extracted
    claims for that paper so old quotes cannot survive a repaired/replaced source.
    """
    from citations import make_key

    with (
        writer_lock(),
        closing(source_connection()) as source,
        closing(connect(write=True)) as dest,
    ):
        signature = source_signature()
        source.execute("BEGIN")
        papers = [
            dict(row)
            for row in source.execute("SELECT * FROM papers ORDER BY paper_id")
        ]
        keys = {}
        if source.execute(
            "SELECT 1 FROM sqlite_master WHERE name='citation_catalog'"
        ).fetchone():
            keys = dict(
                source.execute(
                    "SELECT paper_id,citation_key FROM citation_catalog WHERE paper_id IS NOT NULL"
                )
            )
        all_ids = {paper["paper_id"] for paper in papers}
        selected = set(paper_ids) if paper_ids is not None else all_ids
        papers = [paper for paper in papers if paper["paper_id"] in selected]
        existing = {
            row[0]: row[1]
            for row in dest.execute("SELECT paper_id,fingerprint FROM kg_papers")
        }
        # One pass avoids scanning an unindexed chunks table once per paper.
        chunks_by_paper = defaultdict(list)
        for row in source.execute(
            "SELECT * FROM chunks ORDER BY paper_id,position,chunk_id"
        ):
            if row["paper_id"] in selected:
                chunks_by_paper[row["paper_id"]].append(dict(row))
        changed = skipped = 0
        for index, paper in enumerate(papers):
            pid = paper["paper_id"]
            chunks = chunks_by_paper.pop(pid, [])
            metadata = {
                key: paper.get(key)
                for key in ("title", "authors", "year", "doi", "abstract")
            }
            key = keys.get(pid) or make_key(
                paper.get("title", ""), paper.get("authors", ""), paper.get("year")
            )
            digest = hashlib.sha256(
                json.dumps(
                    [VERSION, TOPICS, metadata, key, chunks], sort_keys=True
                ).encode()
            ).hexdigest()
            if existing.get(pid) == digest:
                skipped += 1
            else:
                emphatic = topic_matches(
                    (paper.get("title") or "") + " " + (paper.get("abstract") or "")
                )
                mentions = defaultdict(list)
                for chunk in chunks:
                    score = _section_score(chunk.get("section_name", ""))
                    if not score:
                        continue
                    raw = chunk.get("text") or ""
                    matches = topic_matches(raw)
                    for tid, position in matches.items():
                        strength = score + (5 if tid in emphatic else 0)
                        mentions[tid].append(
                            (strength, chunk.get("position") or 0, chunk, position)
                        )
                # A title/abstract alone can establish a topic mention, even when
                # full-text parsing is absent. Such links are explicitly labeled.
                metadata_text = (
                    (paper.get("title") or "") + "\n" + (paper.get("abstract") or "")
                )
                for tid, position in topic_matches(metadata_text).items():
                    mentions[tid].append(
                        (
                            6,
                            -1,
                            {
                                "chunk_id": "",
                                "section_name": "Title / abstract",
                                "text": metadata_text,
                            },
                            position,
                        )
                    )
                with dest:
                    dest.execute("DELETE FROM kg_papers WHERE paper_id=?", (pid,))
                    dest.execute(
                        "INSERT INTO kg_papers VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (
                            pid,
                            paper.get("title") or pid,
                            paper.get("authors") or "",
                            paper.get("year"),
                            key,
                            paper.get("doi") or "",
                            paper.get("abstract") or "",
                            digest,
                            len(chunks),
                            time.time(),
                        ),
                    )
                    for tid, candidates in mentions.items():
                        for strength, _, chunk, position in sorted(
                            candidates, key=lambda item: (-item[0], item[1])
                        )[:5]:
                            dest.execute(
                                "INSERT OR IGNORE INTO kg_mentions VALUES(?,?,?,?,?,?,?,?)",
                                (
                                    tid,
                                    pid,
                                    chunk["chunk_id"],
                                    chunk.get("section_name") or "",
                                    chunk.get("page_start"),
                                    chunk.get("page_end"),
                                    _snippet(chunk.get("text") or "", position),
                                    strength,
                                ),
                            )
                changed += 1
            if progress:
                progress(index + 1, len(papers))
        with dest:
            for row in dest.execute("SELECT paper_id FROM kg_papers").fetchall():
                if row[0] not in all_ids:
                    dest.execute("DELETE FROM kg_papers WHERE paper_id=?", (row[0],))
            dest.execute(
                "INSERT OR REPLACE INTO kg_meta VALUES('updated_at',?)",
                (str(time.time()),),
            )
            if paper_ids is None:
                dest.execute(
                    "INSERT OR REPLACE INTO kg_meta VALUES('source_signature',?)",
                    (signature,),
                )
        return {"changed": changed, "unchanged": skipped, **_stats(dest)}


def _stats(conn):
    return {
        "papers": conn.execute("SELECT count(*) FROM kg_papers").fetchone()[0],
        "mapped_papers": conn.execute(
            "SELECT count(DISTINCT paper_id) FROM kg_mentions"
        ).fetchone()[0],
        "topics": conn.execute(
            "SELECT count(DISTINCT topic_id) FROM kg_mentions"
        ).fetchone()[0],
        "passages": conn.execute(
            "SELECT count(DISTINCT chunk_id) FROM kg_mentions WHERE chunk_id!=''"
        ).fetchone()[0],
        "findings": conn.execute("SELECT count(*) FROM kg_claims").fetchone()[0],
        "papers_with_findings": conn.execute(
            "SELECT count(DISTINCT paper_id) FROM kg_claims"
        ).fetchone()[0],
        "checked_chunks": conn.execute(
            "SELECT count(*) FROM kg_attempts WHERE status='ok'"
        ).fetchone()[0],
        "updated_at": float(
            (
                conn.execute(
                    "SELECT value FROM kg_meta WHERE key='updated_at'"
                ).fetchone()
                or [0]
            )[0]
        ),
    }


def status():
    stats = {
        "papers": 0,
        "mapped_papers": 0,
        "topics": 0,
        "passages": 0,
        "findings": 0,
        "papers_with_findings": 0,
        "checked_chunks": 0,
        "updated_at": 0,
    }
    signature = None
    if Path(KNOWLEDGE_DB_PATH).exists():
        with closing(connect()) as conn:
            stats = _stats(conn)
            signature = (
                conn.execute(
                    "SELECT value FROM kg_meta WHERE key='source_signature'"
                ).fetchone()
                or [None]
            )[0]
    if Path(DB_PATH).exists():
        with closing(source_connection()) as source:
            stats["library_papers"] = source.execute(
                "SELECT count(*) FROM papers"
            ).fetchone()[0]
    else:
        stats["library_papers"] = 0
    stats["needs_refresh"] = (
        stats["library_papers"] != stats["papers"] or signature != source_signature()
    )
    return stats


def _scope(conn, q="", year_from=None, year_to=None):
    papers = {
        row["paper_id"]: dict(row)
        for row in conn.execute("SELECT * FROM kg_papers ORDER BY paper_id")
    }
    papers = {
        pid: p
        for pid, p in papers.items()
        if (year_from is None or (p["year"] is not None and p["year"] >= year_from))
        and (year_to is None or (p["year"] is not None and p["year"] <= year_to))
    }
    memberships = defaultdict(dict)
    for row in conn.execute(
        "SELECT topic_id,paper_id,MAX(strength) strength FROM kg_mentions GROUP BY topic_id,paper_id"
    ):
        if row["paper_id"] in papers and row["topic_id"] in TOPIC_BY_ID:
            memberships[row["topic_id"]][row["paper_id"]] = row["strength"]
    if q.strip():
        normalized = normalize(q).lstrip("@")
        matches = set(topic_matches(q))
        matches |= {
            tid
            for tid, t in TOPIC_BY_ID.items()
            if normalized in normalize(t["name"])
            or any(normalized in normalize(a) for a in t["aliases"])
        }
        ids = {pid for tid in matches for pid in memberships[tid]}
        ids |= {
            pid
            for pid, p in papers.items()
            if normalized
            in normalize(
                " ".join(
                    str(p.get(k) or "")
                    for k in ("title", "authors", "citation_key", "abstract")
                )
            )
        }
        papers = {pid: p for pid, p in papers.items() if pid in ids}
        memberships = {
            tid: {pid: s for pid, s in values.items() if pid in papers}
            for tid, values in memberships.items()
        }
    return papers, {tid: values for tid, values in memberships.items() if values}


def _paper_label(paper):
    return "@" + paper["citation_key"] if paper["citation_key"] else paper["title"][:35]


def _topic_node(tid, values):
    topic = TOPIC_BY_ID[tid]
    return {
        "id": "topic:" + tid,
        "name": topic["name"],
        "type": "Topic",
        "category": topic["category"],
        "color": CATEGORY_COLORS[topic["category"]],
        "weight": len(values),
        "paper_count": len(values),
    }


def _paper_node(paper):
    return {
        "id": "paper:" + paper["paper_id"],
        "name": _paper_label(paper),
        "title": paper["title"],
        "type": "Paper",
        "category": "Paper",
        "year": paper["year"],
        "color": CATEGORY_COLORS["Paper"],
        "weight": 1,
        "paper_id": paper["paper_id"],
    }


def research_map(
    q="", focus="", category="", year_from=None, year_to=None, min_papers=2, limit=36
):
    if not Path(KNOWLEDGE_DB_PATH).exists():
        return {
            "nodes": [],
            "edges": [],
            "topics": [],
            "bridges": [],
            "comparisons": [],
            "gaps": [],
            "stats": status(),
            "scope_papers": 0,
            "shown_papers": 0,
        }
    with closing(connect()) as conn:
        papers, memberships = _scope(conn, q, year_from, year_to)
        if focus.startswith("topic:"):
            ids = set(memberships.get(focus[6:], {}))
            papers = {pid: p for pid, p in papers.items() if pid in ids}
        elif focus.startswith("paper:"):
            pid = focus[6:]
            related = {tid for tid, values in memberships.items() if pid in values}
            ids = {other for tid in related for other in memberships[tid]}
            papers = {other: p for other, p in papers.items() if other in ids}
        memberships = {
            tid: {pid: s for pid, s in values.items() if pid in papers}
            for tid, values in memberships.items()
        }
        memberships = {tid: values for tid, values in memberships.items() if values}
        total = max(len(papers), 1)
        eligible = [
            tid
            for tid, values in memberships.items()
            if len(values) >= min_papers
            and (not category or TOPIC_BY_ID[tid]["category"] == category)
        ]

        # Specific topics beat ubiquitous hubs; the selected topic stays visible.
        def topic_score(tid):
            n = len(memberships[tid])
            return math.sqrt(n) * math.log(1 + total / n)

        query_topics = set(topic_matches(q))
        eligible.sort(
            key=lambda tid: (
                tid not in query_topics,
                -topic_score(tid),
                TOPIC_BY_ID[tid]["name"],
            )
        )
        if focus.startswith("topic:") and focus[6:] in eligible:
            eligible.remove(focus[6:])
            eligible.insert(0, focus[6:])
        chosen = eligible[: min(14, limit)]
        scores = Counter()
        paper_topics = defaultdict(set)
        for tid in chosen:
            specificity = math.log(1 + total / len(memberships[tid]))
            for pid, strength in memberships[tid].items():
                scores[pid] += specificity * strength
                paper_topics[pid].add(tid)
        ordered = sorted(
            scores, key=lambda pid: (-scores[pid], -(papers[pid]["year"] or 0), pid)
        )
        # Pick a representative for every displayed topic before filling by rank.
        selected = []
        if focus.startswith("paper:") and focus[6:] in scores:
            selected.append(focus[6:])
        for tid in chosen:
            if any(pid in memberships[tid] for pid in selected):
                continue
            candidate = next(
                (
                    pid
                    for pid in ordered
                    if pid in memberships[tid] and pid not in selected
                ),
                None,
            )
            if candidate and len(selected) < limit:
                selected.append(candidate)
        selected += [pid for pid in ordered if pid not in selected][
            : max(0, limit - len(selected))
        ]
        nodes = [_topic_node(tid, memberships[tid]) for tid in chosen]
        nodes += [_paper_node(papers[pid]) for pid in selected]
        edges = [
            {
                "id": tid + ":" + pid,
                "source": "topic:" + tid,
                "target": "paper:" + pid,
                "relation": "mentions",
                "weight": strength,
                "kind": "mention",
                "description": "Explicit topic mention; inspect to read the source.",
            }
            for tid in chosen
            for pid, strength in memberships[tid].items()
            if pid in selected
        ]
        edges = _readable_edges(edges)
        topics = [
            {
                **TOPIC_BY_ID[tid],
                "paper_count": len(memberships[tid]),
                "id": "topic:" + tid,
            }
            for tid in eligible
        ]
        # Cross-category papers are reading candidates, not inferred discoveries.
        bridges = []
        for pid in ordered:
            tids = paper_topics[pid]
            categories = {TOPIC_BY_ID[tid]["category"] for tid in tids}
            if len(categories) >= 3:
                bridges.append(
                    {
                        **_paper_node(papers[pid]),
                        "topics": [TOPIC_BY_ID[t]["name"] for t in sorted(tids)],
                        "category_count": len(categories),
                    }
                )
                if len(bridges) == 6:
                    break
        gaps = _coverage_pairs(memberships)
        claim_topics = (
            {focus[6:]} if focus.startswith("topic:") else set(topic_matches(q))
        )
        comparisons = _comparisons(conn, set(papers), claim_topics)
        return {
            "nodes": nodes,
            "edges": edges,
            "topics": topics,
            "bridges": bridges,
            "gaps": gaps,
            "comparisons": comparisons,
            "scope_papers": len(papers),
            "shown_papers": len(selected),
            "stats": _stats(conn),
        }


def _readable_edges(edges):
    """Show strong links while retaining all genuine component connections.

    The inspector retains the full memberships. The map starts with three links
    per paper, then a spanning forest keeps weaker but essential bridges visible.
    No connection is added unless it already exists in source mentions.
    """
    ordered = sorted(edges, key=lambda edge: (-edge["weight"], edge["id"]))
    parent = {}

    def root(node):
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    selected = {}
    count = Counter()
    for edge in ordered:
        if count[edge["target"]] < 3:
            selected[edge["id"]] = edge
            count[edge["target"]] += 1
            parent[root(edge["source"])] = root(edge["target"])
    for edge in ordered:
        a, b = root(edge["source"]), root(edge["target"])
        if a != b:
            selected[edge["id"]] = edge
            parent[a] = b
    return list(selected.values())


def _coverage_pairs(memberships):
    # Only specific, reasonably represented topics. Zero co-mentions is a library
    # coverage gap, never proof that a scientific combination is unstudied.
    eligible = sorted(
        (tid for tid, values in memberships.items() if len(values) >= 3),
        key=lambda tid: (len(memberships[tid]), tid),
    )
    pairs = []
    for left, right in itertools.combinations(eligible, 2):
        a, b = TOPIC_BY_ID[left], TOPIC_BY_ID[right]
        if a["category"] == b["category"] or not (
            {a["category"], b["category"]}
            & {"Characterization", "Generation", "Applications"}
        ):
            continue
        overlap = set(memberships[left]) & set(memberships[right])
        if not overlap:
            pairs.append(
                {
                    "left": "topic:" + left,
                    "right": "topic:" + right,
                    "name": a["name"] + " + " + b["name"],
                    "left_count": len(memberships[left]),
                    "right_count": len(memberships[right]),
                    "shared_papers": 0,
                }
            )
    return pairs[:5]


def _comparisons(conn, allowed, topic_ids=None):
    pairs = defaultdict(list)
    for row in conn.execute(
        "SELECT c.*,p.title,p.citation_key,p.year FROM kg_claims c JOIN kg_papers p USING(paper_id) WHERE relation IN ('increases','decreases','no_detected_effect') ORDER BY c.created_at DESC"
    ):
        if row["paper_id"] in allowed and (
            not topic_ids or set(topic_matches(row["quote"])) & topic_ids
        ):
            pairs[(row["source_key"], row["target_key"])].append(dict(row))
    result = []
    for claims in pairs.values():
        if (
            len({c["relation"] for c in claims}) > 1
            and len({c["paper_id"] for c in claims}) > 1
        ):
            representatives = []
            relations, papers = set(), set()
            for claim in claims:
                if claim["relation"] not in relations:
                    representatives.append(claim)
                    relations.add(claim["relation"])
                    papers.add(claim["paper_id"])
            for claim in claims:
                if claim["paper_id"] not in papers:
                    representatives.append(claim)
                    papers.add(claim["paper_id"])
                if len(representatives) >= 8:
                    break
            result.append(
                {
                    "source": claims[0]["source"],
                    "target": claims[0]["target"],
                    "claims": representatives,
                    "label": "Different reported effects — compare conditions",
                }
            )
    return result[:8]


def inspect_node(
    node_id, *, q="", year_from=None, year_to=None, paper_offset=0, paper_limit=20
):
    with closing(connect()) as conn:
        papers, memberships = _scope(conn, q, year_from, year_to)
        if node_id.startswith("topic:") and node_id[6:] in TOPIC_BY_ID:
            tid = node_id[6:]
            pids = set(memberships.get(tid, {}))
            node = _topic_node(tid, {pid: 1 for pid in pids})
            clause, params = "m.topic_id=?", [tid]
        elif node_id.startswith("paper:") and node_id[6:] in papers:
            pid = node_id[6:]
            pids = {pid}
            node = {
                **_paper_node(papers[pid]),
                "abstract": papers[pid]["abstract"],
                "authors": papers[pid]["authors"],
                "doi": papers[pid]["doi"],
            }
            clause, params = "m.paper_id=?", [pid]
        else:
            raise KeyError("This topic or paper is not in the current map.")
        rows = conn.execute(
            "SELECT m.*,p.title,p.citation_key,p.year FROM kg_mentions m JOIN kg_papers p USING(paper_id) WHERE "
            + clause
            + " ORDER BY strength DESC,p.year DESC,m.paper_id,m.chunk_id",
            params,
        )
        passages = []
        counts = Counter()
        seen = set()
        for row in rows:
            if (
                row["paper_id"] not in pids
                or counts[row["paper_id"]] >= 2
                or (row["paper_id"], row["chunk_id"]) in seen
            ):
                continue
            passages.append(dict(row))
            counts[row["paper_id"]] += 1
            seen.add((row["paper_id"], row["chunk_id"]))
            if len(passages) >= 16:
                break
        related = []
        if node_id.startswith("paper:"):
            pid = node_id[6:]
            own = {tid for tid, values in memberships.items() if pid in values}
            scores = Counter()
            common = defaultdict(list)
            for tid in own:
                for other in memberships[tid]:
                    if other != pid:
                        scores[other] += math.log(
                            1 + max(len(papers), 1) / len(memberships[tid])
                        )
                        common[other].append(TOPIC_BY_ID[tid]["name"])
            related = [
                {**_paper_node(papers[pid]), "shared_topics": sorted(common[pid])}
                for pid, _ in scores.most_common(8)
            ]
        claims = [
            dict(row)
            for row in conn.execute(
                "SELECT c.*,p.title,p.citation_key,p.year FROM kg_claims c JOIN kg_papers p USING(paper_id) ORDER BY c.created_at DESC"
            )
            if row["paper_id"] in pids
            and (
                not node_id.startswith("topic:")
                or node_id[6:] in topic_matches(row["quote"])
            )
        ][:30]
        node["paper_count"] = len(pids)
        ordered_papers = sorted(
            pids,
            key=lambda pid: (-(papers[pid]["year"] or 0), papers[pid]["title"], pid),
        )
        return {
            "node": node,
            "passages": passages,
            "related": related,
            "claims": claims,
            "topics": [
                _topic_node(tid, values)
                for tid, values in memberships.items()
                if set(values) & pids
            ],
            "paper_ids": sorted(pids),
            "papers": [
                _paper_node(papers[pid])
                for pid in ordered_papers[paper_offset : paper_offset + paper_limit]
            ],
            "next_paper_offset": paper_offset + paper_limit
            if paper_offset + paper_limit < len(pids)
            else None,
        }


def candidate_chunks(source, query, limit, paper_ids=None):
    """Bounded source passages for matching topics, scoped before applying limit."""
    topics = set(topic_matches(query))
    if not topics or not Path(KNOWLEDGE_DB_PATH).exists():
        return []
    with closing(connect()) as conn:
        sql = (
            "SELECT chunk_id,paper_id,COUNT(DISTINCT topic_id) matches,MAX(strength) score FROM kg_mentions WHERE topic_id IN ("
            + ",".join("?" for _ in topics)
            + ") AND chunk_id!=''"
        )
        params = sorted(topics)
        if paper_ids:
            sql += " AND paper_id IN (" + ",".join("?" for _ in paper_ids) + ")"
            params += list(paper_ids)
        sql += " GROUP BY chunk_id,paper_id ORDER BY matches DESC,score DESC,chunk_id LIMIT ?"
        ids, per_paper = [], Counter()
        candidates = conn.execute(sql, [*params, max(limit * 10, 50)]).fetchall()
        for row in candidates:
            if per_paper[row["paper_id"]] < 3:
                ids.append(row["chunk_id"])
                per_paper[row["paper_id"]] += 1
                if len(ids) >= limit:
                    break
    if not ids:
        return []
    valid = {
        row[0]
        for row in source.execute(
            "SELECT chunk_id FROM chunks WHERE chunk_id IN ("
            + ",".join("?" for _ in ids)
            + ")",
            ids,
        )
    }
    return [cid for cid in ids if cid in valid]


def remove_paper(paper_id):
    if Path(KNOWLEDGE_DB_PATH).exists():
        with closing(connect(write=True)) as conn, conn:
            conn.execute("DELETE FROM kg_papers WHERE paper_id=?", (paper_id,))
