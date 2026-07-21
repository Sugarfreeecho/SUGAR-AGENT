from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
import time
from typing import Any, Callable

from remote_control.service import RemoteControlError, SessionControlService
from remote_control.store import DevicePrincipal

from .config import FeishuConfig
from .models import FeishuInboundMessage, parse_message_event
from .store import FeishuStateStore


logger = logging.getLogger(__name__)


class FeishuSDKTransport:
    """Thin lazy wrapper around Feishu's official ``lark-oapi`` SDK."""

    def __init__(self, config: FeishuConfig):
        self.config = config
        self._lark: Any = None
        self._api_client: Any = None
        self._ws_client: Any = None

    def build(self, event_callback: Callable[[Any], None]) -> None:
        try:
            import lark_oapi as lark
            from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody
        except ImportError as exc:
            raise RuntimeError(
                "FEISHU_ENABLED=1 requires the official 'lark-oapi' package"
            ) from exc
        self._lark = lark
        self._ReplyMessageRequest = ReplyMessageRequest
        self._ReplyMessageRequestBody = ReplyMessageRequestBody
        self._api_client = (
            lark.Client.builder()
            .app_id(self.config.app_id)
            .app_secret(self.config.app_secret)
            .log_level(lark.LogLevel.INFO)
            .build()
        )
        handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(event_callback)
            .build()
        )
        self._ws_client = lark.ws.Client(
            self.config.app_id,
            self.config.app_secret,
            event_handler=handler,
            log_level=lark.LogLevel.INFO,
        )

    def run_forever(self) -> None:
        if self._ws_client is None:
            raise RuntimeError("Feishu SDK transport was not built")
        self._ws_client.start()

    def stop(self) -> None:
        """Best-effort stop for the SDK's blocking WebSocket client."""
        if self._ws_client is None:
            return
        try:
            from lark_oapi.ws import client as ws_client_module

            disconnect = getattr(self._ws_client, "_disconnect", None)
            if callable(disconnect):
                asyncio.run_coroutine_threadsafe(disconnect(), ws_client_module.loop)
            ws_client_module.loop.call_soon_threadsafe(ws_client_module.loop.stop)
        except Exception:
            logger.debug("Feishu WebSocket stop failed", exc_info=True)

    def reply_text(self, message_id: str, text: str, *, uuid_value: str) -> None:
        if self._api_client is None:
            raise RuntimeError("Feishu API client is not initialized")
        content = json.dumps({"text": str(text or "")}, ensure_ascii=False)
        body = (
            self._ReplyMessageRequestBody.builder()
            .content(content)
            .msg_type("text")
            .uuid(uuid_value)
            .build()
        )
        request = (
            self._ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(body)
            .build()
        )
        response = self._api_client.im.v1.message.reply(request)
        if response is None or not response.success():
            code = getattr(response, "code", "unknown")
            msg = getattr(response, "msg", "reply failed")
            raise RuntimeError(f"Feishu reply failed [{code}]: {msg}")


