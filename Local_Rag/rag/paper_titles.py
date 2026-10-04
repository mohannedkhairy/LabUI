"""Recover display titles from local metadata without changing stable paper IDs."""
import json
import re
import sqlite3
from pathlib import Path


def normalize(value):
    return re.sub(r'[^\w]+', ' ', str(value or '').casefold()).strip()


def is_placeholder(title, paper_id='', source_pdf=''):
    title = str(title or '').strip()
    return (not title or normalize(title) in {normalize(paper_id), normalize(Path(source_pdf).stem), normalize(Path(source_pdf).name)}
            or bool(re.fullmatch(r'(?:paper[\s_-]*)?\d+(?:\.pdf)?', title, re.I))
            or title.lower().endswith('.pdf'))


def usable_title(title, paper_id='', source_pdf=''):
    return bool(title and len(str(title).strip()) >= 6 and not is_placeholder(title, paper_id, source_pdf))


def reconcile_titles(db_path, library_path=None, parsed_dir=None, metadata_path=None):
    """Only repair missing/filename titles; preserve curated titles and IDs.

    Sources must match a paper ID, DOI, or an unambiguous source filename.
    No LLM guesses, network calls, PDF renaming, or embedding rebuilds.
    """
    if not Path(db_path).exists():
        return 0
    records = []
    if library_path and Path(library_path).exists():
        try:
            raw = json.loads(Path(library_path).read_text(encoding='utf-8'))
            records.extend(raw if isinstance(raw, list) else raw.get('papers', []))
        except (ValueError, OSError):
            pass
    if parsed_dir and Path(parsed_dir).exists():
        for path in Path(parsed_dir).glob('*.json'):
            try:
                record = json.loads(path.read_text(encoding='utf-8'))
                if isinstance(record, dict):
                    records.append(record)
            except (ValueError, OSError):
                continue
    if metadata_path:
        from ingest.metadata import load_source
        records.extend(load_source(metadata_path))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        columns = {r[1] for r in conn.execute('PRAGMA table_info(papers)')}
        if not {'paper_id','title','source_pdf'} <= columns:
            return 0
        rows = conn.execute('SELECT * FROM papers').fetchall()
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'citation_catalog' in tables:
            records.extend(dict(r) for r in conn.execute('SELECT * FROM citation_catalog'))
        from collections import defaultdict
        by_id, by_doi, by_file = defaultdict(list), defaultdict(list), defaultdict(list)
        for record in records:
            by_id[record.get('paper_id')].append(record)
            if record.get('doi'):
                by_doi[normalize(record['doi'])].append(record)
            source = record.get('source_pdf') or record.get('filename') or record.get('source') or record.get('file') or record.get('path') or ''
            if source:
                by_file[Path(source).name].append(record)
        count = 0
        for row in rows:
            p = dict(row)
            if not is_placeholder(p['title'], p['paper_id'], p['source_pdf'] or ''):
                continue
            matches = []
            candidates = by_id.get(p['paper_id'], []) + by_doi.get(normalize(p.get('doi')), []) + by_file.get(Path(p['source_pdf'] or '').name, [])
            for r in candidates:
                source = r.get('source_pdf') or r.get('filename') or r.get('source') or r.get('file') or r.get('path') or ''
                same_id = r.get('paper_id') == p['paper_id']
                same_doi = bool(p.get('doi') and normalize(r.get('doi')) == normalize(p['doi']))
                same_file = bool(source and p['source_pdf'] and Path(source).name == Path(p['source_pdf']).name)
                if (same_id or same_doi or same_file) and usable_title(r.get('title'), p['paper_id'], p['source_pdf'] or ''):
                    matches.append(str(r['title']).strip())
            # Conflicting metadata requires review rather than guessing.
            unique = {normalize(t) for t in matches}
            if len(unique) != 1:
                continue
            title = matches[0]
            if 'title_original' in columns:
                conn.execute('UPDATE papers SET title_original=COALESCE(NULLIF(title_original,\'\'),title),title=? WHERE paper_id=?', (title,p['paper_id']))
            else:
                conn.execute('UPDATE papers SET title=? WHERE paper_id=?', (title,p['paper_id']))
            if 'citation_catalog' in tables:
                conn.execute('UPDATE citation_catalog SET title=? WHERE paper_id=?', (title,p['paper_id']))
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def title_for(paper_id):
    from config import DB_PATH
    if not DB_PATH.exists():
        return paper_id
    conn = sqlite3.connect(f'{DB_PATH.as_uri()}?mode=ro', uri=True)
    try:
        row = conn.execute('SELECT title FROM papers WHERE paper_id=?', (paper_id,)).fetchone()
        return row[0] if row and row[0] else paper_id
    finally:
        conn.close()


def title_map():
    from config import DB_PATH
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(f'{DB_PATH.as_uri()}?mode=ro', uri=True)
    try:
        return {pid: title for pid, title in conn.execute('SELECT paper_id,title FROM papers') if title}
    finally:
        conn.close()
