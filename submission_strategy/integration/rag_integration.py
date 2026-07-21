"""Manuscript context assembled from the JFR and local RAG databases."""

import json
import os
from pathlib import Path
import re
import sqlite3
import sys


RAG_ROOT = Path(__file__).resolve().parents[2] / "Local_Rag" / "rag"
RAG_DB_PATH = RAG_ROOT / "data" / "rag.db"
JFR_DB_PATH = (
    Path(os.environ.get("JFR_DATA_DIR") or Path.home() / ".local" / "share" / "jfr")
    / "db.sqlite"
)


def _search_text(manuscript: dict) -> str:
    techniques = []
    try:
        techniques = json.loads(manuscript.get("techniques_json") or "[]")
    except (json.JSONDecodeError, TypeError):
        pass
    parts = [str(item).strip() for item in techniques if str(item).strip()]
    if manuscript.get("abstract"):
        parts.append(manuscript["abstract"])
    return " ".join(parts).strip()


def _fts_query(text: str) -> str:
    terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", text.lower())
    unique_terms = list(dict.fromkeys(terms))[:8]
    return " OR ".join(f'"{term}"' for term in unique_terms)


def get_manuscript_context(ms_id: str) -> dict:
    """Return manuscript metadata, persistent paper links, and topical context."""
    from jfr.db.schema import init_db

    conn = init_db(JFR_DB_PATH)
    try:
        row = conn.execute("SELECT * FROM manuscript WHERE id=?", (ms_id,)).fetchone()
        if not row:
            return {"error": "Manuscript not found", "manuscript": None}
        manuscript = dict(row)
    finally:
        conn.close()

    from integration.linking import get_linked_papers

    linked_papers = get_linked_papers(ms_id)
    context_text = _search_text(manuscript)
    fts_query = _fts_query(context_text)
    topical_results = []

    if fts_query and RAG_DB_PATH.exists():
        rag_conn = sqlite3.connect(str(RAG_DB_PATH))
        rag_conn.row_factory = sqlite3.Row
        try:
            rows = rag_conn.execute(
                """
                SELECT c.chunk_id, c.paper_id, c.section_name, c.page_start,
                       c.page_end, c.text, p.title, p.authors, p.year
                FROM chunks_fts
                JOIN chunks c ON c.rowid = chunks_fts.rowid
                JOIN papers p ON p.paper_id = c.paper_id
                WHERE chunks_fts MATCH ?
                ORDER BY bm25(chunks_fts)
                LIMIT 20
                """,
                (fts_query,),
            ).fetchall()
        finally:
            rag_conn.close()

        seen = set()
        for row in rows:
            if row["paper_id"] in seen:
                continue
            seen.add(row["paper_id"])
            topical_results.append(dict(row))
            if len(topical_results) == 10:
                break

    graph_entities = []
    memories = []
    if context_text:
        if str(RAG_ROOT) not in sys.path:
            sys.path.insert(0, str(RAG_ROOT))
        try:
            from retrieval.graph import search_entities_fts

            graph_entities = search_entities_fts(context_text[:200], limit=20)
        except Exception:
            graph_entities = []
        try:
            from memory import get_all_memories

            memories = get_all_memories(limit=10)
        except Exception:
            memories = []

    return {
        "manuscript": manuscript,
        "linked_papers": linked_papers,
        "topical_results": topical_results,
        "graph_entities": graph_entities,
        "memories": memories,
        "rag_results": [
            {
                "source": "local_library",
                "papers": topical_results,
                "entities": graph_entities,
                "memories": memories,
            }
        ],
    }
