import asyncio
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


class _JsonRequest:
    def __init__(self, payload):
        self.payload = payload

    async def json(self):
        return self.payload


async def _render_response(response, range_value: str = ""):
    messages = []
    headers = []
    if range_value:
        headers.append((b"range", range_value.encode("ascii")))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/workspace-media",
        "raw_path": b"/api/workspace-media",
        "query_string": b"",
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "extensions": {},
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await response(scope, receive, send)
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    response_headers = {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in start["headers"]
    }
    return start["status"], response_headers, body


@pytest.mark.parametrize(
    ("name", "payload", "expected_type"),
    [
        ("preview.gif", b"GIF89a-animation", "image/gif"),
        ("sample.mp3", b"ID3-audio-data", "audio/mpeg"),
        ("sample.mp4", b"\x00\x00\x00\x18ftyp-video-data", "video/mp4"),
    ],
)
def test_workspace_media_serves_supported_bytes_inline(
    tmp_path, monkeypatch, name, payload, expected_type
):
    import webui

    workspace = tmp_path / "workspace"
    media_dir = workspace / "media files"
    media_dir.mkdir(parents=True)
    target = media_dir / name
    target.write_bytes(payload)
    monkeypatch.setattr(webui, "WORK_DIR", workspace)

    response = asyncio.run(webui.workspace_media(f"media%20files/{name}"))
    status, headers, body = asyncio.run(_render_response(response))

    assert status == 200
    assert headers["content-type"] == expected_type
    assert headers["cache-control"] == "no-store"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["content-disposition"].startswith("inline;")
    assert body == payload


def test_workspace_media_supports_byte_ranges(tmp_path, monkeypatch):
    import webui

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "clip.mp4"
    target.write_bytes(b"0123456789")
    monkeypatch.setattr(webui, "WORK_DIR", workspace)

    response = asyncio.run(webui.workspace_media("clip.mp4"))
    status, headers, body = asyncio.run(_render_response(response, "bytes=2-5"))

    assert status == 206
    assert headers["accept-ranges"] == "bytes"
    assert headers["content-range"] == "bytes 2-5/10"
    assert body == b"2345"


def test_workspace_media_rejects_missing_and_unsupported_files(tmp_path, monkeypatch):
    import webui

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "movie.avi").write_bytes(b"avi")
    monkeypatch.setattr(webui, "WORK_DIR", workspace)

    assert asyncio.run(webui.workspace_media("")).status_code == 400
    assert asyncio.run(webui.workspace_media("missing.mp3")).status_code == 404
    assert asyncio.run(webui.workspace_media("movie.avi")).status_code == 415


def test_workspace_image_alias_only_accepts_images(tmp_path, monkeypatch):
    import webui

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "preview.gif").write_bytes(b"GIF89a")
    (workspace / "sample.mp3").write_bytes(b"ID3")
    monkeypatch.setattr(webui, "WORK_DIR", workspace)

    image_response = asyncio.run(webui.workspace_image("preview.gif"))
    status, headers, body = asyncio.run(_render_response(image_response))
    assert status == 200
    assert headers["content-type"] == "image/gif"
    assert body == b"GIF89a"
    assert asyncio.run(webui.workspace_image("sample.mp3")).status_code == 415


def test_workspace_image_metadata_returns_raster_and_svg_dimensions(tmp_path, monkeypatch):
    from PIL import Image
    import webui

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    Image.new("RGB", (320, 180)).save(workspace / "preview.png")
    (workspace / "diagram.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360"></svg>',
        encoding="utf-8",
    )
    monkeypatch.setattr(webui, "WORK_DIR", workspace)

    response = asyncio.run(
        webui.workspace_image_metadata(
            _JsonRequest({"rels": ["preview.png", "diagram.svg", "missing.png"]})
        )
    )
    payload = json.loads(response.body)
    assert payload["ok"] is True
    by_rel = {item["rel"]: item for item in payload["images"]}
    assert (by_rel["preview.png"]["width"], by_rel["preview.png"]["height"]) == (320, 180)
    assert (by_rel["diagram.svg"]["width"], by_rel["diagram.svg"]["height"]) == (640, 360)
    assert "missing.png" not in by_rel
    assert response.headers["cache-control"] == "no-store"


def test_workspace_image_metadata_honors_exif_orientation(tmp_path, monkeypatch):
    from PIL import Image
    import webui

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (120, 80)).save(workspace / "rotated.jpg", exif=exif)
    monkeypatch.setattr(webui, "WORK_DIR", workspace)

    response = asyncio.run(
        webui.workspace_image_metadata(_JsonRequest({"rels": ["rotated.jpg"]}))
    )
    payload = json.loads(response.body)
    assert payload["images"][0]["width"] == 80
    assert payload["images"][0]["height"] == 120


def test_workspace_image_overwrite_with_same_size_changes_version(tmp_path, monkeypatch):
    import os
    from PIL import Image
    import webui

    monkeypatch.setattr(webui, "WORK_DIR", tmp_path)
    path = tmp_path / "preview.bmp"
    Image.new("RGB", (32, 24), "red").save(path)
    original = path.read_bytes()
    original_stat = path.stat()
    before = webui._workspace_image_metadata_item("preview.bmp")

    Image.new("RGB", (32, 24), "blue").save(path)
    os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns + 1_000_000_000))
    after = webui._workspace_image_metadata_item("preview.bmp")
    assert len(path.read_bytes()) == len(original)
    assert path.read_bytes() != original
    assert (before["width"], before["height"]) == (after["width"], after["height"])
    assert before["version"] != after["version"]

    response = asyncio.run(webui.workspace_media("preview.bmp"))
    status, headers, body = asyncio.run(_render_response(response))
    assert status == 200
    assert headers["cache-control"] == "no-store"
    assert body == path.read_bytes()
