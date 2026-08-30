#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
if [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python cursor_workspace/build_scripts/init_env.py "$@"
fi
exec python3 cursor_workspace/build_scripts/init_env.py "$@"
