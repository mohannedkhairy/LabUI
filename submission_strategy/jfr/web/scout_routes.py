"""Dashboard widget, report archive, and manual publication-scout controls."""
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from jfr.web.templating import make_templates

router = APIRouter()
templates = make_templates()


def get_scout(request: Request):
    scout = getattr(request.app.state, "publication_scout", None)
    if scout is None:
        raise HTTPException(503, "Publication scout is unavailable. Check the LabUI service log.")
    return scout


@router.get("/api/scout/status")
def status(request: Request):
    return get_scout(request).status()


@router.post("/api/scout/run")
def scan(request: Request):
    scout = get_scout(request)
    run_id = scout.trigger()
    return JSONResponse({"started": run_id is not None, "run_id": run_id, "running": True},
                        status_code=202 if run_id is not None else 200)


@router.post("/research/scout/run")
def scan_form(request: Request):
    get_scout(request).trigger()
    return RedirectResponse("/research/scout", status_code=303)


@router.get("/api/scout/reports")
def reports(request: Request, limit: int = Query(30, ge=1, le=100)):
    return {"items": get_scout(request).reports(limit)}


@router.get("/api/scout/papers")
def papers(request: Request, run_id: int | None = Query(None, ge=1),
           limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return get_scout(request).papers(run_id=run_id, limit=limit, offset=offset)


@router.get("/research/scout/widget", response_class=HTMLResponse)
def widget(request: Request, full: bool = False):
    scout = get_scout(request)
    return templates.TemplateResponse(request, "_scout_widget.html", {
        "scout": scout.status(), "scout_papers": scout.papers(limit=5)["items"], "full": full,
    })


@router.get("/research/scout", response_class=HTMLResponse)
def page(request: Request, run_id: int | None = Query(None, ge=1), offset: int = Query(0, ge=0)):
    scout = get_scout(request)
    selected = scout.report(run_id) if run_id is not None else None
    if run_id is not None and selected is None:
        raise HTTPException(404, "Scout report not found")
    return templates.TemplateResponse(request, "research_scout.html", {
        "scout": scout.status(), "scout_papers": [], "full": True,
        "reports": scout.reports(), "selected": selected, "run_id": run_id,
        "papers": scout.papers(run_id=run_id, offset=offset),
    })
