from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


DEFAULT_UNKNOWN_CONTEXT_WINDOW = 1_000_000
DEFAULT_UNKNOWN_OUTPUT_TOKENS = 8_192
CONTEXT_PROBE_TOKEN_COUNT = 3_000_000
CONTEXT_PROBE_TIMEOUT = 8.0
LEGACY_ENV_IMPORT_MARKER = "imported_from_legacy_env"

CONTEXT_LIMIT_FIELDS = (
    "context_window",
    "context_length",
    "max_context_length",
    "max_model_len",
    "max_sequence_length",
    "input_token_limit",
)
OUTPUT_LIMIT_FIELDS = (
    "max_output_tokens",
    "output_token_limit",
    "max_completion_tokens",
)
_TOKEN_COUNT_PATTERN = r"([0-9][0-9,._ ]*(?:\.[0-9]+)?\s*[kKmM]?)"
CONTEXT_LIMIT_ERROR_PATTERNS = (
    re.compile(r"maximum context length is\s*" + _TOKEN_COUNT_PATTERN + r"\s*tokens?", re.I),
    re.compile(r"max(?:imum)?(?: model)? context(?: length| window)?(?: is|:)?\s*" + _TOKEN_COUNT_PATTERN + r"\s*tokens?", re.I),
    re.compile(r"context(?: length| window)? limit(?: is|:)?\s*" + _TOKEN_COUNT_PATTERN + r"\s*tokens?", re.I),
)


KNOWN_MODEL_LIMITS: list[tuple[str, int, int]] = [
    ("gpt-5.5-pro", 1050000, 128000),
    ("gpt-5.5", 1050000, 128000),
    ("gpt-5.4-mini", 400000, 128000),
    ("gpt-5.4-nano", 400000, 128000),
    ("gpt-5.4", 1050000, 128000),
    ("gpt-5.2", 400000, 128000),
    ("gpt-5-mini", 400000, 128000),
    ("gpt-5-nano", 400000, 128000),
    ("gpt-5", 400000, 128000),
    ("gpt-4.1", 1047576, 32768),
    ("gpt-4o", 128000, 16384),
    ("gpt-4-turbo", 128000, 4096),
    ("gpt-4", 128000, 8192),
    ("gpt-3.5", 16385, 4096),
    ("o4-mini", 200000, 100000),
    ("o3", 200000, 100000),
    ("o1", 200000, 100000),
    ("deepseek-v4", 1000000, 384000),
    ("deepseek-reasoner", 1000000, 384000),
    ("deepseek-chat", 1000000, 384000),
    ("deepseek", 1000000, 384000),
    ("claude-fable-5", 1000000, 128000),
    ("claude-mythos-5", 1000000, 128000),
    ("claude-opus-4.8", 1000000, 128000),
    ("claude-opus-4.7", 1000000, 128000),
    ("claude-opus-4.6", 1000000, 128000),
    ("claude-sonnet-4.5", 1000000, 64000),
    ("claude-haiku-4.5", 200000, 64000),
    ("claude", 200000, 64000),
    ("qwen", 128000, 8192),
    ("glm-4", 128000, 8192),
]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        n = int(value)
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


def _safe_nonnegative_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if number >= 0 else default
    except (TypeError, ValueError):
        return default


MODEL_PRICING_FIELDS = (
    "input_cost_per_million",
    "output_cost_per_million",
    "cache_read_cost_per_million",
    "cache_write_cost_per_million",
    "cost_budget_usd",
)


def profile_pricing(profile: Optional[dict]) -> dict[str, float]:
    row = profile if isinstance(profile, dict) else {}
    return {
        key: _safe_nonnegative_float(row.get(key), 0.0)
        for key in MODEL_PRICING_FIELDS
    }


def _parse_token_count(value: Any) -> int:
    text = str(value or "").strip().lower().replace(",", "").replace("_", "").replace(" ", "")
    if not text:
        return 0
    multiplier = 1
    if text.endswith("k"):
        multiplier = 1_000
        text = text[:-1]
    elif text.endswith("m"):
        multiplier = 1_000_000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except (TypeError, ValueError):
        return 0


