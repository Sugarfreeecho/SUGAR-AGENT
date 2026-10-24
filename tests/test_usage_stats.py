import json
import os
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import usage_stats


def test_streaming_aggregation_reads_bounded_chunks_and_discards_truncated_results(tmp_path, monkeypatch):
    from io import BytesIO
    request = {"model": "stream", "usage": {"prompt_tokens": 2, "completion_tokens": 3}}
    raw = json.dumps({"runs": [{"requests": [request] * 12000}]}).encode()
    reads = []

    class BoundedReader(BytesIO):
        def read(self, size=-1):
            assert 0 <= size <= 65536
            reads.append(size)
            return super().read(size)

        def readinto(self, target):
            assert len(target) <= 65536
            reads.append(len(target))
            return super().readinto(target)

    monkeypatch.setattr(usage_stats, "open", lambda *args: BoundedReader(raw), raising=False)
    assert usage_stats._aggregate_file(tmp_path / "metrics.json")["totals"] == [24000, 36000, 12000]
    assert len(reads) > 2
    monkeypatch.setattr(usage_stats, "open", lambda *args: BoundedReader(raw[:-8]))
    assert usage_stats._aggregate_file(tmp_path / "metrics.json") is None


def _request(started_at, model, prompt, completion, **usage_extra):
    usage = {"prompt_tokens": prompt, "completion_tokens": completion}
    if model:
        usage["model"] = model
    usage.update(usage_extra)
    return {"started_at": started_at, "model": model, "usage": usage}


