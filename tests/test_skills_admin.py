"""技能管理：移除（本机技能目录）与安装同名冲突的三种处理（取消 / 覆盖 / 改名）。"""
import json
import shutil
from pathlib import Path

from starlette.testclient import TestClient


def _write_skill(root: Path, name: str, body: str = "body") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: demo skill\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return skill_dir


def _prepare(monkeypatch, tmp_path):
    import webui

    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    monkeypatch.setattr(webui, "_skills_root_dir", lambda: skills_root)
    monkeypatch.setattr(webui, "_invalidate_skills_cache", lambda: None)
    return webui, skills_root


def _fake_discovery(skills):
    def _discover(*, include_disabled=False, include_resources=False):
        return list(skills)

    return _discover


def test_remove_skill_deletes_project_skill(monkeypatch, tmp_path):
    webui, skills_root = _prepare(monkeypatch, tmp_path)
    target = _write_skill(skills_root, "demo")
    monkeypatch.setattr(
        webui,
        "discover_skills",
        _fake_discovery([{"name": "demo", "source": "project", "base_dir": str(target)}]),
    )

    response = TestClient(webui.fastapi_app).delete("/api/skills/demo")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "name": "demo", "path": str(target)}
    assert not target.exists()


def test_remove_skill_refuses_plugin_skill_and_missing(monkeypatch, tmp_path):
    webui, skills_root = _prepare(monkeypatch, tmp_path)
    plugin_skill = tmp_path / "plugins" / "demo-plugin" / "skills" / "demo"
    plugin_skill.mkdir(parents=True)
    (plugin_skill / "SKILL.md").write_text("---\nname: demo\ndescription: d\n---\n", encoding="utf-8")
    monkeypatch.setattr(
        webui,
        "discover_skills",
        _fake_discovery([{"name": "demo", "source": "plugin", "base_dir": str(plugin_skill)}]),
    )
    client = TestClient(webui.fastapi_app)

    refused = client.delete("/api/skills/demo")
    assert refused.status_code == 400
    assert "插件" in refused.json()["error"]
    assert plugin_skill.exists()

    monkeypatch.setattr(webui, "discover_skills", _fake_discovery([]))
    missing = client.delete("/api/skills/demo")
    assert missing.status_code == 400
    assert "没有找到" in missing.json()["error"]


def test_remove_skill_refuses_path_outside_skills_root(monkeypatch, tmp_path):
    webui, skills_root = _prepare(monkeypatch, tmp_path)
    outside = _write_skill(tmp_path / "elsewhere", "demo")
    monkeypatch.setattr(
        webui,
        "discover_skills",
        _fake_discovery([{"name": "demo", "source": "project", "base_dir": str(outside)}]),
    )

    response = TestClient(webui.fastapi_app).delete("/api/skills/demo")

    assert response.status_code == 400
    assert "技能目录" in response.json()["error"]
    assert outside.exists()


def test_install_skill_conflict_reports_suggestion(monkeypatch, tmp_path):
    webui, skills_root = _prepare(monkeypatch, tmp_path)
    _write_skill(skills_root, "demo", "old")
    _write_skill(skills_root, "demo-2", "old2")
    incoming = _write_skill(tmp_path / "incoming", "demo", "new")

    response = TestClient(webui.fastapi_app).post(
        "/api/skills/install", json={"source": str(incoming), "kind": "dir"}
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["ok"] is False
    assert payload["conflict"]["name"] == "demo"
    assert payload["conflict"]["suggested"] == "demo-3"  # demo-2 也被占
    assert (skills_root / "demo" / "SKILL.md").read_text(encoding="utf-8").endswith("old\n")


def test_install_skill_overwrite_replaces_existing(monkeypatch, tmp_path):
    webui, skills_root = _prepare(monkeypatch, tmp_path)
    _write_skill(skills_root, "demo", "old")
    incoming = _write_skill(tmp_path / "incoming", "demo", "new")

    response = TestClient(webui.fastapi_app).post(
        "/api/skills/install", json={"source": str(incoming), "kind": "dir", "on_conflict": "overwrite"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "demo"
    assert (skills_root / "demo" / "SKILL.md").read_text(encoding="utf-8").endswith("new\n")
    assert not (skills_root / "demo.installing").exists()


def test_install_skill_rename_uses_given_name(monkeypatch, tmp_path):
    webui, skills_root = _prepare(monkeypatch, tmp_path)
    _write_skill(skills_root, "demo", "old")
    incoming = _write_skill(tmp_path / "incoming", "demo", "new")
    client = TestClient(webui.fastapi_app)

    renamed = client.post(
        "/api/skills/install",
        json={"source": str(incoming), "kind": "dir", "on_conflict": "rename", "rename_to": "demo-copy"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "demo-copy"
    assert (skills_root / "demo-copy" / "SKILL.md").read_text(encoding="utf-8").endswith("new\n")
    assert (skills_root / "demo" / "SKILL.md").read_text(encoding="utf-8").endswith("old\n")

    bad = client.post(
        "/api/skills/install",
        json={"source": str(incoming), "kind": "dir", "on_conflict": "rename", "rename_to": "Bad Name"},
    )
    assert bad.status_code == 400
    assert "技能名" in bad.json()["error"]

    bad_mode = client.post(
        "/api/skills/install",
        json={"source": str(incoming), "kind": "dir", "on_conflict": "something"},
    )
    assert bad_mode.status_code == 400
    assert "on_conflict" in bad_mode.json()["error"]


def test_install_skill_upload_conflict_then_overwrite(monkeypatch, tmp_path):
    webui, skills_root = _prepare(monkeypatch, tmp_path)
    _write_skill(skills_root, "demo", "old")
    incoming = _write_skill(tmp_path / "incoming", "demo", "new")
    # 打成一个 zip 当上传包（目录名随意，内部会有 demo/SKILL.md）
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.write(incoming / "SKILL.md", "demo/SKILL.md")
    body = buffer.getvalue()
    client = TestClient(webui.fastapi_app)

    conflict = client.post(
        "/api/skills/install-upload",
        data={"kind": "zip"},
        files={"files": ("demo.zip", body, "application/zip")},
    )
    assert conflict.status_code == 409
    assert conflict.json()["conflict"]["name"] == "demo"

    retried = client.post(
        "/api/skills/install-upload",
        data={"kind": "zip", "on_conflict": "overwrite"},
        files={"files": ("demo.zip", body, "application/zip")},
    )
    assert retried.status_code == 200
    assert (skills_root / "demo" / "SKILL.md").read_text(encoding="utf-8").endswith("new\n")


def test_skills_routes_registered():
    import webui

    paths = {getattr(route, "path", "") for route in webui.fastapi_app.routes}
    assert "/api/skills/{skill_name}" in paths
    assert "/api/skills/install" in paths
