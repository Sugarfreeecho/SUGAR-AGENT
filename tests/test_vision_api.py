import asyncio
import base64
import json
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from attachments import LocalAttachmentStore, SaveImageAttachment, AttachmentError
from attachments.access import require_attachment
from attachments.admission import AdmissionContext, admit_content
from attachments.api import register_attachment_api
from attachments.lifecycle import add_bundle, garbage_collect, import_bundle
from attachments.locking import attachment_lock
from attachments.registry import AttachmentRegistry
from attachments.remote import RemoteImagePolicy, download_image, resolve_target
from attachments.types import ImageRequestPolicy
from remote_control.store import DevicePrincipal
from vision_api import VisionJobs, register_vision_api


def image_bytes(color="red"):
    out = BytesIO()
    Image.new("RGB", (80, 60), color).save(out, "PNG")
    return out.getvalue()


@pytest.fixture
def store(tmp_path):
    return LocalAttachmentStore(tmp_path)


def save(store, color="red"):
    return store.save_images_sync([SaveImageAttachment(image_bytes(color), "image/png")])[0]


ADMIN = DevicePrincipal("local", "Local", frozenset({"admin"}))
ALICE = DevicePrincipal("alice", "Alice", frozenset({"read", "write"}))
BOB = DevicePrincipal("bob", "Bob", frozenset({"read", "write"}))


class Transport:
    def __init__(self, answer="A red rectangle", gate=None):
        self.calls = []
        self.answer = answer
        self.gate = gate
        self.entered = threading.Event()
        self.closed = threading.Event()

    def stream_completion(self, **kwargs):
        self.calls.append(kwargs)
        self.entered.set()
        try:
            if self.gate:
                assert self.gate.wait(5)
            yield SimpleNamespace(kind="content_delta", text=self.answer, usage=None)
            yield SimpleNamespace(kind="usage", usage={"input_tokens": 12, "output_tokens": 4})
        finally:
            self.closed.set()


def jobs_for(tmp_path, transport, modalities=None, policy=None):
    return VisionJobs(tmp_path, lambda _: {"profile_id": "vision", "model": "test",
                     "input_modalities": modalities if modalities is not None else ["text", "image"],
                     "image_request_policy": policy or {}, "transport": transport})


def payload(ref, identity="r1", **extra):
    return {"requestId": identity, "modelProfileId": "vision", "prompt": "Describe", "images": [{"attachmentId": ref["attachmentId"]}], **extra}


def finish(jobs, identity="r1", owner="local"):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        result = jobs.get(owner, identity)
        if result["status"] in {"completed", "failed", "cancelled"}:
            # A final state is committed just before its final SSE event.
            for _ in range(100):
                if any(event["type"] == result["status"] for _, event in jobs.events(owner, identity, 0)):
                    return result
                time.sleep(.01)
            return result
        time.sleep(.01)
    pytest.fail("Vision worker did not finish")


def test_values_are_pure_and_nested_admission_is_atomic(store, monkeypatch):
    from agent_messages import UserMessage, ToolMessage
    from runtime_v2.event_schema import RuntimeEvent
    raw = [{"type": "image", "mediaType": "image/png", "data": base64.b64encode(image_bytes()).decode()}]
    user, tool = UserMessage(raw), ToolMessage(raw, tool_call_id="c1")
    event = RuntimeEvent.from_dict({"seq": 1, "type": "model_tool", "session_id": "s", "payload": {"content": raw}})
    assert user.content == tool.content == event.payload["content"] == raw
    assert not store.root.exists()
    nested = [{"type": "tool_result", "content": raw}, {"type": "tool_result", "content": [{"type": "image", "data": "bad"}]}]
    with pytest.raises(AttachmentError):
        admit_content(nested, AdmissionContext(store), strict=True)
    assert not list(store.root.rglob("image.json"))
    assert "entire image batch rejected" in json.dumps(admit_content(nested, AdmissionContext(store)))


def test_remote_ingestion_freezes_url_and_modes(store, monkeypatch):
    import attachments.admission as admission
    calls = []
    def fetch(url, *_):
        calls.append(url)
        return SaveImageAttachment(image_bytes(), "image/png")
    monkeypatch.setattr(admission, "download_image", fetch)
    source = "Inspect ![picture](https://example.com/image?id=1)"
    admitted = admit_content(source, AdmissionContext(store), scan_remote=True, strict=True)
    ref = admitted[-1]["attachment"]
    assert len(calls) == 1
    assert admit_content(admitted, AdmissionContext(store), scan_remote=True, strict=True) == admitted
    assert len(calls) == 1 and store.read_image_sync(ref)
    for mode, kind in [("passthrough", "image_url"), ("disabled", "text")]:
        result = admit_content(source, AdmissionContext(store, RemoteImagePolicy(mode=mode)), scan_remote=True)
        assert result[-1]["type"] == kind
    assert len(calls) == 1


