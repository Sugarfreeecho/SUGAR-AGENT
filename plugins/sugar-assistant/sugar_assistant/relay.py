"""宿主事件 → Core 的转接层。

宿主的真实事件流（`session_control/service.py` 的 `subscribe(session_id)`）：
    final                  → 本轮最终回答，`content`
    error / run_failed     → 失败，`content` / `error`
    run_interrupted        → 被中止
    tool_approval_required → 需要审批，`approval_id` / `title` / `message`

这一层只做两件事：把事件翻译成 Core 的调用（出站投递 / 注册 Prompt），
以及在一次订阅里维护"审批只提醒一次"的状态。
"""
from __future__ import annotations

import asyncio
import logging

from .prompts import Option, Question, build_prompt
from .runtime import TransportRuntime

LOG = logging.getLogger("sugar_assistant.relay")

TERMINAL = {"final", "error", "run_failed", "run_interrupted", "run_finished"}


class EventRelay:
    def __init__(self, runtime: TransportRuntime, *, timeout: float = 600.0,
                 question_source=None) -> None:
        self.runtime = runtime
        self.timeout = timeout
        self._question_source = question_source or _default_question_source
        self.delivered = 0
        self._pending_progress = ""

    async def consume(self, session_id: str, *, replay_recent: bool = False) -> str:
        """消费一条会话的事件流，返回终止原因。"""
        subscribe = getattr(self.runtime.host, "subscribe", None)
        if subscribe is None:
            raise RuntimeError("宿主桥没有 subscribe（无法接收事件）")
        stream = subscribe(session_id, replay_recent=replay_recent)
        seen_approvals: set[str] = set()
        deadline = asyncio.get_running_loop().time() + self.timeout
        started = asyncio.get_running_loop().time()
        first_seen = False
        try:
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    return "timeout"
                try:
                    event = await asyncio.wait_for(stream.__anext__(), timeout=remaining)
                except (asyncio.TimeoutError, StopAsyncIteration):
                    return "timeout"
                if not isinstance(event, dict):
                    continue
                if not first_seen:
                    first_seen = True
                    LOG.info("relay 首个事件 %.2fs session=%s", asyncio.get_running_loop().time() - started,
                             session_id[:8])
                ended = self.handle_event(session_id, event, seen_approvals)
                if ended:
                    return ended
        finally:
            closer = getattr(stream, "aclose", None)
            if closer is not None:
                try:
                    await closer()
                except Exception:
                    pass

    def handle_event(self, session_id: str, event: dict, seen_approvals: set[str] | None = None) -> str:
        """同步处理单个事件；返回非空字符串表示这一轮结束。"""
        kind = str(event.get("type") or "")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if kind in {"final", "assistant_final_committed"}:
            # runtime_v2 发的是 assistant_final_committed，正文在 payload.content；
            # 旧网关发的是 final + content。两种都认，否则回复会被静默丢掉。
            text = event.get("content") or payload.get("content") or ""
            meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            if kind == "assistant_final_committed" and not meta.get("is_final", True):
                return ""
            if str(text).strip() and str(text).strip() == self._pending_progress:
                self._pending_progress = ""
                return "final"  # 这句刚才已经作为进展发过，不重复
            self.runtime.on_host_event(session_id, str(text), kind="final",
                                       event_id=str(event.get("run_id") or ""))
            self._pending_progress = ""
            self.delivered += 1
            return "final"
        if kind == "ui_event" and str(payload.get("type") or "") == "llm_response":
            # 一轮里可能出现多次 llm_response：后一次出现说明前一次只是中间进展
            text = str(payload.get("content") or "").strip()
            if text and text != self._pending_progress:
                # 一产生就发，不等下一句
                self.runtime.on_host_event(session_id, text, kind="progress",
                                           event_id=str(event.get("run_id") or ""))
                self.delivered += 1
                self._pending_progress = text
            return ""
        if kind == "run_finished":
            return "finished"
        if kind in {"error", "run_failed"}:
            text = str(event.get("content") or event.get("error") or "运行失败")
            self.runtime.on_host_event(session_id, text, kind="error",
                                       event_id=str(event.get("run_id") or ""))
            self.delivered += 1
            return "error"
        if kind == "run_interrupted":
            self.runtime.on_host_event(session_id, "已中止。", kind="error")
            self.delivered += 1
            return "interrupted"
        if kind == "tool_approval_required":
            self._register_approval(session_id, event, seen_approvals)
            return ""
        if kind in {"question_requested", "interaction_requested"}:
            self._register_question(session_id, payload)
            return ""
        return ""

    # ------------------------------------------------------------------ 内部
    def _register_approval(self, session_id: str, event: dict, seen: set[str] | None) -> None:
        approval_id = str(event.get("approval_id") or "")
        if not approval_id or (seen is not None and approval_id in seen):
            return
        if seen is not None:
            seen.add(approval_id)
        title = str(event.get("title") or event.get("tool") or "工具调用")
        detail = str(event.get("message") or "")
        prompt = build_prompt(
            kind="approval",
            session_id=session_id,
            prompt_id=approval_id,
            approval_options=[Option("allow_once", "同意（只这一次）"), Option("deny", "拒绝")],
        )
        prompt.questions = []
        self.runtime.prompts.add(prompt)
        body = prompt.render() + (f"\n\n{title}" + (f"：{detail}" if detail else ""))
        card = {
            "title": "需要你确认一个操作",
            "body": f"{title}" + (f"\n{detail}" if detail else ""),
            "options": [{"label": "同意", "value": "1"}, {"label": "拒绝", "value": "2"}],
        }
        # 群聊里的审批只给帐号主看：有配置就私聊发，群里不落地
        target = ""
        key = self.runtime.sessions.current_conversation(session_id)
        if key and self.runtime.sessions.kind_of(key) == "group" and self.runtime.owner_chat_id:
            target = self.runtime.owner_chat_id
        self.runtime.on_host_event(session_id, body, kind="prompt",
                                   event_id=f"approval:{approval_id}", card=card, to_chat=target)

    def _register_question(self, session_id: str, payload: dict | None = None) -> None:
        """ask_user 卡片：事件里带 questions 就直接用，否则再查宿主。"""
        rows = [payload] if isinstance(payload, dict) and payload.get("questions") else []
        if not rows:
            try:
                rows = self._question_source(session_id)
            except Exception as exc:
                LOG.warning("读取待答提问失败：%s", exc)
                return
        seen = getattr(self.runtime, "_seen_questions", None)
        if seen is None:
            seen = set()
            self.runtime._seen_questions = seen
        for row in rows or []:
            interaction_id = str(row.get("interaction_id") or "")
            if not interaction_id or interaction_id in seen:
                continue
            questions = [
                Question(
                    question_id=str(item.get("question_id") or f"q{i + 1}"),
                    header=str(item.get("header") or ""),
                    text=str(item.get("question") or item.get("text") or ""),
                    options=[
                        Option(str(opt.get("option_id")), str(opt.get("label") or opt.get("text") or opt.get("option_id")))
                        for opt in (item.get("options") or [])
                    ],
                )
                for i, item in enumerate(row.get("questions") or [])
            ]
            if not questions:
                continue
            prompt = build_prompt(kind="question", session_id=session_id,
                                  prompt_id=interaction_id, questions=questions)
            self.runtime.prompts.add(prompt)
            seen.add(interaction_id)
            card = None
            if questions and all(q.options for q in questions):
                sections = []
                for qi, q in enumerate(questions, start=1):
                    head = f"Q{qi}／{len(questions)} {q.header}" if len(questions) > 1 else (q.header or "需要你选择")
                    sections.append({
                        "body": f"**{head}**\n{q.text}",
                        "options": [
                            {"label": f"{oi}. {opt.label}", "value": f"q{qi}:{oi}"}
                            for oi, opt in enumerate(q.options, start=1)
                        ],
                    })
                card = {"title": questions[0].header or "需要你选择", "sections": sections}
            self.runtime.on_host_event(session_id, prompt.render(), kind="prompt",
                                       event_id=f"question:{interaction_id}", card=card)


def _default_question_source(session_id: str) -> list[dict]:
    from human_interaction import get_human_interaction_service  # type: ignore

    return get_human_interaction_service().list(session_id, status="pending")
