"""Independent completion judge for durable Goals."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional, Tuple


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

class JudgeParseError(ValueError):
    pass


def build_judge_prompt(goal: Dict[str, Any], evidence: Any) -> str:
    objective = str(goal.get("objective") or "").strip()
    completion_requested = bool(goal.get("completion_requested_at"))
    submitted_evidence = str(goal.get("completion_request_reason") or "").strip()[:6000]
    evidence_limit = max(
        2000,
        int(os.getenv("GOAL_JUDGE_EVIDENCE_MAX_CHARS", "24000") or 24000),
    )
    if isinstance(evidence, dict):
        goal_dialogue = str(
            evidence.get("goal_dialogue")
            or evidence.get("current_dialogue")
            or ""
        ).strip()
        recent_evidence = str(evidence.get("recent_evidence") or "").strip()
    else:
        goal_dialogue = ""
        recent_evidence = str(evidence or "").strip()
    clipped_recent_evidence = recent_evidence[-evidence_limit:]
    return (
        "You are an independent Goal completion judge. Evaluate only whether the entire "
        "objective is demonstrably complete from the supplied execution evidence.\n\n"
        "Rules:\n"
        "- Return done only when every material part of the objective is complete and the "
        "evidence is sufficient.\n"
        "- A worker's claim that work is complete is not proof by itself.\n"
        "- Return continue when work, verification, or required evidence is missing.\n"
        "- A blocker or need for user input is not completion; return continue.\n"
        "- Do not propose or perform work. Output exactly one JSON object and no markdown.\n\n"
        'Schema: {"verdict":"done|continue","reason":"concise evidence-based reason"}\n\n'
        f"Goal ID: {goal.get('id')}\n"
        f"Worker requested completion: {str(completion_requested).lower()}\n"
        f"Objective:\n{objective}\n\n"
        "Worker-submitted completion evidence (use as an index; corroborate it against "
        "the execution evidence below):\n"
        f"{submitted_evidence or '(no completion evidence submitted)'}\n\n"
        "Goal lifecycle dialogue (complete; not clipped):\n"
        f"{goal_dialogue or '(no Goal-lifecycle dialogue supplied)'}\n\n"
        "Recent auxiliary execution evidence (up to the configured limit):\n"
        f"{clipped_recent_evidence or '(no auxiliary evidence supplied)'}"
    )


def parse_judge_response(raw: str) -> Tuple[str, str]:
    text = str(raw or "").strip()
    if not text:
        raise JudgeParseError("Judge returned an empty response.")
    candidates = [text]
    match = _JSON_OBJECT_RE.search(text)
    if match and match.group(0) != text:
        candidates.append(match.group(0))
    parsed: Optional[Dict[str, Any]] = None
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict):
            parsed = value
            break
    if parsed is None:
        raise JudgeParseError("Judge response is not a JSON object.")
    verdict = str(parsed.get("verdict") or "").strip().lower()
    if verdict not in {"done", "continue"}:
        raise JudgeParseError("Judge verdict must be done or continue.")
    reason = str(parsed.get("reason") or "").strip()
    if not reason:
        raise JudgeParseError("Judge response requires a reason.")
    return verdict, reason[:2000]


def evaluate_goal(
    session_id: str,
    goal: Dict[str, Any],
    evidence: Any,
) -> Dict[str, Any]:
    """Run one independent, tool-free judge call and parse its verdict."""
    from agent_harness import EXECUTOR_TEMPERATURE, resolve_executor_config_for_session
    from llm import LLMRequestContext, LLMRequestPurpose

    client, model, max_output_tokens, _context_window = (
        resolve_executor_config_for_session(session_id)
    )
    candidate_getter = getattr(client, "current_candidate", None)
    candidate = candidate_getter() if callable(candidate_getter) else {}
    if not candidate:
        candidates = list(getattr(client, "candidates", None) or [])
        candidate = dict(candidates[0]) if candidates else {}
    transport = candidate.get("transport")
    complete_text = getattr(transport, "complete_text", None)
    if not callable(complete_text):
        raise RuntimeError("Goal Judge requires a non-streaming LLM transport")

    requested_model = str(candidate.get("model") or model or "")
    request = {
        "model": requested_model,
        "messages": [{"role": "user", "content": build_judge_prompt(goal, evidence)}],
        "temperature": min(float(EXECUTOR_TEMPERATURE), 0.2),
        "max_tokens": int(candidate.get("max_output_tokens") or max_output_tokens),
        "request_context": LLMRequestContext(
            session_id=str(session_id or ""),
            purpose=LLMRequestPurpose.GOAL_JUDGE,
            server_storage_allowed=False,
        ),
    }
    try:
        completion = dict(complete_text(**request) or {})
    except Exception as exc:
        return {
            "failure_kind": "transport",
            "error": str(exc),
            "raw": "",
            "usage": {},
            "model": requested_model,
            "diagnostics": {
                "requested_model": requested_model,
                "max_output_tokens": request["max_tokens"],
                "provider": str(candidate.get("provider") or ""),
                "profile_id": str(candidate.get("profile_id") or ""),
            },
        }

    raw = str(completion.get("text") or "")
    usage = dict(completion.get("usage") or {})
    diagnostics = {
        "requested_model": requested_model,
        "actual_model": str(completion.get("model") or requested_model),
        "max_output_tokens": request["max_tokens"],
        "provider": str(candidate.get("provider") or ""),
        "profile_id": str(candidate.get("profile_id") or ""),
        "response_id": str(completion.get("response_id") or ""),
        "response_status": str(completion.get("status") or ""),
        "finish_reason": str(completion.get("finish_reason") or ""),
        "incomplete_reason": str(completion.get("incomplete_reason") or ""),
        "refusal": str(completion.get("refusal") or ""),
        "content_chars": len(raw),
        "reasoning_tokens": int(usage.get("reasoning_tokens", 0) or 0),
    }
    status = diagnostics["response_status"]
    if completion.get("error") or status == "failed":
        return {
            "failure_kind": "transport",
            "error": str(completion.get("error") or "response_failed"),
            "raw": raw[:4000],
            "usage": usage,
            "model": diagnostics["actual_model"],
            "diagnostics": diagnostics,
        }
    if diagnostics["refusal"]:
        protocol_error = "refusal"
    elif status == "incomplete" or diagnostics["finish_reason"] == "length":
        protocol_error = diagnostics["incomplete_reason"] or "incomplete"
    elif not raw.strip() and diagnostics["reasoning_tokens"] > 0:
        protocol_error = "reasoning_only"
    elif not raw.strip():
        protocol_error = "completed_without_text"
    else:
        protocol_error = ""
    if protocol_error:
        return {
            "failure_kind": "parse",
            "error": protocol_error,
            "raw": raw[:4000],
            "usage": usage,
            "model": diagnostics["actual_model"],
            "diagnostics": diagnostics,
        }
    try:
        verdict, reason = parse_judge_response(raw)
    except JudgeParseError as exc:
        return {
            "failure_kind": "parse",
            "error": str(exc),
            "raw": str(raw or "")[:4000],
            "usage": dict(usage or {}),
            "model": diagnostics["actual_model"],
            "diagnostics": diagnostics,
        }
    return {
        "verdict": verdict,
        "reason": reason,
        "raw": str(raw or "")[:4000],
        "usage": dict(usage or {}),
        "model": diagnostics["actual_model"],
        "diagnostics": diagnostics,
    }
