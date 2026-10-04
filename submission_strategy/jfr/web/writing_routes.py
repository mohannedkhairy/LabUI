"""Writing projects API — mounted under /api/rag (see app.py).

Thin FastAPI layer over the `writing` library (Local_Rag/rag/writing.py):
  - project + file CRUD
  - citation resolution (@paper-id → library papers, ACS numbering)
  - wikilinks / backlinks
  - export (combined .md, BibTeX)
  - push-to-JFR (create or update a journal-fit manuscript from a project)
  - audit: score a file (or arbitrary text) against the installed writing
    standard's measured corpus profile — see Local_Rag/rag/skills/
"""
from __future__ import annotations

import os
import sys
import json
import html
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel

# ── Make Local_Rag/rag importable (same pattern as rag_routes.py) ────────────
_DEFAULT_RAG_DIR = Path(__file__).resolve().parents[3] / "Local_Rag" / "rag"
_LOCAL_RAG_DIR = Path(os.environ.get("LABUI_RAG_DIR") or str(_DEFAULT_RAG_DIR))
if str(_LOCAL_RAG_DIR) not in sys.path:
    sys.path.insert(0, str(_LOCAL_RAG_DIR))

import writing as wr  # noqa: E402
from writing import WritingError  # noqa: E402
from skills import audit as _audit  # noqa: E402
from skills import loader as _skills  # noqa: E402

router = APIRouter()

# Map a file slug or title to a manuscript section, so the audit picks the right
# per-section targets without the user having to say. Order matters: the first
# key found in the normalised text wins, and "results and discussion" must be
# tested before the bare "results"/"discussion" keys.
_SECTION_HINTS = [
    ("results and discussion", "results"),
    ("introduction", "intro"),
    ("background", "intro"),
    ("method", "methods"),
    ("experimental", "methods"),
    ("materials", "methods"),
    ("result", "results"),
    ("discussion", "discussion"),
    ("conclusion", "conclusion"),
    ("abstract", "abstract"),
    ("summary", "abstract"),
    ("reviewer", "reviewer"),
    ("response", "reviewer"),
    ("rebuttal", "reviewer"),
    ("intro", "intro"),
]


def guess_section(*texts: str) -> Optional[str]:
    """Best-effort section id from a file slug/title. None when nothing matches —
    the audit then reports global markers only, which is the honest default."""
    blob = " ".join(t or "" for t in texts).lower().replace("-", " ").replace("_", " ")
    for needle, section in _SECTION_HINTS:
        if needle in blob:
            return section
    return None


def _conn():
    return wr.new_conn()


def _handle(fn):
    """Run a writing-lib call, mapping WritingError → 400/404."""
    try:
        return fn()
    except WritingError as e:
        msg = str(e)
        raise HTTPException(404 if "not found" in msg else 400, msg)
    except Exception as e:  # pragma: no cover
        raise HTTPException(500, f"{type(e).__name__}: {e}")


# ── Models ────────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    title: str = "Untitled manuscript"
    slug: str = ""
    principal_claim: str = ""
    techniques: str = ""


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    jfr_manuscript_id: Optional[str] = None
    principal_claim: Optional[str] = None
    techniques: Optional[str] = None
    settings: Optional[dict] = None


class FileCreate(BaseModel):
    title: str = "Untitled section"
    slug: str = ""
    content: str = ""
    page_style: str = "manuscript"
    layout: dict = {}


class FileUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    page_style: Optional[str] = None
    layout: Optional[dict] = None


class OrderUpdate(BaseModel):
    slugs: list[str]


class CitationImportApply(BaseModel):
    include_review: bool = False


# ── Projects ──────────────────────────────────────────────────────────────────

@router.get("/projects")
def projects_list():
    conn = _conn()
    return _handle(lambda: wr.list_projects(conn))


