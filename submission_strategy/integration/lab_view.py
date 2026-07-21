"""Unified Research Lab views combining RAG and JFR data."""

import os
from pathlib import Path
import sqlite3
import sys


RAG_ROOT = Path(__file__).resolve().parents[2] / "Local_Rag" / "rag"
RAG_DB_PATH = RAG_ROOT / "data" / "rag.db"
MEMORY_DB_PATH = RAG_ROOT / "data" / "memory.db"
GRAPH_DB_PATH = RAG_ROOT / "data" / "graph.db"
JFR_DB_PATH = (
    Path(os.environ.get("JFR_DATA_DIR") or Path.home() / ".local" / "share" / "jfr")
    / "db.sqlite"
)


def _open_jfr_db() -> sqlite3.Connection:
    from jfr.db.schema import init_db

    return init_db(JFR_DB_PATH)


def _table_count(db_path: Path, table: str) -> int:
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def research_lab_view(query: str | None = None, ms_id: str | None = None) -> dict:
    """Return a unified research view for an optional query and manuscript."""
    manuscript_data = None
    manuscript_context = None

    if ms_id:
        conn = _open_jfr_db()
        try:
            row = conn.execute("SELECT * FROM manuscript WHERE id=?", (ms_id,)).fetchone()
            if row:
                from integration.linking import get_linked_papers

                manuscript_data = dict(row)
                manuscript_context = {
                    "manuscript": manuscript_data,
                    "linked_papers": get_linked_papers(ms_id),
                }
        finally:
            conn.close()

    rag_data = None
    if query:
        try:
            if str(RAG_ROOT) not in sys.path:
                sys.path.insert(0, str(RAG_ROOT))
            from memory import get_all_memories
            from retrieval.embed import embed_query, load_embed_model
            from retrieval.rerank import load_reranker
            from retrieval.search import search as rag_search

            tokenizer, embedder = load_embed_model()
            query_vector = embed_query(tokenizer, embedder, query)
            results = rag_search(
                query,
                query_vector,
                load_reranker(),
                top_k=20,
            )
            memories = get_all_memories(limit=10)
            rag_data = {
                "query": query,
                "results": results,
                "total": len(results),
                "graph": {
                    "nodes_count": _table_count(GRAPH_DB_PATH, "entities"),
                    "edges_count": _table_count(GRAPH_DB_PATH, "relations"),
                },
                "memories": [dict(memory) for memory in memories],
            }
        except Exception as exc:
            rag_data = {
                "error": f"RAG search failed: {exc}",
                "query": query,
                "results": [],
                "total": 0,
                "graph": {"nodes_count": 0, "edges_count": 0},
                "memories": [],
            }

    stats = get_research_lab_stats()
    return {
        "lab_view": {
            "query": query,
            "manuscript_id": ms_id,
            "manuscript": manuscript_data,
            "rag_data": rag_data,
            "stats": stats,
        },
        "template_data": {
            "lab_view": manuscript_context or rag_data or stats,
            "available_manuscripts": get_available_manuscripts(),
        },
    }


def research_lab_dashboard(ms_id: str) -> dict:
    """Return manuscript, literature links, journal, and submission context."""
    conn = _open_jfr_db()
    try:
        row = conn.execute("SELECT * FROM manuscript WHERE id=?", (ms_id,)).fetchone()
        if not row:
            return {
                "error": "Manuscript not found",
                "template_data": {
                    "manuscript": None,
                    "linked_papers": [],
                    "journal_stats": {},
                    "submissions": [],
                },
            }

        journals = conn.execute(
            "SELECT * FROM journal ORDER BY impact_factor DESC"
        ).fetchall()
        submissions = conn.execute(
            """
            SELECT s.*, j.name AS journal_name
            FROM submission s
            JOIN journal j ON s.journal_id = j.id
            WHERE s.manuscript_id=?
            ORDER BY s.created_at DESC
            """,
            (ms_id,),
        ).fetchall()
    finally:
        conn.close()

    from integration.linking import get_linked_papers

    impact_factors = [j["impact_factor"] for j in journals if j["impact_factor"] is not None]
    return {
        "template_data": {
            "manuscript": dict(row),
            "linked_papers": get_linked_papers(ms_id),
            "journal_stats": {
                "total": len(journals),
                "avg_if": (
                    sum(impact_factors) / len(impact_factors) if impact_factors else 0
                ),
            },
            "submissions": [dict(submission) for submission in submissions],
        }
    }


def get_research_lab_stats() -> dict:
    """Return live statistics from each LabUI database."""
    conn = _open_jfr_db()
    try:
        manuscripts = conn.execute("SELECT COUNT(*) FROM manuscript").fetchone()[0]
        submissions = conn.execute("SELECT COUNT(*) FROM submission").fetchone()[0]
        active_submissions = conn.execute(
            """
            SELECT COUNT(*) FROM submission
            WHERE current_state NOT IN ('accepted', 'rejected_desk',
                                        'rejected_post_review', 'withdrawn')
            """
        ).fetchone()[0]
    finally:
        conn.close()

    papers = _table_count(RAG_DB_PATH, "papers")
    chunks = _table_count(RAG_DB_PATH, "chunks")
    memories = _table_count(MEMORY_DB_PATH, "memories")
    entities = _table_count(GRAPH_DB_PATH, "entities")
    relations = _table_count(GRAPH_DB_PATH, "relations")
    return {
        "manuscripts": manuscripts,
        "submissions": submissions,
        "active_submissions": active_submissions,
        "rag": {
            "papers_indexed": papers,
            "chunks_indexed": chunks,
            "total_entities": entities,
            "total_memories": memories,
        },
        "graph": {"entities": entities, "relations": relations},
        "library": {"papers": papers, "chunks": chunks},
    }


def get_available_manuscripts() -> list[dict]:
    """Return manuscripts available to the Research Lab selector."""
    conn = _open_jfr_db()
    try:
        rows = conn.execute(
            "SELECT id, title, created_at FROM manuscript ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
