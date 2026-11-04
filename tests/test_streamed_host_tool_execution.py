"""Exercise the nested stream scheduler without a network model or live session."""

import ast
import asyncio
import inspect
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))


def _loop_tree():
    import agent_loop

    return ast.parse(inspect.getsource(agent_loop._react_node_once)).body[0]


def _nested(tree, name):
    return next(node for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name)


def _scope(parallel_safe=True):
    import agent_loop

    descriptor = SimpleNamespace(
        parallel_safe=parallel_safe, pressure_limited=False, early_stream_safe=True,
        execution_name="history_context")

    async def await_tool(state, awaitable, *args, **kwargs):
        return await awaitable

    async def no_steer(*args):
        pass

    return {
        **vars(agent_loop),
        "state": {"session_id": "stream-test"},
        "emit": None,
        "iter_count": 1,
        "session_meta": {},
        "session_work_root": lambda meta: ROOT,
        "tool_registry": SimpleNamespace(resolve=lambda name: descriptor),
        "tool_search": SimpleNamespace(
            BRIDGE_NAMES=set(), call_descriptor=lambda registry, call: descriptor),
        "authorize_tool": lambda **kwargs: (
            None, SimpleNamespace(outcome=agent_loop.DecisionOutcome.ALLOW), None),
        "_await_steerable": await_tool,
        "_raise_if_steer_requested": no_steer,
        "_tool_steer_policy": lambda *args: {"interruptibility": "safe"},
    }


def test_streamed_host_batch_is_unknown_until_turn_and_resets_each_iteration():
    tree = _loop_tree()
    iteration = next(node for node in ast.walk(tree) if isinstance(node, ast.While))

    def assigned_name(node):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            return node.targets[0].id

    start = next(i for i, node in enumerate(iteration.body) if assigned_name(node) == "turn")
    end = next(i for i, node in enumerate(iteration.body)
               if assigned_name(node) == "request_scope_setter")
    setup = "\n".join(ast.unparse(node) for node in iteration.body[start:end])
    # Use the actual host service expression and the actual stream setup in the
    # same closure. This catches both an unbound first read and stale later reads.
    service_dict = next(node for node in ast.walk(tree)
                        if isinstance(node, ast.Dict)
                        and any(isinstance(key, ast.Constant) and key.value == "tool_batch_size"
                                for key in node.keys))
    batch_expr = next(value for key, value in zip(service_dict.keys, service_dict.values)
                      if isinstance(key, ast.Constant) and key.value == "tool_batch_size")
    functions = "\n".join(ast.unparse(_nested(tree, name)) for name in (
        "_early_tool_call_from_acc", "_run_early_tool_call", "_maybe_start_closed_tool_call"))
    harness = f"""
async def scenario():
    early_sizes, final_sizes = [], []
    for final_size in (2, 1):
{textwrap.indent(setup, '        ')}
        async def execute_one(call):
            await asyncio.sleep(0)
            return {ast.unparse(batch_expr)}
{textwrap.indent(functions, '        ')}
        _maybe_start_closed_tool_call({{
            'index': 0, 'id': 'host-call', 'name_delta': 'history_context',
            'arguments_delta': '{{"action":"search","query":"test"}}',
        }})
        early_sizes.append(await asyncio.wait_for(early_tool_tasks[0], 1))
        tool_calls_list = [{{}}] * final_size
        final_sizes.append(await execute_one({{}}))
    return early_sizes, final_sizes
"""
    scope = _scope()
    exec(compile(harness, "stream_batch_regression", "exec"), scope)

    assert asyncio.run(scope["scenario"]()) == ([0, 0], [2, 1])


@pytest.mark.parametrize("execution_path", ["early_parallel", "early_ordered", "post_turn_parallel"])
def test_unexpected_tool_error_keeps_call_id_through_checkpoint(execution_path):
    import agent_loop

    tree = _loop_tree()
    scope = _scope(parallel_safe=execution_path != "early_ordered")
    scope.update(early_tool_results={}, early_tool_tasks={}, early_ordered_tool_lock=asyncio.Lock(),
                 llm_history=[], work_messages=[], checkpointed_tool_result_ids=set(),
                 cpu_pressure=SimpleNamespace(tool_parallelism=lambda limit: 2),
                 _state_run_has_write_fence=lambda state: True,
                 _state_interrupt_requested=lambda state: False)
    committed, emitted = [], []

    async def execute_one(call):
        await asyncio.sleep(0)
        raise RuntimeError("host setup failed")

    def persist(state, message):
        committed.append(message)

    async def fact_commit(function, *args, on_committed):
        result = function(*args)
        on_committed(result)
        return result

    async def emit_result(emit, result, iteration, state):
        emitted.append(agent_loop._tool_result_sse_event(result, iteration))

    async def checkpoint_ready(results):
        for result in results:
            await scope["checkpoint_completed_tool_result"](result)

    scope.update(execute_one=execute_one, run_fact_commit=fact_commit,
                 _persist_state_with_model_append=persist, _emit_tool_call_sse=emit_result,
                 checkpoint_ready_tool_results=checkpoint_ready)
    functions = [_nested(tree, name) for name in (
        "_run_early_tool_call", "is_read_only_tool", "_batch_barrier_positions",
        "_early_task_for", "run_tool_batch", "checkpoint_completed_tool_result")]
    exec(compile(ast.Module(body=functions, type_ignores=[]), "stream_error_regression", "exec"), scope)
    calls = [
        {"name": "history_context", "id": "call-first", "index": 0, "args": {"action": "search"}},
        {"name": "history_context", "id": "call-second", "index": 1, "args": {"action": "search"}},
    ]

    async def scenario():
        if execution_path == "post_turn_parallel":
            return await scope["run_tool_batch"](calls)
        results = await asyncio.gather(*(
            scope["_run_early_tool_call"](call["index"], call) for call in calls))
        # Early completion must still wait for the assistant commit barrier.
        assert committed == [] and emitted == []
        for result in results:
            await scope["checkpoint_completed_tool_result"](result)
        return results

    results = asyncio.run(scenario())
    assert all(result["tool_failed"] for result in results)
    assert [result["tool_id"] for result in results] == ["call-first", "call-second"]
    assert sorted(message.tool_call_id for message in committed) == ["call-first", "call-second"]
    assert all("host setup failed" in message.content for message in committed)
    assert sorted(row["tool_call_id"] for row in emitted) == ["call-first", "call-second"]
    assert all(row["status"]["ok"] is False for row in emitted)
    assistant = agent_loop.AssistantMessage(content="", tool_calls=calls)
    clean, dropped = agent_loop._drop_orphan_tool_messages([assistant, *committed])
    assert dropped == []
    assert len(clean) == 3


