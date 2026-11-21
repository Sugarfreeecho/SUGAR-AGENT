"""Core 编排：一条入站消息怎么变成一轮 run，一轮 run 怎么变回一条消息。

顺序固定（每一步失败都有明确出口）：
    准入与定档 → 命令？ → 幂等占位 → 会话映射 → 带当轮身份起一轮 → （宿主事件）配额 → 入队投递

关键：**权限是每轮现算的**。会话里只存名字，不存 tools/read_only；
同一身份连续说话由宿主自动合并成 steer（`mode=queue` + `_same_turn_actor`），
不同身份自然排在队列里，各轮各自判档。
"""
from __future__ import annotations

import time
import logging
import re
from dataclasses import dataclass, replace
from typing import Any, Callable

from .admission import Admission
from .commands import HELP, parse_command
from .delivery import DeliveryQueue
from .levels import new_actor
from .models import ChannelId, ConversationRef, Delivery, Inbound
from .opstore import OpStore
from .prompts import Option, ParseResult, Prompt, PromptRegistry, Question, build_prompt, parse_reply
from .quota import QuotaModel
from .sessionmap import HostPort, SessionMap

RUNTIME_REV = "2026-11-19.webapi1"
_CARD_CHOICE = re.compile(r"^q(\d+):(\d+)$")
logging.getLogger("sugar_assistant.runtime").info("runtime 模块已加载 rev=%s", RUNTIME_REV)

_ANSWER_HINT = ("其他", "其它", "跳过", "skip")


def _looks_like_answer(text: str) -> bool:
    """像不像在回答提示卡：纯数字/多选，或以"其他/跳过"开头。"""
    value = (text or "").strip()
    if not value:
        return False
    if value.replace(" ", "").replace(",", "").replace("、", "").isdigit():
        return True
    return value.startswith(_ANSWER_HINT)


@dataclass
class HandleResult:
    ok: bool
    status: str  # accepted | duplicate | denied | command | failed
    reason: str = ""
    op_id: str = ""
    session_id: str = ""
    reply: str = ""
    level: str = ""


