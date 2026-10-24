r"""Measure the real Agent loop against a loopback SSE or JSON model, with durable sessions.

Only the model, title generation and remote connection warmup are replaced.
Runtime history, tools, plugin callbacks, streaming and HTTP send use production code.
Example (PowerShell, production runtime):
  & .\python\python.exe -X utf8 scripts/benchmark_agent_interround.py --steps 20 --output report.json
"""
from __future__ import annotations

import argparse
import asyncio
import cProfile
from contextlib import ExitStack
from functools import wraps
import hashlib
import gc
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_worker(mode: str, path: Path, ready_path: Path | None = None) -> None:
    block = b"load" * 65536
    if mode == "cpu":
        if ready_path is not None:
            ready_path.write_text("ready", encoding="utf-8")
        while True:
            hashlib.pbkdf2_hmac("sha256", block, b"benchmark", 2000)
    else:
        with path.open("w+b") as stream:
            if ready_path is not None:
                ready_path.write_text("ready", encoding="utf-8")
            while True:
                stream.seek(0)
                stream.write(block)
                stream.flush()
                os.fsync(stream.fileno())
                time.sleep(0.005)


def distribution(values: list[float]) -> dict:
    ordered = sorted(values)
    def percentile(p):
        return ordered[min(len(ordered) - 1, max(0, int(len(ordered) * p + 0.999999) - 1))]
    return {"samples": len(values), "p50_ms": round(statistics.median(values), 3),
            "p95_ms": percentile(0.95), "p99_ms": percentile(0.99), "max_ms": max(values),
            "over_500ms": sum(value >= 500 for value in values)}


def seed_archived_sessions(session_manager, scratch: Path, count: int, task_dirs: int) -> list[str]:
    """Use real session namespaces and metadata, not rejected dummy directories."""
    assert session_manager.sessions_dir.resolve().is_relative_to(scratch.resolve())
    session_ids = []
    for _ in range(count):
        session_id, *_ = session_manager.get_or_create_session(work_dir=str(scratch))
        session_manager.set_session_archived(session_id, True)
        directory = session_manager.sessions_dir / session_id
        (directory / "runtime_observability.json").write_text(json.dumps({
            "version": 1, "session_id": session_id,
            "runs": [{"run_id": "archived", "status": "finished"}],
        }), encoding="utf-8")
        for child in range(task_dirs):
            (directory / "files/node_modules" / f"package-{child}" / "dist").mkdir(parents=True)
        assert session_manager._load_metadata(session_id).get("archived") is True
        session_ids.append(session_id)
    return session_ids