def _clean_reasoning_effort(value: Any) -> str:
    # UI provides max/high/medium/low, but keep custom provider values possible.
    return str(value or "").strip().lower()


def _clean_thinking_mode(value: Any) -> str:
    # UI provides enabled/disabled, but keep custom provider values possible.
    return str(value or "").strip().lower()


def _known_limits_for_model(model_id: str) -> tuple[int, int] | None:
    mid = str(model_id or "").lower()
    for prefix, known_ctx, known_out in KNOWN_MODEL_LIMITS:
        if mid.startswith(prefix):
            return known_ctx, known_out
    return None


def infer_model_limits(model_id: str, raw: Optional[dict] = None) -> dict[str, Any]:
    raw = raw or {}
    candidates = [raw.get(key) for key in CONTEXT_LIMIT_FIELDS]
    raw_ctx = next((_safe_int(v) for v in candidates if _safe_int(v) > 0), 0)
    ctx = raw_ctx
    ctx_source = "api" if raw_ctx > 0 else ""
    output_candidates = [raw.get(key) for key in OUTPUT_LIMIT_FIELDS]
    raw_out = next((_safe_int(v) for v in output_candidates if _safe_int(v) > 0), 0)
    out = raw_out
    out_source = "api" if raw_out > 0 else ""
    if ctx <= 0 or out <= 0:
        known_limits = _known_limits_for_model(model_id)
        if known_limits:
            known_ctx, known_out = known_limits
            if ctx <= 0:
                ctx = known_ctx
                ctx_source = "known"
            if out <= 0:
                out = known_out
                out_source = "known"
    if raw_ctx <= 0 and ctx <= 0:
        ctx = DEFAULT_UNKNOWN_CONTEXT_WINDOW
        ctx_source = "default"
    if raw_out <= 0:
        out = max(out or DEFAULT_UNKNOWN_OUTPUT_TOKENS, DEFAULT_UNKNOWN_OUTPUT_TOKENS)
        out_source = out_source or "default"
    return {
        "context_window": ctx,
        "max_output_tokens": out,
        "context_source": ctx_source or "default",
        "output_source": out_source or "default",
    }


