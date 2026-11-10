#!/usr/bin/env bash
# Backward-compatible name; setup.sh supports Linux and macOS.
set -euo pipefail
exec "$(cd "$(dirname "$0")" && pwd)/setup.sh" "$@"
