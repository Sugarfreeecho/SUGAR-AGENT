"""File storage for game-arena."""
from __future__ import annotations
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from myagent_plugin_sdk import current_tool_context


def _plugin_data_root() -> Path:
    raw = str(current_tool_context().plugin_data_dir or "").strip()
    if not raw:
        raise RuntimeError("Game Arena requires host-provided plugin_data_dir")
    root = Path(raw).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root

def games_dir() -> Path:
    d = _plugin_data_root() / "games"
    d.mkdir(parents=True, exist_ok=True)
    return d


def migrate_legacy_games(workspace_root: str, plugin_data_dir: str) -> int:
    """Copy legacy game JSON into host storage without deleting old data."""

    workspace = str(workspace_root or "").strip()
    destination = str(plugin_data_dir or "").strip()
    if not workspace or not destination:
        return 0
    legacy = Path(workspace).expanduser().resolve() / ".myagent" / "game-arena" / "games"
    target = Path(destination).expanduser().resolve() / "games"
    if not legacy.is_dir() or legacy == target:
        return 0
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for source in legacy.glob("*.json"):
        if not source.is_file():
            continue
        destination_path = target / source.name
        if destination_path.exists():
            continue
        shutil.copy2(source, destination_path)
        copied += 1
    return copied

def game_path(game_id: str) -> Path:
    safe = "".join(c for c in game_id if c.isalnum() or c in "-_")
    return games_dir() / f"{safe}.json"

def load_game(game_id: str) -> Optional[Dict[str,Any]]:
    p = game_path(game_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def save_game(state: Dict[str,Any]) -> None:
    gid = state.get("id") or state.get("game_id") or "unknown"
    p = game_path(str(gid))
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

def list_games(status: Optional[str]=None, limit: int=20) -> List[Dict[str,Any]]:
    d = games_dir()
    items = []
    for p in d.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if status and data.get("status") != status:
                continue
            items.append(data)
        except Exception:
            continue
    items.sort(key=lambda x: x.get("updated_at",0), reverse=True)
    return items[:limit]
