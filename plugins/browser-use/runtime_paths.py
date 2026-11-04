"""Prefer the application-owned runtime; source checkouts may use system Node."""
from pathlib import Path
import json
import os
import shutil

ROOT = Path(__file__).resolve().parents[2]


def is_packaged(root=None):
    root = root or ROOT
    return any((root / name).is_file() for name in ("browser-bundle.json", "runtime-manifest.json"))


def node_executable(root=None):
    root = root or ROOT
    bundled = root / "node" / ("node.exe" if os.name == "nt" else "node")
    if bundled.is_file():
        return str(bundled)
    # An incomplete installed payload must not silently run an unrelated PATH
    # executable. Its settings page will ask the user to repair the app.
    return "" if is_packaged(root) else (shutil.which("node") or "")


def runtime_installed(directory):
    try:
        expected = json.loads((directory / "package.json").read_text(encoding="utf-8"))["dependencies"]["@playwright/mcp"]
        actual = json.loads((directory / "node_modules/@playwright/mcp/package.json").read_text(encoding="utf-8"))["version"]
        return actual == expected and all((directory / name).is_file() for name in (
            "server.mjs", "engine.mjs", "relay.mjs", "node_modules/playwright/package.json", "node_modules/playwright-core/package.json"))
    except (OSError, ValueError, KeyError):
        return False
