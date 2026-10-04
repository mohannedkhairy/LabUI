"""
Writing projects — multi-file markdown manuscripts with library citations
and cross-file links.

Storage (mirrors the notes/clips pattern: files on disk + a small registry DB):
  - Files on disk:  <MANUSCRIPTS_DIR>/<project-slug>/<file-slug>.md
  - Registry DB:    <DATA_DIR>/manuscripts.db
      writing_projects — id, slug, title, optional JFR link, claim/techniques
      writing_files    — project_id, slug, title, sort_order, timestamps

Citations:
  `@paper-id` tokens (paper_id exactly as stored in the RAG `papers` table,
  e.g. `@zhang-et-al-2024-hydroxide-and-hydronium-ions...`). Only tokens that
  resolve to a real paper are treated as citations, so plain `@words` and
  email addresses never match. Numbering = order of first appearance across
  the project (files in sort order), ACS-style [n].

Cross-file links:
  `[[file-slug]]` or `[[file-slug|display text]]` — resolved against the
  project's own files. Backlinks = which other files reference a given file.
"""
from __future__ import annotations

import json
import mimetypes
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

from config import DB_PATH, MANUSCRIPTS_DB_PATH, MANUSCRIPTS_DIR

MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MB per markdown file
MAX_ASSET_BYTES = 15 * 1024 * 1024  # 15 MB per figure/image asset
ASSET_MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}
PAGE_STYLES = {"manuscript", "blank", "lined", "grid", "dot", "tinted"}
DEFAULT_LAYOUT = {
    "page_size": "letter",
    "margin_top": 22,
    "margin_right": 22,
    "margin_bottom": 22,
    "margin_left": 22,
    "font_size": 14,
    "line_height": 1.72,
    "measure": 86,
    "font_family": "serif",
    "page_style": "manuscript",
    "page_color": "#fffdf8",
}

# ── Regexes ───────────────────────────────────────────────────────────────────
# @paper-id: @ not preceded by word char / dot / slash (kills emails),
# id chars are exactly the paper_id alphabet (verified: [\w\-] only).
CITE_TOKEN_RE = re.compile(r"(?<![\w\.\-])@([A-Za-z0-9_\-]+)")
# [[slug]] or [[slug|text]]
WIKILINK_RE = re.compile(r"\[\[\s*([A-Za-z0-9_\-]+)(?:\s*\|\s*([^\[\]]+?))?\s*\]\]")
# [text](slug.md) relative file link
MD_FILELINK_RE = re.compile(r"\[[^\]]+\]\(([\w\-]+)\.md\)")
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,79}$")


class WritingError(ValueError):
    """User-facing error (bad slug, not found, size limit…)."""


# ── DB ────────────────────────────────────────────────────────────────────────

DDL = """
CREATE TABLE IF NOT EXISTS writing_projects (
    id                  TEXT PRIMARY KEY,
    slug                TEXT UNIQUE NOT NULL,
    title               TEXT NOT NULL,
    jfr_manuscript_id   TEXT,
    principal_claim     TEXT NOT NULL DEFAULT '',
    techniques          TEXT NOT NULL DEFAULT '',
    settings_json       TEXT NOT NULL DEFAULT '{}',
    created_at          REAL NOT NULL,
    updated_at          REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS writing_files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL REFERENCES writing_projects(id) ON DELETE CASCADE,
    slug        TEXT NOT NULL,
    title       TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    page_style  TEXT NOT NULL DEFAULT 'manuscript',
    layout_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(project_id, slug)
);
CREATE INDEX IF NOT EXISTS idx_writing_files_project ON writing_files(project_id, sort_order);

CREATE TABLE IF NOT EXISTS writing_assets (
    id            TEXT PRIMARY KEY,
    project_id    TEXT NOT NULL REFERENCES writing_projects(id) ON DELETE CASCADE,
    stored_name   TEXT NOT NULL,
    original_name TEXT NOT NULL,
    mime_type     TEXT NOT NULL,
    byte_size     INTEGER NOT NULL,
    created_at    REAL NOT NULL,
    UNIQUE(project_id, stored_name)
);
CREATE INDEX IF NOT EXISTS idx_writing_assets_project ON writing_assets(project_id, created_at);
"""


