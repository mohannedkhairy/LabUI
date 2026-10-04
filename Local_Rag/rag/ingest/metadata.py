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
