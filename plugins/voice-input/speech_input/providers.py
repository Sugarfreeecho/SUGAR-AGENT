"""Bounded API calls for multipart speech APIs and Xiaomi MiMo chat audio."""
import base64
import binascii
import json
import time

import httpx

STREAM_LIMIT = 32 * 1024 * 1024


class VoiceAPIError(Exception):
    pass


async def request(config, path, *, limit, **kwargs):
    if not config["base_url"] or not config["model"]:
        raise VoiceAPIError("Configure the API base URL and model in Voice settings")
    headers = {"Authorization": "Bearer " + config["api_key"]} if config["api_key"] else {}
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
            async with client.stream("POST", config["base_url"] + path, headers=headers, **kwargs) as response:
                if not response.is_success:
                    raise VoiceAPIError("Voice provider returned HTTP " + str(response.status_code))
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(data) + len(chunk) > limit:
                        raise VoiceAPIError("Voice provider response exceeds size limit")
                    data.extend(chunk)
                return bytes(data), response.headers.get("content-type", "")
    except httpx.HTTPError as error:
        raise VoiceAPIError("Voice provider connection failed or timed out") from error


async def transcribe(config, audio, language, seconds):
    started = time.monotonic()
    if config["provider"] == "mimo":
        if language not in {"auto", "zh", "en"}:
            raise VoiceAPIError("MiMo ASR accepts auto, zh or en; use auto for dialect recognition")
        data = {"model": config["model"], "stream": False, "messages": [{"role": "user", "content": [
            {"type": "input_audio", "input_audio": {"data": "data:audio/wav;base64," + base64.b64encode(audio).decode("ascii")}}]}],
            "asr_options": {"language": language}}
        raw, _ = await request(config, "/chat/completions", limit=1024 * 1024, json=data)
        try:
            text = json.loads(raw)["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise VoiceAPIError("Invalid MiMo transcription response") from error
    else:
        data = {"model": config["model"], "response_format": "json"}
        if language != "auto":
            data["language"] = language
        raw, _ = await request(config, "/audio/transcriptions", limit=1024 * 1024,
                               data=data, files={"file": ("recording.wav", audio, "audio/wav")})
        try:
            text = json.loads(raw)["text"]
        except (ValueError, KeyError, TypeError) as error:
            raise VoiceAPIError("Invalid transcription response") from error
    if not isinstance(text, str) or len(text) > 65536:
        raise VoiceAPIError("Invalid transcript")
    return {"text": text, "audioSeconds": seconds, "inferenceSeconds": time.monotonic() - started}


async def synthesize(config, text):
    if config["provider"] == "mimo":
        messages = []
        instructions = config["instructions"]
        if config["speed"] != 1:
            instructions += " Speak at " + str(config["speed"]) + " times normal speed."
        if instructions.strip():
            messages.append({"role": "user", "content": instructions})
        messages.append({"role": "assistant", "content": text})
        raw, _ = await request(config, "/chat/completions", limit=48 * 1024 * 1024,
                               json={"model": config["model"], "messages": messages, "stream": False,
                                     "audio": {"format": "wav", "voice": config["voice"]}})
        try:
            encoded = json.loads(raw)["choices"][0]["message"]["audio"]["data"]
            if not isinstance(encoded, str) or len(encoded) > 44 * 1024 * 1024:
                raise ValueError()
            audio = base64.b64decode(encoded, validate=True)
        except (ValueError, KeyError, TypeError, IndexError, binascii.Error) as error:
            raise VoiceAPIError("Invalid MiMo speech response") from error
        content_type = "audio/wav"
    else:
        payload = {"model": config["model"], "input": text, "voice": config["voice"],
                   "speed": config["speed"], "response_format": "mp3"}
        if config["instructions"]:
            payload["instructions"] = config["instructions"]
        audio, content_type = await request(config, "/audio/speech", limit=32 * 1024 * 1024, json=payload)
        content_type = content_type.split(";", 1)[0]
        if content_type not in {"audio/mpeg", "audio/mp3", "audio/wav", "audio/ogg", "audio/flac", "audio/aac", "audio/mp4", "application/octet-stream"}:
            raise VoiceAPIError("Provider did not return audio")
        if content_type == "application/octet-stream":
            content_type = "audio/mpeg"
    if not audio:
        raise VoiceAPIError("Provider returned empty audio")
    return audio, content_type


MIMO_PCM_RATE = 24000


async def synthesize_stream(config, text):
    """Yield little-endian PCM16 mono chunks at MIMO_PCM_RATE from MiMo SSE.

    Only MiMo exposes incremental audio; other providers keep the buffered path.
    """
    if config["provider"] != "mimo":
        raise VoiceAPIError("Streaming speech requires the MiMo provider")
    if not config["base_url"] or not config["model"]:
        raise VoiceAPIError("Configure the API base URL and model in Voice settings")
    messages = []
    instructions = config["instructions"]
    if config["speed"] != 1:
        instructions += " Speak at " + str(config["speed"]) + " times normal speed."
    if instructions.strip():
        messages.append({"role": "user", "content": instructions})
    messages.append({"role": "assistant", "content": text})
    headers = {"Authorization": "Bearer " + config["api_key"]} if config["api_key"] else {}
    payload = {"model": config["model"], "messages": messages, "stream": True,
               "audio": {"format": "pcm16", "voice": config["voice"]}}
    received = 0
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
            async with client.stream("POST", config["base_url"] + "/chat/completions",
                                     headers=headers, json=payload) as response:
                if not response.is_success:
                    raise VoiceAPIError("Voice provider returned HTTP " + str(response.status_code))
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue  # SSE keep-alive and blank separators carry no audio.
                    body = line[5:].strip()
                    if body == "[DONE]":
                        break
                    if not body:
                        continue
                    try:
                        event = json.loads(body)
                    except ValueError:
                        raise VoiceAPIError("Invalid MiMo speech stream") from None
                    choices = event.get("choices") if isinstance(event, dict) else None
                    if not choices:
                        continue  # The final usage frame repeats the id without any audio.
                    delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
                    audio = delta.get("audio") if isinstance(delta, dict) else None
                    encoded = audio.get("data") if isinstance(audio, dict) else None
                    if not isinstance(encoded, str) or not encoded:
                        continue  # Role, reasoning and empty audio frames precede the samples.
                    try:
                        chunk = base64.b64decode(encoded, validate=True)
                    except (ValueError, binascii.Error):
                        raise VoiceAPIError("Invalid MiMo speech stream") from None
                    received += len(chunk)
                    if received > STREAM_LIMIT:
                        raise VoiceAPIError("Voice provider response exceeds size limit")
                    yield chunk
    except httpx.HTTPError as error:
        raise VoiceAPIError("Voice provider connection failed or timed out") from error
