"""Agent-wide Python runtime selection and child-process environment setup."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import MutableMapping


ROOT = Path(__file__).resolve().parents[1]


def bundled_python(root: Path = ROOT, *, windowed: bool = False) -> Path | None:
    """Return the repository-bundled interpreter when it exists."""
    name = "pythonw.exe" if windowed and os.name == "nt" else ("python.exe" if os.name == "nt" else "python3")
    candidate = root / "python" / name
    if candidate.is_file():
        return candidate.resolve()
    if os.name != "nt":
        fallback = root / "python" / "python"
        if fallback.is_file():
            return fallback.resolve()
    return None


def preferred_python(root: Path = ROOT, *, windowed: bool = False) -> Path:
    """Prefer the bundled interpreter; otherwise use the interpreter running the agent."""
    selected = bundled_python(root, windowed=windowed)
    if selected is not None:
        return selected
    current = Path(sys.executable).resolve()
    if windowed and os.name == "nt":
        sibling = current.with_name("pythonw.exe")
        if sibling.is_file():
            return sibling
    return current


def configure_agent_python_environment(
    env: MutableMapping[str, str] | None = None,
    root: Path = ROOT,
) -> MutableMapping[str, str]:
    """Make every child process spawned by the agent inherit the preferred Python first."""
    target = os.environ if env is None else env
    selected = preferred_python(root)
    dirs = [selected.parent]
    scripts = selected.parent / ("Scripts" if os.name == "nt" else "bin")
    if scripts.is_dir():
        dirs.append(scripts)
    existing = target.get("PATH", "")
    existing_parts = [part for part in existing.split(os.pathsep) if part]
    normalized = {os.path.normcase(os.path.abspath(part)) for part in dirs}
    tail = [part for part in existing_parts if os.path.normcase(os.path.abspath(part)) not in normalized]
    target["PATH"] = os.pathsep.join([*(str(part) for part in dirs), *tail])
    target["AGENT_PYTHON_EXE"] = str(selected)
    return target
