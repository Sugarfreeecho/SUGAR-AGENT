"""Voice plugin ownership, credential redaction and both supported API protocols."""
import asyncio
import base64
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "plugins/voice-input"))
from speech_input import providers
from speech_input.api import register_speech_api
from speech_input.service import SpeechService, SpeechError
from tests.test_speech_input import async_test, wave


@async_test
async def test_bundled_adapter_registers_routes_and_joins_shutdown(tmp_path, monkeypatch):
    from plugins import load_plugin
    import plugins.host as hosts
    plugin = load_plugin(ROOT / 'plugins/voice-input')
    monkeypatch.setattr(hosts, 'bundled_host_plugin_enabled', lambda _: True)
    module = hosts._module(plugin)
    app = FastAPI()
    context = {'app': app, 'work_dir': tmp_path}
    module.install(app, context, plugin)
    service = app.state.voice_input_service
    module.install(app, context, plugin)
    assert sum(getattr(route, 'path', '') == '/api/speech/status' for route in app.routes) == 1
    await module.start(context, plugin)
    assert not service._closed
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=('127.0.0.1', 1)), base_url='http://127.0.0.1') as client:
        assert (await client.get('/api/speech/status')).status_code == 200
    await module.stop(context, plugin)
    assert service._closed
    await module.start(context, plugin)
    assert not service._closed
    await module.stop(context, plugin)


def test_disabled_bundled_settings_assets_remain_available(monkeypatch):
    from types import SimpleNamespace
    from plugins import load_plugin
    import plugins
    import plugin_web_gateway as gateway
    plugin = load_plugin(ROOT / 'plugins/voice-input')
    def disabled(_, **_options):
        raise gateway.PluginWebError(404, 'plugin_not_found', 'disabled')
    monkeypatch.setattr(gateway, '_enabled_plugin', disabled)
    monkeypatch.setattr(plugins, 'get_plugin_manager', lambda: SimpleNamespace(discover=lambda: [plugin]))
    assert gateway.plugin_asset('voice-input', 'settings.js') == ROOT / 'plugins/voice-input/web/settings.js'
    assert gateway.plugin_asset('voice-input', 'shared.js') == ROOT / 'plugins/voice-input/web/shared.js'
    with pytest.raises(gateway.PluginWebError):
        gateway.plugin_asset('unknown', 'settings.js')


def test_plugin_manifest_and_trusted_settings_renderer(tmp_path):
    from plugins import load_plugin
    from plugins.ui import plugin_ui_contributions
    plugin = load_plugin(ROOT / "plugins/voice-input")
    rows = plugin_ui_contributions(plugin)
    assert any(row["slot"] == "chat.extension" for row in rows)
    settings = next(row for row in rows if row["slot"] == "settings.section")
    assert "group" not in settings and settings["target"] == "renderer"
    assert settings["renderer"]["module"].startswith("/plugin-assets/voice-input/settings.js")
    untrusted = replace(plugin, root=tmp_path)
    assert not any(row["target"] == "renderer" for row in plugin_ui_contributions(untrusted) if "target" in row)


@async_test
async def test_api_mode_never_checks_or_starts_local_models(tmp_path, monkeypatch):
    service = SpeechService(tmp_path)
    monkeypatch.setattr(service, "_check_cache", lambda: pytest.fail("API mode touched local cache"))
    monkeypatch.setattr(service, "runtime_available", lambda: pytest.fail("API mode checked native dependencies"))
    state = await service.configure({"enabled": True, "asr": {"base_url": "https://asr.example/v1", "model": "recognizer", "api_key": "private-asr"},
                                     "tts": {"enabled": True, "api_key": "private-tts"}})
    assert state["phase"] == "ready" and state["asr"]["api_key_set"]
    assert "private" not in json.dumps(state)
    assert not service.models.exists()
    state = await service.configure({"asr": {"api_key": ""}})
    assert service.settings["asr"]["api_key"] == "private-asr"
    await service.configure({"asr": {"api_key": None}})
    assert not service.settings["asr"]["api_key"]
    with pytest.raises(SpeechError):
        await service.configure({"tts": {"base_url": "https://user:password@service.example/v1"}})
    await service.close()


