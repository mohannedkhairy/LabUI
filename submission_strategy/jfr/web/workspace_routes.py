"""Focused workspace overviews, using existing data without loading AI models."""
import logging
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from jfr.config import get_settings
from jfr.web.templating import make_templates
from jfr.web.workspaces import COOKIE, WORKSPACES

router = APIRouter()
templates = make_templates()
log = logging.getLogger(__name__)


@contextmanager
def read_db(path):
    """Missing data on a fresh installation is an empty state, never a new DB."""
    if not Path(path).is_file():
        yield None
        return
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    try:
        yield connection
    finally:
        connection.close()


def research_paths():
    from config import DB_PATH, MANUSCRIPTS_DB_PATH, MEMORY_DB_PATH
    return {"papers": DB_PATH, "memory": MEMORY_DB_PATH, "writing": MANUSCRIPTS_DB_PATH}


def rows(conn, query, params=()):
    return [dict(row) for row in conn.execute(query, params)]


def lab_overview(path):
    today = date.today()
    data = {"tasks": [], "preparation": [], "results": [], "open_tasks": 0, "overdue": 0,
            "planned": 0, "running": 0, "equipment_count":0, "equipment_attention":0}
    with read_db(path) as conn:
        if conn is None:
            return data
        from jfr.equipment import summary as equipment_summary
        equipment = equipment_summary(conn)
        data.update(equipment_count=equipment['active'],equipment_attention=equipment['attention'])
        data["open_tasks"] = conn.execute("SELECT count(*) FROM task WHERE status!='done'").fetchone()[0]
        data["overdue"] = conn.execute("SELECT count(*) FROM task WHERE status!='done' AND COALESCE(due_date,'')!='' AND due_date<?", (today.isoformat(),)).fetchone()[0]
        data["planned"] = conn.execute("SELECT count(*) FROM experiment WHERE status='planned'").fetchone()[0]
        data["running"] = conn.execute("SELECT count(*) FROM experiment WHERE status='in_progress'").fetchone()[0]
        data["tasks"] = rows(conn, """SELECT t.*,m.title AS manuscript_title FROM task t
            LEFT JOIN manuscript m ON m.id=t.manuscript_id WHERE t.status!='done'
            ORDER BY (t.due_date IS NULL OR t.due_date=''),t.due_date,
                     CASE t.priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,t.position LIMIT 5""")
        data["preparation"] = rows(conn, """SELECT e.*,m.title AS manuscript_title FROM experiment e
            LEFT JOIN manuscript m ON m.id=e.manuscript_id WHERE e.status IN ('planned','in_progress')
            ORDER BY (e.scheduled_for IS NULL OR e.scheduled_for=''),e.scheduled_for,e.created_at DESC LIMIT 5""")
        data["results"] = rows(conn, """SELECT id,name,ran_on,results_md,manuscript_id FROM experiment
            WHERE status='done' ORDER BY COALESCE(ran_on,updated_at) DESC LIMIT 3""")
    for task in data["tasks"]:
        task["overdue"] = bool(task["due_date"] and task["due_date"] < today.isoformat())
        task["href"] = "/plan?open=task:" + quote(task["id"], safe="")
    for item in data["preparation"] + data["results"]:
        item["href"] = "/plan?open=experiment:" + quote(item["id"], safe="")
    return data


def research_overview(paths):
    data = {"paper_count": 0, "session_count": 0, "memory_count": 0,
            "sessions": [], "findings": [], "agents": []}
    with read_db(paths["papers"]) as conn:
        if conn:
            data["paper_count"] = conn.execute("SELECT count(*) FROM papers").fetchone()[0]
    with read_db(paths["memory"]) as conn:
        if conn:
            data["session_count"] = conn.execute("SELECT count(*) FROM sessions").fetchone()[0]
            data["memory_count"] = conn.execute("SELECT count(*) FROM memories").fetchone()[0]
            data["sessions"] = rows(conn, "SELECT session_id,title,agent_id,turn_count FROM sessions ORDER BY updated_at DESC LIMIT 4")
            data["findings"] = rows(conn, "SELECT content,memory_type FROM memories ORDER BY created_at DESC LIMIT 3")
    from generation.agents import AGENTS
    for agent_id in ("gaps", "evidence", "matrix"):
        agent = AGENTS[agent_id]
        data["agents"].append({"name": agent["name"], "description": agent["description"],
                               "href": "/research/chat?agent=" + agent_id})
    for session in data["sessions"]:
        session["href"] = "/research/chat?session=" + quote(session["session_id"], safe="")
    return data


