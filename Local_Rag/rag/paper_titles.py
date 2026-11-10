"""Recover display titles from local metadata without changing stable paper IDs."""
import json
import re
import sqlite3
import unicodedata
from statistics import median
from pathlib import Path


def normalize(value):
    return re.sub(r'[^\w]+', ' ', str(value or '').casefold()).strip()


def is_placeholder(title, paper_id='', source_pdf=''):
    title = str(title or '').strip()
    return (not title or normalize(title) in {normalize(paper_id), normalize(Path(source_pdf).stem), normalize(Path(source_pdf).name)}
            or bool(re.fullmatch(r'(?:paper[\s_-]*)?\d+(?:\.pdf)?', title, re.I))
            or title.lower().endswith('.pdf')
            or bool(re.match(r'^(?:doi\s*:|pii\s*:|10\.\d{4,9}/|untitled\b|microsoft\s+(?:word|powerpoint)\b)', title, re.I))
            or title.casefold() in {'document', 'article', 'paper', 'accepted manuscript',
                                    'abstract', 'introduction', 'regular article', 'research article',
                                    'rapid communication', 'supporting information', 'university of alberta'}
            or bool(re.search(r'\bVol\.\s*\d+.*\bNo\.\s*\d+.*\b(?:19|20)\d{2}\b', title)))


def usable_title(title, paper_id='', source_pdf=''):
    return bool(title and len(str(title).strip()) >= 6 and not is_placeholder(title, paper_id, source_pdf))


def parsed_header(record):
    """Recover an OCR heading followed by a byline from the existing parse.

    Docling often labels a paper's title as a section heading. Retain its page
    provenance and require a real byline rather than guessing from body prose.
    """
    from ingest.metadata import _byline_names, _AFFILIATION_RE
    for section in record.get('sections', [])[:6]:
        name = str(section.get('name') or '').strip().rstrip('†‡* ')
        if name.casefold() in {'abstract', 'introduction', '1. introduction', 'references'}:
            break
        if not 15 <= len(name) <= 500 or len(name.split()) < 3 or not usable_title(name):
            continue
        if name.casefold() in {'body', 'communication', 'research article'} or re.match(r'^(?:\d+[. ]|united states patent|journal\b|available online)', name, re.I):
            continue
        if (section.get('page_start') or 1) > 3:
            continue
        byline = []
        names = []
        for line in str(section.get('text') or '').splitlines()[:5]:
            if _AFFILIATION_RE.search(line):
                break
            byline.append(line)
            candidate = _byline_names(' '.join(byline))
            if candidate:
                names = candidate
            elif names:
                break
        if len(names) >= 2:
            return {'title': ' '.join(name.split()), 'authors': names,
                    'page': section.get('page_start') or 1,
                    'title_quote': section['name'], 'byline_quote': '\n'.join(byline),
                    'method': 'OCR section heading followed by a visible byline'}
    return None


def _first_page_rows(page, include_superscripts=True):
    """Join fragments on the same baseline, removing publisher icon glyphs."""
    lines = []
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            if abs(line.get('dir', (1, 0))[1]) > .1:
                continue
            spans = [s for s in line['spans'] if include_superscripts or not (s.get('flags', 0) & 1)]
            text = ''.join(s['text'] for s in spans)
            text = ''.join(c for c in text if not unicodedata.category(c).startswith('C'))
            text = ' '.join(text.split())
            sizes = [s['size'] for s in spans if any(c.isalnum() for c in s['text'])]
            if text and sizes:
                lines.append({'text': text, 'box': line['bbox'], 'size': max(sizes)})
            elif text and lines and len(text) <= 3:
                # Superscript charges can be their own fragment in scientific titles.
                lines.append({'text': text, 'box': line['bbox'], 'size': max((s['size'] for s in spans), default=0)})
    rows = []
    for line in sorted(lines, key=lambda item: item['box'][1]):
        if rows and abs(rows[-1][0]['box'][1] - line['box'][1]) <= max(2.5, line['size'] * .25):
            rows[-1].append(line)
        else:
            rows.append([line])
    result = []
    for row in rows:
        row.sort(key=lambda item: item['box'][0])
        result.append({'text': ' '.join(item['text'] for item in row), 'size': max(item['size'] for item in row),
                       'box': (min(item['box'][0] for item in row), min(item['box'][1] for item in row),
                               max(item['box'][2] for item in row), max(item['box'][3] for item in row))})
    return result