@async_test
async def test_multipart_asr_and_binary_tts(monkeypatch):
    calls = []

    async def request(config, endpoint, **kwargs):
        calls.append((endpoint, kwargs))
        return (b'{"text":"recognized"}', "application/json") if endpoint.endswith('transcriptions') else (b'ID3audio', 'audio/mpeg')

    monkeypatch.setattr(providers, "request", request)
    config = {"provider": "openai-compatible", "model": "test", "voice": "alloy", "speed": 1.2, "instructions": ""}
    result = await providers.transcribe(config, wave(), "auto", 1)
    assert result["text"] == "recognized"
    assert calls[0][0] == "/audio/transcriptions"
    assert calls[0][1]["files"]["file"] == ("recording.wav", wave(), "audio/wav")
    assert "language" not in calls[0][1]["data"]
    audio, kind = await providers.synthesize(config, "Hello")
    assert audio == b'ID3audio' and kind == 'audio/mpeg'
    assert calls[1][1]["json"] == {"model": "test", "input": "Hello", "voice": "alloy", "speed": 1.2, "response_format": "mp3"}


@async_test
async def test_mimo_asr_and_tts_follow_official_chat_audio_protocol(monkeypatch):
    calls = []

    async def request(config, endpoint, **kwargs):
        calls.append((endpoint, kwargs["json"]))
        message = {"content": "转写"} if config["model"].endswith("asr") else {"audio": {"data": base64.b64encode(wave()).decode()}}
        return json.dumps({"choices": [{"message": message}]}).encode(), "application/json"

    monkeypatch.setattr(providers, "request", request)
    result = await providers.transcribe({"provider": "mimo", "model": "mimo-v2.5-asr"}, wave(), "zh", 1)
    assert result["text"] == "转写"
    assert calls[0][0] == "/chat/completions"
    assert calls[0][1]["messages"][0]["content"][0]["input_audio"]["data"].startswith("data:audio/wav;base64,")
    assert calls[0][1]["asr_options"] == {"language": "zh"}
    result, kind = await providers.synthesize({"provider": "mimo", "model": "mimo-v2.5-tts", "voice": "冰糖", "speed": 1, "instructions": "温柔"}, "只读这句")
    assert result == wave() and kind == "audio/wav"
    body = calls[1][1]
    assert body["messages"] == [{"role": "user", "content": "温柔"}, {"role": "assistant", "content": "只读这句"}]
    assert body["audio"] == {"format": "wav", "voice": "冰糖"}


@async_test
async def test_provider_errors_do_not_reveal_keys_and_response_is_bounded(monkeypatch):
    real_client = httpx.AsyncClient
    def factory(**kwargs):
        return real_client(transport=httpx.MockTransport(lambda request: httpx.Response(401, text='secret error key=private-key')), **kwargs)
    monkeypatch.setattr(httpx, "AsyncClient", factory)
    config = {"base_url": "https://example.test/v1", "model": "test", "api_key": "private-key"}
    with pytest.raises(providers.VoiceAPIError, match="HTTP 401") as error:
        await providers.request(config, "/audio/speech", limit=10, json={})
    assert "private-key" not in str(error.value)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'x' * 11)), **kwargs))
    with pytest.raises(providers.VoiceAPIError, match="size limit"):
        await providers.request(config, "/audio/speech", limit=10, json={})


