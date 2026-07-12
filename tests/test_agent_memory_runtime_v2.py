import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _fail_legacy(*_args, **_kwargs):
    raise AssertionError("Runtime V2 context policy must not touch legacy key_context sidecars")


def test_v2_compress_summary_uses_in_memory_context_not_legacy(monkeypatch):
    import agent_memory

    saved = []
    merged_inputs = []
    monkeypatch.setattr(agent_memory, "_runtime_v2_primary", lambda: True)
    monkeypatch.setattr(agent_memory.session_manager, "load_key_context", _fail_legacy)
    monkeypatch.setattr(agent_memory.session_manager, "save_key_context", _fail_legacy)
    monkeypatch.setattr(agent_memory.session_manager, "append_key_context_history", _fail_legacy)
    monkeypatch.setattr(agent_memory, "_save_active_key_context", lambda sid, text: saved.append((sid, text)))
    monkeypatch.setattr(
        agent_memory,
        "merge_compress_summary_into_key_context",
        lambda existing, summary: merged_inputs.append((existing, summary)) or (existing + "\n" + summary),
    )

    merged = agent_memory._upsert_compress_summary_key_context(
        "s1",
        "new summary",
        current_key_context="existing facts",
    )

    assert "existing facts" in merged
    assert "new summary" in merged
    assert merged_inputs == [("existing facts", "new summary")]
    assert saved == [("s1", merged)]


def test_v2_edit_key_context_uses_supplied_snapshot_and_v2_save(monkeypatch):
    import agent_memory

    saved = []
    monkeypatch.setattr(agent_memory, "_runtime_v2_primary", lambda: True)
    monkeypatch.setattr(agent_memory.session_manager, "load_key_context", _fail_legacy)
    monkeypatch.setattr(agent_memory.session_manager, "save_key_context", _fail_legacy)
    monkeypatch.setattr(agent_memory.session_manager, "append_key_context_history", _fail_legacy)
    monkeypatch.setattr(agent_memory, "load_prompt_template", lambda _name: "{current}\n{instruction}")
    monkeypatch.setattr(
        agent_memory,
        "executor_text_complete",
        lambda _prompt, session_id="": "<key_context>updated v2 facts</key_context>",
    )
    monkeypatch.setattr(agent_memory, "_save_active_key_context", lambda sid, text: saved.append((sid, text)))

    new_doc, message = agent_memory.run_edit_key_context_instruction(
        "s1",
        "update it",
        current_key_context="snapshot facts",
    )

    assert new_doc == "updated v2 facts"
    assert saved == [("s1", "updated v2 facts")]
    assert "已按说明更新" in message


def test_v2_compression_prefix_backup_is_guarded_from_legacy_sidecar():
    source = (APP_DIR / "agent_memory.py").read_text(encoding="utf-8")
    position = source.rfind("session_manager.backup_llm_compress_prefix")

    assert position > 0
    assert "if not _runtime_v2_primary():" in source[position - 300:position]
