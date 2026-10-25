import asyncio
import base64
import json
import sys
import threading
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace

import httpx
import pytest

from tests.test_sugar_bili_scroll_tasks import host


BV1 = "BV1aEnA6JECB"
BV2 = "BV19Rn26CExe"
BV3 = "BV1tsnv6vEyT"


@pytest.fixture
def runtime(host, monkeypatch):
    # Import the real runner before installing the isolated session facade.
    import agent_loop  # noqa: F401
    import agent_mcp
    async def ready():
        pass
    monkeypatch.setattr(agent_mcp, "ensure_started", ready)
    monkeypatch.setattr(agent_mcp, "list_configured_servers", lambda: [
        {"server": "sugar-bili-scroll/bili", "connected": True}])
    cfg = {"daily_quota": 3, "inbound_reply": True, "inbound_public_reply": True,
           "inbound_dm_public_comment": True, "inbound_whitelist": "100 好友", "inbound_channels": "all",
           "inbound_cooldown_minutes": 0, "inbound_max_per_hour": 20}
    monkeypatch.setattr(host, "_settings", lambda *args: dict(cfg))
    sessions, calls = {}, []

    def create(*args, **kwargs):
        sid = "session-"+str(len(sessions)+1)
        sessions[sid] = kwargs
        return (sid, None)

    manager = SimpleNamespace(get_session_summary=lambda sid: sessions.get(sid),
        get_or_create_session=create, set_session_name=lambda *args: None,
        set_session_system_context=lambda sid, text, **kw: sessions[sid].update(system_context=text, system_context_mode=kw.get("mode", "append")),
        _load_metadata=lambda sid: sessions.get(sid, {}), is_interrupt_requested=lambda *args: False)
    monkeypatch.setitem(sys.modules, "agent_harness", SimpleNamespace(session_manager=manager))

    async def reply(home, bvid, text, rpid=0, root=0, picture=None):
        calls.append(("comment", bvid, text, rpid, root, picture))
        return {"success": True, "rpid": 123}

    async def dm(home, uid, text):
        calls.append(("dm", uid, text))
        return {"success": True}

    monkeypatch.setattr(host, "bili_client", SimpleNamespace(load_credential=lambda home: SimpleNamespace(dedeuserid="999"),
        dumps=lambda data: json.dumps(data, ensure_ascii=False), reply=reply, send_message=dm))
    return SimpleNamespace(h=host, flow=host._flow(), cfg=cfg, sessions=sessions, calls=calls)


def event(key="dm:100:1", uid="100", channel="dm", bvid=BV1, rpid=11, root=10, text="你好"):
    return {"key": key, "uid": uid, "channel": channel, "nickname": "访客", "text": text,
            "target": {"kind": "dm" if channel == "dm" else "comment", "uid": uid, "bvid": bvid, "rpid": rpid, "root": root}}


def enqueue(rt, ev):
    rt.flow.store.poll_commit({"bootstrapped": True, "dm": {}, "at": {}, "reply": {}}, [ev])
    assert rt.flow.store.claim(ev["key"])
    return rt.flow.store.job(ev["key"])


def test_tasks_have_independent_quota_reports_and_schedule(runtime, monkeypatch):
    rt, h = runtime, runtime.h
    rows = [h.tasks_mod.new_row(name="A", daily_quota=1, valley_windows="00:00-23:59"),
            h.tasks_mod.new_row(name="B", daily_quota=2, valley_windows="00:00-23:59")]
    h.tasks_mod.save(h._home(), rows)
    identifiers = iter([BV1, BV2])

    def run(*args, **kwargs):
        result = rt.flow.record(kwargs["policy"], {"bvid": next(identifiers), "picked": True, "reason": "值得看"})
        assert result["ok"]
        return {"ok": True}

    monkeypatch.setattr(h, "_run_round_blocking", run)
    assert h.run_once(task_id=rows[0]["id"])["picked_today"] == 1
    assert rt.flow.summary(rows[1])["picked_today"] == 0
    assert h.duty.last_round_at(rt.flow.task_home(rows[1])) is None
    assert h.run_once(task_id=rows[0]["id"])["code"] == "quota_exhausted"
    assert h.run_once(task_id=rows[1]["id"])["picked_today"] == 1
    assert BV2 not in h.duty.report_file(rt.flow.task_home(rows[0])).read_text(encoding="utf-8")
    assert BV1 not in h.duty.report_file(rt.flow.task_home(rows[1])).read_text(encoding="utf-8")
    assert {BV1, BV2} <= h.duty.seen_bvids(h._home())


def test_quota_remains_enforced_when_reports_are_off(runtime):
    rt = runtime
    row = rt.h.tasks_mod.new_row(report_level="off", daily_quota=1)
    rt.h.tasks_mod.save(rt.h._home(), [row])
    policy = {"mode": "duty", "task_id": row["id"]}
    assert rt.flow.record(policy, {"bvid": BV1, "picked": True})["ok"]
    assert not rt.flow.record(policy, {"bvid": BV2, "picked": True})["ok"]
    assert not rt.h.duty.report_file(rt.flow.task_home(row)).exists()
    assert rt.flow.summary(row)["picked_today"] == 1


def test_global_dedup_rejects_another_tasks_pick(runtime):
    rt = runtime
    a, b = rt.h.tasks_mod.new_row(), rt.h.tasks_mod.new_row()
    rt.h.tasks_mod.save(rt.h._home(), [a, b])
    assert rt.flow.record({"mode": "duty", "task_id": a["id"]}, {"bvid": BV1, "picked": False})["ok"]
    assert not rt.flow.record({"mode": "duty", "task_id": b["id"]}, {"bvid": BV1, "picked": True})["ok"]


def test_legacy_facts_are_imported_only_into_original_task(runtime):
    rt, h = runtime, runtime.h
    old = h.tasks_mod.new_row(name="默认任务", session_id="legacy")
    other = h.tasks_mod.new_row(name="其他")
    h.tasks_mod.save(h._home(), [old, other])
    rt.cfg["duty_session_id"] = "legacy"
    h.duty.report_file(h._home()).write_text("### "+BV1+"\n", encoding="utf-8")
    h.duty.note_round(h._home(), picked=1)
    h._task_rows()
    assert rt.flow.summary(old)["picked_today"] == 1
    assert rt.flow.summary(other)["picked_today"] == 0
    assert rt.flow.record({"mode": "duty", "task_id": old["id"]}, {"bvid": BV2, "picked": True})["ok"]
    assert rt.flow.summary(old)["picked_today"] == 2


def tool_context(run_id, name, sid="s"):
    return SimpleNamespace(run_id=run_id, session_id=sid, service=lambda key: name)


