"""Search scope, pipe backpressure, budgets, and actual child cleanup."""
import asyncio
import json
import platform
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
platform.system()  # Warm Windows platform discovery before Popen substitution.
import agent_tools
import grep_runtime
from grep_worker import requires_isolation


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    monkeypatch.setenv("GREP_USE_RIPGREP", "1")
    if not agent_tools._resolve_ripgrep_path():
        pytest.skip("bundled ripgrep required for scope parity")
    for name in ("keep.py", "other.txt", ".hidden/hide.py", "ignored/drop.py",
                 "nested/node_modules/drop.py", "nested/logs/drop.py", "nested/ok.py"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("needle marker\n", encoding="utf-8")
    (tmp_path / ".ignore").write_text("ignored/\n", encoding="utf-8")
    return tmp_path


def search(root, pattern="needle", **kwargs):
    return agent_tools.grep(pattern, path=str(root), **kwargs)


def matches(result):
    return {line.rsplit(":1:", 1)[0] for line in result.splitlines() if ":1:" in line}


@pytest.mark.parametrize("value", ["*.py", ["*.py"], ("*.py",)])
def test_filter_strings_are_complete_patterns(corpus, value):
    result = search(corpus, include=value)
    assert matches(result) == {str(corpus / "keep.py"), str(corpus / "nested/ok.py")}


@pytest.mark.parametrize("value", ["*.txt", ["*.txt"]])
def test_exclude_string_and_array_agree(corpus, value):
    assert matches(search(corpus, exclude=value)) == {
        str(corpus / "keep.py"), str(corpus / "nested/ok.py")}


@pytest.mark.parametrize("value", [42, {"*.py": True}, [None], [1, "*.py"]])
def test_invalid_filters_fail_before_spawn(corpus, value, monkeypatch):
    monkeypatch.setattr(agent_tools.subprocess, "Popen", lambda *a, **kw: pytest.fail("spawned"))
    assert "must be a string or an array of strings" in search(corpus, include=value)


@pytest.mark.parametrize("hidden,ignored", [(False, False), (True, False), (False, True), (True, True)])
def test_compatibility_regex_keeps_rg_candidate_scope(corpus, hidden, ignored):
    kwargs = dict(include_hidden=hidden, include_ignored=ignored)
    native = matches(search(corpus, **kwargs))
    fallback = matches(search(corpus, "(?<=needle) marker", **kwargs))
    assert native == fallback
    assert str(corpus / ".hidden/hide.py") in native if hidden else str(corpus / ".hidden/hide.py") not in native
    assert str(corpus / "ignored/drop.py") in native if ignored else str(corpus / "ignored/drop.py") not in native
    assert not any("node_modules" in name or "nested\\logs" in name for name in native)


def test_explicit_excluded_directory_remains_searchable(corpus):
    assert "drop.py:1:" in search(corpus / "nested/node_modules")
    assert "drop.py:1:" in search(corpus / "nested/node_modules", "(?<=needle) marker")


@pytest.mark.parametrize("pattern", ["needle", "(?<=needle) marker"])
def test_nonrecursive_scope(corpus, pattern):
    assert matches(search(corpus, pattern, recursive=False)) == {
        str(corpus / "keep.py"), str(corpus / "other.txt")}


def test_unavailable_engine_does_not_silently_ignore_ignore_files(corpus, monkeypatch):
    monkeypatch.setattr(agent_tools, "_resolve_ripgrep_path", lambda: None)
    result = search(corpus)
    assert result.startswith("Error:") and "ignore rules" in result
    result = search(corpus, include_ignored=True, include="*.py")
    assert str(corpus / "ignored/drop.py") in matches(result)
    assert not any("node_modules" in name for name in matches(result))


@pytest.mark.parametrize("pattern,isolated", [
    ("needle", False), (r"a\.b", False), ("def (foo|bar)", False),
    ("a+", True), ("(a+)+$", True), (r"(a)\1", True), ("(?<=a)b", True),
])
def test_regex_fast_path_is_conservative(pattern, isolated):
    assert requires_isolation(pattern) is isolated


def test_plain_single_file_keeps_no_spawn_fast_path(tmp_path, monkeypatch):
    file = tmp_path / "中文.py"
    file.write_bytes("NEEDLE 中文\r\nnext\r".encode())
    monkeypatch.setattr(agent_tools.subprocess, "Popen", lambda *a, **kw: pytest.fail("unnecessary spawn"))
    assert "中文.py:1: NEEDLE 中文" in search(file, "needle")
    assert search(file, "needle", case_sensitive=True) == "No matches found"
    assert search(file, include="*.txt") == "No matches found"


def test_binary_size_and_unicode_in_worker(tmp_path, monkeypatch):
    file = tmp_path / "数据.txt"
    file.write_text("你好 marker\n", encoding="utf-8")
    assert "数据.txt:1: 你好 marker" in search(file, "(?<=你好) marker")
    file.write_bytes(b"needle\0binary")
    # Explicit files retain the existing Python decoding/binary behavior.
    assert "needle" in search(file, "needle+")
    assert search(tmp_path, "(?<=need)le") == "No matches found"
    file.write_bytes(b"needle" * 20_000)
    monkeypatch.setenv("GREP_FILE_MAX_BYTES", "100000")
    result = search(file, "needle+")
    assert "skipped 1 large files" in result


@pytest.mark.parametrize("value", ["invalid", "inf", "nan"])
def test_invalid_timeout_cannot_disable_watchdog(monkeypatch, value):
    monkeypatch.setenv("GREP_TIMEOUT_SEC", value)
    assert grep_runtime.SearchRun().timeout == 30


def install_child(monkeypatch, code):
    original = subprocess.Popen
    children = []
    def popen(_args, **kwargs):
        child = original([sys.executable, "-I", "-c", code], **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(agent_tools.subprocess, "Popen", popen)
    monkeypatch.setattr(agent_tools, "_resolve_ripgrep_path", lambda: "synthetic-rg")
    return children


def native(root, **kwargs):
    return agent_tools._grep_with_ripgrep(regex=re.compile("needle"), target=root,
        recursive=True, max_results=kwargs.get("max_results", 10), line_cap=200,
        output_cap=10_000, file_cap=100_000)


def test_large_stderr_does_not_wait_for_timeout(tmp_path, monkeypatch):
    children = install_child(monkeypatch,
        "import sys;sys.stderr.write('e'*262144);sys.stderr.flush();print('file:1:needle',flush=True)")
    monkeypatch.setenv("GREP_TIMEOUT_SEC", "2")
    run = grep_runtime.SearchRun()
    started = time.perf_counter()
    with grep_runtime.bind(run):
        result = native(tmp_path)
    assert "file:1:needle" in result and "timed out" not in result
    assert time.perf_counter() - started < 1.8
    assert run.rows[0]["stderr_bytes"] == 262144
    assert children[0].poll() is not None
    assert all(getattr(children[0], name).closed for name in ("stdout", "stderr"))


def test_cap_stops_child_without_waiting_for_more_output(tmp_path, monkeypatch):
    children = install_child(monkeypatch,
        "import time;print('file:1:needle',flush=True);time.sleep(10)")
    started = time.perf_counter()
    result = native(tmp_path, max_results=1)
    assert "output truncated" in result
    assert time.perf_counter() - started < 2
    assert children[0].poll() is not None


def test_output_cap_and_partial_timeout_are_explicit(tmp_path, monkeypatch):
    install_child(monkeypatch, "import time;print('file:1:needle',flush=True);time.sleep(10)")
    monkeypatch.setenv("GREP_TIMEOUT_SEC", "1")
    result = native(tmp_path)
    assert "file:1:needle" in result and "timed out" in result and "incomplete" in result
    assert "No matches found" not in result
    from tool_result_status import _tool_result_status
    assert _tool_result_status("grep", result)["ok"] is False


def test_read_errors_preserve_partial_hits_and_report_failure(tmp_path, monkeypatch):
    import grep_worker
    from tool_result_status import _tool_result_status
    file = tmp_path / "file.txt"
    file.write_text("needle")
    def scan(path, regex, file_cap, line_cap, emit, *args, **kwargs):
        emit(dict(file=str(path), line=1, text="needle"))
        emit(dict(error="Error reading next.txt: permission denied"))
        return 0
    monkeypatch.setattr(grep_worker, "scan_file", scan)
    result = search(file)
    assert "needle" in result and "permission denied" in result and "incomplete" in result
    assert _tool_result_status("grep", result)["ok"] is False


def test_io_error_is_not_retried_as_python(tmp_path, monkeypatch):
    install_child(monkeypatch, "import sys;sys.stderr.write('Access denied');sys.exit(2)")
    monkeypatch.setattr(agent_tools, "_grep_python", lambda *a: pytest.fail("unexpected retry"))
    assert "Access denied" in search(tmp_path)


def test_one_total_deadline_for_native_enumeration_and_python(tmp_path, monkeypatch):
    file = tmp_path / "sample.txt"
    file.write_text("a" * 32 + "!\n")
    original = subprocess.Popen
    children = []
    def popen(args, **kwargs):
        if "--regexp" in args:
            args = [sys.executable, "-I", "-c",
                    "import sys,time;time.sleep(.65);sys.stderr.write('regex parse error');sys.exit(2)"]
        child = original(args, **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(agent_tools.subprocess, "Popen", popen)
    monkeypatch.setenv("GREP_TIMEOUT_SEC", "1")
    started = time.perf_counter()
    result = search(tmp_path, "^(a+)+$")
    elapsed = time.perf_counter() - started
    assert "timed out" in result and "incomplete" in result
    assert elapsed < 1.7
    assert all(child.poll() is not None for child in children)


def test_cancel_kills_backtracking_process_and_carries_identity(tmp_path, monkeypatch, caplog):
    file = tmp_path / "sample.txt"
    file.write_text("a" * 32 + "!\n")
    original = subprocess.Popen
    children = []
    spawned = threading.Event()
    def popen(args, **kwargs):
        child = original(args, **kwargs)
        children.append(child)
        spawned.set()
        return child
    monkeypatch.setattr(agent_tools.subprocess, "Popen", popen)
    caplog.set_level("INFO", logger="agent_harness")
    async def run():
        task = asyncio.create_task(grep_runtime.invoke(agent_tools.grep,
            dict(pattern="^(a+)+$", path=str(file)),
            dict(session_id="child-session", run_id="run-1", react_iter=3, tool_call_id="call-7")))
        assert await asyncio.to_thread(spawned.wait, 3)
        await asyncio.sleep(.1)
        started = time.perf_counter()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert time.perf_counter() - started < 1.5
    asyncio.run(run())
    assert children and all(child.poll() is not None for child in children)
    rows = [json.loads(r.message.split("grep_timing ", 1)[1]) for r in caplog.records if "grep_timing " in r.message]
    assert len(rows) == 1
    assert rows[0]["tool_call_id"] == "call-7" and rows[0]["session_id"] == "child-session"
    assert rows[0]["stop_reason"] == "cancelled"


def test_expired_worker_queue_does_not_spawn(tmp_path, monkeypatch):
    file = tmp_path / "sample.txt"
    file.write_text("needle")
    monkeypatch.setattr(agent_tools.subprocess, "Popen", lambda *a, **kw: pytest.fail("late spawn"))
    run = grep_runtime.SearchRun(session_id="queued")
    run.deadline = time.perf_counter() - .1
    with grep_runtime.bind(run):
        assert "timed out" in search(file, "needle+")


def test_native_line_buffering_flag_is_always_set(tmp_path, monkeypatch):
    seen = []
    original = subprocess.Popen
    def popen(args, **kwargs):
        seen.append(args)
        return original(args, **kwargs)
    monkeypatch.setattr(agent_tools.subprocess, "Popen", popen)
    (tmp_path / "file.txt").write_text("needle")
    assert "needle" in search(tmp_path)
    assert "--line-buffered" in seen[0]


def test_real_rg_cap_arrives_before_input_eof(tmp_path, monkeypatch):
    original = subprocess.Popen
    writers = []
    def popen(args, **kwargs):
        # Preserve all production rg flags; substitute a pipe-backed input.
        kwargs["stdin"] = subprocess.PIPE
        child = original([*args[:-1], "-"], **kwargs)
        def write():
            try:
                child.stdin.write("needle\n")
                child.stdin.flush()
                time.sleep(.8)
            except (OSError, ValueError):
                pass
            finally:
                child.stdin.close()
        writer = threading.Thread(target=write)
        writer.start()
        writers.append(writer)
        return child
    monkeypatch.setattr(agent_tools.subprocess, "Popen", popen)
    start = time.perf_counter()
    result = native(tmp_path, max_results=1)
    elapsed = time.perf_counter() - start
    for writer in writers:
        writer.join(2)
    assert "needle" in result and "truncated" in result
    assert elapsed < .7  # Input deliberately stays open for .8s.


def test_queue_wait_is_measured_and_cancelled_search_never_starts(tmp_path, monkeypatch, caplog):
    caplog.set_level("INFO", logger="agent_harness")
    file = tmp_path / "file.txt"
    file.write_text("needle")
    monkeypatch.setattr(agent_tools.subprocess, "Popen", lambda *a, **kw: pytest.fail("queued cancellation spawned"))
    entered, release = threading.Event(), threading.Event()
    executor = grep_runtime._SearchExecutor(max_workers=1, capacity=2)
    monkeypatch.setattr(grep_runtime, "_search_executor", lambda: executor)
    def blocker():
        entered.set()
        release.wait(2)
    async def run():
        blocked = executor._executor.submit(blocker)
        assert entered.wait(1)
        task = asyncio.create_task(grep_runtime.invoke(agent_tools.grep,
            dict(pattern="needle+", path=str(file)), dict(tool_call_id="queued")))
        await asyncio.sleep(.06)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, .5)
        assert not release.is_set()
        release.set()
        await asyncio.wrap_future(blocked)
    try:
        asyncio.run(run())
    finally:
        release.set()
        executor.shutdown()
    row = next(json.loads(r.message.split("grep_timing ", 1)[1])
               for r in caplog.records if "grep_timing " in r.message)
    assert row["worker_queue_ms"] is None and row["stop_reason"] == "cancelled"
    assert row["queue_outcome"] == "abandoned_before_start"


def test_parent_agent_cancellation_reaches_native_grep(tmp_path, monkeypatch):
    import agent_loop
    file = tmp_path / "file.txt"
    file.write_text("a" * 32 + "!\n")
    original = subprocess.Popen
    spawned = threading.Event()
    children = []
    def popen(args, **kwargs):
        child = original(args, **kwargs)
        children.append(child)
        spawned.set()
        return child
    monkeypatch.setattr(agent_tools.subprocess, "Popen", popen)
    async def no_steer(*args):
        return None
    monkeypatch.setattr(agent_loop, "_raise_if_steer_requested", no_steer)
    async def run():
        task = asyncio.create_task(agent_loop._await_steerable({},
            agent_loop._invoke_plain_tool(agent_tools.grep, dict(pattern="^(a+)+$", path=str(file)),
                                          grep_metadata=dict(session_id="subagent")),
            None, "tool", cancel_on_parent=True))
        assert await asyncio.to_thread(spawned.wait, 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(run())
    assert children and all(child.poll() is not None for child in children)


def test_concurrent_calls_keep_identity_separate(tmp_path, caplog):
    caplog.set_level("INFO", logger="agent_harness")
    file = tmp_path / "file.txt"
    file.write_text("needle\n")
    async def run():
        return await asyncio.gather(*[grep_runtime.invoke(agent_tools.grep,
            dict(pattern="needle", path=str(file)),
            dict(session_id=f"session-{index}", tool_call_id=f"call-{index}")) for index in range(4)])
    assert all("needle" in result for result in asyncio.run(run()))
    rows = [json.loads(r.message.split("grep_timing ", 1)[1]) for r in caplog.records if "grep_timing " in r.message]
    assert {(r["session_id"], r["tool_call_id"]) for r in rows} == {
        (f"session-{i}", f"call-{i}") for i in range(4)}
