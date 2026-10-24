"""Voice configuration, API providers and optional local CPU recognition."""
import asyncio
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import uuid
from copy import deepcopy

import httpx

from config_paths import config_path
from proc_flags import NO_WINDOW
from .protocol import LANGUAGES, MAX_AUDIO_BYTES, MAX_DURATION_SECONDS, validate_wave
from .configuration import DEFAULTS, merge_settings, public_settings
from . import providers

MODEL_PATH = "/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/2365baeacb507f821a0c8120fcee3d484dba7a07/"
ASSETS = (
    ("model.int8.onnx", MODEL_PATH + "model.int8.onnx", 239233841, "c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51"),
    ("tokens.txt", MODEL_PATH + "tokens.txt", 315894, "f449eb28dc567533d7fa59be34e2abca8784f771850c78a47fb731a31429a1dc"),
    ("silero_vad.onnx", "/csukuangfj/vad/resolve/fba88cd2e921609e7675c3aaf51e0b9b295da4bc/silero_vad.onnx", 1807522,
     "a35ebf52fd3ce5f1469b2a36158dba761bc47b973ea3382b3186ca15b1f5af28"),
)
SOURCES = {"huggingface": "https://huggingface.co", "mirror": "https://hf-mirror.com"}
CACHE_LIMIT_BYTES = 256 * 1024 * 1024
STREAM_CHUNK_BYTES = 64 * 1024


class SpeechError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.status = code, status