@pytest.mark.parametrize("error_type", [asyncio.CancelledError, "steer"])
def test_early_tool_control_interrupts_are_not_converted_to_failures(error_type):
    import agent_loop

    if error_type == "steer":
        error_type = agent_loop._SteerRestartRequested
    scope = _scope()
    scope.update(early_tool_results={}, early_ordered_tool_lock=asyncio.Lock())

    async def execute_one(call):
        raise error_type()

    scope["execute_one"] = execute_one
    runner = _nested(_loop_tree(), "_run_early_tool_call")
    exec(compile(ast.Module(body=[runner], type_ignores=[]), "stream_interrupt_regression", "exec"), scope)
    with pytest.raises(error_type):
        asyncio.run(scope["_run_early_tool_call"](0, {"name": "history_context", "args": {}, "id": "call"}))
    assert scope["early_tool_results"] == {}


def test_read_only_tools_run_parallel_with_serial_tools():
    """A shell call must not delay the read-only calls that follow it."""
    tree = _loop_tree()
    scope = _scope()
    read_descriptor = SimpleNamespace(
        parallel_safe=True, pressure_limited=False, early_stream_safe=True,
        execution_name="read_file")
    serial_descriptor = SimpleNamespace(
        parallel_safe=False, pressure_limited=False, early_stream_safe=True,
        execution_name="run_shell")
    scope.update(
        tool_search=SimpleNamespace(
            BRIDGE_NAMES=set(),
            call_descriptor=lambda registry, call: (
                read_descriptor if call.get("name") == "read_file" else serial_descriptor
            ),
        ),
        early_tool_tasks={}, llm_history=[], work_messages=[],
        checkpointed_tool_result_ids=set(),
        cpu_pressure=SimpleNamespace(tool_parallelism=lambda limit: limit),
        _state_run_has_write_fence=lambda state: True,
        _state_interrupt_requested=lambda state: False,
    )
    committed = []

    def tool_result(call):
        return {
            "type": "tool", "tool_id": call["id"], "tool_name": call["name"],
            "tool_args": dict(call.get("args") or {}), "tool_call_index": call.get("index"),
            "result": "ok", "tool_detail_ui": "ok", "tool_detail_llm": "ok",
            "execution_status": "completed",
        }

    shell_started = asyncio.Event()
    release_shell = asyncio.Event()
    read_finished = asyncio.Event()

    async def execute_one(call):
        if call["name"] == "run_shell":
            shell_started.set()
            await release_shell.wait()
        else:
            read_finished.set()
        return tool_result(call)

    def persist(state, message):
        committed.append(message)

    async def fact_commit(function, *args, on_committed=None):
        result = function(*args)
        if on_committed is not None:
            on_committed(result)
        return result

    async def emit_result(emit, result, iteration, state):
        return None

    async def checkpoint_ready(results):
        for result in results:
            await scope["checkpoint_completed_tool_result"](result)

    scope.update(execute_one=execute_one, run_fact_commit=fact_commit,
                 _persist_state_with_model_append=persist,
                 _emit_tool_call_sse=emit_result,
                 checkpoint_ready_tool_results=checkpoint_ready)
    functions = [_nested(tree, name) for name in (
        "is_read_only_tool", "_batch_barrier_positions", "_early_task_for",
        "run_tool_batch", "checkpoint_completed_tool_result")]
    exec(compile(ast.Module(body=functions, type_ignores=[]), "batch_overlap", "exec"), scope)

    calls = [
        {"name": "run_shell", "id": "call-shell", "index": 0, "args": {"command": "sleep"}},
        {"name": "read_file", "id": "call-read", "index": 1, "args": {"path": "a.txt"}},
    ]

    async def scenario():
        batch = asyncio.create_task(scope["run_tool_batch"](calls))
        await asyncio.wait_for(shell_started.wait(), 1)
        # The read-only call must finish while the shell is still running.
        await asyncio.wait_for(read_finished.wait(), 1)
        assert not batch.done()
        release_shell.set()
        return await asyncio.wait_for(batch, 5)

    results = asyncio.run(scenario())
    assert [row["tool_id"] for row in results] == ["call-shell", "call-read"]
    assert [message.tool_call_id for message in committed] == ["call-read", "call-shell"]
