import asyncio
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from remote_control.transports.feishu.adapter import FeishuTransportAdapter
from remote_control.transports.feishu.config import FeishuConfig
from remote_control.transports.feishu.models import parse_message_event
from remote_control.transports.feishu.store import FeishuStateStore
from remote_control.service import RemoteControlError


def _event(
    message_id="om_1",
    text="hello",
    *,
    chat_id="oc_1",
    chat_type="p2p",
    open_id="ou_1",
    mentions=None,
    message_type="text",
):
    return {
        "event": {
            "sender": {
                "sender_type": "user",
                "sender_id": {"open_id": open_id, "union_id": "on_1"},
            },
            "message": {
                "message_id": message_id,
                "chat_id": chat_id,
                "chat_type": chat_type,
                "message_type": message_type,
                "content": json.dumps({"text": text}, ensure_ascii=False),
                "mentions": mentions or [],
            },
        }
    }


class _FakeSDK:
    def __init__(self):
        self.replies = []
        self.callback = None

    def build(self, callback):
        self.callback = callback

    def run_forever(self):
        return None

    def stop(self):
        return None

    def reply_text(self, message_id, text, *, uuid_value):
        self.replies.append((message_id, text, uuid_value))


class _FakeService:
    def __init__(self):
        self.calls = []
        self.sessions = {}
        self.queues = defaultdict(asyncio.Queue)
        self._counter = 0

    async def execute(self, principal, method, params, *, idempotency_key=""):
        self.calls.append((principal.device_id, method, dict(params), idempotency_key))
        if method == "session.create":
            self._counter += 1
            sid = f"s{self._counter}"
            self.sessions[sid] = {"id": sid, "name": params.get("name") or "New"}
            return {"session_id": sid, "session": self.sessions[sid]}, False
        if method == "session.get":
            sid = params["session_id"]
            if sid not in self.sessions:
                raise RemoteControlError("session_not_found", "missing")
            return {"session": self.sessions[sid]}, False
        if method == "session.send":
            return {"accepted": True, "session_id": params["session_id"], "run_id": "r1"}, False
        if method == "session.steer":
            return {"ok": True, "session_id": params["session_id"]}, False
        if method in {"session.interrupt", "approval.resolve"}:
            return {"ok": True}, False
        raise AssertionError(method)

    def subscribe(self, session_id, *, replay_recent=True):
        queue = self.queues[session_id]

        async def stream():
            while True:
                yield await queue.get()

        return stream()


def _config(tmp_path, **overrides):
    values = {
        "enabled": True,
        "app_id": "cli_test",
        "app_secret": "secret",
        "state_dir": tmp_path,
        "response_timeout_seconds": 5,
        "max_reply_chars": 3500,
    }
    values.update(overrides)
    return FeishuConfig(**values)


def test_parse_text_message_and_remove_mentions():
    parsed = parse_message_event(
        _event(
            text="@_user_1 请继续",
            chat_type="group",
            mentions=[{"key": "@_user_1", "name": "SugarAgent"}],
        )
    )
    assert parsed.text == "请继续"
    assert parsed.mentioned is True
    assert parsed.conversation_key("chat") == "chat:oc_1"


def test_feishu_config_is_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("FEISHU_ENABLED", raising=False)
    config = FeishuConfig.from_env(tmp_path)
    assert config.enabled is False
    monkeypatch.setenv("FEISHU_ENABLED", "1")
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    with pytest.raises(ValueError, match="FEISHU_APP_ID"):
        FeishuConfig.from_env(tmp_path).validate()


def test_state_store_binding_and_message_dedup(tmp_path):
    store = FeishuStateStore(tmp_path)
    assert store.claim_message("om_1") is True
    assert store.claim_message("om_1") is False
    assert store.release_message("om_1") is True
    assert store.claim_message("om_1") is True
    store.bind("p2p:on_1", "s1", chat_id="oc_1", sender_open_id="ou_1")
    assert store.get_binding("p2p:on_1") == "s1"
    assert store.unbind("p2p:on_1") is True
    assert store.get_binding("p2p:on_1") == ""


