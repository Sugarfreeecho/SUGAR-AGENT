"""ask / 审批的统一通道。

宿主侧的真实形态（已核实）：
    question: 1–4 题，每题 2–4 选项，`question_id=q1` / `option_id=q1o1`，可多选；
              答案 = 每题恰好一条 `{question_id, selected_option_ids[], other_text?, skipped}`；
              单选最多 1 项；skipped 时不许带任何答案；"Other" 由 UI 提供，不能当选项。
    approval: 二选一（可带"本会话允许"），必须带合法 approval_id。

IM 侧只有文本，所以：
    * 每条提示分配 4 位 short_code；
    * 同会话只有一条 pending 时裸数字可用，多条时一律不猜；
    * 引用回复可优先定位（由调用方把 message_id 传进来）。
"""
from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Literal

PromptKind = Literal["question", "approval"]

_CODE_RE = re.compile(r"^([0-9A-Fa-f]{4})(?:\s+|$)(.*)$", re.S)
_ALLOW_WORDS = ("同意", "允许", "可以", "好", "行", "yes", "y", "allow", "ok")
_DENY_WORDS = ("拒绝", "不允许", "不行", "不要", "否", "no", "n", "deny", "reject", "取消", "cancel")
_SKIP_WORDS = ("跳过", "skip", "不答")


@dataclass
class Option:
    option_id: str
    label: str
    description: str = ""


@dataclass
class Question:
    question_id: str
    header: str
    text: str
    options: list[Option]
    multi_select: bool = False


@dataclass
class Prompt:
    id: str
    kind: PromptKind
    session_id: str
    short_code: str
    questions: list[Question] = field(default_factory=list)
    approval_options: list[Option] = field(default_factory=list)
    ambiguous: bool = False
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending | answered | expired | cancelled
    message_ref: tuple[str, str] | None = None

    # ------------------------------------------------------------------ 渲染
    def render(self) -> str:
        # 只有一条待答时不显示短码：短码是给"同时有多条提示"消歧用的，
        # 单条还要求用户抄码，实际体验就是"看不懂怎么回"。
        head = f"[{self.short_code}] " if self.ambiguous else ""
        if self.kind == "approval":
            lines = [head + "需要你确认一个操作：", ""]
            for index, option in enumerate(self.approval_options, start=1):
                lines.append(f"{index}. {option.label}")
            lines.append("")
            lines.append("直接回数字即可：1 = 同意，2 = 拒绝。")
            return "\n".join(lines)
        total = len(self.questions)
        lines: list[str] = []
        for index, question in enumerate(self.questions, start=1):
            prefix = head if index == 1 else " " * len(head)
            lines.append(f"{prefix}Q{index}/{total} {question.header or ''}".rstrip())
            lines.append(" " * len(head) + question.text)
            for opt_index, option in enumerate(question.options, start=1):
                suffix = f"　{option.description}" if option.description else ""
                lines.append(f"{' ' * len(head)}{opt_index}. {option.label}{suffix}")
            hint = "可多选，用逗号分隔" if question.multi_select else "单选"
            lines.append(f"{' ' * len(head)}（{hint}；可回「其他：你的答案」或「跳过」）")
            lines.append("")
        if total > 1:
            lines.append("按题序回数字，例如「1 2」；同时有多条待答时，前面加上面方括号里的编号。")
        else:
            lines.append("直接回数字即可，例如「1」。也可以回「其他：你的答案」或「跳过」。")
        return "\n".join(lines).strip()

    # ------------------------------------------------------------------ 结构
    def to_host_payload(self) -> dict[str, Any]:
        if self.kind == "approval":
            return {"approval_id": self.id, "options": [o.option_id for o in self.approval_options]}
        return {
            "interaction_id": self.id,
            "questions": [
                {
                    "question_id": q.question_id,
                    "header": q.header,
                    "question": q.text,
                    "multi_select": q.multi_select,
                    "options": [
                        {"option_id": o.option_id, "label": o.label, "description": o.description}
                        for o in q.options
                    ],
                }
                for q in self.questions
            ],
        }


