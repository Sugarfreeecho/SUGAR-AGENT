"""会话导入：导出 zip / 会话目录 → 新会话（沿用原 id，冲突时换新 id 并改写自有引用）。"""
import asyncio
import io
import json
import zipfile
from pathlib import Path

from starlette.requests import Request


class _FakeRepository:
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir


class _FakeSessionManager:
    def __init__(self, sessions_dir: Path):
        self.repository = _FakeRepository(sessions_dir)

    def _resolve_session_path(self, session_id: str) -> Path:
        return self.repository.sessions_dir / session_id


SESSION_ID = "11111111-2222-3333-4444-555555555555"


def _write_session(root: Path, session_id: str, name: str = "示例会话") -> Path:
    session_dir = root / session_id
    (session_dir / "snapshots").mkdir(parents=True, exist_ok=True)
    (session_dir / "metadata.json").write_text(
        json.dumps(
            {
                "name": name,
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-02T00:00:00",
                "archived": True,
                "pinned": False,
                "active_run_id": "run-1",
                "interrupt_requested": True,
                "unread_result": True,
                "goal_review_pending": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (session_dir / "events.jsonl").write_text(
        json.dumps(
            {"schema_version": 1, "seq": 1, "type": "session_meta", "session_id": session_id, "payload": {"name": name}},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (session_dir / "snapshots" / "latest.json").write_text(
        json.dumps({"session_id": session_id, "revision": 1}),
        encoding="utf-8",
    )
    return session_dir


def _export_zip(monkeypatch, tmp_path, session_id=SESSION_ID, name="示例会话") -> Path:
    import webui

    source_root = tmp_path / "source"
    source_root.mkdir(parents=True, exist_ok=True)
    _write_session(source_root, session_id, name)
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(source_root))
    archive_path, download_name = webui._build_session_export_archive(session_id)
    assert download_name.endswith(".zip")
    return archive_path


def _json_payload(response) -> dict:
    return json.loads(response.body.decode("utf-8"))


def test_import_session_from_export_zip_keeps_original_id(monkeypatch, tmp_path):
    import webui

    archive_path = _export_zip(monkeypatch, tmp_path)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))
    try:
        result = webui._import_session_from(str(archive_path), "zip")

        assert result["id"] == SESSION_ID
        assert result["remapped"] is False
        imported = sessions_dir / SESSION_ID
        assert (imported / "events.jsonl").is_file()
        assert (imported / "snapshots" / "latest.json").is_file()
        meta = json.loads((imported / "metadata.json").read_text(encoding="utf-8"))
        assert meta["name"] == "示例会话"
        # 导入进来的是"死"会话：运行态字段清空、不再归档
        assert meta["active_run_id"] is None
        assert meta["interrupt_requested"] is False
        assert meta["unread_result"] is False
        assert meta["goal_review_pending"] is False
        assert meta["archived"] is False
        assert json.loads((imported / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])["session_id"] == SESSION_ID
    finally:
        archive_path.unlink(missing_ok=True)


def test_import_session_collision_imports_copy_with_new_id(monkeypatch, tmp_path):
    import webui

    archive_path = _export_zip(monkeypatch, tmp_path)
    sessions_dir = tmp_path / "sessions"
    (sessions_dir / SESSION_ID).mkdir(parents=True)
    (sessions_dir / SESSION_ID / "keep.txt").write_text("existing", encoding="utf-8")
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))
    try:
        result = webui._import_session_from(str(archive_path), "zip")

        assert result["id"] != SESSION_ID
        assert result["remapped"] is True
        assert result["idRewriteFiles"] >= 2  # events.jsonl + snapshots/latest.json
        imported = sessions_dir / result["id"]
        assert (imported / "events.jsonl").is_file()
        # 原会话没被动过；副本里的 id 已全部换成新 id
        assert (sessions_dir / SESSION_ID / "keep.txt").read_text(encoding="utf-8") == "existing"
        events_text = (imported / "events.jsonl").read_text(encoding="utf-8")
        assert result["id"] in events_text
        assert SESSION_ID not in events_text
        assert result["id"] in (imported / "snapshots" / "latest.json").read_text(encoding="utf-8")
        meta = json.loads((imported / "metadata.json").read_text(encoding="utf-8"))
        assert meta["name"] == "示例会话（导入）"
    finally:
        archive_path.unlink(missing_ok=True)


