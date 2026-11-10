# Remote retrieval and migration

LabUI can use a configured LM Studio endpoint for chat, embeddings and relevance
ranking. Server addresses, model IDs, dimensions and quantization revisions are
configuration, not machine-specific source defaults. Start from
`deploy/labui.env.example` and keep credentials outside the repository.

## Configure retrieval

Use `RAG_EMBED_PROVIDER=lmstudio` with `RAG_EMBED_BASE_URL`, `RAG_EMBED_MODEL`,
`RAG_EMBED_DIM` and an explicit `RAG_EMBED_REVISION`. Use
`RAG_RERANK_PROVIDER=lmstudio` with `RAG_RERANK_BASE_URL` and
`RAG_RERANKER_MODEL` for remote reranking. The embedding profile records model,
provider, revision, dimensions, normalization and query prompt so incompatible
vector spaces are not silently mixed.

Check active settings through `/api/rag/status`. Keep using the current model
until replacement vectors have been built and validated. Changing only the
configured model or vector dimension on an existing index is not a migration.

## Stage and activate a migration

`tools/rebuild_embeddings.py` builds resumable replacement vectors beside the
existing source database. `tools/complete_gpu_upgrade.py` coordinates service
cutover, backups, settings, memory vectors and health checks. Inspect the CLI
options before running either tool against a real library:

```bash
submission_strategy/.venv/bin/python tools/rebuild_embeddings.py --help
submission_strategy/.venv/bin/python tools/complete_gpu_upgrade.py --help
```

Keep staging files under the ignored `.data` directory. Use a distinct staging
profile for a different model, prompt or quantization. Preserve original PDFs,
paper/chunk tables, citation keys, notes and conversations. Back up the library
and private configuration before activation. A failed activation restores the
previous index and configuration; interrupted work can resume cached batches.

Bulk embedding yields to interactive relevance requests through cross-process
activity leases. File locks release after a crash. An in-flight request must
finish before its next batch yields.

## Relevance and evidence limits

The Qwen relevance adapter uses yes/no token probabilities from a compatible
chat endpoint. This is a generative relevance estimate, not calibrated evidence
confidence or a guarantee of the reference reranker's normalized score. Invalid
probabilities and unexpected model IDs are errors. A dedicated ranking endpoint
may provide better batching and scoring for a particular server.

Hybrid retrieval combines title, BM25, dense and graph passages before final
reranking. Selected-paper scope is retained. The new
[knowledge graph](KNOWLEDGE_GRAPH.md) adds source-backed topic passages and
optional findings with exact quotes. Its comparisons still require scientific
review; the legacy NLP/citation graph is retained separately.

`tools/evaluate_retrieval_smoke.py` supplies a small research-library smoke test.
Store result passages and latency reports outside version control. Such reports
are local sanity checks, not a general benchmark or a substitute for reviewed
relevance labels. PDF layout and OCR parsing remain on the local CPU unless the
parser is separately configured; remote retrieval does not move parsing work.
