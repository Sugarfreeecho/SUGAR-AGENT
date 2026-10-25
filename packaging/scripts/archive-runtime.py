"""Compact desktop runtime resources after dependency installation, before NSIS."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import importlib.util
import json
import marshal
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import zipfile


PACKAGING = Path(__file__).resolve().parents[1]
PTH_NAME = "sugaragent-runtime-archives.pth"
PPT_PATCH_MARKER = "# SugarAgent desktop: archive-backed icons"


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _owned(payload: Path, path: Path) -> None:
    if not path.resolve().is_relative_to(payload.resolve()):
        raise RuntimeError(f"Resource path escapes the isolated payload: {path}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _files(root: Path) -> list[Path]:
    # Windows' embedded Python can lack the long-path-aware executable flag.
    root = Path("\\\\?\\" + str(root.resolve())) if os.name == "nt" else root
    return sorted((path for path in root.rglob("*") if path.is_file()), key=str)


def _entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    archive.writestr(info, data)


def _update_sdk_records(site: Path, target: Path, pth: Path) -> None:
    # pip must uninstall/upgrade the archive, rather than keep loading an old
    # SDK whose original loose files were already removed during preparation.
    for metadata in site.glob("lark_oapi-*.dist-info"):
        record = metadata / "RECORD"
        if not record.is_file():
            continue
        with record.open(newline="", encoding="utf-8") as stream:
            rows = [row for row in csv.reader(stream) if row and
                    not row[0].startswith("lark_oapi/") and row[0] not in (target.name, pth.name)]
        for path in (target, pth):
            digest = base64.urlsafe_b64encode(bytes.fromhex(_sha256(path))).rstrip(b"=").decode("ascii")
            rows.append([path.name, "sha256=" + digest, str(path.stat().st_size)])
        with record.open("w", newline="", encoding="utf-8") as stream:
            csv.writer(stream, lineterminator="\n").writerows(rows)


def archive_sdk(payload: Path) -> dict:
    site = payload / "python" / "Lib" / "site-packages"
    package = site / "lark_oapi"
    _owned(payload, site)
    _owned(payload, package)
    target = site / "lark_oapi.zip"
    if package.is_dir():
        files = _files(package)
        package_root = Path("\\\\?\\" + str(package.resolve())) if os.name == "nt" else package
        # Validate before replacing anything. Native extension modules must
        # remain on disk and cannot be loaded by zipimport.
        if any(path.suffix.lower() in {".pyd", ".dll", ".so"} for path in files):
            raise RuntimeError("lark_oapi now contains native modules; review the desktop archive layout")
        with tempfile.NamedTemporaryFile(dir=site, suffix=".zip", delete=False) as stream:
            temporary = Path(stream.name)
        try:
            with zipfile.ZipFile(temporary, "w", allowZip64=True) as archive:
                for path in files:
                    relative = path.relative_to(package_root)
                    if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
                        continue
                    name = "lark_oapi/" + relative.as_posix()
                    data = path.read_bytes()
                    _entry(archive, name, data)
                    if path.suffix == ".py":
                        code = compile(data, name, "exec", dont_inherit=True, optimize=0)
                        # PEP 552 unchecked hash bytecode, at zipimport's legacy
                        # module.pyc location. No 10,000-file compilation temp tree.
                        bytecode = (importlib.util.MAGIC_NUMBER + struct.pack("<I", 1)
                                    + importlib.util.source_hash(data) + marshal.dumps(code))
                        _entry(archive, name[:-3] + ".pyc", bytecode)
            with zipfile.ZipFile(temporary) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError("SDK archive checksum verification failed")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        # The caller passes an isolated payload, never the developer's Python.
        shutil.rmtree(package_root)
        replaced = len(files)
    elif target.is_file():
        replaced = None
    else:
        # lark-oapi is optional: Feishu remote control imports it lazily and the
        # desktop payload no longer bundles it. Nothing to archive.
        (site / PTH_NAME).unlink(missing_ok=True)
        return None
    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
        if ("lark_oapi/__init__.pyc" not in names or archive.testzip() is not None
                or archive.read("lark_oapi/__init__.pyc")[:4] != importlib.util.MAGIC_NUMBER):
            raise RuntimeError("Invalid or incompatible SDK archive; rebuild the payload dependencies")
    pth = site / PTH_NAME
    pth.write_text("lark_oapi.zip\n", encoding="utf-8")
    _update_sdk_records(site, target, pth)
    return {"path": target.relative_to(payload).as_posix(), "sha256": _sha256(target),
            "entries": len(names), "replacedFiles": replaced,
            "pythonCacheTag": sys.implementation.cache_tag}


def patch_ppt_readers(skill: Path) -> None:
    patches = {
        "scripts/icon_sync.py": [
            ('configure_utf8_stdio()\n', 'configure_utf8_stdio()\n\nfrom sugaragent_icon_archive import materialize_icon\n'),
            ('        src = global_dir / lib / f"{name}.svg"\n'
             '        dst = project_icons / lib / f"{name}.svg"\n',
             '        dst = project_icons / lib / f"{name}.svg"\n'
             '        if dst.is_file():\n'
             '            copied.append(f"{lib}/{name} (already in project)")\n'
             '            continue\n'
             '        src = materialize_icon(global_dir / lib / f"{name}.svg")\n'),
            ('(search: ls {_GLOBAL_ICONS_DIR}/{lib}/ | grep <keyword>)',
             '(search: python scripts/sugaragent_icon_archive.py list --library {lib} --query <keyword>)'),
        ],
        "scripts/svg_finalize/embed_icons.py": [
            ('configure_utf8_stdio()\n', 'configure_utf8_stdio()\n\nfrom sugaragent_icon_archive import materialize_icon\n'),
            ("icon_path = icons_dir / lib / f'{name}.svg'", "icon_path = materialize_icon(icons_dir / lib / f'{name}.svg')"),
            ("icon_path = icons_dir / 'chunk-filled' / f'{icon_name}.svg'", "icon_path = materialize_icon(icons_dir / 'chunk-filled' / f'{icon_name}.svg')"),
            ("icon_path = icons_dir / f'{icon_name}.svg'", "icon_path = materialize_icon(icons_dir / f'{icon_name}.svg')"),
        ],
        "scripts/confirm_ui/server.py": [
            ('configure_utf8_stdio()\n', 'configure_utf8_stdio()\n\nfrom sugaragent_icon_archive import materialize_icon\n'),
            ("icon_path = _ICON_LIBRARY_DIR / library / f'{name}.svg'", "icon_path = materialize_icon(_ICON_LIBRARY_DIR / library / f'{name}.svg')"),
        ],
    }
    # Check all source hooks before modifying any of them. Fail loudly when an
    # upstream skill changes rather than shipping an unusable icon library.
    pending = []
    for relative, replacements in patches.items():
        path = skill / relative
        source = path.read_text(encoding="utf-8")
        if PPT_PATCH_MARKER in source:
            if any(new not in source for _, new in replacements):
                raise RuntimeError(f"Incomplete archived-icon patch: {relative}")
            continue
        for old, new in replacements:
            if source.count(old) != 1:
                raise RuntimeError(f"PPT icon reader changed; review archive adaptation: {relative}: {old}")
            source = source.replace(old, new, 1)
        source += "\n" + PPT_PATCH_MARKER + "\n"
        pending.append((path, source))
    for path, source in pending:
        path.write_text(source, encoding="utf-8")
    shutil.copyfile(PACKAGING / "runtime" / "sugaragent_icon_archive.py",
                    skill / "scripts" / "sugaragent_icon_archive.py")
    guidance = ("\n" + PPT_PATCH_MARKER + "\n"
                "Desktop icon SVGs are bundled in templates/icons/icons.zip and extracted only when used.\n"
                "Search the complete offline library with `python scripts/sugaragent_icon_archive.py list "
                "--library tabler-outline --query home`; use icon_sync.py and the normal SVG/PPTX tools "
                "to load selected icons. Directory listings contain only previously used SVGs.\n")
    for relative in ("SKILL.md", "templates/icons/README.md"):
        path = skill / relative
        if path.is_file() and PPT_PATCH_MARKER not in path.read_text(encoding="utf-8"):
            with path.open("a", encoding="utf-8") as stream:
                stream.write(guidance)


def archive_ppt_icons(payload: Path) -> dict | None:
    skill = payload / "workspace-template" / "skills" / "ppt-master"
    if not skill.exists():
        return None
    _owned(payload, skill)
    root = skill / "templates" / "icons"
    _owned(payload, root)
    target = root / "icons.zip"
    index = root / "icon-archive.json"
    files = [path for path in _files(root) if path.suffix.lower() == ".svg"]
    root_long = Path("\\\\?\\" + str(root.resolve())) if os.name == "nt" else root
    patch_ppt_readers(skill)
    if files:
        entries = {}
        # Include already archived icons if this is a repeat adaptation after a
        # selected icon was materialized. Loose customizations take precedence.
        if target.is_file():
            with zipfile.ZipFile(target) as archive:
                entries.update((name, archive.read(name)) for name in archive.namelist())
        entries.update((path.relative_to(root_long).as_posix(), path.read_bytes()) for path in files)
        with tempfile.NamedTemporaryFile(dir=root, suffix=".zip", delete=False) as stream:
            temporary = Path(stream.name)
        try:
            with zipfile.ZipFile(temporary, "w", allowZip64=True) as archive:
                for name, data in sorted(entries.items()):
                    _entry(archive, name, data)
            with zipfile.ZipFile(temporary) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError("PPT icon archive checksum verification failed")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        _write_json(index, {"schemaVersion": 1, "sha256": _sha256(target), "entries": sorted(entries)})
        for path in files:
            path.unlink()
    elif not target.is_file() or not index.is_file():
        raise RuntimeError("Missing PPT icon SVG files or archive")
    data = json.loads(index.read_text(encoding="utf-8"))
    if data["sha256"] != _sha256(target):
        raise RuntimeError("PPT icon archive does not match its index")
    return {"path": target.relative_to(payload).as_posix(), "sha256": data["sha256"],
            "entries": len(data["entries"])}


def optimize_payload(payload: Path) -> dict:
    payload = payload.resolve()
    if not (payload / "python" / "python.exe").is_file() or not (payload / "app" / "main.py").is_file():
        raise RuntimeError("Expected an isolated desktop payload with python/python.exe and app/main.py")
    # Do not let this script compact the source checkout or an installed runtime.
    if (payload.name != "payload" or payload.parent.name != "build" or payload == PACKAGING.parent
            or any((payload / name).exists() for name in ("workspace", ".config", ".sugaragent"))):
        raise RuntimeError("Refusing to optimize a source checkout or a runtime containing user data")
    result = {"schemaVersion": 1, "sdk": archive_sdk(payload), "pptIcons": archive_ppt_icons(payload)}
    _write_json(payload / "runtime-archives.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(optimize_payload(args.payload), ensure_ascii=False))


if __name__ == "__main__":
    main()
