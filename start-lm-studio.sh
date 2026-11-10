#!/usr/bin/env bash
# Main LM Studio launcher; systemd starts the adapter as a separate service.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="$ROOT/submission_strategy/.venv/bin/python"
CONFIG="${LABUI_CONFIG_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/labui/labui.env}"
if [[ -f "$CONFIG" ]]; then
  set -a
  source "$CONFIG"
  set +a
fi
APP_ONLY=0
if [[ "${1:-}" == "--app-only" ]]; then
  APP_ONLY=1
elif [[ $# != 0 ]]; then
  echo "Usage: ./start-lm-studio.sh [--app-only]" >&2
  exit 2
fi
if [[ ! -x "$PY" ]]; then
  echo "Run ./setup.sh to install the complete runtime first." >&2
  exit 1
fi

# Existing installations keep the same data and embedding model. New instances
# get .data/labui. The historical directory name does not make its data disposable.
DEFAULT_DATA="$ROOT/.data/labui"
if [[ ! -d "$DEFAULT_DATA" && -d "$ROOT/.data/lm-studio-test" ]]; then
  DEFAULT_DATA="$ROOT/.data/lm-studio-test"
fi
DATA="${LABUI_DATA_DIR:-$DEFAULT_DATA}"
PROXY_PORT="${LABUI_LM_PROXY_PORT:-11435}"
export LABUI_LLM_BACKEND=lmstudio
export OLLAMA_BASE_URL="http://127.0.0.1:$PROXY_PORT"
export JFR_DATA_DIR="$DATA/jfr"
export RAG_DATA_DIR="$DATA/rag"
export RAG_PAPERS_DIR="$DATA/papers"
export RAG_OUTPUT_DIR="$DATA/output"
export RAG_NOTES_DIR="$DATA/notes"
export RAG_MANUSCRIPTS_DIR="$DATA/manuscripts"
export JFR_CORPUS_AUTOSTART="${JFR_CORPUS_AUTOSTART:-0}"
export JFR_CORPUS_REFRESH_DAYS="${JFR_CORPUS_REFRESH_DAYS:-0}"
export LABUI_HOST="${LABUI_HOST:-127.0.0.1}"
export LABUI_PORT="${LABUI_PORT:-8770}"
export LABUI_ACCESS_POLICY="${LABUI_ACCESS_POLICY:-$(dirname "$CONFIG")/access.json}"
export RAG_GEN_MODEL="${LM_STUDIO_MODEL:-${RAG_GEN_MODEL:-}}"
export PYTHONPATH="$ROOT/submission_strategy:$ROOT/Local_Rag/rag${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
if [[ "${LABUI_TEST_SMALL_MODELS:-0}" == 1 ]]; then
  export RAG_EMBED_MODEL=BAAI/bge-small-en-v1.5
  export RAG_EMBED_DIM=384
  export RAG_RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
fi
mkdir -p "$DATA"
"$PY" "$ROOT/tools/check_runtime.py"

# Starting the web app never depends on the GPU being online. Model requests
# report a connection error while the GPU is offline; the library stays usable.
if [[ "$APP_ONLY" == 1 ]]; then
  cd "$ROOT/submission_strategy"
  exec "$PY" -m uvicorn jfr.web.app:app --host "$LABUI_HOST" --port "$LABUI_PORT" --no-access-log
fi

"$PY" - "$PROXY_PORT" "$LABUI_HOST" "$LABUI_PORT" <<'PY'
import socket, sys
for host, port in [('127.0.0.1', int(sys.argv[1])), (sys.argv[2], int(sys.argv[3]))]:
    with socket.socket() as sock:
        try:
            sock.bind((host, port))
        except OSError:
            raise SystemExit(f'Port {port} is in use. Check systemctl --user status labui labui-model.')
PY
"$PY" "$ROOT/tools/lm_studio_proxy.py" --port "$PROXY_PORT" >"$DATA/adapter.log" 2>&1 &
PROXY_PID=$!
APP_PID=""
cleanup() {
  if [[ -n "$APP_PID" ]]; then kill "$APP_PID" 2>/dev/null || true; fi
  kill "$PROXY_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo "LabUI — LM Studio; data: $DATA; URL: http://$LABUI_HOST:$LABUI_PORT"
"$0" --app-only &
APP_PID=$!
while kill -0 "$PROXY_PID" 2>/dev/null && kill -0 "$APP_PID" 2>/dev/null; do
  sleep 2
done
echo "A LabUI process stopped; shutting down its companion process." >&2
exit 1