@pytest.mark.parametrize("addresses", [["127.0.0.1"], ["10.0.0.1"], ["::1"], ["169.254.169.254"], ["8.8.8.8", "192.168.1.1"]])
def test_remote_blocks_private_or_mixed_dns(addresses, monkeypatch):
    monkeypatch.setattr("attachments.remote.socket.getaddrinfo", lambda *a, **k: [(0, 0, 0, "", (ip, 443)) for ip in addresses])
    with pytest.raises(AttachmentError) as exc:
        resolve_target("https://example.com/photo.png", RemoteImagePolicy())
    assert exc.value.code == "REMOTE_IMAGE_BLOCKED"


def test_remote_real_http_redirect_limits_and_type(store):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/image")
                self.end_headers()
                return
            body = image_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html" if self.path == "/html" else "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    policy = RemoteImagePolicy(allowed_hosts=("127.0.0.1",))
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        assert download_image(url + "/redirect", store.limits, policy).data == image_bytes()
        for suffix, limits, chosen, code in [
            ("/html", store.limits, policy, "UNSUPPORTED_IMAGE_TYPE"),
            ("/image", replace(store.limits, max_image_bytes=1), policy, "IMAGES_TOO_LARGE"),
            ("/redirect", store.limits, replace(policy, redirects=0), "REMOTE_IMAGE_UNAVAILABLE"),
        ]:
            with pytest.raises(AttachmentError) as exc:
                download_image(url + suffix, limits, chosen)
            assert exc.value.code == code
    finally:
        server.shutdown()
        server.server_close()


def test_acl_gc_queue_pins_and_archive_roundtrip(store, tmp_path):
    ref, unused = save(store), save(store, "blue")
    registry = AttachmentRegistry(store)
    registry.grant(ALICE.device_id, [ref["attachmentId"]], lease_seconds=0)
    with pytest.raises(HTTPException) as exc:
        require_attachment(store, BOB, ref["attachmentId"])
    assert exc.value.status_code == 404
    registry.pin("alice", "queue:q1", [ref["attachmentId"]])
    dry = garbage_collect(store, [], grace_seconds=0)
    assert [item["attachmentId"] for item in dry["candidates"]] == [unused["attachmentId"]]
    assert store.read_image_sync(unused)
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as output:
        add_bundle(output, store, [ref["attachmentId"]])
    second = LocalAttachmentStore(tmp_path / "restore")
    restored = import_bundle(second, BytesIO(archive.getvalue()))
    assert restored == [store.ref_by_id(ref["attachmentId"])]
    assert second.read_image_sync(ref).data == store.read_image_sync(ref).data
    assert garbage_collect(store, [], dry_run=False, grace_seconds=0)["removed"] == [unused["attachmentId"]]
    registry.pin("alice", "queue:q1", [])
    assert garbage_collect(store, [], dry_run=False, grace_seconds=0)["removed"] == [ref["attachmentId"]]


def test_bundle_rejects_traversal_without_partial_import(store):
    ref = save(store)
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("attachments/manifest.json", json.dumps({"version": 1, "images": [{"ref": ref, "path": "../../outside.jpg"}]}))
    with pytest.raises(AttachmentError, match="bundle path"):
        import_bundle(store, BytesIO(archive.getvalue()))


@pytest.mark.parametrize("manifest", [[], {"version": 1, "images": [None]}, {"version": 1, "images": [{"ref": {"attachmentId": []}}]}])
def test_bundle_rejects_malformed_manifest(store, manifest):
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("attachments/manifest.json", json.dumps(manifest))
    with pytest.raises(AttachmentError):
        import_bundle(store, BytesIO(archive.getvalue()))


def test_bundle_restores_missing_image_beside_existing_metadata(store):
    ref = save(store)
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as output:
        add_bundle(output, store, [ref["attachmentId"]])
    path = Path(store.image_host_path(ref))
    path.chmod(0o600)
    path.unlink()
    import_bundle(store, BytesIO(archive.getvalue()))
    assert store.read_image_sync(ref).data


