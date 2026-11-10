# LabUI

A local, private research workbench: **chat with your own PDF library** (retrieval-augmented,
with citations) plus a **journal-fit recommender / submission tracker**. Papers and indexes
stay on the host PC. Generation uses your configured LM Studio server, including a GPU
workstation on your private network. Phone and iPad access use the same hosted library.

This is a clean, self-contained instance: it ships with **no papers and no data**. You add your
own PDFs and they get indexed directly.

The `improved` branch collects the workspace split, weekly publication scout,
author/year citation suggestions, equipment inventory, source-backed knowledge
graph, metadata/retrieval repairs, and shared setup/hosting tools. It contains
source, tests, and portable configuration examples. Personal libraries,
credentials, model weights, and local diagnostic reports stay outside Git.

---

## What you get

- **Three workspaces** — switch between **Lab**, **Research & AI**, and
  **Writing & Publishing** at the top of the sidebar. Each has a focused
  dashboard and navigation; global search connects their shared records.
  See [workspaces](docs/WORKSPACES.md).
- **Equipment inventory** (`/equipment`, in Lab) — descriptions, instrument
  identification, photos/PDFs, important dates, service/calibration history, and
  vendor interactions with follow-up dates. See [inventory details](docs/EQUIPMENT_INVENTORY.md).
- **Nanobubble scout** (dashboard and `/research/scout`) — searches Crossref,
  Europe PMC, and arXiv automatically every week for nanobubble publications from
  only the previous seven complete UTC days. Exact publication dates are required. Saves
  deduplicated reports with paper links, source abstracts, preprint labels, and
  source coverage; includes a **Scan now** button. See [scout details](docs/PUBLICATION_SCOUT.md).
- **Research chat** (`/research/chat`) — ask questions across your library; answers stream with
  inline `[n]` citations and a sources panel. The current chat also searches the web.
- **Paper search** (`/research/search`) — hybrid BM25 + dense (bge-m3) retrieval, reranked.
- **Knowledge graph** (`/research/graph`) — source-backed topic/paper connections,
  author/year search, related reading, library coverage checks, and optional
  local-model findings with exact quotes and experimental conditions. Graph
  questions preserve the selected library scope. See [research map](docs/KNOWLEDGE_GRAPH.md).
- **Upload** (`/research/upload`) — drag in PDFs **or a whole folder**; they auto-index.
- **Notes** (`/research/notes`) — save answers and write-ups; one Markdown file each.
- **Writing citations** — type `@` for suggestions or `@cai` to find papers by
  author. Short author/year keys such as `@cai2024` link to the library; old keys
  remain valid. See [writing citations](docs/WRITING_CITATIONS.md).
- **Markdown + LaTeX math** — chat answers, notes, and experiment results render Markdown with
  KaTeX, so inline `$E = mc^2$` and display `$$\frac{a}{b}$$` math typeset properly.
- **Journal-Fit** (`/journals`, `/manuscripts`) — match a manuscript to candidate journals.
  Ships with a starter set of 23 venues; add more from the **/journals** page by searching
  online (Crossref, by name or ISSN) or entering them manually.

## Prerequisites

- **macOS (Apple Silicon)** or Linux. Full BGE-M3 retrieval needs 16 GB+ RAM;
  smaller local models or a remote model server can reduce local memory use.
- **Python 3.12+** (3.12 recommended). On macOS use Homebrew Python rather than Apple's
  system Python: `brew install python@3.12`. Linux system Python is supported when it
  provides SQLite extension loading. `uv python install 3.12` is another option.
- **LM Studio** serving a chat model. Set its address and model in
  `~/.config/labui/labui.env`; see [hosting](docs/HOSTING.md). Ollama remains an
  alternative through `./start-ollama.sh`.

## Setup

```bash
git clone --branch improved https://github.com/mohannedkhairy/LabUI.git
cd LabUI
./setup.sh            # installs all web features and verifies real imports
```

Then start it:

```bash
./start.sh            # LM Studio; serves http://127.0.0.1:8770
```

First launch downloads the selected embedder and reranker from HuggingFace, then
caches them. Open **http://127.0.0.1:8770**. If you installed the optional Linux
background services, use `systemctl --user restart labui` to restart the app.

`setup_mac.sh` remains an alias for `setup.sh`. All launchers run the same feature
checks before booting, including PDF parsing, web search, journal matching, and
graph extraction. Check or repair an existing environment with:

```bash
submission_strategy/.venv/bin/python tools/check_runtime.py
./setup.sh
```

The root `requirements.txt` is the shared runtime dependency list. Optional CLI
evaluation packages are installed with `./setup.sh --with-evaluation`.
For automatic startup, private phone access, and service controls, see
[hosting](docs/HOSTING.md). Adapter details are in [LM Studio configuration](docs/LM_STUDIO_TESTING.md).

## Development checks

After setup, run the Python regression suite and optional Node behavior checks:

```bash
PYTHONPATH=.:submission_strategy:Local_Rag/rag submission_strategy/.venv/bin/python \
  -c 'import unittest, uvloop; uvloop.install(); unittest.main(module=None, argv=["unittest", "discover", "-s", "tests"])'
node tests/knowledge.test.cjs
node tests/workspaces.test.cjs
node tests/writing_citations.test.cjs
```

Tests use temporary fixtures. Live model/server checks depend on your own
configuration and are separate from the regression suite.

## Adding your papers

Three ways, all of which trigger automatic indexing (`parse → chunk → embed → index`):

1. **Upload page** — `/research/upload`: drag PDFs or a folder, or click *Choose files* /
   *Choose folder*. Folders are scanned recursively.
2. **Drop into the folder** — copy PDFs into `$LABUI_DATA_DIR/papers/` (the host
   configuration selects this directory). The auto-index daemon polls
   every `RAG_INGEST_POLL_INTERVAL` seconds (default 120) and picks up new files.
3. **Index now** — the button on the upload page kicks an immediate index run instead of waiting.

Paper titles are recovered from embedded PDF metadata when the same title can be
verified on the first page. This also repairs older records still showing a
filename when the app starts or a summary is generated. Existing curated titles,
paper IDs, citation keys, and source files are preserved. Corrected titles appear
in the library, summaries, citations, and search results. Research search includes
title matches and supplies the canonical title to the passage reranker, so title
changes take effect without rebuilding embeddings.

When reference-library authors are missing, LabUI recovers the visible author
byline below the title on the PDF's first page, removes superscript affiliation
markers, and preserves author order. The embedded author tag is used to check
the byline; a first-author-only tag does not truncate the coauthor list. Missing
author lists are also backfilled at startup and after indexing, including the
citation catalog. Existing nonempty author metadata is preserved, and uncertain
layouts remain unfilled.

Title recovery also reads title-page section headings from the existing Docling
parse, including OCR text, and checks recognized publisher covers. When local
metadata is insufficient, new PDF imports can look up public DOI records through
Crossref. A registry title and ordered author surnames must match the PDF header
before any metadata is accepted. Set `RAG_METADATA_DOI=0` to disable those lookups.

For an existing library, the following command makes a SQLite backup and repairs
missing or generic labels, preserving paper IDs, citation keys and annotations:

```bash
submission_strategy/.venv/bin/python tools/repair_library_metadata.py \
  --db /path/to/rag.db --audit /path/to/audit --with-doi --apply
```

The optional `--with-model` uses the configured local adapter to select quoted
header text; unsupported titles and author names remain unfilled and appear in
the audit. Omit `--apply` to preview proposals.

Paper summaries are visible in **Library → Reference details**. The upload page
reports the number actually saved across the entire library and lists missing
summaries with their last failure or skip reason. A run counts generated, skipped
and failed items separately. Table-heavy supplements can use the original PDF
text when too little body text entered the search index.

The first batch on a fresh instance creates the index from scratch. Watch progress in the
upload page's *Auto-index* panel, or via `GET /api/rag/status`.

> **First index is slower.** On the very first run, `docling` downloads its PDF layout models
> (~hundreds of MB, one-time) before parsing. Subsequent indexing is much faster.

## Configuration 