def test_strangers_have_zero_tools_and_calls_are_rejected(runtime):
    rt = runtime
    policy = {"mode": "dm", "uid": "200"}
    assert rt.flow.allowed(policy) == []
    rt.flow.store.start_run("bili-dm-x", "s", policy)
    outcome = asyncio.run(rt.h._invoke(tool_context("bili-dm-x", "bili_reply"), {"bvid": BV1, "text": "x"}))
    assert outcome.kind.value == "failed"
    assert rt.calls == []


def test_comment_target_is_pinned_and_independent_of_duty_switch(runtime):
    rt = runtime
    policy = {"mode": "reply", "uid": "100", "job_key": "at:1", "target": {"bvid": BV1, "rpid": 11, "root": 10}}
    rt.flow.store.start_run("bili-reply-x", "s", policy)
    bad = asyncio.run(rt.h._invoke(tool_context("bili-reply-x", "bili_reply"), {"bvid": BV2, "text": "wrong"}))
    assert bad.kind.value == "failed" and rt.calls == []
    good = asyncio.run(rt.h._invoke(tool_context("bili-reply-x", "bili_reply"), {"bvid": BV1, "text": "right"}))
    assert good.kind.value == "completed"
    assert rt.calls[0][1:5] == (BV1, "right", 11, 10)


def test_whitelisted_dm_can_comment_on_requested_video(runtime):
    rt = runtime
    rt.flow.store.start_run("bili-dm-x", "s", {"mode": "dm", "uid": "100"})
    outcome = asyncio.run(rt.h._invoke(tool_context("bili-dm-x", "bili_reply"), {"bvid": BV2, "text": "受托评论"}))
    assert outcome.kind.value == "completed"
    assert rt.calls[0][1] == BV2


def test_revoking_whitelist_blocks_already_visible_tools(runtime):
    rt = runtime
    rt.flow.store.start_run("bili-dm-x", "s", {"mode": "dm", "uid": "100"})
    rt.cfg["inbound_whitelist"] = ""
    outcome = asyncio.run(rt.h._invoke(tool_context("bili-dm-x", "bili_reply"), {"bvid": BV1, "text": "x"}))
    assert outcome.kind.value == "failed" and not rt.calls


def test_cursors_and_jobs_are_committed_together_and_deduplicated(runtime):
    rt = runtime
    state = {"bootstrapped": True, "at": {"id": 8, "ts": 10}}
    rt.flow.store.poll_commit(state, [event("at:8", channel="at")])
    rt.flow.store.note_sent("100")
    rt.flow.store.poll_commit(state, [event("at:8", channel="at")])
    assert len(rt.flow.store.jobs()) == 1
    saved = rt.flow.store.get("inbound")
    assert saved["at"]["id"] == 8 and len(saved["recent"]) == 1


def test_ambiguous_send_is_not_retried_after_restart(runtime, monkeypatch):
    rt = runtime
    ev = event()
    enqueue(rt, ev)

    async def timeout(*args):
        raise TimeoutError("connection lost")

    monkeypatch.setattr(rt.h.bili_client, "send_message", timeout)
    rt.flow.store.annotate(ev["key"], {"reply_key": "send-1"})
    with pytest.raises(TimeoutError):
        asyncio.run(rt.flow.send("send-1", ev["key"], "r", "dm", {"uid": "100"}, "hello"))
    rt.flow.store.recover()
    assert rt.flow.store.job(ev["key"])["status"] == "unknown"
    assert not rt.flow.store.retry(ev["key"])
    assert rt.flow.store.resolve(ev["key"], False)
    assert rt.flow.store.job(ev["key"])["status"] == "pending"


def test_dm_forwards_complete_reply_rows_without_final_duplicates(runtime, monkeypatch):
    rt = runtime

    def run(*args, on_event, **kwargs):
        async def emit():
            for row in [
                {"type": "llm_reasoning", "content": "private reasoning"},
                {"type": "llm_response", "content": "partial", "execution_status": "interrupted"},
                {"type": "llm_response", "content": "hello", "react_iter": 1},
                {"type": "final", "content": "hello"}]:
                await on_event(row)
        asyncio.run(emit())
        return {"ok": True}

    monkeypatch.setattr(rt.h, "_run_round_blocking", run)
    job = enqueue(rt, event(uid="200"))
    rt.flow.process(job)
    assert rt.calls == [("dm", 200, "hello")]
    assert rt.flow.store.job(job["key"])["status"] == "sent"


@pytest.mark.parametrize("earlier_short", [False, True])
def test_long_dm_fails_whole_round_without_sending_or_retry(runtime, monkeypatch, earlier_short):
    rt, body = runtime, "好"*501

    def run(*args, on_event, **kwargs):
        async def emit():
            if earlier_short:
                await on_event({"type": "llm_response", "react_iter": 1, "content": "先查到了资料"})
            await on_event({"type": "final", "content": body})
        asyncio.run(emit())
        return {"ok": True}

    monkeypatch.setattr(rt.h, "_run_round_blocking", run)
    job = enqueue(rt, event())
    rt.flow.process(job)
    saved = rt.flow.store.job(job["key"])
    assert rt.calls == [] and rt.flow.store.deliveries(job_key=job["key"]) == []
    assert saved["status"] == "failed" and "超过500字" in saved["error"]
    assert saved["result"]["permanent"]


def test_same_comment_thread_reuses_session_and_stranger_has_no_tools(runtime, monkeypatch):
    rt = runtime
    seen = []

    def run(prompt, sid, run_id, **kwargs):
        seen.append((sid, kwargs["allow"], prompt))
        return {"ok": True, "finals": ["你好"]}

    monkeypatch.setattr(rt.h, "_run_round_blocking", run)
    for ev in [event("at:1", "200", "at"), event("reply:2", "200", "reply", rpid=12), event("at:3", "200", "at", root=20)]:
        rt.flow.process(enqueue(rt, ev))
    assert seen[0][0] == seen[1][0] != seen[2][0]
    assert all(allow == [] for _, allow, _ in seen)
    assert "rpid=12" in seen[1][2]
    assert len(rt.calls) == 3


def test_white_comment_without_tool_send_has_no_fallback(runtime, monkeypatch):
    rt = runtime
    monkeypatch.setattr(rt.h, "_run_round_blocking", lambda *a, **kw: {"ok": True, "finals": ["这段不应代发"]})
    job = enqueue(rt, event("at:1", "100", "at"))
    rt.flow.process(job)
    assert rt.calls == []
    assert rt.flow.store.job(job["key"])["status"] == "skipped"