class TransportRuntime:
    def __init__(
        self,
        *,
        host: HostPort,
        admission: Admission,
        sessions: SessionMap,
        ops: OpStore,
        prompts: PromptRegistry,
        quota: QuotaModel,
        delivery: DeliveryQueue,
        adapters: dict[str, Any] | None = None,
        clock: Callable[[], float] = time.time,
        console: Any = None,
    ) -> None:
        self.host = host
        self.admission = admission
        self.sessions = sessions
        self.ops = ops
        self.prompts = prompts
        self.quota = quota
        self.delivery = delivery
        self.adapters = adapters or {}
        self._clock = clock
        self.console = console
        self.defaults: dict = {}
        # 群聊里的审批要私聊发给帐号主；留空则仍发在群里
        self.owner_chat_id = ""
        # 快速回应：同会话 60 秒内只回一次"收到"，避免每条消息两条回执
        self.ack_enabled = False
        self._last_ack: dict[str, float] = {}
        # 通道层的"回复凭据"（如微信的 context_token）按对话记住，出站时带回去
        self._context_tokens: dict[tuple[str, str], str] = {}
        self._card_answers: dict[str, dict[int, int]] = {}
        self._shared_sessions: set[str] = set()

    def _chat_name_for(self, chat_id: str) -> str:
        """出站时带上会话名，供浏览器桥按名字定位会话。"""
        try:
            binding = self.sessions.find_by_chat(chat_id)
        except Exception:
            return ""
        return str(getattr(binding, "chat_name", "") or "")

    # ------------------------------------------------------------------ 入站
    def handle_inbound(self, inbound: Inbound) -> HandleResult:
        _t0 = self._clock()
        _lag = _t0 - float(getattr(inbound, "received_at", _t0) or _t0)
        if not getattr(self, "_rev_logged", False):
            self._rev_logged = True
            self._log("runtime_rev", rev=RUNTIME_REV)
        decision = self.admission.check(inbound)
        if not decision.ok:
            self._log("denied", channel=inbound.channel.channel, reason=decision.reason)
            return HandleResult(ok=False, status="denied", reason=decision.reason)

        identity = decision.identity
        level = identity.level if identity else "stranger"

        op = self.ops.claim(inbound)
        if op is None:
            self._log("duplicate", channel=inbound.channel.channel, message_id=inbound.message_id)
            return HandleResult(ok=False, status="duplicate", reason="这条消息已经处理过", level=level)
        self.ops.transition(op, "admitted")

        token = (inbound.raw or {}).get("contextToken") if isinstance(inbound.raw, dict) else None
        if token:
            self._context_tokens[(inbound.channel.channel, inbound.conversation.chat_id)] = str(token)

        command = parse_command(inbound.text)
        if command is not None:
            reply = self._run_command(inbound, command, level, identity)
            self.ops.transition(op, "done")
            self._log("command", name=command.kind, queue_lag=round(_lag, 3),
                      cost=round(self._clock() - _t0, 3))
            return HandleResult(ok=True, status="command", op_id=op.id, reply=reply, level=level)

        # 有待答的提问/审批时，回复先当作答案回填，而不是开新一轮
        binding = self.sessions.get(self.sessions.key_for(inbound))
        if binding is not None and not self.prompts.pending(binding.session_id):
            self.hydrate_prompts(binding.session_id)  # 重载后内存丢了，从宿主补回来
        card_choice = _CARD_CHOICE.match((inbound.text or "").strip())
        if binding is not None and card_choice and self.prompts.pending(binding.session_id):
            return self._apply_card_choice(inbound, binding.session_id, op,
                                           int(card_choice.group(1)), int(card_choice.group(2)), level)
        if binding is not None and self.prompts.pending(binding.session_id):
            parsed = self.answer(binding.session_id, inbound.text)
            if parsed.ok:
                self.ops.transition(op, "done")
                return HandleResult(ok=True, status="prompt", op_id=op.id,
                                    session_id=binding.session_id, reply="已提交。", level=level)
            if _looks_like_answer(inbound.text):
                # 明显是在答题但答不对：回错误提示，不要糊里糊涂丢给模型
                self.ops.transition(op, "done")
                return HandleResult(ok=False, status="prompt_invalid", op_id=op.id,
                                    session_id=binding.session_id, reason=parsed.error,
                                    reply=parsed.error, level=level)

        # 会话名按模式固定（设计稿）：私聊一个会话，群聊一 group 一个会话。
        title = self._title_for(inbound)
        binding, created = self.sessions.resolve(inbound, title=title, system_prompt=self._persona_text(
            "group" if inbound.conversation.kind == "group" else "private"))
        # 新会话首轮：把飞书里已有的历史一并带上，避免“进来就失忆”
        if created:
            try:
                from .history import recent

                past = recent(inbound.conversation.chat_id, 20)
            except Exception:
                past = ""
            if past:
                inbound = replace(inbound, text=f"[飞书历史消息，供参考]\n{past}\n\n[当前消息]\n{inbound.text}")
                self._log("history_loaded", chat=inbound.conversation.chat_id[-10:], lines=past.count("\n") + 1)
        self.ops.transition(op, "queued", session_id=binding.session_id)
        if inbound.conversation.kind == "group":
            self._ensure_shared(binding.session_id)
        if title and title != binding.title and isinstance(inbound.raw, dict) and inbound.raw.get("chatName"):
                # 旧会话标题可能是 chat_id 尾号；拿到群名后顺手修正
                try:
                    self.host.rename_session(binding.session_id, title)
                    self.sessions.bind(self.sessions.key_for(inbound), binding.session_id,
                                       title=title, principal=binding.principal)
                except Exception as exc:
                    self._log("rename_failed", session_id=binding.session_id, reason=str(exc)[:160])

        # 群聊里别人还在跑：不回进宿主队列，直接告知（同一个人则由宿主 steer 追加）
        if inbound.conversation.kind == "group":
            previous = self.ops.by_session(binding.session_id)
            same_sender = bool(previous and previous.principal == inbound.sender.key())
            state = getattr(self.host, "session_state", None)
            if state is not None and not same_sender and state(binding.session_id).get("stream_active"):
                self.ops.force(op.id, "failed")
                self._log("busy", channel=inbound.channel.channel, session_id=binding.session_id)
                return HandleResult(ok=False, status="busy", session_id=binding.session_id,
                                    reply="上一条还在跑，等它完或发 /stop", level=level)

        actor = new_actor(level, subject="sugar-assistant:owner",
                          channel=inbound.channel.channel)
        try:
            self.host.submit(binding.session_id, inbound.text, op_id=op.id, actor=actor)
        except Exception as exc:
            reason = str(exc)
            self._log("submit_error", channel=inbound.channel.channel, reason=reason[:200],
                      session_id=binding.session_id)
            # 只有"会话真的不在/归属别人"才重建；其他错误（网络、授权、忙碌、模型）不能换会话，
            # 否则每失败一次就多一个会话——这正是"每次对话都新建会话"的原因。
            stale = any(key in reason.lower() for key in ("session not found", "another identity"))
            if not stale:
                self.ops.transition(op, "failed")
                return HandleResult(ok=False, status="failed",
                                    reason=f"起一轮失败：{reason}", op_id=op.id, level=level)
            self.sessions.drop(self.sessions.key_for(inbound))
            binding, _created = self.sessions.resolve(inbound, title=title, system_prompt=self._persona_text(
            "group" if inbound.conversation.kind == "group" else "private"))
            self._log("rebind", channel=inbound.channel.channel, session_id=binding.session_id)
            try:
                self.host.submit(binding.session_id, inbound.text, op_id=op.id, actor=actor)
            except Exception as retry_exc:
                self.ops.transition(op, "failed")
                self._log("failed", channel=inbound.channel.channel, reason=str(retry_exc)[:300],
                          session_id=binding.session_id)
                return HandleResult(ok=False, status="failed",
                                    reason=f"起一轮失败：{retry_exc}", op_id=op.id, level=level)

        self.ops.transition(op, "running")
        self._maybe_ack(inbound, binding.session_id)
        self._log("accepted", channel=inbound.channel.channel, level=level,
                  session_id=binding.session_id, message_id=inbound.message_id)
        return HandleResult(ok=True, status="accepted", op_id=op.id, session_id=binding.session_id, level=level)

    # ------------------------------------------------------------------ 出站
    def reply_now(self, inbound: Inbound, text: str) -> None:
        """命令类回复：还没有会话绑定，直接走入站通道发回去。"""
        delivery = Delivery(
            id=f"cmd-{int(self._clock() * 1000)}",
            channel=inbound.channel.channel,
            conversation=ConversationRef(chat_id=inbound.conversation.chat_id),
            kind="final",
            text=text,
            idempotency_key=f"cmd:{inbound.message_id}",
        )
        adapter = self.adapters.get(inbound.channel.channel)
        if adapter is None:
            self._log("delivery", status="failed", channel=inbound.channel.channel,
                      message_kind="command", detail="通道未装配")
            return
        _t0 = self._clock()
        result = adapter.send(delivery)
        elapsed = round(self._clock() - _t0, 3)
        self._log("delivery", status=getattr(result, "status", "sent"),
                  channel=inbound.channel.channel, message_kind="command",
                  detail=f"{getattr(result, 'outcome', '')} {elapsed}s "
                         f"{(getattr(result, 'detail', '') or '')}"[:200])

    def on_host_event(self, session_id: str, text: str, *, kind: str = "final", event_id: str = "",
                      card: dict | None = None, to_chat: str = "") -> Delivery | None:
        if event_id:
            # 多个 relay 同时活着时会重复收到同一个 run 的事件，按 (session, run, kind) 去重
            marker = (session_id, event_id, kind)
            seen = getattr(self, "_delivered_events", None)
            if seen is None:
                seen = set()
                self._delivered_events = seen
            if marker in seen:
                return None
            seen.add(marker)
        conversation_key = self.sessions.current_conversation(session_id)
        if conversation_key is None:
            return None  # 不是本频道发起的会话：正常现象，不当作错误
        op = self.ops.by_session(session_id)

        charge = self.quota.charge(conversation_key)
        if charge.exhausted:
            # 到限不是"卡住"：这一条留给用户下一条消息时补发
            return None

        channel, chat_id = self._split_key(conversation_key)
        if to_chat:
            chat_id = to_chat
        body = text if not charge.warn else f"{text}\n\n（{charge.hint or '通道快用完了，回我一句就能续期。'}）"
        delivery = Delivery(
            id=f"d-{int(self._clock() * 1000)}-{len(self.delivery.pending)}",
            channel=channel,
            conversation=ConversationRef(chat_id=chat_id),
            kind=kind,  # type: ignore[arg-type]
            text=body,
            idempotency_key=event_id or (f"{op.id}:{kind}" if op else ""),
            meta={"context_token": self._context_tokens.get((channel.channel, chat_id), ""),
                  "chat_name": self._chat_name_for(chat_id)},
        )
        if card:
            delivery.meta["card"] = card
        self.delivery.enqueue(delivery)
        self.delivery.pump()
        if delivery.status == "unreachable" and delivery.channel.channel == "feishu":
            self._schedule_bridge(delivery)
        self._log("delivery", status=delivery.status, channel=delivery.channel.channel,
                  message_kind=kind, chat=chat_id[-10:], detail=(delivery.last_error or "")[:200])
        if op is not None and delivery.status in {"acked", "readback"} and kind == "final":
            try:
                self.ops.transition(op, "done")
            except ValueError:
                pass
        return delivery

    def _schedule_bridge(self, delivery: Delivery) -> None:
        """官方通道发不出去时，用宿主插件总线走浏览器（不阻塞当前线程）。"""
        import asyncio
        import os as _os

        if self._try_webapi(delivery):
            return
        try:
            import plugin_bus
        except Exception:
            return
        if not plugin_bus.available("browser"):
            return
        detail = str(delivery.last_error or "")
        if not any(code in detail for code in ("230002", "230027", "230038")):
            return
        meta = delivery.meta or {}
        chat_name = str(meta.get("chat_name") or "")
        tenant = _os.environ.get("SUGAR_WEB_TENANT", "")
        if not chat_name or not tenant:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        async def run() -> None:
            try:
                attachment = (delivery.attachments or [None])[0]
                if attachment is not None:
                    await plugin_bus.call("sugar-assistant", "browser", "send_media",
                                          {"tenant": tenant, "chat_name": chat_name,
                                           "path": attachment.path, "kind": attachment.kind})
                else:
                    await plugin_bus.call("sugar-assistant", "browser", "send_text",
                                          {"tenant": tenant, "chat_name": chat_name,
                                           "text": delivery.text})
                    from sugar_assistant.channels.feishu_worker import _readback_text
                    if not _readback_text(delivery.conversation.chat_id, delivery.text, timeout=8):
                        delivery.last_error = f"{delivery.last_error}；浏览器桥回查未见消息"
                        self._log("bridge_unverified", chat=delivery.conversation.chat_id[-10:])
                        return
                delivery.status = "acked"
                self._log("bridge_sent", chat=delivery.conversation.chat_id[-10:])
            except Exception as exc:
                delivery.last_error = f"{delivery.last_error}；浏览器桥失败：{exc}"
                self._log("bridge_failed", error=str(exc)[:200])

        loop.create_task(run())

    def _try_webapi(self, delivery: Delivery) -> bool:
        """先试 Web 内部接口（/im/gateway，纯 HTTP，不碰页面）；成功就不用开浏览器。"""
        import os as _os

        if delivery.attachments:
            return False
        detail = str(delivery.last_error or "")
        if not any(code in detail for code in ("230002", "230027", "230038")):
            return False
        meta = delivery.meta or {}
        chat_name = str(meta.get("chat_name") or "")
        tenant = _os.environ.get("SUGAR_WEB_TENANT", "")
        if not tenant:
            return False
        try:
            from sugar_assistant import web_api
            from sugar_assistant import web_sender
            cdp = _os.environ.get("SUGAR_WEB_CDP", "")
            if not cdp:
                try:
                    cdp = str(web_sender.load_config().get("cdp_url") or "")
                except Exception:
                    cdp = ""
            result = web_api.send_text(
                delivery.conversation.chat_id, delivery.text, chat_name,
                {"tenant": tenant, "cdp_url": cdp},
            )
        except Exception as exc:
            self._log("webapi_error", error=str(exc)[:200])
            return False
        if result.get("status") == "sent":
            # 接口说成功不算数，必须只读回查到原文
            try:
                from sugar_assistant.channels.feishu_worker import _readback_text
                seen = _readback_text(delivery.conversation.chat_id, delivery.text, timeout=8)
            except Exception:
                seen = False
            if seen:
                delivery.status = "acked"
                self._log("webapi_sent", chat=delivery.conversation.chat_id[-10:])
                return True
            self._log("webapi_unverified", chat=delivery.conversation.chat_id[-10:])
            return False
        self._log("webapi_failed", detail=str(result.get("detail") or "")[:160])
        return False

    def answer(self, session_id: str, text: str, *, quoted: tuple[str, str] | None = None) -> ParseResult:
        pending = self.prompts.pending(session_id)
        result = parse_reply(text, pending, quoted_message=quoted, registry=self.prompts)
        if not result.ok:
            return result
        prompt = next((p for p in pending if p.id == result.prompt_id), None)
        if prompt is None:
            return ParseResult(ok=False, error="提示已失效")
        submit = getattr(self.host, "resolve_prompt", None)
        if submit is None:
            return ParseResult(ok=False, error="宿主缺少 resolve_prompt")
        try:
            submit(prompt, result.payload)
        except Exception as exc:
            return ParseResult(ok=False, error=str(exc))
        self.prompts.close(prompt.id)
        return result

    def hydrate_prompts(self, session_id: str) -> int:
        """插件重载会丢内存 prompt；这里从宿主把 pending 的 ask 重新装回来。"""
        lister = getattr(self.host, "list_pending_questions", None)
        if lister is None:
            return 0
        added = 0
        for row in lister(session_id) or []:
            interaction_id = str(row.get("interaction_id") or "")
            if not interaction_id or self.prompts.get(interaction_id) is not None:
                continue
            questions = [
                Question(
                    question_id=str(item.get("question_id") or f"q{i + 1}"),
                    header=str(item.get("header") or ""),
                    text=str(item.get("question") or item.get("text") or ""),
                    options=[Option(str(opt.get("option_id")), str(opt.get("label") or opt.get("option_id")))
                             for opt in (item.get("options") or [])],
                )
                for i, item in enumerate(row.get("questions") or [])
            ]
            if questions:
                self.prompts.add(build_prompt(kind="question", session_id=session_id,
                                              prompt_id=interaction_id, questions=questions))
                added += 1
        return added

    def _apply_card_choice(self, inbound: Inbound, session_id: str, op, q_index: int, o_index: int,
                           level: str) -> HandleResult:
        prompt = self.prompts.pending(session_id)[0]
        if not 1 <= q_index <= len(prompt.questions):
            return HandleResult(ok=False, status="prompt_invalid", reply="题号不对", level=level)
        question = prompt.questions[q_index - 1]
        if not 1 <= o_index <= len(question.options):
            return HandleResult(ok=False, status="prompt_invalid",
                                reply=f"第 {q_index} 题只有 {len(question.options)} 个选项", level=level)
        choices = self._card_answers.setdefault(prompt.id, {})
        choices[q_index] = o_index
        remaining = len(prompt.questions) - len(choices)
        if remaining > 0:
            self.ops.transition(op, "done")
            return HandleResult(ok=True, status="prompt", session_id=session_id,
                                reply=f"已记录第 {q_index} 题，还剩 {remaining} 题", level=level)
        text = " ".join(str(choices[i]) for i in range(1, len(prompt.questions) + 1))
        parsed = self.answer(session_id, text)
        self._card_answers.pop(prompt.id, None)
        self.ops.transition(op, "done")
        if parsed.ok:
            return HandleResult(ok=True, status="prompt", session_id=session_id, reply="已提交。", level=level)
        return HandleResult(ok=False, status="prompt_invalid", session_id=session_id,
                            reason=parsed.error, reply=parsed.error, level=level)

    # ------------------------------------------------------------------ 命令
    def _run_command(self, inbound: Inbound, command, level: str, identity) -> str:
        if command.kind == "help":
            return HELP
        if command.kind == "whoami":
            axes = identity.axes.as_dict() if identity else {}
            return f"你是 {inbound.sender.key()}，身份：{level}；四轴 {axes}"
        if command.kind == "new":
            key = self.sessions.key_for(inbound)
            self.sessions.drop(key)
            title = command.arg or "新对话"
            session_id = self.host.create_session(title=title, subject=inbound.sender.key(),
                                                  system_prompt=self._persona_text(
                                                      "group" if inbound.conversation.kind == "group" else "private"))
            self.sessions.bind(key, session_id, title=title, principal=inbound.sender.key())
            return f"已开新对话：{title}"
        if command.kind == "list":
            sessions = self.host.list_sessions()
            if not sessions:
                return "还没有对话。"
            lines = ["最近的对话："]
            for index, item in enumerate(sessions[:10], start=1):
                title = str(item.get("title") or item.get("name") or "(无标题)")
                lines.append(f"{index}. {title}")
            lines.append("回 /use N 切过去")
            return "\n".join(lines)
        if command.kind == "use":
            sessions = self.host.list_sessions()
            try:
                index = int(command.arg)
            except (TypeError, ValueError):
                return "用法：/use 2（数字来自 /list）"
            if not 1 <= index <= len(sessions):
                return f"只有 {len(sessions)} 个对话"
            item = sessions[index - 1]
            session_id = str(item.get("session_id") or item.get("id") or "")
            if not session_id:
                return "这个对话没有 id，切不过去"
            title = str(item.get("title") or "(无标题)")
            self.sessions.bind(self.sessions.key_for(inbound), session_id, title=title, principal=inbound.sender.key())
            if inbound.conversation.kind == "group":
                self._ensure_shared(session_id)
            return f"已切到：{title}"
        if command.kind == "stop":
            session_id = self.sessions.session_for_conversation(self.sessions.key_for(inbound))
            if not session_id:
                return "当前没有正在跑的对话"
            self.host.interrupt(session_id)
            return "已中止这一轮"
        if command.kind == "history":
            return self._history(inbound, command.arg)
        if command.kind in {"models", "model"}:
            return self._model(inbound, command.arg)
        if command.kind == "dir":
            return self._dir(inbound, command.arg)
        if command.kind == "rename":
            sid = self._session_id(inbound)
            if not sid:
                return "当前还没有对话"
            name = (command.arg or "").strip()[:160]
            if not name:
                return "用法：/rename 新名称"
            try:
                self.host.rename_session(sid, name)
            except Exception as exc:
                return f"改名失败：{exc}"
            return f"会话已改名为「{name}」"
        if command.kind == "identity":
            from . import identity as identity_mode

            arg = (command.arg or "").strip().lower()
            if not arg:
                return f"当前发送身份：{identity_mode.current()}（可选 bot / user）"
            is_self = bool((inbound.raw or {}).get("self")) if isinstance(inbound.raw, dict) else False
            if level not in {"owner", "whitelist"} and not is_self:
                return "切换身份需要机主或白名单权限"
            try:
                result = identity_mode.set_mode(arg)
            except ValueError as exc:
                return str(exc)
            self._log("identity", mode=result["mode"], chats=result.get("chats"), by=inbound.sender.key())
            if result.get("changed"):
                identity_mode.request_reload(delay=1.5)  # 先让这条回复发出去，再重载换通道
            hint = "" if result["mode"] == "bot" else "；user 模式需要配置要轮询的会话（CLI：identity set user --chat oc_xxx）"
            return f"身份已切到 {result['mode']}{hint}"
        return HELP

    # ------------------------------------------------------------------ 命令实现
    def _session_id(self, inbound: Inbound) -> str:
        return self.sessions.session_for_conversation(self.sessions.key_for(inbound)) or ""

    def _history(self, inbound: Inbound, arg: str) -> str:
        sid = self._session_id(inbound)
        if not sid:
            return "当前还没有对话"
        try:
            limit = max(1, min(int(arg or 10), 50))
        except ValueError:
            limit = 10
        try:
            data = self.host.call("session.history", {"session_id": sid, "limit": limit})
        except Exception as exc:
            return f"读历史失败：{exc}"
        rows = data.get("events") or data.get("messages") or data.get("items") or []
        lines: list[str] = []
        for row in rows[-limit:]:
            role = str(row.get("role") or row.get("type") or "")
            content = str(row.get("content") or row.get("text") or "").strip().replace("\n", " ")
            if content:
                lines.append(f"{role}：{content[:120]}")
        return "\n".join(lines[-limit:]) or "最近没有消息"

    def _model(self, inbound: Inbound, arg: str) -> str:
        profiles = self._profiles()
        if not profiles:
            return "宿主没有可用的模型档案"
        if not arg:
            return "\n".join(f"{i}. {p['name']}（{p['id']}）" for i, p in enumerate(profiles, 1))
        target = arg.strip()
        if target.isdigit() and 1 <= int(target) <= len(profiles):
            target = profiles[int(target) - 1]["id"]
        sid = self._session_id(inbound)
        if not sid:
            return "当前还没有对话"
        try:
            self.host.call("session.update", {"session_id": sid, "model_profile_id": target})
        except Exception as exc:
            return f"切模型失败：{exc}"
        return f"已切到模型 {target}（下一轮生效）"

    def _dir(self, inbound: Inbound, arg: str) -> str:
        sid = self._session_id(inbound)
        if not sid:
            return "当前还没有对话"
        if not arg:
            try:
                data = self.host.call("session.get", {"session_id": sid})
                summary = data.get("session") or {}
                return f"工作目录：{summary.get('work_dir') or summary.get('cwd') or '跟随宿主默认'}"
            except Exception as exc:
                return f"读目录失败：{exc}"
        try:
            self.host.call("session.update", {"session_id": sid, "work_dir": arg.strip()})
        except Exception as exc:
            return f"切目录失败：{exc}"
        return f"工作目录已切到 {arg.strip()}（下一轮生效）"

    @staticmethod
    def _profiles() -> list[dict]:
        import json
        from pathlib import Path

        from . import paths

        path = Path(paths.PROJECT_ROOT) / ".config" / "model_profiles.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        items = raw if isinstance(raw, list) else (raw.get("profiles") or list(raw.values()))
        rows = []
        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            if item.get("enabled") is False:
                continue
            rows.append({"id": str(item["id"]), "name": str(item.get("name") or item.get("model") or item["id"])})
        return rows

    # ------------------------------------------------------------------ 工具
    def _persona_text(self, mode: str = "private") -> str:
        """全局提示词原样注入；再按会话类型追加该模式的「身份 / 风格 / 规则」。"""
        persona = self.console.persona() if self.console is not None else {}
        blocks: list[str] = []
        prompt = str(persona.get("prompt") or "").strip()
        if prompt:
            blocks.append(prompt)
        override = (persona.get("modes") or {}).get(mode) or {}
        lines: list[str] = []
        if override.get("identity"):
            lines.append(f"你的身份：{override['identity']}")
        if override.get("tone"):
            lines.append(f"说话风格：{override['tone']}")
        rules = [line.strip("- ").strip() for line in str(override.get("rules") or "").splitlines() if line.strip()]
        if rules:
            lines.append("硬规则：")
            lines.extend(f"- {rule}" for rule in rules)
        if lines:
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def reconcile_stale_ops(self, *, stale_seconds: float = 600.0) -> list[dict]:
        """启动对账：卡住的 op 用会话历史核实，跑过就记 done，没跑过才 expired。"""
        report: list[dict] = []
        for op in self.ops.stale(stale_seconds):
            matched = False
            if op.session_id and op.text:
                try:
                    page = self.host.call("session.history", {"session_id": op.session_id, "limit": 100})
                    probe = op.text[:30]
                    matched = any(probe in str(item.get("content") or item.get("text") or "")
                                  for item in (page.get("messages") or []))
                except Exception as exc:
                    self._log("reconcile_error", op_id=op.id, reason=str(exc)[:200])
            status = "done" if matched else "expired"
            self.ops.force(op.id, status)
            report.append({"op_id": op.id, "session_id": op.session_id, "status": status})
            self._log("reconcile", op_id=op.id, status=status, session_id=op.session_id)
        return report

    def _ensure_shared(self, session_id: str) -> None:
        """群聊会话标记为共享：谁建的、/use 绑来的都一样，群成员都能进。"""
        if not session_id or session_id in self._shared_sessions:
            return
        try:
            self.host.call("session.update", {"session_id": session_id, "shared": True})
            self._shared_sessions.add(session_id)
        except Exception as exc:
            self._log("share_failed", session_id=session_id, reason=str(exc)[:200])

    def _log(self, kind: str, **fields: Any) -> None:
        if self.console is not None:
            try:
                self.console.log(kind, **fields)
            except Exception:
                pass

    def _maybe_ack(self, inbound: Inbound, session_id: str) -> None:
        if not self.ack_enabled:
            return
        key = self.sessions.key_for(inbound)
        now = self._clock()
        if now - self._last_ack.get(key, 0) < 10:
            return
        self._last_ack[key] = now
        self.on_host_event(session_id, "收到，正在处理…", kind="ack")

    @staticmethod
    def _title_for(inbound: Inbound) -> str:
        """命名规范：
        私聊 → 「小Sugar私聊-<对方名>」；群聊 → 「小Sugar群聊-<群名>」。
        名字拿不到时只保留前缀，不用 chat_id 兜底。
        """
        chat = inbound.conversation.chat_id or ""
        name = ""
        if isinstance(inbound.raw, dict):
            name = str(inbound.raw.get("chatName") or "").strip()
        if inbound.conversation.kind == "group":
            return f"小Sugar群聊-{name}" if name else "小Sugar群聊"
        return f"小Sugar私聊-{name}" if name else "小Sugar私聊"

    @staticmethod
    def _split_key(conversation_key: str) -> tuple[ChannelId, str]:
        parts = conversation_key.split(":")
        channel = parts[0] if parts else "unknown"
        account = parts[1] if len(parts) > 1 else "default"
        rest = ":".join(parts[2:]) if len(parts) > 2 else ""
        chat_id = rest.split("#")[0] if rest else ""
        return ChannelId(channel, account), chat_id
