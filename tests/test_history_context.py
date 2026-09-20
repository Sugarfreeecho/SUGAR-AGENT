import json
import uuid
from pathlib import Path


class _SessionManager:
    def __init__(self, root: Path):
        self.sessions_dir = root

    @staticmethod
    def _normalize_session_id(value: str) -> str:
        return str(uuid.UUID(str(value)))

    def _resolve_session_path(self, session_id: str) -> Path:
        sid = self._normalize_session_id(session_id)
        path = (self.sessions_dir / sid).resolve()
        path.relative_to(self.sessions_dir.resolve())
        return path


def _write_event(manager, session_id, seq, content):
    session_dir = manager._resolve_session_path(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "schema_version": 1,
        "seq": seq,
        "timestamp": "2026-09-20T00:00:00Z",
        "type": "assistant_final_committed",
        "session_id": session_id,
        "payload": {"content": content},
    }
    (session_dir / "events.jsonl").write_text(
        json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def test_archive_excerpt_preserves_dialogue_and_references_omitted_fields(tmp_path):
    from agent_messages import AssistantMessage, ToolMessage, UserMessage
    from history_context import active_excerpt, archive_messages

    manager = _SessionManager(tmp_path)
    session_id = str(uuid.uuid4())
    assistant = AssistantMessage(
        content="assistant final",
        tool_calls=[{"name": "read_file", "args": {"path": "x"}, "id": "call-1"}],
        additional_kwargs={"reasoning_content": "private reasoning"},
    )
    archive = archive_messages(
        manager,
        session_id,
        [
            UserMessage(content="user question"),
            assistant,
            ToolMessage(content="large private tool result", tool_call_id="call-1"),
        ],
        reason="test",
    )

    excerpt = active_excerpt(archive, max_chars=8_000)

    assert "用户: user question" in excerpt
    assert "助手: assistant final" in excerpt
    assert "private reasoning" not in excerpt
    assert "large private tool result" not in excerpt
    assert "[推理已归档 ref=history:" in excerpt
    assert "[工具调用已归档 ref=history:" in excerpt
    assert "[工具结果已归档 ref=history:" in excerpt
    assert Path(archive["path"]).is_file()


def test_archive_excerpt_replaces_only_oversized_visible_body(tmp_path):
    from agent_messages import AssistantMessage, UserMessage
    from history_context import active_excerpt, archive_messages

    manager = _SessionManager(tmp_path)
    session_id = str(uuid.uuid4())
    archive = archive_messages(
        manager,
        session_id,
        [UserMessage(content="u" * 4_000), AssistantMessage(content="short answer")],
        reason="test",
    )

    excerpt = active_excerpt(archive, max_chars=500)

    assert "[用户正文过长，已归档 ref=history:" in excerpt
    assert "助手: short answer" in excerpt


def test_history_context_search_and_read_current_and_global(tmp_path):
    from agent_messages import UserMessage
    from history_context import archive_messages, history_context

    manager = _SessionManager(tmp_path)
    current_id = str(uuid.uuid4())
    other_id = str(uuid.uuid4())
    _write_event(manager, current_id, 1, "current event needle")
    _write_event(manager, other_id, 2, "global-only evidence")
    archive = archive_messages(
        manager,
        current_id,
        [UserMessage(content="archived special phrase")],
        reason="test",
    )

    current = history_context(
        manager, current_id, action="search", scope="current", query="special phrase"
    )
    assert len(current["results"]) == 1
    assert current["results"][0]["content"] == "用户：archived special phrase"
    assert set(current["results"][0]) == {"ref", "content"}
    item_ref = current["results"][0]["ref"]
    item = history_context(
        manager, current_id, action="read", scope="current", ref=item_ref
    )
    assert item == {"content": "用户：archived special phrase"}

    whole_archive = history_context(
        manager, current_id, action="read", scope="current", ref=archive["ref"]
    )
    assert whole_archive == {"content": "用户：archived special phrase"}

    assert history_context(
        manager, current_id, action="search", scope="current", query="global-only"
    )["results"] == []
    global_result = history_context(
        manager, current_id, action="search", scope="global", query="global-only"
    )
    assert len(global_result["results"]) == 1
    assert global_result["results"][0]["session_id"] == other_id
    assert global_result["results"][0]["content"] == "助手：global-only evidence"
    assert "source_file" not in global_result["results"][0]

    sourced = history_context(
        manager,
        current_id,
        action="search",
        scope="current",
        query="current event",
        include_source=True,
    )
    assert sourced["results"][0]["content"] == "助手：current event needle"
    assert sourced["results"][0]["source_file"].endswith("events.jsonl")


def test_history_context_hides_storage_metadata_and_irrelevant_matches(tmp_path):
    from history_context import history_context

    manager = _SessionManager(tmp_path)
    session_id = str(uuid.uuid4())
    session_dir = manager._resolve_session_path(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    events = [
        {
            "schema_version": 1,
            "seq": 7,
            "timestamp": "2026-09-20T00:00:00Z",
            "type": "assistant_final_committed",
            "session_id": session_id,
            "run_id": "irrelevant-run-id",
            "payload": {"content": "clean answer", "internal_counter": 999},
        },
        {
            "schema_version": 1,
            "seq": 8,
            "timestamp": "2026-09-20T00:00:01Z",
            "type": "run_heartbeat",
            "session_id": session_id,
            "payload": {"internal_counter": "metadata-only-needle"},
        },
        {
            "schema_version": 1,
            "seq": 9,
            "timestamp": "2026-09-20T00:00:02Z",
            "type": "assistant_final_committed",
            "session_id": session_id,
            "payload": {"content": "clean answer"},
        },
    ]
    (session_dir / "events.jsonl").write_text(
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
        encoding="utf-8",
    )

    result = history_context(
        manager, session_id, action="search", scope="current", query="clean answer"
    )
    assert len(result["results"]) == 1
    assert result["results"][0]["content"] == "助手：clean answer"
    assert "timestamp" not in json.dumps(result, ensure_ascii=False)
    assert "schema_version" not in json.dumps(result, ensure_ascii=False)
    assert history_context(
        manager,
        session_id,
        action="search",
        scope="current",
        query="metadata-only-needle",
    )["results"] == []
    no_hit_with_source = history_context(
        manager,
        session_id,
        action="search",
        scope="current",
        query="metadata-only-needle",
        include_source=True,
    )
    assert no_hit_with_source["results"] == []
    assert no_hit_with_source["source_files"] == [str(session_dir / "events.jsonl")]

    read = history_context(
        manager,
        session_id,
        action="read",
        scope="current",
        ref=result["results"][0]["ref"],
    )
    assert read == {"content": "助手：clean answer"}


def test_history_context_is_registered_as_read_only_host_tool():
    import builtin_host_tools  # noqa: F401
    from agent_tools import OPENAI_TOOL_DEFINITIONS
    from host_tool_registry import host_tool_invokers

    names = [item["function"]["name"] for item in OPENAI_TOOL_DEFINITIONS]
    assert "history_context" in names
    assert host_tool_invokers.has("history_context")
    policy = host_tool_invokers.policy("history_context")
    assert policy.effect == "read"
    assert policy.parallel_safe is True
