"""Validated, write-only credentials and deployment choices for voice providers."""
from copy import deepcopy
from urllib.parse import urlsplit

DEFAULTS = {
    "enabled": False, "language": "auto",
    "asr": {"provider": "openai-compatible", "base_url": "", "model": "", "api_key": ""},
    "tts": {"enabled": False, "provider": "mimo", "base_url": "https://api.xiaomimimo.com/v1",
            "model": "mimo-v2.5-tts", "api_key": "", "voice": "mimo_default", "speed": 1.0, "instructions": "",
            "autoRead": False},
}


def merge_settings(current, patch):
    if not isinstance(patch, dict) or set(patch) - set(DEFAULTS):
        raise ValueError("Invalid voice settings")
    result = deepcopy(current)
    for key, value in patch.items():
        if key in {"asr", "tts"}:
            if not isinstance(value, dict) or set(value) - set(DEFAULTS[key]):
                raise ValueError("Invalid provider settings")
            for field, content in value.items():
                if field == "api_key" and content == "":
                    continue  # Empty password fields preserve existing credentials.
                result[key][field] = "" if field == "api_key" and content is None else content
        else:
            result[key] = value
    if not isinstance(result["enabled"], bool) or not isinstance(result["tts"]["enabled"], bool):
        raise ValueError("enabled must be boolean")
    if not isinstance(result["tts"]["autoRead"], bool):
        raise ValueError("autoRead must be boolean")
    if result["language"] not in ("auto", "zh", "en", "yue", "ja", "ko"):
        raise ValueError("Unsupported language")
    if result["asr"]["provider"] not in ("local", "openai-compatible", "mimo") or result["tts"]["provider"] not in ("openai-compatible", "mimo"):
        raise ValueError("Unsupported provider")
    for section in ("asr", "tts"):
        for field in ("base_url", "model", "api_key", *(["voice", "instructions"] if section == "tts" else [])):
            content = result[section][field]
            if not isinstance(content, str) or len(content) > (4096 if field == "api_key" else 2048):
                raise ValueError("Invalid " + field)
            if field in {"api_key", "base_url"} and any(ord(char) < 32 for char in content):
                raise ValueError("Invalid " + field)
        url = result[section]["base_url"].strip().rstrip("/")
        parsed = urlsplit(url)
        if url and (parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("API base URL must be an HTTP(S) address without credentials or query parameters")
        result[section]["base_url"] = url
    speed = result["tts"]["speed"]
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not .25 <= speed <= 4:
        raise ValueError("Speech speed must be between 0.25 and 4")
    return result


def public_settings(settings):
    result = deepcopy(settings)
    for section in ("asr", "tts"):
        result[section]["api_key_set"] = bool(result[section].pop("api_key"))
    return result
