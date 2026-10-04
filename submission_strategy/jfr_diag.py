"""Read-only diagnostic for the Journal-Fit Recommender vector store."""
import os, sqlite3
from pathlib import Path

base = Path(os.environ.get("JFR_DATA_DIR", Path.home() / ".local/share/jfr")).expanduser()
db_path = base / "db.sqlite"
vectors_dir = base / "vectors"

print(f"JFR_DATA_DIR : {base}")
print(f"db.sqlite    : {db_path}  (exists={db_path.exists()})")
print(f"vectors dir  : {vectors_dir}  (exists={vectors_dir.exists()})")
print("-" * 70)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
journals = conn.execute("SELECT id, name FROM journal ORDER BY id").fetchall()
print(f"Journals in DB: {len(journals)}")
print(f"corpus_article rows (all journals): {conn.execute('SELECT COUNT(*) FROM corpus_article').fetchone()[0]}")
print("-" * 70)

from qdrant_client import QdrantClient
qc = QdrantClient(path=str(vectors_dir))
try:
    existing = {c.name for c in qc.get_collections().collections}
    print(f"Qdrant collections present: {sorted(existing) or '(none)'}")
    print("-" * 70)
    print(f"{'journal_id':<24} {'sql_articles':>12} {'qdrant_points':>14}")
    for j in journals:
        jid = j["id"]; coll = f"journal_{jid}"
        n_sql = conn.execute(
            "SELECT COUNT(*) FROM corpus_article WHERE journal_id=? AND abstract IS NOT NULL AND abstract!=''",
            (jid,)).fetchone()[0]
        n_vec = qc.get_collection(coll).points_count if coll in existing else "MISSING"
        print(f"{jid:<24} {n_sql:>12} {str(n_vec):>14}")
finally:
    qc.close(); conn.close()