def test_group_message_requires_mention(tmp_path):
    sdk = _FakeSDK()
    service = _FakeService()
    adapter = FeishuTransportAdapter(
        _config(tmp_path, group_require_mention=True),
        service,
        FeishuStateStore(tmp_path),
        sdk_transport=sdk,
    )
    asyncio.run(adapter.handle_event(_event(chat_type="group", text="hello")))
    assert service.calls == []
    assert sdk.replies == []


def test_text_message_creates_session_sends_and_relays_final(tmp_path):
    sdk = _FakeSDK()
    service = _FakeService()
    adapter = FeishuTransportAdapter(
        _config(tmp_path),
        service,
        FeishuStateStore(tmp_path),
        sdk_transport=sdk,
    )

    async def scenario():
        await adapter.handle_event(_event(text="分析这个问题"))
        await service.queues["s1"].put(
            {"type": "final", "run_id": "r1", "content": "分析完成"}
        )
        await asyncio.sleep(0.05)

    asyncio.run(scenario())
    methods = [call[1] for call in service.calls]
    assert methods == ["session.create", "session.send"]
    assert service.calls[-1][3] == "om_1"
    assert [reply[1] for reply in sdk.replies] == ["已收到，正在处理。", "分析完成"]


def test_duplicate_event_does_not_send_twice(tmp_path):
    sdk = _FakeSDK()
    service = _FakeService()
    adapter = FeishuTransportAdapter(
        _config(tmp_path),
        service,
        FeishuStateStore(tmp_path),
        sdk_transport=sdk,
    )

    async def scenario():
        event = _event(text="hello")
        await adapter.handle_event(event)
        await adapter.handle_event(event)

    asyncio.run(scenario())
    assert [call[1] for call in service.calls].count("session.send") == 1


def test_deleted_bound_session_is_recreated_with_new_idempotency_key(tmp_path):
    sdk = _FakeSDK()
    service = _FakeService()
    adapter = FeishuTransportAdapter(
        _config(tmp_path),
        service,
        FeishuStateStore(tmp_path),
        sdk_transport=sdk,
    )

    async def scenario():
        await adapter.handle_event(_event(message_id="om_first", text="hello"))
        service.sessions.pop("s1")
        await adapter.handle_event(_event(message_id="om_second", text="again"))

    asyncio.run(scenario())
    create_calls = [call for call in service.calls if call[1] == "session.create"]
    assert len(create_calls) == 2
    assert create_calls[1][3] == "feishu-rebind:p2p:on_1:s1"


def test_new_session_and_stop_commands(tmp_path):
    sdk = _FakeSDK()
    service = _FakeService()
    adapter = FeishuTransportAdapter(
        _config(tmp_path),
        service,
        FeishuStateStore(tmp_path),
        sdk_transport=sdk,
    )

    async def scenario():
        await adapter.handle_event(_event(message_id="om_new", text="/new 手机会话"))
        await adapter.handle_event(_event(message_id="om_stop", text="/stop"))

    asyncio.run(scenario())
    assert service.sessions["s1"]["name"] == "手机会话"
    assert any(call[1] == "session.interrupt" for call in service.calls)
    assert sdk.replies[-1][1] == "已请求停止当前运行。"


def test_whoami_returns_allowlist_identifiers(tmp_path):
    sdk = _FakeSDK()
    adapter = FeishuTransportAdapter(
        _config(tmp_path),
        _FakeService(),
        FeishuStateStore(tmp_path),
        sdk_transport=sdk,
    )
    asyncio.run(adapter.handle_event(_event(message_id="om_who", text="/whoami")))
    assert "sender_open_id: ou_1" in sdk.replies[0][1]
    assert "chat_id: oc_1" in sdk.replies[0][1]


def test_adapter_lifecycle_dispatches_sdk_callback(tmp_path):
    sdk = _FakeSDK()
    adapter = FeishuTransportAdapter(
        _config(tmp_path),
        _FakeService(),
        FeishuStateStore(tmp_path),
        sdk_transport=sdk,
    )
    adapter.start()
    try:
        assert sdk.callback is not None
        sdk.callback(_event(message_id="om_callback", text="/whoami"))
        deadline = time.time() + 2
        while time.time() < deadline and not sdk.replies:
            time.sleep(0.01)
        assert sdk.replies
        assert "sender_open_id: ou_1" in sdk.replies[0][1]
    finally:
        adapter.stop()
