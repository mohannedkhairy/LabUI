# Knowledge graph

Open **Research & AI → Knowledge graph** (`/research/graph`). The default explorer
connects papers to explicit topics and methods, with source passages explaining
each link. It replaces the old high-frequency entity visualization. The existing
NLP/citation graph database and its API remain intact.

## Explore the library

Search by topic, title, author or citation key such as `@cai2024`. Aliases join
CO₂/CO2/carbon dioxide, NaCl/sodium chloride, and full method names/abbreviations
such as nanoparticle tracking analysis/NTA. The initial vocabulary includes 50
nanobubble topics across systems, chemistry, conditions, properties,
characterization, generation, modeling and applications. It is deliberately
conservative and editable in `retrieval/knowledge_topics.py`; unmatched topics
are not invented by a model.

Filter by publication year, category or minimum topic coverage. Unknown years
are excluded when a year range is applied. The map shows representative papers
and up to 14 topics. Link selection keeps strong connections and essential
bridges, without drawing every mention in the collection. Full membership stays
available in the inspector, including a paginated list of every connected paper.
The SVG map supports zoom, pan and keyboard node selection and uses local assets
without a graph-library CDN or a continuous physics simulation.

Select a paper or topic to see source excerpts with section/page provenance,
short citation keys, PDF links, related reading and extracted findings. Focusing
a neighborhood redraws the map around the selected item. URLs retain the search,
year/category filters, focus, selected node and active tab.

**Reading paths** identifies papers spanning several topic categories and topic
pairs represented separately but with no joint mentions in the current library.
Those pairs indicate library coverage gaps; they are not evidence of scientific
novelty. Shared terminology does not establish a causal relationship or prove
that a method was used experimentally in a paper.

## Evidence and comparisons

Under **Evidence tools → Extract findings**, the configured local chat model
checks up to 12 eligible passages per batch. Select a topic or paper to target
the work; query/year restrictions are retained. Without a selection or search,
the batch scans the mapped library. The API allows batches of 1–60 passages.
Large topic scopes retain all paper IDs; only the number of model calls is
bounded. No local GLiNER/spaCy model is required for this new evidence layer.

Findings retain source/target wording, relation, an exact contiguous quote,
experimental conditions, paper/chunk/section/pages, model and source text hash.
Entities and any conditions must occur in the quoted passage. Fabricated quotes,
unsupported entities, lost negation, positive assertions from explicitly
hypothetical wording, invalid/truncated responses and unknown relations are
rejected. A verified quote confirms its source, not the correctness of the
model's scientific interpretation; the original evidence remains visible.

**Findings to compare** groups equivalent canonical property pairs when different
papers report increasing, decreasing or no detected effects. It preserves the
conditions and quotes for comparison. These are candidate differences, not
automatic contradiction labels. Hypotheses are kept separate. No comparison
does not imply agreement, particularly when extraction coverage is incomplete.

Successful and valid-empty chunks are checkpointed by text hash/model. Failed
or all-invalid responses remain retryable. Stop requests finish the current
passage; completed work stays saved. Reference/bibliography sections are excluded,
and results/discussion/conclusion passages are prioritized. One paper cannot
monopolize a batch. Multiple updates cannot run concurrently, including across
processes. Library changes invalidate that paper's older findings on refresh;
source changes during extraction prevent publication of stale quotes.

**Ask evidence agent** opens a question scoped to every paper behind the selected
node and the active query/year range. The chat displays its graph scope, sends
those paper IDs to retrieval, and excludes web/memory context for that scope.
Failure to resolve a removed/empty scope blocks automatic submission. Clear
scope, a new chat, or opening a different saved session restores ordinary chat.
The scope applies to the current tab; it is not persisted in saved sessions.

Exports include the scoped map and evidence as JSON, or the extracted findings
and source metadata as CSV. CSV text is protected against spreadsheet formula
interpretation.

## Storage and updates

The derived index is `$RAG_DATA_DIR/knowledge.db`, separate from `rag.db`, the
legacy `graph.db`, vector indexes and citation IDs. It stores paper metadata,
up to five representative excerpts per paper/topic, findings and extraction
checkpoints. Counts distinguish unique source passages from topic memberships.
The indexer reads library data without modifying papers, chunks or embeddings.
Its source fingerprints include metadata, citation keys, vocabulary and chunks.
Unchanged papers are skipped. Deleted papers and their derived data are removed.

Refresh map runs in the background without loading a GPU model. Library ingestion
refreshes the map after committing indexed papers. If another map/extraction job
is active, import succeeds and the UI can refresh the derived index later. The
status endpoint checks source content freshness, caching digests while files are
unchanged; timestamp-only changes do not produce false stale-state warnings.
Only relevant source rows contribute to freshness, so auxiliary settings and
SQLite bookkeeping do not trigger refresh warnings. Refreshing an unchanged
815-paper library took 0.76 seconds in the local check; map queries took about
50–60 ms. Initial indexing includes topic extraction and takes longer.

Topic-backed passages also feed hybrid retrieval before its existing final
reranker and paper-diversity handling. Paper restrictions apply before the graph
candidate limit. The legacy fallback is bounded to avoid unbounded expansion.

API routes under `/api/rag/knowledge`:

- `GET /`: map; `q`, `focus`, `category`, `year_from`, `year_to`, `min_papers`, `limit`.
- `GET /status`: coverage, freshness and background-job status.
- `GET /node?id=topic:<slug>|paper:<paper-id>`: evidence and full scoped paper IDs;
  supports `q`, year limits and `paper_offset` for its 20-paper page.
- `POST /build`: incremental library refresh; no destructive reset option.
- `POST /extract`: optional `paper_ids`, `topic_id`, `max_chunks`.
- `POST /cancel`: stop a findings job after the active passage.
- `GET /export?format=json|csv`: query/year-scoped downloads.

Restart an already running app to register the new routes, then reload:

```bash
systemctl --user restart labui
```

Tests cover indexing, source preservation, alias matching, dates/scopes, no
isolated nodes, extraction validation/resume, concurrent jobs, source repairs,
exports, pagination and graph-to-agent scope. The extraction tests use controlled
model responses; actual extraction requires access to the configured model server.
