"""An embedding space is identified by its model and prompts, not only size."""
import hashlib
import json
import re

from config import EMBED_PROVIDER, EMBED_MODEL_BASE, EMBED_DIM, EMBED_REVISION, EMBED_QUERY_INSTRUCTION


def profile(dimensions=None):
    return {'provider': EMBED_PROVIDER, 'model': EMBED_MODEL_BASE,
            'dimensions': dimensions or EMBED_DIM, 'revision': EMBED_REVISION,
            'normalization': 'l2', 'document_format': 'title-section-v1',
            'query_instruction': EMBED_QUERY_INSTRUCTION if EMBED_PROVIDER == 'lmstudio' else ''}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def read_profile(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='embedding_identity'").fetchone():
        return None
    row = conn.execute("SELECT profile_json FROM embedding_identity WHERE id=1").fetchone()
    return json.loads(row[0]) if row else None


def write_profile(conn, value):
    conn.execute('CREATE TABLE IF NOT EXISTS embedding_identity(id INTEGER PRIMARY KEY CHECK(id=1), profile_json TEXT NOT NULL)')
    conn.execute('INSERT OR REPLACE INTO embedding_identity VALUES(1,?)', (json.dumps(value, sort_keys=True),))


def ensure_compatible(conn, dimensions=None):
    schema = conn.execute("SELECT sql FROM sqlite_master WHERE name='chunks_vec'").fetchone()
    if not schema:
        return
    match = re.search(r'FLOAT\[(\d+)\]', schema[0], re.I)
    expected = profile(dimensions)
    if not match or int(match[1]) != expected['dimensions']:
        raise ValueError('Embedding dimensions do not match the paper index. Rebuild vectors before switching models.')
    saved = read_profile(conn)
    if saved and saved != expected:
        raise ValueError('Embedding model/prompt identity does not match this index. Use the matching index or rebuild it.')
    if not saved:
        count = conn.execute('SELECT count(*) FROM chunks_vec').fetchone()[0]
        if count and EMBED_PROVIDER != 'local':
            raise ValueError('This existing index has no matching remote embedding identity. Migrate it before enabling remote embeddings.')
        write_profile(conn, expected)
        conn.commit()