def _session(root: Path, session_id: str, requests, *, mtime=None):
    folder = root / session_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "execution_metrics.json"
    payload = {"runs": [{"run_id": "r1", "requests": requests}]}
    path.write_text(json.dumps(payload), encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _subagent(root: Path, parent_id: str, sub_id: str, requests):
    folder = root / parent_id / "subagents" / sub_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "execution_metrics.json"
    path.write_text(json.dumps({"runs": [{"run_id": "r1", "requests": requests}]}), encoding="utf-8")
    return path


def _request_with_ttft(started_at, model, prompt, completion, ttft):
    row = _request(started_at, model, prompt, completion)
    row["phases"] = {"first_token": {"total_ms": ttft}}
    return row


def test_usage_stats_reports_per_model_ttft_and_profile_grouping(tmp_path):
    """模型表要带平均首字；「按配置」用 model → 档案名的映射合并别名。"""
    usage_stats.reset()
    root = tmp_path / "sessions"
    _session(root, "s1", [
        _request_with_ttft("2026-03-10T10:00:00.000000Z", "vendor/model-a", 100, 10, 400),
        _request_with_ttft("2026-03-10T11:00:00.000000Z", "model-b", 50, 5, 200),
    ])
    mapping = {"vendor/model-a": "Config A", "model-b": "Config B"}

    data = usage_stats.snapshot(root, tmp_path / "cache.json", profiles=mapping, background=False)

    by_model = {row["model"]: row for row in data["models"]}
    assert by_model["vendor/model-a"]["ttftMs"] == 400
    assert by_model["model-b"]["ttftMs"] == 200
    by_profile = {row["model"]: row for row in data["profiles"]}
    assert set(by_profile) == {"Config A", "Config B"}
    assert by_profile["Config A"]["requests"] == 1 and by_profile["Config A"]["ttftMs"] == 400


def test_usage_stats_profile_tail_fallback_never_shadows_an_exact_model(tmp_path):
    """带前缀的别名退到尾段匹配，但不能把别人的精确模型顶掉（cmd 抢 ocgo 那个 bug）。"""
    usage_stats.reset()
    root = tmp_path / "sessions"
    _session(root, "s1", [
        _request("2026-03-10T10:00:00.000000Z", "deepseek/deepseek-v4.1-flash", 100, 10),
        _request("2026-03-10T11:00:00.000000Z", "deepseek-v4.1-flash", 50, 5),
        _request("2026-03-10T12:00:00.000000Z", "vendor/glm-5.2", 20, 2),
    ])
    mapping = {
        "deepseek/deepseek-v4.1-flash": "cmd",
        "deepseek-v4.1-flash": "ocgo",
        "glm-5.2": "glm",
    }

    data = usage_stats.snapshot(root, tmp_path / "cache.json", profiles=mapping, background=False)

    by_profile = {row["model"]: row for row in data["profiles"]}
    assert by_profile["cmd"]["requests"] == 1, "精确匹配的别名归自己"
    assert by_profile["ocgo"]["requests"] == 1, "尾段同名不能把 ocgo 并进 cmd"
    assert by_profile["glm"]["requests"] == 1, "没有精确项时才退到尾段"


def test_usage_stats_lists_unmapped_models_as_other_at_the_end(tmp_path):
    """没落到任何档案的用量归「其他」，量再大也排在最后。"""
    usage_stats.reset()
    root = tmp_path / "sessions"
    _session(root, "s1", [
        _request("2026-03-10T10:00:00.000000Z", "vendor/unknown", 999999, 1),
        _request("2026-03-10T11:00:00.000000Z", "known-model", 10, 1),
    ])

    data = usage_stats.snapshot(root, tmp_path / "cache.json",
                                profiles={"known-model": "Known"}, background=False)

    assert [row["model"] for row in data["profiles"]] == ["Known", "其他"]
    assert data["profiles"][-1]["other"] is True
    assert data["profiles"][0]["other"] is False


def test_usage_stats_counts_subagent_sessions_without_listing_them(tmp_path):
    usage_stats.reset()
    root = tmp_path / "sessions"
    _session(root, "s1", [_request("2026-03-10T10:00:00.000000Z", "model-a", 100, 10)])
    _subagent(root, "s1", "sub-1", [_request("2026-03-10T11:00:00.000000Z", "model-a", 40, 4)])

    data = usage_stats.snapshot(root, tmp_path / "cache.json", background=False)

    totals = data["totals"]
    assert totals["input"] == 140 and totals["output"] == 14, "子代理的 token 要算进总量"
    assert totals["sessions"] == 1 and totals["subagents"] == 1
    assert totals["subagentInput"] == 40 and totals["subagentRequests"] == 1
    assert [row["id"] for row in data["sessions"]] == ["s1"], "子代理不占会话表"
    assert [row["model"] for row in data["models"]] == ["model-a"]


def test_usage_stats_buckets_by_local_day_and_model(tmp_path, monkeypatch):
    usage_stats.reset()
    root = tmp_path / "sessions"
    _session(
        root,
        "s1",
        [
            _request("2026-03-10T16:30:00.000000Z", "model-a", 1000, 100),
            _request("2026-03-10T18:00:00.000000Z", "model-a", 500, 50),
            _request("2026-03-11T02:00:00.000000Z", "model-b", 300, 30),
        ],
    )

    data = usage_stats.snapshot(root, background=False)

    assert data["ready"] is True
    assert data["totals"]["requests"] == 3
    assert data["totals"]["input"] == 1800
    assert data["totals"]["output"] == 180
    assert data["totals"]["tokens"] == 1980
    assert [row["model"] for row in data["models"]] == ["model-a", "model-b"]
    assert data["models"][0]["input"] == 1500
    # 本地日期而不是 UTC 前缀：16:30Z 在东八区已经是次日
    expected = (
        usage_stats.datetime.fromisoformat("2026-03-10T16:30:00.000000+00:00")
        .astimezone()
        .strftime("%Y-%m-%d")
    )
    assert data["days"][0]["day"] == expected


def test_usage_stats_reuses_unchanged_files(tmp_path):
    usage_stats.reset()
    root = tmp_path / "sessions"
    _session(root, "s1", [_request("2026-03-10T10:00:00.000000Z", "m", 10, 1)], mtime=1_700_000_000)
    _session(root, "s2", [_request("2026-03-10T11:00:00.000000Z", "m", 20, 2)], mtime=1_700_000_000)
    cache = tmp_path / "usage_stats.json"

    first = usage_stats.snapshot(root, cache, background=False)
    assert first["parsed"] == 2 and first["reused"] == 0

    second = usage_stats.snapshot(root, cache, background=False, refresh=True)
    assert second["parsed"] == 0 and second["reused"] == 2
    assert second["totals"]["requests"] == 2


def test_usage_stats_replaces_a_changed_file_instead_of_adding(tmp_path):
    usage_stats.reset()
    root = tmp_path / "sessions"
    cache = tmp_path / "usage_stats.json"
    path = _session(root, "s1", [_request("2026-03-10T10:00:00.000000Z", "m", 10, 1)])
    usage_stats.snapshot(root, cache, background=False)

    path.write_text(
        json.dumps({"runs": [{"requests": [
            _request("2026-03-10T10:00:00.000000Z", "m", 10, 1),
            _request("2026-03-10T10:05:00.000000Z", "m", 40, 4),
        ]}]}),
        encoding="utf-8",
    )
    os.utime(path, (time.time() + 5, time.time() + 5))

    data = usage_stats.snapshot(root, cache, background=False, refresh=True)

    assert data["parsed"] == 1 and data["reused"] == 0
    assert data["totals"]["requests"] == 2, "改过的文件要被替换，不是累加"
    assert data["totals"]["input"] == 50


def test_usage_stats_keeps_previous_rows_when_a_file_is_unreadable(tmp_path):
    usage_stats.reset()
    root = tmp_path / "sessions"
    cache = tmp_path / "usage_stats.json"
    path = _session(root, "s1", [_request("2026-03-10T10:00:00.000000Z", "m", 10, 1)])
    usage_stats.snapshot(root, cache, background=False)

    path.write_text("{ this is not json", encoding="utf-8")
    os.utime(path, (time.time() + 5, time.time() + 5))

    data = usage_stats.snapshot(root, cache, background=False, refresh=True)

    assert data["totals"]["requests"] == 1, "读不出来的文件应沿用上次汇总，而不是把数字抹掉"


def test_usage_stats_drops_deleted_sessions(tmp_path):
    usage_stats.reset()
    root = tmp_path / "sessions"
    cache = tmp_path / "usage_stats.json"
    keeper = _session(root, "keep", [_request("2026-03-10T10:00:00.000000Z", "m", 10, 1)])
    doomed = _session(root, "gone", [_request("2026-03-10T10:00:00.000000Z", "m", 99, 9)])
    usage_stats.snapshot(root, cache, background=False)

    doomed.unlink()
    data = usage_stats.snapshot(root, cache, background=False, refresh=True)

    assert data["totals"]["requests"] == 1
    assert [row["id"] for row in data["sessions"]] == ["keep"]
    assert keeper.exists()


def test_usage_stats_falls_back_to_the_request_model_and_reports_cache_hits(tmp_path):
    usage_stats.reset()
    root = tmp_path / "sessions"
    _session(
        root,
        "s1",
        [
            {"started_at": "2026-03-10T10:00:00.000000Z", "model": "requested-only",
             "usage": {"prompt_tokens": 10, "completion_tokens": 1,
                       "prompt_cache_hit_tokens": 8, "prompt_cache_miss_tokens": 2}},
            {"started_at": "2026-03-10T10:01:00.000000Z", "model": "",
             "usage": {"prompt_tokens": 5, "completion_tokens": 1}},
        ],
    )

    data = usage_stats.snapshot(root, background=False)

    assert [row["model"] for row in data["models"]] == ["requested-only", usage_stats.UNKNOWN_MODEL]
    assert data["totals"]["cacheHit"] == 8
    assert data["totals"]["cacheMiss"] == 2


def test_usage_stats_ignores_requests_without_usage(tmp_path):
    usage_stats.reset()
    root = tmp_path / "sessions"
    _session(
        root,
        "s1",
        [
            {"started_at": "2026-03-10T10:00:00.000000Z", "model": "m", "usage": {}},
            {"started_at": "2026-03-10T10:01:00.000000Z", "model": "m"},
            _request("2026-03-10T10:02:00.000000Z", "m", 7, 3),
        ],
    )

    data = usage_stats.snapshot(root, background=False)

    assert data["totals"]["requests"] == 1
    assert data["totals"]["input"] == 7


def test_usage_stats_reports_first_token_and_throughput(tmp_path):
    def timed(stamp, ttft, generation, completion):
        return {
            "started_at": stamp,
            "model": "m",
            "usage": {"prompt_tokens": 10, "completion_tokens": completion},
            "phases": {"first_token": {"total_ms": ttft}, "llm_output": {"total_ms": generation}},
        }

    usage_stats.reset()
    root = tmp_path / "sessions"
    _session(
        root,
        "s1",
        [
            timed("2026-03-10T10:00:00.000000Z", 2000, 4000, 100),
            timed("2026-03-10T10:01:00.000000Z", 3000, 6000, 200),
            _request("2026-03-10T10:02:00.000000Z", "m", 10, 5),
        ],
    )

    totals = usage_stats.snapshot(root, background=False)["totals"]

    assert totals["ttftSamples"] == 2, "没有计时的请求不计入速度样本"
    assert totals["speedSamples"] == 2
    assert totals["ttftMs"] == 2500
    assert totals["tokensPerSec"] == 30.0, "(100+200) tokens / 10s"


def test_usage_stats_serves_stale_numbers_while_rebuilding(tmp_path, monkeypatch):
    usage_stats.reset()
    root = tmp_path / "sessions"
    cache = tmp_path / "usage_stats.json"
    _session(root, "s1", [_request("2026-03-10T10:00:00.000000Z", "m", 10, 1)])
    usage_stats.snapshot(root, cache, background=False)

    monkeypatch.setattr(usage_stats, "CACHE_TTL_SEC", -1)
    data = usage_stats.snapshot(root, cache, background=True)

    assert data["ready"] is True and data.get("stale") is True, "过期时先给旧数字，别让页签闪「统计中」"
    time.sleep(0.3)  # 等后台那一次重建收尾，避免影响后续用例


def test_usage_stats_endpoint_builds_in_the_background_then_serves(tmp_path, monkeypatch):
    import agent_harness
    import webui

    usage_stats.reset()
    sessions = tmp_path / "sessions"
    _session(sessions, "s1", [_request("2026-03-10T10:00:00.000000Z", "m", 10, 1)])
    manager = agent_harness.SessionManager(sessions, tmp_path / "index.json")
    monkeypatch.setattr(webui, "session_manager", manager)
    monkeypatch.setattr(webui, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(webui, "_is_configured", lambda: True)
    client = TestClient(webui.fastapi_app)

    first = client.get("/api/usage-stats").json()["data"]
    assert first["ready"] is False, "首次调用只负责踢后台重建，不能挂在请求上等"

    data = first
    for _ in range(60):
        time.sleep(0.1)
        data = client.get("/api/usage-stats").json()["data"]
        if data.get("ready"):
            break

    assert data["ready"] is True
    assert data["totals"]["requests"] == 1
    assert (tmp_path / ".config" / "usage_stats_cache.json").is_file()
