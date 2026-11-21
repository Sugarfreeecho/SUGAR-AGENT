"""宿主桥：唯一与 SugarAgent 耦合的文件。

对齐的是**新一层** `app/session_control/service.py`（不是旧的 `remote_control`）：
    async execute(principal, method, params, *, idempotency_key="") -> (result, replayed)
    subscribe(session_id, replay_recent=False) -> async iterator[dict]

字段名以该文件为准（已核实）：
    session.create → {"name": ..., "_subject": ...}           → result["session_id"]
    session.send   → {"session_id", "message", "mode", "_level", "_subject", "_source"}
    session.interrupt → {"session_id"}
    approval.resolve  → {"session_id", "approval_id", "decision"}

**权限不落会话**：create 时不传 tools/read_only；身份随每轮 send 下发。
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from typing import Any

from ..levels import turn_actor


class HostBridgeError(RuntimeError):
    pass


def _device_principal():
    """插件自己的宿主身份。拿不到宿主类型时用等价替身（只在测试里发生）。"""
    try:
        from remote_control.store import DevicePrincipal  # type: ignore

        return DevicePrincipal(
            device_id="sugar-assistant",
            name="Sugar Assistant",
            scopes=frozenset({"read", "write", "approvals"}),
            credential_kind="plugin",
        )
    except Exception:
        return _FallbackPrincipal()


class _FallbackPrincipal:
    device_id = "sugar-assistant"
    name = "Sugar Assistant"
    scopes = frozenset({"read", "write", "approvals"})
    credential_kind = "plugin"


class SugarAgentHost:
    """同步门面 + 异步内核。

    Core 是同步的（便于测），宿主 `execute` 是 async：这里做一层受控的桥。
    在事件循环线程里调用会明确报错，而不是死锁。
    """

    def __init__(self, service: Any, *, principal: Any = None, timeout: float = 30.0,
                 resolve_question: Any = None, service_factory: Any = None) -> None:
        self._service = service
        self.principal = principal or _device_principal()
        self.timeout = timeout
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._principals: dict[str, Any] = {}
        self._resolve_question = resolve_question
        self._service_factory = service_factory

    def principal_for(self, subject: str) -> Any:
        """每个对话主体一个设备身份。

        宿主会校验「发起者 id == 会话归属者」，用插件级单一身份去代所有人说话会被
        `_enforce_actor_scope` 拒掉（这正是第一次真机测试里 session.send 失败的原因）。
        """
        key = str(subject or "").strip()
        if key.startswith("sugar:"):
            key = key[len("sugar:"):]  # 已经是主体 id，别叠加前缀
        if not key:
            return self.principal
        cached = self._principals.get(key)
        if cached is not None:
            return cached
        try:
            from remote_control.store import DevicePrincipal  # type: ignore

            principal = DevicePrincipal(
                device_id=f"sugar:{key}",
                name=f"Sugar Assistant · {key}",
                scopes=frozenset({"read", "write", "approvals"}),
                credential_kind="plugin",
            )
        except Exception:
            principal = self.principal
        self._principals[key] = principal
        return principal

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """绑定宿主的事件循环。

        Core 在 worker 线程里跑（`service.handle` 用 `to_thread`），宿主服务却绑在
        它自己的 loop 上。不绑定就会出现「新开一个 loop 去调别人的 asyncio 服务」，
        轻则警告，重则卡死。
        """
        self._loop = loop
    # ------------------------------------------------------------------ 异步桥
    def _await(self, coro):
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is not None and (self._loop is None or running is self._loop):
            coro.close()  # 别把协程对象漏成 "never awaited"
            raise HostBridgeError(
                "在事件循环线程里同步调用宿主桥会死锁；请用 await host.<method>_async(...) 或放到线程里"
            )
        if self._loop is not None and self._loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, self._loop).result(self.timeout)
        return asyncio.run(coro)

    async def _execute(self, method: str, params: dict, *, idempotency_key: str = "", principal: Any = None) -> dict:
        # 每次调用都取一次当前代理：宿主在插件启停/重载时会 bump 源的 epoch，
        # 缓存的旧代理会一直被判"授权已撤销"。transport_service 只是读一次存储，代价很小。
        if self._service_factory is not None:
            try:
                self._service = self._service_factory()
            except Exception:
                pass
        if not hasattr(self._service, "execute"):
            raise HostBridgeError("宿主会话控制服务不可用（缺少 execute）")
        async def call(service):
            value = service.execute(principal or self.principal, method, params,
                                    idempotency_key=idempotency_key)
            if hasattr(value, "__await__"):
                value = await value
            return value

        try:
            result = await call(self._service)
        except Exception as exc:
            # 热重载后宿主给插件源换了 epoch，旧代理会被判“授权已撤销”：换新代理重试一次。
            text = str(exc).lower()
            if self._service_factory and ("revoked" in text or "unregistered runtime source" in text):
                self._service = self._service_factory()
                result = await call(self._service)
            else:
                raise
        # 新一层返回 (result, replayed)
        if isinstance(result, tuple) and len(result) >= 1:
            result = result[0]
        return result or {}

    # ------------------------------------------------------------------ 端口
    def create_session(self, *, title: str, subject: str = "", system_prompt: str = "",
                       shared: bool = False, work_dir: str = "", model_profile_id: str = "") -> str:
        params: dict[str, Any] = {"name": title or "新对话"}
        if shared:
            params["shared"] = True
        if work_dir:
            params["work_dir"] = work_dir
        if model_profile_id:
            params["model_profile_id"] = model_profile_id
        if subject:
            # 宿主把 created_by 记成**主体 id**；这里必须写同一个值，
            # 否则 send 时的作用域校验（created_by == _subject）永远不通过。
            params["_subject"] = getattr(self.principal_for(subject), "device_id", subject)
        if system_prompt:
            # 宿主在 create 时接受 runtime_config.system_prompt（append），
            # 这是目前唯一能把人设写进会话的官方入口。
            params["runtime_config"] = {"system_prompt": {"mode": "append", "text": system_prompt}}
        result = self._await(self._execute("session.create", params,
                                           idempotency_key=f"sugar-create:{uuid.uuid4().hex[:8]}",
                                           principal=self.principal_for(subject)))
        session_id = str(result.get("session_id") or result.get("id") or "")
        if not session_id:
            raise HostBridgeError(f"session.create 没有返回 session_id：{result}")
        return session_id

    def submit(self, session_id: str, text: str, *, op_id: str, actor: dict | None = None) -> str:
        params: dict[str, Any] = {"session_id": session_id, "message": text, "mode": "queue"}
        if actor:
            params.update(actor)
        subject = str((actor or {}).get("_subject") or "")
        principal = self.principal_for(subject)
        if subject:
            params["_subject"] = getattr(principal, "device_id", subject)
        try:
            result = self._await(self._execute("session.send", params, idempotency_key=op_id,
                                               principal=principal))
        except Exception as exc:
            # 宿主把同身份的 queue 自动改判成 steer，而 steer 只接受 append/interrupt
            if "mode must be append or interrupt" not in str(exc):
                raise
            params["mode"] = "append"
            # 同 key 换参数会被宿主拒（Key already belongs to different arguments），重试用新 key
            result = self._await(self._execute("session.send", params, idempotency_key=op_id + ":append",
                                               principal=principal))
        return str(result.get("run_id") or "")

    def rename_session(self, session_id: str, title: str) -> None:
        try:
            self._await(self._execute("session.update", {"session_id": session_id, "name": title}))
        except Exception:
            pass  # 标题钉不住不致命

    def list_sessions(self) -> list[dict]:
        result = self._await(self._execute("session.list", {}))
        items = result.get("sessions") or result.get("items") or []
        return [item for item in items if isinstance(item, dict)]

    def interrupt(self, session_id: str) -> None:
        self._await(self._execute("session.interrupt", {"session_id": session_id}))

    def call(self, method: str, params: dict, *, idempotency_key: str = "") -> dict:
        """透传一个宿主方法（/history、/model、/dir 用得到）。"""
        return self._await(self._execute(method, params, idempotency_key=idempotency_key))

    def session_state(self, session_id: str) -> dict:
        """读会话运行态（是否有一轮在跑）。失败就当未知，不阻塞消息。"""
        try:
            result = self.call("session.get", {"session_id": session_id, "include_runtime": True})
            return dict(result.get("session") or {})
        except Exception:
            return {}

    def list_pending_questions(self, session_id: str) -> list[dict]:
        """宿主进程内的待答提问；插件重载后靠它把内存里的 prompt 补回来。"""
        try:
            from human_interaction import get_human_interaction_service  # type: ignore

            return list(get_human_interaction_service().list(session_id, status="pending") or [])
        except Exception:
            return []

    def resolve_prompt(self, prompt, payload) -> None:
        if prompt.kind == "approval":
            # 宿主认的是 `approve: bool`（见 feishu-transport 的调用），不是 decision 字符串
            self._await(self._execute("approval.resolve", {
                "session_id": prompt.session_id,
                "approval_id": prompt.id,
                "approve": payload.get("decision") == "approve",
            }))
            return
        # ask 卡片：会话控制接口没有 question.*，但宿主进程内有单例服务，直接调它。
        resolver = self._resolve_question
        if resolver is None:
            try:
                from human_interaction import get_human_interaction_service  # type: ignore

                resolver = get_human_interaction_service().resolve_question
            except Exception as exc:  # 不在宿主进程里（CLI/单测）
                raise HostBridgeError(f"宿主缺少 human_interaction：{exc}") from exc
        try:
            resolver(prompt.session_id, prompt.id, payload.get("answers") or [])
        except Exception as exc:
            raise HostBridgeError(f"提交回答失败：{exc}") from exc

    # ------------------------------------------------------------------ 订阅
    def subscribe(self, session_id: str, *, replay_recent: bool = False):
        """返回宿主事件异步迭代器（由 relay 层消费）。"""
        return self._service.subscribe(session_id, replay_recent=replay_recent)


def actor_for(level: str, *, subject: str, channel: str) -> dict:
    """给测试/调用方用：与 Core 下发的字段完全一致。"""
    return turn_actor(level, subject=subject, channel=channel)
