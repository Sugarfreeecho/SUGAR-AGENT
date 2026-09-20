"""
使用本仓库内 tokenizer.json（HuggingFace 格式）估算 token 数。

优先用 HuggingFace `tokenizers` 库（Rust 实现、**不依赖 PyTorch**），避免
`transformers.AutoTokenizer` 触发 torch 检测与长导入。

目录默认：<项目根>/tools/deepseek_v3_tokenizer
或通过环境变量 DEEPSEEK_TOKENIZER_DIR 指定。不可用时回退为「字符 / 4」。

另含「整包输入」token 估算（静态 system + key_context + 多轮对话），供 agent_loop /
agent_memory 与右上角占用一致；其中对 agent_harness / agent_tools 的引用在函数内延迟 import，
避免 agent_harness → agent_tokenizer → agent_harness 循环初始化。
"""

from __future__ import annotations

import logging
import hashlib
import os
import platform
import re
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent_messages import AssistantMessage, SystemMessage, ToolMessage, UserMessage

logger = logging.getLogger(__name__)

_TOKENIZER: Any = None
_LOAD_FAILED: bool = False
_TOKENIZER_LOAD_LOCK = threading.Lock()
_FULL_INPUT_TOKEN_CACHE: Dict[Tuple[str, int, str, str, str, str], Tuple[float, int]] = {}
_FULL_INPUT_TOKEN_CACHE_LOCK = threading.Lock()
_FULL_INPUT_TOKEN_CACHE_TTL_SEC = 30.0
_FULL_INPUT_TOKEN_CACHE_MAX = 256
_PROMPT_USAGE_BASELINE_CACHE: Dict[str, Dict[str, Any]] = {}
_PROMPT_USAGE_EXACT_CACHE: Dict[Tuple[str, str], Tuple[float, int, str]] = {}
_PROMPT_USAGE_CACHE_LOCK = threading.Lock()
_PROMPT_USAGE_CACHE_TTL_SEC = 300.0
_PROMPT_USAGE_EXACT_CACHE_MAX = 256
_TOOL_SCHEMA_CACHE: "OrderedDict[int, tuple[Any, str, int]]" = OrderedDict()
_TOOL_SCHEMA_CACHE_LOCK = threading.Lock()
_TOOL_SCHEMA_CACHE_MAX = 32


def _token_cache_text_hash(text: Any) -> str:
    return hashlib.sha1(str(text or "").encode("utf-8", errors="ignore")).hexdigest()


def _tool_definitions_fingerprint(tools: Optional[List[Dict[str, Any]]]) -> str:
    if not tools:
        return ""
    return _tool_schema_cache_values(tools)[0]


def _tool_schema_cache_values(tools: List[Dict[str, Any]]) -> tuple[str, int]:
    key = id(tools)
    with _TOOL_SCHEMA_CACHE_LOCK:
        cached = _TOOL_SCHEMA_CACHE.get(key)
        if cached is not None and cached[0] is tools:
            _TOOL_SCHEMA_CACHE.move_to_end(key)
            return cached[1], int(cached[2])
    raw = json_dumps_stable(list(tools))
    fingerprint = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()
    tokens = count_text_tokens(raw)
    with _TOOL_SCHEMA_CACHE_LOCK:
        _TOOL_SCHEMA_CACHE[key] = (tools, fingerprint, tokens)
        _TOOL_SCHEMA_CACHE.move_to_end(key)
        while len(_TOOL_SCHEMA_CACHE) > _TOOL_SCHEMA_CACHE_MAX:
            _TOOL_SCHEMA_CACHE.popitem(last=False)
    return fingerprint, tokens


def _request_token_fingerprint(message_fingerprint: str, tool_fingerprint: str) -> str:
    raw = f"{message_fingerprint}\n{tool_fingerprint}"
    return hashlib.sha1(raw.encode("ascii", errors="ignore")).hexdigest()


def _full_input_token_cache_key(
    session_id: str,
    llm_history: List[Any],
    key_context: str,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, int, str, str, str]:
    message_fingerprint = _messages_token_fingerprint_from_hashes(
        _messages_token_hashes(list(llm_history or []))
    )
    return (
        str(session_id or "").strip(),
        len(llm_history or []),
        _token_cache_text_hash(key_context or ""),
        message_fingerprint,
        _tool_definitions_fingerprint(tools),
    )


def _message_token_cache_repr(msg: Any) -> Dict[str, Any]:
    additional_kwargs = getattr(msg, "additional_kwargs", None) or {}
    if not isinstance(additional_kwargs, dict):
        additional_kwargs = {}
    data: Dict[str, Any] = {
        "type": type(msg).__name__,
        "content": str(getattr(msg, "content", "") or ""),
    }
    tool_call_id = getattr(msg, "tool_call_id", "")
    if tool_call_id:
        data["tool_call_id"] = str(tool_call_id)
    name = getattr(msg, "name", "")
    if name:
        data["name"] = str(name)
    tool_calls = getattr(msg, "tool_calls", None) or additional_kwargs.get("tool_calls")
    if tool_calls:
        data["tool_calls"] = tool_calls
    return data


def _message_token_cache_hash(msg: Any) -> str:
    raw = json_dumps_stable(_message_token_cache_repr(msg))
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def json_dumps_stable(value: Any) -> str:
    import json

    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    except Exception:
        return str(value)


def _messages_token_fingerprint_from_hashes(hashes: List[str]) -> str:
    # sha1 is retained deliberately: these fingerprints are persisted in the
    # on-disk prompt-usage baseline cache, so changing the digest would invalidate
    # every existing baseline. Hashing the joined list is a single pass over ~1.5k
    # short hex strings, which is not the per-step cost.
    return hashlib.sha1("\n".join(hashes).encode("ascii", errors="ignore")).hexdigest()


