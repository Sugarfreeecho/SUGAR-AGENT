"""Speech requests remain bounded, cancellable and independent of sessions."""
import asyncio
import hashlib
from functools import wraps
import json
from pathlib import Path
import struct
import sys

import httpx
import pytest
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins' / 'voice-input'))
from speech_input.api import register_speech_api
from speech_input.protocol import MAX_AUDIO_BYTES, validate_wave
from speech_input.service import SpeechError, SpeechService
import speech_input.service as speech_module


def async_test(function):
    @wraps(function)
    def run(*args, **kwargs):
        return asyncio.run(function(*args, **kwargs))
    return run


def wave(seconds=1):
    data = b"\0\0" * int(16000 * seconds)
    return (b"RIFF" + struct.pack("<I", len(data) + 36) + b"WAVEfmt "
            + struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16)
            + b"data" + struct.pack("<I", len(data)) + data)


def test_wave_validation_rejects_malformed_headers_and_duration():
    assert validate_wave(wave()) == 1
    assert validate_wave(wave(120)) == 120
    for audio in (b"", wave()[:-1], wave() + b"extra", wave(120.1), b"X" + wave()[1:]):
        with pytest.raises(ValueError):
            validate_wave(audio)
    for offset, value in ((20, 3), (22, 2), (24, 48000), (34, 8), (40, 0)):
        audio = bytearray(wave())
        struct.pack_into("<H" if offset in (20, 22, 34) else "<I", audio, offset, value)
        with pytest.raises(ValueError):
            validate_wave(bytes(audio))


@pytest.fixture
def service(tmp_path, monkeypatch):
    result = SpeechService(tmp_path)
    result.settings["asr"]["provider"] = "local"
    monkeypatch.setattr(result, "runtime_available", lambda: True)
    return result


@async_test
async def test_settings_default_persist_and_validate(service):
    state = await service.snapshot()
    assert not state["enabled"] and state["phase"] == "unprepared"
    assert state["tts"]["autoRead"] is False
    assert state["tts"]["readParenthetical"] is False
    assert not service.root.exists()
    await service.configure({"enabled": True, "language": "yue", "asr": {"provider": "local"}})
    restored = SpeechService(service.root.parent.parent)
    assert restored.settings["enabled"] is True and restored.settings["language"] == "yue"
    for changes in ({"enabled": "true"}, {"language": "xx"}, {"language": []}, {"unexpected": True}, []):
        with pytest.raises(SpeechError):
            await service.configure(changes)
    assert restored.settings == service.settings
    await service.close()


@async_test
async def test_auto_read_requires_a_boolean(service):
    await service.configure({"tts": {"enabled": True, "autoRead": True}})
    assert service.settings["tts"]["autoRead"] is True
    for value in ("true", 1, None, []):
        with pytest.raises(SpeechError):
            await service.configure({"tts": {"autoRead": value}})
    assert service.settings["tts"]["autoRead"] is True
    await service.configure({"tts": {"readParenthetical": True}})
    assert service.settings["tts"]["readParenthetical"] is True
    for value in ("false", 0, None):
        with pytest.raises(SpeechError):
            await service.configure({"tts": {"readParenthetical": value}})
    await service.configure({"tts": {"autoReadScope": "current"}})
    assert service.settings["tts"]["autoReadScope"] == "current"
    for value in ("open", "ALL", 1, None):
        with pytest.raises(SpeechError):
            await service.configure({"tts": {"autoReadScope": value}})
    await service.configure({"tts": {"autoReadOnlyFocused": True}})
    assert service.settings["tts"]["autoReadOnlyFocused"] is True
    for value in ("true", 1, None):
        with pytest.raises(SpeechError):
            await service.configure({"tts": {"autoReadOnlyFocused": value}})
    await service.close()


@async_test
async def test_transcribe_never_downloads_and_checks_language(service):
    with pytest.raises(SpeechError, match="disabled"):
        await service.transcribe(wave(), "local", "r1")
    await service.configure({"enabled": True})
    with pytest.raises(SpeechError, match="Prepare"):
        await service.transcribe(wave(), "local", "r1")
    service._verified = True
    with pytest.raises(SpeechError, match="Unsupported language"):
        await service.transcribe(wave(), "local", "r1", "xx")
    with pytest.raises(ValueError):
        await service.transcribe(b"invalid", "local", "r1")
    assert service._preparation is None
    await service.close()


@async_test
async def test_prepare_verifies_download_and_reuses_cache(service, monkeypatch):
    content = b"pinned test model"
    asset = ("model.onnx", "/pinned/model", len(content), hashlib.sha256(content).hexdigest())
    monkeypatch.setattr(speech_module, "ASSETS", (asset,))
    service.models.mkdir(parents=True)
    requests = []

    def respond(request):
        requests.append(str(request.url))
        return httpx.Response(200, content=content)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await service._download(client, asset, "mirror")
        await service._download(client, asset, "mirror")
    assert requests == ["https://hf-mirror.com/pinned/model"]
    assert service._check_cache()
    assert not list(service.models.glob("*.part"))
    assert (await service.snapshot())["phase"] == "ready"
    await service.close()


