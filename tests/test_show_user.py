import asyncio
import base64
import json
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from starlette.requests import Request

APP = str(Path(__file__).resolve().parents[1] / "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

from host_tool_registry import HostToolInvocationContext
from runtime_v2.mirror import RuntimeMirror
from runtime_v2.ui_projection import RuntimeUiProjection
from tool_registry import ToolOutcomeKind
from user_presentations import invoke_show_user, prepare_presentation, saved_presentation


@pytest.fixture
def show_context(tmp_path, monkeypatch):
    import attachments
    from attachments.local import LocalAttachmentStore

    store = LocalAttachmentStore(tmp_path / "attachments-workspace")
    monkeypatch.setattr(attachments, "get_attachment_store", lambda *a, **k: store)
    root = tmp_path / "sessions"
    resolver = lambda sid: root / sid

    class Manager:
        sessions_dir = root
        _resolve_session_path = staticmethod(resolver)
        def append_ui_event(self, sid, event, *, require_commit=False):
            assert require_commit
            assert RuntimeMirror(root, resolver).mirror_ui_event(sid, event) is not None
        def get_ui_events_for_display(self, sid):
            return RuntimeUiProjection(root, resolver).read_ui_events(sid)

    manager = Manager()
    events = []
    async def publish(event):
        # A real Runtime V2 display fact must already exist before delivery.
        assert saved_presentation(manager, "s1", event["presentation"]["presentation_id"])
        events.append(event)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    context = HostToolInvocationContext(session_id="s1", run_id="run-1", tool_call_id="call-1",
        emit_event=publish, state={"session_id": "s1"}, services={"session_manager": manager,
        "security_workspace": workspace, "run_interrupt_check": lambda: False})
    return context, manager, store, events, workspace


def test_display_persists_before_publish_and_returns_without_waiting_for_user(show_context):
    context, manager, _, events, _ = show_context
    result = asyncio.run(invoke_show_user(context, {"kind": "text", "title": "实现进展", "text": "正在实现侧栏。"}))
    assert result.kind is ToolOutcomeKind.COMPLETED
    payload = json.loads(result.content)
    assert payload["status"] == "display_requested" and payload["requires_answer"] is False
    assert len(events) == 1 and events[0]["_runtime_v2_committed"] is True
    restored = saved_presentation(manager, "s1", payload["presentation_id"])
    assert restored["text"] == "正在实现侧栏。"
    assert "_runtime_v2_committed" not in manager.get_ui_events_for_display("s1")[0]


@pytest.mark.parametrize("arguments", [
    {"kind": "webpage", "url": "javascript:alert(1)"},
    {"kind": "webpage", "url": "https://user:password@example.test/"},
    {"kind": "webpage", "url": "/api/settings"},
    {"kind": "webpage", "url": "https://example.test:99999/"},
    {"kind": "text", "text": ""},
    {"kind": "text", "text": "ok", "format": "html"},
    {"kind": "text", "text": "a" * 65537},
    {"kind": "image", "data_url": "https://example.test/image.png", "alt": "图片"},
    {"kind": "plugin", "page_id": "main"},
    {"kind": "notice", "text": ""},
    {"kind": "notice", "text": "a" * 4001},
    {"kind": "notice", "text": "ok", "level": "urgent"},
    {"kind": "notice", "text": "ok", "duration_ms": 999},
    {"kind": "notice", "text": "ok", "duration_ms": 30001},
    {"kind": "notice", "text": "ok", "duration_ms": True},
    {"kind": "notification", "text": ""},
    {"kind": "notification", "text": "a" * 2001},
    {"kind": "settings", "section": "https://evil.test/"},
    {"kind": "file", "path": "missing.txt"},
    {"kind": "file", "path": "."},
    {"kind": "shell", "text": "ignored"},
])
def test_invalid_display_is_not_persisted_or_published(show_context, arguments):
    context, manager, _, events, _ = show_context
    result = asyncio.run(invoke_show_user(context, {"title": "内容", **arguments}))
    assert result.kind is ToolOutcomeKind.FAILED
    assert result.code == "invalid_presentation"
    assert not events and not manager.get_ui_events_for_display("s1")


def test_user_file_display_is_not_an_agent_file_read(show_context, tmp_path):
    context, _, _, events, workspace = show_context
    from security.runtime import classify_tool
    from security.models import DecisionOutcome, PERMISSION_PRESETS, PermissionMode
    from security.policy import PolicyEngine
    document = workspace / "guide.md"
    document.write_text("# Guide", encoding="utf-8")
    args = {"kind": "file", "title": "文档", "path": "guide.md"}
    request = classify_tool("show_user", args, workspace)
    assert request.action == "tool.call" and request.resource == "show_user"
    assert asyncio.run(invoke_show_user(context, args)).kind is ToolOutcomeKind.COMPLETED
    assert events[0]["presentation"]["path"] == str(document.resolve())
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    outside_args = {"kind": "file", "title": "外部文件", "path": str(outside)}
    request = classify_tool("show_user", outside_args, workspace)
    preset = PERMISSION_PRESETS[PermissionMode.ASK_FOR_APPROVAL]
    assert PolicyEngine(workspace).decide(request, preset, sandbox_available=True).outcome is DecisionOutcome.ALLOW
    reader = classify_tool("read_file", {"path": str(outside)}, workspace)
    assert reader.action == "fs.read"
    assert "required_dirs" not in request.metadata
    result = asyncio.run(invoke_show_user(context, outside_args))
    assert result.kind is ToolOutcomeKind.COMPLETED
    assert events[-1]["presentation"]["path"] == str(outside.resolve())
    assert "text" not in json.loads(result.content)


@pytest.mark.parametrize("relative", [False, True])
def test_external_display_accepts_absolute_and_parent_relative_paths(show_context, tmp_path, relative):
    _, _, _, _, workspace = show_context
    outside = tmp_path / "目录外 报告.html"
    outside.write_text("<h1>Report</h1>", encoding="utf-8")
    args = {"kind": "file", "title": "报告", "path": "../" + outside.name if relative else str(outside)}
    record = prepare_presentation(args, workspace=workspace)
    assert record["path"] == str(outside.resolve())
    workspace.rmdir()
    assert prepare_presentation(args, workspace=workspace)["path"] == record["path"]


def test_external_viewer_reads_text_media_html_and_sibling_assets_without_a_workspace(show_context, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from urllib.parse import quote
    import webui
    _, _, _, _, workspace = show_context
    external = tmp_path / "目录外 文档"
    external.mkdir()
    (external / "report.txt").write_text("用户查看的正文", encoding="utf-8")
    (external / "index.html").write_text('<link rel="stylesheet" href="style.css"><h1>报告</h1>', encoding="utf-8")
    (external / "style.css").write_text("h1{color:green}", encoding="utf-8")
    Image.new("RGB", (30, 20), "white").save(external / "image.png")
    (external / "audio.wav").write_bytes(b"RIFF-demo")
    workspace.rmdir()
    monkeypatch.setattr(webui, "WORK_DIR", workspace)
    client = TestClient(webui.fastapi_app)
    params = {"work_dir": str(external)}
    response = client.get("/api/workspace-file-text", params={**params, "rel": str(external / "report.txt")})
    assert response.json()["text"] == "用户查看的正文"
    response = client.get("/api/workspace-image", params={**params, "rel": str(external / "image.png")})
    assert response.content == (external / "image.png").read_bytes()
    response = client.get("/api/workspace-media", params={**params, "rel": str(external / "audio.wav")})
    assert response.content == b"RIFF-demo"
    for name in ("index.html", "style.css"):
        url = "/api/workspace-assets/" + quote((external / name).as_posix(), safe="/")
        response = client.get(url, params=params)
        assert response.status_code == 200
        assert response.content == (external / name).read_bytes()
        assert client.get(url).content == response.content


def test_plugin_page_requires_an_enabled_declared_destination(show_context, monkeypatch):
    import user_presentations
    context, _, _, events, _ = show_context
    monkeypatch.setattr(user_presentations, "_plugin_pages", lambda: [{"plugin_id": "demo", "id": "console"}])
    assert asyncio.run(invoke_show_user(context, {"kind": "plugin", "title": "控制台", "plugin_id": "demo"})).kind is ToolOutcomeKind.COMPLETED
    assert events[0]["presentation"]["page_id"] == "console"
    result = asyncio.run(invoke_show_user(context, {"kind": "plugin", "title": "已停用", "plugin_id": "disabled"}))
    assert result.kind is ToolOutcomeKind.FAILED
    assert len(events) == 1


def test_failed_commit_does_not_publish(show_context, monkeypatch):
    context, manager, _, events, _ = show_context
    def fail(*a, **k):
        raise OSError("disk write failed")
    monkeypatch.setattr(manager, "append_ui_event", fail)
    result = asyncio.run(invoke_show_user(context, {"kind": "text", "title": "内容", "text": "未保存"}))
    assert result.kind is ToolOutcomeKind.FAILED and result.code == "presentation_failed"
    assert not events


def test_saved_request_survives_disconnected_live_delivery(show_context):
    context, manager, _, _, workspace = show_context
    async def disconnected(_event):
        raise OSError("browser disconnected")
    context = HostToolInvocationContext(session_id="s1", run_id="r", tool_call_id="t", emit_event=disconnected,
        services={"session_manager": manager, "security_workspace": workspace})
    result = asyncio.run(invoke_show_user(context, {"kind": "text", "title": "结果", "text": "持久内容"}))
    assert result.kind is ToolOutcomeKind.COMPLETED
    assert saved_presentation(manager, "s1", json.loads(result.content)["presentation_id"])["text"] == "持久内容"


def test_image_is_durable_and_http_is_bound_to_its_presentation(show_context, monkeypatch):
    context, manager, store, events, _ = show_context
    import webui
    output = BytesIO()
    Image.new("RGB", (150, 150), "white").save(output, "PNG")
    result = asyncio.run(invoke_show_user(context, {"kind": "image", "title": "登录码", "alt": "二维码",
        "data_url": "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()}))
    assert result.kind is ToolOutcomeKind.COMPLETED
    record = events[0]["presentation"]
    assert "data_url" not in record["image"]
    monkeypatch.setattr(webui, "session_manager", manager)
    monkeypatch.setattr(webui, "get_attachment_store", lambda *_: store)
    response = asyncio.run(webui.read_user_presentation_image("s1", record["presentation_id"]))
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert Image.open(BytesIO(response.body)).size == (150, 150)
    assert asyncio.run(webui.read_user_presentation_image("s1", "missing")).status_code == 404
    assert asyncio.run(webui.read_user_presentation_image("s2", record["presentation_id"])).status_code == 404
    from fastapi import HTTPException
    request = Request({"type": "http", "headers": [(b"host", b"agent.test")], "client": ("198.51.100.2", 8080)})
    with pytest.raises(HTTPException) as error:
        asyncio.run(webui.read_user_presentation_image("s1", record["presentation_id"], request))
    assert error.value.status_code == 401


def test_show_user_is_resident_host_tool_and_independent_of_ask_flag(monkeypatch):
    import builtin_host_tools
    from host_tool_registry import host_tool_invokers
    from tool_search import RESIDENT_TOOLS
    from agent_tools import OPENAI_TOOL_DEFINITIONS
    monkeypatch.setenv("ASK_USER_ENABLED", "0")
    builtin_host_tools.register_builtin_host_tools()
    assert host_tool_invokers.has("show_user") and host_tool_invokers.is_enabled("show_user")
    assert {"show_user", "ask_user"} <= RESIDENT_TOOLS
    assert any(row["function"]["name"] == "show_user" for row in OPENAI_TOOL_DEFINITIONS)


def test_notice_defaults_and_persistent_notice(show_context):
    context, _, _, events, workspace = show_context
    args = {"kind": "notice", "title": "准备就绪", "text": "现在可以预览。"}
    default = prepare_presentation(args, workspace=workspace)
    assert default == {**args, "level": "info", "duration_ms": 8000}
    result = asyncio.run(invoke_show_user(context, {**args, "level": "success", "duration_ms": 0}))
    assert result.kind is ToolOutcomeKind.COMPLETED
    assert events[0]["presentation"]["duration_ms"] == 0


@pytest.mark.parametrize("section", ["general", "models", "skills", "plugins", "hooks", "mcp", "usage", "security", "env", "paths"])
def test_settings_accepts_builtin_tabs_without_changing_configuration(show_context, section):
    _, _, _, _, workspace = show_context
    args = prepare_presentation({"kind": "settings", "title": "设置", "section": section}, workspace=workspace)
    assert args == {"kind": "settings", "title": "设置", "section": section}
    assert not list(workspace.iterdir())


def test_settings_default_and_declared_plugin_sections(show_context, monkeypatch):
    import agent_extensions
    _, _, _, _, workspace = show_context
    args = {"kind": "settings", "title": "设置"}
    assert prepare_presentation(args, workspace=workspace)["section"] == "general"
    monkeypatch.setattr(agent_extensions, "plugin_catalog_snapshot", lambda: {"ui_contributions": [
        {"slot": "settings.section", "plugin_id": "demo", "id": "accounts"},
        {"slot": "details.tab", "plugin_id": "demo", "id": "console"}]})
    assert prepare_presentation({**args, "section": "plugin:demo:accounts"}, workspace=workspace)["section"] == "plugin:demo:accounts"
    for section in ("plugin:demo:console", "plugin:disabled:accounts"):
        with pytest.raises(ValueError, match="not an available"):
            prepare_presentation({**args, "section": section}, workspace=workspace)


@pytest.fixture
def native_provider(monkeypatch):
    import notification_providers
    received = []
    async def native(title, message, session_id):
        received.append((title, message, session_id))
        await asyncio.sleep(0)
    def other(*args):
        pytest.fail("System notification must not send to another channel")
    monkeypatch.setattr(notification_providers, "_providers", {"desktop-notifications": native, "other": other})
    return received


NOTIFICATION = {"kind": "notification", "title": "报告已生成", "text": "可以回来查看结果。"}


def test_native_notification_is_server_side_and_retries_do_not_resend(show_context, native_provider):
    context, manager, _, _, workspace = show_context
    async def disconnected(_event):
        raise OSError("browser closed")
    def new_context():
        return HostToolInvocationContext(session_id="s1", run_id="native-run", tool_call_id="native-call",
            emit_event=disconnected, services={"session_manager": manager, "security_workspace": workspace})
    first = asyncio.run(invoke_show_user(new_context(), NOTIFICATION))
    second = asyncio.run(invoke_show_user(new_context(), NOTIFICATION))
    assert first.kind is second.kind is ToolOutcomeKind.COMPLETED
    payload = json.loads(second.content)
    assert payload["notification_status"] == "requested"
    assert native_provider == [(NOTIFICATION["title"], NOTIFICATION["text"], "s1")]
    assert saved_presentation(manager, "s1", payload["presentation_id"])["notification_status"] == "requested"


def test_concurrent_native_request_has_one_durable_claim(show_context, native_provider):
    context, _, _, _, _ = show_context
    async def invoke_both():
        return await asyncio.gather(invoke_show_user(context, NOTIFICATION), invoke_show_user(context, NOTIFICATION))
    results = asyncio.run(invoke_both())
    assert all(result.kind is ToolOutcomeKind.COMPLETED for result in results)
    assert len(native_provider) == 1


@pytest.mark.parametrize("receipt", ["{unfinished", "null", '{"status":"invalid"}', '{"status":"unknown"}'])
def test_ambiguous_native_receipt_never_resends(show_context, native_provider, receipt):
    context, manager, _, _, _ = show_context
    result = asyncio.run(invoke_show_user(context, NOTIFICATION))
    identity = json.loads(result.content)["presentation_id"]
    path = manager._resolve_session_path("s1") / "presentations" / f"notification-{identity}.json"
    path.write_text(receipt, encoding="utf-8")
    result = asyncio.run(invoke_show_user(context, NOTIFICATION))
    assert json.loads(result.content)["notification_status"] == "unknown"
    assert len(native_provider) == 1


@pytest.mark.parametrize("enabled", [False, True])
def test_native_unavailable_or_failure_keeps_content(show_context, monkeypatch, enabled):
    import notification_providers
    context, manager, _, events, _ = show_context
    def fail(*args):
        raise RuntimeError("native unavailable")
    monkeypatch.setattr(notification_providers, "_providers", {"desktop-notifications": fail} if enabled else {})
    result = asyncio.run(invoke_show_user(context, NOTIFICATION))
    payload = json.loads(result.content)
    assert result.kind is ToolOutcomeKind.COMPLETED
    assert payload["notification_status"] == ("failed" if enabled else "unavailable")
    assert events[0]["presentation"]["text"] == NOTIFICATION["text"]
    assert saved_presentation(manager, "s1", payload["presentation_id"])["notification_status"] == payload["notification_status"]


def test_failed_initial_commit_prevents_native_notification(show_context, native_provider, monkeypatch):
    context, manager, _, _, _ = show_context
    def fail(*args, **kwargs):
        raise OSError("disk write failed")
    monkeypatch.setattr(manager, "append_ui_event", fail)
    result = asyncio.run(invoke_show_user(context, NOTIFICATION))
    assert result.kind is ToolOutcomeKind.FAILED
    assert not native_provider