def test_cache_quota_keeps_lock_files_and_source(store, monkeypatch):
    ref = save(store)
    first = store.read_request_image_sync(ref, ImageRequestPolicy(400, 1000))
    lock_files = list((store.cache_root / ".locks").iterdir())
    monkeypatch.setenv("ATTACHMENT_CACHE_MAX_BYTES", "1000")
    store.read_request_image_sync(ref, ImageRequestPolicy(200, 1000))
    assert all(p.exists() for p in lock_files)
    assert store.read_image_sync(ref)
    assert store.read_request_image_sync(ref, ImageRequestPolicy(400, 1000)).data == first.data
    with attachment_lock(store.root.parent, "catalog"):
        with attachment_lock(store.root.parent, "catalog"):
            pass


def test_process_locks_coordinate_independent_writers(tmp_path):
    import subprocess
    script = tmp_path / "writer.py"
    script.write_text('''import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from attachments.locking import attachment_lock
root = Path(sys.argv[2])
for _ in range(20):
    with attachment_lock(root, "counter"):
        path = root / "counter.txt"
        value = int(path.read_text()) if path.exists() else 0
        time.sleep(.001)
        path.write_text(str(value + 1))
''', encoding="utf-8")
    workers = [subprocess.Popen([sys.executable, str(script), str(Path(__file__).resolve().parents[1] / "app"), str(tmp_path)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
    try:
        for worker in workers:
            _, error = worker.communicate(timeout=20)
            assert worker.returncode == 0, error.decode(errors="replace")
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.kill()
                worker.wait()
    assert (tmp_path / "counter.txt").read_text() == "80"


def test_remote_dns_deadline_and_redirect_revalidation(store, monkeypatch):
    import attachments.remote as remote
    def slow_dns(*args, **kwargs):
        time.sleep(.1)
        return [(0, 0, 0, "", ("8.8.8.8", 443))]
    monkeypatch.setattr(remote.socket, "getaddrinfo", slow_dns)
    with pytest.raises(AttachmentError) as exc:
        resolve_target("https://example.com/a.png", RemoteImagePolicy(timeout=.01))
    assert exc.value.code == "REMOTE_IMAGE_TIMEOUT"
    monkeypatch.setattr(remote.socket, "getaddrinfo", lambda host, *a, **k: [(0, 0, 0, "", ("127.0.0.1" if host == "internal" else "8.8.8.8", 80))])
    opened = []
    def fake_open(url, policy, timeout):
        resolve_target(url, policy)
        opened.append(url)
        return SimpleNamespace(close=lambda: None), SimpleNamespace(status=302, close=lambda: None, getheader=lambda key: "http://internal/private.png")
    monkeypatch.setattr(remote, "_open", fake_open)
    with pytest.raises(AttachmentError) as exc:
        download_image("https://example.com/a.png", store.limits)
    assert exc.value.code == "REMOTE_IMAGE_BLOCKED" and len(opened) == 1


def test_concurrent_idempotency_owner_isolation_and_retained_pins(store, tmp_path):
    ref = save(store)
    gate = threading.Event()
    transport = Transport(gate=gate)
    jobs = jobs_for(tmp_path, transport)
    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            assert list(pool.map(lambda _: jobs.start(ADMIN, payload(ref)), range(6))) == ["r1"] * 6
        assert transport.entered.wait(5)
        assert len(transport.calls) == 1
        with pytest.raises(HTTPException) as exc:
            jobs.start(ADMIN, payload(ref, prompt="different"))
        assert exc.value.status_code == 409
        with pytest.raises(HTTPException) as exc:
            jobs.get("bob", "r1")
        assert exc.value.status_code == 404
    finally:
        gate.set()
    result = finish(jobs)
    assert result["status"] == "completed" and result["images"][0]["state"] == "sent"
    assert result["usage"]["input_tokens"] == 12
    assert "base64" not in json.dumps(result)
    wire = transport.calls[0]["messages"][0]["content"]
    assert wire[-1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    jobs.candidate_resolver = lambda _: pytest.fail("Idempotent replay must not resolve the provider again")
    assert jobs.start(ADMIN, payload(ref, stream=True)) == "r1"
    with AttachmentRegistry(store).connection() as db:
        assert db.execute("SELECT count(*) FROM pins WHERE scope='vision:r1'").fetchone()[0] == 1
    assert jobs.prune("local", "r1")["deleted"]
    with AttachmentRegistry(store).connection() as db:
        assert db.execute("SELECT count(*) FROM pins WHERE scope='vision:r1'").fetchone()[0] == 0


def test_cancel_waits_for_worker_and_closes_stream(store, tmp_path, monkeypatch):
    ref = save(store)
    gate = threading.Event()
    transport = Transport(gate=gate)
    jobs = jobs_for(tmp_path, transport)
    monkeypatch.setenv("VISION_MAX_CONCURRENT_REQUESTS", "1")
    jobs.start(ADMIN, payload(ref))
    assert transport.entered.wait(5)
    try:
        with pytest.raises(HTTPException) as exc:
            jobs.start(ADMIN, payload(ref, identity="r2"))
        assert exc.value.status_code == 429
        cancelled = jobs.cancel("local", "r1")
        assert cancelled["cancellationRequested"] and cancelled["status"] == "running"
        with pytest.raises(HTTPException):
            jobs.prune("local", "r1")
    finally:
        gate.set()
    assert finish(jobs)["status"] == "cancelled"
    assert transport.closed.wait(1)


@pytest.mark.parametrize("answer,schema,status", [('{"color":"red"}', {"type": "object", "required": ["color"]}, "completed"),
    ('{"color":"red"}', {"type": "integer"}, "failed"), ('not JSON', {"type": "object"}, "failed")])
def test_schema_output_validation(store, tmp_path, answer, schema, status):
    jobs = jobs_for(tmp_path, Transport(answer))
    jobs.start(ADMIN, payload(save(store), output={"format": "json_schema", "schema": schema}))
    result = finish(jobs)
    assert result["status"] == status
    if status == "failed":
        assert result["error"]["code"] == "VISION_OUTPUT_INVALID"
    else:
        assert result["structured"] == {"color": "red"}


@pytest.mark.parametrize("modalities,policy,state", [(["text"], {}, "omitted_capability"), (["image"], {"maxImagesPerRequest": 0}, "omitted_budget")])
def test_no_images_does_not_bill_a_text_only_request(store, tmp_path, modalities, policy, state):
    transport = Transport()
    jobs = jobs_for(tmp_path, transport, modalities, policy)
    jobs.start(ADMIN, payload(save(store)))
    result = finish(jobs)
    assert result["error"]["code"] == "VISION_NO_IMAGES"
    assert result["images"][0]["state"] == state
    assert not transport.calls


def test_http_api_sse_resume_json_limits_and_bundle_endpoints(store, tmp_path):
    ref = save(store)
    transport = Transport()
    app = FastAPI()
    register_vision_api(app, tmp_path, jobs_for(tmp_path, transport).candidate_resolver, lambda: None)
    register_attachment_api(app, tmp_path, lambda: None)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1234)), base_url="http://localhost") as client:
            response = await client.post("/api/vision/analyze", json=payload(ref, stream=True))
            assert response.status_code == 200
            assert "event: completed" in response.text and "event: image_prepared" in response.text
            response = await client.get("/api/vision/requests/r1/events?after=1")
            assert "event: accepted" not in response.text and "event: completed" in response.text
            assert (await client.post("/api/vision/analyze", content=b"x" * (256 * 1024 + 1))).status_code == 413
            assert (await client.post("/api/vision/analyze", json=payload(ref), headers={"Origin": "https://evil.example"})).status_code == 403
            response = await client.post("/api/attachments/export", json={"attachmentIds": [ref["attachmentId"]]})
            assert response.status_code == 200
            restored = await client.post("/api/attachments/import", content=response.content, headers={"Content-Type": "application/zip"})
            assert restored.status_code == 200 and restored.json()["images"][0]["attachmentId"] == ref["attachmentId"]
            assert (await client.delete("/api/vision/requests/r1/history")).json()["deleted"]
    asyncio.run(run())


def test_remote_http_requires_device_and_attachment_grant(store, tmp_path):
    ref = save(store)
    AttachmentRegistry(store).grant("alice", [ref["attachmentId"]])
    gateway = SimpleNamespace(config=SimpleNamespace(enabled=True, bootstrap_token="", allowed_origins=()),
                              store=SimpleNamespace(authenticate_device=lambda token: {"alice-token": ALICE, "bob-token": BOB}.get(token)))
    app = FastAPI()
    register_vision_api(app, tmp_path, jobs_for(tmp_path, Transport()).candidate_resolver, lambda: gateway)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("192.0.2.1", 1234)), base_url="http://myagent") as client:
            assert (await client.post("/api/vision/analyze", json=payload(ref))).status_code == 401
            assert (await client.post("/api/vision/analyze", json=payload(ref), headers={"Authorization": "Bearer bob-token"})).status_code == 404
            result = await client.post("/api/vision/analyze", json=payload(ref), headers={"Authorization": "Bearer alice-token"})
            assert result.status_code == 200 and result.json()["status"] == "completed"
            assert (await client.get("/api/vision/requests/r1", headers={"Authorization": "Bearer bob-token"})).status_code == 404
            assert (await client.get("/api/vision/metrics", headers={"Authorization": "Bearer alice-token"})).status_code == 403
    asyncio.run(run())