class SpeechService:
    """Own model cache, preparation and inference until application shutdown."""

    def __init__(self, work_dir):
        self.root = config_path(work_dir, "speech-input")
        self.models = self.root / "models"
        self.cache = self.root / "cache"
        self.settings = deepcopy(DEFAULTS)
        try:
            stored = json.loads((self.root / "settings.json").read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                self.settings = merge_settings(self.settings, stored)
                if "asr" not in stored and stored.get("enabled") is True:
                    self.settings["asr"]["provider"] = "local"
        except (OSError, ValueError):
            pass  # No settings, or an interrupted external edit: keep explicit defaults.
        self.state = {"phase": "unprepared"}
        self._verified = False
        self._inspected = False
        self._inspection = None
        self._preparation = None
        self._operation = asyncio.Lock()
        self._worker = None
        self._idle = None
        self._jobs = {}
        self._streams = 0
        self._closed = False

    def runtime_available(self):
        return importlib.util.find_spec("sherpa_onnx") is not None and importlib.util.find_spec("numpy") is not None

    async def snapshot(self):
        local = self.settings["asr"]["provider"] == "local"
        if local and not self._inspected and not self._preparation and not self._closed:
            if self._inspection is None:
                self._inspection = asyncio.create_task(asyncio.to_thread(self._check_cache))
            self._verified = await asyncio.shield(self._inspection)
            self._inspected = True
            self.state = {"phase": "ready" if self._verified else "unprepared"}
        phase = self.state if local else {"phase": "ready" if self.settings["asr"]["base_url"] and self.settings["asr"]["model"] else "unconfigured"}
        return {**phase, **public_settings(self.settings), "runtimeAvailable": self.runtime_available() if local else True,
                "modelBytes": sum(asset[2] for asset in ASSETS), "maxAudioBytes": MAX_AUDIO_BYTES,
                "maxDurationSeconds": MAX_DURATION_SECONDS, "languages": LANGUAGES,
                "workerLoaded": self._worker is not None and self._worker.returncode is None}

    def _matches(self, asset):
        path = self.models / asset[0]
        if not path.is_file() or path.stat().st_size != asset[2]:
            return False
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest() == asset[3]

    def _check_cache(self):
        return all(self._matches(asset) for asset in ASSETS)

    async def configure(self, changes):
        try:
            updated = merge_settings(self.settings, changes)
        except ValueError as error:
            raise SpeechError("invalid-settings", str(error)) from error
        self.root.mkdir(parents=True, exist_ok=True)
        partial = self.root / (uuid.uuid4().hex + ".tmp")
        try:
            with partial.open("x", encoding="utf-8") as stream:
                os.chmod(partial, 0o600)
                stream.write(json.dumps(updated))
            os.replace(partial, self.root / "settings.json")
        finally:
            partial.unlink(missing_ok=True)
        previous = self.settings
        self.settings = updated
        if not updated["enabled"] or updated["asr"] != previous["asr"] or updated["language"] != previous["language"] or updated["tts"] != previous["tts"]:
            await self.cancel_preparation()
            tasks = list(self._jobs.values())
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self._stop_worker()
        return await self.snapshot()

    def _require_available(self):
        if self._closed or not self.settings["enabled"]:
            raise SpeechError("disabled", "Speech input is disabled", 409)

    async def prepare(self, source="auto"):
        self._require_available()
        if self.settings["asr"]["provider"] != "local":
            raise SpeechError("not-local", "Model preparation is only used by local recognition", 409)
        if not self.runtime_available():
            raise SpeechError("missing-runtime", "Install the voice plugin's optional requirements.txt for local recognition", 503)
        if source not in ("auto", *SOURCES):
            raise SpeechError("invalid-source", "Unknown model source")
        if self._inspection is not None:
            await asyncio.shield(self._inspection)
        if self._preparation and not self._preparation.done():
            return
        if self._operation.locked():
            raise SpeechError("busy", "Speech recognizer is busy", 409)
        self.state = {"phase": "checking"}
        self._preparation = asyncio.create_task(self._prepare(source))

    async def _download(self, client, asset, source):
        if await asyncio.to_thread(self._matches, asset):
            return
        origins = list(SOURCES.values()) if source == "auto" else [SOURCES[source]]
        failure = ""
        for origin in origins:
            partial = self.models / (asset[0] + "." + uuid.uuid4().hex + ".part")
            try:
                self.state = {"phase": "downloading", "file": asset[0], "completedBytes": 0,
                              "totalBytes": asset[2], "source": origin}
                digest, received = hashlib.sha256(), 0
                async with client.stream("GET", origin + asset[1]) as response:
                    response.raise_for_status()
                    with partial.open("xb") as stream:
                        async for chunk in response.aiter_bytes(256 * 1024):
                            received += len(chunk)
                            if received > asset[2]:
                                raise SpeechError("integrity", "Downloaded model exceeds its expected size")
                            digest.update(chunk)
                            stream.write(chunk)
                            self.state["completedBytes"] = received
                self.state["phase"] = "verifying"
                if received != asset[2] or digest.hexdigest() != asset[3]:
                    raise SpeechError("integrity", "Model checksum verification failed")
                os.replace(partial, self.models / asset[0])
                return
            except (httpx.HTTPError, SpeechError) as error:
                # Keep URLs and signed redirect parameters out of public errors.
                failure = f"{origin}: {type(error).__name__}"
            finally:
                partial.unlink(missing_ok=True)
        raise SpeechError("download-failed", "Model download failed (" + failure + ")", 502)

    async def _prepare(self, source):
        async with self._operation:
            try:
                self.models.mkdir(parents=True, exist_ok=True)
                async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
                    await asyncio.wait_for(self._download_all(client, source), 3600)
                self._verified = self._inspected = True
                self.state = {"phase": "loading"}
                await self._start_worker()
                self.state = {"phase": "ready"}
                self._schedule_idle()
            except asyncio.CancelledError:
                await self._stop_worker()
                self.state = {"phase": "ready" if self._verified else "cancelled"}
            except Exception as error:
                await self._stop_worker()
                self.state = {"phase": "failed", "error": str(error) if isinstance(error, SpeechError)
                              else type(error).__name__, "code": getattr(error, "code", "preparation-failed")}

    async def _download_all(self, client, source):
        for asset in ASSETS:
            await self._download(client, asset, source)

    async def cancel_preparation(self):
        task = self._preparation
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if self.state["phase"] in {"checking", "downloading", "verifying", "loading"}:
                self.state = {"phase": "ready" if self._verified else "cancelled"}

    async def _start_worker(self):
        if self._idle:
            self._idle.cancel()
        if self._worker and self._worker.returncode is None:
            return self._worker
        await self._stop_worker()
        executable = Path(sys.executable)
        if executable.name.lower() == "pythonw.exe":
            executable = executable.with_name("python.exe")
        self._worker = await asyncio.create_subprocess_exec(
            str(executable), "-u", str(Path(__file__).with_name("worker.py")), str(self.models),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, creationflags=NO_WINDOW, limit=256 * 1024,
        )
        try:
            frame = await asyncio.wait_for(self._worker.stdout.readline(), 120)
            if json.loads(frame) != {"ready": True}:
                raise ValueError("Invalid worker readiness")
        except (ValueError, asyncio.TimeoutError) as error:
            raise SpeechError("worker-failed", "Speech model could not load; check runtime and model files", 503) from error
        return self._worker

    async def _stop_worker(self):
        if self._idle:
            self._idle.cancel()
            self._idle = None
        worker, self._worker = self._worker, None
        if worker:
            if worker.returncode is None:
                try:
                    worker.kill()
                except ProcessLookupError:
                    pass  # Process exited between observation and cancellation.
            await worker.wait()
            if worker.stdin:
                worker.stdin.close()

    def _schedule_idle(self):
        if self._idle:
            self._idle.cancel()
        worker = self._worker

        async def expire():
            async with self._operation:
                if self._worker is worker:
                    await self._stop_worker()

        self._idle = asyncio.get_running_loop().call_later(300, lambda: asyncio.create_task(expire()))

    async def transcribe(self, audio, owner, identity, language=None):
        self._require_available()
        seconds = validate_wave(audio)
        language = language or self.settings["language"]
        if language not in LANGUAGES:
            raise SpeechError("invalid-language", "Unsupported language")
        if self.settings["asr"]["provider"] != "local":
            return await self._api_job(owner, identity, providers.transcribe, deepcopy(self.settings["asr"]), audio, language, seconds)
        if not self.runtime_available():
            raise SpeechError("missing-runtime", "Local recognition runtime is missing", 503)
        if not self._verified:
            raise SpeechError("unprepared", "Prepare the speech model before recording", 409)
        if self._operation.locked():
            raise SpeechError("busy", "Speech recognizer is busy", 429)
        key = (owner, identity)
        if key in self._jobs:
            raise SpeechError("duplicate-request", "Speech request already exists", 409)
        async with self._operation:
            self._jobs[key] = asyncio.current_task()
            try:
                worker = await self._start_worker()
                data = {"audio": base64.b64encode(audio).decode("ascii"), "language": language}

                async def exchange():
                    worker.stdin.write((json.dumps(data) + "\n").encode("ascii"))
                    await worker.stdin.drain()
                    return await worker.stdout.readline()

                frame = await asyncio.wait_for(exchange(), 120)
                result = json.loads(frame)
                if (not isinstance(result, dict) or not isinstance(result.get("text"), str)
                        or len(result["text"]) > 65536):
                    raise ValueError("Invalid transcript")
                self._schedule_idle()
                return result
            except asyncio.CancelledError:
                await self._stop_worker()
                raise
            except Exception as error:
                await self._stop_worker()
                raise SpeechError("transcription-failed", "Speech recognition failed; retry the recording", 503) from error
            finally:
                self._jobs.pop(key, None)

    async def cancel(self, owner, identity):
        task = self._jobs.get((owner, identity))
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _api_job(self, owner, identity, operation, *arguments):
        key = (owner, identity)
        if key in self._jobs or len(self._jobs) >= 4:
            raise SpeechError("busy", "Voice service is busy", 429)
        self._jobs[key] = asyncio.current_task()
        try:
            return await asyncio.wait_for(operation(*arguments), 180)
        except asyncio.TimeoutError as error:
            raise SpeechError("provider-timeout", "Voice provider timed out", 504) from error
        except providers.VoiceAPIError as error:
            raise SpeechError("provider-failed", str(error), 502) from error
        finally:
            self._jobs.pop(key, None)

    async def synthesize(self, text, owner, identity):
        if self._closed or not self.settings["tts"]["enabled"]:
            raise SpeechError("tts-disabled", "Enable text-to-speech in Voice settings", 409)
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise SpeechError("invalid-text", "Speech text must contain 1 to 4000 characters")
        return await self._api_job(owner, identity, providers.synthesize, deepcopy(self.settings["tts"]), text)

    def _cache_key(self, text):
        config = self.settings["tts"]
        material = json.dumps([config["provider"], config["base_url"], config["model"], config["voice"],
                               config["speed"], config["instructions"], text], ensure_ascii=False)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def stream_parameters(self, text):
        """Validate a streaming request eagerly so failures stay ordinary HTTP errors."""
        if self._closed or not self.settings["tts"]["enabled"]:
            raise SpeechError("tts-disabled", "Enable text-to-speech in Voice settings", 409)
        if self.settings["tts"]["provider"] != "mimo":
            raise SpeechError("streaming-unsupported", "Streaming speech requires the MiMo provider", 409)
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise SpeechError("invalid-text", "Speech text must contain 1 to 4000 characters")
        key = self._cache_key(text)
        # Checked before the response starts, otherwise a full queue would look like a broken stream.
        if not (self.cache / (key + ".pcm")).is_file() and self._streams >= 4:
            raise SpeechError("busy", "Voice service is busy", 429)
        return key, providers.MIMO_PCM_RATE

    async def stream_speech(self, text, key, owner, identity):
        """Yield PCM16 mono chunks, replaying the cache and filling it as audio arrives."""
        del owner, identity  # Streaming is cancelled by the closed response, not by job handles.
        path = self.cache / (key + ".pcm")
        if path.is_file() and path.stat().st_size > 1:
            try:
                os.utime(path, None)  # Least-recently-used order follows playback, not creation.
            except OSError:
                pass
            with path.open("rb") as source:
                while True:
                    chunk = source.read(STREAM_CHUNK_BYTES)
                    if not chunk:
                        return
                    yield chunk
        if self._streams >= 4:
            raise SpeechError("busy", "Voice service is busy", 429)
        partial = self.cache / (key + "." + uuid.uuid4().hex + ".part")
        handle = None
        self._streams += 1
        try:
            self.cache.mkdir(parents=True, exist_ok=True)
            handle = partial.open("wb")
            async for chunk in providers.synthesize_stream(deepcopy(self.settings["tts"]), text):
                handle.write(chunk)
                yield chunk
            handle.close()
            handle = None
            os.replace(partial, path)
            self._trim_cache()
        finally:
            self._streams -= 1
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
            partial.unlink(missing_ok=True)

    def _trim_cache(self):
        """Keep the PCM cache inside its byte budget, oldest access first."""
        entries = []
        try:
            for entry in self.cache.glob("*.pcm"):
                try:
                    stat = entry.stat()
                except OSError:
                    continue
                entries.append((stat.st_mtime, stat.st_size, entry))
        except OSError:
            return
        total = sum(size for _, size, _ in entries)
        for _, size, entry in sorted(entries):
            if total <= CACHE_LIMIT_BYTES:
                break
            try:
                entry.unlink()
            except OSError:
                continue
            total -= size

    async def close(self):
        self._closed = True
        await self.cancel_preparation()
        tasks = list(self._jobs.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self._stop_worker()
        if self._inspection:
            await asyncio.gather(self._inspection, return_exceptions=True)
