# Skill packs

A skill pack is a folder of markdown that defines a writing standard. Layout follows
the Claude skill convention:

```
skills/
  loader.py                    # progressive loader — assembles prompt slices
  audit.py                     # adapter over a pack's scripts/audit_draft.py
  build_phrasebank_html.py     # builds the browsable Phrase Bank page
  <skill-name>/
    SKILL.md                   # frontmatter (name, description) + overview
    references/*.md            # the detailed guides
    scripts/audit_draft.py     # optional; exposes audit_text(text, section) -> dict
    phrase-bank.html           # build artifact — see "Phrase Bank tab" below
```

## Why nothing is ever loaded whole

`nanobubble-paper-writer` is ~33,000 tokens of markdown. `RAG_GEN_NUM_CTX` defaults
to 32,768. The pack does not fit in the context window even on its own, and a local
model follows a short sharp brief far better than a long essay regardless.

So `loader.build_writing_brief(section, mode)` assembles a compact brief from named
slices, highest-value-first, under an explicit character budget:

1. measured register targets (sentence length, voice, hedging, punctuation)
2. the connective budget (per-1,000-word ceilings)
3. that section's corpus anchors (citation density, passive rate, …)
4. that section's phrase-bank moves — **patterns only**, exemplars stripped
5. general logical moves, banned vocabulary, paragraph/sentence craft
6. signature features of the house register

Result: **~2,700–3,600 tokens** per request instead of 33,000, leaving the rest of
the window for retrieved excerpts, style samples, and the answer. In `revise` mode
the phrase bank gives way to the mechanical pre-delivery scan.

Exemplar sentences (`> "quoted text" — Source`) are dropped from prompts on purpose:
they are the bulk of the phrase bank by volume, and a local model tends to imitate a
quoted sentence rather than abstract from it. The patterns carry the reusable shape
at a fraction of the cost. The exemplars remain in the files for humans to read.

## Wiring

| Piece | Where |
|---|---|
| Agent opts in | `generation/agents.py` — `"skill": "<name>"` on the agent dict |
| Brief injected | `generation/agents.py:resolve_system()`, called by `generation/prompt.py:build_messages()` |
| Section plumbed through | `jfr/web/rag_routes.py` — `QueryBody.section`, `.write_mode`, `.draft_text` |
| Status / preview | `GET /api/rag/skills`, `GET /api/rag/skills/brief?section=results&preview=true` |
| Audit | `POST /api/rag/writing/audit`, `GET /api/rag/projects/{id}/files/{slug}/audit`, `GET /api/rag/projects/{id}/audit` |
| UI | `templates/writing_workspace.html` (Draft / Revise / Audit), `templates/research_chat.html` (section picker), `templates/research_phrasebank.html` (Phrase Bank tab) |
| Phrase Bank page | `GET /api/rag/skills/{skill}/phrasebank.html`, embedded by `GET /research/phrasebank` |

Everything degrades gracefully. Remove the pack folder and `resolve_system()` falls
back to the built-in rules in `agents.py`; the audit endpoints return 503 and the UI
disables its buttons.

## Phrase Bank tab

`/research/phrasebank` (sidebar → Research Lab → Phrase Bank) shows the pack's
rhetorical moves, reusable patterns, and attested exemplars, with search and
per-section / per-source filters. Clicking a pattern copies it.

It is a **self-contained page inside an iframe**, not a Jinja template. That keeps
it byte-identical to the standalone artifact (it works opened directly in a
browser) and keeps its serif typography and column layout from fighting Tailwind.
The one thing that crosses the boundary is the theme: `research_phrasebank.html`
posts `{type:'labui-theme', theme:'dark'|'light'}` into the frame on load and
whenever the sidebar toggle flips the `dark` class, and the page falls back to
`prefers-color-scheme` when opened standalone.

**It is a build artifact and it goes stale.** Everything else in a pack is read at
request time; this page is not. After editing `references/phrase-bank.md`:

```bash
python3 Local_Rag/rag/skills/build_phrasebank_html.py
```

The tab shows a "No phrase bank built" panel with that command when the file is
missing, so a fresh pack fails legibly rather than silently.

## Adding or updating a pack

Drop the folder in and restart. `loader.py` caches file reads with `lru_cache`, so a
running process will not see edits until restart (or `loader._read.cache_clear()`).

To point the loader at a new pack, set `"skill"` on the agent. To change which
reference file backs a section, edit `loader.SECTION_MAP`.

## Auditing without the app

The pack's audit script is a standalone CLI, stdlib only:

```bash
python3 nanobubble-paper-writer/scripts/audit_draft.py --section results draft.md
python3 nanobubble-paper-writer/scripts/audit_draft.py --json draft.md
```
