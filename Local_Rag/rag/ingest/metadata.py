"""Read-only metadata sources used while parsing/indexing PDFs.

Mendeley is an input library here, never an output target.  Exported BibTeX,
RIS, and CSL-JSON files are the most portable source formats; a small,
defensive SQLite adapter also handles the common Mendeley Desktop layouts by
discovering a document-like table rather than assuming one schema.
"""
from __future__ import annotations

import difflib
import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _year(value: Any) -> int | None:
    m = re.search(r"\b(19|20)\d{2}\b", str(value or ""))
    return int(m.group(0)) if m else None


def _doi(value: Any) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", value)
    return value.rstrip(" .;,)")


def _clean_record(record: dict[str, Any]) -> dict[str, Any]:
    authors = record.get("authors", "")
    if isinstance(authors, list):
        authors = "; ".join(str(a) for a in authors if a)
    return {
        "title": str(record.get("title") or "").strip(),
        "authors": str(authors or "").strip(),
        "year": _year(record.get("year")),
        "doi": _doi(record.get("doi")),
        "journal": str(record.get("journal") or "").strip(),
        "volume": str(record.get("volume") or "").strip(),
        "issue": str(record.get("issue") or record.get("number") or "").strip(),
        "pages": str(record.get("pages") or record.get("page") or "").strip(),
        "publisher": str(record.get("publisher") or "").strip(),
        "url": str(record.get("url") or "").strip(),
        "path": str(record.get("path") or record.get("file") or "").strip(),
        "external_key": str(record.get("external_key") or record.get("id") or "").strip(),
    }


def _sqlite_records(path: Path) -> list[dict[str, Any]]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        records: list[dict[str, Any]] = []
        for table in tables:
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table.replace(chr(34), chr(34)*2)}")')]
            low = {c.lower(): c for c in cols}
            title_col = next((low[x] for x in ("title", "document_title", "name") if x in low), None)
            if not title_col:
                continue
            # Skip obvious non-reference tables that happen to have a name.
            if not any(x in low for x in ("doi", "authors", "author", "year", "date", "abstract", "journal", "source")):
                continue
            def col(*names: str) -> str | None:
                return next((low[x] for x in names if x in low), None)
            author_col = col("authors", "author", "creator", "contributors")
            year_col = col("year", "date", "publication_year", "issued")
            doi_col = col("doi", "DOI".lower())
            journal_col = col("journal", "source", "publication", "container_title")
            volume_col = col("volume")
            issue_col = col("issue", "number")
            pages_col = col("pages", "page")
            publisher_col = col("publisher")
            url_col = col("url", "link", "web_url")
            path_col = col("path", "file", "filename", "file_name", "local_url")
            select = [title_col] + [x for x in (author_col, year_col, doi_col, journal_col, volume_col, issue_col, pages_col, publisher_col, url_col, path_col) if x]
            quoted = ", ".join(f'"{x.replace(chr(34), chr(34)*2)}"' for x in select)
            try:
                rows = conn.execute(f'SELECT {quoted} FROM "{table.replace(chr(34), chr(34)*2)}" LIMIT 100000').fetchall()
            except sqlite3.Error:
                continue
            for row in rows:
                values = iter(row)
                item = {"title": next(values, "")}
                for key, present in (("authors", author_col), ("year", year_col), ("doi", doi_col), ("journal", journal_col), ("volume", volume_col), ("issue", issue_col), ("pages", pages_col), ("publisher", publisher_col), ("url", url_col), ("path", path_col)):
                    if present:
                        item[key] = next(values, "")
                item["external_key"] = f"{table}:{len(records)}"
                clean = _clean_record(item)
                if clean["title"]:
                    records.append(clean)
            # The first useful document table is normally enough; retaining
            # additional tables can create duplicates and false matches.
            if records:
                break
        return records
    finally:
        conn.close()