@router.post("/projects", status_code=201)
def projects_create(body: ProjectCreate):
    conn = _conn()
    return _handle(lambda: wr.create_project(
        conn, body.title, slug=body.slug,
        principal_claim=body.principal_claim, techniques=body.techniques,
    ))


@router.get("/projects/{project_id}")
def projects_get(project_id: str):
    conn = _conn()
    return _handle(lambda: wr.get_project(conn, project_id))


@router.put("/projects/{project_id}")
def projects_update(project_id: str, body: ProjectUpdate):
    conn = _conn()
    return _handle(lambda: wr.update_project(
        conn, project_id, title=body.title,
        jfr_manuscript_id=body.jfr_manuscript_id,
        principal_claim=body.principal_claim, techniques=body.techniques,
        settings=body.settings,
    ))


@router.delete("/projects/{project_id}")
def projects_delete(project_id: str):
    conn = _conn()
    _handle(lambda: wr.delete_project(conn, project_id))
    return {"ok": True}


# ── Files ─────────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/files", status_code=201)
def files_create(project_id: str, body: FileCreate):
    conn = _conn()
    return _handle(lambda: wr.create_file(
        conn, project_id, body.title, slug=body.slug, content=body.content,
        page_style=body.page_style, layout=body.layout,
    ))


@router.put("/projects/{project_id}/files/order")
def files_order(project_id: str, body: OrderUpdate):
    """MUST be declared before the /files/{slug} routes — FastAPI matches in
    declaration order and '{slug}' would otherwise swallow 'order'."""
    conn = _conn()
    _handle(lambda: wr.reorder_files(conn, project_id, body.slugs))
    return {"ok": True}


@router.get("/projects/{project_id}/files/{slug}")
def files_get(project_id: str, slug: str):
    conn = _conn()
    return _handle(lambda: wr.get_file(conn, project_id, slug))


@router.put("/projects/{project_id}/files/{slug}")
def files_update(project_id: str, slug: str, body: FileUpdate):
    conn = _conn()
    return _handle(lambda: wr.update_file(
        conn, project_id, slug, title=body.title, content=body.content,
        page_style=body.page_style, layout=body.layout,
    ))


@router.delete("/projects/{project_id}/files/{slug}")
def files_delete(project_id: str, slug: str):
    conn = _conn()
    _handle(lambda: wr.delete_file(conn, project_id, slug))
    return {"ok": True}


# ── Project assets / figures ────────────────────────────────────────────────

@router.get("/projects/{project_id}/assets")
def assets_list(project_id: str):
    conn = _conn()
    return {"assets": _handle(lambda: wr.list_assets(conn, project_id))}


@router.post("/projects/{project_id}/assets", status_code=201)
async def assets_upload(project_id: str, file: UploadFile = File(...)):
    data = await file.read()
    conn = _conn()
    return _handle(lambda: wr.create_asset(
        conn, project_id, file.filename or "figure", file.content_type or "", data,
    ))


@router.get("/projects/{project_id}/assets/{asset_id}")
def assets_get(project_id: str, asset_id: str):
    conn = _conn()
    meta, path = _handle(lambda: wr.get_asset(conn, project_id, asset_id))
    # Omit Content-Disposition: attachment so the same endpoint can be used by
    # <img> tags in the live preview as well as by direct downloads.
    return FileResponse(str(path), media_type=meta["mime_type"])


@router.delete("/projects/{project_id}/assets/{asset_id}")
def assets_delete(project_id: str, asset_id: str):
    conn = _conn()
    _handle(lambda: wr.delete_asset(conn, project_id, asset_id))
    return {"ok": True}


# ── Citations & links ─────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/citations")
def projects_citations(project_id: str):
    conn = _conn()
    return {"citations": _handle(lambda: wr.project_citations(conn, project_id))}


@router.get("/cite/search")
def cite_search(q: str = Query(""), limit: int = Query(12, ge=1, le=30)):
    return {"papers": _handle(lambda: wr.search_papers(q, limit))}