@async_test
async def test_download_rejects_corruption_and_manual_source_never_falls_back(service):
    content = b"good"
    asset = ("model.onnx", "/pinned", len(content), hashlib.sha256(content).hexdigest())
    service.models.mkdir(parents=True)
    requests = []

    def respond(request):
        requests.append(str(request.url))
        return httpx.Response(200, content=b"bad!")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(SpeechError, match="download failed"):
            await service._download(client, asset, "mirror")
    assert requests == ["https://hf-mirror.com/pinned"]
    assert list(service.models.iterdir()) == []
    await service.close()


@async_test
async def test_automatic_source_fallback(service):
    content = b"good"
    asset = ("model.onnx", "/pinned", 4, hashlib.sha256(content).hexdigest())
    service.models.mkdir(parents=True)
    requests = []

    def respond(request):
        requests.append(request.url.host)
        return httpx.Response(503) if request.url.host == "huggingface.co" else httpx.Response(200, content=content)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await service._download(client, asset, "auto")
    assert requests == ["huggingface.co", "hf-mirror.com"]
    await service.close()


@async_test
async def test_preparation_is_host_owned_and_cancelled_on_disable(service, monkeypatch):
    entered = asyncio.Event()
    stopped = asyncio.Event()

    async def download(*args):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(service, "_download_all", download)
    await service.configure({"enabled": True})
    await service.prepare()
    first = service._preparation
    await entered.wait()
    await service.prepare()
    assert service._preparation is first
    await service.configure({"enabled": False})
    assert stopped.is_set() and first.done()
    assert not service._operation.locked()
    assert (await service.snapshot())["phase"] == "cancelled"
    await service.close()


async def fake_worker(service, monkeypatch, tmp_path, mode="success"):
    script = tmp_path / "worker.py"
    script.write_text(
        "import sys,json,time\nprint('{\"ready\":true}',flush=True)\n"
        "for line in sys.stdin:\n"
        + (" time.sleep(30)\n" if mode == "hang" else
           " print(json.dumps({'text':'测试文本','audioSeconds':1,'inferenceSeconds':0.01}),flush=True)\n"), encoding="utf-8")
    create = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        return await create(sys.executable, "-u", str(script), **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    await service.configure({"enabled": True})
    service._verified = service._inspected = True
    service.state = {"phase": "ready"}


@async_test
async def test_real_worker_pipe_reuse_and_shutdown(service, monkeypatch, tmp_path):
    await fake_worker(service, monkeypatch, tmp_path)
    first = await service.transcribe(wave(), "alice", "r1")
    worker = service._worker
    second = await service.transcribe(wave(), "alice", "r2")
    assert first["text"] == second["text"] == "测试文本"
    assert service._worker is worker
    assert not service._jobs
    await service.close()
    assert worker.returncode is not None


@async_test
async def test_cancel_is_owner_scoped_and_reaps_native_worker(service, monkeypatch, tmp_path):
    await fake_worker(service, monkeypatch, tmp_path, "hang")
    job = asyncio.create_task(service.transcribe(wave(), "alice", "r1"))
    for _ in range(100):
        if service._worker and service._worker.stdout and service._jobs:
            break
        await asyncio.sleep(.01)
    worker = service._worker
    await service.cancel("bob", "r1")
    assert not job.done()
    with pytest.raises(SpeechError, match="busy"):
        await service.transcribe(wave(), "alice", "r2")
    await service.cancel("alice", "r1")
    assert job.cancelled() and worker.returncode is not None
    assert service._worker is None and not service._operation.locked()
    await service.close()


@async_test
async def test_api_authentication_limits_and_transient_result(service, monkeypatch, tmp_path):
    await fake_worker(service, monkeypatch, tmp_path)
    app = FastAPI()
    register_speech_api(app, tmp_path, service=service)
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 1234))
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        state = await client.get("/api/speech/status")
        assert state.status_code == 200
        result = await client.post("/api/speech/transcribe", content=wave(), headers={"X-Speech-Request-Id": "r1"})
        assert result.status_code == 200 and result.json()["text"] == "测试文本"
        assert (await client.post("/api/speech/transcribe", content=wave())).status_code == 400
        assert (await client.post("/api/speech/transcribe", content=b"invalid", headers={"X-Speech-Request-Id": "bad"})).status_code == 400
        assert (await client.post("/api/speech/transcribe", content=b"x" * (MAX_AUDIO_BYTES + 1), headers={"X-Speech-Request-Id": "large"})).status_code == 413
        assert (await client.patch("/api/speech/config", json={"enabled": True}, headers={"Origin": "https://evil.example"})).status_code == 403
        assert (await client.patch("/api/speech/config", content=b"[]")).status_code == 400
        assert (await client.post("/api/speech/prepare", json={"source": "http://evil.example"})).status_code == 400
    external = httpx.ASGITransport(app=app, client=("192.0.2.20", 1234))
    async with httpx.AsyncClient(transport=external, base_url="http://127.0.0.1") as client:
        assert (await client.get("/api/speech/status")).status_code == 401
    assert not list(tmp_path.rglob("*.wav"))
    assert not list(tmp_path.rglob("*session*"))
    await service.close()