def new_conn() -> sqlite3.Connection:
    MANUSCRIPTS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(MANUSCRIPTS_DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(DDL)
    # Migrations for databases created before layout/assets support.
    for table, columns in {
        "writing_projects": [("settings_json", "TEXT NOT NULL DEFAULT '{}'" )],
        "writing_files": [
            ("page_style", "TEXT NOT NULL DEFAULT 'manuscript'"),
            ("layout_json", "TEXT NOT NULL DEFAULT '{}'"),
        ],
    }.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, ddl in columns:
            if name not in have:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                except sqlite3.OperationalError as exc:
                    # Another request may have completed the same idempotent
                    # migration between PRAGMA and ALTER.
                    if "duplicate column name" not in str(exc).lower():
                        raise
    conn.execute("CREATE TABLE IF NOT EXISTS writing_assets ("
                 "id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES writing_projects(id) ON DELETE CASCADE, "
                 "stored_name TEXT NOT NULL, original_name TEXT NOT NULL, mime_type TEXT NOT NULL, "
                 "byte_size INTEGER NOT NULL, created_at REAL NOT NULL, UNIQUE(project_id, stored_name))")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_writing_assets_project ON writing_assets(project_id, created_at)")
    conn.commit()
    conn.row_factory = sqlite3.Row
    return conn


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _slugify(text: str, taken: set[str] | None = None) -> str:
    base = re.sub(r"[^\w\-]+", "-", (text or "").strip()).strip("-").lower()[:60]
    base = base or "untitled"
    if taken is None:
        return base
    candidate, i = base, 2
    while candidate in taken:
        candidate = f"{base}-{i}"
        i += 1
    return candidate


def _validate_slug(slug: str) -> str:
    slug = (slug or "").strip()
    if not SLUG_RE.match(slug):
        raise WritingError(
            "invalid name — use letters, numbers, '_' or '-' (no spaces, dots, slashes)"
        )
    return slug


def _project_dir(slug: str) -> Path:
    return MANUSCRIPTS_DIR / slug


def _file_path(project_slug: str, file_slug: str) -> Path:
    return _project_dir(project_slug) / f"{file_slug}.md"


def _require_project(conn: sqlite3.Connection, project_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT p.*, (SELECT COUNT(*) FROM writing_files f WHERE f.project_id = p.id) AS file_count"
        " FROM writing_projects p WHERE p.id = ?", (project_id,)
    ).fetchone()
    if row is None:
        raise WritingError("project not found")
    return row


# ── Projects ──────────────────────────────────────────────────────────────────

def create_project(
    conn: sqlite3.Connection,
    title: str,
    slug: str = "",
    principal_claim: str = "",
    techniques: str = "",
) -> dict:
    title = (title or "").strip() or "Untitled manuscript"
    taken = {r[0] for r in conn.execute("SELECT slug FROM writing_projects")}
    slug = _validate_slug(slug) if slug else _slugify(title, taken)
    if slug in taken:
        raise WritingError(f"a project named '{slug}' already exists")
    pid = _gen_id("wp")
    now = time.time()
    conn.execute(
        "INSERT INTO writing_projects (id, slug, title, principal_claim, techniques, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (pid, slug, title, principal_claim or "", techniques or "", now, now),
    )
    conn.commit()
    return get_project(conn, pid)


def list_projects(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT p.*, (SELECT COUNT(*) FROM writing_files f WHERE f.project_id = p.id) AS file_count"
        " FROM writing_projects p ORDER BY p.updated_at DESC"
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            saved = json.loads(d.get("settings_json") or "{}")
        except (TypeError, ValueError):
            saved = {}
        d["settings"] = {**DEFAULT_LAYOUT, **saved}
        d["files"] = [
            dict(f) for f in conn.execute(
                "SELECT slug, title, sort_order, page_style, layout_json FROM writing_files"
                " WHERE project_id=? ORDER BY sort_order, slug", (r["id"],)
            ).fetchall()
        ]
        for f in d["files"]:
            try:
                f["layout"] = json.loads(f.get("layout_json") or "{}")
            except (TypeError, ValueError):
                f["layout"] = {}
            path = _file_path(d["slug"], f["slug"])
            f["words"] = (word_count(path.read_text(encoding="utf-8", errors="replace"))
                          if path.exists() else 0)
        d["total_words"] = sum(f["words"] for f in d["files"])
        out.append(d)
    return out


def get_project(conn: sqlite3.Connection, project_id: str) -> dict:
    r = _require_project(conn, project_id)
    d = dict(r)
    try:
        saved = json.loads(d.get("settings_json") or "{}")
    except (TypeError, ValueError):
        saved = {}
    d["settings"] = {**DEFAULT_LAYOUT, **saved}
    d["files"] = [
        dict(f) for f in conn.execute(
            "SELECT slug, title, sort_order, updated_at, page_style, layout_json FROM writing_files"
            " WHERE project_id=? ORDER BY sort_order, slug", (project_id,)
        ).fetchall()
    ]
    for f in d["files"]:
        try:
            f["layout"] = json.loads(f.get("layout_json") or "{}")
        except (TypeError, ValueError):
            f["layout"] = {}
    return d


def update_project(
    conn: sqlite3.Connection,
    project_id: str,
    title: Optional[str] = None,
    jfr_manuscript_id: Optional[str] = None,
    principal_claim: Optional[str] = None,
    techniques: Optional[str] = None,
    settings: Optional[dict] = None,
) -> dict:
    _require_project(conn, project_id)
    fields, params = [], []
    if title is not None:
        title = title.strip() or "Untitled manuscript"
        fields.append("title=?"); params.append(title)
    if jfr_manuscript_id is not None:
        fields.append("jfr_manuscript_id=?"); params.append(jfr_manuscript_id or None)
    if principal_claim is not None:
        fields.append("principal_claim=?"); params.append(principal_claim)
    if techniques is not None:
        fields.append("techniques=?"); params.append(techniques)
    if settings is not None:
        merged = {**DEFAULT_LAYOUT, **(settings or {})}
        merged["page_size"] = merged["page_size"] if merged["page_size"] in ("letter", "a4") else "letter"
        merged["page_style"] = merged["page_style"] if merged["page_style"] in PAGE_STYLES else "manuscript"
        fields.append("settings_json=?"); params.append(json.dumps(merged, separators=(",", ":")))
    if fields:
        fields.append("updated_at=?"); params.append(time.time())
        params.append(project_id)
        conn.execute(f"UPDATE writing_projects SET {', '.join(fields)} WHERE id=?", params)
        conn.commit()
    return get_project(conn, project_id)


def delete_project(conn: sqlite3.Connection, project_id: str) -> None:
    r = _require_project(conn, project_id)
    conn.execute("DELETE FROM writing_projects WHERE id=?", (project_id,))
    conn.commit()
    d = _project_dir(r["slug"])
    if d.exists():
        import shutil
        shutil.rmtree(d, ignore_errors=True)


# ── Files ─────────────────────────────────────────────────────────────────────

def _list_file_slugs(conn: sqlite3.Connection, project_id: str) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT slug FROM writing_files WHERE project_id=? ORDER BY sort_order, slug",
        (project_id,),
    ).fetchall()]


