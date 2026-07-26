"""Independent completion judge for durable Goals."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional, Tuple


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class JudgeParseError(ValueError):
    pass


def build_judge_prompt(goal: Dict[str, Any], evidence: str) -> str:
    objective = str(goal.get("objective") or "").strip()
    completion_requested = bool(goal.get("completion_requested_at"))
    evidence_limit = max(
        2000,
        int(os.getenv("GOAL_JUDGE_EVIDENCE_MAX_CHARS", "24000") or 24000),
    )
    clipped_evidence = str(evidence or "")[-evidence_limit:]
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
        f"Execution evidence:\n{clipped_evidence or '(no evidence supplied)'}"
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
    evidence: str,
) -> Dict[str, Any]:
    """Run one independent, tool-free judge call and parse its verdict."""
    from agent_harness import EXECUTOR_TEMPERATURE, resolve_executor_config_for_session
    from agent_openai import single_turn_text_completion

    client, model, max_output_tokens, _context_window = (
        resolve_executor_config_for_session(session_id)
    )
    judge_max_tokens = max(
        128,
        int(os.getenv("GOAL_JUDGE_MAX_OUTPUT_TOKENS", "512") or 512),
    )
    raw, usage = single_turn_text_completion(
        client,
        model,
        build_judge_prompt(goal, evidence),
        temperature=min(float(EXECUTOR_TEMPERATURE), 0.2),
        max_tokens=min(int(max_output_tokens), judge_max_tokens),
    )
    try:
        verdict, reason = parse_judge_response(raw)
    except JudgeParseError as exc:
        return {
            "failure_kind": "parse",
            "error": str(exc),
            "raw": str(raw or "")[:4000],
            "usage": dict(usage or {}),
            "model": str(model or ""),
        }
    return {
        "verdict": verdict,
        "reason": reason,
        "raw": str(raw or "")[:4000],
        "usage": dict(usage or {}),
        "model": str(model or ""),
    }