def test_new_dm_is_steered_into_existing_run(runtime, monkeypatch):
    rt, started, release = runtime, threading.Event(), threading.Event()
    steers, runs = [], []
    monkeypatch.setitem(sys.modules, "agent_loop", SimpleNamespace(
        enqueue_session_steer=lambda sid, text, **kw: steers.append((sid, text, kw)) or {"ok": True},
        remove_session_steer=lambda *a, **kw: {"ok": True}))

    def run(prompt, sid, run_id, on_event, **kwargs):
        runs.append(sid)
        started.set()
        assert release.wait(5)
        async def emit():
            await on_event({"type": "user_steer", "client_id": steers[0][2]["client_id"]})
            await on_event({"type": "final", "content": "收到两条"})
        asyncio.run(emit())
        return {"ok": True}

    monkeypatch.setattr(rt.h, "_run_round_blocking", run)

    async def scenario():
        rt.flow.store.poll_commit({"bootstrapped": True}, [event()])
        await rt.flow.dispatch()
        assert await asyncio.to_thread(started.wait, 3)
        rt.flow.store.poll_commit({"bootstrapped": True}, [event("dm:100:2", text="再问一句")])
        await rt.flow.dispatch()
        release.set()
        await asyncio.gather(*rt.flow.workers.values())

    asyncio.run(scenario())
    assert len(runs) == 1 and len(steers) == 1
    assert steers[0][2]["mode"] == "append"
    assert rt.flow.store.job("dm:100:2")["status"] == "sent"
    assert len(rt.calls) == 1


def test_run_counters_survive_a_new_store_instance(runtime):
    rt = runtime
    rt.flow.store.start_run("r", "s", {})
    assert rt.flow.store.reserve("r", "pictures", 1)
    cold = rt.h.store_mod.Store(rt.h._home())
    assert not cold.reserve("r", "pictures", 1)
    assert [cold.reserve("r", "emotes", 3) for _ in range(4)] == [True, True, True, False]


def test_log_rotation_is_bounded(runtime, monkeypatch):
    h = runtime.h
    monkeypatch.setattr(h.duty, "LOG_MAX_BYTES", 1)
    for _ in range(8):
        h.duty.log(h._home(), "entry")
    assert len(list(h._home().glob("duty.log*"))) == 4


@pytest.fixture
def api(runtime, monkeypatch):
    from fastapi import FastAPI
    import plugins.storage
    app, rt = FastAPI(), runtime
    home = rt.h._home()
    monkeypatch.setattr(plugins.storage, "plugin_storage_layout", lambda pid: SimpleNamespace(data_dir=home))
    rt.h.bili_client.credential_path = lambda root: root / "credential.json"
    monkeypatch.setattr(rt.h, "asr", SimpleNamespace(ready=lambda engine: {"ready": True}))
    rt.h.tasks_mod.save(home, [])
    rt.h.install(app, {}, rt.h._runtime["plugin"])
    return rt, app


def test_task_http_crud_statistics_and_report(api):
    rt, app = api

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver", headers={"origin": "http://testserver"}) as client:
            bad = await client.post("/api/sugar-bili-scroll/tasks", json={"daily_quota": -1})
            assert bad.status_code == 400
            bad = await client.post("/api/sugar-bili-scroll/tasks", json={"valley_windows": "bad"})
            assert bad.status_code == 400
            created = await client.post("/api/sugar-bili-scroll/tasks", json={"name": "教程", "daily_quota": 2})
            assert created.status_code == 200
            row = created.json()["item"]
            assert row["picked_today"] == 0
            rt.flow.record({"mode": "duty", "task_id": row["id"]}, {"bvid": BV1, "picked": True, "title": "教程标题"})
            listed = (await client.get("/api/sugar-bili-scroll/tasks")).json()["items"]
            assert listed[0]["picked_today"] == 1 and listed[0]["remaining"] == 1
            report = await client.get("/api/sugar-bili-scroll/report", params={"task_id": row["id"]})
            assert "教程标题" in report.json()["text"]
            assert (await client.get("/api/sugar-bili-scroll/report", params={"day": "../../bad"})).status_code == 400
            assert (await client.post("/api/sugar-bili-scroll/tasks/missing/run")).status_code == 404
            assert (await client.patch("/api/sugar-bili-scroll/tasks/"+row["id"], json={"enabled": False})).status_code == 200
            assert (await client.post("/api/sugar-bili-scroll/tasks/"+row["id"]+"/run")).status_code == 400
            assert (await client.delete("/api/sugar-bili-scroll/tasks/"+row["id"])).status_code == 200
            assert (await client.get("/api/sugar-bili-scroll/tasks")).json()["items"] == []
            assert (await client.post("/api/sugar-bili-scroll/tasks", headers={"origin": "http://foreign.example"}, json={})).status_code == 403

    asyncio.run(scenario())


def test_inbound_poll_persists_equal_timestamp_events_and_dry_run_does_not_advance(runtime, monkeypatch):
    rt, h = runtime, runtime.h
    state = {"bootstrapped": True, "at": {"id": 1, "ts": 10}, "dm": {}, "reply": {"id": 0, "ts": 0}}
    h.inbound.save_state(h._home(), state)

    async def get_at(**kwargs):
        return {"items": [{"id": n, "at_time": 10, "user": {"mid": 200}, "item": {
            "uri": "https://www.bilibili.com/video/"+BV1, "source_id": n+10, "root_id": 10, "source_content": "hello"}} for n in (3, 2)]}

    monkeypatch.setitem(sys.modules, "bilibili_api", SimpleNamespace(session=SimpleNamespace(get_at=get_at)))
    dry = asyncio.run(h.inbound.poll(h._home(), object(), "999", ["at"], dry_run=True))
    assert [ev["key"] for ev in dry["events"]] == ["999:at:2", "999:at:3"]
    assert rt.flow.store.get("inbound")["at"]["id"] == 1
    assert rt.flow.store.jobs() == []
    real = asyncio.run(h.inbound.poll(h._home(), object(), "999", ["at"]))
    assert len(real["events"]) == len(rt.flow.store.jobs()) == 2
    assert rt.flow.store.get("inbound")["at"]["id"] == 3
    assert real["events"][0]["target"]["rpid"] == 12


def test_unknown_transport_result_stays_unknown(runtime, monkeypatch):
    rt = runtime
    job = enqueue(rt, event())

    async def uncertain(*args):
        return {"success": False, "uncertain": True, "error": "timeout"}

    monkeypatch.setattr(rt.h.bili_client, "send_message", uncertain)
    asyncio.run(rt.flow.send("ambiguous", job["key"], "r", "dm", {"uid": "100"}, "hello"))
    rt.flow.finish_job(job["key"], {}, "")
    assert rt.flow.store.job(job["key"])["status"] == "unknown"


