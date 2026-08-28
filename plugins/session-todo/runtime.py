"""Long-run reminder policy owned by the optional Todo workflow."""


def initialize(host_module):
    def initialize_state(state, _prior_messages=None):
        host_module.session_plan_store.sync_session_from_key_context(
            state["session_id"], state.get("key_context", "") or ""
        )

    def migrate_key_context(session_id, key_context):
        return host_module.session_manager.migrate_todo_plan_off_key_context(
            session_id, key_context
        )

    def context_changed(state):
        host_module.session_plan_store.sync_session_from_key_context(
            state["session_id"], state.get("key_context", "") or ""
        )

    def after_run(state):
        manager = host_module.session_plan_store
        if not manager.has_active_plan(state["session_id"]):
            return
        items = manager._by_session.get(state["session_id"], [])
        if items and all(item.get("status") == "completed" for item in items):
            manager._by_session[state["session_id"]] = []
            if not host_module._runtime_v2_is_primary():
                host_module.session_manager.save_todo_plan(state["session_id"], "")
    def before_round(state):
        rounds = int(state.get("_todo_rounds_since_update", 0) or 0)
        rounds = rounds + 1 if host_module.session_plan_store.has_active_plan(state["session_id"]) else 0
        state["_todo_rounds_since_update"] = rounds
        if rounds < 25 or (rounds - 25) % 5:
            return None
        return {
            "message": host_module.SystemMessage(content=(
                "[Session plan reminder]\nThe plan has not been updated for "
                f"{rounds} model rounds. Update it now if progress changed."
            )),
            "status": f"Session plan has not been updated for {rounds} rounds; reminder inserted",
        }
    return {
        "before_round": before_round,
        "initialize_state": initialize_state,
        "migrate_key_context": migrate_key_context,
        "context_changed": context_changed,
        "after_run": after_run,
    }
