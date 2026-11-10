"""Replace one paper's unreadable passages after OCR and embeddings succeed.

Prepare the parsed JSON separately and inspect it first. This command snapshots
the index, stages all vectors, then swaps passages in one SQLite transaction.
Paper identity, PDF path, curated metadata, summaries, and other papers survive.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag/rag'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest.chunk import chunk_paper
from ingest.build_index import _insert_chunk, _insert_vec
from ingest.parse_pdfs import is_garbled
from retrieval.index_identity import ensure_compatible, profile
from tools.rebuild_embeddings import open_index


def replace_text(conn, parsed, vectors):
    chunks = chunk_paper(parsed)
    if not chunks or is_garbled(parsed['sections']):
        raise ValueError('OCR did not produce readable passages')
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.shape != (len(chunks), profile()['dimensions']) or not np.isfinite(vectors).all():
        raise ValueError('Invalid replacement vectors')
    if np.any(np.linalg.norm(vectors, axis=1) == 0):
        raise ValueError('Zero replacement vectors')
    ensure_compatible(conn)
    pid = parsed['paper_id']
    if not conn.execute('SELECT 1 FROM papers WHERE paper_id=?', (pid,)).fetchone():
        raise ValueError('Paper is not indexed')
    conn.execute('BEGIN IMMEDIATE')
    with conn:
        old_ids = [row[0] for row in conn.execute("SELECT chunk_id FROM chunks WHERE paper_id=? AND section_name!='Saved highlight'", (pid,))]
        conn.executemany('DELETE FROM chunks_vec WHERE chunk_id=?', [(cid,) for cid in old_ids])
        conn.executemany('DELETE FROM chunks WHERE chunk_id=?', [(cid,) for cid in old_ids])
        for chunk, vector in zip(chunks, vectors):
            _insert_chunk(conn, chunk)
            _insert_vec(conn, chunk['chunk_id'], vector)
        conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
    return len(chunks)


def run(parsed_file, backup_dir):
    from config import DB_PATH, PARSED_DIR
    from retrieval.embed import load_embed_model, embed_texts
    if not DB_PATH.is_file():
        raise ValueError('The configured library index does not exist')
    parsed = json.loads(parsed_file.read_text())
    if not parsed.get('sections') or is_garbled(parsed['sections']):
        raise ValueError('Replacement parse is empty or unreadable')
    backup_dir.mkdir(parents=True, exist_ok=True)
    conn = open_index(DB_PATH)
    try:
        if not conn.execute('SELECT 1 FROM papers WHERE paper_id=?', (parsed['paper_id'],)).fetchone():
            raise ValueError('Paper is not in the configured library')
        ensure_compatible(conn)
        with sqlite3.connect(backup_dir / ('before-ocr-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.sqlite')) as target:
            conn.backup(target)
        chunks = chunk_paper(parsed)
        model = load_embed_model()[1]
        # Everything remote happens before the write transaction.
        vectors = embed_texts(None, model, [chunk['embedded_text'] for chunk in chunks])
        count = replace_text(conn, parsed, vectors)
        destination = PARSED_DIR / (parsed['paper_id'] + '.json')
        if destination.exists():
            shutil.copy2(destination, backup_dir / destination.name)
        temporary = destination.with_suffix('.repair-tmp')
        temporary.write_text(json.dumps(parsed, ensure_ascii=False, indent=2))
        temporary.replace(destination)
        print(f"Repaired {parsed['paper_id']}: {count} readable passages")
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parsed-json', required=True, type=Path)
    parser.add_argument('--backup-dir', required=True, type=Path)
    args = parser.parse_args()
    run(args.parsed_json, args.backup_dir)
