#!/usr/bin/env bash
# Complete Linux/macOS runtime setup. No application data or models are removed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/submission_strategy/.venv"
PYBIN="$VENV/bin/python"
EVALUATION=0
for argument in "$@"; do
  case "$argument" in
    --with-evaluation) EVALUATION=1 ;;
    --help|-h)
      echo "Usage: ./setup.sh [--with-evaluation]"
      echo "Installs all web features, the spaCy model, and verifies real imports."
      echo "LABUI_PYTHON can select Python >=3.12; LABUI_TORCH_BACKEND=cpu forces CPU wheels."
      exit 0 ;;
    *) echo "Unknown option: $argument" >&2; exit 2 ;;
  esac
done

if [[ ! -x "$PYBIN" ]]; then
  PY="${LABUI_PYTHON:-}"
  if [[ -z "$PY" ]]; then
    for candidate in python3.12 python3.13 python3; do
      if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; assert sys.version_info >= (3,12)' 2>/dev/null; then
        PY="$(command -v "$candidate")"
        break
      fi
    done
  fi
  if [[ -z "$PY" ]]; then
    echo "Python 3.12+ is required. Install it, or use: uv python install 3.12" >&2
    exit 1
  fi
  if [[ -e "$VENV" ]]; then
    echo "The existing virtual environment cannot run. Move $VENV aside, then rerun setup." >&2
    exit 1
  fi
  if command -v uv >/dev/null 2>&1; then
    uv venv --seed --python "$PY" "$VENV"
  else
    "$PY" -m venv "$VENV"
  fi
fi
"$PYBIN" -c 'import sys; assert sys.version_info >= (3,12), "Python >=3.12 is required"'

if command -v uv >/dev/null 2>&1; then
  INSTALL=(uv pip install --python "$PYBIN")
  "${INSTALL[@]}" pip
else
  "$PYBIN" -m ensurepip --upgrade
  INSTALL=("$PYBIN" -m pip install)
fi

# A remote generator GPU does not require local CUDA packages.
TORCH_BACKEND="${LABUI_TORCH_BACKEND:-auto}"
if [[ "$TORCH_BACKEND" == "cpu" ]] || { [[ "$(uname -s)" == "Linux" && "$TORCH_BACKEND" == "auto" ]] && ! command -v nvidia-smi >/dev/null 2>&1; }; then
  "${INSTALL[@]}" 'torch>=2.12,<3' torchvision --index-url https://download.pytorch.org/whl/cpu
fi

REQS="$ROOT/requirements.txt"
if [[ "$EVALUATION" == 1 ]]; then REQS="$ROOT/requirements-evaluation.txt"; fi
"${INSTALL[@]}" -r "$REQS" -e "$ROOT/submission_strategy"
if ! "$PYBIN" -c 'import en_core_web_sm' >/dev/null 2>&1; then
  "$PYBIN" -m spacy download en_core_web_sm
fi
if [[ "$EVALUATION" == 1 ]]; then
  "$PYBIN" "$ROOT/tools/check_runtime.py" --evaluation
else
  "$PYBIN" "$ROOT/tools/check_runtime.py"
fi
"$PYBIN" -m pip check
echo "Setup complete. Use ./start.sh for LM Studio or ./start-ollama.sh for Ollama."
echo "Docling and GLiNER download their model weights on first use."
