import concurrent.futures
from pathlib import Path
from queue import Queue
import sys
import threading
from types import SimpleNamespace

import httpx
import pytest

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from agent_request_timing import RequestPreparationTrace, current_request_trace, request_timing_scope


def test_shared_trace_factory_keeps_only_the_immediately_previous_tool_boundary():
    from agent_request_timing import new_request_trace
    state = dict(session_id="s", _runtime_v2_run_id="r", _last_tool_returned_iter=6,
                 _last_tool_returned_perf=20, _last_tool_result_committed_perf=21,
                 _last_model_worker_done_perf=19)
    current = new_request_trace(state, 7, 22).snapshot()
    assert current["anchors"]["tool_returned"] == 20
    assert current["anchors"]["tool_result_committed"] == 21
    assert current["anchors"]["local_ready"] == 20
    assert current["previous_tool_iter"] == 6
    stale = new_request_trace(state, 8, 23).snapshot()
    assert stale["previous_tool_iter"] is None
    assert "tool_returned" not in stale["anchors"]


def test_trace_keeps_earliest_endpoint_and_does_not_count_generation():
    trace = RequestPreparationTrace("s", "run", 2, previous_tool_iter=1,
                                    anchors={"tool_returned": 1, "local_ready": 1.1})
    trace.mark("http_send_entered", 1.25)
    trace.mark("http_send_entered", 8)
    trace.mark("http_headers_started", 1.3)
    snapshot = trace.snapshot()
    assert snapshot["tool_return_to_http_send_ms"] == 250
    assert snapshot["local_ready_to_http_send_ms"] == 150
    assert snapshot["tool_return_to_headers_ms"] == 300
    assert snapshot["previous_tool_iter"] == 1


def test_outer_retry_keeps_first_send_and_original_preparation_boundaries():
    from agent_request_timing import new_request_trace
    state = dict(session_id="s", _runtime_v2_run_id="r", _last_tool_returned_iter=6,
                 _last_tool_returned_perf=20, _last_tool_result_committed_perf=21)
    first = new_request_trace(state, 7, 22)
    first.mark("http_send_entered", 22.1)
    state["_last_model_worker_done_perf"] = 25
    retry = new_request_trace(state, 7, 30, previous_trace=first)
    retry.mark("http_send_entered", 30.1)
    assert retry is first
    snapshot = retry.snapshot()
    assert snapshot["anchors"]["preparation_started"] == 22
    assert snapshot["anchors"]["local_ready"] == 20
    assert snapshot["anchors"]["http_send_entered"] == 22.1
    assert snapshot["tool_return_to_http_send_ms"] == 2100


@pytest.mark.parametrize("change,iteration", [
    ({"session_id": "other"}, 7), ({"_runtime_v2_run_id": "other"}, 7),
    ({}, 8), ({"_last_tool_returned_perf": 24}, 7),
    ({"_last_tool_returned_iter": 5}, 7),
])
def test_retry_trace_cannot_cross_request_or_tool_boundary(change, iteration):
    from agent_request_timing import new_request_trace
    state = dict(session_id="s", _runtime_v2_run_id="r", _last_tool_returned_iter=6,
                 _last_tool_returned_perf=20)
    first = new_request_trace(state, 7, 22)
    first.mark("http_send_entered", 22.1)
    state.update(change)
    current = new_request_trace(state, iteration, 30, previous_trace=first)
    assert current is not first
    assert not current.snapshot()["http_send_observed"]


def test_retry_without_a_send_does_not_invent_a_send_endpoint():
    from agent_request_timing import new_request_trace
    state = dict(session_id="s", _runtime_v2_run_id="r")
    first = new_request_trace(state, 1, 22)
    retry = new_request_trace(state, 1, 30, previous_trace=first)
    assert retry is first
    assert not retry.snapshot()["http_send_observed"]
    retry.mark("http_send_entered", 30.1)
    assert retry.snapshot()["preparation_to_http_send_ms"] == 8100


def test_parallel_requests_keep_transport_marks_on_their_own_trace():
    from agent_harness import RequestResponseLogger

    barrier = threading.Barrier(2)
    traces = [RequestPreparationTrace("s", f"r{i}", 2) for i in range(2)]

    def handler(request):
        barrier.wait(timeout=2)
        request.extensions["trace"]("http11.send_request_headers.started", {})
        request.extensions["trace"]("http11.send_request_body.started", {})
        return httpx.Response(200, json={"ok": True})

    with RequestResponseLogger(transport=httpx.MockTransport(handler)) as client:
        def send(trace):
            with request_timing_scope(trace):
                client.start_transport_trace()
                request = client.build_request("GET", "http://benchmark.invalid/local")
                assert client.send(request).status_code == 200
            assert current_request_trace() is None
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            list(pool.map(send, traces))
    for trace in traces:
        anchors = trace.snapshot()["anchors"]
        assert anchors["http_send_entered"] <= anchors["http_headers_started"] <= anchors["http_body_started"]
    assert traces[0].snapshot()["run_id"] != traces[1].snapshot()["run_id"]


def test_stream_candidate_thread_inherits_request_trace():
    from agent_messages import UserMessage
    from agent_openai import run_chat_completion_stream_worker

    seen = []
    chunk = SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(content="ok", reasoning_content=None, tool_calls=None),
        finish_reason=None, stop_reason=None,
    )], usage=None, model="test-model")

    def create(**kwargs):
        seen.append(current_request_trace())
        return iter([chunk])

    trace = RequestPreparationTrace("s", "r", 1)
    with request_timing_scope(trace):
        run_chat_completion_stream_worker(
            Queue(), SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
            "test-model", [UserMessage(content="hello")], temperature=0, max_tokens=16,
        )
    assert seen == [trace]
    assert not trace.snapshot()["http_send_observed"]
