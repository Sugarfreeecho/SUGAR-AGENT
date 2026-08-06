import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def test_native_absolute_workspace_path_is_allowed(tmp_path, monkeypatch):
    import webui

    workspace = tmp_path / "workspace"
    target = workspace / "nested" / "file.txt"
    target.parent.mkdir(parents=True)
    target.write_text("ok", encoding="utf-8")
    monkeypatch.setattr(webui, "WORK_DIR", workspace)

    assert webui._resolve_allowed_local_path(str(target), True) == target.resolve()


def test_slash_rooted_virtual_path_still_resolves_under_workspace(tmp_path, monkeypatch):
    import webui

    workspace = tmp_path / "workspace"
    target = workspace / "nested" / "file.txt"
    target.parent.mkdir(parents=True)
    target.write_text("ok", encoding="utf-8")
    monkeypatch.setattr(webui, "WORK_DIR", workspace)

    assert webui._resolve_allowed_local_path("/nested/file.txt", True) == target.resolve()


def test_existing_absolute_path_outside_workspace_is_allowed(tmp_path, monkeypatch):
    import webui

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    monkeypatch.setattr(webui, "WORK_DIR", workspace)

    assert webui._resolve_allowed_local_path(str(outside), True) == outside.resolve()


def test_missing_absolute_path_is_rejected(tmp_path, monkeypatch):
    import webui

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    missing = tmp_path / "missing.txt"
    monkeypatch.setattr(webui, "WORK_DIR", workspace)

    with pytest.raises(FileNotFoundError):
        webui._resolve_allowed_local_path(str(missing), True)


def test_virtual_paths_stay_under_workspace(tmp_path, monkeypatch):
    import webui

    workspace = tmp_path / "workspace"
    target = workspace / "nested" / "file.txt"
    target.parent.mkdir(parents=True)
    target.write_text("ok", encoding="utf-8")
    monkeypatch.setattr(webui, "WORK_DIR", workspace)

    assert webui._resolve_allowed_local_path(
        "/nested/file.txt", True
    ) == target.resolve()