def create_file(
    conn: sqlite3.Connection,
    project_id: str,
    title: str,
    slug: str = "",
    content: str = "",
    page_style: str = "manuscript",
    layout: Optional[dict] = None,
) -> dict:
    p = _require_project(conn, project_id)
    title = (title or "").strip() or "Untitled section"
    taken = set(_list_file_slugs(conn, project_id))
    slug = _validate_slug(slug) if slug else _slugify(title, taken)
    if slug in taken:
        raise WritingError(f"a file named '{slug}' already exists in this project")
    if len((content or "").encode("utf-8")) > MAX_FILE_BYTES:
        raise WritingError("content too large (max 2 MB)")
    page_style = page_style if page_style in PAGE_STYLES else "manuscript"
    now = time.time()
    next_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM writing_files WHERE project_id=?",
        (project_id,),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO writing_files (project_id, slug, title, sort_order, created_at, updated_at, page_style, layout_json)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (project_id, slug, title, next_order, now, now, page_style,
         json.dumps(layout or {}, separators=(",", ":"))),
    )
    d = _project_dir(p["slug"])
    d.mkdir(parents=True, exist_ok=True)
    _file_path(p["slug"], slug).write_text(content or "", encoding="utf-8")
    conn.execute("UPDATE writing_projects SET updated_at=? WHERE id=?", (now, project_id))
    conn.commit()
    return get_file(conn, project_id, slug)


