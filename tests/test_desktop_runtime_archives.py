"""Desktop resource compatibility checks; never invoke the payload or installer build."""
import importlib.util
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


archives = load_module("desktop_archive_builder", ROOT / "packaging/scripts/archive-runtime.py")
icons = load_module("desktop_archived_icons", ROOT / "packaging/runtime/sugaragent_icon_archive.py")


def sdk_fixture(tmp_path):
    payload = tmp_path / "build/payload"
    package = payload / "python/Lib/site-packages/lark_oapi"
    (package / "api").mkdir(parents=True)
    (package / "__init__.py").write_text("from .api import value\n", encoding="utf-8")
    (package / "api/__init__.py").write_text("value = '归档 SDK'\n", encoding="utf-8")
    (package / "api/message.txt").write_text("offline resource", encoding="utf-8")
    (package / "__pycache__").mkdir()
    (package / "__pycache__/old.pyc").write_bytes(b"obsolete cache")
    metadata = package.parent / "lark_oapi-1.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Name: lark-oapi\nVersion: 1.0\n", encoding="utf-8")
    (metadata / "RECORD").write_text("lark_oapi/__init__.py,,\nlark_oapi/api/__init__.py,,\n"
                                    "lark_oapi-1.0.dist-info/METADATA,,\nlark_oapi-1.0.dist-info/RECORD,,\n",
                                    encoding="utf-8")
    return payload, package, metadata


