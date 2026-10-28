"""The activity capsule must use the same ownership and live-job facts as the sidebar."""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def capsule_api(tmp_path, monkeypatch):
    from execution_services import jobs
    from plugins import load_plugin
    import plugins.host as hosts

    index = {"child": "root", "grandchild": "child", "other-child": "other",
             "cycle-a": "cycle-b", "cycle-b": "cycle-a"}
    owners = {"root", "child", "grandchild", "other", "other-child"}
    for owner in owners:
        (tmp_path / owner).mkdir()
    manager = SimpleNamespace(_load_subagent_index=lambda: index,
        _load_metadata_unlocked=lambda owner: {"name": "Name " + owner},
        _resolve_session_path=lambda owner: tmp_path / owner)
    service = jobs.ExecutionService(manager)
    recovered = []

    async def recover(owner):
        recovered.append(owner)

    async def persist(*args):
        pass

    async def call(operation, *args, **kwargs):
        return await operation(*args, **kwargs)

    monkeypatch.setattr(service, "recover", recover)
    monkeypatch.setattr(service, "persist", persist)
    monkeypatch.setattr(service, "call", call)
    for number, (owner, visible, status, kind) in enumerate([
        ("root", True, "running", "process"),
        ("grandchild", True, "stopping", "pty-send"),
        ("child", True, "running", "process"),
        ("root", False, "running", "process"),
        ("root", True, "completed", "process"),
        ("child", True, "failed", "process"),
        ("other-child", True, "running", "process"),
        ("cycle-a", True, "running", "process"),
    ]):
        job = jobs.Job(f"{number:032x}", owner, kind, "job " + str(number), visible=visible,
                       status=status, started_at=100 - number)
        job.output.append(b"hello output")
        service.jobs[job.id] = job

    plugin = load_plugin(ROOT / "plugins/execution-tools")
    module = hosts._module(plugin)
    monkeypatch.setattr(module, "execution_service", lambda manager: service)
    monkeypatch.setattr(hosts, "bundled_host_plugin_enabled", lambda identifier: True)
    app = FastAPI()
    module.install(app, {"session_manager": manager}, plugin)
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, service=service, manager=manager, recovered=recovered)


def test_active_subtree_matches_background_counts_and_does_not_recover_history(capsule_api, monkeypatch):
    import agent_subagent
    from execution_services import jobs
    from session_activity import background_work_snapshot

    c = capsule_api
    monkeypatch.setattr(jobs, "_SERVICE", c.service)
    monkeypatch.setattr(agent_subagent, "subagent_registry", SimpleNamespace(running_runs=lambda: {}))
    monkeypatch.setattr("session_lifecycle.is_run_active", lambda sid: False)
    result = c.client.get('/sessions/root/jobs?include_descendants=true&active_only=true')
    assert result.status_code == 200
    rows = result.json()["jobs"]
    assert [row["owner_session_id"] for row in rows] == ["child", "grandchild", "root"]
    assert [row["owner_label"] for row in rows] == ["Name child", "Name grandchild", "Name root"]
    assert len(rows) == background_work_snapshot(c.manager)["root"]["background_jobs_running"] == 3
    assert c.recovered == []
    assert all(row["status"] in jobs.ACTIVE for row in rows)


def test_child_only_includes_its_subtree_and_default_endpoint_is_compatible(capsule_api):
    c = capsule_api
    rows = c.client.get('/sessions/child/jobs?include_descendants=true&active_only=true').json()["jobs"]
    assert {row["owner_session_id"] for row in rows} == {"child", "grandchild"}
    rows = c.client.get('/sessions/root/jobs').json()["jobs"]
    assert [row["status"] for row in rows] == ["running", "completed"]
    assert all("owner_session_id" not in row for row in rows)
    assert c.recovered == ["root"]
    rows = c.client.get('/sessions/root/jobs?active_only=true').json()["jobs"]
    assert len(rows) == 1


def test_output_is_non_consuming_and_stop_requires_the_real_owner(capsule_api):
    c = capsule_api
    identifier = f"{2:032x}"
    assert c.client.get(f'/sessions/root/jobs/{identifier}/output').status_code == 404
    headers = {"Origin": "http://testserver"}
    assert c.client.post(f'/sessions/root/jobs/{identifier}/kill', headers=headers, json={}).status_code == 404
    result = c.client.get(f'/sessions/child/jobs/{identifier}/output?offset=0').json()
    assert result["text"] == "hello output"
    assert c.service.jobs[identifier].output.cursor == 0
    result = c.client.post(f'/sessions/child/jobs/{identifier}/kill', headers=headers, json={})
    assert result.status_code == 200, result.text
    assert result.json()["job"]["status"] == "stopping"
    assert c.service.jobs[f"{0:032x}"].status == "running"
    assert c.client.get('/sessions/missing/jobs?include_descendants=true&active_only=true').status_code == 404


def test_finished_tasks_disappear_and_subagent_cycles_terminate(capsule_api):
    c = capsule_api
    for job in c.service.jobs.values():
        job.status = "completed"
    result = c.client.get('/sessions/root/jobs?include_descendants=true&active_only=true')
    assert result.json() == {"jobs": []}
    assert c.recovered == []