def test_import_session_from_directory_copies_without_touching_source(monkeypatch, tmp_path):
    import webui

    source_root = tmp_path / "downloaded"
    source_root.mkdir()
    _write_session(source_root, SESSION_ID, "文件夹导入")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))

    result = webui._import_session_from(str(source_root / SESSION_ID), "dir")

    assert result["id"] == SESSION_ID
    assert (source_root / SESSION_ID / "events.jsonl").is_file()  # 原目录原样保留
    assert (sessions_dir / SESSION_ID / "events.jsonl").is_file()


def test_import_session_from_parent_directory_finds_nested_session(monkeypatch, tmp_path):
    import webui

    source_root = tmp_path / "bundle"
    source_root.mkdir()
    _write_session(source_root, SESSION_ID, "嵌套导入")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))

    result = webui._import_session_from(str(source_root), "dir")

    assert result["id"] == SESSION_ID
    assert (sessions_dir / SESSION_ID / "metadata.json").is_file()


def test_import_session_rejects_directory_without_events(monkeypatch, tmp_path):
    import webui

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    empty = tmp_path / "not-a-session"
    empty.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))

    try:
        webui._import_session_from(str(empty), "dir")
        raise AssertionError("should reject a folder without events.jsonl")
    except ValueError as exc:
        assert "events.jsonl" in str(exc)


def test_import_session_rejects_paths_inside_sessions_dir(monkeypatch, tmp_path):
    import webui

    sessions_dir = tmp_path / "sessions"
    existing = _write_session(sessions_dir, SESSION_ID, "本机会话")
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))

    try:
        webui._import_session_from(str(existing), "dir")
        raise AssertionError("should reject importing from inside the sessions directory")
    except ValueError as exc:
        assert "会话目录内部" in str(exc)


def test_import_session_api_returns_session_payload(monkeypatch, tmp_path):
    import webui

    archive_path = _export_zip(monkeypatch, tmp_path)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))

    class _JsonRequest:
        async def json(self):
            return {"source": str(archive_path), "kind": "zip"}

    try:
        response = asyncio.run(webui.import_session_api(_JsonRequest()))
        payload = _json_payload(response)
        assert response.status_code == 200
        assert payload["ok"] is True
        assert payload["session"]["id"] == SESSION_ID
    finally:
        archive_path.unlink(missing_ok=True)


def test_import_session_api_reports_bad_source(monkeypatch, tmp_path):
    import webui

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))

    class _JsonRequest:
        async def json(self):
            return {"source": str(tmp_path / "missing.zip"), "kind": "zip"}

    response = asyncio.run(webui.import_session_api(_JsonRequest()))
    payload = _json_payload(response)
    assert response.status_code == 400
    assert payload["ok"] is False
    assert "路径不存在" in payload["error"]


def _multipart_request(fields, files) -> Request:
    boundary = "----myagent-session-import-test"
    body = b""
    for name, value in fields:
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        body += str(value).encode() + b"\r\n"
    for name, filename, content in files:
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        body += b"Content-Type: application/octet-stream\r\n\r\n"
        body += content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/sessions/import-upload",
        "headers": [
            (b"content-type", f"multipart/form-data; boundary={boundary}".encode()),
            (b"content-length", str(len(body)).encode()),
        ],
    }
    sent = {"done": False}

    async def receive():
        if sent["done"]:
            return {"type": "http.disconnect"}
        sent["done"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def _zip_bytes(session_id: str, name: str = "上传导入") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{session_id}/metadata.json", json.dumps({"name": name}, ensure_ascii=False))
        archive.writestr(
            f"{session_id}/events.jsonl",
            json.dumps({"seq": 1, "type": "session_meta", "session_id": session_id}, ensure_ascii=False) + "\n",
        )
    return buffer.getvalue()


def test_import_session_upload_accepts_zip(monkeypatch, tmp_path):
    import webui

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))

    request = _multipart_request([("kind", "zip")], [("files", "session-export.zip", _zip_bytes(SESSION_ID))])
    response = asyncio.run(webui.import_session_upload(request))
    payload = _json_payload(response)

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["session"]["id"] == SESSION_ID
    assert (sessions_dir / SESSION_ID / "events.jsonl").is_file()


def test_import_session_upload_accepts_dropped_folder(monkeypatch, tmp_path):
    import webui

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))

    session_id = "99999999-8888-7777-6666-555555555555"
    request = _multipart_request(
        [("kind", "dir")],
        [
            ("files", f"{session_id}/metadata.json", json.dumps({"name": "拖入的会话"}, ensure_ascii=False).encode()),
            (
                "files",
                f"{session_id}/events.jsonl",
                (json.dumps({"seq": 1, "type": "session_meta", "session_id": session_id}, ensure_ascii=False) + "\n").encode(),
            ),
        ],
    )
    response = asyncio.run(webui.import_session_upload(request))
    payload = _json_payload(response)

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["session"]["id"] == session_id
    assert (sessions_dir / session_id / "metadata.json").is_file()