def infer_model_task_capabilities(
    model_id: str,
    profile_name: str = "",
    context_window: int = 0,
) -> dict[str, Any]:
    """Infer concise task-routing hints from a model family/name.

    These are conservative routing hints for the parent agent, not guarantees
    that every provider endpoint exposes every modality of a model family.
    """
    key = f"{profile_name} {model_id}".strip().lower()
    tags: list[str] = []
    descriptions: list[str] = []

    def add(tag: str, description: str) -> None:
        if tag not in tags:
            tags.append(tag)
            descriptions.append(description)

    low_cost_variant = bool(re.search(
        r"(?:^|[-_/])(mini|nano|flash|lite|haiku|turbo|small)(?:[-_. /]|$)",
        key,
    ))
    if "deepseek" in key or "minimax" in key or low_cost_variant:
        add(
            "low_cost_parallel",
            "低成本/多并发：批量总结、信息抽取、常规代码探索和大量独立 subagent",
        )

    is_minimax = "minimax" in key
    hard_family = any(name in key for name in ("gpt", "claude", "glm"))
    hard_variant = any(name in key for name in (
        "reasoner", "reasoning", "thinking", "-pro", "-max", "opus",
        "gemini-pro", "gemini-3.1-pro", "grok", "mimo-v2.5-pro",
        "kimi-k2", "qwen-max", "qwen3-max", "mistral-large", "command-r-plus",
    )) or bool(re.search(r"(?:^|[-_/])o[134](?:[-_. /]|$)", key))
    if (hard_family or hard_variant) and not is_minimax:
        add(
            "hard_reasoning",
            "高难度：复杂推理、架构设计、疑难调试和长链路决策",
        )

    if any(name in key for name in (
        "deepseek", "gemini", "grok", "perplexity", "sonar", "deep-research",
        "deep_research", "command-r",
    )):
        add(
            "research",
            "调查调研：多源搜索、资料核验、事实交叉验证和研究综述",
        )

    broad_multimodal_family = any(name in key for name in (
        "gpt", "claude", "gemini", "grok", "minimax-m3", "mimo", "qwen", "kimi",
    ))
    explicit_multimodal = any(name in key for name in (
        "vision", "-vl", "_vl", "omni", "multimodal", "pixtral", "llava", "molmo",
        "internvl", "cogvlm", "nova-pro", "nova-lite", "phi-vision", "gemma-vision",
    )) or bool(re.search(r"glm[-_.]?[0-9.]*v(?:[-_. /]|$)", key))
    if broad_multimodal_family or explicit_multimodal:
        add(
            "multimodal_candidate",
            "多模态候选：图片识别、OCR、UI 截图和图文理解；须确认具体型号及接口支持图片输入",
        )

    code_or_agent_family = any(name in key for name in (
        "gpt", "claude", "glm", "deepseek", "gemini", "grok", "minimax-m3", "mimo",
        "qwen", "kimi", "coder", "codestral", "mistral", "llama",
    ))
    if code_or_agent_family:
        add(
            "coding",
            "代码：代码理解、实现修改、测试和调试",
        )
        add(
            "agent",
            "Agent：工具调用、任务规划、状态跟踪和多步骤执行",
        )

    if _safe_int(context_window, 0) >= 200_000:
        add(
            "long_context",
            "长上下文：大型文档、长日志和大代码库的总结与检索",
        )

    if not tags:
        add(
            "general",
            "通用：未识别到明确专长，默认继承父模型，除非已有人工验证",
        )
    return {
        "capability_tags": tags,
        "capability_description": "；".join(descriptions),
        "capability_source": "automatic:model-family-heuristic",
    }


def _normalize_base_url(base_url: str) -> str:
    url = str(base_url or "").strip().rstrip("/")
    if not url:
        return ""
    if url.endswith("/models"):
        return url[: -len("/models")]
    return url


def models_url_for_base(base_url: str) -> str:
    base = _normalize_base_url(base_url)
    if not base:
        return ""
    return base + "/models"


def chat_completions_url_for_base(base_url: str) -> str:
    base = _normalize_base_url(base_url)
    if not base:
        return ""
    return base + "/chat/completions"


def extract_context_window_from_error(error_body: Any) -> int:
    if isinstance(error_body, (dict, list)):
        text = json.dumps(error_body, ensure_ascii=False)
    else:
        text = str(error_body or "")
    for pattern in CONTEXT_LIMIT_ERROR_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        tokens = _parse_token_count(match.group(1))
        if tokens > 0:
            return tokens
    return 0


def probe_context_window_from_error(
    client: httpx.Client,
    base_url: str,
    headers: dict[str, str],
    model_id: str,
    timeout: float = CONTEXT_PROBE_TIMEOUT,
) -> int:
    url = chat_completions_url_for_base(base_url)
    if not url or not str(model_id or "").strip():
        return 0
    probe_text = "x " * CONTEXT_PROBE_TOKEN_COUNT
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": probe_text}],
        "max_tokens": 1,
        "stream": False,
    }
    try:
        resp = client.post(url, headers=headers, json=payload, timeout=timeout)
    except httpx.HTTPError:
        return 0
    if resp.status_code != 400:
        return 0
    bodies: list[Any] = [resp.text]
    try:
        bodies.append(resp.json())
    except ValueError:
        pass
    for body in bodies:
        context_window = extract_context_window_from_error(body)
        if context_window > 0:
            return context_window
    return 0


