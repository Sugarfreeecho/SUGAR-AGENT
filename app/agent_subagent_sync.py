"""Keep manually operated child sessions connected to their parent task."""

from __future__ import annotations

from datetime import datetime, timezone


async def publish_to_ancestors(manager, session_id: str, event: dict) -> None:
    from agent_subagent_events import tag_subagent_forward_event
    from session_event_bus import publish_session_event

    source_id = str(session_id)
    cursor = source_id
    seen = {cursor}
    direct_parent = ""
    while cursor:
        meta = manager._load_metadata(cursor)
        parent = str(meta.get("parent_session_id") or "") if meta.get("is_subagent") else ""
        if not parent or parent in seen:
            break
        direct_parent = direct_parent or parent
        seen.add(parent)
        forwarded = tag_subagent_forward_event(event, agent_id=source_id)
        forwarded.update(session_id=source_id, ephemeral=True)
        forwarded.setdefault("parent_session_id", direct_parent)
        await publish_session_event(parent, forwarded)
        cursor = parent


async def start_manual_subagent_run(manager, state: dict) -> None:
    sid = str(state.get("session_id") or "")
    load_metadata = getattr(manager, "_load_metadata", None)
    meta = load_metadata(sid) if callable(load_metadata) else {}
    parent = str(meta.get("parent_session_id") or "") if meta.get("is_subagent") else ""
    if not parent:
        return
    run_id = str(state.get("_runtime_v2_run_id") or "")
    state["_manual_subagent"] = {
        "parent_session_id": parent,
        "description": str(meta.get("subagent_description") or meta.get("name") or "subagent"),
        "subagent_type": str(meta.get("subagent_type") or "generalPurpose"),
    }
    now = datetime.now(timezone.utc).isoformat()
    manager.patch_subagent_metadata(sid, {
        "subagent_run_id": run_id, "subagent_run_status": "running",
        "subagent_run_started_at": now, "subagent_run_finished_at": "",
        "subagent_run_heartbeat_at": now, "subagent_run_error": "",
        "subagent_ok": None, "subagent_error": "", "result_preview": "",
    })
    manager.upsert_subagent_task(parent, sid, {
        "status": "running", "run_id": run_id, "started_at": now,
        "finished_at": "", "error": "", "result_preview": "",
    })
    await publish_to_ancestors(manager, sid, {
        "type": "subagent_start", "run_id": run_id, "resumed": True,
        **state["_manual_subagent"],
    })


async def finish_manual_subagent_run(manager, state: dict, terminal_event: dict) -> None:
    child = state.get("_manual_subagent")
    if not child or state.get("_manual_subagent_finished"):
        return
    sid = str(state["session_id"])
    run_id = str(state.get("_runtime_v2_run_id") or "")
    # A superseded writer must never overwrite the replacement run's outcome.
    if str(manager._load_metadata(sid).get("subagent_run_id") or "") != run_id:
        return
    from agent_subagent import _is_subagent_user_interrupt_final

    result = str(state.get("final_response") or "").strip()
    event_type = str(terminal_event.get("type") or "")
    interrupted = event_type == "run_interrupted" or _is_subagent_user_interrupt_final(result)
    error = str(terminal_event.get("error") or state.get("_run_error") or "")
    if interrupted:
        status, error = "interrupted", "interrupted"
    elif event_type == "run_failed" or error or state.get("react_limit_reached") or not result:
        status = "failed"
        error = error or ("max_react_iter" if state.get("react_limit_reached") else "missing_final")
    else:
        status = "completed"
    body = result or f"Error: {error}"
    now = datetime.now(timezone.utc).isoformat()
    output_file = manager.write_subagent_output(sid, body)
    manager.patch_subagent_metadata(sid, {
        "subagent_run_status": status, "subagent_run_finished_at": now,
        "subagent_run_error": error, "subagent_ok": status == "completed",
        "subagent_error": error, "result_preview": body[:1200],
    })
    parent = child["parent_session_id"]
    manager.upsert_subagent_task(parent, sid, {
        "status": status, "run_id": run_id, "finished_at": now,
        "error": error, "result_preview": body[:1200], "output_file": output_file,
    })
    manager.append_pending_subagent_result(parent, {
        "agent_id": sid, "run_id": run_id, **child, "status": status,
        "result": body, "error": error, "output_file": output_file,
        "finished_at": now, "parent_run_id": "",
    })
    state["_manual_subagent_finished"] = True
    await publish_to_ancestors(manager, sid, {
        "type": "subagent_finish", "run_id": run_id, **child,
        "ok": status == "completed", "status": status, "error": error,
        "result_preview": body[:1200],
    })
