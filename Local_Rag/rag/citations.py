"""Citation catalog for the writing workspace.

The RAG ``papers`` table remains the source of indexed documents.  This module
adds a small, metadata-oriented catalog with stable human-friendly keys and
aliases, so the editor can use ``@smith2024nanobubbles`` instead of a long
opaque paper id.  Imports are parsed into reviewable proposals; no ambiguous
record is silently merged.
"""
from __future__ import annotations

import difflib
import json
import re
import sqlite3
import time
import unicodedata
import uuid
from pathlib import Path
from typing import Any

from config import DB_PATH, DATA_DIR


DDL = """
CREATE TABLE IF NOT EXISTS citation_catalog (
    citation_key TEXT PRIMARY KEY,
    paper_id TEXT UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    authors TEXT NOT NULL DEFAULT '',
    year INTEGER,
    doi TEXT NOT NULL DEFAULT '',
    journal TEXT NOT NULL DEFAULT '',
    volume TEXT NOT NULL DEFAULT '',
    issue TEXT NOT NULL DEFAULT '',
    pages TEXT NOT NULL DEFAULT '',
    publisher TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    abstract TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'rag',
    external_id TEXT NOT NULL DEFAULT '',
    aliases_json TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 1.0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_citation_catalog_title ON citation_catalog(title);
CREATE INDEX IF NOT EXISTS idx_citation_catalog_doi ON citation_catalog(doi);
CREATE TABLE IF NOT EXISTS citation_imports (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    filename TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    record_count INTEGER NOT NULL DEFAULT 0,
    matched_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS citation_import_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id TEXT NOT NULL REFERENCES citation_imports(id) ON DELETE CASCADE,
    external_key TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    proposed_key TEXT,
    paper_id TEXT,
    score REAL NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'review'
);
CREATE INDEX IF NOT EXISTS idx_citation_import_matches_batch ON citation_import_matches(import_id);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='papers'").fetchone():
        have_papers = {r[1] for r in conn.execute("PRAGMA table_info(papers)").fetchall()}
        for col in ("journal", "volume", "issue", "pages", "publisher", "url", "abstract"):
            if col not in have_papers:
                conn.execute(f"ALTER TABLE papers ADD COLUMN {col} TEXT")
    conn.executescript(DDL)
    have = {r[1] for r in conn.execute("PRAGMA table_info(citation_import_matches)").fetchall()}
    if "record_json" not in have:
        conn.execute("ALTER TABLE citation_import_matches ADD COLUMN record_json TEXT NOT NULL DEFAULT '{}' ")
    have_catalog = {r[1] for r in conn.execute("PRAGMA table_info(citation_catalog)").fetchall()}
    for col in ("volume", "issue", "pages", "publisher"):
        if col not in have_catalog:
            conn.execute(f"ALTER TABLE citation_catalog ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
    conn.commit()
    return conn


def init_db() -> None:
    conn = _conn()
    conn.close()


def _norm(value: Any) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _doi(value: Any) -> str:
    s = str(value or "").strip().lower()
    s = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", s)
    return s.rstrip(" .;)")


def _author_family(authors: str) -> str:
    first = re.split(r"\s*(?:;|\band\b|\|)\s*", authors or "", maxsplit=1, flags=re.I)[0].strip()
    if "," in first:
        first = first.split(",", 1)[0]
    else:
        first = first.split()[-1] if first.split() else ""
    return re.sub(r"[^a-z0-9]", "", _norm(first).replace(" ", ""))


def make_key(title: str, authors: str = "", year: Any = None, taken: set[str] | None = None) -> str:
    """Generate a deterministic, readable citation key and avoid collisions."""
    family = _author_family(authors)
    y = str(year) if year else ""
    words = [w for w in _norm(title).split() if w not in {"the", "a", "an", "of", "and", "in", "for", "on"}]
    stem = "".join(words[:3])[:34] or "reference"
    base = f"{family}{y}{stem}" if family else f"{y}{stem}"
    base = re.sub(r"[^A-Za-z0-9]", "", base)[:48] or "reference"
    if taken is None:
        return base
    candidate = base
    suffix = 2
    while candidate in taken:
        candidate = f"{base}{suffix}"
        suffix += 1
    return candidate


def _aliases(row: sqlite3.Row | dict[str, Any]) -> list[str]:
    raw = row.get("aliases_json", "[]") if isinstance(row, dict) else row["aliases_json"]
    try:
        result = json.loads(raw or "[]")
        return [str(x) for x in result if x]
    except Exception:
        return []


def sync_rag_papers(force: bool = False) -> int:
    """Idempotently add/update indexed papers in the citation catalog."""
    if not DB_PATH.exists():
        return 0
    conn = _conn()
    rows = conn.execute("SELECT paper_id, title, authors, year, doi, journal, volume, issue, pages, publisher, url, abstract FROM papers").fetchall()
    # The catalog is queried on every autocomplete keystroke. Once all indexed
    # papers have a catalog row, avoid rewriting the table; an explicit sync at
    # startup (or after ingest) still fills newly added papers.
    paper_count = len(rows)
    catalog_count = conn.execute("SELECT COUNT(*) FROM citation_catalog WHERE paper_id IS NOT NULL").fetchone()[0]
    titles_changed = conn.execute("SELECT 1 FROM papers p JOIN citation_catalog c ON p.paper_id=c.paper_id WHERE COALESCE(p.title,'')<>COALESCE(c.title,'') LIMIT 1").fetchone()
    if not force and catalog_count >= paper_count and not titles_changed:
        conn.close()
        return 0
    existing = {r[0]: r[1] for r in conn.execute("SELECT paper_id, citation_key FROM citation_catalog WHERE paper_id IS NOT NULL")}
    keys = {r[0] for r in conn.execute("SELECT citation_key FROM citation_catalog")}
    now = time.time()
    count = 0
    for p in rows:
        pid, title, authors, year, doi, journal, volume, issue, pages, publisher, url, abstract = p
        title, authors, doi = title or "", authors or "", _doi(doi)
        journal, volume, issue, pages, publisher, url, abstract = (journal or "", volume or "", issue or "", pages or "", publisher or "", url or "", abstract or "")
        old_key = existing.get(pid)
        if old_key:
            conn.execute(
                "UPDATE citation_catalog SET title=CASE WHEN ?!='' THEN ? ELSE title END, authors=CASE WHEN ?!='' THEN ? ELSE authors END, year=COALESCE(?, year), doi=CASE WHEN ?!='' THEN ? ELSE doi END, journal=CASE WHEN ?!='' THEN ? ELSE journal END, volume=CASE WHEN ?!='' THEN ? ELSE volume END, issue=CASE WHEN ?!='' THEN ? ELSE issue END, pages=CASE WHEN ?!='' THEN ? ELSE pages END, publisher=CASE WHEN ?!='' THEN ? ELSE publisher END, url=CASE WHEN ?!='' THEN ? ELSE url END, abstract=CASE WHEN ?!='' THEN ? ELSE abstract END, updated_at=? WHERE paper_id=?",
                (title, title, authors, authors, year, doi, doi, journal, journal, volume, volume, issue, issue, pages, pages, publisher, publisher, url, url, abstract, abstract, now, pid),
            )
        else:
            key = make_key(title or pid, authors, year, keys)
            keys.add(key)
            aliases = [pid]
            if title and title != pid:
                aliases.append(title)
            conn.execute(
                "INSERT INTO citation_catalog (citation_key,paper_id,title,authors,year,doi,journal,volume,issue,pages,publisher,url,abstract,aliases_json,source,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (key, pid, title, authors, year, doi, journal, volume, issue, pages, publisher, url, abstract, json.dumps(aliases), "rag", now, now),
            )
        count += 1
    conn.commit()
    conn.close()
    return count


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["aliases"] = _aliases(d)
    d.pop("aliases_json", None)
    d["key"] = d["citation_key"]
    return d


def catalog_search(q: str, limit: int = 12) -> list[dict[str, Any]]:
    q = (q or "").strip()
    if not q or not DB_PATH.exists():
        return []
    sync_rag_papers()
    conn = _conn()
    like = f"%{q.replace('%', '').replace('_', '')}%"
    rows = conn.execute(
        "SELECT * FROM citation_catalog WHERE citation_key LIKE ? OR title LIKE ? OR authors LIKE ? OR doi LIKE ? OR paper_id LIKE ? OR aliases_json LIKE ? ORDER BY (year IS NULL), year DESC, title LIMIT ?",
        (like, like, like, like, like, like, max(1, min(int(limit), 50))),
    ).fetchall()
    out = [_row_dict(r) for r in rows]
    conn.close()
    return out


def resolve_key(token: str) -> dict[str, Any] | None:
    token = (token or "").strip().lstrip("@")
    if not token or not DB_PATH.exists():
        return None
    sync_rag_papers()
    conn = _conn()
    row = conn.execute("SELECT * FROM citation_catalog WHERE citation_key=? OR paper_id=?", (token, token)).fetchone()
    if not row:
        row = conn.execute("SELECT * FROM citation_catalog WHERE aliases_json LIKE ? LIMIT 1", (f'%"{token}"%',)).fetchone()
    conn.close()
    return _row_dict(row) if row else None


def render_bibtex(records: list[dict[str, Any]] | None = None) -> str:
    if records is None:
        sync_rag_papers()
        conn = _conn()
        records = [_row_dict(r) for r in conn.execute("SELECT * FROM citation_catalog ORDER BY citation_key").fetchall()]
        conn.close()
    lines = ["% Citation catalog — generated by LabUI", ""]
    for c in records:
        fields = []
        for name, value in (("author", c.get("authors")), ("title", c.get("title")), ("year", c.get("year")), ("journal", c.get("journal")), ("volume", c.get("volume")), ("number", c.get("issue")), ("pages", c.get("pages")), ("publisher", c.get("publisher")), ("doi", c.get("doi")), ("url", c.get("url"))):
            if value:
                # Escape outside the f-string: backslashes inside f-string
                # expressions are a SyntaxError before Python 3.12.
                escaped = str(value).replace('{', '\\{').replace('}', '\\}')
                fields.append(f"  {name:<10}= {{{escaped}}},")
        lines.append(f"@article{{{c.get('citation_key') or c.get('key') or 'reference'},")
        lines.extend(fields)
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


def _parse_bibtex(text: str) -> list[dict[str, Any]]:
    records = []
    for m in re.finditer(r"@\w+\s*\{\s*([^,]+),(.*?)(?=\n\s*@\w+\s*\{|\Z)", text or "", re.S):
        fields = {k.lower(): v.strip().strip("{}\" ") for k, v in re.findall(r"([A-Za-z][\w-]*)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\"|[^,\n]+)", m.group(2))}
        records.append({"external_key": m.group(1).strip(), "title": fields.get("title", ""), "authors": fields.get("author", ""), "year": _year(fields.get("year")), "doi": _doi(fields.get("doi")), "journal": fields.get("journal", fields.get("journaltitle", "")), "volume": fields.get("volume", ""), "issue": fields.get("number", fields.get("issue", "")), "pages": fields.get("pages", fields.get("page", "")), "publisher": fields.get("publisher", ""), "url": fields.get("url", "")})
    return records


def _parse_ris(text: str) -> list[dict[str, Any]]:
    out, cur = [], {}
    for line in (text or "").splitlines() + ["ER  -"]:
        m = re.match(r"^([A-Z0-9]{2})\s+-\s?(.*)$", line.strip())
        if not m:
            continue
        tag, value = m.group(1), m.group(2).strip()
        if tag == "ER":
            if cur:
                out.append({"external_key": cur.get("ID", ""), "title": cur.get("TI", cur.get("T1", "")), "authors": "; ".join(cur.get("AU", [])), "year": _year(cur.get("PY", cur.get("Y1"))), "doi": _doi(cur.get("DO")), "journal": cur.get("JO", cur.get("JF", "")), "volume": cur.get("VL", ""), "issue": cur.get("IS", ""), "pages": cur.get("SP", "") + ("-" + cur.get("EP", "") if cur.get("EP") else ""), "publisher": cur.get("PB", ""), "url": cur.get("UR", "")})
            cur = {}
        elif tag == "AU":
            cur.setdefault(tag, []).append(value)
        else:
            cur[tag] = value
    return out


def _year(value: Any) -> int | None:
    m = re.search(r"\b(19|20)\d{2}\b", str(value or ""))
    return int(m.group(0)) if m else None


def parse_import(text: str, fmt: str = "") -> list[dict[str, Any]]:
    fmt = (fmt or "").lower().lstrip(".")
    if fmt in {"json", "csl", "csl-json"} or text.lstrip().startswith("["):
        data = json.loads(text)
        if isinstance(data, dict): data = data.get("items", [data])
        out = []
        for r in data or []:
            names = []
            for a in r.get("author", []) or []:
                names.append(" ".join(filter(None, [a.get("family"), a.get("given")])) or a.get("literal", ""))
            out.append({"external_key": r.get("id", ""), "title": r.get("title", ""), "authors": "; ".join(names), "year": _year((r.get("issued", {}).get("date-parts", [[None]])[0] or [None])[0]), "doi": _doi(r.get("DOI", r.get("doi", ""))), "journal": r.get("container-title", ""), "volume": r.get("volume", ""), "issue": r.get("issue", ""), "pages": r.get("page", ""), "publisher": r.get("publisher", ""), "url": r.get("URL", "")})
        return out
    if fmt in {"ris", "research-info-systems"} or re.search(r"^TY\s+-", text, re.M):
        return _parse_ris(text)
    return _parse_bibtex(text)


def _match_record(r: dict[str, Any], catalog: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float, str]:
    rd, rt = _doi(r.get("doi")), _norm(r.get("title"))
    if rd:
        for c in catalog:
            if rd == _doi(c.get("doi")):
                return c, 1.0, "exact DOI"
    if rt:
        best, score = None, 0.0
        for c in catalog:
            ct = _norm(c.get("title"))
            if not ct: continue
            s = difflib.SequenceMatcher(None, rt, ct).ratio()
            if s > score: best, score = c, s
        if score >= 0.96: return best, score, "normalized title"
        if score >= 0.84: return best, score, "similar title — review"
    return None, 0.0, "no deterministic match"


def import_records(records: list[dict[str, Any]], source: str, filename: str = "") -> dict[str, Any]:
    sync_rag_papers()
    conn = _conn()
    catalog = [_row_dict(r) for r in conn.execute("SELECT * FROM citation_catalog").fetchall()]
    batch = "ci_" + uuid.uuid4().hex[:10]
    now = time.time()
    conn.execute("INSERT INTO citation_imports (id,source,filename,created_at,record_count) VALUES (?,?,?,?,?)", (batch, source, filename or "", now, len(records)))
    matches = []
    matched = 0
    for r in records:
        c, score, reason = _match_record(r, catalog)
        status = "matched" if c and score >= 0.96 else "review"
        if c and status == "matched": matched += 1
        proposed = c.get("citation_key") if c else make_key(r.get("title", "reference"), r.get("authors", ""), r.get("year"), {x.get("citation_key") for x in catalog})
        conn.execute("INSERT INTO citation_import_matches (import_id,external_key,title,proposed_key,paper_id,score,reason,status,record_json) VALUES (?,?,?,?,?,?,?,?,?)", (batch, r.get("external_key", ""), r.get("title", ""), proposed, c.get("paper_id") if c else None, score, reason, status, json.dumps(r, ensure_ascii=False)))
        matches.append({"external_key": r.get("external_key", ""), "title": r.get("title", ""), "proposed_key": proposed, "paper_id": c.get("paper_id") if c else None, "score": score, "reason": reason, "status": status})
    conn.execute("UPDATE citation_imports SET matched_count=? WHERE id=?", (matched, batch))
    conn.commit(); conn.close()
    return {"batch_id": batch, "record_count": len(records), "matched_count": matched, "matches": matches}


def import_file(data: bytes, filename: str = "") -> dict[str, Any]:
    text = data.decode("utf-8-sig", errors="replace")
    fmt = Path(filename or "").suffix
    records = parse_import(text, fmt)
    if not records:
        raise ValueError("no citation records recognized; use BibTeX, RIS, or CSL-JSON")
    return import_records(records, fmt.lstrip(".") or "bibtex", filename)


def import_batch(batch_id: str) -> dict[str, Any] | None:
    conn = _conn()
    b = conn.execute("SELECT * FROM citation_imports WHERE id=?", (batch_id,)).fetchone()
    if not b: conn.close(); return None
    ms = [dict(r) for r in conn.execute("SELECT * FROM citation_import_matches WHERE import_id=? ORDER BY id", (batch_id,)).fetchall()]
    conn.close()
    return {"batch": dict(b), "matches": ms}


def apply_import_batch(batch_id: str, include_review: bool = False) -> dict[str, Any]:
    """Apply exact/high-confidence matches; optionally approve review rows."""
    conn = _conn()
    rows = conn.execute("SELECT * FROM citation_import_matches WHERE import_id=? ORDER BY id", (batch_id,)).fetchall()
    if not rows:
        conn.close()
        raise ValueError("import batch not found or empty")
    added = updated = 0
    taken = {r[0] for r in conn.execute("SELECT citation_key FROM citation_catalog")}
    for row in rows:
        if row["status"] == "matched":
            allowed = True
        elif include_review and row["status"] == "review":
            allowed = True
        else:
            continue
        try: record = json.loads(row["record_json"] or "{}")
        except Exception: record = {}
        paper_id = row["paper_id"]
        now = time.time()
        if paper_id:
            # Fill missing metadata without replacing stronger existing values.
            conn.execute("UPDATE citation_catalog SET authors=CASE WHEN authors='' THEN ? ELSE authors END, year=COALESCE(year,?), doi=CASE WHEN doi='' THEN ? ELSE doi END, journal=CASE WHEN journal='' THEN ? ELSE journal END, url=CASE WHEN url='' THEN ? ELSE url END, updated_at=? WHERE paper_id=?", (record.get("authors", ""), record.get("year"), _doi(record.get("doi")), record.get("journal", ""), record.get("url", ""), now, paper_id))
            conn.execute("UPDATE citation_catalog SET volume=CASE WHEN volume='' THEN ? ELSE volume END, issue=CASE WHEN issue='' THEN ? ELSE issue END, pages=CASE WHEN pages='' THEN ? ELSE pages END, publisher=CASE WHEN publisher='' THEN ? ELSE publisher END WHERE paper_id=?", (record.get("volume", ""), record.get("issue", ""), record.get("pages", ""), record.get("publisher", ""), paper_id))
            # Keep the indexed paper card in sync with the catalog so existing
            # search/detail views become complete immediately after approval.
            conn.execute("UPDATE papers SET authors=CASE WHEN (authors IS NULL OR authors='') THEN ? ELSE authors END, year=COALESCE(year,?), doi=COALESCE(NULLIF(doi,''),?), journal=COALESCE(NULLIF(journal,''),?), volume=COALESCE(NULLIF(volume,''),?), issue=COALESCE(NULLIF(issue,''),?), pages=COALESCE(NULLIF(pages,''),?), publisher=COALESCE(NULLIF(publisher,''),?), url=COALESCE(NULLIF(url,''),?) WHERE paper_id=?", (record.get("authors", ""), record.get("year"), _doi(record.get("doi")), record.get("journal", ""), record.get("volume", ""), record.get("issue", ""), record.get("pages", ""), record.get("publisher", ""), record.get("url", ""), paper_id))
            if record.get("external_key"):
                current = conn.execute("SELECT aliases_json FROM citation_catalog WHERE paper_id=?", (paper_id,)).fetchone()
                aliases = json.loads(current[0] or "[]") if current else []
                if record["external_key"] not in aliases:
                    aliases.append(record["external_key"])
                    conn.execute("UPDATE citation_catalog SET aliases_json=? WHERE paper_id=?", (json.dumps(aliases), paper_id))
            updated += 1
        else:
            key = row["proposed_key"] or make_key(record.get("title", "reference"), record.get("authors", ""), record.get("year"), taken)
            if key in taken: key = make_key(record.get("title", "reference"), record.get("authors", ""), record.get("year"), taken)
            taken.add(key)
            conn.execute("INSERT OR IGNORE INTO citation_catalog (citation_key,title,authors,year,doi,journal,url,source,external_id,aliases_json,confidence,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (key, record.get("title", ""), record.get("authors", ""), record.get("year"), _doi(record.get("doi")), record.get("journal", ""), record.get("url", ""), "mendeley", record.get("external_key", ""), json.dumps([record.get("external_key", "")]), row["score"] or 0.0, now, now))
            added += 1
        conn.execute("UPDATE citation_import_matches SET status='applied' WHERE id=?", (row["id"],))
    conn.commit(); conn.close()
    return {"batch_id": batch_id, "applied": updated, "added": added}
