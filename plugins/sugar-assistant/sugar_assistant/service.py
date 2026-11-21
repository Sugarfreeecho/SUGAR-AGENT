"""把 Core 与事件转接装成一个对 Adapter 友好的门面。

Adapter 只需要 `await handle(inbound)`：它会
  1. 在线程里跑同步的 Core（准入 / 幂等 / 会话 / 起一轮）；
  2. 起一轮成功后挂一条订阅，把宿主事件翻译成出站投递或审批提示。
"""
from __future__ import annotations

import asyncio
import logging

from .models import Inbound
from .relay import EventRelay
from .runtime import HandleResult, TransportRuntime
from .commands import parse_command

LOG = logging.getLogger("sugar_assistant.service")


class SugarAssistantService:
    def __init__(self, runtime: TransportRuntime, *, relay_timeout: float = 600.0,
                 merge_window_ms: int = 0) -> None:
        self.runtime = runtime
        self.relay = EventRelay(runtime, timeout=relay_timeout)
        self._tasks: set[asyncio.Task] = set()
        self.merge_window = max(0, int(merge_window_ms)) / 1000.0
        self._buffers: dict[str, dict] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._relay_tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------ 入站
    async def handle(self, inbound: Inbound) -> HandleResult:
        # 命令必须立即处理：合并窗口会让 /help 这类交互白等 0.3 秒
        if self.merge_window and not parse_command(inbound.text):
            return await self._handle_batched(inbound)
        result = await asyncio.to_thread(self.runtime.handle_inbound, inbound)
        if not result.ok and result.status not in {"duplicate"}:
            LOG.warning("入站未处理：status=%s reason=%s", result.status, result.reason or "-")
        if result.reply:
            await asyncio.to_thread(self.runtime.reply_now, inbound, result.reply)
        if result.ok and result.session_id:
            self._spawn_relay(result.session_id)
        return result

    async def _handle_batched(self, inbound: Inbound) -> HandleResult:
        """0.8s 合并：同会话连续几条合成一轮，避免上下文被切成一句一段。"""
        key = f"{inbound.channel.channel}:{inbound.conversation.chat_id}"
        buffer = self._buffers.get(key)
        if buffer is not None:
            buffer["texts"].append(inbound.text)
            buffer["last"] = inbound
            return HandleResult(ok=True, status="buffered")
        buffer = {"texts": [inbound.text], "first": inbound, "last": inbound}
        self._buffers[key] = buffer
        task = asyncio.create_task(self._flush_buffer(key))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return HandleResult(ok=True, status="buffered")

    async def _flush_buffer(self, key: str) -> None:
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:  # 同一会话串行提交，避免后一批先到把顺序颠倒
            await self._flush_locked(key)

    async def _flush_locked(self, key: str) -> None:
        try:
            await asyncio.sleep(self.merge_window)
            buffer = self._buffers.pop(key, None)
            if not buffer:
                return
            first = buffer["first"]
            merged = dict(first.__dict__)
            parts = [t for t in buffer["texts"] if t]
            merged["text"] = "\n\n".join(parts)
            inbound = Inbound(**merged)
            self.runtime._log("merge", conversation=key, count=len(parts),
                              message_ids=[getattr(first, "message_id", "")])
            result = await asyncio.to_thread(self.runtime.handle_inbound, inbound)
            if not result.ok and result.status != "duplicate":
                LOG.warning("合并后的消息未处理：status=%s reason=%s", result.status, result.reason or "-")
            if result.reply:
                await asyncio.to_thread(self.runtime.reply_now, inbound, result.reply)
            if result.ok and result.session_id:
                self._spawn_relay(result.session_id)
        except Exception:
            LOG.exception("合并消息处理失败（key=%s）", key)
            self.runtime._log("flush_error", conversation=key)

    def _spawn_relay(self, session_id: str) -> None:
        previous = self._relay_tasks.get(session_id)
        if previous is not None and not previous.done():
            previous.cancel()  # 同一会话只保留一个订阅者，避免重复投递
        self._relay_tasks[session_id] = task = asyncio.create_task(
            self._relay(session_id), name=f"sugar-relay-{session_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        task.add_done_callback(lambda _t: self._relay_tasks.pop(session_id, None))

    async def _relay(self, session_id: str) -> None:
        try:
            reason = await self.relay.consume(session_id)
            if reason == "timeout":
                LOG.debug("会话 %s 的订阅超时结束", session_id)
            if self.relay.delivered == 0:
                LOG.info("会话 %s 这一轮没有消息转发到通道（reason=%s）", session_id[:8], reason)
        except Exception as exc:  # 订阅失败不该影响其它会话
            LOG.warning("会话 %s 的事件订阅失败：%s", session_id, exc)

    # ------------------------------------------------------------------ 生命周期
    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()


async def start_channels(adapters: dict, sink) -> list[tuple[str, str]]:
    """逐个启动通道；单个通道起不来只记录，不拖垮插件。

    返回 [(通道名, 错误)]，空列表表示全部成功。没有凭据时飞书会在这里报缺配置，
    这是**预期降级**，不是加载失败。
    """
    failures: list[tuple[str, str]] = []
    for name, adapter in adapters.items():
        try:
            await adapter.start(sink)
        except Exception as exc:
            LOG.warning("通道 %s 启动失败：%s", name, exc)
            failures.append((name, str(exc)))
    return failures