def test_admission_limit_is_atomic_across_store_instances(runtime):
    rt = runtime
    assert rt.flow.store.admit("1", "100", 0, 1)
    cold = rt.h.store_mod.Store(rt.h._home())
    assert not cold.admit("2", "200", 0, 1)
    assert cold.admit("1", "100", 0, 1)


def test_crash_after_dm_receipt_does_not_generate_again(runtime):
    rt = runtime
    job = enqueue(rt, event())
    rt.flow.store.annotate(job["key"], {"reply_key": "receipt"})
    asyncio.run(rt.flow.send("receipt", job["key"], "r", "dm", {"uid": "100"}, "hello"))
    rt.flow.store.recover()
    assert rt.flow.store.job(job["key"])["status"] == "sent"


def test_task_switches_are_checked_again_at_execution(runtime):
    rt = runtime
    row = rt.h.tasks_mod.new_row(auto_comment=True, mention_name="主人")
    rt.h.tasks_mod.save(rt.h._home(), [row])
    policy = {"mode": "duty", "task_id": row["id"]}
    rt.flow.store.start_run("bili-duty-x", "s", policy)
    assert "bili_reply" in rt.flow.allowed(policy)
    rt.h.tasks_mod.update(rt.h._home(), row["id"], {"auto_comment": False})
    outcome = asyncio.run(rt.h._invoke(tool_context("bili-duty-x", "bili_reply"), {"bvid": BV1, "text": "不能发送"}))
    assert outcome.kind.value == "failed" and rt.calls == []


def test_send_limits_queue_reply_rows_without_regenerating(runtime, monkeypatch):
    rt, model_calls = runtime, []
    rt.cfg["inbound_cooldown_minutes"] = 1

    def run(*args, on_event, **kwargs):
        model_calls.append(1)
        async def emit():
            await on_event({"type": "llm_response", "react_iter": 1, "content": "第一条"})
            await on_event({"type": "final", "content": "第二条"})
        asyncio.run(emit())
        return {"ok": True}

    monkeypatch.setattr(rt.h, "_run_round_blocking", run)
    job = enqueue(rt, event())
    rt.flow.process(job)
    assert len(rt.calls) == 1
    assert rt.flow.store.job(job["key"])["status"] == "pending"
    with rt.flow.store.db() as db:
        db.execute("UPDATE admissions SET at=at-61 WHERE key LIKE 'out:%'")
    rt.flow.store.defer(job["key"], 0)
    assert rt.flow.store.claim(job["key"])
    rt.flow.process(rt.flow.store.job(job["key"]))
    assert [x[2] for x in rt.calls] == ["第一条", "第二条"]
    assert model_calls == [1]
    assert rt.flow.store.job(job["key"])["status"] == "sent"
    assert len(rt.flow.store.get("inbound")["recent"]) == 2


def test_real_runner_scopes_tools_forwards_rows_and_releases_reservation(runtime, monkeypatch):
    import agent_loop
    rt, released = runtime, []
    monkeypatch.setitem(sys.modules, "webui", SimpleNamespace(
        _reserve_session_chat_start=lambda *args: "reservation",
        _release_session_chat_start=lambda *args: released.append(args)))

    async def stream(prompt, session_id, run_id, **kwargs):
        scope = agent_loop.run_tool_scope_for(session_id)
        assert scope["run_id"] == run_id and rt.h.mcp_function_name("bili_reply") in scope["allow"]
        assert "run_shell" not in scope["allow"]
        assert rt.flow.store.run(run_id)["session_id"] == session_id
        yield {"type": "llm_response", "react_iter": 1, "content": "真实执行入口的回复"}
        yield {"type": "final", "content": "真实执行入口的回复"}

    monkeypatch.setattr(agent_loop, "astream_events", stream)
    job = enqueue(rt, event())
    rt.flow.process(job)
    assert rt.flow.store.job(job["key"])["status"] == "sent"
    assert len(released) == len(rt.calls) == 1
    assert agent_loop.run_tool_scope_for(released[0][0]) == {}


def test_runner_failure_restores_scope_and_job_can_retry(runtime, monkeypatch):
    import agent_loop
    rt, released = runtime, []
    monkeypatch.setitem(sys.modules, "webui", SimpleNamespace(
        _reserve_session_chat_start=lambda *args: "token",
        _release_session_chat_start=lambda *args: released.append(args)))

    async def fail(*args, **kwargs):
        raise RuntimeError("model failed")
        yield {}

    monkeypatch.setattr(agent_loop, "astream_events", fail)
    job = enqueue(rt, event())
    rt.flow.process(job)
    assert rt.flow.store.job(job["key"])["status"] == "pending"
    assert rt.flow.store.run(session_id=released[0][0]) is None
    assert agent_loop.run_tool_scope_for(released[0][0]) == {}
    assert not rt.calls