def _require_file(conn: sqlite3.Connection, project_id: str, slug: str) -> tuple[dict, Path]:
    slug = _validate_slug(slug)
    p = _require_project(conn, project_id)
    row = conn.execute(
        "SELECT * FROM writing_files WHERE project_id=? AND slug=?", (project_id, slug)
    ).fetchone()
    if row is None:
        raise WritingError("file not found")
    return dict(row), _file_path(p["slug"], slug)


def get_file(conn: sqlite3.Connection, project_id: str, slug: str) -> dict:
    row, path = _require_file(conn, project_id, slug)
    p = _require_project(conn, project_id)
    content = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    d = dict(row)
    d["content"] = content
    d["word_count"] = word_count(content)
    d["project_slug"] = p["slug"]
    d["page_style"] = d.get("page_style") if d.get("page_style") in PAGE_STYLES else "manuscript"
    try:
        d["layout"] = json.loads(d.get("layout_json") or "{}")
    except (TypeError, ValueError):
        d["layout"] = {}
    # Outgoing references (citations + wikilinks) for the links panel.
    d["cites"] = resolve_citations(content)
    d["links"] = resolve_wikilinks(content, set(_list_file_slugs(conn, project_id)))
    d["backlinks"] = [
        s for s in _list_file_slugs(conn, project_id)
        if s != slug and _file_references(conn, p["slug"], project_id, s, slug)
    ]
    return d


def _file_references(
    conn: sqlite3.Connection, project_slug: str, project_id: str, other_slug: str, target_slug: str
) -> bool:
    path = _file_path(project_slug, other_slug)
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return bool(
        re.search(r"\[\[\s*" + re.escape(target_slug) + r"(?:\s*\||\s*\]\])", text) or
        re.search(r"\]\(" + re.escape(target_slug) + r"\.md\)", text)
    )


def update_file(
    conn: sqlite3.Connection,
    project_id: str,
    slug: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    page_style: Optional[str] = None,
    layout: Optional[dict] = None,
) -> dict:
    row, path = _require_file(conn, project_id, slug)
    if content is not None and len(content.encode("utf-8")) > MAX_FILE_BYTES:
        raise WritingError("content too large (max 2 MB)")
    now = time.time()
    if title is not None:
        title = title.strip() or row["title"]
        conn.execute(
            "UPDATE writing_files SET title=?, updated_at=? WHERE project_id=? AND slug=?",
            (title, now, project_id, slug),
        )
    if content is not None:
        path.write_text(content, encoding="utf-8")
    if page_style is not None:
        if page_style not in PAGE_STYLES:
            raise WritingError(f"unknown page style: {page_style}")
        conn.execute("UPDATE writing_files SET page_style=? WHERE project_id=? AND slug=?",
                     (page_style, project_id, slug))
    if layout is not None:
        conn.execute("UPDATE writing_files SET layout_json=? WHERE project_id=? AND slug=?",
                     (json.dumps(layout, separators=(",", ":")), project_id, slug))
    conn.execute(
        "UPDATE writing_files SET updated_at=? WHERE project_id=? AND slug=?",
        (now, project_id, slug),
    )
    conn.execute("UPDATE writing_projects SET updated_at=? WHERE id=?", (now, project_id))
    conn.commit()
    return get_file(conn, project_id, slug)


def delete_file(conn: sqlite3.Connection, project_id: str, slug: str) -> None:
    row, path = _require_file(conn, project_id, slug)
    conn.execute("DELETE FROM writing_files WHERE project_id=? AND slug=?", (project_id, slug))
    conn.execute("UPDATE writing_projects SET updated_at=? WHERE id=?", (time.time(), project_id))
    conn.commit()
    if path.exists():
        path.unlink()


def reorder_files(conn: sqlite3.Connection, project_id: str, slugs: list[str]) -> None:
    _require_project(conn, project_id)
    known = set(_list_file_slugs(conn, project_id))
    if set(slugs) != known:
        raise WritingError("reorder list must contain every file slug exactly once")
    for i, s in enumerate(slugs):
        conn.execute(
            "UPDATE writing_files SET sort_order=? WHERE project_id=? AND slug=?",
            (i, project_id, s),
        )
    conn.commit()


# ── Project assets ───────────────────────────────────────────────────────────

def _asset_project(conn: sqlite3.Connection, project_id: str) -> sqlite3.Row:
    return _require_project(conn, project_id)