@async_test
async def test_plugin_gate_and_tts_owner_cancellation(tmp_path, monkeypatch):
    service = SpeechService(tmp_path)
    await service.configure({"enabled": True, "tts": {"enabled": True}})
    entered = asyncio.Event()
    released = asyncio.Event()
    async def synthesize(*args):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            released.set()
    monkeypatch.setattr(providers, "synthesize", synthesize)
    task = asyncio.create_task(service.synthesize("hello", "alice", "tts1"))
    await entered.wait()
    await service.cancel("bob", "tts1")
    assert not task.done()
    await service.cancel("alice", "tts1")
    assert task.cancelled() and released.is_set()
    app = FastAPI()
    register_speech_api(app, tmp_path, service=service, enabled_resolver=lambda: False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1)), base_url="http://127.0.0.1") as client:
        result = await client.get('/api/speech/status')
        assert not result.json()["plugin_enabled"]
        assert (await client.patch('/api/speech/config', json={"enabled": True})).status_code == 404
        assert (await client.post('/api/speech/synthesize', json={"text": "hello", "requestId": "tts"})).status_code == 404
    await service.close()


@async_test
async def test_tts_http_returns_audio_and_rejects_oversized_text(tmp_path, monkeypatch):
    service = SpeechService(tmp_path)
    await service.configure({"tts": {"enabled": True}})
    async def synthesize(*args): return wave(), "audio/wav"
    monkeypatch.setattr(providers, 'synthesize', synthesize)
    app = FastAPI()
    register_speech_api(app, tmp_path, service=service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1)), base_url="http://127.0.0.1") as client:
        result = await client.post('/api/speech/synthesize', json={"text": "hello", "requestId": "r1"})
        assert result.content == wave() and result.headers['cache-control'] == 'no-store'
        result = await client.post('/api/speech/synthesize', json={"text": 'x' * 4001, "requestId": "r2"})
        assert result.status_code == 400
    await service.close()


MIMO_TTS = {"provider": "mimo", "model": "mimo-v2.5-tts", "voice": "冰糖", "speed": 1, "instructions": ""}


@async_test
async def test_streaming_tts_caches_pcm_and_replays_it(tmp_path, monkeypatch):
    service = SpeechService(tmp_path)
    await service.configure({"tts": {"enabled": True}})
    calls = []

    async def stream(config, text):
        calls.append(text)
        yield b"\x01\x02" * 8
        yield b"\x03\x04" * 8

    monkeypatch.setattr(providers, "synthesize_stream", stream)
    key, rate = service.stream_parameters("hello")
    first = b"".join([c async for c in service.stream_speech("hello", key, "alice", "a1")])
    assert first == b"\x01\x02" * 8 + b"\x03\x04" * 8 and rate == 24000
    second = b"".join([c async for c in service.stream_speech("hello", key, "alice", "a2")])
    assert second == first and calls == ["hello"]  # Second pass is a cache replay, not a new call.
    assert [p.name for p in (tmp_path / ".config/speech-input/cache").iterdir()] == [key + ".pcm"]
    await service.close()


@async_test
async def test_streaming_tts_keeps_partial_audio_out_of_the_cache(tmp_path, monkeypatch):
    service = SpeechService(tmp_path)
    await service.configure({"tts": {"enabled": True}})

    async def stream(config, text):
        yield b"\x00\x00" * 4
        raise providers.VoiceAPIError("Voice provider returned HTTP 500")

    monkeypatch.setattr(providers, "synthesize_stream", stream)
    key, _ = service.stream_parameters("hello")
    with pytest.raises(providers.VoiceAPIError):
        async for _ in service.stream_speech("hello", key, "alice", "a1"):
            pass
    assert not list((tmp_path / ".config/speech-input/cache").glob("*.pcm"))
    assert not list((tmp_path / ".config/speech-input/cache").glob("*.part"))
    await service.close()


@async_test
async def test_streaming_endpoint_rejects_non_mimo_providers(tmp_path, monkeypatch):
    service = SpeechService(tmp_path)
    await service.configure({"tts": {"enabled": True, "provider": "openai-compatible", "base_url": "https://example.test/v1", "model": "tts-1"}})
    app = FastAPI()
    register_speech_api(app, tmp_path, service=service)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1)), base_url="http://127.0.0.1") as client:
        result = await client.post('/api/speech/synthesize/stream', json={"text": "hello", "requestId": "s1"})
        assert result.status_code == 409 and result.json()["code"] == "streaming-unsupported"
    await service.close()