def probe_model_context(
    base_url: str,
    api_key: str,
    model_id: str,
    fallback: Optional[dict] = None,
    timeout: float = 20.0,
) -> Dict[str, Any]:
    base = _normalize_base_url(base_url)
    if not base:
        raise ValueError("missing base_url")
    mid = str(model_id or "").strip()
    if not mid:
        raise ValueError("missing model")
    fallback = fallback if isinstance(fallback, dict) else {}
    limits = infer_model_limits(mid, fallback)
    headers = {}
    if str(api_key or "").strip():
        headers["Authorization"] = "Bearer " + str(api_key).strip()
    probed_context = 0
    if headers.get("Authorization"):
        with httpx.Client(timeout=timeout) as client:
            probed_context = probe_context_window_from_error(client, base, headers, mid)
    if probed_context > 0:
        limits["context_window"] = probed_context
        limits["context_source"] = "probe"
        if int(limits["max_output_tokens"]) >= probed_context:
            limits["max_output_tokens"] = min(DEFAULT_UNKNOWN_OUTPUT_TOKENS, max(1, probed_context - 1))
            limits["output_source"] = "default"
    return {
        "id": mid,
        "context_window": limits["context_window"],
        "model_context_window": limits["context_window"],
        "max_output_tokens": limits["max_output_tokens"],
        "limit_source": limits["context_source"],
        "context_window_source": limits["context_source"],
        "output_limit_source": limits["output_source"],
        "probe_attempted": bool(headers.get("Authorization")),
        "probe_succeeded": probed_context > 0,
    }


def profile_store_path(project_root: Path) -> Path:
    return Path(project_root).resolve() / "model_profiles.json"


def legacy_profile_store_path(project_root: Path) -> Path:
    return Path(project_root).resolve() / "app" / "model_profiles.json"


def load_store(project_root: Path) -> dict:
    path = profile_store_path(project_root)
    if not path.is_file():
        legacy_path = legacy_profile_store_path(project_root)
        if legacy_path.is_file():
            path = legacy_path
    if not path.is_file():
        return {"profiles": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"profiles": []}
    if not isinstance(data, dict):
        return {"profiles": []}
    profiles = data.get("profiles")
    if not isinstance(profiles, list):
        data["profiles"] = []
    return {"profiles": data["profiles"]}


def save_store(project_root: Path, data: dict) -> None:
    path = profile_store_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "profiles": [p for p in data.get("profiles", []) if isinstance(p, dict)],
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def public_profile(profile: dict) -> dict:
    out = dict(profile)
    out["enabled"] = profile.get("enabled") is not False
    out["api_key_set"] = bool(str(profile.get("api_key") or "").strip())
    out["usable"] = is_usable_profile(profile)
    inferred = infer_model_task_capabilities(
        str(profile.get("model") or ""),
        str(profile.get("name") or ""),
        _safe_int(profile.get("context_window"), 0),
    )
    out.update(inferred)
    custom_description = str(profile.get("capability_description") or "").strip()
    if custom_description:
        out["capability_description"] = custom_description
        out["capability_source"] = "manual"
    return out


def is_usable_profile(profile: object) -> bool:
    """Return whether a saved profile has everything needed for execution."""
    if not isinstance(profile, dict):
        return False
    if profile.get("enabled") is False:
        return False
    if not str(profile.get("id") or "").strip():
        return False
    if not str(profile.get("model") or "").strip():
        return False
    if not str(profile.get("base_url") or "").strip():
        return False
    llm_type = str(profile.get("llm_type") or "openai").strip().lower()
    api_key = str(profile.get("api_key") or "").strip()
    if llm_type != "local" and (not api_key or "YOUR_API_KEY" in api_key.upper()):
        return False
    if _safe_int(profile.get("context_window"), 0) <= 0:
        return False
    if _safe_int(profile.get("max_output_tokens"), 0) <= 0:
        return False
    return True