class FeishuTransportAdapter:
    HELP_TEXT = (
        "SugarAgent 飞书命令：\n"
        "• /new [名称]：新建并绑定会话\n"
        "• /session：查看当前会话\n"
        "• /whoami：查看飞书用户与群聊 ID\n"
        "• /stop：停止当前运行\n"
        "• /approve <审批ID>：允许工具执行\n"
        "• /reject <审批ID>：拒绝工具执行\n"
        "• /help：显示帮助\n"
        "普通文本会发送到当前会话；会话运行中时会作为 append steer 排队。"
    )

    def __init__(
        self,
        config: FeishuConfig,
        service: SessionControlService,
        state_store: FeishuStateStore,
        *,
        sdk_transport: Any | None = None,
    ):
        self.config = config
        self.service = service
        self.state_store = state_store
        self.sdk = sdk_transport or FeishuSDKTransport(config)
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._event_thread: threading.Thread | None = None
        self._ws_thread: threading.Thread | None = None
        self._loop_ready = threading.Event()
        self._stopping = threading.Event()

    def start(self) -> None:
        self.config.validate()
        if not self.config.enabled:
            return
        if self._event_thread and self._event_thread.is_alive():
            return
        self._stopping.clear()
        self._loop_ready.clear()

        def event_loop_main() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._event_loop = loop
            self._loop_ready.set()
            loop.run_forever()
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

        self._event_thread = threading.Thread(
            target=event_loop_main,
            name="feishu-events",
            daemon=True,
        )
        self._event_thread.start()
        if not self._loop_ready.wait(timeout=5.0) or self._event_loop is None:
            raise RuntimeError("Feishu event loop failed to start")
        try:
            self.sdk.build(self._on_sdk_event)
        except Exception:
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)
            self._event_thread.join(timeout=5.0)
            self._event_loop = None
            self._event_thread = None
            raise

        def ws_main() -> None:
            try:
                self.sdk.run_forever()
            except Exception:
                if not self._stopping.is_set():
                    logger.exception("Feishu long connection stopped unexpectedly")

        self._ws_thread = threading.Thread(
            target=ws_main,
            name="feishu-websocket",
            daemon=True,
        )
        self._ws_thread.start()
        logger.info("Feishu transport adapter started")

    def stop(self) -> None:
        self._stopping.set()
        try:
            self.sdk.stop()
        finally:
            if self._event_loop and self._event_loop.is_running():
                self._event_loop.call_soon_threadsafe(self._event_loop.stop)
            if self._event_thread:
                self._event_thread.join(timeout=5.0)
        logger.info("Feishu transport adapter stopped")

    def _on_sdk_event(self, data: Any) -> None:
        loop = self._event_loop
        if loop is None or not loop.is_running() or self._stopping.is_set():
            logger.warning("Dropping Feishu event because adapter loop is unavailable")
            return
        future = asyncio.run_coroutine_threadsafe(self.handle_event(data), loop)

        def report_failure(done: Any) -> None:
            try:
                done.result()
            except Exception:
                logger.exception("Feishu inbound event processing failed")
                try:
                    message_id = parse_message_event(data).message_id
                    self.state_store.release_message(message_id)
                    asyncio.run_coroutine_threadsafe(
                        self._reply(
                            message_id,
                            "消息处理失败，请稍后重新发送。",
                            purpose="processing-failed",
                        ),
                        loop,
                    )
                except Exception:
                    logger.debug("Failed to report Feishu processing error", exc_info=True)

        future.add_done_callback(report_failure)

    def _principal(self, message: FeishuInboundMessage) -> DevicePrincipal:
        identity = message.sender_union_id or message.sender_open_id
        return DevicePrincipal(
            device_id=f"feishu:{identity}",
            name=f"Feishu user {identity}",
            scopes=frozenset({"read", "write", "approvals"}),
            credential_kind="feishu",
        )

    def _admission_error(self, message: FeishuInboundMessage) -> str:
        if not message.message_id or not message.chat_id or not message.sender_open_id:
            return "invalid_event"
        if message.sender_type not in {"user", ""}:
            return "bot_sender"
        if self.config.allowed_open_ids and not (
            {message.sender_open_id, message.sender_union_id} & self.config.allowed_open_ids
        ):
            return "user_not_allowed"
        if self.config.allowed_chat_ids and message.chat_id not in self.config.allowed_chat_ids:
            return "chat_not_allowed"
        if message.is_group and self.config.group_require_mention and not message.mentioned:
            return "mention_required"
        return ""

    async def _reply(self, message_id: str, text: str, *, purpose: str) -> None:
        value = str(text or "").strip() or "（空响应）"
        chunks = [
            value[index : index + self.config.max_reply_chars]
            for index in range(0, len(value), self.config.max_reply_chars)
        ] or ["（空响应）"]
        for index, chunk in enumerate(chunks):
            uuid_value = hashlib.sha256(
                f"{message_id}:{purpose}:{index}:{chunk}".encode("utf-8")
            ).hexdigest()[:32]
            await asyncio.to_thread(
                self.sdk.reply_text,
                message_id,
                chunk,
                uuid_value=uuid_value,
            )

    async def _current_session(
        self, message: FeishuInboundMessage, principal: DevicePrincipal, *, create: bool
    ) -> str:
        key = message.conversation_key(self.config.session_scope)
        sid = await asyncio.to_thread(self.state_store.get_binding, key)
        stale_sid = ""
        if sid:
            try:
                await self.service.execute(principal, "session.get", {"session_id": sid})
                return sid
            except RemoteControlError as exc:
                if exc.code != "session_not_found":
                    raise
                stale_sid = sid
        if not create:
            return ""
        result, _ = await self.service.execute(
            principal,
            "session.create",
            {"name": f"飞书会话 {message.chat_id[-8:]}"},
            idempotency_key=(
                f"feishu-rebind:{key}:{stale_sid}"
                if stale_sid
                else f"feishu-binding:{key}"
            ),
        )
        sid = str(result.get("session_id") or "")
        await asyncio.to_thread(
            self.state_store.bind,
            key,
            sid,
            chat_id=message.chat_id,
            sender_open_id=message.sender_open_id,
        )
        return sid

    async def _new_session(
        self, message: FeishuInboundMessage, principal: DevicePrincipal, name: str
    ) -> str:
        result, _ = await self.service.execute(
            principal,
            "session.create",
            {"name": name or f"飞书会话 {message.chat_id[-8:]}"},
            idempotency_key=f"{message.message_id}:new",
        )
        sid = str(result.get("session_id") or "")
        await asyncio.to_thread(
            self.state_store.bind,
            message.conversation_key(self.config.session_scope),
            sid,
            chat_id=message.chat_id,
            sender_open_id=message.sender_open_id,
        )
        return sid

    async def _relay_run(
        self,
        message: FeishuInboundMessage,
        session_id: str,
        run_ref: dict[str, str],
        ready: asyncio.Event,
        reply_ready: asyncio.Event,
    ) -> None:
        stream = self.service.subscribe(session_id, replay_recent=False)
        next_event = asyncio.create_task(stream.__anext__())
        ready.set()
        deadline = time.monotonic() + self.config.response_timeout_seconds
        notified_approvals: set[str] = set()
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                try:
                    event = await asyncio.wait_for(next_event, timeout=remaining)
                except (asyncio.TimeoutError, StopAsyncIteration):
                    return
                next_event = asyncio.create_task(stream.__anext__())
                if not isinstance(event, dict):
                    continue
                expected_run = str(run_ref.get("run_id") or "")
                event_run = str(event.get("run_id") or event.get("runId") or "")
                if expected_run and event_run and expected_run != event_run:
                    continue
                event_type = str(event.get("type") or "")
                if event_type == "tool_approval_required":
                    approval_id = str(event.get("approval_id") or "")
                    if approval_id and approval_id not in notified_approvals:
                        notified_approvals.add(approval_id)
                        await reply_ready.wait()
                        await self._reply(
                            message.message_id,
                            "需要工具审批：\n"
                            f"{event.get('title') or event.get('tool') or '工具调用'}\n"
                            f"{event.get('message') or ''}\n"
                            f"允许：/approve {approval_id}\n拒绝：/reject {approval_id}",
                            purpose=f"approval:{approval_id}",
                        )
                elif event_type == "final":
                    await reply_ready.wait()
                    await self._reply(
                        message.message_id,
                        str(event.get("content") or ""),
                        purpose=f"final:{expected_run}",
                    )
                    return
                elif event_type in {"error", "run_failed"}:
                    await reply_ready.wait()
                    await self._reply(
                        message.message_id,
                        "运行失败：" + str(event.get("content") or event.get("error") or "未知错误"),
                        purpose=f"error:{expected_run}",
                    )
                    return
                elif event_type == "run_interrupted":
                    await reply_ready.wait()
                    await self._reply(
                        message.message_id,
                        "运行已停止。",
                        purpose=f"interrupted:{expected_run}",
                    )
                    return
        finally:
            next_event.cancel()
            await asyncio.gather(next_event, return_exceptions=True)
            await stream.aclose()

    async def handle_event(self, data: Any) -> None:
        message = parse_message_event(data)
        admission_error = self._admission_error(message)
        if admission_error:
            logger.info(
                "Ignoring Feishu message %s: %s", message.message_id, admission_error
            )
            return
        claimed = await asyncio.to_thread(
            self.state_store.claim_message, message.message_id
        )
        if not claimed:
            logger.info("Ignoring duplicate Feishu message %s", message.message_id)
            return
        if message.message_type not in {"text", "post"} or not message.text:
            await self._reply(
                message.message_id,
                "当前版本只支持文本消息和富文本中的文字。",
                purpose="unsupported",
            )
            return

        principal = self._principal(message)
        text = message.text.strip()
        command, _, argument = text.partition(" ")
        command_lower = command.lower()

        if command_lower in {"/help", "帮助"}:
            await self._reply(message.message_id, self.HELP_TEXT, purpose="help")
            return
        if command_lower in {"/new", "新会话"}:
            sid = await self._new_session(message, principal, argument.strip())
            await self._reply(
                message.message_id, f"已新建并绑定会话：{sid}", purpose="new"
            )
            return
        if command_lower in {"/session", "会话"}:
            sid = await self._current_session(message, principal, create=False)
            await self._reply(
                message.message_id,
                f"当前会话：{sid}" if sid else "当前尚未绑定会话，发送消息后会自动创建。",
                purpose="session",
            )
            return
        if command_lower == "/whoami":
            await self._reply(
                message.message_id,
                "sender_open_id: " + message.sender_open_id + "\n"
                "sender_union_id: " + (message.sender_union_id or "（无）") + "\n"
                "chat_id: " + message.chat_id,
                purpose="whoami",
            )
            return
        if command_lower in {"/stop", "停止"}:
            sid = await self._current_session(message, principal, create=False)
            if not sid:
                await self._reply(message.message_id, "当前没有可停止的会话。", purpose="stop-none")
                return
            await self.service.execute(
                principal,
                "session.interrupt",
                {"session_id": sid, "reason": "feishu_user"},
                idempotency_key=f"{message.message_id}:stop",
            )
            await self._reply(message.message_id, "已请求停止当前运行。", purpose="stop")
            return
        if command_lower in {"/approve", "/reject"}:
            approval_id = argument.strip()
            sid = await self._current_session(message, principal, create=False)
            if not sid or not approval_id:
                await self._reply(
                    message.message_id,
                    "格式：/approve <审批ID> 或 /reject <审批ID>",
                    purpose="approval-format",
                )
                return
            await self.service.execute(
                principal,
                "approval.resolve",
                {
                    "session_id": sid,
                    "approval_id": approval_id,
                    "approve": command_lower == "/approve",
                },
                idempotency_key=f"{message.message_id}:approval",
            )
            await self._reply(
                message.message_id,
                "已允许该工具执行。" if command_lower == "/approve" else "已拒绝该工具执行。",
                purpose="approval-resolved",
            )
            return

        sid = await self._current_session(message, principal, create=True)
        ready = asyncio.Event()
        reply_ready = asyncio.Event()
        run_ref: dict[str, str] = {}
        relay_task = asyncio.create_task(
            self._relay_run(message, sid, run_ref, ready, reply_ready)
        )
        await ready.wait()
        try:
            try:
                result, _ = await self.service.execute(
                    principal,
                    "session.send",
                    {"session_id": sid, "message": text, "ui_message": text},
                    idempotency_key=message.message_id,
                )
            except RemoteControlError as exc:
                if exc.code != "session_busy":
                    raise
                result, _ = await self.service.execute(
                    principal,
                    "session.steer",
                    {
                        "session_id": sid,
                        "message": text,
                        "ui_message": text,
                        "mode": "append",
                        "client_id": message.message_id,
                    },
                    idempotency_key=f"{message.message_id}:steer",
                )
            run_ref["run_id"] = str(result.get("run_id") or "")
            await self._reply(
                message.message_id,
                "已收到，正在处理。",
                purpose="accepted",
            )
            reply_ready.set()
        except Exception:
            relay_task.cancel()
            await asyncio.gather(relay_task, return_exceptions=True)
            raise
