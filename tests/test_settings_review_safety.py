"""Security and persistence regressions found in the settings-center review."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
import io
import json
import os
import re
import stat
import tarfile
import threading
import zipfile

import pytest
from fastapi.testclient import TestClient


def test_bootstrap_cannot_end_script_and_roundtrips_session_id():
    import webui

    class Probe(HTMLParser):
        injected = False

        def handle_starttag(self, tag, attrs):
            if ("id", "settings-review-probe") in attrs:
                self.injected = True

    payload = '</ScRiPt><p id=settings-review-probe>probe</p><script>中文&\u2028\u2029'
    client = TestClient(webui.fastapi_app)
    for route in ("/settings", "/setup/env", "/setup/mcp", "/setup/extensions"):
        response = client.get(route, params={"session_id": payload})
        assert response.status_code == 200
        probe = Probe()
        probe.feed(response.text)
        assert not probe.injected
        bootstrap = re.search(r"window\.__MYAGENT_SETTINGS__\s*=\s*(.*?)\s*;\s*</script>", response.text, re.S)[1]
        assert "<" not in bootstrap and "&" not in bootstrap
        assert json.loads(bootstrap)["sessionId"] == payload


def test_settings_assets_support_conditional_cache_and_invalidate(tmp_path, monkeypatch):
    import webui

    asset = tmp_path / "core.js"
    asset.write_text("old();", encoding="utf-8")
    monkeypatch.setattr(webui, "_SETTINGS_STATIC_DIR", tmp_path)
    client = TestClient(webui.fastapi_app)
    first = client.get("/static/settings/core.js?v=1")
    assert first.status_code == 200 and first.headers["cache-control"] == "no-cache"
    unchanged = client.get("/static/settings/core.js?v=1", headers={"If-None-Match": first.headers["etag"]})
    assert unchanged.status_code == 304 and unchanged.content == b""
    weak = client.get("/static/settings/core.js", headers={"If-None-Match": "W/" + first.headers["etag"]})
    assert weak.status_code == 304
    version = webui._settings_asset_version()
    asset.write_text("new();", encoding="utf-8")
    changed = client.get("/static/settings/core.js?v=1", headers={"If-None-Match": first.headers["etag"]})
    assert changed.status_code == 200 and changed.text == "new();"
    assert changed.headers["etag"] != first.headers["etag"]
    assert webui._settings_asset_version() != version
    assert client.get("/settings").headers["cache-control"].startswith("no-store")


def test_concurrent_env_changes_merge_and_preserve_comments(tmp_path):
    import webui

    path = tmp_path / ".env"
    path.write_text("# keep this comment\nKEEP=1\nDROP=1\n", encoding="utf-8")
    barrier = threading.Barrier(3)

    def write(index):
        barrier.wait(timeout=5)
        webui._persist_env_updates(path, {f"NEW_{index}": str(index)}, ["DROP"] if index == 0 else [])

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(write, range(3)))
    text = path.read_text(encoding="utf-8")
    assert "# keep this comment" in text and "KEEP=1" in text and "DROP=" not in text
    assert all(f"NEW_{index}={index}" in text for index in range(3))
    assert list(tmp_path.glob("*.tmp")) == []


def test_env_replace_failure_keeps_original_and_cleans_staging(tmp_path, monkeypatch):
    import webui

    path = tmp_path / ".env"
    original = b"KEEP=1\n"
    path.write_bytes(original)

    def fail(*args):
        raise PermissionError("replace denied")

    monkeypatch.setattr(webui.os, "replace", fail)
    with pytest.raises(PermissionError):
        webui._persist_env_updates(path, {"NEW": "2"})
    assert path.read_bytes() == original
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows read-only attribute behavior")
def test_readonly_env_failure_leaves_no_staging_file(tmp_path):
    import webui

    path = tmp_path / ".env"
    path.write_text("KEEP=1\n", encoding="utf-8")
    path.chmod(0o400)
    try:
        with pytest.raises(PermissionError):
            webui._persist_env_updates(path, {"NEW": "2"})
        assert path.read_text() == "KEEP=1\n"
        assert list(tmp_path.glob("*.tmp")) == []
    finally:
        path.chmod(0o600)


def test_env_api_persists_off_event_loop(tmp_path, monkeypatch):
    import webui

    path = tmp_path / ".env"
    monkeypatch.setattr(webui, "dotenv_file_path", lambda: path)
    monkeypatch.setattr(webui, "refresh_executor_client_from_env", lambda: None)
    actual = webui._persist_env_updates
    threads = []

    def record(*args):
        threads.append(threading.get_ident())
        return actual(*args)

    monkeypatch.setattr(webui, "_persist_env_updates", record)

    class Request:
        async def json(self):
            return {"values": {"NEW": "2"}}

    main_thread = threading.get_ident()
    response = asyncio.run(webui.save_env_snapshot(Request()))
    assert response.status_code == 200
    assert threads and all(thread != main_thread for thread in threads)


def test_env_reset_clears_runtime_value_after_dotenv_refresh(tmp_path, monkeypatch):
    import dotenv
    import webui
    from security import security_enabled

    path = tmp_path / ".env"
    path.write_text("SECURITY_ENABLED=0\nKEEP=1\n", encoding="utf-8")
    monkeypatch.setenv("SECURITY_ENABLED", "0")
    monkeypatch.setenv("KEEP", "1")
    monkeypatch.setattr(webui, "dotenv_file_path", lambda: path)
    monkeypatch.setattr(webui, "refresh_executor_client_from_env", lambda: dotenv.load_dotenv(path, override=True))
    assert not security_enabled()
    response = TestClient(webui.fastapi_app).post("/api/env", json={"remove": ["SECURITY_ENABLED"]})
    assert response.status_code == 200
    assert "SECURITY_ENABLED" not in os.environ
    assert security_enabled()
    assert path.read_text(encoding="utf-8") == "KEEP=1\n"


def test_env_removal_takes_precedence_over_update_in_file_and_runtime(tmp_path, monkeypatch):
    import webui

    path = tmp_path / ".env"
    path.write_text("ASK_USER_ENABLED=0\n", encoding="utf-8")
    monkeypatch.setenv("ASK_USER_ENABLED", "0")
    webui._persist_env_updates(path, {"ASK_USER_ENABLED": "0"}, ["ASK_USER_ENABLED"])
    assert "ASK_USER_ENABLED" not in os.environ
    assert "ASK_USER_ENABLED" not in path.read_text(encoding="utf-8")
    assert webui.ask_user_enabled()


def test_reset_work_dir_reports_restart_required(tmp_path, monkeypatch):
    import webui

    path = tmp_path / ".env"
    path.write_text(f'WORK_DIR="{(tmp_path / "custom-workspace").as_posix()}"\n', encoding="utf-8")
    monkeypatch.setenv("WORK_DIR", str(tmp_path / "custom-workspace"))
    monkeypatch.setattr(webui, "dotenv_file_path", lambda: path)
    monkeypatch.setattr(webui, "refresh_executor_client_from_env", lambda: None)
    response = TestClient(webui.fastapi_app).post("/api/env", json={"remove": ["WORK_DIR"]})
    assert response.status_code == 200 and response.json()["restart_required"] is True
    assert "WORK_DIR" not in os.environ


def test_root_git_skills_use_declared_names_without_repo_collision(tmp_path, monkeypatch):
    import subprocess
    from pathlib import Path
    import webui

    skills = tmp_path / "skills"
    monkeypatch.setattr(webui, "_skills_root_dir", lambda: skills)

    def clone(args, **kwargs):
        name = args[-2].rsplit("/", 1)[1].removesuffix(".git")
        target = Path(args[-1])
        target.mkdir()
        (target / "SKILL.md").write_text(f"---\nname: {name}\ndescription: fixture\n---\n", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", clone)
    for name in ("alpha", "beta"):
        installed = webui._install_skill_from(f"https://example.invalid/{name}.git", "git")
        assert installed == skills / name
        assert (installed / "SKILL.md").is_file()
    assert not (skills / "repo").exists()
    with pytest.raises(ValueError, match="技能已存在：alpha"):
        webui._install_skill_from("https://example.invalid/alpha.git", "git")


@pytest.mark.parametrize("suffix", [".zip", ".tar.gz"])
def test_flat_archive_uses_declared_skill_name(tmp_path, monkeypatch, suffix):
    import webui

    skills = tmp_path / "skills"
    monkeypatch.setattr(webui, "_skills_root_dir", lambda: skills)
    content = b"---\nname: archive-skill\ndescription: fixture\n---\n"
    archive = tmp_path / ("download" + suffix)
    if suffix == ".zip":
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("SKILL.md", content)
    else:
        with tarfile.open(archive, "w:gz") as bundle:
            entry = tarfile.TarInfo("SKILL.md")
            entry.size = len(content)
            bundle.addfile(entry, io.BytesIO(content))
    installed = webui._install_skill_from(str(archive), "archive")
    assert installed == skills / "archive-skill"
    assert (installed / "SKILL.md").read_bytes() == content


@pytest.mark.parametrize("metadata", ["name: ../escape", "name: C:/escape", "description: missing", "name: [invalid"])
def test_skill_install_rejects_invalid_declared_identity(tmp_path, monkeypatch, metadata):
    import webui

    skills = tmp_path / "skills"
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text(f"---\n{metadata}\n---\n", encoding="utf-8")
    monkeypatch.setattr(webui, "_skills_root_dir", lambda: skills)
    with pytest.raises(ValueError, match="SKILL.md"):
        webui._install_skill_from(str(source), "dir")
    assert list(skills.iterdir()) == []


@pytest.mark.parametrize("name", ["../stage-escape/x", "..\\escape\\x", "/absolute/x", "C:/escape/x"])
def test_skill_zip_rejects_paths_outside_staging(tmp_path, name):
    import webui

    archive = tmp_path / "skill.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(name, "blocked")
    stage = tmp_path / "stage"
    stage.mkdir()
    with pytest.raises(ValueError, match="非法路径"):
        webui._extract_skill_archive(archive, stage)
    assert list(stage.rglob("*")) == []


def test_skill_zip_rejects_links_and_size_or_count_limits(tmp_path, monkeypatch):
    import webui

    archive = tmp_path / "skill.zip"
    link = zipfile.ZipInfo("skill/link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(link, "../outside")
    with pytest.raises(ValueError, match="链接"):
        webui._extract_skill_archive(archive, tmp_path / "stage")
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("one", "1234")
        bundle.writestr("two", "5678")
    monkeypatch.setattr(webui, "_SKILL_ARCHIVE_MAX_BYTES", 6)
    with pytest.raises(ValueError, match="体积"):
        webui._extract_skill_archive(archive, tmp_path / "stage2")
    monkeypatch.setattr(webui, "_SKILL_ARCHIVE_MAX_ENTRIES", 1)
    with pytest.raises(ValueError, match="文件数"):
        webui._extract_skill_archive(archive, tmp_path / "stage3")


def test_skill_tar_accepts_regular_files_and_rejects_links(tmp_path):
    import webui

    archive = tmp_path / "skill.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        entry = tarfile.TarInfo("skill/SKILL.md")
        entry.size = 4
        entry.mode = 0o755
        bundle.addfile(entry, io.BytesIO(b"demo"))
    webui._extract_skill_archive(archive, tmp_path / "safe")
    assert (tmp_path / "safe/skill/SKILL.md").read_text() == "demo"
    if os.name != "nt":
        assert (tmp_path / "safe/skill/SKILL.md").stat().st_mode & 0o111 == 0o111
    with tarfile.open(archive, "w:gz") as bundle:
        entry = tarfile.TarInfo("skill/link")
        entry.type = tarfile.SYMTYPE
        entry.linkname = "../outside"
        bundle.addfile(entry)
    with pytest.raises(ValueError, match="链接"):
        webui._extract_skill_archive(archive, tmp_path / "unsafe")


def test_skill_description_is_a_yaml_string(tmp_path, monkeypatch):
    import webui
    import yaml

    description = 'Contains: punctuation\n---\nname: injected\n"quotes" # comment'
    monkeypatch.setattr(webui, "_skills_root_dir", lambda: tmp_path)
    response = TestClient(webui.fastapi_app).post("/api/skills/create", json={"name": "safe", "description": description})
    assert response.status_code == 200
    text = (tmp_path / "safe/SKILL.md").read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(re.split(r"(?m)^---\s*$", text, maxsplit=2)[1])
    assert frontmatter == {"name": "safe", "description": description}
