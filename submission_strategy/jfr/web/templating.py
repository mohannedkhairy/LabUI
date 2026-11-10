"""One shell context for main pages, background tools, and workspace dashboards."""
from pathlib import Path

from fastapi.templating import Jinja2Templates

from jfr.web.themes import manifest
from jfr.web.workspaces import workspace_context


def make_templates():
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"),
                               context_processors=[workspace_context])
    templates.env.globals["appearance"] = manifest()
    return templates