def test_sdk_imports_bytecode_and_resources_from_archive(tmp_path):
    payload, package, metadata = sdk_fixture(tmp_path)
    report = archives.archive_sdk(payload)
    assert not package.exists()
    assert metadata.is_dir()
    with (metadata / "RECORD").open(encoding="utf-8", newline="") as stream:
        records = list(csv.reader(stream))
    recorded_files = {row[0] for row in records}
    assert "lark_oapi.zip" in recorded_files
    assert "sugaragent-runtime-archives.pth" in recorded_files
    assert not any(name.startswith("lark_oapi/") for name in recorded_files)
    assert report["replacedFiles"] == 4
    target = payload / report["path"]
    with zipfile.ZipFile(target) as archive:
        assert archive.read("lark_oapi/__init__.pyc")[:4] == importlib.util.MAGIC_NUMBER
        assert not any("__pycache__" in name for name in archive.namelist())
    probe = r'''
import site, sys, importlib.metadata, pkgutil
sys.path[:] = [p for p in sys.path if 'site-packages' not in p]
site.addsitedir(sys.argv[1])
import lark_oapi
assert '.zip' in lark_oapi.__file__ and lark_oapi.__file__.endswith('.pyc')
assert lark_oapi.value == '归档 SDK'
assert pkgutil.get_data('lark_oapi.api', 'message.txt') == b'offline resource'
assert importlib.metadata.version('lark-oapi') == '1.0'
print('ARCHIVE_IMPORT_OK')
'''
    result = subprocess.run([sys.executable, "-B", "-c", probe, str(package.parent)],
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ARCHIVE_IMPORT_OK" in result.stdout
    digest = report["sha256"]
    assert archives.archive_sdk(payload)["sha256"] == digest
    assert not package.exists()


def test_sdk_native_module_drift_keeps_original_files(tmp_path):
    payload, package, _ = sdk_fixture(tmp_path)
    (package / "native.pyd").write_bytes(b"native module")
    with pytest.raises(RuntimeError, match="native modules"):
        archives.archive_sdk(payload)
    assert package.is_dir()
    assert not (package.parent / "lark_oapi.zip").exists()


def test_sdk_symlink_cannot_compact_original_developer_package(tmp_path):
    payload = tmp_path / "build/payload"
    site = payload / "python/Lib/site-packages"
    site.mkdir(parents=True)
    original = tmp_path / "developer/lark_oapi"
    original.mkdir(parents=True)
    (original / "__init__.py").write_text("value = 42\n", encoding="utf-8")
    try:
        (site / "lark_oapi").symlink_to(original, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlink creation is unavailable")
    with pytest.raises(RuntimeError, match="escapes"):
        archives.archive_sdk(payload)
    assert (original / "__init__.py").read_text(encoding="utf-8") == "value = 42\n"


def icon_fixture(tmp_path):
    root = tmp_path / "icons"
    root.mkdir()
    data = b'<svg viewBox="0 0 24 24"><path d="M0 0L24 24"/></svg>'
    archive = root / "icons.zip"
    with zipfile.ZipFile(archive, "w") as writer:
        writer.writestr("tabler-outline/home.svg", data)
        writer.writestr("tabler-outline/user.svg", data)
    (root / "icon-archive.json").write_text(json.dumps({
        "schemaVersion": 1, "sha256": archives._sha256(archive),
        "entries": ["tabler-outline/home.svg", "tabler-outline/user.svg"],
    }), encoding="utf-8")
    return root, data


def test_icon_listing_is_lazy_and_extraction_preserves_custom_icons(tmp_path):
    root, data = icon_fixture(tmp_path)
    assert icons.list_icons(root, "tabler-outline", "home") == ["tabler-outline/home"]
    assert list(root.rglob("*.svg")) == []
    selected = icons.materialize_icon(root / "tabler-outline/home.svg")
    assert selected.read_bytes() == data
    assert not (root / "tabler-outline/user.svg").exists()
    selected.write_bytes(b"custom local icon")
    assert icons.materialize_icon(selected).read_bytes() == b"custom local icon"
    assert icons.materialize_icon(root / "tabler-outline/missing.svg").exists() is False


def test_readonly_icon_root_falls_back_to_single_cached_icon(tmp_path, monkeypatch):
    root, data = icon_fixture(tmp_path)
    original = icons._write_icon
    def readonly(destination, content):
        if destination.is_relative_to(root):
            raise PermissionError("read-only runtime")
        return original(destination, content)
    monkeypatch.setattr(icons, "_write_icon", readonly)
    monkeypatch.setattr(icons.tempfile, "gettempdir", lambda: str(tmp_path / "cache"))
    selected = icons.materialize_icon(root / "tabler-outline/home.svg")
    assert selected.read_bytes() == data
    assert selected.is_relative_to(tmp_path / "cache")
    assert list(root.rglob("*.svg")) == []
    assert len(list((tmp_path / "cache").rglob("*.svg"))) == 1


def test_ppt_adaptation_fails_before_removing_icons_when_reader_changes(tmp_path):
    payload = tmp_path / "build/payload"
    skill = payload / "workspace-template/skills/ppt-master"
    (skill / "templates/icons").mkdir(parents=True)
    (skill / "templates/icons/home.svg").write_text("<svg/>", encoding="utf-8")
    (skill / "scripts").mkdir()
    (skill / "scripts/icon_sync.py").write_text("# upstream changed\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="reader changed"):
        archives.archive_ppt_icons(payload)
    assert (skill / "templates/icons/home.svg").is_file()
    assert not (skill / "templates/icons/icons.zip").exists()


def test_real_ppt_readers_expand_only_selected_icons_and_preserve_project_customization(tmp_path):
    source = ROOT / "workspace/skills/ppt-master"
    if not (source / "scripts/svg_finalize/embed_icons.py").is_file():
        pytest.skip("Local PPT skill input is unavailable")
    payload = tmp_path / "build/payload"
    skill = payload / "workspace-template/skills/ppt-master"
    shutil.copytree(source / "scripts", skill / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    icon_root = skill / "templates/icons/tabler-outline"
    icon_root.mkdir(parents=True)
    svg = '<svg viewBox="0 0 24 24"><path d="M0 0L24 24" fill="currentColor"/></svg>'
    (icon_root / "home.svg").write_text(svg, encoding="utf-8")
    (icon_root / "unused.svg").write_text(svg, encoding="utf-8")
    (icon_root / "preview.svg").write_text(svg, encoding="utf-8")
    first = archives.archive_ppt_icons(payload)
    assert first["entries"] == 3
    assert list(icon_root.glob("*.svg")) == []
    assert archives.archive_ppt_icons(payload)["sha256"] == first["sha256"]
    project = tmp_path / "project"
    (project / "icons/tabler-outline").mkdir(parents=True)
    (project / "icons/tabler-outline/home.svg").write_text("custom", encoding="utf-8")
    probe = r'''
import ast, re, sys
from pathlib import Path
from xml.etree import ElementTree as ET
sys.path.insert(0, sys.argv[1])
from icon_sync import sync_icons
from svg_finalize.embed_icons import resolve_icon_path, extract_paths_from_icon
from svg_to_pptx.use_expander import expand_use_data_icons
from sugaragent_icon_archive import materialize_icon
scripts, project = Path(sys.argv[1]), Path(sys.argv[2])
icons = scripts.parent / 'templates/icons'
copied, missing = sync_icons(project, ['tabler-outline/home'], icons)
assert not missing and 'already in project' in copied[0]
assert (project / 'icons/tabler-outline/home.svg').read_text() == 'custom'
assert not (icons / 'tabler-outline/home.svg').exists()
icon, size = resolve_icon_path('tabler-outline/home', icons)
assert icon.is_file() and size == 24
assert extract_paths_from_icon(icon)[0]
root = ET.fromstring('<svg><use data-icon="tabler-outline/home" width="24" height="24"/></svg>')
assert expand_use_data_icons(root, icons) == 1
assert root.find('use') is None
assert not (icons / 'tabler-outline/unused.svg').exists()
# Exercise the real confirmation-preview reader without starting Flask/UI.
server = ast.parse((scripts / 'confirm_ui/server.py').read_text(encoding='utf-8'))
preview = next(item for item in server.body if isinstance(item, ast.FunctionDef) and item.name == '_icon_preview_svg')
namespace = {'_ICON_LIBRARY_DIR': icons, 'materialize_icon': materialize_icon, 're': re}
exec(compile(ast.Module(body=[preview], type_ignores=[]), 'confirm-preview', 'exec'), namespace)
assert '<path' in namespace['_icon_preview_svg']('tabler-outline', 'preview')
assert not (icons / 'tabler-outline/unused.svg').exists()
print('PPT_ARCHIVE_OK')
'''
    result = subprocess.run([sys.executable, "-B", "-c", probe, str(skill / "scripts"), str(project)],
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PPT_ARCHIVE_OK" in result.stdout


def test_builder_rejects_stale_or_expanded_payload(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is unavailable")
    payload, package, _ = sdk_fixture(tmp_path)
    info = {"schemaVersion": 1, "sdk": archives.archive_sdk(payload), "pptIcons": None}
    (payload / "runtime-archives.json").write_text(json.dumps(info), encoding="utf-8")
    script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { assertRuntimeArchives } = require(process.argv[1]);
const payload = process.argv[2];
assert.doesNotThrow(() => assertRuntimeArchives(payload));
fs.mkdirSync(path.join(payload, 'python/Lib/site-packages/lark_oapi'));
assert.throws(() => assertRuntimeArchives(payload), /SDK/);
fs.unlinkSync(path.join(payload, 'runtime-archives.json'));
assert.throws(() => assertRuntimeArchives(payload), /归档优化/);
'''
    result = subprocess.run([node, "-e", script, str(ROOT / "packaging/scripts/runtime-archives.cjs"), str(payload)],
                            capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_archive_cli_refuses_installed_user_runtime(tmp_path):
    payload = tmp_path / "build/payload"
    (payload / "python").mkdir(parents=True)
    (payload / "python/python.exe").touch()
    (payload / "app").mkdir()
    (payload / "app/main.py").touch()
    (payload / "workspace").mkdir()
    with pytest.raises(RuntimeError, match="Refusing"):
        archives.optimize_payload(payload)


def test_payload_cleanup_keeps_archive_bytecode_and_is_idempotent(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is unavailable")
    payload = tmp_path / "payload"
    package = payload / "python/Lib/site-packages/example"
    cache = package / "__pycache__"
    cache.mkdir(parents=True)
    (package / "module.py").write_text("value = 1\n", encoding="utf-8")
    (cache / "module.cpython-310.pyc").write_bytes(b"cache")
    with zipfile.ZipFile(package.parent / "sdk.zip", "w") as archive:
        archive.writestr("sdk/__init__.pyc", b"keep archived bytecode")
    before = (package.parent / "sdk.zip").read_bytes()
    script = r'''
const assert = require('node:assert/strict');
const { cleanupPyc, assertNoLooseBytecode } = require(process.argv[1]);
const root = process.argv[2];
assert.throws(() => assertNoLooseBytecode(root), /字节码/);
assert.equal(cleanupPyc(root).files, 1);
assertNoLooseBytecode(root);
assert.equal(cleanupPyc(root).files, 0);
'''
    result = subprocess.run([node, "-e", script, str(ROOT / "packaging/scripts/payload-bytecode.cjs"), str(payload)],
                            capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not cache.exists()
    assert (package / "module.py").is_file()
    assert (package.parent / "sdk.zip").read_bytes() == before


def test_cleanup_refuses_bytecode_only_modules_without_deleting_other_caches(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is unavailable")
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "normal.py").write_text("value = 1\n", encoding="utf-8")
    (payload / "normal.pyc").write_bytes(b"cache")
    (payload / "source_missing.pyc").write_bytes(b"bytecode-only module")
    script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { cleanupPyc } = require(process.argv[1]);
const root = process.argv[2];
assert.throws(() => cleanupPyc(root), /没有源码/);
assert.ok(fs.existsSync(path.join(root, 'normal.pyc')));
assert.ok(fs.existsSync(path.join(root, 'source_missing.pyc')));
'''
    result = subprocess.run([node, "-e", script, str(ROOT / "packaging/scripts/payload-bytecode.cjs"), str(payload)],
                            capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