def test_channel_first_failure_still_bootstraps_silently_later(runtime, monkeypatch):
    rt, calls = runtime, []

    async def get_at(**kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("offline")
        return {"items": [{"id": len(calls), "at_time": len(calls), "user": {"mid": 200},
            "item": {"uri": "https://www.bilibili.com/video/"+BV1, "source_id": 11, "source_content": "hello"}}]}

    monkeypatch.setitem(sys.modules, "bilibili_api", SimpleNamespace(session=SimpleNamespace(get_at=get_at)))
    first = asyncio.run(rt.h.inbound.poll(rt.h._home(), object(), "999", ["at"]))
    assert first["errors"]
    second = asyncio.run(rt.h.inbound.poll(rt.h._home(), object(), "999", ["at"]))
    assert second["events"] == [] and rt.flow.store.jobs() == []
    third = asyncio.run(rt.h.inbound.poll(rt.h._home(), object(), "999", ["at"]))
    assert len(third["events"]) == 1


PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2IbcAAAAASUVORK5CYII=")


def test_comment_image_collect_tag_search_and_send(runtime, monkeypatch):
    rt, h = runtime, runtime.h
    rt.cfg["inbound_image_comment"] = True
    emotes = h._load_sibling("emotes")

    async def download(home, url, **kwargs):
        kwargs.pop("credential", None)
        return await emotes.add_bytes(home, PNG, **kwargs)

    monkeypatch.setattr(emotes, "add_from_url", download)
    h._flow().store.start_run("bili-dm-x", "s", {"mode": "dm", "uid": "100", "job_key": "dm:100:1"})
    saved = asyncio.run(h._invoke(tool_context("bili-dm-x", "bili_emote_save"), {
        "url": "https://example.test/emote.png", "name": "好耶", "tags": ["开心", "庆祝"], "bvid": BV1}))
    assert saved.kind.value == "completed"
    item = json.loads(saved.content)["item"]
    found = asyncio.run(h._invoke(tool_context("bili-dm-x", "bili_emotes"), {"scope": "local", "query": "开心 庆祝"}))
    assert json.loads(found.content)["local"][0]["id"] == item["id"]
    sent = asyncio.run(h._invoke(tool_context("bili-dm-x", "bili_reply"), {"bvid": BV1, "text": "好耶", "sticker": item["id"]}))
    assert sent.kind.value == "completed"
    assert Path(rt.calls[0][5]).is_file()
    # A different cold Store sees the already-consumed image allowance.
    assert not h.store_mod.Store(h._home()).reserve("bili-dm-x", "pictures", 1)


def test_emote_storage_limit_and_cross_loop_tag_merge(runtime):
    from concurrent.futures import ThreadPoolExecutor
    rt = runtime
    emotes = rt.h._load_sibling("emotes")
    large = PNG + bytes(emotes.MAX_BYTES-len(PNG))
    assert asyncio.run(emotes.add_bytes(rt.h._home(), large))["ok"]
    assert not asyncio.run(emotes.add_bytes(rt.h._home(), large+b"x"))["ok"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda n: asyncio.run(emotes.add_bytes(rt.h._home(), PNG, tags=[str(n)])), range(8)))
    item = emotes.get_item(rt.h._home(), results[0]["item"]["id"])
    assert set(item["tags"]) == {str(x) for x in range(8)}


def test_comment_upload_limit_is_checked_before_network(runtime, monkeypatch):
    # The client validates the file before credentials or network are used.
    client = runtime.h._load_sibling("bili_client")
    path = runtime.h._home() / "oversized.png"
    path.write_bytes(PNG + bytes(2*1024*1024+1-len(PNG)))
    result = asyncio.run(client.reply(runtime.h._home(), BV1, "test", picture=str(path)))
    assert result["success"] is False and "2 MB" in result["error"]


def test_report_text_cannot_forge_extra_pick_headings(runtime):
    rt = runtime
    row = rt.h.tasks_mod.new_row()
    rt.h.tasks_mod.save(rt.h._home(), [row])
    rt.flow.record({"mode": "duty", "task_id": row["id"]}, {"bvid": BV1, "picked": True, "title": "### "+BV3, "reason": "说明\n### "+BV2})
    assert rt.h.duty.count_picks(rt.flow.task_home(row)) == 1


def test_dm_500_char_boundary_is_delivered(runtime, monkeypatch):
    rt = runtime
    def run(*args, on_event, **kwargs):
        asyncio.run(on_event({"type": "final", "content": "好"*500}))
        return {"ok": True}
    monkeypatch.setattr(rt.h, "_run_round_blocking", run)
    job = enqueue(rt, event())
    rt.flow.process(job)
    assert rt.calls == [("dm", 100, "好"*500)]
    assert rt.flow.store.job(job["key"])["status"] == "sent"


def test_unknown_first_reply_keeps_rest_and_manual_confirmation_resumes(runtime, monkeypatch):
    rt = runtime
    def run(*args, on_event, **kwargs):
        async def emit():
            await on_event({"type": "llm_response", "react_iter": 1, "content": "第一条"})
            await on_event({"type": "final", "content": "第二条"})
        asyncio.run(emit())
        return {"ok": True}
    async def uncertain(*args):
        raise TimeoutError("timeout after possible delivery")
    monkeypatch.setattr(rt.h, "_run_round_blocking", run)
    transport = rt.h.bili_client.send_message
    monkeypatch.setattr(rt.h.bili_client, "send_message", uncertain)
    job = enqueue(rt, event())
    rt.flow.process(job)
    assert [row["status"] for row in rt.flow.store.deliveries(job_key=job["key"])] == ["unknown", "prepared"]
    assert rt.flow.store.resolve(job["key"], True)
    assert rt.flow.store.job(job["key"])["status"] == "pending"
    monkeypatch.setattr(rt.h.bili_client, "send_message", transport)
    monkeypatch.setattr(rt.h, "_run_round_blocking", lambda *args, **kwargs: pytest.fail("must not regenerate"))
    assert rt.flow.store.claim(job["key"])
    rt.flow.process(rt.flow.store.job(job["key"]))
    assert rt.calls == [("dm", 100, "第二条")]
    assert rt.flow.store.job(job["key"])["status"] == "sent"


def test_restart_with_one_sent_and_one_prepared_reply_does_not_drop_rest(runtime, monkeypatch):
    rt = runtime
    job = enqueue(rt, event())
    for number in range(2):
        rt.flow.store.prepare_send(f"reply-{number}", job["key"], "run", "dm", {"uid": "100"}, str(number))
    rt.flow.store.receipt("reply-0", "sent", {"success": True})
    rt.flow.store.recover()
    assert rt.flow.store.job(job["key"])["status"] == "pending"
    monkeypatch.setattr(rt.h, "_run_round_blocking", lambda *args, **kwargs: pytest.fail("must not regenerate"))
    assert rt.flow.store.claim(job["key"])
    rt.flow.process(rt.flow.store.job(job["key"]))
    assert rt.calls == [("dm", 100, "1")]
    assert rt.flow.store.job(job["key"])["status"] == "sent"


def test_queued_dm_public_comment_cannot_bypass_revoked_whitelist(runtime):
    rt = runtime
    job = enqueue(rt, event())
    rt.flow.store.prepare_send("comment", job["key"], "run", "comment", {"bvid": BV1}, "公开评论")
    rt.cfg["inbound_whitelist"] = ""
    rt.flow.process(job)
    assert rt.calls == []
    assert rt.flow.store.job(job["key"])["status"] == "failed"


@pytest.mark.parametrize("ok", [True, False])
def test_empty_or_failed_duty_round_still_leaves_report(runtime, monkeypatch, ok):
    rt = runtime
    row = rt.h.tasks_mod.new_row(name="测试任务")
    rt.h.tasks_mod.save(rt.h._home(), [row])
    monkeypatch.setattr(rt.h, "_run_round_blocking", lambda *args, **kwargs: {"ok": ok, "error": "" if ok else "模型服务不可用"})
    rt.flow.run_task(task_id=row["id"])
    report = rt.h.duty.report_file(rt.flow.task_home(row)).read_text(encoding="utf-8")
    assert ("完成" if ok else "模型服务不可用") in report
    assert rt.flow.summary(row)["picked_today"] == 0