| Variable | Default | Purpose |
|---|---|---|
| `LM_STUDIO_URL` | from local-model config, else `http://localhost:1234/v1` | GPU model server. |
| `LM_STUDIO_MODEL` | *(auto)* | Pin the exact chat model ID; otherwise auto-select from the server. |
| `LABUI_DATA_DIR` | `.data/labui` or existing legacy library | Main databases, PDFs, notes, and writing projects. |
| `RAG_GEN_MODEL` | *(auto)* | Generator override; the LM Studio launcher prefers `LM_STUDIO_MODEL`. |
| `RAG_GEN_PREFER` | `qwen3,qwen2.5,qwen,llama,gemma,mistral,phi` | Substring preference order when auto-selecting (Qwen3 first). |
| `OLLAMA_BASE_URL` | launcher-managed | Compatibility endpoint; native Ollama uses port 11434, the LM Studio adapter uses 11435. |
| `RAG_EMBED_MODEL` / `RAG_EMBED_DIM` | `BAAI/bge-m3` / `1024` | Embedder. **Changing the dim requires a fresh re-index** (it's baked into the vector table). |
| `RAG_RERANKER_MODEL` | `BAAI/bge-reranker-v2-m3` | Cross-encoder reranker. |
| `RAG_DATA_DIR` / `RAG_PAPERS_DIR` | in-tree | Relocate the index / papers folder. |
| `RAG_OUTPUT_DIR` | `Local_Rag/output` | Relocate summary files and the optional paper metadata library. |
| `RAG_GEN_NUM_CTX` | `32768` | Native Ollama context window. LM Studio uses its server-side context setting. |
| `RAG_INGEST_POLL_INTERVAL` | `120` | Auto-index poll seconds. |
| `JFR_DATA_DIR` | `$LABUI_DATA_DIR/jfr` | Journal-Fit data (db, vectors). |
| `LABUI_SCOUT_ENABLED` | `1` | Weekly nanobubble publication scans; `0` pauses automatic scans. |
| `LABUI_HOST` / `LABUI_PORT` | `127.0.0.1` / `8770` | Keep loopback binding for owner-only Tailscale Serve access. |

The generator model can also be picked live from the in-app model dropdown (top bar), which
lists chat models available from the configured generator server.

## How it works

```
LabUI/
├── start.sh / setup_mac.sh        # launcher + one-shot setup (cross-platform)
├── requirements.txt               # consolidated deps
├── submission_strategy/           # FastAPI host app (Journal-Fit) + web/ templates
│   └── jfr/web/rag_routes.py       #   RAG API mounted at /api/rag/*
└── Local_Rag/
    ├── papers/                    # YOUR PDFs land here (starts empty)
    └── rag/                       # RAG pipeline: ingest/, retrieval/, generation/
        └── data/                  # rag.db (FTS5 + sqlite-vec), created on first index
```

- **Generation**: the local adapter translates chat requests to LM Studio; the GPU server controls its model context window.
- **Embeddings/rerank**: `sentence-transformers` on MPS/CUDA/CPU (auto-detected).
- **Index**: one SQLite DB with FTS5 (BM25) + a `vec0` virtual table for dense vectors.

## Troubleshooting

- **Generator unavailable** — check LM Studio on the GPU server and `journalctl --user -u labui-model`.
- **sqlite-vec fails to load** — you're on Apple's system Python; use Homebrew `python@3.12`.
- **Uploads don't index** — check `GET /api/rag/status` → `ingest.message`; ensure PDFs are
  real (not scanned-image-only, which docling may skip) and under 200 MB.
- **Out of memory** — the PC runs retrieval/parsing, while the GPU server runs generation. Use appropriately sized models on each.
- **Port in use** — check `systemctl --user status labui labui-model`; avoid starting a second copy.

## Privacy

The host stores your research data and sends generator context to your configured
LM Studio server. Internet calls include model downloads, web search for chat,
and journal lookups/corpus refreshes. The Web tab displays results; it does not
disable search. Private remote access uses Tailscale Serve and an owner-identity
check. No public sharing endpoint is enabled.
</content>
## Publication workflow

Open **Submissions** to start a journal attempt for a manuscript. Its workspace shows a
graphical publication path, the current stage, available next actions, reviewer
responses grouped by round, and a dated history of decisions and progress notes.

The path is drafting → internal review → supervisor approval → submission → peer
review ↔ revisions → acceptance → optional proofs → publication. Revisions may
repeat. Each reviewer comment in the current round needs a response and an
addressed check before recording a resubmission. Rejections and withdrawals keep
their history, and allow a new journal attempt for the manuscript.

After acceptance, use **Record publication** to save the publication date and at
least one of a DOI, publication link, or final PDF (up to 50 MB). The paper then
appears under **Published papers**, with its final PDF and full review timeline.
This records an existing publication in LabUI; journal submission and publication
still happen through the journal. PDFs stay in the private LabUI attachment store.
Existing submission records are upgraded automatically without removing history.

Each stage has an editable **event date**, separate from the timestamp when you
logged it. Choose **Timeline → Edit timeline dates** to correct several dates at
once, including for completed submissions. Saving also updates the original
submission date, publication date, stage ages, and journal turnaround statistics.
Known event dates must follow the workflow order; events can share a day. Leave
unknown dates blank. Existing logging timestamps are retained.

For an older manuscript, choose its **Starting stage** and **Date this stage began**
when starting a timeline. An already published paper can start at **Accepted**;
then record its publication with the actual publication date and paper details.
Earlier stages remain marked as unrecorded.

## Import an existing PDF collection

`tools/import_pdfs.py` copies a local folder into LabUI storage and indexes it in
small batches. It checks PDFs, skips exact SHA-256 duplicates (including existing
papers), avoids filename collisions, and records each outcome in a resumable
manifest. Originals are read only. Once copying finishes, the source drive is no
longer needed for indexing. For example, from this checkout:

```bash
submission_strategy/.venv/bin/python tools/import_pdfs.py \
  --source '/path/to/pdfs' --data-dir .data/labui --batch-size 5
```

Use the data directory configured in `LABUI_DATA_DIR` for your installation.
LabUI must be running. Import progress appears on **Upload papers**; the detailed
manifest is in `<data-dir>/imports/<job-id>/manifest.json`. Rerunning the same
command resumes its manifest, including rechecking an interrupted index batch.
Failed conversions are reported separately and keep a local staging copy.

Publication years come from reference metadata, printed journal citations,
verified DOI records, or explicit publication dates in the PDF. An unknown year
stays blank, and reindexing preserves an existing year. To recover missing years
in an older library, preview the evidence before applying it:

```bash
submission_strategy/.venv/bin/python tools/repair_paper_years.py \
  --db .data/labui/rag/rag.db --audit .data/year-repair/preview --fetch-doi
```

Use your installation's data directory. Add `--apply` to backfill missing years;
the command first backs up SQLite and saves per-paper evidence in the audit
directory. Citation records receive the same dates without changing their keys.
