import sys
from pathlib import Path
from queue import Queue
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer"},
                },
                "required": ["command"],
            },
        },
    }
]


def _dsml(command="python -c \"print('ok')\"", timeout="60"):
    return (
        "<｜DSML｜tool_calls>\n"
        '<｜DSML｜invoke name="run_shell">\n'
        f'<｜DSML｜parameter name="command" string="true">{command}</｜DSML｜parameter>\n'
        f'<｜DSML｜parameter name="timeout" string="false">{timeout}</｜DSML｜parameter>\n'
        "</｜DSML｜invoke>\n"
        "</｜DSML｜tool_calls>"
    )


def test_non_stream_dsml_in_reasoning_becomes_valid_tool_call():
    from agent_openai import parse_assistant_message

    msg = SimpleNamespace(
        content="",
        reasoning_content="先检查文件。\n" + _dsml(),
        tool_calls=None,
    )
    turn = parse_assistant_message(msg, tools=TOOLS)

    assert turn.content == ""
    assert turn.reasoning_content == "先检查文件。"
    assert len(turn.tool_calls or []) == 1
    call = turn.tool_calls[0]
    assert call["name"] == "run_shell"
    assert call["args"] == {
        "command": "python -c \"print('ok')\"",
        "timeout": 60,
    }
    assert call["id"].startswith("call_dsml_")


def test_unknown_or_malformed_dsml_is_not_executed_or_exposed():
    from agent_openai import parse_assistant_message

    unknown = _dsml().replace('name="run_shell"', 'name="delete_everything"')
    msg = SimpleNamespace(
        content="准备执行。\n" + unknown,
        reasoning_content=None,
        tool_calls=None,
    )
    turn = parse_assistant_message(msg, tools=TOOLS)

    assert turn.content == ""
    assert turn.tool_calls is None
    assert "DSML" not in turn.content


def test_mixed_valid_and_incomplete_dsml_is_rejected_as_one_unsafe_turn():
    from agent_openai import parse_assistant_message

    content = "准备执行。\n" + _dsml() + "\n<｜DSML｜invoke name=\"run_shell\">"
    msg = SimpleNamespace(content=content, reasoning_content=None, tool_calls=None)
    turn = parse_assistant_message(msg, tools=TOOLS)

    assert turn.content == ""
    assert turn.tool_calls is None
    assert "DSML" not in turn.content


def test_text_after_dsml_is_not_misclassified_as_an_executable_protocol_turn():
    from agent_openai import parse_assistant_message

    content = "下面只是协议示例：\n" + _dsml() + "\n这不是实际调用。"
    msg = SimpleNamespace(content=content, reasoning_content=None, tool_calls=None)
    turn = parse_assistant_message(msg, tools=TOOLS)

    assert turn.content == ""
    assert turn.tool_calls is None


def test_standard_tool_calls_remain_authoritative_over_raw_dsml_artifact():
    from agent_openai import parse_assistant_message

    standard = SimpleNamespace(
        id="call_standard",
        function=SimpleNamespace(
            name="run_shell",
            arguments='{"command":"echo standard","timeout":30}',
        ),
    )
    msg = SimpleNamespace(
        content=_dsml(command="echo conflicting"),
        reasoning_content=None,
        tool_calls=[standard],
    )
    turn = parse_assistant_message(msg, tools=TOOLS)

    assert turn.content == ""
    assert len(turn.tool_calls or []) == 1
    assert turn.tool_calls[0]["id"] == "call_standard"
    assert turn.tool_calls[0]["args"]["command"] == "echo standard"


def test_dsml_inside_fenced_example_remains_plain_text():
    from agent_openai import parse_assistant_message

    content = "示例：\n```\n" + _dsml() + "\n```"
    msg = SimpleNamespace(content=content, reasoning_content=None, tool_calls=None)
    turn = parse_assistant_message(msg, tools=TOOLS)

    assert "DSML" in turn.content
    assert turn.tool_calls is None


def test_stream_dsml_is_held_back_and_recovered_without_frontend_leak():
    from agent_messages import UserMessage
    from agent_openai import run_chat_completion_stream_worker

    raw = "先检查。\n" + _dsml(command="python -c \"print(123)\"")
    pieces = [
        raw[:8],
        raw[8:15],
        raw[15:42],
        raw[42:117],
        raw[117:],
    ]
    chunks = []
    for piece in pieces:
        delta = SimpleNamespace(content=None, reasoning_content=piece, tool_calls=None)
        chunks.append(
            SimpleNamespace(
                choices=[SimpleNamespace(delta=delta, finish_reason=None, stop_reason=None)],
                usage=None,
                model="deepseek-v4-test",
            )
        )
    chunks.append(
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content=None, reasoning_content=None, tool_calls=None),
                    finish_reason="stop",
                    stop_reason=None,
                )
            ],
            usage=None,
            model="deepseek-v4-test",
        )
    )
    completions = SimpleNamespace(create=lambda **_kwargs: iter(chunks))
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    q = Queue()

    run_chat_completion_stream_worker(
        q,
        client,
        "deepseek-v4-test",
        [UserMessage(content="inspect")],
        tools=TOOLS,
        temperature=0,
        max_tokens=256,
    )

    rows = []
    while not q.empty():
        rows.append(q.get())
    visible = "".join(
        str(row[1])
        for row in rows
        if row and row[0] in {"reasoning", "content"}
    )
    turn = next(row[1] for row in rows if row and row[0] == "turn")
    finish = next(row[1] for row in rows if row and row[0] == "finish")
    deltas = [row[1] for row in rows if row and row[0] == "tool_call_delta"]

    assert visible == "先检查。\n"
    assert "DSML" not in visible
    assert turn.reasoning_content == "先检查。"
    assert turn.content == ""
    assert len(turn.tool_calls or []) == 1
    assert turn.tool_calls[0]["args"]["command"] == 'python -c "print(123)"'
    assert turn.tool_calls[0]["args"]["timeout"] == 60
    assert deltas[0]["name_delta"] == "run_shell"
    assert finish["finish_reason"] == "tool_calls"