@dataclass
class ParseResult:
    ok: bool
    prompt_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    ambiguous: tuple[str, ...] = ()


class PromptRegistry:
    """待答提示的登记处；持久化只存"编号 → 待答"的最小信息。"""

    def __init__(self) -> None:
        self._prompts: dict[str, Prompt] = {}
        self._by_code: dict[str, str] = {}
        self._by_message: dict[tuple[str, str], str] = {}

    # ------------------------------------------------------------------ 写
    def add(self, prompt: Prompt) -> Prompt:
        if not prompt.short_code:
            prompt.short_code = self._new_code()
        # 已有别的待答提示时才算"有歧义"，渲染时才需要带短码
        prompt.ambiguous = bool(self.pending(prompt.session_id))
        self._prompts[prompt.id] = prompt
        self._by_code[prompt.short_code.upper()] = prompt.id
        return prompt

    def attach_message(self, prompt: Prompt, chat_id: str, message_id: str) -> None:
        prompt.message_ref = (chat_id, message_id)
        self._by_message[(chat_id, message_id)] = prompt.id

    def close(self, prompt_id: str, status: str = "answered") -> None:
        prompt = self._prompts.get(prompt_id)
        if prompt is not None:
            prompt.status = status
            self._by_code.pop(prompt.short_code.upper(), None)

    # ------------------------------------------------------------------ 读
    def pending(self, session_id: str) -> list[Prompt]:
        return [p for p in self._prompts.values() if p.status == "pending" and p.session_id == session_id]

    def by_code(self, code: str) -> Prompt | None:
        pid = self._by_code.get(code.upper())
        return self._prompts.get(pid) if pid else None

    def get(self, prompt_id: str) -> Prompt | None:
        return self._prompts.get(prompt_id)

    def by_message(self, chat_id: str, message_id: str) -> Prompt | None:
        pid = self._by_message.get((chat_id, message_id))
        return self._prompts.get(pid) if pid else None

    # ------------------------------------------------------------------ 内部
    def _new_code(self) -> str:
        for _ in range(50):
            code = secrets.token_hex(2).upper()
            if code not in self._by_code:
                return code
        raise RuntimeError("分配 short_code 失败")


def parse_reply(
    text: str,
    pending: list[Prompt],
    *,
    quoted_message: tuple[str, str] | None = None,
    registry: PromptRegistry | None = None,
) -> ParseResult:
    """把一条 IM 回复解析成宿主可用的答案。

    优先级：引用回复 > 带编号 > 唯一待答。
    """
    raw = (text or "").strip()
    if not raw:
        return ParseResult(ok=False, error="空回复")

    target: Prompt | None = None
    body = raw

    if quoted_message is not None and registry is not None:
        target = registry.by_message(*quoted_message)
        if target is not None and target.status != "pending":
            return ParseResult(ok=False, error="这条提示已经处理过了")

    match = _CODE_RE.match(raw)
    if target is None and match:
        code, rest = match.group(1).upper(), match.group(2).strip()
        found = next((p for p in pending if p.short_code.upper() == code), None)
        if found is None:
            return ParseResult(ok=False, error=f"没有待答的编号 {code}")
        target, body = found, rest

    if target is None:
        if not pending:
            return ParseResult(ok=False, error="当前没有待答的提示")
        if len(pending) > 1:
            codes = " / ".join(p.short_code for p in pending)
            return ParseResult(ok=False, ambiguous=tuple(p.short_code for p in pending),
                               error=f"现在有 {len(pending)} 个待答（{codes}），请带上编号，例如「{pending[0].short_code} 1」")
        target = pending[0]

    if target.status != "pending":
        return ParseResult(ok=False, error="这条提示已经处理过了")

    if target.kind == "approval":
        return _parse_approval(target, body)
    return _parse_question(target, body)