def _legacy_env_profile_payload(env: dict[str, Any]) -> Optional[dict]:
    """Translate a complete legacy .env model configuration into a profile payload."""
    llm_type = str(env.get("EXECUTOR_LLM_TYPE") or "openai").strip().lower() or "openai"
    if llm_type == "local":
        model = str(env.get("LOCAL_LLM") or env.get("EXECUTOR_LLM") or "").strip()
        local_host = str(env.get("LOCAL_LLM_HOST") or "").strip()
        base_url = local_host or str(env.get("OPENAI_BASE_URL") or "").strip()
        if local_host and base_url.rstrip("/").lower().endswith("/v1") is False:
            base_url = base_url.rstrip("/") + "/v1"
    else:
        model = str(env.get("EXECUTOR_LLM") or "").strip()
        base_url = str(env.get("OPENAI_BASE_URL") or "").strip()
    api_key = str(env.get("OPENAI_API_KEY") or "").strip()
    if not model or not base_url:
        return None
    if llm_type != "local" and (not api_key or "YOUR_API_KEY" in api_key.upper()):
        return None

    limits = infer_model_limits(model)
    context_window = _safe_int(env.get("CONTEXT_WINDOW"), limits["context_window"])
    max_output_tokens = _safe_int(env.get("MAX_OUTPUT_TOKENS"), limits["max_output_tokens"])
    if context_window <= 0 or max_output_tokens <= 0:
        return None
    inferred_model_window = _safe_int(limits.get("context_window"), 0)
    model_context_window = max(inferred_model_window, context_window + max_output_tokens)
    return {
        "name": model,
        "model": model,
        "llm_type": llm_type,
        "base_url": base_url,
        "api_key": api_key,
        "context_window": context_window,
        "max_output_tokens": max_output_tokens,
        "model_context_window": model_context_window,
        "thinking_mode": str(env.get("LLM_THINKING_MODE") or "").strip(),
        "reasoning_effort": str(env.get("LLM_REASONING_EFFORT") or "").strip(),
        "temperature": str(env.get("EXECUTOR_TEMPERATURE") or "").strip(),
        "extra_body_json": str(env.get("LLM_EXTRA_BODY_JSON") or "").strip(),
        "enabled": True,
    }


def _legacy_env_profile_identity(profile: dict) -> tuple[str, ...]:
    return (
        str(profile.get("model") or "").strip(),
        str(profile.get("llm_type") or "openai").strip().lower(),
        _normalize_base_url(str(profile.get("base_url") or "")),
        str(profile.get("api_key") or "").strip(),
        str(_safe_int(profile.get("context_window"), 0)),
        str(_safe_int(profile.get("max_output_tokens"), 0)),
        str(profile.get("thinking_mode") or "").strip().lower(),
        str(profile.get("reasoning_effort") or "").strip().lower(),
        str(profile.get("temperature") or "").strip(),
        str(profile.get("extra_body_json") or "").strip(),
    )


def register_legacy_env_model_profile(project_root: Path, env: dict[str, Any]) -> dict:
    """Import legacy .env model settings exactly once without making .env a runtime fallback."""
    data = load_store(project_root)
    profiles = [p for p in data.get("profiles", []) if isinstance(p, dict)]
    already_imported = next(
        (p for p in profiles if p.get(LEGACY_ENV_IMPORT_MARKER) is True),
        None,
    )
    if already_imported is not None:
        model = str(already_imported.get("model") or "").strip()
        if str(already_imported.get("name") or "").strip() == f"{model}（从 .env 导入）":
            already_imported["name"] = model
            save_store(project_root, {"profiles": profiles})
        return {"ok": True, "action": "already_imported", "profile": dict(already_imported)}

    payload = _legacy_env_profile_payload(env)
    if payload is None:
        return {"ok": True, "action": "skipped_incomplete", "profile": None}

    identity = _legacy_env_profile_identity(payload)
    existing = next(
        (p for p in profiles if _legacy_env_profile_identity(p) == identity),
        None,
    )
    if existing is not None:
        existing[LEGACY_ENV_IMPORT_MARKER] = True
        existing.setdefault("source", "legacy_env_import")
        existing.setdefault("legacy_env_imported_at", _now())
        save_store(project_root, {"profiles": profiles})
        return {"ok": True, "action": "matched_existing", "profile": dict(existing)}

    digest = hashlib.sha256("\0".join(identity).encode("utf-8")).hexdigest()[:16]
    payload["id"] = f"legacy-env-{digest}"
    payload["priority"] = len(profiles) + 1
    imported = upsert_profile(project_root, payload)

    data = load_store(project_root)
    for profile in data.get("profiles", []):
        if not isinstance(profile, dict) or profile.get("id") != imported.get("id"):
            continue
        profile[LEGACY_ENV_IMPORT_MARKER] = True
        profile["source"] = "legacy_env_import"
        profile["legacy_env_imported_at"] = _now()
        imported = dict(profile)
        break
    save_store(project_root, data)
    return {"ok": True, "action": "created", "profile": imported}


