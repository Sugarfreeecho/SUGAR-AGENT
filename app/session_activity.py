"""Live background work attributed to its session and visible ancestors."""
from __future__ import annotations


def background_work_snapshot(manager, *, subagent_index=None) -> dict[str, dict[str, int]]:
    from agent_subagent import subagent_registry
    from execution_services import jobs
    from session_lifecycle import is_run_active

    if subagent_index is None:
        load_index = getattr(manager, "_load_subagent_index", None)
        subagent_index = load_index() if callable(load_index) else {}
    activity = {}

    def ancestors(owner):
        seen = {owner}
        while owner in subagent_index:
            owner = subagent_index[owner]
            if owner in seen:
                break
            seen.add(owner)
            yield owner

    def add(owner, field):
        counts = activity.setdefault(owner, {"background_jobs_running": 0, "subagent_running": 0})
        counts[field] += 1

    running_children = set(subagent_registry.running_runs())
    running_children.update(child for child in subagent_index if is_run_active(child))
    for child in running_children:
        for parent in ancestors(child):
            add(parent, "subagent_running")
    service = jobs._SERVICE
    if service is not None and service.manager is manager:
        # Copy before iterating: the execution loop owns job insertion/removal.
        for job in tuple(service.jobs.values()):
            if job.visible and job.status in jobs.ACTIVE:
                add(job.owner, "background_jobs_running")
                for parent in ancestors(job.owner):
                    add(parent, "background_jobs_running")
    return activity


def attach_background_work(summary: dict, activity: dict) -> None:
    counts = activity.get(str(summary.get("id") or ""), {})
    summary["background_jobs_running"] = counts.get("background_jobs_running", 0)
    summary["subagent_running"] = counts.get("subagent_running", 0)
    if any(counts.values()) and summary.get("unread_result_status") != "failed":
        summary["unread_result"] = False
