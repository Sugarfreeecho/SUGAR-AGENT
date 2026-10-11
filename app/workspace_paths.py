"""Read configured application paths without starting the agent or moving data."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Mapping


def resolve_env_path(name: str, default: Path | str, *, base: Path,
                     environment: Mapping[str, str] | None = None) -> Path:
    values = os.environ if environment is None else environment
    raw = str(values.get(name) or "").strip()
    path = Path(raw or default).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def configured_paths(project_root: Path | str | None = None, *,
                     environment: Mapping[str, str] | None = None,
                     default_work_dir: Path | str | None = None,
                     default_log_dir: Path | str | None = None) -> dict[str, str]:
    root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
    values = dict(os.environ if environment is None else environment)
    primary = root / "app" / ".env"
    if primary.is_file():
        from dotenv import dotenv_values
        file_values = {str(k).lstrip("\ufeff"): str(v) for k, v in dotenv_values(primary).items() if v is not None}
        override = values.get("MYAGENT_DOTENV_OVERRIDE", "1").lower() not in {"0", "false", "no", "off"}
        values = {**values, **file_values} if override else {**file_values, **values}
    work = resolve_env_path("WORK_DIR", default_work_dir or root / "workspace", base=root, environment=values)
    return {
        "work_dir": str(work),
        "sessions_dir": str(work / "sessions"),
        "skills_dir": str(resolve_env_path("SKILLS_DIR", work / "skills", base=root, environment=values)),
        "log_dir": str(resolve_env_path("LOG_DIR", default_log_dir or root / "logs", base=root, environment=values)),
    }


def configured_workspace_root(project_root: Path | str | None = None) -> Path:
    return Path(configured_paths(project_root)["work_dir"])


def server_workspace_root(base_url: str) -> Path:
    """Verification scripts must seed/clean the storage of the server they use."""
    from urllib.request import urlopen
    with urlopen(base_url.rstrip("/") + "/api/workspace-info", timeout=10) as response:
        payload = json.load(response)
    root = Path(payload["work_dir"]).expanduser()
    if not root.is_absolute() or not root.is_dir():
        raise ValueError(f"Server workspace is not a local directory: {root}")
    return root.resolve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root")
    parser.add_argument("--work-dir", help="Fallback when WORK_DIR is not configured")
    parser.add_argument("--log-dir", help="Fallback when LOG_DIR is not configured")
    args = parser.parse_args()
    print(json.dumps(configured_paths(args.project_root, default_work_dir=args.work_dir,
                                     default_log_dir=args.log_dir), ensure_ascii=True))
