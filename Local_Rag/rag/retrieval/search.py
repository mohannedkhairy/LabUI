"""
Hybrid retrieval: title + BM25 + dense + graph, fused before reranking.
"""
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    DB_PATH,
    BM25_TOP_N, DENSE_TOP_N, RRF_K, RERANK_TOP_N,
    FINAL_TOP_K, MAX_PER_PAPER, MIN_DIVERSE,
)


def _open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.enable_load_extension(True)
    import sqlite_vec
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.row_factory = sqlite3.Row
    return conn


def _sanitize_fts(query: str) -> str:
    """Turn free text into a safe FTS5 query: each token individually quoted
    and OR-joined. Quoting the whole query as one phrase (the old behaviour)
    only matched chunks containing the words consecutively, so the BM25 arm
    returned nothing for most natural-language questions."""
    tokens = re.findall(r"\w+", query)
    return " OR ".join(f'"{t}"' for t in tokens) if tokens else '""'


def _title_search(conn: sqlite3.Connection, query: str, top_n: int,
                  selected_paper_ids: list[str] = None) -> list[str]:
    """Retrieve passages from matching paper titles, even if absent in the body.

    Uses canonical metadata directly, so a recovered title is searchable
    immediately without rebuilding the PDF's embeddings.
    """
    stopwords = {'a', 'an', 'the', 'and', 'or', 'of', 'on', 'in', 'for', 'to',
                 'with', 'from', 'by', 'how', 'what', 'is', 'are', 'does', 'do',
                 'find', 'paper', 'papers', 'about', 'called'}
    terms = list(dict.fromkeys(t for t in re.findall(r'\w+', query.casefold()) if t not in stopwords))
    if not terms or len(terms) > 20:
        return []
    clauses = ["lower(p.title) LIKE ? ESCAPE '\\'" for _ in terms]
    params = ['%' + term.replace('_', '\\_') + '%' for term in terms]
    if selected_paper_ids:
        clauses.append('p.paper_id IN (' + ','.join('?' for _ in selected_paper_ids) + ')')
        params.extend(selected_paper_ids)
    params.append(top_n)
    rows = conn.execute(
        'SELECT c.chunk_id FROM chunks c JOIN papers p USING(paper_id) WHERE '
        + ' AND '.join(clauses) + ' ORDER BY c.position, c.chunk_id LIMIT ?', params,
    ).fetchall()
    return [r['chunk_id'] for r in rows]


