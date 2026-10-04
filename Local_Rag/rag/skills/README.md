# Skill packs

A skill pack is a folder of markdown that defines a writing standard. Layout follows
the Claude skill convention:

```
skills/
  loader.py                    # progressive loader — assembles prompt slices
  audit.py                     # adapter over a pack's scripts/audit_draft.py
  build_phrasebank_html.py     # renders the browsable Phrase Bank page
  style_bank.py                # your phrase bank — moves mined from your style samples
  <skill-name>/
    SKILL.md                   # frontmatter (name, description) + overview
    references/*.md            # the detailed guides
    scripts/audit_draft.py     # optional; exposes audit_text(text, section) -> dict
    phrase-bank.html           # standalone copy of the page (the app renders it live)
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
| Phrase Bank page | `GET /api/rag/skills/{skill}/phrasebank.html` (rendered live, your sentences merged in), embedded by `GET /research/phrasebank` |
| Your phrase bank | `skills/style_bank.py`; `GET /api/rag/style/phrasebank`, `POST …/rebuild`, `POST …/hide` |
| Phrases panel | `GET /api/rag/skills/phrases?section=results` → writing workspace drawer → Phrases |

Everything degrades gracefully. Remove the pack folder and `resolve_system()` falls
back to the built-in rules in `agents.py`; the audit endpoints return 503 and the UI
disables its buttons.

## Phrase Bank tab

`/research/phrasebank` (sidebar → Research Lab → Phrase Bank) shows the pack's
rhetorical moves, reusable patterns, and attested exemplars, with search and
per-section / per-source filters. Clicking a pattern copies it.

It is a **self-contained page inside an iframe**, not a Jinja template, so its serif
typography and column layout do not fight Tailwind. The app renders it **on request**
from `references/phrase-bank.md` (`build_phrasebank_html.render()`), so it never goes
stale. The shell posts its theme into the frame — light/dark, the selected palette's
colour variables, and the font set's stylesheet — and the page falls back to
`prefers-color-scheme` when opened standalone.

`python3 Local_Rag/rag/skills/build_phrasebank_html.py` still writes a standalone copy
(`<pack>/phrase-bank.html`, without your sentences) for use outside the app.

## Your phrase bank (style samples → moves)

`style_bank.py` reads the writing-style samples (Research Lab → Writing Style),
splits them into sentences (aware of `et al.`, `Fig.`, `e.g.`…), and matches each one
against the pack's pattern frames — `However, X.` becomes `^However,\s+(.+?)`, and so
on, with the most specific frame winning. A sentence that fits a frame becomes **your
own exemplar of that move**. It also measures your connective rates against the
phrase bank's corpus budget and lists the sentence openers you reuse.

The result is cached at `<RAG_DATA_DIR>/style/.phrasebank.json` and rebuilt
automatically whenever a sample (or `phrase-bank.md`) changes. Sentences filed under
the wrong move can be hidden from the Writing Style page ("Not this move").

Where it shows up:

- **Phrase Bank page** — your sentences sit first in each move (teal, source "You"),
  plus panels comparing your connective rates with the corpus.
- **Writing Style page** — every sample shows which move each sentence performs,
  with the frame's words in bold.
- **Style Writer prompts** — `generation/agents.py:resolve_system()` appends
  `style_bank.brief_slice()`: your sentences for the moves of the section being
  drafted, and the connectives you already over-use. Unlike corpus exemplars (stripped
  because a local model copies them), these are your own words, so echoing their
  rhythm is the point.
- **Writing workspace → Phrases** — the section's frames (click to insert, first blank
  selected) with your sentences and two corpus exemplars under each.

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
