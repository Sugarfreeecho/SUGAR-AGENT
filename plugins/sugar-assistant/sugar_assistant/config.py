"""配置：一个文件管多通道；密钥只从环境变量读，不进配置文件。

权限不在这里配：身份四轴由 `levels.py` 按当轮身份现算，
配置里只有"谁算白名单/白名单群"这类判定证据。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import paths

SECRET_MARKERS = ("secret", "token", "password", "apikey", "api_key")


@dataclass
class ChannelConfig:
    name: str
    enabled: bool = False
    account: str = "default"
    quota: str = "none"
    allow: list[str] = field(default_factory=list)        # 白名单个人（UID / open_id）
    allow_groups: list[str] = field(default_factory=list)  # 白名单群（整群提权到 private 档）
    group_members: dict[str, int] = field(default_factory=dict)  # 已知群人数；未知则不填

    def to_json(self) -> dict:
        return {
            "enabled": self.enabled,
            "account": self.account,
            "quota": self.quota,
            "allow": list(self.allow),
            "allow_groups": list(self.allow_groups),
            "group_members": dict(self.group_members),
        }


@dataclass
class Config:
    enabled: bool = True
    session_scope: str = "chat"
    channels: dict[str, ChannelConfig] = field(default_factory=dict)
    principals: dict[str, str] = field(default_factory=dict)  # principal key → 备注（谁是主人）
    delivery: dict = field(default_factory=lambda: {"max_attempts": 3, "backoff": [0.5, 2.0, 8.0], "readback": True})
    # 新会话默认值：workspace / model 各自可跟随宿主或手动指定
    defaults: dict = field(default_factory=lambda: {
        "workspace": {"mode": "host", "path": ""},
        "model": {"mode": "host", "profile_id": ""},
    })

    # ------------------------------------------------------------------ 载入
    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> "Config":
        # 默认读宿主分配的 data 目录；首次启动会把插件目录里的旧 config.json 搬过去
        paths.migrate_legacy()
        target = Path(path) if path else Path(paths.config_path())
        raw: dict = {}
        if target.exists():
            with open(target, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            _reject_secrets(raw, str(target))
        channels = {}
        for name, item in (raw.get("channels") or {}).items():
            if isinstance(item, dict):
                channels[str(name)] = ChannelConfig(
                    name=str(name),
                    enabled=bool(item.get("enabled", False)),
                    account=str(item.get("account") or "default"),
                    quota=str(item.get("quota") or "none"),
                    allow=[str(x) for x in (item.get("allow") or [])],
                    allow_groups=[str(x) for x in (item.get("allow_groups") or [])],
                    group_members={str(k): int(v) for k, v in (item.get("group_members") or {}).items()},
                )
        return cls(
            enabled=bool(raw.get("enabled", True)),
            session_scope=str(raw.get("session_scope") or "chat"),
            channels=channels,
            principals=dict(raw.get("principals") or {}),
            delivery={**{"max_attempts": 3, "backoff": [0.5, 2.0, 8.0], "readback": True}, **(raw.get("delivery") or {})},
            defaults={**{"workspace": {"mode": "host", "path": ""}, "model": {"mode": "host", "profile_id": ""}},
                      **(raw.get("defaults") or {})},
        )

    # ------------------------------------------------------------------ 查询
    def enabled_channels(self) -> set[str]:
        return {name for name, cfg in self.channels.items() if cfg.enabled}

    def allowed_principals(self) -> set[str]:
        """白名单个人：`channel:user_id` 与裸 user_id 两种写法都认。"""
        keys: set[str] = set()
        for name, cfg in self.channels.items():
            for entry in cfg.allow:
                keys.add(entry)
                if ":" not in entry:
                    keys.add(f"{name}:{entry}")
        return keys

    def allowed_groups(self) -> set[str]:
        groups: set[str] = set()
        for cfg in self.channels.values():
            groups.update(cfg.allow_groups)
        return groups

    def group_members(self) -> dict[str, int]:
        members: dict[str, int] = {}
        for cfg in self.channels.values():
            members.update(cfg.group_members)
        return members


def _reject_secrets(raw: dict, path: str) -> None:
    """配置文件里出现明文密钥就直接拒绝启动：这类错误一旦提交进仓库就收不回来。"""

    def walk(node, trail: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                lower = str(key).lower()
                if any(marker in lower for marker in SECRET_MARKERS) and isinstance(value, str) and value.strip():
                    raise ValueError(f"{path}: 字段 {trail}/{key} 看起来是明文密钥；请改为环境变量（见 README）")
                walk(value, f"{trail}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{trail}[{index}]")

    walk(raw, "")
