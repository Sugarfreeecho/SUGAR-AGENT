import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

def test_worker_session_event_reaches_initialized_server_loop(monkeypatch):
    import webui

    async def scenario():
        scheduled = []
        monkeypatch.setattr(webui, "_UI_ATTENTION_MAIN_LOOP", None)
        monkeypatch.setattr(
            webui,
            "_schedule_ui_attention_notify",
            lambda session_id, reason: scheduled.append((session_id, reason)),
        )

        webui.initialize_ui_attention_notifications()
        await asyncio.to_thread(
            webui._on_session_event_for_attention_notify,
            "session-1",
            {"type": "run_finished"},
        )
        await asyncio.sleep(0)

        assert webui._UI_ATTENTION_MAIN_LOOP is asyncio.get_running_loop()
        assert scheduled == [("session-1", "completed")]

    asyncio.run(scenario())


def test_attention_listener_ignores_unrelated_and_forwarded_events(monkeypatch):
    import webui

    async def scenario():
        scheduled = []
        monkeypatch.setattr(webui, "_UI_ATTENTION_MAIN_LOOP", asyncio.get_running_loop())
        monkeypatch.setattr(
            webui,
            "_schedule_ui_attention_notify",
            lambda session_id, reason: scheduled.append((session_id, reason)),
        )

        webui._on_session_event_for_attention_notify("session-1", {"type": "status"})
        webui._on_session_event_for_attention_notify(
            "session-1",
            {"type": "run_finished", "_subagent_forward": True},
        )
        await asyncio.sleep(0)

        assert scheduled == []

    asyncio.run(scenario())


def test_notification_context_contains_status_session_and_latest_question(monkeypatch):
    import webui

    monkeypatch.setattr(
        webui.session_manager,
        "get_session_summary",
        lambda session_id: {
            "id": session_id,
            "name": "提醒优化",
            "last_user_preview": "托盘能否复用已有页面？",
        },
    )

    title, message = webui._notification_context("session-1", "completed")

    assert title == "SugarAgent"
    assert "状态：已完成" in message
    assert "会话：提醒优化" in message
    assert "最近问题：托盘能否复用已有页面？" in message


def test_pending_notification_context_includes_count(monkeypatch):
    import webui

    monkeypatch.setattr(webui.session_manager, "get_session_summary", lambda _sid: {})

    _title, message = webui._notification_context("session-1", "pending", 2)

    assert "状态：待处理（2 项）" in message
    assert "会话：未命名会话" in message
    assert "最近问题：暂无" in message


def test_runtime_status_reports_busy_when_any_session_is_running(monkeypatch):
    import webui

    monkeypatch.setattr(
        webui.session_manager,
        "index",
        [{"id": "idle"}, {"id": "running"}],
    )
    monkeypatch.setattr(
        webui,
        "_session_run_state_fields_light",
        lambda sid: {"run_active": sid == "running"},
    )

    payload = webui._runtime_status_payload()

    assert payload["status"] == "busy"
    assert payload["active_run_count"] == 1


def _patch_runtime_status_probes(monkeypatch, runs):
    import webui

    import cpu_pressure
    import runtime_observability

    monkeypatch.setattr(webui.session_manager, "index", [{"id": "session-1"}])
    monkeypatch.setattr(
        webui,
        "_session_run_state_fields_light",
        lambda _sid: {"run_active": False},
    )
    monkeypatch.setattr(
        cpu_pressure,
        "snapshot",
        lambda: type("CpuSnapshot", (), {"mode": "ok"})(),
    )
    monkeypatch.setattr(
        runtime_observability,
        "snapshot",
        lambda _sid: {"runs": runs},
    )


def _run_row(run_id, status, *, resolved=False, finished_at="2026-01-01T00:00:00Z"):
    row = {"run_id": run_id, "status": status, "finished_at": finished_at}
    if resolved:
        row["resolved"] = True
    return row


def test_runtime_status_alert_while_manual_pause_unresolved(monkeypatch):
    import webui

    _patch_runtime_status_probes(monkeypatch, [_run_row("run-1", "interrupted")])

    payload = webui._runtime_status_payload()

    assert payload["status"] == "alert"


def test_runtime_status_online_after_manual_pause_residue_deleted(monkeypatch):
    import webui

    _patch_runtime_status_probes(
        monkeypatch, [_run_row("run-1", "interrupted", resolved=True)]
    )

    payload = webui._runtime_status_payload()

    assert payload["status"] == "online"


def test_runtime_status_online_when_newer_run_finished(monkeypatch):
    import webui

    _patch_runtime_status_probes(
        monkeypatch,
        [
            _run_row("run-1", "interrupted", finished_at="2026-01-01T00:00:00Z"),
            _run_row("run-2", "finished", finished_at="2026-01-01T01:00:00Z"),
        ],
    )

    payload = webui._runtime_status_payload()

    assert payload["status"] == "online"


def test_runtime_status_alert_when_latest_run_failed(monkeypatch):
    import webui

    _patch_runtime_status_probes(monkeypatch, [_run_row("run-1", "failed")])

    payload = webui._runtime_status_payload()

    assert payload["status"] == "alert"


def test_mark_runs_resolved_persists_and_is_idempotent(tmp_path, monkeypatch):
    import runtime_observability

    monkeypatch.setattr(runtime_observability, "_path_resolver", None)
    monkeypatch.setattr(runtime_observability, "_sessions_root", tmp_path)
    runtime_observability._cache.clear()
    runtime_observability._flush_timers.clear()
    try:
        runtime_observability.start_run("session-resolve", "run-1", kind="chat")
        runtime_observability.finish_run("session-resolve", "run-1", "interrupted")

        marked = runtime_observability.mark_runs_resolved("session-resolve")

        assert marked == 1
        snap = runtime_observability.snapshot("session-resolve")
        assert snap["runs"][0]["resolved"] is True
        assert snap["runs"][0]["resolved_at"]

        assert runtime_observability.mark_runs_resolved("session-resolve") == 1
        assert runtime_observability.snapshot("session-resolve")["runs"][0]["resolved"] is True
    finally:
        runtime_observability._cache.clear()
        runtime_observability._flush_timers.clear()


def test_ui_presence_reuse_requires_recent_heartbeat(monkeypatch):
    import webui

    monkeypatch.setattr(
        webui,
        "_ui_presence_tokens",
        {
            "fresh": {"seen_at": 95.0, "active": False},
            "stale": {"seen_at": 1.0, "active": True},
        },
    )

    assert webui._ui_presence_has_reusable(100.0) is True
    assert webui._ui_presence_has_reusable(120.0) is False