@router.get("/citations/autocomplete")
def citations_autocomplete(q: str = Query(""), limit: int = Query(12, ge=1, le=30)):
    """Fast editor lookup over stable keys, aliases, and catalog metadata."""
    def run():
        from citations import catalog_search
        return catalog_search(q, limit)
    return {"citations": _handle(run)}


@router.get("/citations/catalog")
def citations_catalog(q: str = Query(""), limit: int = Query(50, ge=1, le=100)):
    def run():
        from citations import catalog_search
        if q:
            return catalog_search(q, limit)
        from citations import sync_rag_papers, _conn, _row_dict
        sync_rag_papers()
        conn = _conn()
        rows = [_row_dict(r) for r in conn.execute("SELECT * FROM citation_catalog ORDER BY citation_key LIMIT ?", (limit,)).fetchall()]
        conn.close()
        return rows
    return {"citations": _handle(run)}


@router.post("/citations/sync")
def citations_sync():
    """Populate catalog rows for papers added since the last sync."""
    def run():
        from citations import init_db, sync_rag_papers
        init_db()
        return {"synced": sync_rag_papers(force=True)}
    return _handle(run)


@router.get("/citations/export")
def citations_export(format: str = Query("bibtex")):
    if format.lower() not in {"bibtex", "bib", "bibtex-catalog"}:
        raise HTTPException(400, "format must be 'bibtex'")
    def run():
        from citations import render_bibtex
        return render_bibtex()
    return PlainTextResponse(_handle(run), headers={"Content-Disposition": 'attachment; filename="labui-citation-catalog.bib"'})


@router.post("/citations/import")
async def citations_import(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "citation import is limited to 10 MB")
    def run():
        from citations import import_file
        try:
            return import_file(data, file.filename or "references.bib")
        except (ValueError, json.JSONDecodeError) as exc:
            raise WritingError(str(exc))
    return _handle(run)


@router.get("/citations/import/{batch_id}")
def citations_import_batch(batch_id: str):
    def run():
        from citations import import_batch
        result = import_batch(batch_id)
        if result is None:
            raise WritingError("import batch not found")
        return result
    return _handle(run)


@router.post("/citations/import/{batch_id}/apply")
def citations_import_apply(batch_id: str, body: CitationImportApply = CitationImportApply()):
    def run():
        from citations import apply_import_batch
        return apply_import_batch(batch_id, include_review=body.include_review)
    return _handle(run)


# ── Export ────────────────────────────────────────────────────────────────────

# ── Audit — score prose against the installed writing standard ────────────────

class AuditBody(BaseModel):
    text: str
    section: Optional[str] = None       # explicit override; else guessed


@router.post("/writing/audit")
def writing_audit(body: AuditBody):
    """Audit arbitrary text. Used by the workspace for a selection, and usable
    from anywhere else that has prose in hand."""
    section = (body.section or "").strip().lower() or None
    if section and section not in _skills.SECTION_MAP:
        section = None
    if not _audit.available():
        raise HTTPException(503, "no writing standard installed (Local_Rag/rag/skills/)")
    return _handle(lambda: _audit.audit_text(body.text or "", section))


@router.get("/projects/{project_id}/files/{slug}/audit")
def file_audit(project_id: str, slug: str, section: str = Query("")):
    """Audit one file of a writing project. The section is inferred from the
    file's slug and title unless given explicitly."""
    if not _audit.available():
        raise HTTPException(503, "no writing standard installed (Local_Rag/rag/skills/)")

    def run():
        conn = _conn()
        try:
            f = wr.get_file(conn, project_id, slug)
        finally:
            conn.close()
        sec = (section or "").strip().lower() or None
        if sec not in _skills.SECTION_MAP:
            sec = guess_section(f.get("slug"), f.get("title"))
        report = _audit.audit_text(f.get("content") or "", sec)
        report["file"] = {"slug": f.get("slug"), "title": f.get("title"),
                          "section_guess": sec}
        return report

    return _handle(run)