def writing_overview(path, paths):
    data = {"projects": [], "project_count": 0, "manuscripts": [], "manuscript_count": 0,
            "submissions": [], "active_count": 0, "published_count": 0}
    with read_db(paths["writing"]) as conn:
        if conn:
            data["project_count"] = conn.execute("SELECT count(*) FROM writing_projects").fetchone()[0]
            data["projects"] = rows(conn, """SELECT p.id,p.title,p.updated_at,
                (SELECT count(*) FROM writing_files f WHERE f.project_id=p.id) AS section_count
                FROM writing_projects p ORDER BY p.updated_at DESC LIMIT 5""")
    with read_db(path) as conn:
        if conn:
            data["manuscript_count"] = conn.execute("SELECT count(*) FROM manuscript").fetchone()[0]
            data["manuscripts"] = rows(conn, "SELECT id,title FROM manuscript ORDER BY updated_at DESC LIMIT 3")
            data["published_count"] = conn.execute("SELECT count(*) FROM submission WHERE current_state='published'").fetchone()[0]
            from jfr.db.schema import TERMINAL_STATES
            from jfr.tracker.workflow import STATE_LABELS
            excluded = sorted(TERMINAL_STATES)
            data["active_count"] = conn.execute(
                f"SELECT count(*) FROM submission WHERE current_state NOT IN ({','.join('?' for _ in excluded)})", excluded).fetchone()[0]
            data["submissions"] = rows(conn, f"""SELECT s.id,s.current_state,m.title,j.name AS journal_name
                FROM submission s JOIN manuscript m ON m.id=s.manuscript_id JOIN journal j ON j.id=s.journal_id
                WHERE s.current_state NOT IN ({','.join('?' for _ in excluded)}) ORDER BY s.updated_at DESC LIMIT 4""", excluded)
            for submission in data["submissions"]:
                submission["state_label"] = STATE_LABELS.get(submission["current_state"], submission["current_state"].replace("_", " "))
    for project in data["projects"]:
        project["href"] = "/write/" + quote(project["id"], safe="")
    return data