# Per-message hash cache. A step's message list is the previous step's list plus a
# few appends, so rehashing every message each step is O(total history) work for
# O(new) changes -- measured, that was 516 ms on the first step of a large session
# and 22 ms in steady state, the single largest per-round cost.
#
# A recent history of previously hashed lists is kept and the *longest object-
# identity prefix* is reused, rather than requiring the same list object to be
# passed again: callers rebuild the list each step while the messages themselves
# are carried over, so keying on the list alone would never hit. The stored
# references also keep every stored identity valid -- storing ``id()`` would let a
# collected message free its address for a new message to inherit the old hash
# (observed as a wrong token estimate in tests).
#
# Messages are treated as immutable once appended, the same assumption the prompt
# caches already make.
_MESSAGE_TOKEN_LIST_CACHE: "deque" = deque(maxlen=8)


def _clear_message_token_hash_cache() -> None:
    _MESSAGE_TOKEN_LIST_CACHE.clear()


def _reuse_hash_prefix(items: List[Any]) -> Tuple[List[str], int]:
    """Longest cached prefix sharing object identity with ``items``."""
    best_hashes: List[str] = []
    best_len = 0
    for cached_len, cached_hashes, cached_msgs in _MESSAGE_TOKEN_LIST_CACHE:
        if cached_len <= best_len or cached_len > len(items):
            continue
        if all(a is b for a, b in zip(items[:cached_len], cached_msgs)):
            best_hashes = cached_hashes
            best_len = cached_len
            if best_len == len(items):
                break
    return best_hashes, best_len


def _messages_token_hashes(messages: List[Any]) -> List[str]:
    """Per-message hashes, reusing the longest shared prefix.

    Mirrors the session-log projection DSH uses: each message is hashed once and
    the result is carried forward, so a step costs O(new messages) rather than
    O(total history).
    """
    items = list(messages or [])
    if not items:
        return []
    cached_hashes, start = _reuse_hash_prefix(items)
    hashes = list(cached_hashes)
    for msg in items[start:]:
        hashes.append(_message_token_cache_hash(msg))
    _MESSAGE_TOKEN_LIST_CACHE.append((len(items), hashes, items))
    return hashes


def _evict_prompt_usage_exact_cache_locked(now: float) -> None:
    expired = [
        key
        for key, cached in _PROMPT_USAGE_EXACT_CACHE.items()
        if now - float(cached[0]) > _PROMPT_USAGE_CACHE_TTL_SEC
    ]
    for key in expired:
        _PROMPT_USAGE_EXACT_CACHE.pop(key, None)
    while len(_PROMPT_USAGE_EXACT_CACHE) > _PROMPT_USAGE_EXACT_CACHE_MAX:
        oldest = min(_PROMPT_USAGE_EXACT_CACHE.items(), key=lambda item: item[1][0])[0]
        _PROMPT_USAGE_EXACT_CACHE.pop(oldest, None)


def _is_loop_marker_text(text: str) -> bool:
    c = (text or "").strip()
    return c == "New Agent Loop Start" or c.startswith("Loop finished")


def _strip_tool_display_prefix(text: Any) -> Any:
    if isinstance(text, list):
        from attachments.content import map_text_parts
        return map_text_parts(text, _strip_tool_display_prefix)
    s = str(text or "")
    return re.sub(r"^(?:\U0001f527\s*)?Tool Call:\s*[^\n]*?->\s*", "", s, count=1)


