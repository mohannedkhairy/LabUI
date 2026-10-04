"""
Experiment notes ⇄ Research-Lab Notes, kept in sync both ways.

An experiment's notes (`experiment.notes_md` in the JFR database) are mirrored
into the Notes library as one markdown file per experiment:

    NOTES_DIR/experiment-<exp_id>.md
    ---
    title: <experiment name>
    experiment: <exp_id>
    folder: experiments          # the "Experiments" folder, created on demand
    date: <first written>
    ---

    # <experiment name>

    <notes_md>

Direction of truth:
  * Saving an experiment (Planner, API) rewrites the mirror from notes_md.
  * Editing the mirror in Notes writes the body back into notes_md
    (rag_routes.api_note_update calls `update_from_note`).
  * Clearing an experiment's notes removes the mirror; deleting an experiment
    keeps the note but unlinks it — the writing is never thrown away.
  * Moving the mirror to another Notes folder is respected on later syncs.

Notes are plain files handled by rag_routes; the frontmatter format here
matches its `_parse_frontmatter` / `_write_note`. Everything is best-effort:
a Notes failure never blocks saving an experiment.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

FOLDER_ID = "experiments"
FOLDER_NAME = "Experiments"
_FOLDERS_FILE = ".folders.json"
_FM_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


def notes_dir() -> Path | None:
    try:
        from config import NOTES_DIR          # Local_Rag/rag/config.py
        return Path(NOTES_DIR)
    except Exception:
        return None


def note_id(exp_id: str) -> str:
    return f"experiment-{exp_id}"


def _parse(text: str) -> tuple[dict, str]:
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip("\"'")
    return meta, text[m.end():]


def _write(path: Path, meta: dict, body: str) -> None:
    lines = ["---"] + [f"{k}: {v}" for k, v in meta.items() if v] + ["---"]
    text = "\n".join(lines) + "\n\n" + body
    if path.exists() and path.read_text(encoding="utf-8", errors="replace") == text:
        return                                # unchanged — keep the mtime
    path.write_text(text, encoding="utf-8")


def _one_line(s: str) -> str:
    # Frontmatter values are single lines.
    return re.sub(r"\s+", " ", s or "").strip()


def ensure_folder(nd: Path) -> None:
    p = nd / _FOLDERS_FILE
    try:
        folders = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    except (OSError, ValueError):
        folders = []
    if any(f.get("id") == FOLDER_ID for f in folders):
        return
    folders.append({"id": FOLDER_ID, "name": FOLDER_NAME,
                    "created_at": datetime.now().isoformat()[:19]})
    p.write_text(json.dumps(folders, ensure_ascii=False, indent=2), encoding="utf-8")


def _strip_heading(body: str, title: str) -> str:
    """Body as stored in the note, minus the `# title` line the writer adds."""
    body = body.lstrip("\n")
    m = re.match(r"#\s+(.+?)\s*\n", body)
    if m and m.group(1).strip() == title.strip():
        body = body[m.end():]
    return body.strip("\n")


def sync(exp: dict) -> str | None:
    """Mirror one experiment's notes into Notes. Returns the note id, or None."""
    nd = notes_dir()
    if nd is None or not exp or not exp.get("id"):
        return None
    try:
        nd.mkdir(parents=True, exist_ok=True)
        path = nd / f"{note_id(exp['id'])}.md"
        text = (exp.get("notes_md") or "").strip()
        meta: dict = {}
        if path.exists():
            meta, _ = _parse(path.read_text(encoding="utf-8", errors="replace"))
        if not text:
            # Notes cleared in the experiment → drop the mirror (only if it is
            # still ours; an unlinked note is the user's now).
            if path.exists() and meta.get("experiment") == exp["id"]:
                path.unlink()
            return None
        ensure_folder(nd)
        title = _one_line(exp.get("name") or exp["id"])
        _write(path, {
            "title": title,
            "experiment": exp["id"],
            "folder": meta.get("folder") or FOLDER_ID,
            "date": meta.get("date") or datetime.now().isoformat()[:19],
        }, f"# {title}\n\n{text}\n")
        return note_id(exp["id"])
    except Exception as e:                    # never block the experiment save
        print(f"[experiment-notes] sync {exp.get('id')}: {e}")
        return None


def unlink(exp_id: str, name: str = "") -> None:
    """Experiment deleted: keep its note, drop the link, say so in the title."""
    nd = notes_dir()
    if nd is None:
        return
    path = nd / f"{note_id(exp_id)}.md"
    try:
        if not path.exists():
            return
        meta, body = _parse(path.read_text(encoding="utf-8", errors="replace"))
        if meta.get("experiment") != exp_id:
            return
        meta.pop("experiment", None)
        meta["title"] = f"{_one_line(name or meta.get('title') or exp_id)} (experiment deleted)"
        _write(path, meta, body)
    except Exception as e:
        print(f"[experiment-notes] unlink {exp_id}: {e}")


def update_from_note(conn, meta: dict, body: str) -> bool:
    """A mirrored note was edited in Notes → write its text back to the
    experiment. `body` is the note body after the frontmatter."""
    exp_id = meta.get("experiment")
    if not exp_id:
        return False
    row = conn.execute("SELECT id FROM experiment WHERE id=?", (exp_id,)).fetchone()
    if not row:
        return False
    text = _strip_heading(body, meta.get("title", ""))
    conn.execute(
        "UPDATE experiment SET notes_md=?, updated_at=? WHERE id=?",
        (text, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), exp_id),
    )
    conn.commit()
    return True


def backfill(conn) -> int:
    """Mirror every experiment that has notes (idempotent; run at startup)."""
    n = 0
    for r in conn.execute("SELECT id, name, notes_md FROM experiment "
                          "WHERE notes_md IS NOT NULL AND TRIM(notes_md) != ''").fetchall():
        if sync(dict(r)):
            n += 1
    return n