def search_workspaces(query, limit=12, preferred="lab"):
    """Search existing records across all spaces without invoking retrieval/AI."""
    paths = research_paths()
    needle = query.strip()
    escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like = "%" + escaped + "%"
    hits = []
    with read_db(get_settings().db_path) as conn:
        if conn:
            for table, field, kind, space, href in [
                ("task", "title", "Task", "lab", "/plan?open=task:"),
                ("experiment", "name", "Experiment", "lab", "/plan?open=experiment:"),
                ("manuscript", "title", "Manuscript", "writing", "/manuscripts/"),
            ]:
                for record in rows(conn, f"SELECT id,{field} AS title FROM {table} WHERE {field} LIKE ? ESCAPE '\\' ORDER BY updated_at DESC LIMIT ?", (like, limit)):
                    target = href + quote(record["id"], safe="") + ("/edit" if table == "manuscript" else "")
                    hits.append({"label": record["title"], "sub": WORKSPACES[space]["name"],
                                 "tag": kind, "space": space, "href": target})
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='equipment'").fetchone():
                for record in rows(conn,"""SELECT id,name,model,serial_number,asset_tag,location FROM equipment
                    WHERE name LIKE ? ESCAPE '\\' OR model LIKE ? ESCAPE '\\' OR serial_number LIKE ? ESCAPE '\\'
                    OR asset_tag LIKE ? ESCAPE '\\' OR vendor_name LIKE ? ESCAPE '\\' ORDER BY updated_at DESC LIMIT ?""",
                                   (like,like,like,like,like,limit)):
                    hits.append({'label':record['name'],'sub':' · '.join(value for value in [record['model'],record['asset_tag'],record['location']] if value),
                                 'tag':'Equipment','space':'lab','href':'/equipment/'+quote(record['id'],safe='')})
    with read_db(paths["writing"]) as conn:
        if conn:
            for record in rows(conn, "SELECT id,title FROM writing_projects WHERE title LIKE ? ESCAPE '\\' ORDER BY updated_at DESC LIMIT ?", (like, limit)):
                hits.append({"label": record["title"], "sub": "Writing & Publishing", "space": "writing",
                             "tag": "Writing project", "href": "/write/" + quote(record["id"], safe="")})
    with read_db(paths["papers"]) as conn:
        if conn:
            has_catalog = conn.execute("SELECT 1 FROM sqlite_master WHERE name='citation_catalog'").fetchone()
            if has_catalog:
                paper_rows = rows(conn, """SELECT p.paper_id,p.title,p.authors,p.year,c.citation_key FROM papers p
                    LEFT JOIN citation_catalog c ON c.paper_id=p.paper_id
                    WHERE p.title LIKE ? ESCAPE '\\' OR p.authors LIKE ? ESCAPE '\\' OR c.citation_key LIKE ? ESCAPE '\\'
                    ORDER BY p.year DESC,p.title LIMIT ?""", (like, like, like, limit))
            else:
                paper_rows = rows(conn, """SELECT paper_id,title,authors,year FROM papers
                    WHERE title LIKE ? ESCAPE '\\' OR authors LIKE ? ESCAPE '\\' ORDER BY year DESC,title LIMIT ?""", (like, like, limit))
            for record in paper_rows:
                hits.append({"label": record["title"] or record["paper_id"],
                             "sub": " · ".join(str(value) for value in [record.get("citation_key"), record["authors"], record["year"]] if value),
                             "tag": "Paper", "space": "research", "href": "/research/paper/" + quote(record["paper_id"], safe="") + "/view",
                             "key": record.get("citation_key") or ""})
    hits.sort(key=lambda item: (not item.get("key", "").casefold().startswith(needle.casefold()) if item.get("key") else True,
                               not item["label"].casefold().startswith(needle.casefold()),
                               item["space"] != preferred, item["label"].casefold()))
    return hits[:limit]


@router.get("/api/workspaces/search")
def global_search(request: Request, q: str = Query(..., min_length=2, max_length=120),
                  limit: int = Query(12, ge=1, le=30), workspace: str = ""):
    preferred = workspace if workspace in WORKSPACES else request.cookies.get(COOKIE, "lab")
    try:
        return {"items": search_workspaces(q, limit, preferred)}
    except (sqlite3.Error, OSError):
        log.exception("Global workspace search failed")
        raise HTTPException(503, "Search is temporarily unavailable") from None


@router.get("/", include_in_schema=False)
def workspace_home(request: Request):
    space = WORKSPACES.get(request.cookies.get(COOKIE), WORKSPACES["lab"])
    return RedirectResponse(space["home"], status_code=307)


@router.get("/spaces/{space_id}", response_class=HTMLResponse)
def workspace_dashboard(request: Request, space_id: str):
    if space_id not in WORKSPACES:
        raise HTTPException(404, "Workspace not found")
    settings = get_settings()
    overview_error = None
    try:
        if space_id == "lab":
            overview = lab_overview(settings.db_path)
        elif space_id == "research":
            overview = research_overview(research_paths())
        else:
            overview = writing_overview(settings.db_path, research_paths())
    except (sqlite3.Error, OSError):
        log.exception("Could not read %s workspace overview", space_id)
        overview = {}
        overview_error = "This overview is temporarily unavailable. You can still open your tools from the sidebar."
    response = templates.TemplateResponse(request, "dashboard.html", {"overview": overview, "overview_error": overview_error},
                                          status_code=503 if overview_error else 200)
    response.set_cookie(COOKIE, space_id, max_age=365 * 24 * 60 * 60, samesite="lax", httponly=True)
    return response
