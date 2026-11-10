"""Recover publication years with evidence, preserving existing bibliographic dates."""
from datetime import date
import html
import json
from pathlib import Path
import re
import sqlite3
import unicodedata


YEAR = r'(?:18|19|20)\d{2}'
_JOURNAL = re.compile(r'\b(journal|j\.|phys\.?|langmuir|colloids|materials|matter|science|sci|adv|chem\.?|energy|fuels|engineering|environ|review|technol|fluid|nanomedicine|physica|process|membrane|water|aiche|acta)\b', re.I)


def valid_year(value):
    if isinstance(value, bool):
        return None
    if not re.fullmatch(YEAR, str(value or '').strip()):
        return None
    year = int(value)
    return year if 1800 <= year <= date.today().year + 1 else None


def record_year(record):
    """Print/issue year wins over early-online publication; registration dates do not qualify."""
    for field in ('published-print', 'published', 'issued', 'published-online'):
        try:
            year = valid_year(record[field]['date-parts'][0][0])
        except (KeyError, TypeError, IndexError):
            continue
        if year:
            return {'year': year, 'source': 'doi:' + field, 'quote': json.dumps(record[field])}
    return None


def _fold(value):
    value = re.sub('<[^>]+>', '', html.unescape(str(value or '')))
    return ''.join(c for c in unicodedata.normalize('NFKD', value).casefold() if c.isalnum())


def matching_record(record, title, authors='', dois=()):
    titles = record.get('title') or []
    if not isinstance(titles, list) or not titles:
        return False
    candidates = [_fold(titles[0])]
    if record.get('subtitle'):
        candidates.append(_fold(titles[0] + ' ' + record['subtitle'][0]))
    if len(_fold(title)) < 12 or _fold(title) not in candidates:
        return False
    doi = str(record.get('DOI') or '').casefold()
    if doi and doi in {str(d).casefold() for d in dois}:
        return True
    families = [a.get('family') for a in record.get('author', []) if isinstance(a, dict) and a.get('family')]
    return bool(families and authors and all(_fold(name) in _fold(authors) for name in families))


def text_year(text, strong_only=False):
    """Use citation headers and explicitly labeled dates, never arbitrary four-digit numbers."""
    text = unicodedata.normalize('NFKC', text or '')
    text = re.split(r'Articles You May|You may also like|\n\s*(?:References|Bibliography)\s*\n', text, maxsplit=1, flags=re.I)[0]
    lines = [' '.join(line.split()) for line in text.splitlines()]
    strong = []
    for index, line in enumerate(lines):
        if re.search(r'\b(received|accepted|revised|downloaded|copyright)\b|©', line, re.I):
            continue
        # Printed volume/issue citation, including Elsevier, ACS, AIP, Wiley.
        if _JOURNAL.search(line):
            citation = ' '.join(lines[index:index + 4])[:500]
            # DOI suffixes and in-text references contain unrelated years.
            citation = re.sub(r'https?://\S+|\bdoi:\S+', '', citation, flags=re.I)
            if re.search(r'\bet\s+al\.', citation, re.I) and not re.search(r'\bCite|\bCitation|\bSci\.\s+Adv\.', citation, re.I):
                continue
            patterns = [rf'\b\d{{1,4}}\s*\(\s*({YEAR})\s*\)\s*[,;:]?\s*\d',
                        rf'\b\d{{1,4}}\s+({YEAR})\s+\d+\s*[–-]',
                        rf'\b({YEAR})\s*[,;:]\s*\d{{1,4}}\s*[,;:.]',
                        rf'\b({YEAR})\s*[;,]\s*\d+(?:\([^)]*\))?\s*:',
                        rf'\b\d+\s*,\s*\d+\s*\(\s*({YEAR})\s*\)',
                        rf'\b({YEAR})\)?\s*[,;]?\s*vol\.?\s*\w']
            for pattern in patterns:
                for match in re.finditer(pattern, citation, re.I):
                    strong.append((valid_year(match[1]), citation))
            if re.search(r'\b(?:19|20)\d{2}\s+SPE\b|\b(?:Jan(?:uary)?|Feb(?:ruary)?|March|April|May|June|July|Aug(?:ust)?|Sept(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+' + YEAR, line, re.I):
                years = re.findall(YEAR, line)
                if len(set(years)) == 1:
                    strong.append((valid_year(years[0]), line))
        if re.search(r'\bVol(?:ume)?\.?\s+\d+', line, re.I):
            block = ' '.join(lines[max(0, index - 1):index + 3])
            block = re.split(r'https?://|\bdoi:|\bPublished|\bDownloaded', block, maxsplit=1, flags=re.I)[0]
            preceding = re.search(r'\b(' + YEAR + r')\)?\s*[,;]?\s*Vol(?:ume)?\.?\s+\d+', block, re.I)
            if preceding:
                strong.append((valid_year(preceding[1]), block))
            found = re.search(r'\bVol(?:ume)?\.?\s+\d+[^\n]{0,100}?\b(' + YEAR + r')\b', block, re.I)
            if found:
                strong.append((valid_year(found[1]), block))
    unique = {year for year, _ in strong if year}
    if len(unique) == 1:
        year = unique.pop()
        return {'year': year, 'source': 'pdf:journal-citation', 'quote': next(quote for y, quote in strong if y == year)}
    if unique or strong_only:
        return None
    for source, pattern in [
        ('pdf:arxiv-version', rf'\barXiv\s*:\s*(?:\d{{4}}\.\d{{4,5}}|[a-z.-]+/\d{{7}})(?:v\d+)?\s*(?:\[[^\]]+\])?\s*\d{{1,2}}\s+[a-z]+\s+({YEAR})\b'),
        ('pdf:publication-date', rf'\b(?:first\s+published(?:\s+online)?|published\s+online|publication\s+date|date\s+of\s+publication|date\s+of\s+patent)\b[^\n]{{0,80}}?\b({YEAR})\b'),
        ('pdf:copyright', rf'(?:©|\(c\)|copyright(?:\s*©)?)\s*(?:by[^\n]{{0,90}}?,\s*)?({YEAR})\b'),
    ]:
        matches = [(valid_year(m[1]), m[0]) for m in re.finditer(pattern, text, re.I)]
        years = {y for y, _ in matches if y}
        if len(years) == 1:
            year = years.pop()
            return {'year': year, 'source': source, 'quote': next(q for y, q in matches if y == year)}
    # Thesis title pages carry a degree/date; manuscript-received dates and
    # repository form revision dates do not qualify.
    if re.search(r'\bdegree\s+of\b|\bdoctor\s+of\s+philosophy\b', text, re.I):
        matches = re.findall(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Spring|Summer|Fall|Autumn|Winter)\s+(' + YEAR + r')\b', text, re.I)
        years = {valid_year(y) for y in matches} - {None}
        if len(years) == 1:
            return {'year': years.pop(), 'source': 'pdf:thesis-date', 'quote': '\n'.join(line for line in lines if any(y in line for y in matches))}
    return None


