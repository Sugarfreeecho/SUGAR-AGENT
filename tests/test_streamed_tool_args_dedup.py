import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


BODY = (
    '{"items":[{"id":"inspect","text":"核对历史裁剪、投影与测试入口","status":"in_progress"},'
    '{"id":"fix","text":"实现裁剪优化与安全超时状态核验","status":"pending"},'
    '{"id":"test","text":"运行回归测试并说明生效方式","status":"pending"}]}'
)


def _split_copy(body):
    """Drop the two characters right after '{"items":[' like the live stream did."""
    head = '{"items":['
    assert body.startswith(head + '{"')
    return head + body[len(head) + 2:]


def test_repeated_payload_with_dropped_fragment_is_recovered():
    from agent_openai import _recover_repeated_stream_arguments

    damaged = _split_copy(BODY)
    raw = damaged + BODY * 3
    assert len(raw) == 750

    assert _recover_repeated_stream_arguments(raw) == {
        "items": [
            {"id": "inspect", "text": "核对历史裁剪、投影与测试入口", "status": "in_progress"},
            {"id": "fix", "text": "实现裁剪优化与安全超时状态核验", "status": "pending"},
            {"id": "test", "text": "运行回归测试并说明生效方式", "status": "pending"},
        ]
    }


def test_pure_duplicate_payload_is_recovered():
    from agent_openai import _recover_repeated_stream_arguments

    assert _recover_repeated_stream_arguments(BODY + BODY) is not None


def test_tool_acc_uses_recovered_args_instead_of_transport_error():
    from agent_openai import _tool_acc_to_parsed_list

    raw = _split_copy(BODY) + BODY * 3
    calls = _tool_acc_to_parsed_list(
        {1: {"id": "call_0fa7fa19806a4cb797acc15766546986", "name": "update_todo", "arguments": raw}}
    )

    assert len(calls) == 1
    assert calls[0]["name"] == "update_todo"
    assert "_stream_corrupted_arguments" not in calls[0]["args"]
    assert [item["id"] for item in calls[0]["args"]["items"]] == ["inspect", "fix", "test"]


def test_valid_arguments_are_untouched():
    from agent_openai import _tool_acc_to_parsed_list

    calls = _tool_acc_to_parsed_list(
        {0: {"id": "a", "name": "update_todo", "arguments": BODY}}
    )

    assert calls[0]["args"]["items"][0]["id"] == "inspect"


def test_single_malformed_payload_still_reports_corruption():
    from agent_openai import _recover_repeated_stream_arguments, _tool_acc_to_parsed_list

    broken = '{"items":[{"id":"inspect",'
    assert _recover_repeated_stream_arguments(broken) is None

    calls = _tool_acc_to_parsed_list({0: {"id": "a", "name": "update_todo", "arguments": broken}})
    assert calls[0]["args"]["_stream_corrupted_arguments"] == broken


def test_repeated_text_inside_a_string_is_not_repaired():
    from agent_openai import _recover_repeated_stream_arguments

    # Valid JSON whose value repeats internally must never hit the repair path.
    value = '{"text":"' + "abc" * 40 + '"}'
    assert _recover_repeated_stream_arguments(value) is None


def test_unrelated_truncated_payload_is_not_repaired():
    from agent_openai import _recover_repeated_stream_arguments

    truncated = BODY[:-40]
    assert _recover_repeated_stream_arguments(truncated) is None
