#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
KEEP_VENV=0

if [[ "${1:-}" == "--keep-venv" ]]; then
  KEEP_VENV=1
fi
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="${PYTHON_BIN:-python3}"
fi

args=(uninstall --root "$ROOT")
if [[ "$KEEP_VENV" == "1" ]]; then
  args+=(--keep-venv)
fi
"$PYTHON" "$ROOT/app/platform_install.py" "${args[@]}"
echo "Service integration removed. Workspace, configuration, plugins, and logs were preserved."