def _bm25_search(conn: sqlite3.Connection, query: str, top_n: int, selected_paper_ids: list[str] = None) -> list[str]:
    """Return chunk_ids ranked by BM25."""
    fts_query = _sanitize_fts(query)
    filter_clause = ""
    params = [fts_query]
    
    if selected_paper_ids:
        placeholders = ",".join("?" * len(selected_paper_ids))
        filter_clause = f" AND c.paper_id IN ({placeholders}) "
        params.extend(selected_paper_ids)
    
    params.append(top_n)

    try:
        rows = conn.execute(
            f"""
            SELECT c.chunk_id
            FROM chunks_fts f
            JOIN chunks c ON c.chunk_id = f.chunk_id
            WHERE chunks_fts MATCH ? {filter_clause}
            ORDER BY rank
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
        return [r["chunk_id"] for r in rows]
    except sqlite3.OperationalError:
        # Fallback: try unquoted query
        plain = re.sub(r'[^\w\s]', ' ', query).strip()
        if not plain:
            return []
        try:
            plain_params = [plain]
            if selected_paper_ids:
                plain_params.extend(selected_paper_ids)
            plain_params.append(top_n)
            
            rows = conn.execute(
                f"""
                SELECT c.chunk_id
                FROM chunks_fts f
                JOIN chunks c ON c.chunk_id = f.chunk_id
                WHERE chunks_fts MATCH ? {filter_clause}
                ORDER BY rank
                LIMIT ?
                """,
                tuple(plain_params),
            ).fetchall()
            return [r["chunk_id"] for r in rows]
        except Exception:
            return []


def _dense_search(
    conn: sqlite3.Connection, query_vec: np.ndarray, top_n: int, selected_paper_ids: list[str] = None
) -> list[str]:
    """Return chunk_ids ranked by cosine similarity via sqlite-vec."""
    from retrieval.index_identity import ensure_compatible
    ensure_compatible(conn, len(query_vec))
    vec_bytes = query_vec.astype(np.float32).tobytes()
    filter_clause = ""
    params = [vec_bytes, top_n]

    if selected_paper_ids:
        # Constrain the KNN itself (sqlite-vec supports IN on the primary key).
        # Filtering with a JOIN after the fact discards selected-paper chunks
        # that fall outside the *global* top-k, returning few or no results
        # once the library outgrows k.
        ph = ",".join("?" * len(selected_paper_ids))
        chunk_ids = [
            r[0] for r in conn.execute(
                f"SELECT chunk_id FROM chunks WHERE paper_id IN ({ph})",
                selected_paper_ids,
            )
        ]
        if not chunk_ids:
            return []
        vph = ",".join("?" * len(chunk_ids))
        filter_clause = f" AND v.chunk_id IN ({vph}) "
        params.extend(chunk_ids)

    try:
        rows = conn.execute(
            f"""
            SELECT v.chunk_id
            FROM chunks_vec v
            WHERE v.embedding MATCH ?
              AND v.k = ?
              {filter_clause}
            ORDER BY v.distance
            """,
            tuple(params),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        # Missing/empty index (fresh install) — degrade like _bm25_search does.
        if 'no such table' in str(exc).lower():
            return []
        raise
    return [r["chunk_id"] for r in rows]


def _rrf(lists: list[list[str]], k: int = RRF_K) -> list[str]:
    """Reciprocal Rank Fusion over multiple ranked lists."""
    scores: dict[str, float] = {}
    for ranked in lists:
        for rank, chunk_id in enumerate(ranked, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda x: -scores[x])


def _graph_search(conn, query, top_n, selected_paper_ids=None):
    from retrieval.knowledge import candidate_chunks
    try:
        evidence = candidate_chunks(conn, query, top_n, selected_paper_ids)
        if evidence:
            return evidence
    except sqlite3.Error:
        pass
    from retrieval.graph import GRAPH_DB_PATH, search_entities_fts, expand_entity_neighbors, get_chunks_for_entities
    if not GRAPH_DB_PATH.exists():
        return []
    try:
        seeds = search_entities_fts(query, limit=10)
        entities = expand_entity_neighbors([entity['entity_id'] for entity in seeds], hops=1)
        ids = get_chunks_for_entities([entity['entity_id'] for entity in entities], limit=top_n)
        if not ids:
            return []
        sql = 'SELECT chunk_id FROM chunks WHERE chunk_id IN (' + ','.join('?' for _ in ids) + ')'
        params = list(ids)
        if selected_paper_ids:
            sql += ' AND paper_id IN (' + ','.join('?' for _ in selected_paper_ids) + ')'
            params.extend(selected_paper_ids)
        allowed = {row[0] for row in conn.execute(sql, params)}
        return [cid for cid in ids if cid in allowed]
    except sqlite3.Error:
        return []


def _fetch_chunks(conn: sqlite3.Connection, chunk_ids: list[str]) -> list[dict]:
    if not chunk_ids:
        return []
    placeholders = ",".join("?" * len(chunk_ids))
    rows = conn.execute(
        f"""
        SELECT c.chunk_id, c.paper_id, c.section_name, c.page_start, c.page_end, c.text,
               p.title, p.authors, p.year, p.doi, p.journal, p.url, p.abstract
        FROM chunks c
        JOIN papers p ON p.paper_id = c.paper_id
        WHERE c.chunk_id IN ({placeholders})
        """,
        chunk_ids,
    ).fetchall()
    # Preserve order from chunk_ids list
    by_id = {r["chunk_id"]: dict(r) for r in rows}
    return [by_id[cid] for cid in chunk_ids if cid in by_id]


def _diversify(chunks: list[dict], max_per_paper: int, min_total: int) -> list[dict]:
    """Cap results per paper to avoid one paper dominating."""
    counts: dict[str, int] = {}
    primary, overflow = [], []
    for c in chunks:
        pid = c["paper_id"]
        if counts.get(pid, 0) < max_per_paper:
            primary.append(c)
            counts[pid] = counts.get(pid, 0) + 1
        else:
            overflow.append(c)

    if len(primary) < min_total:
        needed = min_total - len(primary)
        primary.extend(overflow[:needed])

    return primary


def search(
    query: str,
    query_vec: np.ndarray,
    reranker,
    top_k: int = FINAL_TOP_K,
    selected_paper_ids: list[str] = None,
) -> list[dict]:
    """
    Full hybrid retrieval pipeline.
    query_vec: normalized float32 vector from the configured embedding model.
    reranker: configured relevance scorer from retrieval.rerank.
    Returns list of chunk dicts with metadata.
    """
    from retrieval.rerank import rerank as do_rerank

    conn = _open_db()

    try:
        title_ids = _title_search(conn, query, BM25_TOP_N, selected_paper_ids)
        bm25_ids  = _bm25_search(conn, query, BM25_TOP_N, selected_paper_ids)
        dense_ids = _dense_search(conn, query_vec, DENSE_TOP_N, selected_paper_ids)
        graph_ids = _graph_search(conn, query, RERANK_TOP_N, selected_paper_ids)
        fused_ids = _rrf([title_ids, bm25_ids, dense_ids, graph_ids])[:RERANK_TOP_N]
        candidates = _fetch_chunks(conn, fused_ids)
    finally:
        conn.close()

    if not candidates:
        return []

    reranked = do_rerank(reranker, query, candidates, top_n=top_k * 2)
    diversified = _diversify(reranked, MAX_PER_PAPER, MIN_DIVERSE)
    return diversified[:top_k]