def _default_tokenizer_dir() -> Path:
    env = (os.getenv("DEEPSEEK_TOKENIZER_DIR") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "tools" / "deepseek_v3_tokenizer"


def _get_tokenizer() -> Optional[Any]:
    """返回 `tokenizers.Tokenizer` 实例，失败则 None（之后始终走字符/4）。"""
    global _TOKENIZER, _LOAD_FAILED
    if _LOAD_FAILED:
        return None
    if _TOKENIZER is not None:
        return _TOKENIZER
    # Startup warming and the first live request may race.  Serialize the actual
    # load so a large tokenizer.json is never parsed twice.
    with _TOKENIZER_LOAD_LOCK:
        if _LOAD_FAILED:
            return None
        if _TOKENIZER is not None:
            return _TOKENIZER
        d = _default_tokenizer_dir()
        path = d / "tokenizer.json"
        if not path.is_file():
            _LOAD_FAILED = True
            logger.info("未找到 DeepSeek 词表（缺 tokenizer.json），token 估算使用字符/4：%s", d)
            return None
        try:
            from tokenizers import Tokenizer  # type: ignore

            _TOKENIZER = Tokenizer.from_file(str(path))
            logger.info("已加载 tokenizer.json 用于 token 估算（tokenizers，无 PyTorch 依赖）：%s", path)
            return _TOKENIZER
        except Exception as e:
            _LOAD_FAILED = True
            logger.warning("加载 tokenizer.json 失败，回退字符/4：%s", e)
            return None


def warm_tokenizer() -> bool:
    """Load the tokenizer and run a tiny encode off the first-request path."""
    started = time.perf_counter()
    tok = _get_tokenizer()
    if tok is None:
        return False
    try:
        tok.encode("MyAgent tokenizer warmup")
    except Exception:
        logger.debug("tokenizer warm-up encode failed", exc_info=True)
        return False
    logger.info("tokenizer warmed ms=%.0f", (time.perf_counter() - started) * 1000.0)
    return True


def _flatten_message_parts(msg: Any) -> str:
    """One message's contribution to the flattened count text (empty when skipped).

    Split out of :func:`_flatten_messages_for_count` so the incremental counter can
    rebuild a tail without re-walking the whole history.
    """
    if isinstance(msg, SystemMessage) and _is_loop_marker_text(getattr(msg, "content", "")):
        return ""
    parts: List[str] = []
    if hasattr(msg, "content"):
        c = msg.content
        if isinstance(c, str):
            parts.append(_strip_tool_display_prefix(c) if isinstance(msg, ToolMessage) else c)
        elif c is not None:
            parts.append(str(c))
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        parts.append(str(msg.tool_calls))
    ak = getattr(msg, "additional_kwargs", None) or {}
    if isinstance(ak, dict) and ak.get("reasoning_content"):
        parts.append(str(ak["reasoning_content"]))
    return "\n\n".join(parts)


def _flatten_messages_for_count(messages: List[Any]) -> str:
    """与历史上 estimate_message 口径一致：汇总 content、tool_calls、reasoning。"""
    return "\n\n".join(_flatten_message_parts(m) for m in messages)


def _count_by_chars_4(s: str) -> int:
    if not s:
        return 0
    return max(0, len(s) // 4)


def count_text_tokens(text: str) -> int:
    s = text or ""
    tok = _get_tokenizer()
    if tok is None:
        return _count_by_chars_4(s)
    try:
        enc = tok.encode(s)
        return len(enc.ids)
    except Exception as e:
        logger.debug("encode 失败，回退字符/4：%s", e)
        return _count_by_chars_4(s)


def count_message_tokens(messages: List[Any]) -> int:
    return count_text_tokens(_flatten_messages_for_count(messages))


# Incremental exact token count for a growing flattened history.
#
# ``_flatten_messages_for_count`` joins per-message parts with "\n\n", so the text
# for N messages is a prefix plus a tail. Tokenizing the concatenation is not the
# same as tokenizing the pieces separately -- but tokenizing ``prefix`` and
# ``"\n\n" + tail`` as two pieces is: measured against the whole-string count that
# matched exactly in 7 of 10 trials and was +1 otherwise, whereas summing
# per-message counts was 3-5% low. The accuracy matters because this number gates
# context compression (``effective_input_est > active_context_window``): an
# under-estimate lets a request overrun the window and the endpoint rejects it.
#
# Cached keys are the *flattened prefixes*, not message identities: callers pass a
# freshly built list each round (reasoning stripped, subagent notes injected), so
# the same history rarely yields the same objects. Comparing the text is
# unambiguous and costs a C-level string compare instead of a tokenizer pass.
#
# Several histories interleave within one round -- the request messages, the
# provider-calibration baseline, and any concurrent session. The exact-match dict
# below carries that load (a dict hit is O(1) on the text's hash), so this deque
# only needs to cover the append case; each entry pins a full flattened history in
# memory, so it stays small.
_FLATTEN_TOKEN_CACHE: "deque" = deque(maxlen=4)
_FLATTEN_TOKEN_EXACT: Dict[str, int] = {}
# Message-identity prefixes for constructing the flattened text itself. The token
# cache avoids re-tokenizing history, but without this companion cache every call
# still walked every message and rebuilt every part before joining the same 1-2 MB
# prefix. ``strip_reasoning_for_api_request`` preserves transformed prefix
# identities, so only newly appended messages need Python-level flattening.
_FLATTEN_TEXT_CACHE: "deque" = deque(maxlen=8)
# Counts how each message-token count was satisfied. See message_token_path_stats.
_MESSAGE_TOKEN_PATH_STATS: Dict[str, int] = {"exact": 0, "prefix": 0, "full": 0}
# Per-call-site split of the same counts, e.g. "estimate:full" / "suffix:full".
# Several distinct histories are counted per round (the request messages and the
# provider-calibration baseline); without this split a round-level counter cannot
# say which one took the expensive path.
_MESSAGE_TOKEN_SITE_STATS: Dict[str, int] = {}
# Set by a caller immediately before invoking the estimator.
_TOKEN_SITE_HINT = ""
# Outcome of the most recent seed attempt. ``""`` means seeding never ran, which
# is itself the diagnosis: the provider-prefix branch was not taken.
_SEED_LAST = ""


def _record_token_path(path: str, chars: int = 0) -> None:
    _MESSAGE_TOKEN_PATH_STATS[path] = _MESSAGE_TOKEN_PATH_STATS.get(path, 0) + 1
    if path == "full":
        # How many characters the tokenizer actually had to chew. A "full" pass on
        # a two-message suffix is free; on the whole 300k-token history it is not.
        # Without this the count alone cannot be read as a cost.
        _MESSAGE_TOKEN_PATH_STATS["full_chars"] = (
            _MESSAGE_TOKEN_PATH_STATS.get("full_chars", 0) + int(chars)
        )
    if _TOKEN_SITE_HINT:
        key = "%s:%s" % (_TOKEN_SITE_HINT, path)
        _MESSAGE_TOKEN_SITE_STATS[key] = _MESSAGE_TOKEN_SITE_STATS.get(key, 0) + 1
        if path == "full":
            # Which call site paid for the full pass, and how big it was. A "full"
            # on a 1.3 MB history is the whole remaining token cost; on a two-message
            # suffix it is free. The count alone cannot distinguish them.
            ckey = "%s:full_chars" % _TOKEN_SITE_HINT
            _MESSAGE_TOKEN_SITE_STATS[ckey] = _MESSAGE_TOKEN_SITE_STATS.get(ckey, 0) + int(chars)


def _clear_flatten_token_cache() -> None:
    _FLATTEN_TOKEN_CACHE.clear()
    _FLATTEN_TOKEN_EXACT.clear()
    _FLATTEN_TEXT_CACHE.clear()


def _flatten_messages_incremental(messages: List[Any]) -> str:
    """Build flattened history by reusing the longest identical message prefix."""
    items = list(messages or [])
    if not items:
        return ""
    best_items: List[Any] = []
    best_text = ""
    for cached_items, cached_text in _FLATTEN_TEXT_CACHE:
        cached_len = len(cached_items)
        if cached_len <= len(best_items) or cached_len > len(items):
            continue
        if all(left is right for left, right in zip(items[:cached_len], cached_items)):
            best_items = cached_items
            best_text = cached_text
            if cached_len == len(items):
                break
    if len(best_items) == len(items):
        text = best_text
    else:
        tail = "\n\n".join(
            _flatten_message_parts(item) for item in items[len(best_items):]
        )
        text = (best_text + "\n\n" + tail) if best_items else tail
    _FLATTEN_TEXT_CACHE.append((items, text))
    return text


def _seed_flatten_token_cache(messages: List[Any], tokens: Optional[int] = None) -> None:
    """Register the flattened text of ``messages`` with a known token count.

    Used where the count already comes from a better source (the provider
    baseline) so no tokenizer pass is warranted, but the *text* still needs to be
    registered: the next request asks for this history plus its own tail, and only
    a stored entry lets it tokenize the tail alone.

    Pass ``tokens`` whenever it is known. Seeding without a count leaves an entry
    that can never satisfy the exact or prefix lookup, so the caller that asks
    about this same history pays a full tokenize -- measured as ``tok_full=1``
    every round with ``tok_exact=0``, i.e. the cache never hit.
    """
    global _SEED_LAST
    try:
        text = _flatten_messages_incremental(messages)
        if not text and not messages:
            _SEED_LAST = "empty"
            return
    except Exception as exc:
        _SEED_LAST = "flatten-failed:%s" % type(exc).__name__
        return
    if tokens is None or tokens <= 0:
        _SEED_LAST = "bad-tokens:%r" % (tokens,)
        return
    _FLATTEN_TOKEN_CACHE.append((text, int(tokens)))
    if len(_FLATTEN_TOKEN_EXACT) > 64:
        _FLATTEN_TOKEN_EXACT.clear()
    _FLATTEN_TOKEN_EXACT[text] = int(tokens)
    _SEED_LAST = "ok:len=%d" % len(text)


def count_message_tokens_incremental(messages: List[Any]) -> int:
    """Token count of the flattened history, tokenizing only newly appended text.

    Two lookup tiers, cheapest first:

    1. Exact text already counted -- a dict hit, no string walk.
    2. A cached *shorter* prefix of this text -- tokenize only the remainder.

    The prefix tier is one-directional on purpose. Measured, a caller that asks for
    a shorter history after a longer one (the provider-calibration baseline after
    the request messages) cannot use a longer cached text at all, and it then fell
    back to a full tokenize every round: ~870 ms on a 700 KB history, which is why
    the estimate still scaled with context length after the first attempt.

    Falls back to the whole-string count when nothing matches, so the result is
    never less exact than :func:`count_message_tokens`.
    """
    # Empty parts are kept: the whole-string path joins them too, so dropping one
    # would collapse two "\n\n" separators into one and under-count (measured up to
    # 17 tokens over 400 messages). Byte-identical text is what makes the cold path
    # equal to :func:`count_message_tokens`.
    text = _flatten_messages_incremental(messages)
    if not text and not messages:
        return 0
    exact = _FLATTEN_TOKEN_EXACT.get(text)
    if exact is not None:
        _record_token_path("exact")
        return exact
    best_prefix, best_tokens = "", 0
    for cached_text, cached_tokens in _FLATTEN_TOKEN_CACHE:
        if len(cached_text) <= len(best_prefix) or len(cached_text) >= len(text):
            continue
        # The cached text must be exactly this prefix, ending on a message
        # boundary: prefix + "\n\n" + tail is the whole text.
        if text.startswith(cached_text) and text[len(cached_text):len(cached_text) + 2] == "\n\n":
            best_prefix, best_tokens = cached_text, cached_tokens
    if not best_prefix:
        total = count_text_tokens(text)
        _record_token_path("full", len(text))
    else:
        tail_text = text[len(best_prefix):]
        total = best_tokens + count_text_tokens(tail_text)
        _record_token_path("prefix", len(tail_text))
    _FLATTEN_TOKEN_CACHE.append((text, total))
    if len(_FLATTEN_TOKEN_EXACT) > 64:
        _FLATTEN_TOKEN_EXACT.clear()
    _FLATTEN_TOKEN_EXACT[text] = total
    return total


def message_token_path_stats(reset: bool = False) -> Dict[str, int]:
    """How many counts took each path: exact hit, prefix reuse, or full tokenize.

    The per-round cost is fully explained by this split -- "exact"/"prefix" are
    milliseconds, "full" tokenizes the whole history. ``<site>:<path>`` keys break
    the same counts down by call site (``request`` = the messages being sent,
    ``calibration`` = the provider-usage baseline), so a round showing one "full"
    says which of them caused it.
    """
    snapshot = dict(_MESSAGE_TOKEN_PATH_STATS)
    snapshot.update(_MESSAGE_TOKEN_SITE_STATS)
    if _SEED_LAST:
        snapshot["seed"] = _SEED_LAST
    if reset:
        for key in list(_MESSAGE_TOKEN_PATH_STATS):
            _MESSAGE_TOKEN_PATH_STATS[key] = 0
        _MESSAGE_TOKEN_SITE_STATS.clear()
    return snapshot


# Seam for the message-level token estimate used by the request estimator. Tests
# replace this to keep the tokenizer out of the assertion path; production leaves
# it as the incremental counter above. Named explicitly (rather than the estimator
# reaching for ``agent_harness.estimate_tokens``) so an injected estimator is
# honoured instead of silently bypassed.
message_token_estimator: Callable[[List[Any]], int] = count_message_tokens_incremental


def count_tool_definition_tokens(tools: Optional[List[Dict[str, Any]]]) -> int:
    """Estimate the serialized tool-schema portion of one model request."""
    if not tools:
        return 0
    return _tool_schema_cache_values(tools)[1]


def _prompt_usage_baseline_path(session_id: str) -> Optional[Path]:
    try:
        from agent_harness import session_manager

        session_path = Path(session_manager._resolve_session_path(session_id))
        if not session_path.is_dir():
            return None
        return session_path / "snapshots" / "prompt_tokens.json"
    except Exception:
        return None


def _load_prompt_usage_baseline(session_id: str) -> Optional[Dict[str, Any]]:
    path = _prompt_usage_baseline_path(session_id)
    if path is None:
        return None
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    hashes = payload.get("hashes")
    if not isinstance(hashes, list) or not all(isinstance(item, str) for item in hashes):
        return None
    try:
        if int(payload.get("version") or 0) != 1:
            return None
        tokens = int(payload.get("tokens") or 0)
        count = int(payload.get("count") or 0)
    except (TypeError, ValueError):
        return None
    if tokens <= 0 or count != len(hashes):
        return None
    return {
        "ts": time.monotonic(),
        "hashes": list(hashes),
        "message_fingerprint": str(payload.get("message_fingerprint") or ""),
        "tool_fingerprint": str(payload.get("tool_fingerprint") or ""),
        "count": count,
        "tokens": tokens,
        "tool_tokens": max(0, int(payload.get("tool_tokens") or 0)),
    }


def _persist_prompt_usage_baseline(session_id: str, baseline: Dict[str, Any]) -> None:
    path = _prompt_usage_baseline_path(session_id)
    if path is None:
        return
    tmp = path.with_name(
        f".prompt-tokens-{os.getpid()}-{threading.get_ident()}-{time.time_ns()}"
    )
    try:
        import json

        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(
            json.dumps(
                {
                    "version": 1,
                    "hashes": list(baseline.get("hashes") or []),
                    "message_fingerprint": baseline.get("message_fingerprint") or "",
                    "tool_fingerprint": baseline.get("tool_fingerprint") or "",
                    "count": int(baseline.get("count") or 0),
                    "tokens": int(baseline.get("tokens") or 0),
                    "tool_tokens": int(baseline.get("tool_tokens") or 0),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except OSError:
        pass
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def record_prompt_tokens_for_messages(
    session_id: str,
    messages: List[Any],
    prompt_tokens: int,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Record provider-reported input tokens for an exact request package."""
    sid = str(session_id or "").strip()
    try:
        tokens = int(prompt_tokens or 0)
    except (TypeError, ValueError):
        tokens = 0
    if not sid or tokens <= 0:
        return
    from agent_harness import strip_reasoning_for_api_request

    stripped = strip_reasoning_for_api_request(list(messages or []))
    hashes = _messages_token_hashes(stripped)
    message_fingerprint = _messages_token_fingerprint_from_hashes(hashes)
    tool_fingerprint = _tool_definitions_fingerprint(tools)
    fingerprint = _request_token_fingerprint(message_fingerprint, tool_fingerprint)
    now = time.monotonic()
    baseline = {
        "ts": now,
        "hashes": hashes,
        "message_fingerprint": message_fingerprint,
        "tool_fingerprint": tool_fingerprint,
        "count": len(hashes),
        "tokens": tokens,
        "messages": list(stripped),
        "tool_tokens": count_tool_definition_tokens(tools),
    }
    with _PROMPT_USAGE_CACHE_LOCK:
        _PROMPT_USAGE_BASELINE_CACHE[sid] = baseline
        _PROMPT_USAGE_EXACT_CACHE[(sid, fingerprint)] = (now, tokens, "provider_exact")
        _evict_prompt_usage_exact_cache_locked(now)
    _persist_prompt_usage_baseline(sid, baseline)


def estimate_full_input_tokens_for_messages(
    session_id: str,
    messages: List[Any],
    *,
    tools: Optional[List[Dict[str, Any]]] = None,
    return_source: bool = False,
) -> Any:
    """
    Estimate tokens for the already-built API request package.

    Prefer exact provider usage from a previous identical request, then reuse a
    provider-reported prefix baseline and estimate only the appended suffix.
    """
    from agent_harness import estimate_tokens, strip_reasoning_for_api_request

    sid = str(session_id or "").strip()
    # Diagnostic escape hatch, checked before any branch: trust the provider's own
    # count and skip the local tokenizer entirely. This measures how much of the
    # per-round cost this estimate actually is by running without it, instead of
    # inferring it from a timing breakdown. Off by default -- it trades the
    # compression trigger's accuracy for the measurement.
    if str(os.getenv("CONTEXT_TOKEN_SKIP_LOCAL_ESTIMATE") or "").strip() in {"1", "true", "yes", "on"}:
        cached_baseline = _PROMPT_USAGE_BASELINE_CACHE.get(sid) if sid else None
        if cached_baseline is None and sid:
            cached_baseline = _load_prompt_usage_baseline(sid)
        provider_tokens = int((cached_baseline or {}).get("tokens") or 0)
        if provider_tokens > 0:
            result = (provider_tokens, "provider_skip_local")
            return result if return_source else result[0]
    stripped = strip_reasoning_for_api_request(list(messages or []))
    hashes = _messages_token_hashes(stripped)
    message_fingerprint = _messages_token_fingerprint_from_hashes(hashes)
    tool_fingerprint = _tool_definitions_fingerprint(tools)
    fingerprint = _request_token_fingerprint(message_fingerprint, tool_fingerprint)
    now = time.monotonic()
    calibration = None
    with _PROMPT_USAGE_CACHE_LOCK:
        exact = _PROMPT_USAGE_EXACT_CACHE.get((sid, fingerprint)) if sid else None
        if exact and now - exact[0] <= _PROMPT_USAGE_CACHE_TTL_SEC:
            result = (int(exact[1]), str(exact[2] if len(exact) > 2 else "provider_exact"))
            return result if return_source else result[0]
        baseline = _PROMPT_USAGE_BASELINE_CACHE.get(sid) if sid else None
        if baseline and now - float(baseline.get("ts") or 0) > _PROMPT_USAGE_CACHE_TTL_SEC:
            _PROMPT_USAGE_BASELINE_CACHE.pop(sid, None)
            baseline = None
    if baseline is None and sid:
        baseline = _load_prompt_usage_baseline(sid)
        if baseline:
            with _PROMPT_USAGE_CACHE_LOCK:
                _PROMPT_USAGE_BASELINE_CACHE.setdefault(sid, baseline)
    with _PROMPT_USAGE_CACHE_LOCK:
        if baseline:
            base_count = int(baseline.get("count") or 0)
            base_tokens = int(baseline.get("tokens") or 0)
            base_fingerprint = str(baseline.get("message_fingerprint") or "")
            base_tool_fingerprint = str(baseline.get("tool_fingerprint") or "")
            if (
                base_count > 0
                and base_tokens > 0
                and base_tool_fingerprint == tool_fingerprint
                and base_count <= len(hashes)
                and _messages_token_fingerprint_from_hashes(hashes[:base_count]) == base_fingerprint
            ):
                suffix = stripped[base_count:]
                suffix_tokens = int(estimate_tokens(suffix)) if suffix else 0
                margin = max(8, len(suffix) * 4) if suffix else 0
                estimated = base_tokens + suffix_tokens + margin
                # Seed the flattened-text cache with the provider's own count.
                # This early return skips the full-history count below, so without
                # seeding nothing registered the text the next request asks about --
                # and every later request re-tokenized the whole history (observed
                # as tok_full=1 on every round with tok_exact=0). ``base_tokens``
                # covers the baseline part and ``suffix_tokens`` the appended part;
                # the margin is deliberately excluded, since it is a safety add-on
                # that would otherwise be re-counted wherever this is reused.
                _seed_flatten_token_cache(stripped, base_tokens + suffix_tokens)
                _PROMPT_USAGE_EXACT_CACHE[(sid, fingerprint)] = (now, estimated, "provider_prefix")
                _evict_prompt_usage_exact_cache_locked(now)
                result = (int(estimated), "provider_prefix")
                return result if return_source else result[0]
            base_hashes = list(baseline.get("hashes") or [])
            common = 0
            for left, right in zip(base_hashes, hashes):
                if left != right:
                    break
                common += 1
            changed_tail = (len(base_hashes) - common) + (len(hashes) - common)
            if (
                base_tool_fingerprint == tool_fingerprint
                and common > 0
                and common >= max(1, min(len(base_hashes), len(hashes)) // 2)
                and changed_tail <= 4
            ):
                calibration = dict(baseline)
    tool_tokens = count_tool_definition_tokens(tools)
    # Incremental count: this history is the previous step's plus a few appends, so
    # tokenizing the whole thing every step is O(all history) for O(new) changes.
    # Measured on a 433 KB history the full tokenizer pass is ~670 ms against ~1 ms
    # for the appended tail, and this is one of the larger per-round costs.
    # ``message_token_estimator`` is the injection seam (see its definition).
    global _TOKEN_SITE_HINT
    _TOKEN_SITE_HINT = "request"
    estimated = int(message_token_estimator(stripped)) + tool_tokens
    _TOKEN_SITE_HINT = ""
    source = "local_estimate"
    if calibration:
        base_tokens = int(calibration.get("tokens") or 0)
        base_messages = list(calibration.get("messages") or [])
        _TOKEN_SITE_HINT = "calibration"
        base_local_tokens = (
            int(message_token_estimator(base_messages))
            + int(calibration.get("tool_tokens") or 0)
            if base_messages
            else 0
        )
        _TOKEN_SITE_HINT = ""
        if base_tokens > 0 and base_local_tokens > 0:
            estimated = max(0, int(round(estimated * (base_tokens / base_local_tokens))))
            source = "provider_calibrated"
    with _PROMPT_USAGE_CACHE_LOCK:
        if sid:
            _PROMPT_USAGE_EXACT_CACHE[(sid, fingerprint)] = (now, estimated, source)
            _evict_prompt_usage_exact_cache_locked(now)
    result = (estimated, source)
    return result if return_source else result[0]


def estimate_calculated_input_tokens_for_messages(
    messages: List[Any],
    tools: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """Estimate an assembled API request locally, without provider-usage caches.

    This is deliberately the same pure-tokenizer path used by the history
    preview in context compression.  It is used by CONTEXT_TOKEN_MODE=calculated
    so the auto-compression trigger cannot disagree with that preview merely
    because a provider reported a different token count for an earlier request.
    """
    from agent_harness import estimate_tokens, strip_reasoning_for_api_request

    stripped = strip_reasoning_for_api_request(list(messages or []))
    return int(estimate_tokens(stripped)) + count_tool_definition_tokens(tools)


# ==================== 整包输入 token（与主模型上送一致）====================


def inject_missing_tool_messages(messages: List[Any]) -> List[Any]:
    """
    含 tool_calls 的 assistant 后必须紧跟对应 id 的 tool 消息；缺则用占位 ToolMessage 补齐，避免 400。
    """
    result: List[Any] = []
    idx = 0
    n = len(messages)
    while idx < n:
        msg = messages[idx]
        result.append(msg)
        if isinstance(msg, AssistantMessage) and getattr(msg, "tool_calls", None):
            need_ids = [tc.get("id") for tc in msg.tool_calls if tc.get("id")]
            seen = set()
            idx += 1
            while idx < n and isinstance(messages[idx], ToolMessage):
                tm = messages[idx]
                tid = getattr(tm, "tool_call_id", None) or ""
                if tid:
                    seen.add(tid)
                result.append(tm)
                idx += 1
            for tid in need_ids:
                if tid and tid not in seen:
                    result.append(
                        ToolMessage(
                            content="[工具返回缺失：可能因会话中断或历史压缩未保留，此为占位。]",
                            tool_call_id=tid,
                        )
                    )
            continue
        idx += 1
    return result


def messages_for_openai_turns(llm_history: List[Any]) -> List[Any]:
    """
    从持久化 llm_history 中构造 API 多轮（user/assistant/tool），不含前置静态 system 链与 key_context system（由外部拼接）。
    压缩区在微压与全量保留之间，可为：
    - 新版：System「Conversation compacted」+ User「[压缩摘要]…」，均原样上送（user 不包一层 [系统上下文]）；
    - 旧版：System「【历史上下文已压缩/摘要区】…」仍原样上送。
    其它非以上 System（提醒等）转为带 [系统上下文] 前缀的 user，避免与专用 system 层混淆。
    """
    from agent_harness import (
        is_compress_summary_system_message,
        is_conversation_compress_boundary_system,
    )

    out: List[Any] = []
    skip_contents = {
        "New Agent Loop Start",
        "Loop finished",
    }
    for msg in llm_history:
        if isinstance(msg, UserMessage):
            out.append(msg)
        elif isinstance(msg, AssistantMessage):
            out.append(msg)
        elif isinstance(msg, ToolMessage):
            out.append(ToolMessage(content=_strip_tool_display_prefix(msg.content), tool_call_id=msg.tool_call_id))
        elif isinstance(msg, SystemMessage):
            c = (msg.content or "").strip()
            if c in skip_contents:
                continue
            if is_compress_summary_system_message(msg) or is_conversation_compress_boundary_system(msg):
                out.append(msg)
                continue
            out.append(UserMessage(content="[系统上下文]\n" + (msg.content or "")))
        else:
            out.append(UserMessage(content=str(getattr(msg, "content", ""))))
    return out


def build_env_static(session_id: Optional[str] = None) -> str:
    """Build the Environment block: calendar month, OS, paths, session storage (no live workspace listing)."""
    from agent_harness import PROJECT_ROOT as AGENT_PROJECT_ROOT, WORK_DIR, session_manager
    from agent_tools import describe_run_shell_executor_for_prompt

    sid = (session_id or "").strip()

    wdir = str(WORK_DIR.resolve())
    proj = str(AGENT_PROJECT_ROOT.resolve())

    session_lines = ""
    if sid:
        try:
            from runtime_v2 import runtime_v2_primary

            is_v2 = bool(runtime_v2_primary())
        except Exception:
            is_v2 = True
        sdir = session_manager._get_session_path(sid).resolve()
        try:
            v_session = "/" + str(sdir.relative_to(WORK_DIR.resolve())).replace("\\", "/")
        except ValueError:
            v_session = f"/sessions/{sid}"
        v_key = f"{v_session}/key_context.md"
        v_todo = f"{v_session}/todo_plan.md"
        session_lines = f"""
- **Session storage directory**: {sdir}
  - Virtual path from `WORK_DIR`: `{v_session}`. Use this virtual path with file tools when possible; OS-absolute paths are shown only for orientation.
  - Main files: `llm_history.json`, `dialogue_history.json` (user↔final from `ui_events`), `work_messages.json`, `ui_events.json`, `key_context.md`, `todo_plan.md`, `metadata.json`, plus related artifacts.
  - Read or grep this directory when in-context messages are insufficient and you need persisted history or the event stream.
  - Persistent key facts belong in `key_context.md`: `{v_key}`. Use `context_manage` with `mode=edit_key_context` to revise it.
  - Live todo state belongs in `todo_plan.md`: `{v_todo}`. Use `update_todo`, or `read_file` on `{v_todo}` when you need to inspect it.
  - Extra `key_context` system message: when non-empty, the server injects the rendered full `key_context.md` body; legacy sessions may strip an embedded `## Todo 计划` section."""
        if is_v2:
            session_lines = f"""
- **Session storage directory**: {sdir}
  - Runtime V2 canonical path from `WORK_DIR`: `{v_session}`.
  - Canonical facts and rebuildable state live in `events.jsonl`, `snapshots/latest.json`, metadata, indexes, and referenced blobs. Legacy `llm_history.json`, `ui_events.json`, `key_context.md`, and `todo_plan.md` may be absent or stale and must not be used as context authority.
  - The server injects the active model context and summary. Use `context_manage` for explicit compact/summary edits and `update_todo` for the live plan; do not directly edit Runtime V2 storage files.
  - Use the conversation history APIs/UI when older visible history is needed."""
    else:
        session_lines = "\n- **Session storage directory**: not set for this run."

    run_shell_executor_hint = describe_run_shell_executor_for_prompt()
    current_year_month = datetime.now().strftime("%Y-%m")

    text = f"""
## Environment
- **Calendar month (host local time)**: **{current_year_month}**
- **OS**: {platform.system()} | **Python**: {platform.python_version()}
{run_shell_executor_hint}
- **MCP extensions** (optional): With `mcp_servers.json` at the project root (or env `MCP_SERVERS_JSON`), or settings saved via **Advanced settings → MCP configuration**, each exact server configuration requires one human registration confirmation before it connects and exposes tools as `mcp_<server_alias>_<tool_name>`. Tool calls then follow the current global permission mode and central `allow/ask/deny` policy.
- **Agent project root** (`AGENT_PROJECT_ROOT`): {proj}
  - This is the agent application's own source tree and project-level config root, including files such as `app/agent_loop.py`, `app/agent_tools.py`, `app/agent_harness.py`, `app/agent_tokenizer.py`, `app/prompt.md`, and `mcp_servers.json`.
  - When the user asks about "your" features, mechanisms, configuration, tool behavior, prompt behavior, self-checks, or asks you to inspect/check yourself, first use this root to read the relevant code and infer the agent's actual behavior before answering.
- **Work root** (`WORK_DIR`): {wdir}
  - Virtual `/` maps to this directory. Relative paths and virtual paths like `/outputs/a.txt` resolve under `WORK_DIR`.
  - `write_file`, `apply_patch`, `edit_file`, `web_download`, `delete_file` (soft-delete target: `WORK_DIR/.trash/`), and restricted `run_shell` resolve relative paths under this tree; **native absolute paths outside WORK_DIR are permitted** after the user approves the target directory through the approval card in restricted modes (full access allows them directly).
  - `delete_file` refuses protected tool state under `sessions/`, `skills/`, `.trash/`, and their children.

## This conversation's storage{session_lines}
    """.strip()
    return text


def build_static_system_segments(
    skills_catalog: str,
    env_static: str,
    language: str = "zh-CN",
) -> List[str]:
    """
    静态 system 分段上送（不含 key_context、不含对话轮）。
    顺序兼顾可读性与前缀缓存：角色原则 → 工具清单 → 调用策略 → 技能目录 → 环境。
    """
    from agent_harness import load_prompt_template

    normalized_language = str(language or "zh-CN").strip().lower()
    is_english = normalized_language in {"en", "en-us", "en-gb", "english"}
    def load_for_language(name: str) -> str:
        return (
            load_prompt_template(name, "en")
            if is_english
            else load_prompt_template(name)
        )

    identity = load_for_language("system_identity").strip()
    contract = load_for_language("system_tool_contract").strip()
    skills_tpl = load_for_language("system_skills_intro").strip()
    skills_block = skills_tpl.format(skills_catalog=skills_catalog)
    identity_heading = "## Role and response principles" if is_english else "## 角色与回答原则"
    contract_heading = "## Tool-calling policy" if is_english else "## 工具调用策略"
    skills_heading = "## Skills catalog" if is_english else "## 技能目录"
    parts = [
        identity_heading + "\n\n" + identity,
        contract_heading + "\n\n" + contract,
        skills_heading + "\n\n" + skills_block,
        env_static.strip(),
    ]
    return [p for p in parts if p.strip()]


def estimate_full_input_tokens_for_llm_history(
    session_id: str,
    llm_history: List[Any],
    key_context: str,
    language: str = "zh-CN",
    tools: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """
    与 react_node 发往主模型前、`compute_context_tokens_for_session`（右上角）一致的整包 token：
    静态 system 多段 + key_context 注入 + 多轮 turn（含 tool 占位补齐），reasoning 剥除口径相同。
    """
    from agent_harness import (
        estimate_tokens,
        key_context_body_for_system_prompt,
        strip_reasoning_for_api_request,
    )
    from agent_tools import get_skills_catalog

    sid = str(session_id or "").strip()
    cache_key = (
        *_full_input_token_cache_key(sid, llm_history, key_context or "", tools),
        str(language or "zh-CN"),
    )
    now = time.monotonic()
    with _FULL_INPUT_TOKEN_CACHE_LOCK:
        cached = _FULL_INPUT_TOKEN_CACHE.get(cache_key)
        if cached and now - cached[0] <= _FULL_INPUT_TOKEN_CACHE_TTL_SEC:
            return int(cached[1])
    skills_catalog = get_skills_catalog()
    env_static = build_env_static(sid if sid else None)
    kc_body = key_context_body_for_system_prompt(key_context or "")
    static_segments = build_static_system_segments(skills_catalog, env_static, language)
    turn_msgs = inject_missing_tool_messages(messages_for_openai_turns(llm_history))
    llm_messages: List[Any] = [SystemMessage(content=s) for s in static_segments]
    if kc_body:
        llm_messages.append(SystemMessage(content=kc_body))
    llm_messages.extend(turn_msgs)
    _for_est = strip_reasoning_for_api_request(llm_messages)
    # Route through the incremental estimator, not the raw tokenizer. The context
    # meter (top-right) and the compression preview both call this function, and
    # their history is the same one the next request will send -- so tokenizing it
    # here also seeds the prefix cache that request reuses. Calling the raw
    # tokenizer instead left this the one remaining full pass per round.
    estimated = int(message_token_estimator(_for_est)) + count_tool_definition_tokens(tools)
    with _FULL_INPUT_TOKEN_CACHE_LOCK:
        if len(_FULL_INPUT_TOKEN_CACHE) >= _FULL_INPUT_TOKEN_CACHE_MAX:
            oldest = min(_FULL_INPUT_TOKEN_CACHE.items(), key=lambda item: item[1][0])[0]
            _FULL_INPUT_TOKEN_CACHE.pop(oldest, None)
        _FULL_INPUT_TOKEN_CACHE[cache_key] = (now, estimated)
    return estimated


def estimate_hybrid_input_tokens_for_llm_history(
    session_id: str,
    llm_history: List[Any],
    key_context: str,
    language: str = "zh-CN",
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[int, str]:
    """Estimate a persisted session using the same provider-calibrated path as a live request."""
    from agent_harness import key_context_body_for_system_prompt
    from agent_tools import get_skills_catalog

    sid = str(session_id or "").strip()
    skills_catalog = get_skills_catalog()
    env_static = build_env_static(sid if sid else None)
    kc_body = key_context_body_for_system_prompt(key_context or "")
    static_segments = build_static_system_segments(skills_catalog, env_static, language)
    turn_msgs = inject_missing_tool_messages(messages_for_openai_turns(llm_history))
    llm_messages: List[Any] = [SystemMessage(content=s) for s in static_segments]
    if kc_body:
        llm_messages.append(SystemMessage(content=kc_body))
    llm_messages.extend(turn_msgs)
    estimated, source = estimate_full_input_tokens_for_messages(
        sid,
        llm_messages,
        tools=tools,
        return_source=True,
    )
    return int(estimated), str(source)
