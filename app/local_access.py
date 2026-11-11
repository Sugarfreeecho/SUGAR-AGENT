"""本机访问令牌。

目的：把"真 UI"和"本机随便一个进程"分开，至少做到
- 跨站页面无法替用户建/删会话（默认拦截）；
- 开启严格模式后，本机写操作必须带令牌。
"""
from __future__ import annotations

import os
import secrets
import threading
from pathlib import Path

TOKEN_HEADER = "x-myagent-local-token"
COOKIE_NAME = "myagent_local"
_LOOSE_ENV = "MYAGENT_LOCAL_TOKEN_STRICT"
_CACHE: dict[str, str] = {}
_LOCK = threading.Lock()


def state_dir() -> Path:
    override = os.getenv("MYAGENT_SESSION_CONTROL_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        root = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        return root / "SugarAgent" / "session-control"
    return Path(os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "sugaragent" / "session-control"


def token_path() -> Path:
    return state_dir() / "local-ui.token"


def local_token() -> str:
    """进程内缓存；文件只给本用户可读，供本机脚本主动带上。"""
    with _LOCK:
        cached = _CACHE.get("token")
        if cached:
            return cached
        path = token_path()
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            value = ""
        if not value:
            value = secrets.token_urlsafe(32)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value + "\n", encoding="utf-8")
                os.chmod(path, 0o600)
            except OSError:
                pass
        _CACHE["token"] = value
        return value


def reset_cache() -> None:
    with _LOCK:
        _CACHE.clear()


def strict_enabled() -> bool:
    return os.getenv(_LOOSE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def presented_token(headers, cookies=None) -> str:
    value = str(headers.get(TOKEN_HEADER) or "").strip() if headers is not None else ""
    if value:
        return value
    if cookies:
        try:
            return str(cookies.get(COOKIE_NAME) or "").strip()
        except Exception:
            return ""
    return ""


def check_request(method: str, path: str, headers, cookies=None) -> str:
    """返回空串表示放行，否则返回拒绝原因。"""
    if str(method or "").upper() in {"GET", "HEAD", "OPTIONS"}:
        return ""
    if not str(path or "").startswith("/sessions"):
        return ""
    token = presented_token(headers, cookies)
    if token:
        return "" if secrets.compare_digest(token, local_token()) else "local_token_mismatch"
    site = str(headers.get("sec-fetch-site") or "").strip().lower() if headers is not None else ""
    origin = str(headers.get("origin") or "").strip() if headers is not None else ""
    if site in {"cross-site", "same-site"}:
        return "local_cross_site_blocked"
    if strict_enabled() and (origin or site):
        return "local_token_required"
    return ""
