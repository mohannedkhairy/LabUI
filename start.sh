#!/usr/bin/env bash
# LM Studio is the primary backend. The optional Ollama launcher remains usable.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ "${LABUI_LLM_BACKEND:-lmstudio}" == "ollama" ]]; then
  exec "$ROOT/start-ollama.sh" "$@"
fi
exec "$ROOT/start-lm-studio.sh" "$@"