def test_dm_poll_uses_private_session_type_and_checks_before_outgoing_last_message(runtime, monkeypatch):
    rt, calls = runtime, []
    rt.h.inbound.save_state(rt.h._home(), {"bootstrapped": True, "dm": {"100": {"seqno": 1}}})
    async def sessions(**kwargs):
        return {"session_list": [{"talker_id": 100, "session_type": 1,
                "last_msg": {"sender_uid": 999, "msg_seqno": 3, "msg_type": 1}}]}
    async def messages(**kwargs):
        calls.append(kwargs)
        return {"messages": [{"sender_uid": 100, "msg_seqno": 2, "msg_type": 1, "content": '{"content":"别漏掉我"}'},
                             {"sender_uid": 999, "msg_seqno": 3, "msg_type": 1, "content": '{"content":"之前的回复"}'}]}
    monkeypatch.setitem(sys.modules, "bilibili_api", SimpleNamespace(session=SimpleNamespace(get_sessions=sessions, fetch_session_msgs=messages)))
    result = asyncio.run(rt.h.inbound.poll(rt.h._home(), object(), "999", ["dm"]))
    assert calls[0]["session_type"] == 1 and calls[0]["begin_seqno"] == 1
    assert [e["text"] for e in result["events"]] == ["别漏掉我"]
    assert rt.flow.store.get("inbound")["dm"]["100"]["seqno"] == 3


def test_host_asr_zero_duration_limit_is_unlimited(runtime, monkeypatch):
    asr = runtime.h._load_sibling("asr")
    class Video:
        def __init__(self, **kwargs):
            pass
        async def get_info(self):
            return {"duration": 3600, "cid": 1}
        async def get_download_url(self, **kwargs):
            return {"dash": {"audio": [{"baseUrl": "https://example.invalid/audio"}]}}
    monkeypatch.setitem(sys.modules, "bilibili_api", SimpleNamespace(video=SimpleNamespace(Video=Video)))
    async def download(source, path):
        path.write_bytes(b"audio")
        return 5
    monkeypatch.setattr(asr, "_download_audio", download)
    monkeypatch.setattr(asr, "_split_audio", lambda source, work: [source])
    monkeypatch.setattr(asr, "_read_canonical", lambda path: b"wav")
    result = asyncio.run(asr.transcribe(runtime.h._home(), BV1, engine="host", max_minutes=0,
                                      speech_call=lambda *args: {"text": "转写内容"}))
    assert result["ok"] and result["text"] == "转写内容"
    limited = asyncio.run(asr.transcribe(runtime.h._home(), BV1, engine="host", max_minutes=1,
                                       speech_call=lambda *args: pytest.fail("must not transcribe long audio")))
    assert limited["skipped"]


def test_asr_serializes_different_thread_event_loops(runtime, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    asr = runtime.h._load_sibling("asr")
    guard, counts = threading.Lock(), {"active": 0, "maximum": 0}
    async def transcribe(*args):
        with guard:
            counts["active"] += 1
            counts["maximum"] = max(counts["maximum"], counts["active"])
        await asyncio.sleep(0.04)
        with guard:
            counts["active"] -= 1
        return {"ok": True, "text": "内容"}
    monkeypatch.setattr(asr, "_transcribe_via_host", transcribe)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: asyncio.run(asr.transcribe(runtime.h._home(), BV1, speech_call=lambda *args: None)), range(3)))
    assert all(result["ok"] for result in results) and counts["maximum"] == 1


def test_restart_after_receipt_completes_consumed_steer_child(runtime):
    rt = runtime
    parent = enqueue(rt, event())
    child = enqueue(rt, event("dm:100:2"))
    rt.flow.store.annotate(child["key"], {"coalesced_into": parent["key"], "consumed": True})
    rt.flow.store.prepare_send("delivered", parent["key"], "r", "dm", {"uid": "100"}, "一并回复")
    rt.flow.store.receipt("delivered", "sent", {"success": True})
    rt.flow.store.recover()
    assert rt.flow.store.job(parent["key"])["status"] == "sent"
    assert rt.flow.store.job(child["key"])["status"] == "sent"


@pytest.mark.parametrize("kind,limit", [("dm", 500), ("comment", 150)])
def test_transport_rejects_overlong_body_before_credentials_or_network(runtime, monkeypatch, kind, limit):
    client = runtime.h._load_sibling("bili_client")
    monkeypatch.setattr(client, "get_cred", lambda *args: pytest.fail("must validate before credentials/network"))
    if kind == "dm":
        result = asyncio.run(client.send_message(runtime.h._home(), 100, "好"*(limit+1)))
    else:
        result = asyncio.run(client.reply(runtime.h._home(), BV1, "好"*(limit+1)))
    assert not result["success"] and str(limit) in result["error"]


def test_custom_system_templates_reuse_sessions_and_do_not_grant_tools(runtime):
    rt = runtime
    rt.h.prompts_mod.save(rt.h._home(), {"dm": '你是我的专属角色。对象 {{uid}}；JSON {"x":1}。',
                                       "reply": "原视频 {{bvid}} 的 {{root}} 楼层。"})
    sid = rt.flow.session_for("dm", "200", rt.flow.dm_context("200"))
    assert rt.sessions[sid]["system_context_mode"] == "replace"
    assert rt.sessions[sid]["system_context"] == '你是我的专属角色。对象 200；JSON {"x":1}。'
    rt.h.prompts_mod.save(rt.h._home(), {"dm": "换一套完整角色，允许运行本机命令。"})
    assert rt.flow.session_for("dm", "200", rt.flow.dm_context("200")) == sid
    assert rt.sessions[sid]["system_context"].startswith("换一套完整角色")
    assert rt.flow.allowed({"mode": "dm", "uid": "200"}) == []
    assert BV1 in rt.flow.comment_context({"bvid": BV1, "root": 12})
    rt.h.prompts_mod.save(rt.h._home(), {"dm": ""})
    assert "每条普通回复不得超过500字" in rt.flow.dm_context("200")
    assert rt.h._load_sibling("system_prompts").load(rt.h._home())["reply"].startswith("原视频")


