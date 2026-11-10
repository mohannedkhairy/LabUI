# LM Studio configuration

`./start.sh` selects LM Studio by default. `./start-lm-studio.sh` starts the
app and its localhost model adapter. Use `./start-ollama.sh` for Ollama.
See [hosting](HOSTING.md) for optional Linux services and private client access.

Run `./setup.sh`, then copy `deploy/labui.env.example` to
`~/.config/labui/labui.env` and adjust it for your machine. The launcher also
supports `LABUI_CONFIG_FILE`. The adapter can read
`~/.config/local-model/config.json` and an optional private token file. No
machine-specific configuration, credentials or model weights ship in this branch.

## Settings

- `LM_STUDIO_URL`: server root or `/v1` URL, such as `http://localhost:1234/v1`.
- `LM_STUDIO_MODEL`: optional exact chat model ID; otherwise select an available model.
- `LM_STUDIO_API_KEY`: optional bearer token; keep it in private configuration.
- `LM_STUDIO_REASONING_EFFORT`: optional request-level reasoning setting.
- `LABUI_LM_PROXY_PORT`: adapter port; default 11435.
- `LABUI_PORT`: app port; default 8770.
- `LABUI_DATA_DIR`: library directory; preserve the existing location on upgrades.

Open http://127.0.0.1:8770 after startup. The model picker lists available chat
models. Generation, summaries, memory extraction and graph findings use the
configured server. Image attachments require a vision-capable model.

The adapter translates Ollama `/api/chat` requests and NDJSON responses to and
from LM Studio chat completions and SSE. It also passes through nonstreaming
`/v1/chat/completions` for memory extraction. Ollama evaluation-specific
`/api/generate` and embedding endpoints are outside this adapter's scope.

LM Studio owns the loaded context window; Ollama's `num_ctx` is not forwarded.
The output limit defaults to 4096 tokens and can be overridden by
`options.num_predict`. Truncated or empty replies are errors. Requests to the
configured model server bypass environment HTTP proxies.

Embeddings and reranking can run locally or on a compatible remote endpoint.
Match the embedding model and dimensions to the index. A different model needs a
migration even if its dimensions match. `LABUI_TEST_SMALL_MODELS=1` is available
for standalone development; use an isolated data directory for such experiments.
See [remote retrieval](GPU_RETRIEVAL.md) for configuration and migration tools.

## Development checks

```bash
./setup.sh
submission_strategy/.venv/bin/python tools/check_runtime.py
submission_strategy/.venv/bin/python tools/lm_studio_proxy.py --check
```

All launchers run feature dependency checks. `/api/health` and `/api/rag/status`
report readiness. Parsing or legacy graph-extraction requests report missing
imports before starting background work. New topic mapping does not require a
local NLP model; findings extraction uses the chat server.

The shared requirements cover the web runtime. Optional evaluation packages
are installed with `./setup.sh --with-evaluation` and require their own supported
backend. Unit tests use temporary data and controlled model responses. They do
not establish live model quality or scientific claim accuracy.
