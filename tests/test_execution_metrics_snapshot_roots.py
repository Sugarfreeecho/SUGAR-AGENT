"""Concurrent diagnostics must not copy all requests while holding the lock."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import execution_metrics as metrics


@pytest.fixture
def isolated_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(metrics, "_root", tmp_path)
    monkeypatch.setattr(metrics, "_path_resolver", None)
    monkeypatch.setattr(metrics, "_sessions", {})
    monkeypatch.setattr(metrics, "_flush_deadlines", {})
    monkeypatch.setattr(metrics, "_flush_failed_sessions", set())
    monkeypatch.setattr(metrics, "_FLUSH_DELAY_SEC", 3600)
    return tmp_path


def capture():
    with metrics._lock:
        return metrics._capture_snapshot(metrics._load("s"))


def test_published_requests_survive_every_nested_mutation(isolated_metrics):
    metrics.record_request("s", "run", 1, context={"nested": [1]})
    metrics.record_phase("s", "run", 1, "pre_api", {"build": 2})
    metrics.record_stream_event("s", "run", 1, {"step": "first_delta", "ms_since_api_start": 1})
    frozen = capture()
    original = copy.deepcopy(frozen)
    old_root = frozen["runs"][0]["requests"][0]
    metrics.record_phase("s", "run", 1, "pre_api", {"estimate": 3})
    metrics.record_stream_event("s", "run", 1, {"step": "first_delta", "ms_since_api_start": 4})
    metrics.record_usage("s", "run", 1, {"prompt_tokens": 12})
    metrics.record_tool("s", "run", 1, "read_file", 5, False)
    metrics.record_request("s", "run", 1, context={"nested": [2]})
    metrics.record_run_fields("s", "run", extra={"value": [3]})
    assert frozen == original
    current = capture()
    row = current["runs"][0]["requests"][0]
    assert row is not old_root
    assert row["phases"]["pre_api"]["events"] == {"build": 2, "estimate": 3}
    assert row["phases"]["llm_stream"]["events"][0]["ms_since_api_start"] == 4
    assert row["usage"]["prompt_tokens"] == 12
    assert row["tools"][0]["duration_ms"] == 5
    assert row["context"]["nested"] == [2]
    metrics.flush("s")
    encoded = (isolated_metrics / "s/execution_metrics.json").read_text(encoding="utf-8")
    assert "_published" not in encoded
    assert json.loads(encoded) == current


def test_callers_cannot_mutate_published_input_values(isolated_metrics):
    context = {"nested": [1]}
    events = {"nested": [2]}
    extra = {"nested": [3]}
    metrics.record_request("s", "run", 1, context=context)
    metrics.record_phase("s", "run", 1, "custom", events, detail=extra)
    metrics.record_run_fields("s", "run", detail=extra)
    frozen = capture()
    original = copy.deepcopy(frozen)
    context["nested"].append(4)
    events["nested"].append(5)
    extra["nested"].append(6)
    assert frozen == original
    assert capture() == original


def test_loaded_requests_freeze_without_copying_unchanged_history(isolated_metrics, monkeypatch):
    data = {"session_id": "s", "version": 1, "runs": [{
        "run_id": "run", "requests": [{"react_iter": i, "phases": {"p": {"events": [i]}}}
                                       for i in range(1, 173)]}]}
    metrics._sessions["s"] = data
    frozen = capture()
    roots = frozen["runs"][0]["requests"]
    assert all(isinstance(row, metrics._RequestMetrics) for row in roots)
    real_copy = copy.deepcopy

    def check_copy(value, *args, **kwargs):
        assert all(value is not row for row in roots[:-1]), "copied a historical request"
        return real_copy(value, *args, **kwargs)

    monkeypatch.setattr(metrics.copy, "deepcopy", check_copy)
    again = capture()
    assert all(a is b for a, b in zip(roots, again["runs"][0]["requests"]))
    metrics.record_request("s", "run", 172, latest=42)
    newest = capture()["runs"][0]["requests"]
    assert all(a is b for a, b in zip(roots[:-1], newest[:-1]))
    assert "latest" not in roots[-1]
    assert newest[-1]["latest"] == 42


def test_public_snapshots_are_detached_and_run_pruning_preserves_old_snapshot(isolated_metrics, monkeypatch):
    metrics.record_request("s", "run", 1, context={"nested": [1]})
    published = capture()
    public = metrics.snapshot("s")
    public["runs"][0]["requests"][0]["context"]["nested"].append(2)
    assert capture()["runs"][0]["requests"][0]["context"]["nested"] == [1]
    monkeypatch.setattr(metrics, "_MAX_RUNS", 1)
    metrics.record_request("s", "next", 1, latest=9)
    assert len(published["runs"]) == 1
    assert published["runs"][0]["run_id"] == "run"
    assert capture()["runs"][0]["run_id"] == "next"
