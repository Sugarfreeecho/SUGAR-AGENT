#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
MODE="auto"

if [[ "${1:-}" == "--server" ]]; then
  MODE="server"
  shift
elif [[ "${1:-}" == "--desktop" ]]; then
  MODE="desktop"
  shift
fi

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  bash "$ROOT/scripts/install_unix.sh" --mode "$MODE"
fi

# Verify dependencies on every start: a copied environment used to skip newly
# added requirements (e.g. psutil) and fail later at import time.
if ! "$ROOT/.venv/bin/python" "$ROOT/app/check_requirements.py"; then
  echo "Syncing Python dependencies..."
  "$ROOT/.venv/bin/python" -m pip install --disable-pip-version-check -r "$ROOT/app/requirements.txt"
  "$ROOT/.venv/bin/python" "$ROOT/app/check_requirements.py" || {
    echo "Dependency sync failed; see the missing list above." >&2
    exit 1
  }
fi

exec "$ROOT/scripts/agentctl" start --tray "$@"