def _visible_title(page):
    """Require a prominent title followed by a byline and affiliation/abstract."""
    from ingest.metadata import _byline_names
    rows = _first_page_rows(page)
    clean_rows = _first_page_rows(page, include_superscripts=False)
    sizes = [row['size'] for row in rows if len(row['text']) >= 15]
    if not sizes:
        return None
    body_size = median(sizes)
    i = 0
    while i < len(rows):
        first = rows[i]
        i += 1
        if first['box'][1] > page.rect.height * .55 or first['size'] < body_size * 1.15:
            continue
        group = [first]
        while i < len(rows) and .95 <= rows[i]['size'] / first['size'] <= 1.05 and rows[i]['box'][1] - group[-1]['box'][3] <= first['size'] * 1.5:
            group.append(rows[i])
            i += 1
        # A heading can shrink on its second line. Do not mistake that line
        # for a new title, or for an all-capitals author name.
        if i < len(rows) and first['text'].isupper() and rows[i]['text'].isupper() and rows[i]['size'] >= body_size * 1.15 and rows[i]['box'][1] - group[-1]['box'][3] < first['size']:
            group.append(rows[i])
            i += 1
        candidate = re.sub(r'(?<=-)\s+(?=[a-z])', '', ' '.join(row['text'] for row in group))
        if not 20 <= len(candidate) <= 500 or len(candidate.split()) < 4:
            continue
        if re.search(r'^(journal\b|research article\b|articles you may|science\s*direct\b|download)', candidate, re.I):
            continue
        following = [r for r in clean_rows if r['box'][1] >= group[-1]['box'][3] - 1]
        if not following or following[0]['box'][1] - group[-1]['box'][3] > 60:
            continue
        names = []
        for row in following[:4]:
            found = _byline_names(row['text'])
            if not found:
                break
            names.extend(found)
        if names and (len(names) >= 2 or any(re.search(r'\b(abstract|university|institute|department|dated|australia)\b|@', r['text'], re.I) for r in following[1:5])):
            return candidate.rstrip('*†‡ ')
    return None


def title_pages(document):
    """Look past publisher/repository covers, never arbitrary later paper pages."""
    yield document[0]
    cover = document[0].get_text().casefold()
    if any(marker in cover for marker in ('accepted manuscript', 'complete list of authors',
                                         'this is a repository copy', 'this is the accepted',
                                         'provided by', 'to cite this article', 'articles you may be interested',
                                         'accepted article', 'you may also like', 'prism repository')):
        for index in range(1, min(3, len(document))):
            yield document[index]


def verified_pdf_title(source_pdf):
    """Verify metadata against page 1, or use a prominent title/byline layout.

    A summary can describe the subject without containing the actual title.
    Ground recovery in the PDF itself; never invent a name from its topic.
    """
    if not source_pdf or not Path(source_pdf).is_file():
        return None
    try:
        import pymupdf
        with pymupdf.open(source_pdf) as document:
            if not len(document):
                return None
            title = " ".join((document.metadata.get('title') or '').split())
            def compact(value):
                return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())
            generic = (not usable_title(title, source_pdf=source_pdf)
                       or title.casefold() in {'untitled', 'document', 'microsoft word', 'article', 'paper'}
                       or re.match(r'^(microsoft\s+(word|powerpoint)\b|untitled\b|doi\s*:|10\.\d{4,9}/)', title, re.I))
            for page in title_pages(document):
                visible = _visible_title(page)
                if not generic and compact(title) in compact(page.get_text()):
                    # Publisher title tags are sometimes truncated mid-word.
                    if visible and compact(visible).startswith(compact(title)):
                        return visible
                    return title
                if visible:
                    return visible
            return None
    except Exception:
        return None


def apply_recovered_title(conn, paper_id, title):
    """Update a placeholder label and its citation record; keep IDs and keys."""
    columns = {r[1] for r in conn.execute('PRAGMA table_info(papers)')}
    row = conn.execute('SELECT title,source_pdf FROM papers WHERE paper_id=?', (paper_id,)).fetchone()
    if not row or not usable_title(title, paper_id, row[1] or ''):
        return False
    if not is_placeholder(row[0], paper_id, row[1] or ''):
        # Only extend a publisher-truncated metadata tag. A curated title
        # that differs from the PDF tag is never overwritten.
        if not row[0] or len(row[0]) < 30 or not normalize(title).startswith(normalize(row[0])) or normalize(title) == normalize(row[0]):
            return False
        try:
            import pymupdf
            with pymupdf.open(row[1]) as document:
                if normalize(document.metadata.get('title')) != normalize(row[0]):
                    return False
            if verified_pdf_title(row[1]) != title:
                return False
        except Exception:
            return False
    original = ",title_original=COALESCE(NULLIF(title_original,''),title)" if 'title_original' in columns else ''
    changed = conn.execute(
        f'UPDATE papers SET title=?{original} WHERE paper_id=? AND title IS ?',
        (title, paper_id, row[0]),
    ).rowcount
    if not changed:
        return False
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='citation_catalog'").fetchone():
        conn.execute('UPDATE citation_catalog SET title=? WHERE paper_id=?', (title, paper_id))
    return True


def recover_paper_title(conn, paper_id):
    row = conn.execute('SELECT title,source_pdf FROM papers WHERE paper_id=?', (paper_id,)).fetchone()
    if not row:
        return None
    if is_placeholder(row[0], paper_id, row[1] or ''):
        title = verified_pdf_title(row[1])
        if title and apply_recovered_title(conn, paper_id, title):
            conn.commit()
            return title
    return row[0] or paper_id


def reconcile_titles(db_path, library_path=None, parsed_dir=None, metadata_path=None):
    """Only repair missing/filename titles; preserve curated titles and IDs.

    Sources must match a paper ID, DOI, or an unambiguous source filename.
    Also checks embedded PDF titles against page 1 when local cards lack a title.
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
                    recovered = parsed_header(record)
                    if recovered:
                        records.append(dict(record, title=recovered['title']))
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
                if len(p['title'] or '') >= 80:
                    title = verified_pdf_title(p['source_pdf'])
                    if title and apply_recovered_title(conn, p['paper_id'], title):
                        count += 1
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
            if len(unique) > 1:
                continue
            title = matches[0] if unique else verified_pdf_title(p['source_pdf'])
            if title and apply_recovered_title(conn, p['paper_id'], title):
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
