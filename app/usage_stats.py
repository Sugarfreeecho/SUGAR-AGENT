"""把每次会话的 token 用量汇总成一份本机口径的统计。

原始数据在 ``<sessions>/<id>/execution_metrics.json``：每个 run 的 ``requests[]``
里有一条 ``usage``（prompt_tokens / completion_tokens / 缓存命中 / 推理 token）。
一次全量解析接近 200MB、十几秒，所以这里按 ``(mtime_ns, size)`` 做增量——只有变过
的会话文件才重新解析，其余复用它上次的每文件汇总。第一次打开页签是「统计中」，
之后是秒回。
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import ijson

logger = logging.getLogger(__name__)

# 4：模型桶多了首字延迟两格，老缓存的桶长度对不上，必须重建。
CACHE_VERSION = 4
CACHE_TTL_SEC = 20.0
MAX_DAYS = 730
MAX_MODELS = 40
# 会话表在前端默认只显示 30 行，但检索要能覆盖全部会话，所以整份带上（约 45KB）。
MAX_SESSIONS = 400
UNKNOWN_MODEL = "(未标注)"
# 「按配置」里没落到任何档案的桶。单独起名并始终排在末尾，免得混在中间像是个配置。
OTHER_PROFILE = "其他"

_lock = threading.Lock()
_building = False
_cache: Optional[dict] = None
_cache_at = 0.0
_error = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _local_day(value: Any) -> str:
    """UTC 时间戳 → 本地日期。

    存储里是 UTC（`...Z`），而人看用量是按自己的一天算的；直接切前 10 位会让
    晚上 8 点后的请求算到第二天。
    """
    text = str(value or "").strip()
    if len(text) < 10:
        return ""
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text[:10] if text[:4].isdigit() else ""
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone().strftime("%Y-%m-%d")


def _add(bucket: Dict[str, List[int]], key: str, prompt: int, completion: int, ttft: int = 0) -> None:
    """桶结构固定为 [输入, 输出, 请求数, 首字累计, 首字样本数]，天桶只用前三格。"""
    row = bucket.get(key)
    if row is None:
        bucket[key] = [prompt, completion, 1, ttft if ttft > 0 else 0, 1 if ttft > 0 else 0]
        return
    row[0] += prompt
    row[1] += completion
    row[2] += 1
    if len(row) < 5:
        row.extend([0, 0])
    if ttft > 0:
        row[3] += ttft
        row[4] += 1


def _request_ttft(request: dict, usage: dict) -> int:
    """请求发出 → 首个 token 的毫秒数。

    落盘数据里首选 ``phases.first_token.total_ms``，其次顶层的 ``first_token_ms``；
    ``usage._timing`` 只存在于流式路径的内存对象里，几乎没有落盘，放最后兜底。
    """
    phases = request.get("phases")
    if isinstance(phases, dict):
        first = phases.get("first_token")
        if isinstance(first, dict):
            value = _int(first.get("total_ms"))
            if value > 0:
                return value
    value = _int(request.get("first_token_ms"))
    if value > 0:
        return value
    timing = usage.get("_timing")
    if isinstance(timing, dict):
        return _int(timing.get("first_token_wait_ms"))
    return 0


def _request_generation_ms(request: dict) -> int:
    """首 token → 结束的纯生成时长（``phases.llm_output.total_ms``）。"""
    phases = request.get("phases")
    if isinstance(phases, dict):
        output = phases.get("llm_output")
        if isinstance(output, dict):
            return _int(output.get("total_ms"))
    return 0


def _aggregate_file(path: Path) -> Optional[dict]:
    """读一个会话文件，只留下按天/按模型的桶。

    返回 None 表示这个文件这次读不出来（可能正被写入）——调用方会沿用上一次的
    汇总，避免数字忽高忽低。
    """
    try:
        with open(path, "rb") as handle:
            events = iter(ijson.parse(handle))
            if next(events, None) != ("", "start_map", None):
                return None
            return _aggregate_requests(ijson.items(events, "runs.item.requests.item"))
    except (OSError, ValueError, ijson.JSONError):
        return None


def _aggregate_requests(requests) -> dict:
    """Keep only one request in memory; reject the whole result on parse errors."""
    days: Dict[str, List[int]] = {}
    models: Dict[str, List[int]] = {}
    total = [0, 0, 0]
    cache_hit = cache_miss = reasoning = 0
    ttft_sum = ttft_n = gen_sum = gen_out = gen_n = 0
    last_at = ""

    for request in requests:
        if not isinstance(request, dict):
            continue
        usage = request.get("usage")
        if not isinstance(usage, dict) or not usage:
            continue
        prompt = _int(usage.get("prompt_tokens"))
        completion = _int(usage.get("completion_tokens"))
        if prompt <= 0 and completion <= 0:
            continue
        model = str(usage.get("model") or request.get("model") or "").strip() or UNKNOWN_MODEL
        day = _local_day(request.get("started_at"))
        ttft = _request_ttft(request, usage)
        # 首字延迟也按模型分桶，模型表才能显示「平均首 token」。
        _add(models, model, prompt, completion, ttft)
        if day:
            _add(days, day, prompt, completion)
        total[0] += prompt
        total[1] += completion
        total[2] += 1
        cache_hit += _int(usage.get("prompt_cache_hit_tokens"))
        cache_miss += _int(usage.get("prompt_cache_miss_tokens"))
        reasoning += _int(usage.get("reasoning_tokens"))
        if ttft > 0:
            ttft_sum += ttft
            ttft_n += 1
        generation = _request_generation_ms(request)
        if generation > 0:
            gen_sum += generation
            gen_out += completion
            gen_n += 1
        started = str(request.get("started_at") or "")
        if started > last_at:
            last_at = started

    return {
        "days": days,
        "models": models,
        "totals": total,
        "cache_hit": cache_hit,
        "cache_miss": cache_miss,
        "reasoning": reasoning,
        "ttft_ms": ttft_sum,
        "ttft_n": ttft_n,
        "gen_ms": gen_sum,
        "gen_out": gen_out,
        "gen_n": gen_n,
        "last_at": last_at,
    }


def _read_cache(cache_path: Optional[Path]) -> dict:
    if cache_path is None:
        return {}
    try:
        with open(cache_path, "rb") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        return {}
    return data


def _write_cache(cache_path: Optional[Path], data: dict) -> None:
    if cache_path is None:
        return
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
        tmp.replace(cache_path)
    except OSError as exc:
        logger.debug("usage stats cache write skipped: %s", exc)


def _build(sessions_dir: Path, cache_path: Optional[Path]) -> dict:
    """扫一遍会话目录，只重算变过的文件。"""
    previous = _read_cache(cache_path)
    prev_files = previous.get("files")
    prev_files = prev_files if isinstance(prev_files, dict) else {}

    files: Dict[str, dict] = {}
    parsed = reused = 0
    # 子代理的用量记在 sessions/<父会话>/subagents/<子代理>/execution_metrics.json，
    # 只扫一层会漏掉它们（实测占总输出的一成多）。
    candidates = [(path, "main") for path in Path(sessions_dir).glob("*/execution_metrics.json")]
    candidates += [(path, "subagent") for path in Path(sessions_dir).glob("*/subagents/*/execution_metrics.json")]
    for path, kind in sorted(candidates, key=lambda item: str(item[0])):
        try:
            stat = path.stat()
        except OSError:
            continue
        session_id = (
            f"{path.parent.parent.parent.name}/{path.parent.name}"
            if kind == "subagent"
            else path.parent.name
        )
        cached = prev_files.get(session_id)
        if (
            isinstance(cached, dict)
            and cached.get("mtime_ns") == stat.st_mtime_ns
            and cached.get("size") == stat.st_size
        ):
            files[session_id] = cached
            reused += 1
            continue
        row = _aggregate_file(path)
        if row is None:
            if isinstance(cached, dict):
                files[session_id] = cached
            continue
        row["mtime_ns"] = stat.st_mtime_ns
        row["size"] = stat.st_size
        row["kind"] = kind
        row["id"] = session_id
        files[session_id] = row
        parsed += 1

    data = {
        "version": CACHE_VERSION,
        "updatedAt": _now(),
        "parsed": parsed,
        "reused": reused,
        "files": files,
    }
    _write_cache(cache_path, data)
    logger.info("usage stats rebuilt: parsed=%d reused=%d files=%d", parsed, reused, len(files))
    return data


def _compose(
    cache: dict,
    names: Optional[Dict[str, str]] = None,
    profile_names: Optional[Dict[str, str]] = None,
) -> dict:
    """把每文件汇总合成一份给前端的小载荷。"""
    names = names or {}
    files = cache.get("files") if isinstance(cache.get("files"), dict) else {}

    days: Dict[str, List[int]] = {}
    models: Dict[str, List[int]] = {}
    totals = [0, 0, 0]
    cache_hit = cache_miss = reasoning = 0
    ttft_sum = ttft_n = gen_sum = gen_out = gen_n = 0
    last_at = ""

    for row in files.values():
        if not isinstance(row, dict):
            continue
        for key, bucket in (row.get("days") or {}).items():
            target = days.setdefault(key, [0, 0, 0])
            target[0] += _int(bucket[0])
            target[1] += _int(bucket[1])
            target[2] += _int(bucket[2])
        for key, bucket in (row.get("models") or {}).items():
            target = models.setdefault(key, [0, 0, 0, 0, 0])
            target[0] += _int(bucket[0])
            target[1] += _int(bucket[1])
            target[2] += _int(bucket[2])
            if len(bucket) > 4:
                target[3] += _int(bucket[3])
                target[4] += _int(bucket[4])
        bucket = row.get("totals") or [0, 0, 0]
        totals[0] += _int(bucket[0])
        totals[1] += _int(bucket[1])
        totals[2] += _int(bucket[2])
        cache_hit += _int(row.get("cache_hit"))
        cache_miss += _int(row.get("cache_miss"))
        reasoning += _int(row.get("reasoning"))
        ttft_sum += _int(row.get("ttft_ms"))
        ttft_n += _int(row.get("ttft_n"))
        gen_sum += _int(row.get("gen_ms"))
        gen_out += _int(row.get("gen_out"))
        gen_n += _int(row.get("gen_n"))
        last_at = max(last_at, str(row.get("last_at") or ""))

    day_rows = [
        {"day": key, "input": value[0], "output": value[1], "requests": value[2]}
        for key, value in sorted(days.items())
    ][-MAX_DAYS:]

    def _avg_ttft(bucket) -> Optional[int]:
        return round(bucket[3] / bucket[4]) if len(bucket) > 4 and bucket[4] else None

    model_rows = [
        {"model": key, "input": value[0], "output": value[1], "requests": value[2], "ttftMs": _avg_ttft(value)}
        for key, value in models.items()
    ]
    model_rows.sort(key=lambda item: (item["input"] + item["output"], item["requests"]), reverse=True)

    # 「按模型配置」：拿设置里的 model → 档案名做映射，把同一档案的不同 model 别名合到一起。
    # 请求里没有记录当时用的档案，所以这是按当前配置反推，改过配置的历史数据会跟当时不一致。
    by_profile: Dict[str, List[int]] = {}
    for key, value in models.items():
        label = (profile_names or {}).get(key)
        if not label:
            # 用量里常见「供应商/模型」，档案只写模型名：精确匹配不上时再退化到尾段。
            # 反过来不行——尾段当别名提前塞进映射，会把别名真正的主人顶掉。
            tail = key.rsplit("/", 1)[-1]
            if tail and tail != key:
                label = (profile_names or {}).get(tail)
        label = label or OTHER_PROFILE
        target = by_profile.setdefault(label, [0, 0, 0, 0, 0])
        for index in range(3):
            target[index] += _int(value[index])
        if len(value) > 4:
            target[3] += _int(value[3])
            target[4] += _int(value[4])
    profile_rows = [
        {"model": key, "input": value[0], "output": value[1], "requests": value[2], "ttftMs": _avg_ttft(value),
         "other": key == OTHER_PROFILE}
        for key, value in by_profile.items()
    ]
    # 其他永远垫底，不用跟真配置抢位置。
    profile_rows.sort(key=lambda item: (item["other"], -(item["input"] + item["output"]), -item["requests"]))

    session_rows = []
    main_sessions = sub_sessions = 0
    sub_totals = [0, 0, 0]
    for session_id, row in files.items():
        if not isinstance(row, dict):
            continue
        bucket = row.get("totals") or [0, 0, 0]
        if row.get("kind") == "subagent":
            # 子代理的 token 计入总量，但不混进「会话」列表——它们是会话内部的执行单元。
            sub_sessions += 1
            sub_totals[0] += _int(bucket[0])
            sub_totals[1] += _int(bucket[1])
            sub_totals[2] += _int(bucket[2])
            continue
        main_sessions += 1
        session_rows.append(
            {
                "id": session_id,
                "name": str(names.get(session_id) or session_id[:8]),
                "input": _int(bucket[0]),
                "output": _int(bucket[1]),
                "requests": _int(bucket[2]),
                "lastAt": str(row.get("last_at") or ""),
            }
        )
    session_rows.sort(key=lambda item: item["input"] + item["output"], reverse=True)

    return {
        "ready": True,
        "generatedAt": cache.get("updatedAt") or _now(),
        "parsed": _int(cache.get("parsed")),
        "reused": _int(cache.get("reused")),
        "totals": {
            "tokens": totals[0] + totals[1],
            "input": totals[0],
            "output": totals[1],
            "requests": totals[2],
            "sessions": main_sessions,
            "subagents": sub_sessions,
            "subagentInput": sub_totals[0],
            "subagentOutput": sub_totals[1],
            "subagentRequests": sub_totals[2],
            "models": len(models),
            "cacheHit": cache_hit,
            "cacheMiss": cache_miss,
            "reasoning": reasoning,
            "ttftMs": round(ttft_sum / ttft_n) if ttft_n else None,
            "ttftSamples": ttft_n,
            "tokensPerSec": round(gen_out / (gen_sum / 1000.0), 1) if gen_sum > 0 else None,
            "speedSamples": gen_n,
            "lastAt": last_at,
        },
        "days": day_rows,
        "models": model_rows[:MAX_MODELS],
        "modelsTotal": len(model_rows),
        "profiles": profile_rows[:MAX_MODELS],
        "profilesTotal": len(profile_rows),
        "sessions": session_rows[:MAX_SESSIONS],
        "sessionsTotal": len(session_rows),
    }


def _worker(sessions_dir: Path, cache_path: Optional[Path]) -> None:
    global _building, _cache, _cache_at, _error
    try:
        data = _build(sessions_dir, cache_path)
        with _lock:
            _cache = data
            _cache_at = time.time()
            _error = ""
    except Exception as exc:  # noqa: BLE001 — 统计失败不该把设置页搞崩
        logger.warning("usage stats build failed: %s", exc)
        with _lock:
            _error = str(exc)
            _cache_at = time.time()
    finally:
        with _lock:
            _building = False


def _start_build(sessions_dir: Path, cache_path: Optional[Path]) -> bool:
    """起一个后台重建线程；已经在建就返回 False。"""
    global _building
    with _lock:
        if _building:
            return False
        _building = True
    threading.Thread(
        target=_worker,
        args=(sessions_dir, cache_path),
        name="usage-stats-build",
        daemon=True,
    ).start()
    return True


def snapshot(
    sessions_dir: Path,
    cache_path: Optional[Path] = None,
    names: Optional[Dict[str, str]] = None,
    profiles: Optional[Dict[str, str]] = None,
    *,
    refresh: bool = False,
    background: bool = True,
) -> dict:
    """返回汇总载荷；首次或缓存过期时先返回 ``{"ready": False}`` 并在后台重建。"""
    global _building, _cache, _cache_at, _error
    with _lock:
        cache = _cache
        error = _error
        cooled = _cache_at > 0 and (time.time() - _cache_at) < CACHE_TTL_SEC
    if not refresh and cooled:
        # 建失败也要冷静一会儿，否则每个轮询都会再扫一遍 200MB。
        return _compose(cache, names, profiles) if cache is not None else {"ready": False, "error": error}

    if background:
        _start_build(Path(sessions_dir), cache_path)
        if cache is not None and not refresh:
            # 有过期结果就先给旧的、后台刷新，别让页签每次打开都闪一下「统计中」。
            data = _compose(cache, names, profiles)
            data["stale"] = True
            return data
        return {"ready": False, "error": error}

    # 同步路径：测试与一次性脚本用。
    with _lock:
        _building = True
    try:
        data = _build(Path(sessions_dir), cache_path)
        with _lock:
            _cache = data
            _cache_at = time.time()
            _error = ""
    finally:
        with _lock:
            _building = False
    return _compose(_cache or {}, names, profiles)


def reset() -> None:
    """丢掉进程内缓存（测试用）。"""
    global _building, _cache, _cache_at, _error
    with _lock:
        _building = False
        _cache = None
        _cache_at = 0.0
        _error = ""
