"""把各部件装成一台运行时（Core 的唯一装配点）。"""
from __future__ import annotations

import os
from typing import Any, Iterable

from .admission import Admission
from .config import Config
from .delivery import DeliveryQueue
from .opstore import OpStore
from .prompts import PromptRegistry
from .quota import quota_for
from .runtime import TransportRuntime
from .sessionmap import HostPort, SessionMap
from .storage import JsonStore


def create_runtime(
    config: Config,
    host: HostPort,
    adapters: dict[str, Any] | None = None,
    *,
    state_dir: str | None = None,
    console: Any = None,
) -> TransportRuntime:
    base = state_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "state")
    base = os.path.abspath(base)
    os.makedirs(base, exist_ok=True)

    adapters = adapters or {}
    quota_kinds = {cfg.quota for cfg in config.channels.values()} or {"none"}
    quota = quota_for("window10") if "window10" in quota_kinds else quota_for("rate" if "rate" in quota_kinds else "none")

    admission = Admission(
        enabled_channels=config.enabled_channels(),
        allowed_principals=config.allowed_principals(),
        allowed_groups=config.allowed_groups(),
        group_members=config.group_members(),
    )
    delivery = DeliveryQueue(
        lambda channel: _sender_for(channel, adapters),
        max_attempts=int(config.delivery.get("max_attempts") or 3),
        backoff=config.delivery.get("backoff") or (0.5, 2.0, 8.0),
        sleeper=lambda _seconds: None,  # 宿主轮询里不等；退避交给 Adapter
        readback=bool(config.delivery.get("readback", True)),
    )
    session_map = SessionMap(JsonStore(os.path.join(base, "sessions.json")), host, scope=config.session_scope)
    session_map.defaults = config.defaults
    runtime = TransportRuntime(
        host=host,
        admission=admission,
        sessions=session_map,
        ops=OpStore(JsonStore(os.path.join(base, "ops.json"))),
        prompts=PromptRegistry(),
        quota=quota,
        delivery=delivery,
        adapters=adapters,
        console=console,
    )
    runtime.defaults = config.defaults
    return runtime


def _sender_for(channel: str, adapters: dict[str, Any]) -> Any:
    adapter = adapters.get(channel)
    if adapter is None:
        raise RuntimeError(f"没有注册通道适配器：{channel}")
    return adapter


def build_adapters(config: Config) -> dict[str, Any]:
    """按 config 里启用的通道装配 Adapter。目前只有飞书（复用 feishu-transport 的连接方式）。"""
    adapters: dict[str, Any] = {}
    feishu_cfg = config.channels.get("feishu")
    if feishu_cfg is not None and feishu_cfg.enabled:
        from .channels.feishu import build_channel

        adapters["feishu"] = build_channel()
    wechat_cfg = config.channels.get("wechat")
    if wechat_cfg is not None and wechat_cfg.enabled:
        from .channels.sidecar import SidecarChannel, SidecarSpec
        from .models import Capabilities

        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sidecar", "wechat.mjs")
        adapters["wechat"] = SidecarChannel(
            SidecarSpec(
                name="wechat",
                script=os.path.abspath(script),
                capabilities=Capabilities(
                    text=True, markdown=False, threads=False, mentions=False,
                    media_in=frozenset({"image", "file", "voice"}), media_out=frozenset({"image", "file"}),
                    proactive=True, group=True, quota="window10",
                ),
            )
        )
    qq_cfg = config.channels.get("qq")
    if qq_cfg is not None and qq_cfg.enabled:
        from .channels.sidecar import SidecarChannel, SidecarSpec
        from .models import Capabilities

        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sidecar", "qq.mjs")
        adapters["qq"] = SidecarChannel(
            SidecarSpec(
                name="qq",
                script=os.path.abspath(script),
                capabilities=Capabilities(
                    text=True, markdown=False, threads=False, mentions=False,
                    media_in=frozenset({"image", "file", "voice"}), media_out=frozenset({"image", "file"}),
                    proactive=True, group=False, quota="rate",  # 与 dsh-qq 一致：只做私聊
                ),
            )
        )
    return adapters
