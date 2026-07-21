from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str) -> frozenset[str]:
    return frozenset(
        value.strip()
        for value in os.getenv(name, "").split(",")
        if value.strip()
    )


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class FeishuConfig:
    enabled: bool
    app_id: str
    app_secret: str
    state_dir: Path
    allowed_open_ids: frozenset[str] = frozenset()
    allowed_chat_ids: frozenset[str] = frozenset()
    group_require_mention: bool = True
    session_scope: str = "chat"
    response_timeout_seconds: int = 7200
    max_reply_chars: int = 3500

    @classmethod
    def from_env(cls, project_root: Path) -> "FeishuConfig":
        configured_dir = os.getenv("FEISHU_STATE_DIR", "").strip()
        state_dir = (
            Path(configured_dir).expanduser()
            if configured_dir
            else Path(project_root) / ".myagent" / "feishu"
        )
        scope = os.getenv("FEISHU_SESSION_SCOPE", "chat").strip().lower()
        if scope not in {"chat", "thread"}:
            scope = "chat"
        return cls(
            enabled=_bool_env("FEISHU_ENABLED", False),
            app_id=os.getenv("FEISHU_APP_ID", "").strip(),
            app_secret=os.getenv("FEISHU_APP_SECRET", "").strip(),
            state_dir=state_dir,
            allowed_open_ids=_csv_env("FEISHU_ALLOWED_OPEN_IDS"),
            allowed_chat_ids=_csv_env("FEISHU_ALLOWED_CHAT_IDS"),
            group_require_mention=_bool_env("FEISHU_GROUP_REQUIRE_MENTION", True),
            session_scope=scope,
            response_timeout_seconds=_int_env(
                "FEISHU_RESPONSE_TIMEOUT_SEC", 7200, 60, 86400
            ),
            max_reply_chars=_int_env("FEISHU_MAX_REPLY_CHARS", 3500, 500, 8000),
        )

    def validate(self) -> None:
        if not self.enabled:
            return
        missing = []
        if not self.app_id:
            missing.append("FEISHU_APP_ID")
        if not self.app_secret:
            missing.append("FEISHU_APP_SECRET")
        if missing:
            raise ValueError(
                "Feishu is enabled but required configuration is missing: "
                + ", ".join(missing)
            )
