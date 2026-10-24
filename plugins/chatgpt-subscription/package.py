"""Build a source-only installable ZIP, excluding all runtime credentials/caches."""
import argparse
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent


def build(output):
    files = [ROOT / item for item in (".myagent-plugin/plugin.json", "host.py", "requirements.txt", "README.md", "package.py")]
    for folder in ("chatgpt_plan", "web", "tests"):
        files.extend(path for path in (ROOT / folder).rglob("*") if path.is_file()
                     and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts
                     and path.suffix in {".py", ".html", ".js", ".css"})
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Write the package outside the plugin source directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, ROOT.name + "/" + path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert all(name.startswith("chatgpt-subscription/") for name in archive.namelist())
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    print(build(parser.parse_args().output))