def benchmark(args, scratch: Path) -> dict:
    os.environ.update({
        "MYAGENT_DOTENV_OVERRIDE": "0", "WORK_DIR": str(scratch),
        "MYAGENT_SECURITY_HOME": str(scratch / "security"), "MCP_ENABLED": "false",
        "MYAGENT_UI_CLOSED_NOTIFY": "0", "MYAGENT_TOOL_SEARCH": "off",
    })
    os.environ.setdefault("RUNTIME_V2_SNAPSHOT_INLINE_GRACE_MS", "10")
    sys.path.insert(0, str(ROOT / "app"))
    import agent_loop as agent
    import agent_harness as harness
    import execution_metrics
    import runtime_observability
    from runtime_v2 import RuntimeHistoryOps, RuntimeProjector, SnapshotStore
    from openai import OpenAI
    assert harness.session_manager.sessions_dir.resolve().is_relative_to(scratch.resolve())
    if args.watchdog_full_scan_ms:
        runtime_observability._FULL_SCAN_INTERVAL_SEC = args.watchdog_full_scan_ms / 1000

    logging.basicConfig(filename=str(args.output.with_suffix(".log")), level=logging.INFO,
                        encoding="utf-8", force=True)
    # Match WebUI startup: these workers exist before any measured Agent run.
    prewarmed_snapshot_workers = SnapshotStore.start_checkpoint_workers()
    for index in range(args.steps * args.tools_per_round):
        fixture = f"benchmark fixture {index}\n"
        if args.fixture_source:
            fixture = args.fixture_source.read_text(encoding="utf-8")
        (scratch / f"fixture-{index}.txt").write_text(fixture, encoding="utf-8")
    archived_session_ids = seed_archived_sessions(
        harness.session_manager, scratch, args.archived_sessions, args.archived_task_dirs)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        counter = 0
        def log_message(self, *_args):
            pass
        def do_POST(self):
            request_payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            index = Handler.counter
            Handler.counter += 1
            if index < args.steps:
                calls = []
                for slot in range(args.tools_per_round):
                    fixture_index = index * args.tools_per_round + slot
                    tool_args = {"path": str(scratch / f"fixture-{fixture_index}.txt")}
                    if args.tool == "write_file":
                        tool_args["content"] = f"benchmark update {fixture_index}\n"
                    elif args.tool == "run_shell":
                        tool_args = {"command": f"echo benchmark-{fixture_index}"}
                    calls.append({"index": slot, "id": f"call-{index}-{slot}",
                        "type": "function", "function": {"name": args.tool, "arguments": json.dumps(tool_args)}})
                delta = {"role": "assistant", "tool_calls": calls}
                reason = "tool_calls"
            else:
                delta, reason = {"role": "assistant", "content": "Benchmark completed."}, "stop"
            if not request_payload.get("stream"):
                message = dict(delta)
                if "tool_calls" in message:
                    message["tool_calls"] = [{key:value for key,value in call.items() if key != "index"}
                                             for call in message["tool_calls"]]
                message["reasoning_content"] = "".join(
                    f"Inspecting fixture, step {part}. " for part in range(args.stream_fragments))
                body = json.dumps({"id":f"chat-{index}", "object":"chat.completion", "created":1,
                    "model":"benchmark-model", "choices":[{"index":0,"message":message,"finish_reason":reason}],
                    "usage":{"prompt_tokens":1000+index*100,"completion_tokens":100,"total_tokens":1100+index*100}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            def chunk(value, finish=None):
                return {"id": f"chat-{index}", "object": "chat.completion.chunk", "created": 1,
                        "model": "benchmark-model", "choices": [{"index": 0, "delta": value, "finish_reason": finish}]}
            deltas = []
            if args.stream_fragments > 1:
                for part in range(args.stream_fragments):
                    deltas.append({"reasoning_content": f"Inspecting fixture, step {part}. "})
                if "tool_calls" in delta:
                    for tool in delta["tool_calls"]:
                        arguments = tool["function"]["arguments"]
                        width = max(1, (len(arguments) + args.stream_fragments - 1) // args.stream_fragments)
                        for offset in range(0, len(arguments), width):
                            fragment = {"index": tool["index"], "function": {"arguments": arguments[offset:offset + width]}}
                            if offset == 0:
                                fragment.update(id=tool["id"], type="function")
                                fragment["function"]["name"] = tool["function"]["name"]
                            deltas.append({"tool_calls": [fragment]})
                else:
                    deltas.append(delta)
            else:
                deltas.append(delta)
            chunks = [chunk(value) for value in deltas] + [chunk({}, reason)]
            # Exercise the production usage callbacks, including sessions with
            # no Goal. Omitting usage silently bypassed that local hot path.
            chunks.append({"id": f"chat-{index}", "object": "chat.completion.chunk", "created": 1,
                           "model": "benchmark-model", "choices": [],
                           "usage": {"prompt_tokens": 1000 + index * 100,
                                     "completion_tokens": 100, "total_tokens": 1100 + index * 100}})
            frames = [("data: " + json.dumps(value) + "\n\n").encode() for value in chunks]
            frames.append(b"data: [DONE]\n\n")
            body = b"".join(frames)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            for frame in frames:
                self.wfile.write(frame)
                self.wfile.flush()
                if args.fragment_interval_ms:
                    time.sleep(args.fragment_interval_ms / 1000)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    http = harness.RequestResponseLogger(trust_env=False, timeout=30)
    client = OpenAI(api_key="local-benchmark", base_url=f"http://127.0.0.1:{server.server_port}/v1",
                    http_client=http, max_retries=0)

    def model_config(_sid):
        return client, "benchmark-model", 1024, 8_000_000

    async def one_case(name: str, long_history: bool) -> dict:
        sid, *_ = harness.session_manager.get_or_create_session(work_dir=str(scratch))
        parent_sid = None
        if args.subagent:
            parent_sid = sid
            sid = harness.session_manager.create_subagent_session(
                parent_sid, "interround benchmark", "generalPurpose", 1)
        ops = RuntimeHistoryOps(harness.session_manager.sessions_dir,
                                path_resolver=harness.session_manager._resolve_session_path)
        if long_history:
            text = ("benchmark history " * 128)[:2048]
            messages = [{"type": "user" if index % 2 == 0 else "assistant",
                         "content": f"history {index}: {text}"} for index in range(args.long_messages)]
            rows = [{"type": "model_history_replaced", "payload": {"messages": messages, "reason": "benchmark"}}]
            rows += [{"type": "context_tokens", "payload": {"estimated": index, "benchmark_padding": "x" * 8192}}
                     for index in range(args.journal_events)]
            rows += [{"type": "execution_recorded", "run_id": "seed-completed", "payload": {
                "execution_id": f"seed-{index}", "kind": "tool", "tool": "read_file", "status": "completed",
                "run_id": "seed-completed", "result": "prior result " * 600}}
                for index in range(args.execution_records)]
            events = ops.event_log.append_batch(sid, rows)
            snapshot = ops.projector.project(events)
            ops.snapshots.stamp_event_log(sid, snapshot, ops.event_log.event_path(sid))
            ops.snapshots.write(sid, snapshot)
        initial_log_bytes = ops.event_log.event_path(sid).stat().st_size if ops.event_log.event_path(sid).exists() else 0
        Handler.counter = 0
        errors = []
        entered = time.perf_counter()
        watchdog_samples = []
        watchdog_stop = asyncio.Event()
        async def watchdog():
            import runtime_observability as obs
            while not watchdog_stop.is_set():
                scan_started = time.perf_counter()
                await asyncio.to_thread(obs.scan_stale_runs, 90,
                                        live_checker=lambda s, r: s == sid)
                watchdog_samples.append(round((time.perf_counter() - scan_started) * 1000, 3))
                try:
                    await asyncio.wait_for(watchdog_stop.wait(), args.watchdog_interval_ms / 1000)
                except asyncio.TimeoutError:
                    pass
        watchdog_task = asyncio.create_task(watchdog()) if args.watchdog_interval_ms else None
        profile = cProfile.Profile(timer=time.thread_time) if args.profile else None
        if profile is not None:
            profile.enable()
        try:
            if args.subagent:
                from agent_subagent import _execute_subagent_run, subagent_registry
                async def parent_emit(event):
                    if event.get("type") == "error":
                        errors.append(str(event.get("content") or event.get("message")))
                await _execute_subagent_run(
                    child_id=sid, parent_session_id=parent_sid, user_text="Read each benchmark fixture, then finish.",
                    description="interround benchmark", subagent_type="generalPurpose", resumed=False,
                    parent_emit=parent_emit, run_in_background=args.subagent_background,
                )
                if args.subagent_background:
                    await subagent_registry.wait(sid, timeout=args.timeout)
                    if subagent_registry.is_running(sid):
                        raise TimeoutError("background benchmark subagent did not finish")
            else:
                async for event in agent.astream_events("Read each benchmark fixture, then finish.",
                                                        session_id=sid, context_token_mode=args.token_mode):
                    if event.get("type") == "error":
                        errors.append(str(event.get("content") or event.get("message")))
        finally:
            watchdog_stop.set()
            if watchdog_task is not None:
                await watchdog_task  # Join the scan before removing its temporary files.
        completed = time.perf_counter()
        if profile is not None:
            profile.disable()
            profile.dump_stats(str(args.output.with_suffix(f".{name}.main.pstats")))
        execution_metrics.flush(sid)
        data = execution_metrics._load(sid)
        run = data["runs"][-1]
        if args.subagent and (not run.get("run_id") or run.get("status") != "finished"):
            raise RuntimeError(f"subagent must have a distinct finished run: {run.get('run_id')!r} {run.get('status')}")
        requests = run["requests"]
        if isinstance(requests, dict):
            requests = list(requests.values())
        traces = [request["local_request_timing"] for request in requests if "local_request_timing" in request]
        measured = [trace for trace in traces if "tool_return_to_headers_ms" in trace]
        replay_events = [row for row in replay_observations if entered <= row["at"] <= completed]
        def in_gap(row):
            return any(trace["anchors"]["tool_returned"] <= row["at"] <= trace["anchors"]["http_headers_started"]
                       for trace in measured)
        phases = [request.get("phases", {}).get("pre_api", {}).get("events", {}) for request in requests]
        cache_counts = {
            "full_model_projection_calls": sum(row["kind"] == "full" for row in replay_events),
            "interround_full_model_projection_calls": sum(row["kind"] == "full" and in_gap(row) for row in replay_events),
            "projection_tail_catchups": sum(row["kind"] == "tail" for row in replay_events),
            "projection_version_misses": sum(row["kind"] == "version_miss" for row in replay_events),
            "registry_cache_hits": sum("tool_registry_cache_hit" in phase for phase in phases),
            "registry_stale_hits": sum("tool_registry_stale_hit" in phase for phase in phases),
            "registry_rebuilds": sum("tool_registry_revision" in phase
                                      and "tool_registry_cache_hit" not in phase
                                      and "tool_registry_stale_hit" not in phase for phase in phases),
        }
        tool_rows = [tool for request in requests for tool in request.get("tools", [])]
        if any(tool.get("failed") for tool in tool_rows) or len(tool_rows) != args.steps * args.tools_per_round:
            raise RuntimeError(f"{name}: benchmark tools must all succeed: {tool_rows}")
        if errors or len(measured) != args.steps:
            raise RuntimeError(f"{name}: expected {args.steps} complete gaps, got {len(measured)}, errors={errors}")
        checkpoint_wait_started = time.perf_counter()
        assert SnapshotStore(harness.session_manager.sessions_dir,
                             path_resolver=harness.session_manager._resolve_session_path).wait_for_checkpoint(sid, 10)
        # The final fact also schedules an independent execution checkpoint.
        # Join it outside the measured run before TemporaryDirectory removes
        # its files; otherwise Windows can race its open/replace with rmtree.
        from runtime_v2.execution_journal import ExecutionJournal
        from runtime_v2.recovery_checkpoint import RecoveryCheckpoint
        recovery_journal = ExecutionJournal(
            harness.session_manager.sessions_dir,
            path_resolver=harness.session_manager._resolve_session_path)
        assert RecoveryCheckpoint.wait(recovery_journal, sid, 10)
        with recovery_journal._session_lock(sid):
            recovery_state = recovery_journal._state(sid)
        RecoveryCheckpoint.schedule(recovery_journal, sid, recovery_state, force=True)
        assert RecoveryCheckpoint.wait(recovery_journal, sid, 10)
        recovered = RecoveryCheckpoint.load(recovery_journal, sid)
        if recovered is None or recovered["seq"] != recovery_state["seq"]:
            raise RuntimeError("benchmark execution recovery checkpoint was not saved and validated")
        from runtime_v2 import RuntimeModelProjection
        durable = RuntimeModelProjection(harness.session_manager.sessions_dir,
            path_resolver=harness.session_manager._resolve_session_path).read_message_dicts(sid)
        expected_ids = {f"call-{step}-{slot}" for step in range(args.steps) for slot in range(args.tools_per_round)}
        durable_tools = [row for row in durable if row.get("type") == "tool"]
        if (len(durable_tools) != len(expected_ids)
                or {row.get("tool_call_id") for row in durable_tools} != expected_ids):
            raise RuntimeError("benchmark durable model history lost or duplicated a tool result")
        return {"case": name, "session_id": sid, "parent_session_id": parent_sid, "run_id": run["run_id"],
                "long_history": long_history,
                "injected_load": {"cpu_workers": args.stress_workers if name.startswith("loaded") else 0,
                                  "io_workers": 1 if name.startswith("loaded") else 0},
                "run_elapsed_ms": round((completed - entered) * 1000, 3),
                "post_run_checkpoint_wait_ms": round((time.perf_counter() - checkpoint_wait_started) * 1000, 3),
                "initial_log_bytes": initial_log_bytes, "history_messages": args.long_messages if long_history else 0,
                "http_requests": Handler.counter, "first_request_from_entry_ms": round(
                    (traces[0]["anchors"]["http_headers_started"] - entered) * 1000, 3),
                "successful_tools": len(tool_rows),
                "durable_model_tools": len(durable_tools),
                "recovery_checkpoint_validated": True,
                "watchdog_scans": watchdog_samples,
                "cache_counts": cache_counts,
                "tool_to_headers": distribution([trace["tool_return_to_headers_ms"] for trace in measured]),
                "tool_to_http_send": distribution([trace["tool_return_to_http_send_ms"] for trace in measured]),
                "local_ready_to_http_send": distribution([trace["local_ready_to_http_send_ms"] for trace in measured]),
                "traces": traces, "requests": requests}

    cases = []
    diagnostic_spans = []
    replay_observations = []
    try:
        with ExitStack() as patches:
            if args.reference_ui_row_commits:
                patches.enter_context(patch.object(harness.SessionManager, "_commit_display_batch_if_supported",
                                                    lambda *a, **k: None))
            if args.reference_disk_reads:
                from runtime_v2.event_log import SessionEventLog
                patches.enter_context(patch.object(SessionEventLog, "recent_owned_append", lambda *a, **k: None))
                patches.enter_context(patch.object(SnapshotStore, "_read_stamped_suffix", lambda *a, **k: None))
                patches.enter_context(patch.object(runtime_observability, "_observability_paths",
                    lambda root: list(root.rglob("runtime_observability.json")) if root else []))
            original_project = RuntimeProjector.project
            original_catchup = SnapshotStore.project_after_append
            def counted_project(projector, events):
                replay_observations.append({"at": time.perf_counter(), "kind": "full"})
                return original_project(projector, events)
            def counted_catchup(store, sid, snapshot, log, projector, through_seq):
                kind = "tail" if store._projection_version_matches(snapshot) else "version_miss"
                replay_observations.append({"at": time.perf_counter(), "kind": kind})
                return original_catchup(store, sid, snapshot, log, projector, through_seq)
            patches.enter_context(patch.object(RuntimeProjector, "project", counted_project))
            patches.enter_context(patch.object(SnapshotStore, "project_after_append", counted_catchup))
            if args.diagnostics:
                import agent_openai
                from agent_request_timing import current_request_trace
                from runtime_v2.event_log import SessionEventLog
                from runtime_v2.execution_journal import ExecutionJournal

                def capture(label, started, cpu_started, call_args, call_kwargs):
                    trace = current_request_trace()
                    event = next((arg for arg in reversed(call_args) if isinstance(arg, dict) and "type" in arg), {})
                    diagnostic_spans.append({
                        "label": label, "started": started, "ended": time.perf_counter(),
                        "thread_cpu_ms": round((time.thread_time() - cpu_started) * 1000, 3),
                        "thread": threading.current_thread().name, "event_type": event.get("type"),
                        "react_iter": trace.react_iter if trace is not None else event.get("react_iter"),
                    })

                def observed_sync(label, function):
                    @wraps(function)
                    def observed(*call_args, **call_kwargs):
                        started, cpu_started = time.perf_counter(), time.thread_time()
                        try:
                            return function(*call_args, **call_kwargs)
                        finally:
                            capture(label, started, cpu_started, call_args, call_kwargs)
                    return observed

                def observed_async(label, function):
                    @wraps(function)
                    async def observed(*call_args, **call_kwargs):
                        started, cpu_started = time.perf_counter(), time.thread_time()
                        try:
                            return await function(*call_args, **call_kwargs)
                        finally:
                            capture(label, started, cpu_started, call_args, call_kwargs)
                    return observed

                for owner, name in (
                    (harness.SessionManager, "append_ui_event"),
                    (ExecutionJournal, "record"), (ExecutionJournal, "_state"),
                    (SessionEventLog, "_append_unlocked"),
                    (SnapshotStore, "project_after_append"),
                    (agent, "_persist_state"), (agent, "_runtime_v2_replace_model_history"),
                    (agent, "_state_run_has_write_fence"),
                    (agent, "_runtime_v2_append_model_message"),
                    (agent, "derive_dialogue_from_assistant_history"),
                    (agent, "_message_to_dict"),
                    (agent_openai, "messages_to_openai_params"),
                    (harness.RequestResponseLogger, "build_request"),
                    (threading.Thread, "start"),
                ):
                    patches.enter_context(patch.object(owner, name, observed_sync(name, getattr(owner, name))))
                for name in ("_emit_tool_call_sse", "persist_execution_event", "_raise_if_steer_requested"):
                    patches.enter_context(patch.object(agent, name, observed_async(name, getattr(agent, name))))
            if args.profile:
                original_react = agent._react_node_once
                async def profiled_react(*call_args, **kwargs):
                    profile = cProfile.Profile(timer=time.thread_time)
                    profile.enable()
                    try:
                        return await original_react(*call_args, **kwargs)
                    finally:
                        profile.disable()
                        profile.dump_stats(str(args.output.with_suffix(".react.pstats")))
                patches.enter_context(patch.object(agent, "_react_node_once", profiled_react))
            for module in (agent, harness):
                patches.enter_context(patch.object(module, "resolve_executor_config_for_session", model_config))
                patches.enter_context(patch.object(module, "executor_http_client", http))
            patches.enter_context(patch.object(harness, "warm_llm_connections_if_stale", lambda: False))
            patches.enter_context(patch.object(agent, "setup_logging", lambda *a, **k: None))
            patches.enter_context(patch.object(agent, "schedule_session_title_generation", lambda *a: False))
            patches.enter_context(patch.object(agent, "MAX_REACT_ITER", max(64, args.steps + 5)))
            if args.non_stream:
                patches.enter_context(patch.object(agent, "EXECUTOR_STREAM", False))
            for loaded in (False, True):
                if args.only_case and not args.only_case.startswith("loaded" if loaded else "light"):
                    continue
                workers = []
                ready_paths = []
                try:
                    if loaded:
                        for index, mode in enumerate(["cpu"] * args.stress_workers + ["io"]):
                            ready = scratch / f"stress-{index}.ready"
                            ready_paths.append(ready)
                            workers.append(subprocess.Popen(
                                [sys.executable, str(Path(__file__).resolve()), "--load-worker", mode,
                                 "--load-path", str(scratch / f"stress-{index}.bin"),
                                 "--load-ready-path", str(ready)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                            ))
                        deadline = time.monotonic() + 30
                        while not all(path.is_file() for path in ready_paths):
                            if any(worker.poll() is not None for worker in workers):
                                raise RuntimeError("load worker exited before becoming ready")
                            if time.monotonic() >= deadline:
                                raise TimeoutError("load workers did not become ready within 30s")
                            time.sleep(0.02)
                        time.sleep(2)
                    for long_history in (False, True):
                        name = ("loaded" if loaded else "light") + ("_long" if long_history else "_short")
                        if args.only_case and name != args.only_case:
                            continue
                        if any(worker.poll() is not None for worker in workers):
                            raise RuntimeError("load worker stopped before measured case")
                        try:
                            import psutil
                            worker_cpu_before = [sum(psutil.Process(worker.pid).cpu_times()[:2]) for worker in workers]
                        except ImportError:
                            worker_cpu_before = None
                        case_started = time.perf_counter()
                        result = asyncio.run(asyncio.wait_for(one_case(name, long_history), args.timeout))
                        case_elapsed = time.perf_counter() - case_started
                        if any(worker.poll() is not None for worker in workers):
                            raise RuntimeError("load worker stopped during measured case")
                        if worker_cpu_before is not None:
                            worker_cpu_after = [sum(psutil.Process(worker.pid).cpu_times()[:2]) for worker in workers]
                            result["load_worker_cpu_seconds"] = [round(after - before, 3)
                                for before, after in zip(worker_cpu_before, worker_cpu_after)]
                            result["load_sample_elapsed_seconds"] = round(case_elapsed, 3)
                        cases.append(result)
                        print(json.dumps({key: result[key] for key in ("case", "initial_log_bytes", "tool_to_headers")}), flush=True)
                finally:
                    for worker in workers:
                        worker.terminate()
                    for worker in workers:
                        worker.wait(timeout=10)
    finally:
        server.shutdown()
        client.close()
        execution_metrics.flush()
        gc.collect()
    return {"scope": ("Production task subagent" if args.subagent else "Production astream_events")
                     + " with a loopback model; no paid API calls",
            "subagent": {"enabled": args.subagent, "background": args.subagent_background},
            "scratch": {"parent": str(scratch.parent), "volume": scratch.drive},
            "python": {"executable": sys.executable, "version": sys.version},
            "snapshot_inline_grace_ms": os.environ["RUNTIME_V2_SNAPSHOT_INLINE_GRACE_MS"],
            "diagnostic_spans": diagnostic_spans,
            "prewarmed_snapshot_workers": prewarmed_snapshot_workers,
            "tool": args.tool, "token_mode": args.token_mode,
            "tools_per_round": args.tools_per_round,
            "execution_records": args.execution_records,
            "reference_disk_reads": args.reference_disk_reads,
            "reference_ui_row_commits": args.reference_ui_row_commits,
            "stream": {"enabled": not args.non_stream, "fragments": args.stream_fragments, "fragment_interval_ms": args.fragment_interval_ms,
                       "usage_included": True, "fixture_source": str(args.fixture_source) if args.fixture_source else None},
            "watchdog": {"archived_sessions": args.archived_sessions,
                         "archive_session_ids": archived_session_ids,
                         "archive_metadata_validated": True,
                         "archived_task_dirs": args.archived_task_dirs,
                         "interval_ms": args.watchdog_interval_ms,
                         "full_scan_ms": args.watchdog_full_scan_ms or runtime_observability._FULL_SCAN_INTERVAL_SEC * 1000},
            "threshold_ms": 500, "load": {"cpu_workers": args.stress_workers,
            "readiness": "live process handles and ready handshake", "warmup_seconds": 2,
            "logical_cpus": os.cpu_count(), "io_workers": 1, "io_block_bytes": 262144, "io_pause_seconds": 0.005},
            "long_messages": args.long_messages, "journal_events": args.journal_events, "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--tools-per-round", type=int, default=1, help="Native tool calls in each model response")
    parser.add_argument("--execution-records", type=int, default=0, help="Completed execution records seeded into long cases")
    parser.add_argument("--reference-disk-reads", action="store_true", help="A/B reference using disk reads and recursive enumeration")
    parser.add_argument("--reference-ui-row-commits", action="store_true", help="Reference using individual journal/UI commits with the same facts")
    parser.add_argument("--tool", choices=("read_file", "write_file", "run_shell"), default="read_file")
    parser.add_argument("--token-mode", choices=("hybrid", "calculated"), default="hybrid")
    parser.add_argument("--long-messages", type=int, default=1000)
    parser.add_argument("--journal-events", type=int, default=4000)
    parser.add_argument("--stress-workers", type=int, default=min(8, max(1, (os.cpu_count() or 2) // 2)))
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--only-case", choices=("light_short", "light_long", "loaded_short", "loaded_long"))
    parser.add_argument("--profile", action="store_true", help="Write thread-CPU profiles; timings are diagnostic, not acceptance data")
    parser.add_argument("--diagnostics", action="store_true", help="Record nested local operation spans; diagnostic data, not acceptance data")
    parser.add_argument("--stream-fragments", type=int, default=1, help="Reasoning and argument fragments per response")
    parser.add_argument("--fragment-interval-ms", type=float, default=0, help="Loopback stream frame spacing")
    parser.add_argument("--non-stream", action="store_true", help="Exercise the production non-streaming request path with JSON replies")
    parser.add_argument("--subagent", action="store_true", help="Measure the actual task subagent entry and child delivery")
    parser.add_argument("--subagent-background", action="store_true", help="Run --subagent on its persistent background loop")
    parser.add_argument("--fixture-source", type=Path, help="Read-only source copied into disposable read fixtures")
    parser.add_argument("--archived-sessions", type=int, default=0, help="Disposable archived observability files")
    parser.add_argument("--archived-task-dirs", type=int, default=0, help="Task package directories under each archived session")
    parser.add_argument("--watchdog-interval-ms", type=float, default=0, help="Run the real stale-run scanner concurrently")
    parser.add_argument("--watchdog-full-scan-ms", type=float, default=0, help="Override the full-scan cadence in this disposable benchmark")
    parser.add_argument("--output", type=Path, default=ROOT / ".analysis/interround-500ms-implementation/benchmark.json")
    parser.add_argument("--scratch-parent", type=Path, help="Disposable fixture parent, for testing on the production filesystem volume")
    parser.add_argument("--load-worker", choices=("cpu", "io"), help=argparse.SUPPRESS)
    parser.add_argument("--load-path", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--load-ready-path", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.subagent_background and not args.subagent:
        parser.error("--subagent-background requires --subagent")
    if args.subagent and args.token_mode != "hybrid":
        parser.error("task subagent currently uses hybrid counting; --token-mode calculated is main-only")
    if args.load_worker:
        load_worker(args.load_worker, args.load_path, args.load_ready_path)
        return
    if (args.steps < 1 or args.tools_per_round < 1 or args.execution_records < 0
            or args.long_messages < 0 or args.journal_events < 0 or args.stress_workers < 0
            or args.stream_fragments < 1 or args.fragment_interval_ms < 0):
        parser.error("steps must be positive; history and worker counts must be non-negative")
    if (args.archived_sessions < 0 or args.archived_task_dirs < 0
            or args.watchdog_interval_ms < 0 or args.watchdog_full_scan_ms < 0):
        parser.error("archived sessions and watchdog interval must be non-negative")
    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    scratch_parent = (args.scratch_parent if args.scratch_parent is not None else Path(tempfile.gettempdir())).resolve()
    scratch_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="myagent-interround-", dir=scratch_parent) as directory:
        scratch = Path(directory).resolve()
        assert scratch.parent == scratch_parent
        report = benchmark(args, scratch)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
