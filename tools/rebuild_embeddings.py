"""Stage replacement vectors without changing live search, then activate offline.

Run with the TARGET embedding settings in the environment. `--activate` must
run with the app and ingestion writers stopped, after a final staging catch-up.
It validates all source hashes and atomically replaces only derived vectors.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

import numpy as np
import sqlite_vec

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag/rag'))
from retrieval.index_identity import profile, write_profile


def open_index(path):
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def inputs(conn):
    rows = conn.execute('''SELECT c.chunk_id,c.text,c.section_name,p.title
        FROM chunks c JOIN papers p USING(paper_id) ORDER BY c.chunk_id''').fetchall()
    result = []
    for row in rows:
        text = row['text'] if row['section_name'] == 'Saved highlight' else f"[{row['title']} — {row['section_name']}]\n{row['text']}"
        result.append((row['chunk_id'], text, hashlib.sha256(text.encode()).hexdigest()))
    return result


def stage(source, destination, batch_size=8, encoder=None):
    from retrieval.embed import load_embed_model, embed_texts
    destination.parent.mkdir(parents=True, exist_ok=True)
    expected = profile()
    conn = sqlite3.connect(destination)
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS staged_vectors(chunk_id TEXT PRIMARY KEY, source_hash TEXT NOT NULL, embedding BLOB NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS stage_profile(profile_json TEXT NOT NULL)')
        saved = conn.execute('SELECT profile_json FROM stage_profile').fetchone()
        if saved and json.loads(saved[0]) != expected:
            raise ValueError('This staging file belongs to another embedding model/profile')
        if not saved:
            conn.execute('INSERT INTO stage_profile VALUES(?)', (json.dumps(expected, sort_keys=True),))
            conn.commit()
        with sqlite3.connect(source) as original:
            original.row_factory = sqlite3.Row
            rows = inputs(original)
        known = dict(conn.execute('SELECT chunk_id,source_hash FROM staged_vectors'))
        pending = [(cid, text, digest) for cid, text, digest in rows if known.get(cid) != digest]
        if pending:
            model = encoder or load_embed_model()[1]
            start = time.monotonic()
            for i in range(0, len(pending), batch_size):
                batch = pending[i:i+batch_size]
                vectors = embed_texts(None, model, [r[1] for r in batch])
                if vectors.shape != (len(batch), expected['dimensions']) or not np.isfinite(vectors).all():
                    raise ValueError('Staging returned invalid vectors; original index is unchanged')
                conn.executemany('INSERT OR REPLACE INTO staged_vectors VALUES(?,?,?)',
                                 [(row[0], row[2], vector.astype(np.float32).tobytes()) for row, vector in zip(batch, vectors)])
                conn.commit()
                done = len(rows)-len(pending)+min(i+len(batch),len(pending))
                state = {'running': True, 'phase':'building', 'done':done, 'total':len(rows),
                         'model': expected['model'], 'dimensions': expected['dimensions'],
                         'elapsed_seconds':round(time.monotonic()-start,1)}
                status = destination.parent / 'status.json'
                tmp = status.with_suffix('.tmp')
                tmp.write_text(json.dumps(state));tmp.replace(status)
                if i % (batch_size*10) == 0:
                    print(f"Staged {done}/{len(rows)} vectors ({state['elapsed_seconds']}s)", flush=True)
        (destination.parent / 'status.json').write_text(json.dumps({'running':False,'phase':'ready','done':len(rows),'total':len(rows),'model':expected['model'],'dimensions':expected['dimensions']}))
        print(f'Staging snapshot complete: {len(rows)} chunks; {len(pending)} new/changed vectors', flush=True)
        return len(pending)
    finally:
        conn.close()


def activate(source, staged):
    expected = profile()
    conn = open_index(source)
    vectors = sqlite3.connect(staged)
    try:
        saved = vectors.execute('SELECT profile_json FROM stage_profile').fetchone()
        if not saved or json.loads(saved[0]) != expected:
            raise ValueError('Staged model identity does not match the target configuration')
        backup = staged.parent / ('original-rag-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.sqlite')
        with sqlite3.connect(backup) as target:
            conn.backup(target)
        conn.execute('BEGIN IMMEDIATE')
        with conn:
            rows = inputs(conn)
            known = dict(vectors.execute('SELECT chunk_id,source_hash FROM staged_vectors'))
            if any(known.get(cid) != digest for cid, text, digest in rows):
                raise ValueError('The library changed after staging. Run a final staging catch-up; the original index is unchanged.')
            lengths = dict(vectors.execute('SELECT chunk_id,length(embedding) FROM staged_vectors'))
            if any(lengths.get(cid) != expected['dimensions']*4 for cid, _, _ in rows):
                raise ValueError('Staged vector dimensions are invalid')
            conn.execute('DROP TABLE chunks_vec')
            conn.execute(f"CREATE VIRTUAL TABLE chunks_vec USING vec0(chunk_id TEXT PRIMARY KEY,embedding FLOAT[{expected['dimensions']}])")
            current = {r[0] for r in rows}
            cursor = vectors.execute('SELECT chunk_id,embedding FROM staged_vectors')
            while batch := cursor.fetchmany(128):
                batch = [row for row in batch if row[0] in current]
                if any(not np.isfinite(np.frombuffer(row[1], dtype=np.float32)).all() or np.linalg.norm(np.frombuffer(row[1], dtype=np.float32)) <= 0 for row in batch):
                    raise ValueError('Staged vectors contain invalid values; activation rolled back')
                conn.executemany('INSERT INTO chunks_vec VALUES(?,?)', batch)
            write_profile(conn, expected)
        print(f'Activated {len(rows)} vectors; original database backup: {backup}', flush=True)
        (staged.parent / 'status.json').write_text(json.dumps({'running':False,'phase':'active','done':len(rows),'total':len(rows),'model':expected['model'],'dimensions':expected['dimensions']}))
        return backup
    finally:
        vectors.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-db', type=Path, required=True)
    parser.add_argument('--stage-db', type=Path, required=True)
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    if args.batch_size < 1 or args.source_db.resolve() == args.stage_db.resolve():
        parser.error('Use a positive batch size and a separate staging database')
    if args.activate:
        activate(args.source_db, args.stage_db)
    else:
        stage(args.source_db, args.stage_db, args.batch_size)


if __name__ == '__main__':
    main()
