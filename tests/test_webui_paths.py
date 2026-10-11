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


@pytest.mark.parametrize("kind", ["relative", "virtual", "absolute"])
def test_saved_legacy_media_path_resolves_after_config_rename(tmp_path, monkeypatch, kind):
    import webui
    from config_paths import config_dir

    workspace = tmp_path / "workspace"
    legacy = workspace / ".sugaragent/history-media/image.png"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"saved-image")
    config_dir(workspace)
    monkeypatch.setattr(webui, "WORK_DIR", workspace)
    raw = {
        "relative": ".sugaragent/history-media/image.png",
        "virtual": "/.sugaragent/history-media/image.png",
        "absolute": str(legacy),
    }[kind]

    resolved = webui._resolve_allowed_local_path(raw, True)

    assert resolved == workspace / ".config/history-media/image.png"
    assert resolved.read_bytes() == b"saved-image"
