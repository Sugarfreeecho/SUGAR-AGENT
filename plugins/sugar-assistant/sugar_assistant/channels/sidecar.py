"""Node sidecar 通道：把「已经写好的连接层」当子进程用，不重写协议。

协议是 JSON Lines（一行一个 JSON），双向：

    sidecar → Core
      {"type":"ready"}
      {"type":"inbound","peerId":..,"chatId":..,"groupId":..,"messageId":..,
       "contextToken":..,"text":..,"receivedAt":..}
      {"type":"sent","id":<请求 id>,"ok":true,"serverMessageId":..}
      {"type":"sent","id":<请求 id>,"ok":false,"error":".."}

    Core → sidecar
      {"type":"send","id":..,"to":..,"text":..,"contextToken":..}
      {"type":"stop"}

为什么用子进程而不是移植：微信那套长轮询、context_token、10 条窗口已经在
`dsh-wechat/packages/core` 里跑通过；重写一遍等于重新踩一遍协议坑。
"""
from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from ..models import Capabilities, ChannelId, ConversationRef, Delivery, Inbound, Principal, SendOutcome, SendResult
from .base import AdapterError, InboundSink

LOG = logging.getLogger("sugar_assistant.sidecar")


@dataclass
class SidecarSpec:
    name: str
    script: str = ""
    command: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    capabilities: Capabilities = field(default_factory=Capabilities)
    send_timeout: float = 20.0
    node: str = "node"

    def argv(self) -> list[str]:
        return list(self.command) or [self.node, self.script]


