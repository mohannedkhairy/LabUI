"""Read public DOI records, accepting only metadata grounded in this PDF header."""
import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote
from uuid import uuid4

import requests


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', html.unescape(str(text or ''))).casefold() if c.isalnum())


def pdf_dois(path):
    import pymupdf
    from paper_titles import title_pages
    with pymupdf.open(path) as document:
        text = ' '.join(page.get_text() for page in title_pages(document))
        text += ' ' + ' '.join(str(document.metadata.get(k) or '') for k in ('title', 'subject', 'keywords'))
    return list(dict.fromkeys(match.rstrip('.,;:)').lower() for match in
                re.findall(r'10\.\d{4,9}/[^\s<>\[\]{}"\u0000-\u001f]+', text)))[:4]


def validate_doi_record(record, headers):
    if not isinstance(record, dict):
        raise ValueError('Invalid DOI record')
    titles = [re.sub('<[^>]+>', '', html.unescape(t)) for t in record.get('title', []) if t]
    if not titles or len(titles[0]) < 12:
        raise ValueError('DOI record has no usable title')
    title = ' '.join(titles[0].split())
    authors = record.get('author') or []
    if not isinstance(authors, list) or not authors or any(not isinstance(author, dict) or not author.get('family') or not author.get('given') for author in authors):
        raise ValueError('DOI record has an incomplete author list')
    for page, header in headers.items():
        text = fold(header)
        start = text.find(fold(title))
        if start < 0 or start > 2200:
            continue
        byline = text[start + len(fold(title)):][:2200]
        position = 0
        for author in authors:
            family = fold(author['family'])
            found = byline.find(family, position)
            if found < 0:
                break
            position = found + len(family)
        else:
            from paper_years import record_year
            publication = record_year(record)
            return {'title': title, 'authors': [' '.join((a['given'], a['family'])) for a in authors],
                    'year': publication['year'] if publication else None,
                    'page': int(page), 'doi': record.get('DOI'), 'method': 'Crossref DOI record verified against PDF title and ordered author surnames'}
    raise ValueError('DOI title or ordered authors do not match the PDF header')


def recover_doi_metadata(dois, headers, cache_dir):
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.trust_env = False
    session.headers['User-Agent'] = 'LabUI/1.0 (local bibliographic metadata repair)'
    try:
        for doi in dois:
            cache = cache_dir / (hashlib.sha256(doi.encode()).hexdigest() + '.json')
            try:
                if cache.exists():
                    record = json.loads(cache.read_text())
                else:
                    response = session.get('https://api.crossref.org/works/' + quote(doi, safe=''), timeout=20)
                    if response.status_code in (404, 400):
                        cache.write_text('{}')
                        continue
                    response.raise_for_status()
                    record = response.json()['message']
                    temporary = cache.with_suffix('.' + uuid4().hex + '.tmp')
                    temporary.write_text(json.dumps(record, ensure_ascii=False))
                    temporary.replace(cache)
                return validate_doi_record(record, headers)
            except (requests.RequestException, ValueError, KeyError, OSError):
                continue
        return None
    finally:
        session.close()
