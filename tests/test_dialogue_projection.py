from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from agent_harness import derive_dialogue_from_assistant_history, COMPACT_RECAP_USER_PREFIX
from agent_messages import AssistantMessage, UserMessage, SystemMessage, ToolMessage


def test_only_last_eligible_final_in_each_user_segment_is_visible():
    user = UserMessage(content="question")
    first = AssistantMessage(content="first", metadata={"is_final": True})
    last = AssistantMessage(content="last", metadata={"is_final": True})
    next_user = UserMessage(content="next")
    history = [AssistantMessage(content="orphan", metadata={"is_final": True}), user,
               first, SystemMessage(content="New Agent Loop Start"),
               ToolMessage(content="tool", tool_call_id="t"), last,
               AssistantMessage(content="draft"), next_user]
    assert derive_dialogue_from_assistant_history(history) == [user, last, next_user]


def test_filtered_users_and_micro_shrink_finals_do_not_split_or_replace_segment():
    user = UserMessage(content="question")
    final = AssistantMessage(content="answer", metadata={"is_final": True})
    recap = UserMessage(content=COMPACT_RECAP_USER_PREFIX + " recap")
    micro_user = UserMessage(content="working", metadata={"micro_shrink": True})
    shrunk = AssistantMessage(content="work", metadata={"is_final": True, "micro_shrink": True})
    legacy = AssistantMessage(content="【微压工作块】hidden", metadata={"is_final": True})
    assert derive_dialogue_from_assistant_history([user, final, recap, micro_user, shrunk, legacy]) == [user, final]
    assert derive_dialogue_from_assistant_history([user, shrunk, legacy]) == [user]