def test_import_session_upload_rejects_folder_without_events(monkeypatch, tmp_path):
    import webui

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))

    request = _multipart_request([("kind", "dir")], [("files", "folder/readme.txt", b"nothing here")])
    response = asyncio.run(webui.import_session_upload(request))
    payload = _json_payload(response)

    assert response.status_code == 400
    assert payload["ok"] is False
    assert "events.jsonl" in payload["error"]


def test_import_session_routes_are_registered():
    import webui

    paths = {getattr(route, "path", "") for route in webui.fastapi_app.routes}
    assert "/api/sessions/import" in paths
    assert "/api/sessions/import-upload" in paths


def test_import_sessions_batch_reports_per_item_results(monkeypatch, tmp_path):
    from starlette.testclient import TestClient

    import webui

    archive_path = _export_zip(monkeypatch, tmp_path)
    folder_source = tmp_path / "downloaded"
    folder_source.mkdir()
    _write_session(folder_source, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "文件夹批次")
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))
    client = TestClient(webui.fastapi_app)
    try:
        response = client.post(
            "/api/sessions/import",
            json={
                "sources": [
                    str(archive_path),
                    str(folder_source / "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
                    str(tmp_path / "missing.zip"),
                ],
                "kind": "zip",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert [item["id"] for item in payload["imported"]] == [
            SESSION_ID,
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        ]
        assert len(payload["failed"]) == 1
        assert "路径不存在" in payload["failed"][0]["error"]
        assert (sessions_dir / SESSION_ID / "events.jsonl").is_file()
        assert (sessions_dir / "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" / "events.jsonl").is_file()
    finally:
        archive_path.unlink(missing_ok=True)


def test_import_sessions_batch_rejects_empty_and_oversized_lists(monkeypatch, tmp_path):
    from starlette.testclient import TestClient

    import webui

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))
    client = TestClient(webui.fastapi_app)

    empty = client.post("/api/sessions/import", json={"sources": ["  ", ""], "kind": "zip"})
    assert empty.status_code == 400
    assert empty.json()["error"] == "sources is required"

    too_many = client.post("/api/sessions/import", json={"sources": ["x"] * 201, "kind": "zip"})
    assert too_many.status_code == 400
    assert "200" in too_many.json()["error"]


def test_import_session_endpoints_answer_over_asgi(monkeypatch, tmp_path):
    """HTTP 层：两个路由都可达（不启动 lifespan，只走路由与处理器）。"""
    from starlette.testclient import TestClient

    import webui

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))
    client = TestClient(webui.fastapi_app)

    missing = client.post("/api/sessions/import", json={"source": str(tmp_path / "nope.zip"), "kind": "zip"})
    assert missing.status_code == 400
    assert "路径不存在" in missing.json()["error"]

    no_files = client.post("/api/sessions/import-upload", data={"kind": "zip"})
    assert no_files.status_code == 400
    assert no_files.json()["ok"] is False

    bad_kind = client.post("/api/sessions/import", json={"source": "x", "kind": "git"})
    assert bad_kind.status_code == 400
    assert "kind" in bad_kind.json()["error"]


def test_import_session_endpoint_imports_export_zip_over_asgi(monkeypatch, tmp_path):
    from starlette.testclient import TestClient

    import webui

    archive_path = _export_zip(monkeypatch, tmp_path)
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))
    client = TestClient(webui.fastapi_app)
    try:
        response = client.post("/api/sessions/import", json={"source": str(archive_path), "kind": "zip"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["session"]["id"] == SESSION_ID
        assert payload["session"]["name"] == "示例会话"
        assert (sessions_dir / SESSION_ID / "events.jsonl").is_file()
    finally:
        archive_path.unlink(missing_ok=True)


def test_import_session_upload_endpoint_accepts_multipart_over_asgi(monkeypatch, tmp_path):
    from starlette.testclient import TestClient

    import webui

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))
    client = TestClient(webui.fastapi_app)

    response = client.post(
        "/api/sessions/import-upload",
        data={"kind": "zip"},
        files={"files": ("session-export.zip", _zip_bytes(SESSION_ID), "application/zip")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["session"]["id"] == SESSION_ID
    assert (sessions_dir / SESSION_ID / "events.jsonl").is_file()