def upsert_profile(project_root: Path, payload: dict) -> dict:
    data = load_store(project_root)
    profiles = data.setdefault("profiles", [])
    pid = str(payload.get("id") or "").strip()
    if not pid:
        pid = uuid.uuid4().hex
    old_index = next((i for i, p in enumerate(profiles) if isinstance(p, dict) and p.get("id") == pid), -1)
    old = profiles[old_index] if old_index >= 0 else None
    now = _now()
    model = str(payload.get("model") or "").strip()
    name = str(payload.get("name") or model).strip()
    base_url = _normalize_base_url(str(payload.get("base_url") or ""))
    incoming_api_key = str(payload.get("api_key") or "").strip() if "api_key" in payload else ""
    existing_api_key = str((old or {}).get("api_key") or "").strip()
    if not model:
        raise ValueError("missing model")
    if not base_url:
        raise ValueError("missing base_url")
    llm_type = str(payload.get("llm_type") or "openai").strip().lower() or "openai"
    if llm_type != "local" and not incoming_api_key and not existing_api_key:
        raise ValueError("missing api_key")
    profile = dict(old or {})
    priority_default = _safe_int((old or {}).get("priority"), len(profiles) + 1)
    enabled = payload.get("enabled") if "enabled" in payload else (old or {}).get("enabled", True)
    profile.update(
        {
            "id": pid,
            "name": name,
            "model": model,
            "llm_type": llm_type,
            "base_url": base_url,
            "context_window": _safe_int(payload.get("context_window"), DEFAULT_UNKNOWN_CONTEXT_WINDOW),
            "max_output_tokens": _safe_int(payload.get("max_output_tokens"), 8192),
            "model_context_window": _safe_int(payload.get("model_context_window"), 0),
            "thinking_mode": _clean_thinking_mode(payload.get("thinking_mode")),
            "reasoning_effort": _clean_reasoning_effort(payload.get("reasoning_effort")),
            "temperature": str(payload.get("temperature") or "").strip(),
            "extra_body_json": str(payload.get("extra_body_json") or "").strip(),
            "priority": _safe_int(payload.get("priority"), priority_default),
            "enabled": enabled is not False,
            "updated_at": now,
        }
    )
    for pricing_field in MODEL_PRICING_FIELDS:
        if pricing_field in payload:
            profile[pricing_field] = _safe_nonnegative_float(
                payload.get(pricing_field),
                0.0,
            )
    if "capability_description" in payload:
        capability_description = str(payload.get("capability_description") or "").strip()
        if capability_description:
            profile["capability_description"] = capability_description
        else:
            profile.pop("capability_description", None)
    if incoming_api_key:
        profile["api_key"] = incoming_api_key
    if not profile.get("created_at"):
        profile["created_at"] = now
    if old_index >= 0:
        profiles[old_index] = profile
    else:
        profiles.append(profile)
    save_store(project_root, data)
    return profile


def sorted_profiles(project_root: Path) -> list[dict]:
    profiles = [p for p in load_store(project_root).get("profiles", []) if isinstance(p, dict)]
    return sorted(
        profiles,
        key=lambda p: (
            _safe_int(p.get("priority"), 999999),
            str(p.get("updated_at") or ""),
            str(p.get("id") or ""),
        ),
    )


def top_profile(project_root: Path) -> Optional[dict]:
    profiles = [p for p in sorted_profiles(project_root) if is_usable_profile(p)]
    return dict(profiles[0]) if profiles else None