def pdf_text(path, parsed=None):
    import pymupdf
    from paper_titles import title_pages
    texts = []
    if path and Path(path).is_file():
        try:
            with pymupdf.open(path) as document:
                texts = [page.get_text() for page in title_pages(document)]
                front = texts[0] if texts else ''
                # RSC accepted manuscripts use a stock journal cover whose
                # featured paper and issue date belong to a different article.
                if 'this is an accepted manuscript' in front.casefold() and len(texts) > 1:
                    texts = texts[1:]
                if re.search(r'thesis|dissertation', str(path), re.I) or 'research thesis' in front.casefold():
                    texts = [page.get_text() for page in list(document)[:6]
                             if re.search(r'\bdegree\s+of\b|\bdoctor\s+of\s+philosophy\b', page.get_text(), re.I)] or texts
                elif 0 < len(front.strip()) < 100 and len(document) > 20:
                    texts.extend(page.get_text() for page in list(document)[1:6]
                                 if re.search(r'copyright|first published|ISBN', page.get_text(), re.I))
        except (OSError, RuntimeError, ValueError):
            pass
    if not any(len(t.strip()) > 100 for t in texts) and parsed:
        texts.append('\n'.join(str(s.get('name') or '') + '\n' + str(s.get('text') or '')
                  for s in parsed.get('sections', []) if (s.get('page_start') or 1) == 1)[:16000])
    return '\n'.join(texts)


def apply_year(conn, paper_id, evidence):
    year = valid_year(evidence.get('year'))
    if year is None:
        raise ValueError('Invalid publication year')
    changed = conn.execute('UPDATE papers SET year=? WHERE paper_id=? AND year IS NULL', (year, paper_id)).rowcount
    if not changed:
        return False
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='citation_catalog'").fetchone():
        conn.execute('UPDATE citation_catalog SET year=? WHERE paper_id=?', (year, paper_id))
    conn.execute('''CREATE TABLE IF NOT EXISTS paper_year_evidence(
        paper_id TEXT PRIMARY KEY,year INTEGER NOT NULL,source TEXT NOT NULL,evidence_json TEXT NOT NULL)''')
    conn.execute('INSERT OR REPLACE INTO paper_year_evidence VALUES(?,?,?,?)',
                 (paper_id, year, evidence['source'], json.dumps(evidence, ensure_ascii=False)))
    return True