@pytest.mark.parametrize("protocol", ["chat", "responses"])
def test_sdk_stream_closed_when_consumer_cancels(protocol):
    from llm.transport import OpenAICompatibleTransport, OpenAIResponsesTransport
    class Stream:
        closed = False
        def __iter__(self):
            if protocol == "chat":
                yield {"choices": [{"delta": {"content": "hello"}}]}
            else:
                yield {"type": "response.output_text.delta", "delta": "hello"}
        def close(self):
            self.closed = True
    response = Stream()
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **k: response)),
                             responses=SimpleNamespace(create=lambda **k: response))
    transport = OpenAICompatibleTransport(client) if protocol == "chat" else OpenAIResponsesTransport(client, base_url="https://test.invalid/v1", websocket_mode="off")
    stream = transport.stream_completion(model="test", messages=[{"role": "user", "content": "hello"}])
    assert next(stream).text == "hello"
    stream.close()
    assert response.closed


def test_session_export_includes_reachable_images(store, tmp_path, monkeypatch):
    import webui
    ref = save(store)
    session = tmp_path / "sessions" / "s1"
    session.mkdir(parents=True)
    (session / "events.jsonl").write_text(json.dumps({"content": [{"type": "image", "attachment": ref}]}) + "\n")
    monkeypatch.setattr(webui, "WORK_DIR", tmp_path)
    monkeypatch.setattr(webui, "session_manager", SimpleNamespace(repository=SimpleNamespace(sessions_dir=session.parent), _resolve_session_path=lambda sid: session))
    assert garbage_collect(store, [session.parent], dry_run=False, grace_seconds=0)["removed"] == []
    archive, _ = webui._build_session_export_archive("s1")
    try:
        with zipfile.ZipFile(archive) as bundle:
            assert "s1/events.jsonl" in bundle.namelist()
            manifest = json.loads(bundle.read("attachments/manifest.json"))
            assert manifest["images"][0]["ref"]["attachmentId"] == ref["attachmentId"]
        restored = import_bundle(LocalAttachmentStore(tmp_path / "another-workspace"), archive)
        assert restored[0]["attachmentId"] == ref["attachmentId"]
    finally:
        archive.unlink(missing_ok=True)


