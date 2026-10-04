"""Paper Review API — mounted under /api/rag (see jfr/web/app.py).

A backend layer for a local dual-pane review workspace (main text + figures)
with in-PDF marks and a page-anchored notebook. Schema is defined in
`jfr/db/schema.py` — the tables live in the same SQLite DB as the journal-fit
and experiment stores, so the whole app remains "one local workbench, one DB."

All mark and note identifiers are client-owned uuids (crypto.randomUUID on the
browser). That keeps undo/redo history stable across snapshot rebuilds, and
means the client is allowed to send the full set back for a bulk replace.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

# jfr.db is in the parent tree; ensure it's importable
from jfr.config import get_settings
from jfr.db import get_conn

router = APIRouter()


def _conn():
    return get_conn(get_settings().db_path)


# ── Pydantic models ──────────────────────────────────────────────────────────

class MarkIn(BaseModel):
    id: str
    type: str  # one of: highlight | note | ellipse | rectangle
    page: int
    rects: list[dict[str, Any]] = []  # list of {x,y,width,height} in [0,1]
    color: str = "#f4d75e"
    note: str = ""


class MarkPatch(BaseModel):
    type: Optional[str] = None
    page: Optional[int] = None
    rects: Optional[list[dict[str, Any]]] = None
    color: Optional[str] = None
    note: Optional[str] = None


class NoteIn(BaseModel):
    id: str
    page: int
    text: str


class NotePatch(BaseModel):
    page: Optional[int] = None
    text: Optional[str] = None


class SnapshotIn(BaseModel):
    """Full-snapshot replace: used by the client for a 'commit undo/redo state'
    call to avoid 50+ individual row upserts."""
    marks: list[MarkIn] = []
    notes: list[NoteIn] = []


def _validate_paper_id(pid: str) -> str:
    pid = (pid or "").strip()
    if not re.match(r"^[\w\-\/\.]+$", pid):
        raise HTTPException(400, "invalid paper_id")
    return pid


def _validate_color(c: str) -> str:
    c = (c or "").strip()
    if not re.match(r"^#[0-9a-fA-F]{6}$", c):
        raise HTTPException(400, "invalid color")
    return c


def _validate_rects(rects: Any) -> list[dict]:
    if not isinstance(rects, list):
        raise HTTPException(400, "rects must be a list")
    cleaned = []
    for r in rects:
        if not isinstance(r, dict):
            raise HTTPException(400, "rect must be an object")
        x, y = r.get("x"), r.get("y")
        w, h = r.get("width"), r.get("height")
        vals: list[object] = [x, y, w, h]
        if any(v is None or not isinstance(v, (int, float)) or isinstance(v, bool)
               for v in vals):
            raise HTTPException(400, "rect must have numeric x,y,width,height")
        x = float(x); y = float(y); w = float(w); h = float(h)
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 and 0.0 <= w <= 1.0 and 0.0 <= h <= 1.0):
            raise HTTPException(400, "rect coordinates must be in [0,1]")
        if w <= 0 or h <= 0:
            continue
        cleaned.append({"x": x, "y": y, "width": w, "height": h})
    return cleaned


def _row_to_mark(r) -> dict:
    return {
        "id": r["id"],
        "type": r["type"],
        "page": r["page"],
        "rects": json.loads(r["rects_json"]),
        "color": r["color"],
        "note": r["note"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


def _row_to_note(r) -> dict:
    return {
        "id": r["id"],
        "page": r["page"],
        "text": r["text"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


# ── /api/rag/review ────────────────────────────────────────────────────────

@router.get("/review/papers")
def api_review_list_papers():
    """Papers that have a review record (any mark, note, or even an opened flag).
    Used by the 'Browse reviews' section on the review page."""
    conn = _conn()
    rows = conn.execute(
        """
        SELECT pr.paper_id, pr.title, pr.opened_at, pr.updated_at,
               (SELECT COUNT(*) FROM review_mark rm WHERE rm.paper_id = pr.paper_id) as marks_count,
               (SELECT COUNT(*) FROM review_note rn WHERE rn.paper_id = pr.paper_id) as notes_count
        FROM paper_review pr
        ORDER BY pr.updated_at DESC
        LIMIT 500
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/review/paper/{paper_id}")
def api_review_get(paper_id: str):
    """Full snapshot: marks, notes, and last-updated info for a paper."""
    pid = _validate_paper_id(paper_id)
    conn = _conn()
    # Ensure the paper_review row exists (lazy create on first view)
    exists = conn.execute(
        "SELECT 1 FROM paper_review WHERE paper_id = ? LIMIT 1", (pid,)
    ).fetchone()
    if not exists:
        now = None
        conn.execute(
            "INSERT OR IGNORE INTO paper_review(paper_id, opened_at) VALUES(?, COALESCE(?, ?))",
            (pid, None, "2000-01-01T00:00:00Z"),
        )
        conn.commit()
    mark_rows = conn.execute(
        "SELECT * FROM review_mark WHERE paper_id = ? ORDER BY created_at DESC", (pid,)
    ).fetchall()
    note_rows = conn.execute(
        "SELECT * FROM review_note WHERE paper_id = ? ORDER BY created_at DESC", (pid,)
    ).fetchall()
    info_row = conn.execute(
        "SELECT title, opened_at, updated_at FROM paper_review WHERE paper_id = ?",
        (pid,),
    ).fetchone()
    conn.close()
    info = dict(info_row) if info_row else {}
    return {
        "paper_id": pid,
        "title": info.get("title") or "",
        "opened_at": info.get("opened_at"),
        "updated_at": info.get("updated_at"),
        "marks": [_row_to_mark(r) for r in mark_rows],
        "notes": [_row_to_note(r) for r in note_rows],
    }


