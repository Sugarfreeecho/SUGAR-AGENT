"""Browser package uploads are bounded and use the existing installers."""
import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def upload_client(tmp_path, monkeypatch):
    import webui
    monkeypatch.setenv("SKILLS_DIR", str(tmp_path / "skills"))
    monkeypatch.setattr(webui, "_invalidate_skills_cache", lambda: None)
    return TestClient(webui.fastapi_app)


SKILL = b'---\nname: dropped-skill\ndescription: Uploaded skill\n---\nRead files.'


@pytest.mark.parametrize("kind", ["dir", "zip"])
def test_skill_drop_installs_contents_using_frontmatter_name(upload_client, tmp_path, kind):
    if kind == "zip":
        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, "w") as archive:
            archive.writestr("example/SKILL.md", SKILL)
            archive.writestr("example/assets/a.txt", b"content")
        files = [("files", ("example.zip", bundle.getvalue(), "application/zip"))]
    else:
        files = [("files", ("example/SKILL.md", SKILL)), ("files", ("example/assets/a.txt", b"content"))]
    result = upload_client.post("/api/skills/install-upload", data={"kind": kind}, files=files)
    assert result.status_code == 200, result.text
    assert result.json()["name"] == "dropped-skill"
    assert (tmp_path / "skills/dropped-skill/assets/a.txt").read_text() == "content"


@pytest.mark.parametrize("filename", ["../outside", "/absolute", "C:/outside", "folder/../outside", "folder\\outside", "folder//bad", "folder/NUL.txt", "folder/trailing."])
def test_upload_rejects_invalid_relative_paths(upload_client, tmp_path, filename):
    result = upload_client.post("/api/skills/install-upload", data={"kind": "dir"}, files=[("files", (filename, b"x"))])
    assert result.status_code == 400
    assert not (tmp_path / "skills").exists()


def test_upload_rejects_duplicates_and_total_limit(upload_client, monkeypatch):
    import webui
    result = upload_client.post("/api/skills/install-upload", data={"kind": "dir"}, files=[("files", ("a.txt", b"x")), ("files", ("A.txt", b"x"))])
    assert result.status_code == 400
    monkeypatch.setattr(webui, "_SKILL_ARCHIVE_MAX_BYTES", 5)
    result = upload_client.post("/api/skills/install-upload", data={"kind": "dir"}, files=[("files", ("a.txt", b"123456"))])
    assert result.status_code == 413


def test_plugin_drop_runs_installer_and_refreshes_runtime(upload_client, monkeypatch):
    import agent_extensions
    import webui
    calls = []
    def install(source):
        root = Path(source)
        assert json.loads((root / "demo/.myagent-plugin/plugin.json").read_text())["id"] == "demo"
        calls.append(root)
        return {"action": "installed", "plugin_id": "demo"}
    async def refresh():
        calls.append("refresh")
    async def mcp():
        calls.append("mcp")
    monkeypatch.setattr(agent_extensions, "install_plugin", install)
    monkeypatch.setattr(webui, "refresh_web_plugin_lifecycle", refresh)
    monkeypatch.setattr(webui.agent_mcp, "force_reload", mcp)
    response = upload_client.post("/api/plugins/install-upload", data={"kind": "dir"}, files=[("files", ("demo/.myagent-plugin/plugin.json", b'{"id":"demo"}'))])
    assert response.status_code == 200
    assert calls[1:] == ["refresh", "mcp"]
    assert not calls[0].exists(), "temporary upload contents must be cleaned"


@pytest.mark.parametrize("route", ["skills", "plugins"])
def test_dropped_archive_cannot_escape_staging(upload_client, route, tmp_path):
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("../../escaped.txt", "bad")
    response = upload_client.post(f"/api/{route}/install-upload", data={"kind": "zip"}, files=[("files", ("bad.zip", bundle.getvalue()))])
    assert response.status_code == 400
    assert not (tmp_path / "escaped.txt").exists()


def test_env_snapshot_reports_effective_paths_without_writing_defaults(tmp_path, monkeypatch):
    import agent_extensions
    import agent_harness
    import webui
    env = tmp_path / ".env"
    env.write_text("# defaults only\n", encoding="utf-8")
    monkeypatch.setattr(webui, "dotenv_file_path", lambda: env)
    monkeypatch.setattr(webui, "WORK_DIR", tmp_path / "work")
    monkeypatch.setenv("SKILLS_DIR", str(tmp_path / "skills"))
    monkeypatch.setattr(agent_harness, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(agent_extensions, "plugin_manager", lambda: SimpleNamespace(discovery_dirs=[tmp_path / "plugins", tmp_path / "user-plugins"]))
    monkeypatch.setattr(agent_extensions, "hooks_config_path", lambda: tmp_path / "hooks.json")
    paths = TestClient(webui.fastapi_app).get("/api/env").json()["effective_paths"]
    assert paths["WORK_DIR"] == [str((tmp_path / "work").resolve())]
    assert paths["SKILLS_DIR"] == [str((tmp_path / "skills").resolve())]
    assert paths["LOG_DIR"] == [str((tmp_path / "logs").resolve())]
    assert len(paths["PLUGINS_DIR"]) == 2
    assert paths["HOOKS_PATH"] == [str((tmp_path / "hooks.json").resolve())]
    assert env.read_text() == "# defaults only\n"