def _asset_ext(original_name: str, mime_type: str) -> str:
    if mime_type in ASSET_MIME_TYPES:
        return ASSET_MIME_TYPES[mime_type]
    guessed = mimetypes.guess_extension(mime_type or "") or Path(original_name or "").suffix.lower()
    return guessed if guessed in set(ASSET_MIME_TYPES.values()) else ".bin"


def _asset_path(project_slug: str, stored_name: str) -> Path:
    return _project_dir(project_slug) / "assets" / stored_name


def list_assets(conn: sqlite3.Connection, project_id: str) -> list[dict]:
    p = _asset_project(conn, project_id)
    rows = conn.execute(
        "SELECT id, original_name, mime_type, byte_size, created_at, stored_name "
        "FROM writing_assets WHERE project_id=? ORDER BY created_at DESC",
        (project_id,),
    ).fetchall()
    return [{**dict(r), "url": f"/api/rag/projects/{project_id}/assets/{r['id']}"} for r in rows
            if _asset_path(p["slug"], r["stored_name"]).exists()]


def get_asset(conn: sqlite3.Connection, project_id: str, asset_id: str) -> tuple[dict, Path]:
    p = _asset_project(conn, project_id)
    row = conn.execute(
        "SELECT * FROM writing_assets WHERE project_id=? AND id=?", (project_id, asset_id)
    ).fetchone()
    if row is None:
        raise WritingError("asset not found")
    path = _asset_path(p["slug"], row["stored_name"])
    if not path.exists():
        raise WritingError("asset file not found")
    return dict(row), path


