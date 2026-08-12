#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
MODE="auto"
SKIP_SYSTEM_PACKAGES="${SUGARAGENT_SKIP_SYSTEM_PACKAGES:-0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --skip-system-packages)
      SKIP_SYSTEM_PACKAGES=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

OS="$(uname -s)"
if [[ "$MODE" == "auto" ]]; then
  if [[ "$OS" == "Darwin" || -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    MODE="desktop"
  else
    MODE="server"
  fi
fi
if [[ "$MODE" != "desktop" && "$MODE" != "server" ]]; then
  echo "--mode must be auto, desktop, or server" >&2
  exit 2
fi
if [[ "$OS" == "Darwin" && "$MODE" != "desktop" ]]; then
  echo "macOS source installs currently support desktop mode only." >&2
  exit 2
fi

if [[ "$OS" == "Linux" ]]; then
  if [[ "$(uname -m)" != "x86_64" ]]; then
    echo "The supported Linux target is Ubuntu 22.04/24.04 x86_64." >&2
    exit 1
  fi
  if [[ ! -r /etc/os-release ]] || ! grep -q '^ID=ubuntu' /etc/os-release; then
    echo "The supported Linux target is Ubuntu 22.04/24.04." >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  source /etc/os-release
  if [[ "${VERSION_ID:-}" != "22.04" && "${VERSION_ID:-}" != "24.04" ]]; then
    echo "Unsupported Ubuntu release: ${VERSION_ID:-unknown}. Expected 22.04 or 24.04." >&2
    exit 1
  fi
  if [[ "$SKIP_SYSTEM_PACKAGES" != "1" ]]; then
    packages=(python3 python3-venv python3-pip git libmagic1)
    if [[ "$MODE" == "desktop" ]]; then
      packages+=(python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 zenity xdg-utils)
    fi
    sudo apt-get update
    sudo apt-get install -y "${packages[@]}"
  fi
  VENV_ARGS=(--system-site-packages)
elif [[ "$OS" == "Darwin" ]]; then
  VENV_ARGS=()
else
  echo "Unsupported operating system: $OS" >&2
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.10 or newer is required. On macOS, install a universal2 Python from python.org." >&2
  exit 1
fi
"$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
  echo "Python 3.10 or newer is required." >&2
  exit 1
}

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "${VENV_ARGS[@]}" "$ROOT/.venv"
fi
"$ROOT/.venv/bin/python" -m pip install --disable-pip-version-check --upgrade pip
"$ROOT/.venv/bin/python" -m pip install --disable-pip-version-check -r "$ROOT/app/requirements.txt"
chmod 0755 "$ROOT/app/native/sugaragent-egress-helper" "$ROOT/app/native/sugaragent-egress-helper.py"
"$ROOT/.venv/bin/python" "$ROOT/app/platform_install.py" install --root "$ROOT" --mode "$MODE"

if [[ "$OS" == "Linux" && "$MODE" == "server" ]]; then
  install_user="${USER:-$(id -un)}"
  sudo loginctl enable-linger "$install_user"
fi

echo "SugarAgent installed in $MODE mode."
echo "Start it with: $ROOT/scripts/agentctl start"