def reorder_profiles(project_root: Path, ordered_ids: list[str]) -> list[dict]:
    data = load_store(project_root)
    profiles = [p for p in data.get("profiles", []) if isinstance(p, dict)]
    rank = {str(pid): idx + 1 for idx, pid in enumerate(ordered_ids) if str(pid).strip()}
    next_rank = len(rank) + 1
    for p in profiles:
        pid = str(p.get("id") or "")
        if pid in rank:
            p["priority"] = rank[pid]
        else:
            p["priority"] = next_rank
            next_rank += 1
    data["profiles"] = profiles
    save_store(project_root, data)
    return sorted_profiles(project_root)


def delete_profile(project_root: Path, profile_id: str) -> bool:
    data = load_store(project_root)
    before = len(data.get("profiles", []))
    data["profiles"] = [p for p in data.get("profiles", []) if p.get("id") != profile_id]
    save_store(project_root, data)
    return len(data["profiles"]) != before


def set_profile_enabled(project_root: Path, profile_id: str, enabled: bool) -> Optional[dict]:
    """Persist a profile's availability without deleting its configuration."""
    data = load_store(project_root)
    for profile in data.get("profiles", []):
        if not isinstance(profile, dict) or str(profile.get("id") or "") != str(profile_id or ""):
            continue
        profile["enabled"] = bool(enabled)
        profile["updated_at"] = _now()
        save_store(project_root, data)
        return dict(profile)
    return None


def get_profile(project_root: Path, profile_id: str) -> Optional[dict]:
    if not profile_id:
        return None
    for profile in load_store(project_root).get("profiles", []):
        if isinstance(profile, dict) and profile.get("id") == profile_id:
            return dict(profile)
    return None


def fallback_chain(project_root: Path, selected_profile_id: str = "") -> list[dict]:
    selected = get_profile(project_root, selected_profile_id)
    chain: list[dict] = []
    seen: set[str] = set()
    if is_usable_profile(selected):
        chain.append(selected)
        seen.add(str(selected.get("id") or ""))
    for profile in sorted_profiles(project_root):
        if not is_usable_profile(profile):
            continue
        pid = str(profile.get("id") or "")
        if pid and pid not in seen:
            chain.append(dict(profile))
            seen.add(pid)
    return chain


def profile_cache_key(profile: dict) -> str:
    body = json.dumps(
        {
            "id": profile.get("id"),
            "model": profile.get("model"),
            "llm_type": profile.get("llm_type"),
            "base_url": profile.get("base_url"),
            "api_key": profile.get("api_key"),
            "thinking_mode": profile.get("thinking_mode"),
            "reasoning_effort": profile.get("reasoning_effort"),
            "temperature": profile.get("temperature"),
            "extra_body_json": profile.get("extra_body_json"),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def discover_models(base_url: str, api_key: str, timeout: float = 20.0) -> List[Dict[str, Any]]:
    url = models_url_for_base(base_url)
    if not url:
        raise ValueError("missing base_url")
    headers = {}
    if str(api_key or "").strip():
        headers["Authorization"] = "Bearer " + str(api_key).strip()
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data") if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise ValueError("models response is not a list")
        out: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            mid = str(item.get("id") or item.get("name") or "").strip()
            if not mid:
                continue
            raw_has_context = any(k in item for k in CONTEXT_LIMIT_FIELDS)
            raw_has_limits = raw_has_context or any(k in item for k in OUTPUT_LIMIT_FIELDS)
            limits = infer_model_limits(mid, item)
            out.append(
                {
                    "id": mid,
                    "owned_by": item.get("owned_by") or item.get("owner") or "",
                    "created": item.get("created") or None,
                    "context_window": limits["context_window"],
                    "model_context_window": limits["context_window"],
                    "max_output_tokens": limits["max_output_tokens"],
                    "raw_has_limits": raw_has_limits,
                    "limit_source": limits["context_source"],
                    "context_window_source": limits["context_source"],
                    "output_limit_source": limits["output_source"],
                }
            )
    out.sort(key=lambda row: row["id"].lower())
    return out
