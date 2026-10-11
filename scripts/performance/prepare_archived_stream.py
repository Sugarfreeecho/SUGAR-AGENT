"""Extract archived frontend assets into a temporary, isolated replay site."""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVES = [
    Path(r"D:\AI\AI Agent\SugarAgent Version\version\20260930.zip"),
    *(ROOT / f"202610{day}.zip" for day in ("03", "04", "07", "09")),
]


def file_sha256(file):
    digest = hashlib.sha256()
    with file.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    work = Path(tempfile.mkdtemp(prefix="archived-stream-replay-"))
    versions = []
    for archive in ARCHIVES:
        version = archive.stem
        target = work / version
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
            index = next(n for n in names if n.replace("\\", "/").endswith("app/templates/dist/index.html"))
            dist_prefix = index.rsplit("index.html", 1)[0]
            project_prefix = dist_prefix.rsplit("app/templates/dist/", 1)[0]
            selected = []
            for entry in zf.infolist():
                name = entry.filename.replace("\\", "/")
                if entry.is_dir():
                    continue
                if name.startswith(dist_prefix):
                    relative = "site/" + name[len(dist_prefix):]
                elif name.startswith(project_prefix + "plugins/") and "/web/" in name:
                    relative = name[len(project_prefix):]
                elif name.startswith(project_prefix + "app/templates/static/"):
                    relative = "static/" + name.split("app/templates/static/", 1)[1]
                elif name.startswith(project_prefix + "frontend/src/"):
                    relative = "source/" + name.split("frontend/src/", 1)[1]
                else:
                    continue
                dest = target / relative
                resolved = dest.resolve()
                if not resolved.is_relative_to(target.resolve()):
                    raise ValueError("Archive path escapes diagnostic directory")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(entry))
                selected.append(relative)
            html = (target / "site/index.html").read_text(encoding="utf-8")
            js = re.search(r'src="(/assets/main-[^"]+\.js)"', html).group(1)
            css = re.search(r'href="(/assets/main-[^"]+\.css)"', html).group(1)
            versions.append({
                "version": version, "archive": str(archive), "archive_sha256": file_sha256(archive),
                "directory": str(target), "js": js, "css": css,
                "js_sha256": hashlib.sha256((target / "site" / js.lstrip("/")).read_bytes()).hexdigest(),
                "css_sha256": hashlib.sha256((target / "site" / css.lstrip("/")).read_bytes()).hexdigest(),
                "source_present": any(n.startswith("source/") for n in selected),
                "plugin_present": (target / "plugins/change-review/web/change-review.js").exists(),
            })
    # This is a tokenizer-labelled replay corpus, not an actual LLM invocation.
    import tiktoken
    encoding = tiktoken.get_encoding("cl100k_base")
    unit = "执行过程：检查文件与依赖，读取代码后比较结果。The stream resumes after a brief pause, wraps to the next line, and continues at a steady rate.\n"
    text = unit * 12000
    tokens = encoding.encode(text)
    corpus = {}
    for size in (8000, 128000):
        value = encoding.decode(tokens[:size])
        corpus[str(size)] = {"text": value, "token_count": len(encoding.encode(value)), "characters": len(value)}
    (work / "corpus.json").write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    manifest = {"work": str(work), "tokenizer": "cl100k_base", "versions": versions}
    (work / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    pointer = ROOT / ".git/archived-stream-replay-work.json"
    pointer.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