def create_asset(
    conn: sqlite3.Connection,
    project_id: str,
    original_name: str,
    mime_type: str,
    data: bytes,
) -> dict:
    p = _asset_project(conn, project_id)
    mime_type = (mime_type or "").split(";", 1)[0].strip().lower()
    if mime_type not in ASSET_MIME_TYPES:
        raise WritingError("unsupported image type — use PNG, JPEG, WebP, GIF, or SVG")
    if not data or len(data) > MAX_ASSET_BYTES:
        raise WritingError("image is empty or larger than 15 MB")
    original_name = Path(original_name or "figure").name[:180]
    asset_id = _gen_id("asset")
    stored_name = asset_id + _asset_ext(original_name, mime_type)
    path = _asset_path(p["slug"], stored_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    now = time.time()
    conn.execute(
        "INSERT INTO writing_assets (id, project_id, stored_name, original_name, mime_type, byte_size, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (asset_id, project_id, stored_name, original_name, mime_type, len(data), now),
    )
    conn.execute("UPDATE writing_projects SET updated_at=? WHERE id=?", (now, project_id))
    conn.commit()
    row, _ = get_asset(conn, project_id, asset_id)
    return {**row, "url": f"/api/rag/projects/{project_id}/assets/{asset_id}"}


def delete_asset(conn: sqlite3.Connection, project_id: str, asset_id: str) -> None:
    row, path = get_asset(conn, project_id, asset_id)
    conn.execute("DELETE FROM writing_assets WHERE project_id=? AND id=?", (project_id, asset_id))
    conn.execute("UPDATE writing_projects SET updated_at=? WHERE id=?", (time.time(), project_id))
    conn.commit()
    path.unlink(missing_ok=True)


# ── Citations & links resolution ──────────────────────────────────────────────

def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _load_known_paper_ids() -> set[str]:
    if not DB_PATH.exists():
        return set()
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    try:
        return {r[0] for r in conn.execute("SELECT paper_id FROM papers")}
    finally:
        conn.close()


def resolve_citations(text: str) -> list[str]:
    """Unique citation identifiers cited in text, in first-appearance order.

    Both legacy RAG ``paper_id`` values and citation-catalog keys are accepted.
    For catalog entries linked to a RAG paper we return the paper id to retain
    compatibility with older exports; standalone imported references use their
    catalog key.
    """
    known = _load_known_paper_ids()
    seen: list[str] = []
    for m in CITE_TOKEN_RE.finditer(text or ""):
        token = m.group(1)
        canonical = token if token in known else None
        if canonical is None:
            try:
                from citations import resolve_key
                rec = resolve_key(token)
                canonical = (rec or {}).get("paper_id") or (rec or {}).get("citation_key")
            except Exception:
                canonical = None
        if canonical and canonical not in seen:
            seen.append(canonical)
    return seen


def resolve_wikilinks(text: str, valid_slugs: set[str]) -> list[dict]:
    """Wikilinks / relative .md links to files in this project, in order."""
    seen: list[dict] = []
    for m in WIKILINK_RE.finditer(text or ""):
        slug, label = m.group(1), (m.group(2) or m.group(1)).strip()
        if slug in valid_slugs and all(s["slug"] != slug for s in seen):
            seen.append({"slug": slug, "label": label})
    for m in MD_FILELINK_RE.finditer(text or ""):
        slug = m.group(1)
        if slug in valid_slugs and all(s["slug"] != slug for s in seen):
            seen.append({"slug": slug, "label": slug})
    return seen


def _paper_row(paper_id: str) -> Optional[dict]:
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    try:
        row = conn.execute(
            "SELECT paper_id, title, authors, year, doi, journal, volume, issue, pages, publisher, url, abstract FROM papers WHERE paper_id=?",
            (paper_id,),
        ).fetchone()
        return dict(zip(("paper_id", "title", "authors", "year", "doi", "journal", "volume", "issue", "pages", "publisher", "url", "abstract"), row)) if row else None
    finally:
        conn.close()


def _catalog_row(token: str) -> Optional[dict]:
    """Resolve a catalog key/legacy id to a metadata record, if available."""
    try:
        from citations import resolve_key
        rec = resolve_key(token)
        if not rec:
            return None
        return {
            "paper_id": rec.get("paper_id") or rec.get("citation_key"),
            "citation_key": rec.get("citation_key"),
            "title": rec.get("title"), "authors": rec.get("authors"),
            "year": rec.get("year"), "doi": rec.get("doi"),
            "journal": rec.get("journal"), "volume": rec.get("volume"),
            "issue": rec.get("issue"), "pages": rec.get("pages"),
            "publisher": rec.get("publisher"), "url": rec.get("url"),
        }
    except Exception:
        return None


def project_citations(conn: sqlite3.Connection, project_id: str) -> list[dict]:
    """All cited papers in the project, numbered by first appearance across
    files (files in sort order)."""
    p = _require_project(conn, project_id)
    ordered: list[str] = []
    for f in conn.execute(
        "SELECT slug FROM writing_files WHERE project_id=? ORDER BY sort_order, slug",
        (project_id,),
    ).fetchall():
        path = _file_path(p["slug"], f["slug"])
        if not path.exists():
            continue
        for pid in resolve_citations(path.read_text(encoding="utf-8", errors="replace")):
            if pid not in ordered:
                ordered.append(pid)
    out = []
    for n, pid in enumerate(ordered, start=1):
        row = _paper_row(pid) or _catalog_row(pid) or {"paper_id": pid, "title": None, "authors": None, "year": None, "doi": None}
        # Add the stable catalog key even when the legacy papers row resolved
        # first, so BibTeX exports and the UI can display the short key.
        if "citation_key" not in row:
            cat = _catalog_row(pid)
            if cat:
                row = {**row, "citation_key": cat.get("citation_key")}
        out.append({"n": n, **row})
    return out


def search_papers(q: str, limit: int = 12) -> list[dict]:
    """Citation-picker search over the library (title/authors/doi/paper_id)."""
    q = (q or "").strip()
    if len(q) < 2:
        return []
    if not DB_PATH.exists():
        return []
    # Catalog search includes stable keys, aliases, imported references, and
    # richer metadata while retaining the old endpoint's ``paper_id`` field.
    try:
        from citations import catalog_search
        catalog = catalog_search(q, limit)
        if catalog:
            return catalog
    except Exception:
        pass
    like = f"%{q.replace('%', '').replace('_', '')}%"
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    try:
        rows = conn.execute(
            """SELECT paper_id, title, authors, year, doi FROM papers
               WHERE title LIKE ? OR authors LIKE ? OR doi LIKE ? OR paper_id LIKE ?
               ORDER BY (year IS NULL), year DESC LIMIT ?""",
            (like, like, like, like, limit),
        ).fetchall()
        return [dict(zip(("paper_id", "title", "authors", "year", "doi"), r)) for r in rows]
    finally:
        conn.close()


# ── Export ────────────────────────────────────────────────────────────────────

def _bibtex_key(paper_id: str) -> str:
    key = re.sub(r"[^A-Za-z0-9]", "", paper_id)
    return key[:40] or "ref"


def render_bibtex(citations: list[dict]) -> str:
    lines = ["% References — cited in this manuscript (generated by LabUI)", ""]
    for c in citations:
        key = c.get("citation_key") or _bibtex_key(c["paper_id"])
        fields = []
        if c.get("authors"):
            fields.append(f"  author  = {{{c['authors']}}},")
        if c.get("title"):
            fields.append(f"  title   = {{{c['title']}}},")
        if c.get("year"):
            fields.append(f"  year    = {{{c['year']}}},")
        if c.get("journal"):
            fields.append(f"  journal = {{{c['journal']}}},")
        if c.get("volume"):
            fields.append(f"  volume  = {{{c['volume']}}},")
        if c.get("issue"):
            fields.append(f"  number  = {{{c['issue']}}},")
        if c.get("pages"):
            fields.append(f"  pages   = {{{c['pages']}}},")
        if c.get("publisher"):
            fields.append(f"  publisher = {{{c['publisher']}}},")
        if c.get("doi"):
            fields.append(f"  doi     = {{{c['doi']}}},")
        if c.get("url"):
            fields.append(f"  url     = {{{c['url']}}},")
        lines.append(f"@article{{{key},")
        lines.extend(fields)
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


def _replace_citations(text: str, numbered: dict[str, int]) -> str:
    def sub(m: re.Match) -> str:
        n = numbered.get(m.group(1))
        return f"[{n}]" if n else m.group(0)
    return CITE_TOKEN_RE.sub(sub, text or "")


def _flatten_filelinks(text: str, titles_by_slug: dict[str, str]) -> str:
    """For a clean standalone manuscript: [[slug|label]] → label, [[slug]] →
    the section's title, [text](slug.md) → text."""
    def wik(m: re.Match) -> str:
        return m.group(2) or titles_by_slug.get(m.group(1), m.group(1))
    text = WIKILINK_RE.sub(wik, text or "")
    text = MD_FILELINK_RE.sub(r"\1", text)
    return text


def render_export_md(conn: sqlite3.Connection, project_id: str) -> str:
    """Combined manuscript: title, files in order, then a numbered References
    section. `@paper-id` tokens become [n]."""
    p = _require_project(conn, project_id)
    citations = project_citations(conn, project_id)
    numbered = {}
    for c in citations:
        numbered[c["paper_id"]] = c["n"]
        if c.get("citation_key"):
            numbered[c["citation_key"]] = c["n"]
    titles: dict[str, str] = {}

    parts = [f"# {p['title']}", ""]
    file_rows = conn.execute(
        "SELECT slug, title FROM writing_files WHERE project_id=? ORDER BY sort_order, slug",
        (project_id,),
    ).fetchall()
    titles = {f["slug"]: f["title"] for f in file_rows}
    for f in file_rows:
        path = _file_path(p["slug"], f["slug"])
        body = path.read_text(encoding="utf-8", errors="replace").strip() if path.exists() else ""
        if not body:
            continue
        first = body.splitlines()[0].strip() if body else ""
        if not first.startswith("#"):
            parts.append(f"## {f['title']}")
            parts.append("")
        parts.append(_flatten_filelinks(_replace_citations(body, numbered), titles))
        parts.append("")
    if citations:
        parts.append("## References")
        parts.append("")
        for c in citations:
            authors = f"{c['authors']}. " if c.get("authors") else ""
            year = f" {c['year']}." if c.get("year") else ""
            doi = f" DOI: {c['doi']}." if c.get("doi") else ""
            parts.append(f"[{c['n']}] {authors}{c.get('title') or c['paper_id']}.{year}{doi}")
    return "\n".join(parts).rstrip() + "\n"


def abstract_text(conn: sqlite3.Connection, project_id: str) -> str:
    """Best-effort abstract for JFR push: file 'abstract' if present, else
    the first non-empty file."""
    p = _require_project(conn, project_id)
    files = conn.execute(
        "SELECT slug FROM writing_files WHERE project_id=? ORDER BY sort_order, slug",
        (project_id,),
    ).fetchall()
    candidates = [f["slug"] for f in files]
    for slug in (["abstract"] if "abstract" in candidates else []) + (candidates[:1] if candidates else []):
        path = _file_path(p["slug"], slug)
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                return text
    return ""
