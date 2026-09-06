import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from workspace_media_snapshots import snapshot_workspace_images


def _snapshot_path(markdown: str, work_dir: Path) -> Path:
    destination = markdown.split("](<", 1)[1].split(">", 1)[0]
    return work_dir / destination


def test_snapshot_keeps_old_bytes_when_source_name_is_reused(tmp_path):
    source = tmp_path / "preview.png"
    source.write_bytes(b"first-image")
    first_markdown = snapshot_workspace_images("![preview](preview.png)", tmp_path)
    first_snapshot = _snapshot_path(first_markdown, tmp_path)

    source.write_bytes(b"second-image")
    second_markdown = snapshot_workspace_images("![preview](preview.png)", tmp_path)
    second_snapshot = _snapshot_path(second_markdown, tmp_path)

    assert first_markdown != second_markdown
    assert first_snapshot.read_bytes() == b"first-image"
    assert second_snapshot.read_bytes() == b"second-image"
    assert source.read_bytes() == b"second-image"


def test_snapshot_is_content_addressed_and_preserves_markdown_title(tmp_path):
    source = tmp_path / "image with spaces.png"
    source.write_bytes(b"same-image")
    content = '![one]("image with spaces.png" "caption")\n![two](<image with spaces.png>)'

    rewritten = snapshot_workspace_images(content, tmp_path)
    lines = rewritten.splitlines()
    assert lines[0].endswith(' "caption")')
    assert _snapshot_path(lines[0], tmp_path) == _snapshot_path(lines[1], tmp_path)
    assert len(list((tmp_path / ".sugaragent" / "history-media").glob("*.png"))) == 1


def test_snapshot_skips_external_images_and_code_examples(tmp_path):
    (tmp_path / "local.png").write_bytes(b"local")
    content = (
        "![remote](https://example.com/image.png)\n"
        "`![inline](local.png)`\n"
        "```md\n![fenced](local.png)\n```\n"
        "![local](local.png)\n"
    )

    rewritten = snapshot_workspace_images(content, tmp_path)
    assert "![remote](https://example.com/image.png)" in rewritten
    assert "`![inline](local.png)`" in rewritten
    assert "![fenced](local.png)" in rewritten
    assert "![local](<.sugaragent/history-media/" in rewritten


def test_snapshot_leaves_missing_and_non_image_files_unchanged(tmp_path):
    (tmp_path / "report.txt").write_text("text", encoding="utf-8")
    content = "![missing](missing.png)\n![text](report.txt)"
    assert snapshot_workspace_images(content, tmp_path) == content