def load_source(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.exists() or not p.is_file():
        return []
    try:
        if p.suffix.lower() in {".sqlite", ".sqlite3", ".db"}:
            return _sqlite_records(p)
        from citations import parse_import
        return [_clean_record(r) for r in parse_import(p.read_text(encoding="utf-8-sig", errors="replace"), p.suffix)]
    except Exception:
        return []


def load_sources(paths: list[str | Path] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in paths or []:
        for record in load_source(path):
            marker = (_norm(record.get("title")), _doi(record.get("doi")))
            if marker == ("", "") or marker in seen:
                continue
            seen.add(marker)
            out.append(record)
    return out


def match(pdf_path: Path, extracted_title: str, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not records:
        return None
    stem = _norm(pdf_path.stem)
    title = _norm(extracted_title)
    best, best_score = None, 0.0
    for record in records:
        score = 0.0
        path = _norm(record.get("path"))
        if path and _norm(Path(str(record.get("path"))).stem) == stem:
            score = 1.0
        rt = _norm(record.get("title"))
        if title and rt:
            score = max(score, difflib.SequenceMatcher(None, title, rt).ratio())
        if stem and rt:
            score = max(score, difflib.SequenceMatcher(None, stem, rt).ratio() * 0.94)
        if score > best_score:
            best, best_score = record, score
    return dict(best, match_score=best_score) if best and best_score >= 0.86 else None


_AFFILIATION_RE = re.compile(
    r'\b(university|college|department|school|institute|laboratory|facility|academy|'
    r'abstract|keywords|highlights|received|corresponding|copyright|faculty|centre|center|'
    r'progress|report|generated|constants|atmospheric|evaluation|nanobubbles|'
    r'regular article|rapid communication|supporting information)\b|@|https?://', re.I,
)


def _compact(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())


def _byline_names(text: str) -> list[str]:
    """Split a visible byline after superscript affiliation spans are removed."""
    text = ''.join(c for c in text if not unicodedata.category(c).startswith('C'))
    text = re.sub(r'\s*[（(][^()（）]*[\u3400-\u9fff][^()（）]*[)）]', '', text)
    text = re.sub(r'[*†‡⁎∗♭✉]', ' ', text)
    text = re.sub(r'^by\s+', '', text, flags=re.I)
    text = re.sub(r',\s*SPE(?=\s*[,;]|$)', '', text)
    text = text.replace('·', ',')
    # TeX PDFs can expose accent glyphs before their base letter.
    for mark, combining in [('¨', '\u0308'), ('´', '\u0301'), ('`', '\u0300'), ('ˆ', '\u0302')]:
        text = re.sub(re.escape(mark) + r'([a-zA-Z])', lambda m: unicodedata.normalize('NFC', m[1] + combining), text)
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'(?<=[A-Za-z])[0-9]+(?=[,;\s]|$)', '', text)
    text = re.sub(r'\b([A-ZÀ-ÖØ-Þ]{2,})\s+(?=[A-Z][a-z])', r'\1; ', text)
    text = re.sub(r'\s+[a-z](?:\s*,\s*[a-z])*(?=\s*,|$)', '', text)
    text = re.sub(r'\s+[a-f]{2,3}(?=\s*[,;]|\s+and\b|$)', '', text)
    text = re.sub(r',\s*(?:[0-9]+\s*,\s*)+(?=[A-Z])', ', ', text)
    text = re.sub(r',\s+(?=,)', '', text)
    if re.search(r'\band\s*$', text):
        return []
    names = []
    for part in re.split(r'\s*[,;]\s*|\s+(?:and|&)\s+', text):
        name = re.sub(r'^(?:and|&)\s+', '', ' '.join(part.split()).strip()).strip("' ")
        if not name:
            continue
        # Some PDFs keep a plain affiliation letter in the same text span.
        name = re.sub(r'\s+[a-z]$', '', name)
        words = name.split()
        if not 2 <= len(words) <= 5 or _AFFILIATION_RE.search(name):
            return []
        if any(not (c.isalpha() or c in " .'-’‐‑–") for c in name):
            return []
        particles = {'de', 'del', 'da', 'di', 'van', 'von', 'der', 'den', 'la', 'le', 'al', 'bin'}
        if any(not word[0].isupper() and word.casefold() not in particles for word in words):
            return []
        if name not in names:
            names.append(name)
    return names


def verified_pdf_authors(source_pdf: str | Path, title: str = '') -> list[str]:
    """Recover the first-page byline, preserving order and excluding affiliations.

    A title anchors the location. The PDF author tag, when present, must match
    the byline. It is often only the first author, so it is not treated as the
    complete author list. Uncertain layouts remain unfilled.
    """
    if not source_pdf or not Path(source_pdf).is_file():
        return []
    try:
        import pymupdf
        from paper_titles import verified_pdf_title, title_pages
        title = verified_pdf_title(source_pdf) or title
        if not title or len(_compact(title)) < 6:
            return []
        with pymupdf.open(source_pdf) as document:
            if not len(document):
                return []
            page = next((p for p in title_pages(document) if _compact(title) in _compact(p.get_text())), None)
            if page is None:
                return []
            blocks = [b for b in page.get_text('dict')['blocks'] if b.get('lines')]
            # A PDF text block may contain the title, authors and abstract.
            # Locate the title's last row, rather than the block's bottom.
            from paper_titles import _first_page_rows
            page_rows = _first_page_rows(page)
            matches = []
            for start in range(len(page_rows)):
                for end in range(start, min(start + 8, len(page_rows))):
                    if _compact(title) in _compact(' '.join(r['text'] for r in page_rows[start:end + 1])):
                        matches.append(page_rows[end]['box'][3])
                        break
            if not matches:
                return []
            title_bottom = min(matches)
            lines = []
            for block in blocks:
                for line in block['lines']:
                    if line['bbox'][1] < title_bottom - 1:
                        continue
                    spans = [s for s in line['spans'] if not (s.get('flags', 0) & 1)]
                    pieces = []
                    for span in spans:
                        value = span['text']
                        if pieces and re.match(r'^(?:and|&)\b', value) and pieces[-1][-1:].isalpha():
                            pieces.append(' ')
                        pieces.append(value)
                    text = ' '.join(''.join(pieces).split())
                    sizes = [s['size'] for s in spans if s['text'].strip()]
                    if text and sizes:
                        lines.append({'text': text, 'box': line['bbox'], 'size': max(sizes)})
            # ORCID icons can split one author row into separate text blocks.
            rows = []
            for line in sorted(lines, key=lambda item: item['box'][1]):
                if rows and abs(rows[-1][0]['box'][1] - line['box'][1]) <= max(2, line['size'] * .3):
                    rows[-1].append(line)
                else:
                    rows.append([line])
            byline = []
            font_size = None
            previous_bottom = title_bottom
            for row in rows:
                row.sort(key=lambda item: item['box'][0])
                text = ' '.join(item['text'] for item in row)
                size = max(item['size'] for item in row)
                top = min(item['box'][1] for item in row)
                bottom = max(item['box'][3] for item in row)
                if top - previous_bottom > (36 if font_size is None else font_size * 1.8):
                    break
                if (font_size is not None and size < font_size * .85) or _AFFILIATION_RE.search(text):
                    break
                byline.append(text)
                font_size = font_size or size
                previous_bottom = bottom
            authors = _byline_names(' '.join(byline))
            hint = str(document.metadata.get('author') or '').strip()
            hinted_names = _byline_names(hint) if hint else []
            hints = hinted_names
            if any(_compact(name) not in _compact('; '.join(authors)) for name in hints):
                return []
            if not hint and len(authors) == 1:
                # A single author needs the same title + institutional anchor.
                if not any(_AFFILIATION_RE.search(line['text']) or re.search(r'\bAustralia\b', line['text']) for line in lines[:6]):
                    return []
            if len(authors) == 1 and font_size is not None:
                # Some journals interleave authors with separate affiliations.
                # Do not save just the first person from such a header.
                for later in rows[len(byline):len(byline) + 12]:
                    later_text = ' '.join(item['text'] for item in later)
                    if re.search(r'\b(abstract|received|published|introduction)\b', later_text, re.I):
                        break
                    if abs(max(item['size'] for item in later) - font_size) < font_size * .1 and _byline_names(later_text):
                        return []
            return authors
    except Exception:
        return []


def reconcile_authors(db_path: str | Path) -> int:
    """Backfill missing author metadata without rebuilding chunks or vectors."""
    if not Path(db_path).exists():
        return 0
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        columns = {row[1] for row in connection.execute('PRAGMA table_info(papers)')}
        if not {'paper_id', 'title', 'authors', 'source_pdf'} <= columns:
            return 0
        catalog = bool(connection.execute("SELECT 1 FROM sqlite_master WHERE name='citation_catalog'").fetchone())
        count = 0
        rows = connection.execute("SELECT paper_id,title,source_pdf FROM papers WHERE COALESCE(trim(authors),'')=''").fetchall()
        for paper in rows:
            authors = verified_pdf_authors(paper['source_pdf'], paper['title'])
            if not authors:
                continue
            value = '; '.join(authors)
            changed = connection.execute("UPDATE papers SET authors=? WHERE paper_id=? AND COALESCE(trim(authors),'')=''",
                                         (value, paper['paper_id'])).rowcount
            if changed:
                if catalog:
                    connection.execute("UPDATE citation_catalog SET authors=? WHERE paper_id=? AND COALESCE(trim(authors),'')=''",
                                       (value, paper['paper_id']))
                count += 1
        connection.commit()
        return count
    finally:
        connection.close()