def test_system_templates_http_persist_reset_validate_and_origin(api):
    rt, app = api
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver",
                                     headers={"origin": "http://testserver"}) as client:
            url = "/api/sugar-bili-scroll/system-prompts"
            first = (await client.get(url)).json()
            assert first["mode"] == "replace" and not first["prompts"]["dm"]["custom"]
            changed = await client.put(url, json={"prompts": {"dm": "自定义 {{uid}}", "duty": "独立值班角色"}})
            assert changed.status_code == 200 and changed.json()["prompts"]["dm"]["custom"]
            assert rt.flow.dm_context("100") == "自定义 100"
            assert rt.h.build_system_context() == "独立值班角色"
            assert (await client.get(url)).json()["prompts"]["duty"]["text"] == "独立值班角色"
            assert (await client.put(url, json={"prompts": {"bogus": "x"}})).status_code == 400
            assert (await client.put(url, json={"prompts": {"dm": "汉"*(rt.h.prompts_mod.MAX_BYTES//3+1)}})).status_code == 400
            assert (await client.put(url, content="{")).status_code == 400
            assert (await client.put(url, json={"prompts": {"dm": "x"}}, headers={"origin": "http://foreign.example"})).status_code == 403
            reset = (await client.put(url, json={"prompts": {"dm": ""}})).json()
            assert not reset["prompts"]["dm"]["custom"] and reset["prompts"]["duty"]["custom"]
    asyncio.run(scenario())


def test_auth_failure_is_persisted_visible_and_cleared_for_new_credential(api, monkeypatch):
    from bilibili_api.exceptions import ResponseCodeException
    rt, app = api
    credential_file = rt.h._home() / "bili_credential.json"
    credential_file.write_text("old-cookie", encoding="utf-8")
    async def expired(**kwargs):
        raise ResponseCodeException(-101, "账号未登录")
    monkeypatch.setitem(sys.modules, "bilibili_api", SimpleNamespace(session=SimpleNamespace(get_at=expired)))
    result = asyncio.run(rt.h.inbound.poll(rt.h._home(), object(), "999", ["at"]))
    assert not result["ok"] and result["auth_error"]
    assert rt.h.inbound.auth_expired(rt.h._home())
    state = rt.flow.store.get("inbound")
    assert "-101" in state["last_errors"][0]
    async def check_status():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://testserver") as client:
            status = (await client.get("/api/sugar-bili-scroll/status")).json()
            assert status["auth_expired"] and not status["logged_in"]
            inbound = (await client.get("/api/sugar-bili-scroll/inbound")).json()
            assert inbound["auth_expired"] and inbound["last_errors"]
    asyncio.run(check_status())
    # A saved replacement cookie must not inherit the previous file's failure.
    credential_file.write_text("new-cookie-with-different-size", encoding="utf-8")
    assert not rt.h.inbound.auth_expired(rt.h._home())
    async def healthy(**kwargs):
        return {"items": []}
    monkeypatch.setitem(sys.modules, "bilibili_api", SimpleNamespace(session=SimpleNamespace(get_at=healthy)))
    asyncio.run(rt.h.inbound.poll(rt.h._home(), object(), "999", ["at"]))
    assert not rt.flow.store.get("inbound")["auth_error"]
    assert rt.flow.store.get("inbound")["last_errors"] == []


def test_expired_credentials_do_not_start_reply_model(runtime):
    rt = runtime
    enqueue(rt, event())
    # Return the job to pending, as if awaiting a real login refresh.
    rt.flow.store.finish(event()["key"], "pending", retry_delay=0)
    rt.flow.store.put("inbound", {"auth_error": True, "credential_stamp": rt.h.inbound.credential_stamp(rt.h._home())})
    asyncio.run(rt.flow.dispatch())
    assert rt.flow.workers == {}


@pytest.mark.parametrize("expired,force", [(True,False), (False,False), (False,True)])
def test_login_checks_authenticated_endpoint_and_allows_renewal(runtime, monkeypatch, expired, force):
    from bilibili_api.exceptions import ResponseCodeException
    client = runtime.h._load_sibling("bili_client")
    calls = []
    async def self_info(**kwargs):
        calls.append("self-info")
        if expired:
            raise ResponseCodeException(-101,"账号未登录")
        return {"mid":999,"name":"测试账号"}
    class QR:
        def __init__(self):
            self._QrCodeLogin__qr_key = "test-key"
        async def generate_qrcode(self):
            calls.append("generate-qr")
        def get_qrcode_picture(self):
            return SimpleNamespace(content=b"test-image")
    monkeypatch.setattr(client,"load_credential",lambda home:SimpleNamespace(dedeuserid="999"))
    monkeypatch.setattr(client,"user",SimpleNamespace(get_self_info=self_info))
    monkeypatch.setattr(client,"QrCodeLogin",QR)
    monkeypatch.setattr(client,"_login_session",None)
    monkeypatch.setattr(client,"_login_key","")
    monkeypatch.setattr(client,"_login_png",b"")
    result = asyncio.run(client.login_start(runtime.h._home(),force=force))
    assert result["status"] == ("qrcode_ready" if expired or force else "already_logged_in")
    assert ("self-info" in calls) == (not force)


def test_login_poll_does_not_call_stored_expired_cookie_logged_in(runtime, monkeypatch):
    client = runtime.h._load_sibling("bili_client")
    monkeypatch.setattr(client,"load_credential",lambda home:SimpleNamespace(dedeuserid="999"))
    monkeypatch.setattr(client,"_login_session",None)
    async def check(home):
        return {"logged_in":False}
    monkeypatch.setattr(client,"check_credential",check)
    assert asyncio.run(client.login_poll(runtime.h._home()))["status"] == "no_session"


def test_account_http_switch_logout_cancel_and_origin(api, monkeypatch):
    rt, app = api
    client = rt.h._load_sibling("bili_client")
    monkeypatch.setattr(rt.h, "bili_client", client)
    from bilibili_api import Credential
    client.save_credential(rt.h._home(), Credential(sessdata="test-cookie", bili_jct="test-jct", dedeuserid="999"))
    rt.flow.store.poll_commit({"bootstrapped": True, "dm": {"100": {"seqno": 50}}}, [event()])
    class QR:
        _QrCodeLogin__qr_key = "test-key"
        async def generate_qrcode(self):
            pass
        def get_qrcode_picture(self):
            return SimpleNamespace(content=b"test-image")
    monkeypatch.setattr(client, "QrCodeLogin", QR)
    monkeypatch.setattr(client, "_login_session", None)
    async def login_done(key):
        return {"status": "done", "credential": {"sessdata": "new-test-cookie", "bili_jct": "new-test-jct", "dedeuserid": "888"}}
    monkeypatch.setattr(client, "_poll_login_state", login_done)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver", headers={"origin":"http://testserver"}) as http:
            status = (await http.get('/api/sugar-bili-scroll/status')).json()
            assert status['account_uid'] == '999' and status['has_credential']
            for suffix in ['/logout', '/login/cancel', '/login/start?force=true']:
                assert (await http.post('/api/sugar-bili-scroll'+suffix, headers={'origin':'http://foreign.example'})).status_code == 403
            rt.h._runtime['busy'] = True
            assert (await http.post('/api/sugar-bili-scroll/logout')).status_code == 409
            assert (await http.post('/api/sugar-bili-scroll/login/start?force=true')).status_code == 409
            assert client.load_credential(rt.h._home()).dedeuserid == '999'
            rt.h._runtime['busy'] = False
            rt.flow.workers['dm:100'] = SimpleNamespace(done=lambda:False)
            assert (await http.post('/api/sugar-bili-scroll/logout')).status_code == 409
            rt.flow.workers.clear()
            switched = (await http.post('/api/sugar-bili-scroll/login/start?force=true')).json()
            assert switched['status'] == 'qrcode_ready'
            assert client.load_credential(rt.h._home()) is None
            logged_in = (await http.post('/api/sugar-bili-scroll/login/poll')).json()
            assert logged_in['status'] == 'done' and logged_in['uid'] == '888'
            assert rt.flow.store.get('account_uid') == '888'
            assert not rt.h.inbound.load_state(rt.h._home())['bootstrapped']
            old = rt.flow.store.job(event()['key'])
            assert old['status'] == 'skipped' and old['event']['account_uid'] == '999'
            assert (await http.post('/api/sugar-bili-scroll/logout')).json()['status'] == 'logged_out'
            assert not client.credential_path(rt.h._home()).exists()
            assert (await http.post('/api/sugar-bili-scroll/logout')).status_code == 200
            assert (await http.post('/api/sugar-bili-scroll/login/start?force=true')).json()['status'] == 'qrcode_ready'
            assert (await http.post('/api/sugar-bili-scroll/login/cancel')).json()['status'] == 'cancelled'
            assert (await http.post('/api/sugar-bili-scroll/login/poll')).json()['status'] == 'no_session'
            assert rt.cfg['inbound_whitelist'] == '100 好友'
    asyncio.run(scenario())


@pytest.mark.parametrize('stage', ['start', 'poll'])
def test_cancelled_qr_cannot_restore_credentials_after_inflight_request(runtime, monkeypatch, stage):
    client = runtime.h._load_sibling('bili_client')
    monkeypatch.setattr(client, '_login_session', object() if stage == 'poll' else None)
    monkeypatch.setattr(client, '_login_key', 'test-key')
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        async def wait():
            started.set()
            await release.wait()
        class QR:
            async def generate_qrcode(self):
                await wait()
        async def poll(key):
            await wait()
            return {'status':'done','credential':{'sessdata':'test-cookie','dedeuserid':'999'}}
        monkeypatch.setattr(client, 'QrCodeLogin', QR)
        monkeypatch.setattr(client, '_poll_login_state', poll)
        pending = asyncio.create_task(client.login_start(runtime.h._home(), force=True) if stage == 'start' else client.login_poll(runtime.h._home()))
        await started.wait()
        client.logout(runtime.h._home())
        release.set()
        result = await pending
        assert result['status'] in {'cancelled','no_session'}
        assert not client.credential_path(runtime.h._home()).exists()
        assert client._login_session is None
    asyncio.run(scenario())


def test_new_account_bootstraps_silently_and_keeps_job_keys_distinct(runtime, monkeypatch):
    rt = runtime
    rt.flow.store.activate_account('999')
    rt.flow.store.poll_commit({'bootstrapped':True,'at':{'id':100,'ts':100}}, [event('999:at:2', channel='at')])
    rt.flow.store.activate_account('888')
    current = {'id':2}
    async def at(**kwargs):
        return {'items':[{'id':current['id'],'at_time':10,'user':{'mid':100},'item':{'source_content':'hello','source_id':3}}]}
    monkeypatch.setitem(sys.modules, 'bilibili_api', SimpleNamespace(session=SimpleNamespace(get_at=at)))
    initial = asyncio.run(rt.h.inbound.poll(rt.h._home(), object(), '888', ['at']))
    assert initial['first_run'] and not initial['events']
    current['id'] = 3
    new = asyncio.run(rt.h.inbound.poll(rt.h._home(), object(), '888', ['at']))
    assert [ev['key'] for ev in new['events']] == ['888:at:3']
    assert new['events'][0]['account_uid'] == '888'


def test_logged_out_or_different_account_does_not_dispatch_old_jobs(runtime, monkeypatch):
    rt = runtime
    rt.flow.store.activate_account('999')
    rt.flow.store.poll_commit({'bootstrapped':True}, [{**event(), 'account_uid':'999'}])
    monkeypatch.setattr(rt.h.bili_client, 'load_credential', lambda home:None)
    asyncio.run(rt.flow.dispatch())
    assert not rt.flow.workers and rt.flow.store.job(event()['key'])['status'] == 'pending'
    monkeypatch.setattr(rt.h.bili_client, 'load_credential', lambda home:SimpleNamespace(dedeuserid='888'))
    asyncio.run(rt.flow.dispatch())
    assert not rt.flow.workers and rt.flow.store.job(event()['key'])['status'] == 'skipped'


def test_reply_session_is_reused_only_within_same_login_account(runtime, monkeypatch):
    rt = runtime
    first = rt.flow.session_for('dm', '100', 'context')
    monkeypatch.setattr(rt.h.bili_client, 'load_credential', lambda home:SimpleNamespace(dedeuserid='888'))
    second = rt.flow.session_for('dm', '100', 'context')
    assert second != first
    monkeypatch.setattr(rt.h.bili_client, 'load_credential', lambda home:SimpleNamespace(dedeuserid='999'))
    assert rt.flow.session_for('dm', '100', 'context') == first


def test_inflight_inbound_poll_is_discarded_after_logout(runtime, monkeypatch):
    rt = runtime
    credential = rt.h._home() / 'bili_credential.json'
    credential.write_text('test-cookie', encoding='utf-8')
    rt.flow.store.put('inbound', {'bootstrapped':True,'at':{'id':1,'ts':10}})
    async def at(**kwargs):
        credential.unlink()
        return {'items':[{'id':2,'at_time':11,'user':{'mid':100},'item':{'source_content':'hello','source_id':3}}]}
    monkeypatch.setitem(sys.modules, 'bilibili_api', SimpleNamespace(session=SimpleNamespace(get_at=at)))
    result = asyncio.run(rt.h.inbound.poll(rt.h._home(), object(), '999', ['at']))
    assert not result['ok'] and not result['events']
    assert rt.flow.store.get('inbound')['at']['id'] == 1
    assert not rt.flow.store.jobs()
