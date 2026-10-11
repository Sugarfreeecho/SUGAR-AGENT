"""Build an offline Windows x64 package; never include data/ or user sessions."""
import hashlib
import argparse
import importlib.metadata
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        raise SystemExit("Build on Windows x64")
    import PyInstaller
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "versions/manifest.json").read_text(encoding="utf-8"))
    for v in manifest["versions"]:
        for kind in ("js", "css"):
            asset = ROOT / "versions" / v["version"] / "site" / v[kind].lstrip("/")
            assert hashlib.sha256(asset.read_bytes()).hexdigest() == v[kind + "_sha256"], asset
    dest = args.output.resolve() / "SessionReplay"
    if dest.exists():
        raise SystemExit("Output already exists; choose a clean output directory before rebuilding")
    with tempfile.TemporaryDirectory(prefix="session-replay-build-") as work:
        work = Path(work)
        subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
                        "--name", "SessionReplay", "--distpath", str(work / "dist"),
                        "--workpath", str(work / "build"), "--specpath", str(work), str(ROOT / "server.py")], check=True)
        shutil.copytree(work / "dist/SessionReplay", dest)
    for name in ("web", "versions"):
        shutil.copytree(ROOT / name, dest / name)
    for name in ("README.md", "start.cmd", "启动.cmd"):
        data = (ROOT / name).read_text(encoding="utf-8")
        (dest / name).write_bytes(data.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
    source = dest / "source"
    source.mkdir()
    for name in ("server.py", "session_data.py", "playback.py", "experiments.py", "prepare_experiments.cjs", "build_portable.py"):
        shutil.copy2(ROOT / name, source / name)
    shutil.copytree(ROOT / "tests", source / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    licenses = dest / "licenses"
    licenses.mkdir()
    pylicense = Path(sys.base_prefix) / "LICENSE.txt"
    if not pylicense.exists():
        pylicense = Path(sys.base_prefix) / "LICENSE"
    if pylicense.is_file():
        shutil.copy2(pylicense, licenses / "Python-LICENSE.txt")
    distribution = importlib.metadata.distribution("pyinstaller")
    for file in distribution.files or []:
        if file.name.lower() in {"copying.txt", "license", "license.txt", "copying"}:
            shutil.copy2(distribution.locate_file(file), licenses / ("PyInstaller-" + file.name))
    (licenses / "THIRD-PARTY-NOTICES.txt").write_text(
        "Python runtime: Python Software Foundation license.\n"
        "PyInstaller bootloader: GPL with exception permitting bundled application distribution.\n"
        "Original SugarAgent frontend resources are included from the owner's supplied backups.\n"
        "Frontend dependency versions and package notices: source/frontend-package.json.\n", encoding="utf-8")
    package_json = ROOT.parents[1] / "frontend/package.json"
    if package_json.is_file():
        shutil.copy2(package_json, source / "frontend-package.json")
    node_modules = ROOT.parents[1] / "frontend/node_modules"
    if node_modules.is_dir():
        for path in node_modules.rglob("*"):
            if path.is_file() and path.name.lower().split(".")[0] in {"license", "copying", "notice"}:
                target = licenses / "frontend" / path.relative_to(node_modules)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
    archive = dest.parent / "SessionReplay-Windows-x64.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(dest.rglob("*")):
            if path.is_file():
                assert "data" not in path.relative_to(dest).parts
                z.write(path, "SessionReplay/" + path.relative_to(dest).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(digest + "  " + archive.name + "\n", encoding="ascii")
    print(json.dumps({"zip": str(archive), "bytes": archive.stat().st_size, "sha256": digest}))


if __name__ == "__main__":
    main()
