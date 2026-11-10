# LabUI workspaces

The sidebar's **Workspace** selector opens three focused spaces:

| Workspace | Overview | Tools |
|---|---|---|
| Lab | `/spaces/lab` | Calendar, tasks, experiment preparation, equipment inventory, active experiments, and results |
| Research & AI | `/spaces/research` | Local AI chat and agents, paper library/search/review, publication scout, research memory, notes, and knowledge graph |
| Writing & Publishing | `/spaces/writing` | Writing projects, citations, manuscripts, journal recommendations, submissions, published papers, and writing style/phrase bank |

The selector uses native HTML links and works without JavaScript. Each selected
space has its own sidebar menu and dashboard. LabUI remembers an explicitly
selected workspace in the `labui_workspace` cookie; `/` opens that overview.
The default for a new browser is Lab. The logo returns to the current space's
overview. Invalid cookie values fall back to Lab.

## Existing links and shared data

Existing page and API URLs are preserved. Opening an experiment or task selects
the Lab navigation; opening a paper selects Research; opening a writing project
or submission selects Writing. Writing style and phrase bank belong to Writing,
even though their existing URLs begin with `/research/`. The older `/lab` evidence
page remains available as **Manuscript evidence** in global search.

The spaces share the same databases, PDFs, writing files, paper IDs, citation keys,
and relationships. No data migration, file move, or reindexing is involved.
Preparation uses existing experiment objectives, methods, conditions, and equipment
fields. Tasks and experiments still use the existing planner; sidebar links select
the appropriate view and item kind. Calendar explicitly includes both kinds.

Research agent cards open the existing chat in the selected mode. Recent
conversation links restore the actual saved session and its agent. Generation,
embedding, index, reranker status, and model selection now live in Research's
sidebar. Writing's existing AI tools still use the shared model preference and
default model. Theme controls and global search remain available in every space.

## Focused dashboards

- **Lab:** open/overdue tasks, planned/running experiment counts, next tasks,
  experiment preparation, recent completed results, and equipment needing action.
- **Research:** library/conversation/memory counts, research agent shortcuts,
  weekly nanobubble scout, recent conversations, and retained findings.
- **Writing:** projects/manuscript/active-submission counts, recent writing
  projects, publication progress, manuscripts, and publication/style links.

Overviews read existing SQLite records using read-only connections. They do not
load embedding or generation models. Fresh installations show empty states
without creating optional databases. If overview data is unavailable, the page
retains its sidebar and tool links.

## Global search

Use **Search** or Ctrl/Cmd+K from any space. Navigation matches cover tools in all
three spaces. Typing two or more characters also searches saved task titles,
experiment names, manuscript titles, writing-project titles, and paper titles,
authors, and citation keys. For example, `cai2024` opens its library paper.
Saved-item results open their original record; paper links select Research
automatically. Queries use bounded, parameterized read-only searches and ignore
outdated responses while the query changes.

`GET /api/workspaces/search?q=saline&limit=12&workspace=lab` supplies saved-item
results. The optional workspace argument influences ordering, not visibility.

## Implementation and checks

`jfr/web/workspaces.py` defines ownership and navigation. The common template
factory in `templating.py` supplies that context to the main app, publication
scout, and workspace routes. Dashboards and global search live in
`workspace_routes.py`; the shared shell remains `base.html`.

```bash
PYTHONPATH=.:submission_strategy submission_strategy/.venv/bin/python \
  -m unittest discover -s tests -p test_workspaces.py -v
node tests/workspaces.test.cjs
```

The existing mobile navigation drawer contains the same workspace selector.
Dashboard columns collapse to a single column on narrow screens. The selector
supports keyboard navigation and Escape; navigation marks the active page with
`aria-current`.

An already running app needs a restart to load the new Python routes:

```bash
systemctl --user restart labui
```

Reload the browser afterward. The current implementation was checked with Python
route tests, actual-library rendering, JavaScript behavior checks, and rendered
script parsing. Browser interaction/geometry and a live service restart could
not be verified in the restricted development session.

Templates also include a compatibility fallback for an existing process that
has not loaded the new Python context yet. Its original tools remain accessible;
the new overview routes become available after the restart.