def test_profile_controls_history_quota_and_crash_recovery(store, tmp_path, monkeypatch):
    transport = Transport()
    jobs = jobs_for(tmp_path, transport)
    resolver = jobs.candidate_resolver
    jobs.candidate_resolver = lambda profile: {**resolver(profile), "max_output_tokens": 16384, "reasoning_effort": "low"}
    ref = save(store)
    monkeypatch.setenv("VISION_MAX_STORED_REQUESTS", "1")
    jobs.start(ADMIN, payload(ref))
    assert finish(jobs)["status"] == "completed"
    assert transport.calls[0]["max_tokens"] == 16384 and transport.calls[0]["reasoning_effort"] == "low"
    with pytest.raises(HTTPException) as exc:
        jobs.start(ADMIN, payload(ref, "r2"))
    assert exc.value.status_code == 507
    with jobs.connection() as db:
        db.execute("UPDATE jobs SET state='accepted',updated=0,result=? WHERE id='r1'", (json.dumps({"requestId": "r1", "status": "accepted"}),))
    assert jobs.get("local", "r1")["error"]["code"] == "VISION_INTERRUPTED"
    assert jobs.events("local", "r1", 0)[-1][1]["type"] == "failed"
    jobs.prune("local", "r1")
    jobs.start(ADMIN, payload(ref, "r2"))
    assert finish(jobs, "r2")["status"] == "completed"