@router.get("/projects/{project_id}/audit")
def project_audit(project_id: str):
    """Audit every file in a project, plus the combined manuscript. Gives the
    whole-paper connective budget, which per-file audits cannot: 'However' ten
    times is fine across 6,000 words and wrong inside one 300-word section."""
    if not _audit.available():
        raise HTTPException(503, "no writing standard installed (Local_Rag/rag/skills/)")

    def run():
        conn = _conn()
        try:
            project = wr.get_project(conn, project_id)
            files = []
            for f in project.get("files", []):
                doc = wr.get_file(conn, project_id, f["slug"])
                sec = guess_section(doc.get("slug"), doc.get("title"))
                rep = _audit.audit_text(doc.get("content") or "", sec)
                files.append({"slug": f["slug"], "title": f["title"],
                              "section_guess": sec, "report": rep})
            combined = wr.render_export_md(conn, project_id)
        finally:
            conn.close()
        return {
            "project": {"id": project_id, "title": project.get("title")},
            "files": files,
            "combined": _audit.audit_text(combined, None),
        }

    return _handle(run)


@router.get("/projects/{project_id}/export")
def projects_export(project_id: str, format: str = Query("md")):
    conn = _conn()
    if format == "bibtex":
        text = _handle(lambda: wr.render_bibtex(wr.project_citations(conn, project_id)))
        name = f"{project_id}-references.bib"
    elif format == "md":
        text = _handle(lambda: wr.render_export_md(conn, project_id))
        name = f"{project_id}.md"
    elif format in ("html", "print"):
        project = _handle(lambda: wr.get_project(conn, project_id))
        text = _handle(lambda: wr.render_export_md(conn, project_id))
        settings = {**wr.DEFAULT_LAYOUT, **(project.get("settings") or {})}
        # The standalone document deliberately uses the same browser renderer as
        # the workspace (marked + KaTeX), keeping math and GFM behavior aligned.
        source_json = json.dumps(text, ensure_ascii=False).replace("</", "<\\/")
        page_w = "8.5in" if settings.get("page_size") == "letter" else "210mm"
        page_h = "11in" if settings.get("page_size") == "letter" else "297mm"
        style = settings.get("page_style") if settings.get("page_style") in wr.PAGE_STYLES else "manuscript"
        bg = html.escape(str(settings.get("page_color") or "#fffdf8"), quote=True)
        css = f"""
          :root {{ --mt:{float(settings.get('margin_top', 22))}mm; --mr:{float(settings.get('margin_right', 22))}mm;
                   --mb:{float(settings.get('margin_bottom', 22))}mm; --ml:{float(settings.get('margin_left', 22))}mm;
                   --paper-bg:{bg}; --fs:{float(settings.get('font_size', 14))}px; --lh:{float(settings.get('line_height', 1.72))}; }}
          @page {{ size:{page_w} {page_h}; margin:var(--mt) var(--mr) var(--mb) var(--ml); }}
          * {{ box-sizing:border-box; }} body {{ margin:0; color:#29251f; background:#ece8df; font-family: Georgia, serif; }}
          main {{ width:min(100%, 8.5in); min-height:11in; margin:24px auto; padding:var(--mt) var(--mr) var(--mb) var(--ml);
                  background:var(--paper-bg); font-size:var(--fs); line-height:var(--lh); }}
          main.lined {{ background-color:var(--paper-bg); background-image:linear-gradient(to bottom, transparent 0, transparent calc(1.72em - 1px), rgba(66,125,160,.22) calc(1.72em - 1px), rgba(66,125,160,.22) 1.72em); background-size:100% 1.72em; }}
          main.grid {{ background-image:linear-gradient(rgba(90,110,120,.12) 1px, transparent 1px), linear-gradient(90deg, rgba(90,110,120,.12) 1px, transparent 1px); background-size:22px 22px; }}
          main.dot {{ background-image:radial-gradient(rgba(90,110,120,.28) 1px, transparent 1px); background-size:14px 14px; }}
          main.tinted {{ background:var(--paper-bg); }}
          h1,h2,h3 {{ break-after:avoid; }} img {{ max-width:100%; height:auto; display:block; margin:1em auto; }} figure {{ break-inside:avoid; margin:1.2em 0; }}
          figcaption {{ text-align:center; color:#665f55; font-size:.9em; }} table {{ border-collapse:collapse; max-width:100%; }} th,td {{ border-bottom:1px solid #cfc8bc; padding:5px 8px; text-align:left; }}
          @media print {{ body {{ background:white; }} main {{ width:auto; min-height:0; margin:0; box-shadow:none; }} }}
        """
        return HTMLResponse(f"""<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(project.get('title','Manuscript'))}</title>
          <link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css'>
          <style>{css}</style></head><body><main class='{style}' id='paper'><div id='content'></div></main>
          <script type='application/json' id='source'>{source_json}</script>
          <script src='https://cdn.jsdelivr.net/npm/dompurify@3.2.6/dist/purify.min.js'></script>
          <script src='https://cdn.jsdelivr.net/npm/marked@12/marked.min.js'></script>
          <script src='https://cdn.jsdelivr.net/npm/marked-katex-extension@5/lib/index.umd.js'></script>
          <script>marked.use({{gfm:true,breaks:false}}); if(window.markedKatex) marked.use(markedKatex({{throwOnError:false,nonStandard:true}}));
            const src=JSON.parse(document.getElementById('source').textContent); const out=marked.parse(src); document.getElementById('content').innerHTML=window.DOMPurify ? DOMPurify.sanitize(out) : out;</script>
          </body></html>""", headers={"Content-Disposition": f'attachment; filename="{project_id}.html"'})
    else:
        raise HTTPException(400, "format must be 'md', 'html', 'print', or 'bibtex'")
    return PlainTextResponse(
        text,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# ── Push to JFR ───────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/push-jfr")
def projects_push_jfr(project_id: str):
    """Create (or update) a journal-fit manuscript from this project:
    title ← project title, abstract ← 'abstract' file (or first file),
    claim/techniques ← project fields. Links the two records."""
    from jfr.config import get_settings
    from jfr.db import get_conn
    from jfr.tracker import create_manuscript, get_manuscript, update_manuscript

    conn = _conn()
    project = _handle(lambda: wr.get_project(conn, project_id))
    abstract = _handle(lambda: wr.abstract_text(conn, project_id))
    if not abstract:
        raise HTTPException(400, "Add an abstract (a file named 'abstract', or any section with text) before pushing to JFR.")
    claim = (project.get("principal_claim") or "").strip()
    if not claim:
        # Fall back to the first sentence of the abstract so the NOT NULL
        # constraint is satisfied with something meaningful.
        first = abstract.strip().split(". ")[0].rstrip(".")
        claim = (first + ".") if len(first) > 8 else abstract[:200]
    techniques = [t.strip() for t in (project.get("techniques") or "").split(",") if t.strip()]

    jfr_conn = get_conn(get_settings().db_path)
    existing = project.get("jfr_manuscript_id")
    if existing and get_manuscript(jfr_conn, existing):
        update_manuscript(
            jfr_conn, existing,
            title=project["title"], abstract=abstract,
            principal_claim=claim, techniques=techniques,
        )
        created = False
    else:
        existing = create_manuscript(
            jfr_conn,
            title=project["title"],
            abstract=abstract,
            principal_claim=claim,
            techniques=techniques,
            ms_id=f"wp.{project['slug']}",
        )
        created = True
    jfr_conn.close()

    wr.update_project(conn, project_id, jfr_manuscript_id=existing)
    return {
        "jfr_manuscript_id": existing,
        "created": created,
        "recommend_url": f"/recommend?ms={existing}",
    }
