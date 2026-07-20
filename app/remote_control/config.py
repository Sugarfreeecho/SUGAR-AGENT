from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class RemoteControlConfig:
    enabled: bool
    state_dir: Path
    bootstrap_token: str = ""
    pairing_ttl_seconds: int = 600
    idempotency_ttl_seconds: int = 86400
    max_frame_bytes: int = 256 * 1024
    outbound_queue_size: int = 1000
    loopback_pairing_only: bool = True
    allowed_origins: tuple[str, ...] = ()

    @classmethod
    def from_env(cls, project_root: Path) -> "RemoteControlConfig":
        configured_dir = os.getenv("MYAGENT_REMOTE_CONTROL_STATE_DIR", "").strip()
        state_dir = (
            Path(configured_dir).expanduser()
            if configured_dir
            else Path(project_root) / ".myagent" / "remote-control"
        )
        origins = tuple(
            item.strip().rstrip("/")
            for item in os.getenv("MYAGENT_REMOTE_CONTROL_ALLOWED_ORIGINS", "").split(",")
            if item.strip()
        )
        return cls(
            enabled=_bool_env("MYAGENT_REMOTE_CONTROL_ENABLED", False),
            state_dir=state_dir,
            bootstrap_token=os.getenv("MYAGENT_REMOTE_CONTROL_BOOTSTRAP_TOKEN", "").strip(),
            pairing_ttl_seconds=_int_env(
                "MYAGENT_REMOTE_CONTROL_PAIRING_TTL_SEC", 600, 60, 3600
            ),
            idempotency_ttl_seconds=_int_env(
                "MYAGENT_REMOTE_CONTROL_IDEMPOTENCY_TTL_SEC", 86400, 300, 604800
            ),
            max_frame_bytes=_int_env(
                "MYAGENT_REMOTE_CONTROL_MAX_FRAME_BYTES", 256 * 1024, 4096, 4 * 1024 * 1024
            ),
            outbound_queue_size=_int_env(
                "MYAGENT_REMOTE_CONTROL_OUTBOUND_QUEUE", 1000, 50, 10000
            ),
            loopback_pairing_only=_bool_env(
                "MYAGENT_REMOTE_CONTROL_LOOPBACK_PAIRING_ONLY", True
            ),
            allowed_origins=origins,
        )

