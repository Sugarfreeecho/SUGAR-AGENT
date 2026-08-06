from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass

from .models import CapabilityRequest
from .store import redact_security_value


_CRITICAL = re.compile(
    r"(?i)(?:format\s+[a-z]:|clear-disk|remove-item\s+[^;\r\n]*(?:\\windows|\\users)"
    r"|reg\s+delete|bcdedit|disable.*(?:firewall|defender)|credential|id_rsa|\.ssh)"
)
_EXPLICIT_HIGH_RISK = re.compile(
    r"(?i)(?:明确|确认|允许|批准|请|需要|就是要|intentionally|explicitly|confirm|approve|allow)"
    r".{0,80}(?:删除|覆盖|清空|系统|外部|上传|发送|delete|overwrite|destroy|system|external|upload|send)"
)

_REVIEWER_MAX_TOKENS = 8192
_REVIEWER_TIMEOUT_SECONDS = 180.0


@dataclass(frozen=True)
class ReviewResult:
    approved: bool
    reason: str
    risk: str
    # False when the automatic reviewer could not produce a decision at all
    # (model failure/timeout/invalid output). The request is still fail-closed
    # (never auto-approved), but the UI must present it as "reviewer
    # unavailable" instead of "auto-review denied".
    available: bool = True


async def review_request(request: CapabilityRequest, *, user_intent: str) -> ReviewResult:
    """Review one immutable request. Failure is deliberately fail-closed."""
    if request.effect in {"credential", "policy_change"} or _CRITICAL.search(request.resource):
        return ReviewResult(
            False, "Critical credential, policy, or system risk.", "critical"
        )
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_review_with_model, request, user_intent),
                timeout=_REVIEWER_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            last_error = exc
    return ReviewResult(
        False,
        f"Automatic reviewer unavailable: {last_error}",
        "unknown",
        available=False,
    )


def _review_with_model(request: CapabilityRequest, user_intent: str) -> ReviewResult:
    from agent_harness import executor_client, executor_model

    prompt = {
        "user_intent": str(redact_security_value(user_intent or ""))[:4000],
        "request": {
            "action": request.action,
            "resource": str(redact_security_value(request.resource))[:4000],
            "effect": request.effect,
            "principal": request.principal,
            "args_digest": request.args_digest,
        },
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You are a read-only security reviewer. You cannot change the request. "
                "Approve only when the exact action is clearly required by the user's "
                "stated intent and does not exfiltrate data, access credentials, persistently "
                "weaken security, or cause disproportionate destruction. Return JSON only: "
                '{"decision":"approve|deny","risk":"low|medium|high|critical","reason":"..."}.'
            ),
        },
        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
    ]

    def _call(extra_body: dict | None = None):
        return executor_client.chat.completions.create(
            model=executor_model,
            messages=messages,
            temperature=0,
            max_tokens=_REVIEWER_MAX_TOKENS,
            timeout=_REVIEWER_TIMEOUT_SECONDS,
            **({"extra_body": extra_body} if extra_body else {}),
        )

    def _extract_text(response) -> str:
        text = str(response.choices[0].message.content or "").strip()
        if text and response.choices[0].finish_reason == "length":
            # Reasoning models can spend the whole budget before emitting the
            # JSON body; a truncated blob is as unusable as an empty one.
            return ""
        return text

    raw = _extract_text(_call())
    if not raw:
        # Retry once with thinking disabled: reasoning-only output (content
        # empty) is common on DeepSeek-style free endpoints with a small
        # max_tokens, and disabling thinking makes the JSON body come back
        # directly instead of after a long chain of thought.
        raw = _extract_text(
            _call(extra_body={"thinking": {"type": "disabled"}})
        )
    if not raw:
        raise ValueError("reviewer returned an empty response")
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"reviewer returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("reviewer returned a non-object response")
    risk = str(data.get("risk") or "unknown").lower()
    decision = str(data.get("decision") or "deny").lower()
    if decision not in {"approve", "deny"}:
        raise ValueError(f"reviewer returned unknown decision {decision!r}")
    reason = str(data.get("reason") or "Reviewer supplied no rationale.")[:1000]
    if risk == "critical":
        return ReviewResult(False, reason, risk)
    if risk == "high" and not _EXPLICIT_HIGH_RISK.search(str(user_intent or "")):
        return ReviewResult(
            False,
            "High-risk requests require explicit authorization in the user's task.",
            risk,
        )
    return ReviewResult(decision == "approve", reason, risk)
