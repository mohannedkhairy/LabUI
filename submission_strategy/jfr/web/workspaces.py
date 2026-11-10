"""Shared workspace ownership and navigation for every HTML renderer."""
from urllib.parse import urlsplit

HOME = "M3 10l9-7 9 7v10H3V10zm6 10v-7h6v7"
CALENDAR = "M8 3v4m8-4v4M3 10h18M5 5h14v16H5V5z"
TASK = "M9 5H5v16h14V5h-4M9 3h6v4H9V3zm0 11l2 2 4-5"
FLASK = "M9 3h6m-5 0v7L4 20h16l-6-10V3M8 14h8"
CHAT = "M21 11c0 5-4 8-9 8H8l-5 3 2-6c-1-1-2-3-2-5a9 8 0 0118 0z"
BOOK = "M12 5v16M3 4c4-1 6 0 9 2 3-2 5-3 9-2v15c-4-1-6 0-9 2-3-2-5-3-9-2V4z"
SEARCH = "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
DOCUMENT = "M5 3h10l4 4v14H5V3zm4 8h6m-6 4h6"
GRAPH = "M5 5l14 3-7 12L5 5zm0 0l7 15m0-15v15"
PEN = "M4 20l1-5L16 4l4 4L9 19l-5 1zm11-15l4 4"


def link(label, href, icon):
    return {"label": label, "href": href, "icon": icon}


WORKSPACES = {
    "lab": {
        "id": "lab", "name": "Lab", "description": "Preparation, equipment, tasks, and experiments",
        "home": "/spaces/lab", "icon": FLASK,
        "primary": link("Prepare an experiment", "/plan?new=experiment", FLASK),
        "secondary": link("New task", "/plan?new=task", TASK),
        "nav": [link("Overview", "/spaces/lab", HOME), link("Calendar", "/plan?view=month&kind=all", CALENDAR),
                link("Tasks", "/plan?view=board&kind=task", TASK),
                link("Experiments", "/plan?view=list&kind=experiment", FLASK),
                link("Equipment inventory", "/equipment", DOCUMENT)],
    },
    "research": {
        "id": "research", "name": "Research & AI", "description": "Your papers, local AI, and research agents",
        "home": "/spaces/research", "icon": CHAT,
        "primary": link("Chat with papers", "/research/chat", CHAT),
        "secondary": link("Add papers", "/research/upload", DOCUMENT),
        "nav": [link("Overview", "/spaces/research", HOME), link("Chat & agents", "/research/chat", CHAT),
                link("Library", "/library", BOOK), link("Paper search", "/research/search", SEARCH),
                link("Publication scout", "/research/scout", CALENDAR), link("Paper review", "/review", DOCUMENT),
                link("Research memory", "/research/memory", BOOK), link("Notes", "/research/notes", PEN),
                link("Knowledge graph", "/research/graph", GRAPH), link("Add papers", "/research/upload", DOCUMENT)],
    },
    "writing": {
        "id": "writing", "name": "Writing & Publishing", "description": "Drafts, citations, and the path to publication",
        "home": "/spaces/writing", "icon": PEN,
        "primary": link("Open writing projects", "/write", PEN),
        "secondary": link("New manuscript", "/manuscripts/new", DOCUMENT),
        "nav": [link("Overview", "/spaces/writing", HOME), link("Writing projects", "/write", PEN),
                link("Manuscripts", "/manuscripts", DOCUMENT), link("Journal recommendations", "/recommend", SEARCH),
                link("Submissions", "/submissions", DOCUMENT), link("Published papers", "/publications", BOOK),
                link("Journals", "/journals", BOOK), link("Writing style", "/research/style", PEN)],
    },
}
COOKIE = "labui_workspace"


def workspace_for_path(path, preferred="lab"):
    for space in WORKSPACES.values():
        if path == space["home"]:
            return space
    # Specific writing tools precede the general /research ownership rule.
    for prefix in ("/research/style", "/research/phrasebank", "/write", "/manuscripts",
                   "/recommend", "/submissions", "/publications", "/journals"):
        if path == prefix or path.startswith(prefix + "/"):
            return WORKSPACES["writing"]
    for prefix in ("/plan", "/tasks", "/experiments", "/schedule", "/equipment"):
        if path == prefix or path.startswith(prefix + "/"):
            return WORKSPACES["lab"]
    for prefix in ("/research", "/library", "/review", "/lab"):
        if path == prefix or path.startswith(prefix + "/"):
            return WORKSPACES["research"]
    return WORKSPACES.get(preferred, WORKSPACES["lab"])


def active_navigation(request, entry):
    target = urlsplit(entry["href"])
    path = request.url.path
    if path != target.path and not path.startswith(target.path + "/"):
        return False
    if target.path == "/plan":
        kind = request.query_params.get("kind")
        if "kind=task" in target.query:
            return kind == "task"
        if "kind=experiment" in target.query:
            return kind == "experiment"
        return kind not in {"task", "experiment"}
    return True


def workspace_context(request):
    space = workspace_for_path(request.url.path, request.cookies.get(COOKIE, "lab"))
    commands = [[item["label"] if item["label"] != "Overview" else space["name"] + " overview",
                 item["href"], space["name"]]
                for space in WORKSPACES.values() for item in space["nav"]]
    commands.extend([
        ["Research agents", "/research/chat#agent-select", "Research & AI"],
        ["Manuscript evidence", "/lab", "Research & AI"],
        ["Phrase bank", "/research/style?tab=phrases", "Writing & Publishing"],
    ])
    return {"workspace": space, "workspaces": list(WORKSPACES.values()),
            "workspace_navigation": [{**entry, "active": active_navigation(request, entry)} for entry in space["nav"]],
            "workspace_commands": commands}