@router.delete("/review/paper/{paper_id}/clear")
def api_review_clear(paper_id: str):
    """Remove all marks + notes + the paper_review row itself (reset the space)."""
    pid = _validate_paper_id(paper_id)
    conn = _conn()
    conn.execute("DELETE FROM review_mark WHERE paper_id = ?", (pid,))
    conn.execute("DELETE FROM review_note WHERE paper_id = ?", (pid,))
    conn.execute("DELETE FROM paper_review WHERE paper_id = ?", (pid,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Marks ───────────────────────────────────────────────────────────────────

@router.get("/review/paper/{paper_id}/marks")
def api_marks_list(paper_id: str):
    pid = _validate_paper_id(paper_id)
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM review_mark WHERE paper_id = ? ORDER BY created_at DESC", (pid,)
    ).fetchall()
    conn.close()
    return [_row_to_mark(r) for r in rows]


@router.put("/review/paper/{paper_id}/marks/snapshot")
def api_marks_snapshot(paper_id: str, body: SnapshotIn):
    """Full replacement of every mark for a paper — used by the client's undo/redo
    path so it can send one request rather than 50 upserts."""
    pid = _validate_paper_id(paper_id)
    for m in body.marks:
        _validate_color(m.color)
        _validate_rects(m.rects)
        if m.type not in ("highlight", "note", "ellipse", "rectangle"):
            raise HTTPException(400, "invalid mark type")
    conn = _conn()
    # Replace all rows in one transaction
    conn.execute("DELETE FROM review_mark WHERE paper_id = ?", (pid,))
    for m in body.marks:
        conn.execute(
            "INSERT OR REPLACE INTO review_mark(id, paper_id, type, page, rects_json, color, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (m.id, pid, m.type, int(m.page), json.dumps(m.rects), m.color, m.note),
        )
    conn.execute(
        "INSERT OR IGNORE INTO paper_review(paper_id, opened_at) VALUES(?, COALESCE(?, ?))",
        (pid, None, "2000-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    return {"count": len(body.marks)}


@router.post("/review/paper/{paper_id}/marks", status_code=201)
def api_mark_create(paper_id: str, body: MarkIn):
    _validate_color(body.color)
    _validate_rects(body.rects)
    if body.type not in ("highlight", "note", "ellipse", "rectangle"):
        raise HTTPException(400, "invalid mark type")
    pid = _validate_paper_id(paper_id)
    conn = _conn()
    conn.execute(
        "INSERT OR IGNORE INTO paper_review(paper_id, opened_at) VALUES(?, COALESCE(?, ?))",
        (pid, None, "2000-01-01T00:00:00Z"),
    )
    try:
        conn.execute(
            "INSERT OR REPLACE INTO review_mark(id, paper_id, type, page, rects_json, color, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (body.id, pid, body.type, int(body.page), json.dumps(body.rects), body.color, body.note),
        )
    except Exception as e:
        conn.close()
        if "UNIQUE" in str(e):
            raise HTTPException(409, "mark id already exists")
        raise HTTPException(500, str(e))
    conn.commit()
    conn.close()
    return {"id": body.id, "ok": True}


@router.patch("/review/paper/{paper_id}/marks/{mark_id}")
def api_mark_update(paper_id: str, mark_id: str, body: MarkPatch):
    pid = _validate_paper_id(paper_id)
    if body.color is not None:
        _validate_color(body.color)
    if body.rects is not None:
        _validate_rects(body.rects)
    if body.type not in (None, "highlight", "note", "ellipse", "rectangle"):
        raise HTTPException(400, "invalid mark type")
    conn = _conn()
    if not conn.execute(
        "SELECT 1 FROM review_mark WHERE paper_id=? AND id=?", (pid, mark_id)
    ).fetchone():
        conn.close()
        raise HTTPException(404, "mark not found")
    fields = []
    params = []
    for key, new in (
        ("type", body.type),
        ("page", body.page),
        ("color", body.color),
        ("note", body.note),
    ):
        if new is not None:
            fields.append(f"{key} = ?")
            params.append(new)
    if body.rects is not None:
        fields.append("rects_json = ?")
        params.append(json.dumps(body.rects))
    if not fields:
        conn.close()
        return {"ok": True}
    fields.append("updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')")
    params.extend([pid, mark_id])
    conn.execute(
        f"UPDATE review_mark SET {', '.join(fields)} WHERE paper_id = ? AND id = ?",
        params,
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/review/paper/{paper_id}/marks/{mark_id}")
def api_mark_delete(paper_id: str, mark_id: str):
    pid = _validate_paper_id(paper_id)
    conn = _conn()
    res = conn.execute(
        "DELETE FROM review_mark WHERE paper_id=? AND id=?", (pid, mark_id)
    )
    conn.commit()
    conn.close()
    if res.rowcount == 0:
        raise HTTPException(404, "mark not found")
    return {"ok": True}


# ── Notes ───────────────────────────────────────────────────────────────────

@router.get("/review/paper/{paper_id}/notes")
def api_notes_list(paper_id: str):
    pid = _validate_paper_id(paper_id)
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM review_note WHERE paper_id = ? ORDER BY created_at DESC", (pid,)
    ).fetchall()
    conn.close()
    return [_row_to_note(r) for r in rows]


@router.put("/review/paper/{paper_id}/notes/snapshot")
def api_notes_snapshot(paper_id: str, body: SnapshotIn):
    pid = _validate_paper_id(paper_id)
    conn = _conn()
    conn.execute("DELETE FROM review_note WHERE paper_id = ?", (pid,))
    for n in body.notes:
        if not n.text.strip():
            continue
        conn.execute(
            "INSERT OR REPLACE INTO review_note(id, paper_id, page, text) VALUES(?, ?, ?, ?)",
            (n.id, pid, int(n.page), n.text),
        )
    conn.execute(
        "INSERT OR IGNORE INTO paper_review(paper_id, opened_at) VALUES(?, COALESCE(?, ?))",
        (pid, None, "2000-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    return {"count": len(body.notes)}


@router.post("/review/paper/{paper_id}/notes", status_code=201)
def api_note_create(paper_id: str, body: NoteIn):
    if not body.text.strip():
        raise HTTPException(400, "note text cannot be empty")
    pid = _validate_paper_id(paper_id)
    conn = _conn()
    conn.execute(
        "INSERT OR IGNORE INTO paper_review(paper_id, opened_at) VALUES(?, COALESCE(?, ?))",
        (pid, None, "2000-01-01T00:00:00Z"),
    )
    try:
        conn.execute(
            "INSERT OR REPLACE INTO review_note(id, paper_id, page, text) VALUES(?, ?, ?, ?)",
            (body.id, pid, int(body.page), body.text),
        )
    except Exception as e:
        conn.close()
        if "UNIQUE" in str(e):
            raise HTTPException(409, "note id already exists")
        raise HTTPException(500, str(e))
    conn.commit()
    conn.close()
    return {"id": body.id, "ok": True}


@router.patch("/review/paper/{paper_id}/notes/{note_id}")
def api_note_update(paper_id: str, note_id: str, body: NotePatch):
    pid = _validate_paper_id(paper_id)
    if body.text is not None and not body.text.strip():
        raise HTTPException(400, "note text cannot be empty")
    conn = _conn()
    if not conn.execute(
        "SELECT 1 FROM review_note WHERE paper_id=? AND id=?", (pid, note_id)
    ).fetchone():
        conn.close()
        raise HTTPException(404, "note not found")
    fields = []
    params = []
    for key, new in (("page", body.page), ("text", body.text)):
        if new is not None:
            fields.append(f"{key} = ?")
            params.append(new)
    if not fields:
        conn.close()
        return {"ok": True}
    fields.append("updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')")
    params.extend([pid, note_id])
    conn.execute(
        f"UPDATE review_note SET {', '.join(fields)} WHERE paper_id = ? AND id = ?",
        params,
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/review/paper/{paper_id}/notes/{note_id}")
def api_note_delete(paper_id: str, note_id: str):
    pid = _validate_paper_id(paper_id)
    conn = _conn()
    res = conn.execute(
        "DELETE FROM review_note WHERE paper_id=? AND id=?", (pid, note_id)
    )
    conn.commit()
    conn.close()
    if res.rowcount == 0:
        raise HTTPException(404, "note not found")
    return {"ok": True}


# ── Plain-text export ────────────────────────────────────────────────────────

@router.get("/review/paper/{paper_id}/export")
def api_review_export(paper_id: str):
    """Concatenate the review notes + mark notes into a single .txt export
    (parallel to Parsecneuro's `export-notes`)."""
    pid = _validate_paper_id(paper_id)
    conn = _conn()
    note_rows = conn.execute(
        "SELECT * FROM review_note WHERE paper_id = ? ORDER BY created_at ASC", (pid,)
    ).fetchall()
    mark_rows = conn.execute(
        "SELECT * FROM review_mark WHERE paper_id = ? ORDER BY created_at ASC", (pid,)
    ).fetchall()
    info_row = conn.execute(
        "SELECT title, opened_at FROM paper_review WHERE paper_id = ?", (pid,)
    ).fetchone()
    conn.close()
    info = dict(info_row) if info_row else {}

    lines: list[str] = []
    title = info.get("title") or pid
    lines.append(f"# Review: {title}")
    lines.append(f"Paper ID: {pid}")
    if info.get("opened_at"):
        lines.append(f"Opened: {info['opened_at']}")
    lines.append("")
    if note_rows:
        lines.append(f"── Notes ({len(note_rows)}) ──")
        for r in note_rows:
            lines.append(f"[p{r['page']}] {r['text']}\n")
    else:
        lines.append("── No notes ──\n")
    if mark_rows:
        lines.append(f"── Marks ({len(mark_rows)}) ──")
        for r in mark_rows:
            rects = json.loads(r["rects_json"])
            rects_str = ", ".join(
                f"({rc['x']:.3f},{rc['y']:.3f},{rc['width']:.3f}x{rc['height']:.3f})"
                for rc in rects
            )
            lines.append(
                f"[{r['type']}] p{r['page']} color {r['color']}  {rects_str}\n"
            )
            if r["note"]:
                lines.append(f"   ↳ {r['note']}\n")
    else:
        lines.append("── No marks ──")
    return PlainTextResponse("\n".join(lines))


# ── PDF proxy (convenience so the browser doesn't also hit /api/rag/pdf) ──────

@router.get("/review/paper/{paper_id}/pdf")
def api_review_pdf(paper_id: str):
    """Serve the source PDF for this paper. Delegates to the rag DB."""
    pid = _validate_paper_id(paper_id)
    try:
        import sys
        import os
        from pathlib import Path

        _DEFAULT_RAG_DIR = (
            Path(__file__).resolve().parents[3] / "Local_Rag" / "rag"
        )
        _LOCAL_RAG_DIR = Path(
            os.environ.get("LABUI_RAG_DIR") or str(_DEFAULT_RAG_DIR)
        )
        if str(_LOCAL_RAG_DIR) not in sys.path:
            sys.path.insert(0, str(_LOCAL_RAG_DIR))
        from config import DB_PATH as RAG_DB  # type: ignore
        import sqlite3

        if not RAG_DB.exists():
            raise HTTPException(404, "rag database not found")
        conn = sqlite3.connect(str(RAG_DB))
        row = conn.execute(
            "SELECT source_pdf FROM papers WHERE paper_id = ?", (pid,)
        ).fetchone()
        conn.close()
        if not row or not row[0]:
            raise HTTPException(404, "paper not found in rag db")
        p = Path(row[0])
        if not p.exists():
            raise HTTPException(404, "source PDF file missing on disk")
        from fastapi.responses import FileResponse

        return FileResponse(str(p), media_type="application/pdf", filename=p.name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"pdf lookup failed: {e}")