class SidecarChannel:
    """一个通道 = 一个 Node 子进程 + 一套 JSON Lines。"""

    def __init__(self, spec: SidecarSpec) -> None:
        self.spec = spec
        self.id = spec.name
        self.capabilities = spec.capabilities
        self._proc: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._sink: InboundSink | None = None
        self._loop = None
        self._waiters: dict[str, queue.Queue] = {}
        self._lock = threading.Lock()
        self._seq = 0
        self.started = False
        self.last_error = ""
        self.sent = 0
        self.failed = 0
        self._stop = threading.Event()

    # ------------------------------------------------------------------ 生命周期
    async def start(self, sink: InboundSink) -> None:
        import asyncio

        self._sink = sink
        self._loop = asyncio.get_running_loop()
        env = {**os.environ, **self.spec.env}
        try:
            self._proc = subprocess.Popen(
                self.spec.argv(),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", bufsize=1, env=env,
            )
        except FileNotFoundError as exc:
            raise AdapterError(self.id, f"启动 sidecar 失败（找不到 {self.spec.node}）：{exc}") from exc
        self._reader = threading.Thread(target=self._read_loop, name=f"sugar-{self.id}-reader", daemon=True)
        self._reader.start()
        threading.Thread(target=self._drain_stderr, name=f"sugar-{self.id}-stderr", daemon=True).start()
        self.started = True

    async def stop(self) -> None:
        self._stop.set()
        proc, self._proc = self._proc, None
        self.started = False
        if proc is None:
            return
        try:
            self._write({"type": "stop"})
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        finally:
            # 关掉管道，否则测试与长跑进程都会攒下未关闭的文件句柄
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    if stream is not None:
                        stream.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------ 入站
    def _read_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            for line in proc.stdout:
                if self._stop.is_set():
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                try:
                    self._dispatch(message)
                except Exception as exc:  # 单条坏消息不能带走整个读循环
                    LOG.warning("%s 分发失败：%s", self.id, exc)
        except Exception as exc:
            if not self._stop.is_set():
                self.last_error = f"读取 sidecar 输出失败：{exc}"
                LOG.warning("%s 读循环退出：%s", self.id, exc)

    def _dispatch(self, message: dict) -> None:
        kind = str(message.get("type") or "")
        if kind == "sent":
            request_id = str(message.get("id") or "")
            waiter = self._waiters.pop(request_id, None)
            if waiter is not None:
                waiter.put(message)
            return
        if kind == "ready":
            LOG.info("%s sidecar 就绪", self.id)
            return
        if kind == "recv":
            # 每个入站都留痕：出问题时能数清"收到几条"，而不是靠猜
            LOG.info("%s 入站 message=%s chars=%s chat=%s",
                     self.id, str(message.get("messageId") or "")[-12:],
                     message.get("chars"), str(message.get("chatId") or "")[-8:])
            return
        if kind == "poll":
            LOG.info("%s 轮询 chat=%s items=%s", self.id, message.get("chat"), message.get("items"))
            return
        if kind == "error":
            self.last_error = str(message.get("error") or message.get("message") or "sidecar error")
            LOG.warning("%s sidecar 报错：%s", self.id, self.last_error)
            return
        if kind != "inbound":
            return
        inbound = self._to_inbound(message)
        if inbound is None:
            return
        sink, loop = self._sink, self._loop
        if sink is None or loop is None:
            return
        import asyncio

        asyncio.run_coroutine_threadsafe(sink(inbound), loop)

    def _to_inbound(self, message: dict) -> Inbound | None:
        peer = str(message.get("peerId") or message.get("from") or "")
        text = str(message.get("text") or "")
        chat = str(message.get("chatId") or message.get("groupId") or peer)
        if not peer or not text:
            return None
        return Inbound(
            channel=ChannelId(self.id, str(message.get("account") or "default")),
            conversation=ConversationRef(chat_id=chat, kind="group" if message.get("groupId") else "p2p"),
            sender=Principal(self.id, peer),
            message_id=str(message.get("messageId") or f"{peer}:{message.get('receivedAt') or time.time()}"),
            text=text,
            raw={"contextToken": message.get("contextToken"), "self": bool(message.get("self")),
                 "chatName": str(message.get("chatName") or "")},
        )

    # ------------------------------------------------------------------ 出站
    def send(self, delivery: Delivery) -> SendResult:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            self.failed += 1
            return SendResult(SendOutcome.UNREACHABLE, "sidecar 未运行")
        request_id = self._next_id()
        waiter: queue.Queue = queue.Queue(maxsize=1)
        self._waiters[request_id] = waiter
        started = time.perf_counter()
        payload = {
            "type": "send",
            "id": request_id,
            "to": delivery.conversation.chat_id,
            "text": delivery.text,
        }
        card = (delivery.meta or {}).get("card")
        if card:
            payload.update({"type": "card", "card": card})
        meta = delivery.meta or {}
        token = meta.get("context_token") or meta.get("contextToken")
        if token:
            payload["contextToken"] = token
        try:
            self._write(payload)
        except Exception as exc:
            self._waiters.pop(request_id, None)
            self.failed += 1
            return SendResult(SendOutcome.UNREACHABLE, f"写入 sidecar 失败：{exc}")
        try:
            result = waiter.get(timeout=self.spec.send_timeout)
        except queue.Empty:
            self._waiters.pop(request_id, None)
            self.failed += 1
            return SendResult(SendOutcome.UNREACHABLE, "sidecar 未回执")
        total_ms = round((time.perf_counter() - started) * 1000)
        api_ms = result.get("apiMs")
        timing = f"api={api_ms}ms pipe={total_ms - int(api_ms)}ms" if isinstance(api_ms, int) else f"total={total_ms}ms"
        if result.get("ok"):
            self.sent += 1
            return SendResult(SendOutcome.ACKED, timing)
        detail = str(result.get("error") or "发送失败")
        self.failed += 1
        self.last_error = detail
        return SendResult(SendOutcome.UNREACHABLE, self.last_error)

    def verify(self, delivery: Delivery) -> SendResult:
        return SendResult(SendOutcome.UNREACHABLE, "sidecar 通道不做回读确认")

    def health(self) -> dict:
        proc = self._proc
        return {
            "channel": self.id,
            "started": self.started,
            "alive": bool(proc and proc.poll() is None),
            "sent": self.sent,
            "failed": self.failed,
            "last_error": self.last_error,
        }

    # ------------------------------------------------------------------ 内部
    def _write(self, payload: dict) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise RuntimeError("sidecar 未启动")
        with self._lock:
            proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            proc.stdin.flush()

    def _next_id(self) -> str:
        with self._lock:
            self._seq += 1
            return f"req-{self._seq}"

    def _drain_stderr(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        for line in proc.stderr:
            line = line.strip()
            if line:
                # lark 的连接状态只走 stderr：把它提到 info，日志里能看出"连上没连上"
                if "connected" in line.lower() or "error" in line.lower():
                    LOG.info("%s: %s", self.id, line[:300])
                else:
                    LOG.debug("%s stderr: %s", self.id, line[:300])
