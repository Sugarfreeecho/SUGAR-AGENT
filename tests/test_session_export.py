import asyncio
from io import BytesIO
import json
import zipfile
from pathlib import Path


class _FakeRepository:
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir


class _FakeSessionManager:
    def __init__(self, sessions_dir: Path):
        self.repository = _FakeRepository(sessions_dir)

    def _resolve_session_path(self, session_id: str) -> Path:
        return self.repository.sessions_dir / session_id


class _FakeRenameSessionManager:
    def __init__(self):
        self.renames = []

    def set_session_name(self, session_id: str, name: str) -> None:
        self.renames.append((session_id, name))


def test_export_session_downloads_complete_session_directory(monkeypatch, tmp_path):
    import webui

    sessions_dir = tmp_path / "sessions"
    session_dir = sessions_dir / "session-1"
    (session_dir / "snapshots").mkdir(parents=True)
    (session_dir / "metadata.json").write_text(json.dumps({"name": "Example"}), encoding="utf-8")
    (session_dir / "snapshots" / "latest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))

    response = asyncio.run(webui.export_session("session-1"))
    archive_path = Path(response.path)
    try:
        assert response.media_type == "application/zip"
        assert response.filename == "session-session-1.zip"
        with zipfile.ZipFile(archive_path) as archive:
            assert set(archive.namelist()) >= {
                "session-1/",
                "session-1/metadata.json",
                "session-1/snapshots/latest.json",
            }
    finally:
        archive_path.unlink(missing_ok=True)


def test_export_session_rejects_missing_directory(monkeypatch, tmp_path):
    import webui

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))

    response = asyncio.run(webui.export_session("missing"))
    assert response.status_code == 404


def test_export_download_ignores_quoted_hashes_and_keeps_real_images(monkeypatch, tmp_path):
    from PIL import Image
    from starlette.testclient import TestClient

    import webui
    from attachments import LocalAttachmentStore, SaveImageAttachment
    from attachments.lifecycle import collect_image_references, collect_references, import_bundle

    store = LocalAttachmentStore(tmp_path / "source")
    image = BytesIO()
    Image.new("RGB", (8, 8), "red").save(image, format="PNG")
    ref = store.save_images_sync([SaveImageAttachment(image.getvalue(), "image/png")])[0]
    quoted_hash = "sha256:" + "f" * 64
    session_dir = tmp_path / "sessions" / "session-1"
    (session_dir / "snapshots").mkdir(parents=True)
    event = {"content": [
        {"type": "image", "attachment": ref},
        {"type": "text", "text": f"Example identifier: {quoted_hash}"},
    ]}
    (session_dir / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
    (session_dir / "snapshots" / "latest.json").write_text(json.dumps(event), encoding="utf-8")
    (session_dir / "notes.md").write_text(quoted_hash, encoding="utf-8")
    # Conservative GC still protects quoted hashes; exports only require real refs.
    assert collect_references([session_dir]) == {ref["attachmentId"], quoted_hash}
    assert collect_image_references([session_dir]) == {ref["attachmentId"]}
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(session_dir.parent))
    monkeypatch.setattr(webui, "get_attachment_store", lambda _: store)
    monkeypatch.setattr(webui, "_is_configured", lambda: True)
    built_paths = []
    build_archive = webui._build_session_export_archive

    def build(session_id):
        path, name = build_archive(session_id)
        built_paths.append(path)
        return path, name

    monkeypatch.setattr(webui, "_build_session_export_archive", build)
    response = TestClient(webui.fastapi_app).get("/sessions/session-1/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert 'filename="session-session-1.zip"' in response.headers["content-disposition"]
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        assert json.loads(archive.read("session-1/events.jsonl")) == event
        manifest = json.loads(archive.read("attachments/manifest.json"))
        assert [item["ref"]["attachmentId"] for item in manifest["images"]] == [ref["attachmentId"]]
    restored = LocalAttachmentStore(tmp_path / "restored")
    assert import_bundle(restored, BytesIO(response.content)) == [manifest["images"][0]["ref"]]
    assert restored.read_image_sync(ref).data == store.read_image_sync(ref).data
    assert len(built_paths) == 1 and not built_paths[0].exists()


def test_export_missing_real_image_reports_error_without_leaking_archive(monkeypatch, tmp_path):
    import webui
    from attachments import LocalAttachmentStore

    session_dir = tmp_path / "sessions" / "session-1"
    session_dir.mkdir(parents=True)
    ref = {"attachmentId": "sha256:" + "f" * 64, "mediaType": "image/png",
           "bytes": 100, "width": 8, "height": 8}
    (session_dir / "events.jsonl").write_text(json.dumps({"content": [
        {"type": "image", "attachment": ref},
    ]}), encoding="utf-8")
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(session_dir.parent))
    monkeypatch.setattr(webui, "get_attachment_store", lambda _: LocalAttachmentStore(tmp_path))
    created = []
    mkstemp = webui.tempfile.mkstemp

    def temporary_archive(**kwargs):
        fd, name = mkstemp(dir=tmp_path, **kwargs)
        created.append(Path(name))
        return fd, name

    monkeypatch.setattr(webui.tempfile, "mkstemp", temporary_archive)
    response = asyncio.run(webui.export_session("session-1"))
    assert response.status_code == 400
    assert "Attachment missing or corrupt" in json.loads(response.body)["error"]
    assert len(created) == 1 and not created[0].exists()


def test_rename_session_normalizes_name_and_rejects_blank(monkeypatch):
    import webui

    fake = _FakeRenameSessionManager()
    monkeypatch.setattr(webui, "session_manager", fake)

    blank = asyncio.run(webui.rename_session("session-1", "   "))
    saved = asyncio.run(webui.rename_session("session-1", "  Renamed session  "))

    assert blank.status_code == 400
    assert saved.status_code == 200
    saved_payload = json.loads(saved.body.decode("utf-8"))
    assert saved_payload["status"] == "ok"
    assert isinstance(saved_payload["state_revision"], int)
    assert saved_payload["state_revision"] > 0
    assert fake.renames == [("session-1", "Renamed session")]
