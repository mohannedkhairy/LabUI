# Runtime checks and troubleshooting

Use the shared installer and feature checks when an app page works but PDF
parsing, search or another feature is unavailable:

```bash
./setup.sh
submission_strategy/.venv/bin/python tools/check_runtime.py
```

The installer uses `submission_strategy/.venv` and the root requirements. The
legacy `setup_mac.sh` and RAG requirements entrypoint forward to that supported
installation path. Evaluation-only dependencies use
`./setup.sh --with-evaluation`.

All launchers run feature preflights. `/api/health` and `/api/rag/status` expose
readiness for application, retrieval, parsing, attachments, web search, journals
and legacy graph extraction. Health is degraded when a required dependency is
missing even if a model is loaded. Background jobs retain errors instead of
silently reporting success or treating failed imports as an empty result.

Nested PDF imports retain parser failures for inspection. Embedding models keep
their supported context limits, and model/vector dimension mismatches fail
before indexing. Memory-vector repairs preserve stored text and conversations.
Use backups and validated migration tools before changing a real vector index.

After a repair, verify readiness and try a disposable fixture in an isolated
library. Live model, parser and retrieval checks depend on your hardware and
configuration. Passing unit tests does not establish scientific answer accuracy.