def _parse_approval(prompt: Prompt, body: str) -> ParseResult:
    text = body.strip().lower()
    if not text:
        return ParseResult(ok=False, error="回复为空，未提交")
    if any(text == word or text.startswith(word) for word in _DENY_WORDS):
        return ParseResult(ok=True, prompt_id=prompt.id, payload={"decision": "deny"})
    if any(text == word or text.startswith(word) for word in _ALLOW_WORDS):
        return ParseResult(ok=True, prompt_id=prompt.id, payload={"decision": "approve"})
    if text.isdigit():
        index = int(text)
        if 1 <= index <= len(prompt.approval_options or ()):
            option = prompt.approval_options[index - 1]
            decision = "approve" if "allow" in option.option_id or option.option_id.endswith("yes") else "deny"
            return ParseResult(ok=True, prompt_id=prompt.id, payload={"decision": decision})
    return ParseResult(ok=False, error="没看懂：回「同意」或「拒绝」")


def _parse_question(prompt: Prompt, body: str) -> ParseResult:
    text = body.strip()
    if not text:
        return ParseResult(ok=False, error="回复为空，未提交")

    if any(text == word for word in _SKIP_WORDS):
        answers = [{"question_id": q.question_id, "selected_option_ids": [], "skipped": True} for q in prompt.questions]
        return ParseResult(ok=True, prompt_id=prompt.id, payload={"answers": answers})

    other_match = re.match(r"^其他\s*[:：]\s*(.+)$", text, re.S)
    other_text = other_match.group(1).strip() if other_match else None

    numbers: list[list[int]] = []
    if other_text is None:
        tokens = [token for token in re.split(r"[\s,，、]+", text) if token]
        if not tokens or not all(token.isdigit() for token in tokens):
            return ParseResult(ok=False, error="没看懂：回编号（如 1），或「其他：你的答案」")
        if len(prompt.questions) > 1 and len(numbers) == 0:
            # 多题时必须按题序给出等量编号，或用「q1=1」形式
            if all("=" in token for token in tokens):
                return ParseResult(ok=False, error="暂不支持 q= 形式，请按题序回数字")
            if len(tokens) == 1:
                return ParseResult(ok=False, error=f"这有 {len(prompt.questions)} 题，请按题序回，例如「1 2」")
        numbers = [[int(token) for token in tokens]]

    answers: list[dict[str, Any]] = []
    if other_text is not None:
        for index, question in enumerate(prompt.questions):
            if index == 0:
                answers.append({"question_id": question.question_id, "selected_option_ids": [],
                                "other_text": other_text, "skipped": False})
            else:
                return ParseResult(ok=False, error=f"第 {index + 1} 题还没答")
        return ParseResult(ok=True, prompt_id=prompt.id, payload={"answers": answers})

    picked = numbers[0]
    for index, question in enumerate(prompt.questions):
        if index >= len(picked):
            return ParseResult(ok=False, error=f"第 {index + 1} 题还没答")
        value = picked[index]
        if not 1 <= value <= len(question.options):
            return ParseResult(ok=False, error=f"第 {index + 1} 题只有 {len(question.options)} 个选项")
        answers.append({
            "question_id": question.question_id,
            "selected_option_ids": [question.options[value - 1].option_id],
            "skipped": False,
        })
    return ParseResult(ok=True, prompt_id=prompt.id, payload={"answers": answers})


def build_prompt(
    *,
    kind: PromptKind,
    session_id: str,
    questions: list[Question] | None = None,
    approval_options: list[Option] | None = None,
    prompt_id: str | None = None,
) -> Prompt:
    return Prompt(
        id=prompt_id or secrets.token_hex(8),
        kind=kind,
        session_id=session_id,
        short_code="",
        questions=list(questions or []),
        approval_options=list(approval_options or [
            Option("allow_once", "同意（只这一次）"),
            Option("deny", "拒绝"),
        ]),
    )
