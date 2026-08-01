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

exec "$ROOT/scripts/agentctl" start --tray "$@"
