"""P0 一致性用例（按手册「会话权限分级」重写）。

跑法（在插件目录下）：
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
import asyncio
import json
import threading

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

from sugar_assistant.admission import Admission  # noqa: E402
from sugar_assistant.channels.fake import FakeChannel, inbound  # noqa: E402
from sugar_assistant.config import ChannelConfig, Config  # noqa: E402
from sugar_assistant.delivery import DeliveryQueue  # noqa: E402
from sugar_assistant.levels import axes_for, classify, normalize_level  # noqa: E402
from sugar_assistant.models import Delivery  # noqa: E402
from sugar_assistant.plugin import build_adapters, create_runtime  # noqa: E402
from sugar_assistant.prompts import Option, Question, PromptRegistry, build_prompt, parse_reply  # noqa: E402
from sugar_assistant.quota import WindowQuota  # noqa: E402
from sugar_assistant.bridge.sugaragent import HostBridgeError, SugarAgentHost  # noqa: E402
from sugar_assistant.prompts import build_prompt as _build_prompt  # noqa: E402
from sugar_assistant.relay import EventRelay  # noqa: E402
from sugar_assistant.service import SugarAssistantService, start_channels  # noqa: E402
from sugar_assistant import cli  # noqa: E402
from sugar_assistant import paths  # noqa: E402
from sugar_assistant.channels.feishu import FeishuSettings, build_channel, parse_event, split_reply  # noqa: E402
from sugar_assistant.channels.sidecar import SidecarChannel, SidecarSpec  # noqa: E402


class FakeHost:
    def __init__(self) -> None:
        self.created: list[dict] = []
        self.submitted: list[dict] = []
        self.interrupted: list[str] = []
        self.resolved: list[tuple[str, dict]] = []
        self.called: list[tuple[str, dict]] = []
        self._seq = 0

    def create_session(self, *, title: str, subject: str = "", system_prompt: str = "",
                       shared: bool = False, work_dir: str = "", model_profile_id: str = "") -> str:
        self._seq += 1
        session_id = f"s-{self._seq}"
        self.created.append({"session_id": session_id, "title": title, "subject": subject,
                             "system_prompt": system_prompt, "shared": shared,
                             "work_dir": work_dir, "model_profile_id": model_profile_id})
        return session_id

    def submit(self, session_id: str, text: str, *, op_id: str, actor: dict | None = None) -> None:
        self.submitted.append({"session_id": session_id, "text": text, "op_id": op_id, "actor": actor or {}})

    def rename_session(self, session_id: str, title: str) -> None:
        pass

    def list_sessions(self) -> list[dict]:
        return [{"session_id": item["session_id"], "title": item["title"]} for item in self.created]

    def interrupt(self, session_id: str) -> None:
        self.interrupted.append(session_id)

    def resolve_prompt(self, prompt, payload) -> None:
        self.resolved.append((prompt.id, payload))

    async def subscribe(self, session_id, replay_recent=False):
        if False:  # 空异步生成器，供 relay 的类型检查用
            yield {}

    def call(self, method, params, *, idempotency_key=""):
        self.called.append((method, dict(params)))
        if method == "session.history":
            return {"events": [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "在的"}]}
        if method == "session.get":
            return {"session": {"work_dir": "D:/tmp"}}
        return {"ok": True}


def build_config(**overrides) -> Config:
    channels = {
        "fake": ChannelConfig(
            name="fake",
            enabled=True,
            allow=["fake:u-owner"],
            allow_groups=["g-vip"],
            group_members={"g-small": 3},
        )
    }
    config = Config(enabled=True, session_scope="chat", channels=channels, principals={"fake:u-owner": "机主"})
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def build_runtime(tmpdir: str):
    host = FakeHost()
    channel = FakeChannel()
    runtime = create_runtime(build_config(), host, adapters={"fake": channel}, state_dir=tmpdir)
    return runtime, host, channel


class LevelTests(unittest.TestCase):
    """五类身份 + 四轴档位（手册 §二 / §三）。"""

    def test_matrix_values(self) -> None:
        self.assertEqual(axes_for("owner").as_dict(), {"control": 4, "tools": 4, "scope": 4, "directory": 4})
        self.assertEqual(axes_for("whitelist").as_dict(), {"control": 3, "tools": 3, "scope": 3, "directory": 3})
        self.assertEqual(axes_for("private").as_dict(), {"control": 3, "tools": 3, "scope": 2, "directory": 2})
        self.assertEqual(axes_for("group").as_dict(), {"control": 2, "tools": 2, "scope": 2, "directory": 2})
        self.assertEqual(axes_for("stranger").as_dict(), {"control": 1, "tools": 1, "scope": 1, "directory": 1})

    def test_aliases_normalized(self) -> None:
        for raw, expected in [("DM", "private"), ("小群", "private"), ("白名单", "whitelist"), ("陌生", "stranger")]:
            self.assertEqual(normalize_level(raw), expected)

    def test_classify_small_group_is_private(self) -> None:
        self.assertEqual(classify(is_private=False, members=3), "private")

    def test_classify_unknown_membership_is_group(self) -> None:
        # 人数拿不到一律按群聊，不降级成私聊
        self.assertEqual(classify(is_private=False, members=None), "group")

    def test_classify_whitelisted_group(self) -> None:
        self.assertEqual(classify(is_private=False, members=30, whitelisted_group=True), "private")


class AdmissionTests(unittest.TestCase):
    def _admission(self, **kwargs) -> Admission:
        params = dict(
            enabled_channels={"fake"},
            allowed_principals={"fake:u-owner"},
            allowed_groups={"g-vip"},
            group_members={"g-small": 3},
        )
        params.update(kwargs)
        return Admission(**params)

    def test_private_chat_gets_private_level(self) -> None:
        decision = self._admission().check(inbound("你好", peer="u-someone"))
        self.assertTrue(decision.ok)
        self.assertEqual(decision.level, "private")
        self.assertEqual(decision.tools_axis, 3)

    def test_group_chat_gets_group_level(self) -> None:
        decision = self._admission().check(inbound("你好", peer="u-someone", kind="group", chat="g-big"))
        self.assertEqual(decision.level, "group")
        self.assertEqual(decision.tools_axis, 2)

    def test_small_group_gets_private(self) -> None:
        decision = self._admission().check(inbound("你好", peer="u-1", kind="group", chat="g-small"))
        self.assertEqual(decision.level, "private")

    def test_whitelisted_group_gets_private(self) -> None:
        decision = self._admission().check(inbound("你好", peer="u-1", kind="group", chat="g-vip"))
        self.assertEqual(decision.level, "private")

    def test_whitelisted_user_gets_whitelist(self) -> None:
        decision = self._admission().check(inbound("你好", peer="u-owner", kind="group", chat="g-big"))
        self.assertEqual(decision.level, "whitelist")

    def test_empty_enabled_set_denies_everything(self) -> None:
        decision = self._admission(enabled_channels=set()).check(inbound("你好", peer="u-owner"))
        self.assertFalse(decision.ok)
        self.assertIn("通道未启用", decision.reason)


class TurnActorTests(unittest.TestCase):
    """权限不落会话：会话只拿标题，身份随每轮下发。"""

    def test_session_created_without_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, _ = build_runtime(tmp)
            runtime.handle_inbound(inbound("你好", message_id="m-1"))
            self.assertEqual(set(host.created[0].keys()),
                             {"session_id", "title", "subject", "system_prompt", "shared",
                              "work_dir", "model_profile_id"})
            # 归属固定为插件自身：bot/user 切换不应导致会话重建
            self.assertEqual(host.created[0]["subject"], "sugar-assistant:owner")

    def test_turn_actor_carries_level_and_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, _ = build_runtime(tmp)
            runtime.handle_inbound(inbound("你好", peer="u-owner", message_id="m-1"))
            actor = host.submitted[0]["actor"]
            self.assertEqual(actor["_level"], "whitelist")
            self.assertEqual(actor["_subject"], "sugar-assistant:owner")
            # _source 由宿主 ServiceProxy 注入（带 epoch），插件不自造
            self.assertNotIn("_source", actor)

    def test_group_member_actor_is_group_level(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, _ = build_runtime(tmp)
            runtime.handle_inbound(inbound("你好", peer="u-x", chat="g-big", kind="group", message_id="m-1"))
            self.assertEqual(host.submitted[0]["actor"]["_level"], "group")

    def test_same_person_two_messages_share_session(self) -> None:
        # 宿主用 mode=queue + 同一 actor 判定"同人合并"，插件只需保证 actor 一致
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, _ = build_runtime(tmp)
            runtime.handle_inbound(inbound("一", peer="u-owner", message_id="m-1"))
            runtime.handle_inbound(inbound("二", peer="u-owner", message_id="m-2"))
            self.assertEqual(host.submitted[0]["session_id"], host.submitted[1]["session_id"])
            self.assertEqual(host.submitted[0]["actor"], host.submitted[1]["actor"])


class IdempotencyTests(unittest.TestCase):

    def test_session_owned_by_old_identity_is_rebound(self) -> None:
        """升级前建的会话归属旧身份：send 被拒后要丢掉映射、重建一次。"""

        class RebindHost(FakeHost):
            def submit(self, session_id, text, *, op_id, actor=None):
                if session_id == "s-1":
                    raise RuntimeError("Session belongs to another identity")
                super().submit(session_id, text, op_id=op_id, actor=actor)

        with tempfile.TemporaryDirectory() as tmp:
            host = RebindHost()
            runtime = create_runtime(build_config(), host, adapters={"fake": FakeChannel()}, state_dir=tmp)
            result = runtime.handle_inbound(inbound("hi", peer="u-owner", message_id="m-1"))
            self.assertEqual(result.status, "accepted")
            self.assertEqual(result.session_id, "s-2")
            self.assertEqual(len(host.created), 2)

    def test_deleted_session_is_recreated(self) -> None:
        """宿主会话被删后，映射还留着：send 报 Session not found，应自动重建。"""

        class DeletedHost(FakeHost):
            def submit(self, session_id, text, *, op_id, actor=None):
                if session_id == "s-1":
                    raise RuntimeError("Session not found")
                super().submit(session_id, text, op_id=op_id, actor=actor)

        with tempfile.TemporaryDirectory() as tmp:
            host = DeletedHost()
            runtime = create_runtime(build_config(), host, adapters={"fake": FakeChannel()}, state_dir=tmp)
            result = runtime.handle_inbound(inbound("在吗", peer="u-owner", message_id="m-9"))
            self.assertEqual(result.status, "accepted")
            self.assertEqual(result.session_id, "s-2")
    def test_same_message_id_runs_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, _ = build_runtime(tmp)
            first = runtime.handle_inbound(inbound("在吗", peer="u-owner", message_id="m-1"))
            second = runtime.handle_inbound(inbound("在吗", peer="u-owner", message_id="m-1"))
            self.assertTrue(first.ok)
            self.assertEqual(second.status, "duplicate")
            self.assertEqual(len(host.submitted), 1)


class CommandTests(unittest.TestCase):

    def test_identity_switch_persists(self) -> None:
        from sugar_assistant import identity

        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("SUGAR_DATA_DIR")
            os.environ["SUGAR_DATA_DIR"] = tmp
            try:
                self.assertEqual(identity.current(), "bot")
                identity.set_mode("user")
                self.assertEqual(identity.current(), "user")
                with self.assertRaises(ValueError):
                    identity.set_mode("root")
            finally:
                os.environ.pop("SUGAR_DATA_DIR", None)
                if old is not None:
                    os.environ["SUGAR_DATA_DIR"] = old

    def test_question_event_sends_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, channel = build_runtime(tmp)
            runtime.sessions.resolve(inbound("hi", peer="u-owner", message_id="m-1"), title="小Sugar私聊")
            relay = EventRelay(runtime)
            event = {
                "type": "interaction_requested",
                "payload": {
                    "interaction_id": "i-1",
                    "questions": [{
                        "question_id": "q1", "header": "选一个", "question": "接下来做什么？",
                        "options": [{"option_id": "q1o1", "label": "继续"},
                                    {"option_id": "q1o2", "label": "换话题"}],
                    }],
                },
            }
            relay.handle_event("s-1", event)
            card = (channel.outbox[-1].meta or {}).get("card") or {}
            self.assertTrue(card.get("sections") or card.get("options"), "ask 必须以卡片形式发到飞书")

    def test_merge_keeps_order_and_separator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, channel = build_runtime(tmp)
            service = SugarAssistantService(runtime, merge_window_ms=120)

            async def run() -> None:
                await service.handle(inbound("第一条", peer="u-owner", message_id="m-1"))
                await service.handle(inbound("第二条", peer="u-owner", message_id="m-2"))
                await asyncio.sleep(0.4)

            asyncio.run(run())
            text = host.submitted[-1]["text"]
            self.assertLess(text.index("第一条"), text.index("第二条"))
            self.assertIn("\n\n", text)

    def test_help_command_is_sent_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, channel = build_runtime(tmp)
            service = SugarAssistantService(runtime, merge_window_ms=0)
            result = asyncio.run(service.handle(inbound("/help", peer="u-owner", message_id="m-help")))
            self.assertEqual(result.status, "command")
            self.assertTrue(channel.sent_texts, "命令回复应当直接发回通道")
            self.assertIn("/new", channel.sent_texts[-1])
    def test_whoami_reports_level_and_axes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, _ = build_runtime(tmp)
            result = runtime.handle_inbound(inbound("/whoami", peer="u-someone", message_id="m-1"))
            self.assertIn("private", result.reply)
            self.assertIn("control", result.reply)

    def test_new_command_creates_new_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, _ = build_runtime(tmp)
            runtime.handle_inbound(inbound("一", peer="u-owner", message_id="m-1"))
            runtime.handle_inbound(inbound("/new 另一个话题", peer="u-owner", message_id="m-2"))
            self.assertEqual(len(host.created), 2)

    def test_history_command_reads_host(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, _ = build_runtime(tmp)
            runtime.handle_inbound(inbound("你好", peer="u-owner", message_id="m-1"))
            result = runtime.handle_inbound(inbound("/history 5", peer="u-owner", message_id="m-2"))
            self.assertIn("在的", result.reply)
            self.assertEqual(host.called[-1][0], "session.history")

    def test_dir_command_updates_host(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, _ = build_runtime(tmp)
            runtime.handle_inbound(inbound("你好", peer="u-owner", message_id="m-1"))
            result = runtime.handle_inbound(inbound("/dir D:/work", peer="u-owner", message_id="m-2"))
            self.assertIn("D:/work", result.reply)
            self.assertEqual(host.called[-1][0], "session.update")
            self.assertEqual(host.called[-1][1]["work_dir"], "D:/work")


class QuotaTests(unittest.TestCase):
    def test_warn_at_eighth_and_exhaust_at_tenth(self) -> None:
        quota = WindowQuota()
        charges = [quota.charge("c1", "tok") for _ in range(10)]
        self.assertTrue(charges[7].warn)
        self.assertFalse(charges[7].exhausted)
        self.assertTrue(charges[9].exhausted)
        self.assertFalse(charges[8].warn)

    def test_new_token_resets_window(self) -> None:
        quota = WindowQuota()
        for _ in range(10):
            quota.charge("c1", "tok-a")
        self.assertEqual(quota.charge("c1", "tok-b").used, 1)


class PromptTests(unittest.TestCase):
    def _prompt(self, registry: PromptRegistry, *, questions: int = 1):
        qs = [
            Question(
                question_id=f"q{index + 1}",
                header=f"第{index + 1}题",
                text="选一个",
                options=[Option(f"q{index + 1}o1", "甲"), Option(f"q{index + 1}o2", "乙")],
            )
            for index in range(questions)
        ]
        return registry.add(build_prompt(kind="question", session_id="s-1", questions=qs))

    def test_single_choice_without_code(self) -> None:
        registry = PromptRegistry()
        self._prompt(registry)
        result = parse_reply("2", registry.pending("s-1"), registry=registry)
        self.assertTrue(result.ok)
        self.assertEqual(result.payload["answers"][0]["selected_option_ids"], ["q1o2"])

    def test_ambiguous_when_multiple_pending(self) -> None:
        registry = PromptRegistry()
        first = self._prompt(registry)
        self._prompt(registry)
        result = parse_reply("1", registry.pending("s-1"), registry=registry)
        self.assertFalse(result.ok)
        self.assertEqual(len(result.ambiguous), 2)
        self.assertIn(first.short_code, result.error)

    def test_code_disambiguates(self) -> None:
        registry = PromptRegistry()
        first = self._prompt(registry)
        self._prompt(registry)
        result = parse_reply(f"{first.short_code} 1", registry.pending("s-1"), registry=registry)
        self.assertTrue(result.ok)
        self.assertEqual(result.prompt_id, first.id)

    def test_other_text(self) -> None:
        registry = PromptRegistry()
        self._prompt(registry)
        result = parse_reply("其他：用 Redis", registry.pending("s-1"), registry=registry)
        self.assertEqual(result.payload["answers"][0]["other_text"], "用 Redis")

    def test_skip(self) -> None:
        registry = PromptRegistry()
        self._prompt(registry)
        result = parse_reply("跳过", registry.pending("s-1"), registry=registry)
        self.assertTrue(result.payload["answers"][0]["skipped"])

    def test_multi_question_requires_all_answers(self) -> None:
        registry = PromptRegistry()
        self._prompt(registry, questions=2)
        self.assertFalse(parse_reply("1", registry.pending("s-1"), registry=registry).ok)
        good = parse_reply("1 2", registry.pending("s-1"), registry=registry)
        self.assertTrue(good.ok)
        self.assertEqual(len(good.payload["answers"]), 2)

    def test_out_of_range_rejected(self) -> None:
        registry = PromptRegistry()
        self._prompt(registry)
        self.assertFalse(parse_reply("9", registry.pending("s-1"), registry=registry).ok)

    def test_single_prompt_render_has_no_short_code(self) -> None:
        registry = PromptRegistry()
        prompt = self._prompt(registry)
        text = prompt.render()
        self.assertNotIn(f"[{prompt.short_code}]", text)
        self.assertIn("直接回数字", text)

    def test_second_prompt_render_carries_code(self) -> None:
        registry = PromptRegistry()
        self._prompt(registry)
        second = self._prompt(registry)
        self.assertIn(f"[{second.short_code}]", second.render())


class DeliveryTests(unittest.TestCase):
    def _queue(self, channel: FakeChannel, **kwargs) -> DeliveryQueue:
        return DeliveryQueue(lambda name: channel, sleeper=lambda _s: None, **kwargs)

    def test_retry_then_ack(self) -> None:
        channel = FakeChannel()
        channel.failures = 1
        queue = self._queue(channel, max_attempts=3, readback=False)
        base = inbound("x")
        delivery = Delivery(id="d1", channel=base.channel, conversation=base.conversation, text="hi", idempotency_key="k1")
        queue.enqueue(delivery)
        report = queue.pump()
        self.assertEqual(delivery.status, "acked")
        self.assertEqual(delivery.attempts, 2)
        self.assertEqual(report.retried, 1)

    def test_unreachable_stops_after_max_attempts(self) -> None:
        channel = FakeChannel()
        channel.failures = 9
        queue = self._queue(channel, max_attempts=3, readback=False)
        base = inbound("x")
        delivery = Delivery(id="d2", channel=base.channel, conversation=base.conversation, text="hi")
        queue.enqueue(delivery)
        queue.pump()
        self.assertEqual(delivery.status, "unreachable")
        self.assertEqual(delivery.attempts, 3)

    def test_readback_saves_a_failed_send(self) -> None:
        channel = FakeChannel()
        channel.failures = 1
        channel.verify_ok = True
        queue = self._queue(channel, max_attempts=3, readback=True)
        base = inbound("x")
        delivery = Delivery(id="d3", channel=base.channel, conversation=base.conversation, text="hi")
        queue.enqueue(delivery)
        queue.pump()
        self.assertEqual(delivery.status, "readback")

    def test_idempotent_key_not_sent_twice(self) -> None:
        channel = FakeChannel()
        queue = self._queue(channel)
        base = inbound("x")
        first = Delivery(id="d4", channel=base.channel, conversation=base.conversation, text="hi", idempotency_key="same")
        queue.enqueue(first)
        queue.pump()
        second = Delivery(id="d5", channel=base.channel, conversation=base.conversation, text="hi", idempotency_key="same")
        queue.enqueue(second)
        report = queue.pump()
        self.assertEqual(second.status, "acked")
        self.assertEqual(report.sent, 0)
        self.assertEqual(len(channel.outbox), 1)


class HostEventTests(unittest.TestCase):
    def test_assistant_output_reaches_channel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, channel = build_runtime(tmp)
            runtime.handle_inbound(inbound("你好", peer="u-owner", message_id="m-1"))
            session_id = host.submitted[0]["session_id"]
            delivery = runtime.on_host_event(session_id, "我在这儿")
            self.assertIsNotNone(delivery)
            self.assertEqual(channel.sent_texts, ["我在这儿"])

    def test_unbound_session_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, _, channel = build_runtime(tmp)
            self.assertIsNone(runtime.on_host_event("s-unknown", "谁在说话"))
            self.assertEqual(channel.sent_texts, [])

    def test_answer_prompt_submits_to_host(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, _ = build_runtime(tmp)
            runtime.handle_inbound(inbound("你好", peer="u-owner", message_id="m-1"))
            session_id = host.submitted[0]["session_id"]
            prompt = runtime.prompts.add(
                build_prompt(
                    kind="question",
                    session_id=session_id,
                    questions=[Question("q1", "标题", "选哪个", [Option("q1o1", "甲"), Option("q1o2", "乙")])],
                )
            )
            result = runtime.answer(session_id, "1")
            self.assertTrue(result.ok)
            self.assertEqual(host.resolved[0][0], prompt.id)


class FakeService:
    """模拟 session_control/service.py 的 execute(principal, method, params, idempotency_key)。"""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.next_session_id = "s-bridge"

    async def execute(self, principal, method, params, *, idempotency_key=""):
        self.calls.append({"method": method, "params": dict(params), "key": idempotency_key})
        if method == "session.create":
            return {"session_id": self.next_session_id}, False
        if method == "session.send":
            return {"accepted": True, "run_id": "r-1"}, False
        return {}, False

    async def subscribe(self, session_id, replay_recent=False):
        if False:
            yield {}


class RelayTests(unittest.TestCase):
    """宿主事件 → 出站投递 / 审批提示。"""

    def test_final_event_delivers_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, channel = build_runtime(tmp)
            runtime.handle_inbound(inbound("你好", peer="u-owner", message_id="m-1"))
            session_id = host.submitted[0]["session_id"]
            relay = EventRelay(runtime)
            ended = relay.handle_event(session_id, {"type": "final", "content": "答完了", "run_id": "r-1"})
            self.assertEqual(ended, "final")
            self.assertEqual(channel.sent_texts, ["答完了"])

    def test_error_event_delivers_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, channel = build_runtime(tmp)
            runtime.handle_inbound(inbound("你好", peer="u-owner", message_id="m-1"))
            session_id = host.submitted[0]["session_id"]
            EventRelay(runtime).handle_event(session_id, {"type": "run_failed", "error": "模型 429"})
            self.assertTrue(any("429" in text for text in channel.sent_texts))

    def test_same_approval_only_notified_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, channel = build_runtime(tmp)
            runtime.handle_inbound(inbound("你好", peer="u-owner", message_id="m-1"))
            session_id = host.submitted[0]["session_id"]
            relay = EventRelay(runtime)
            seen: set[str] = set()
            event = {"type": "tool_approval_required", "approval_id": "a-1", "tool": "run_shell"}
            relay.handle_event(session_id, event, seen)
            relay.handle_event(session_id, event, seen)
            self.assertEqual(len(runtime.prompts.pending(session_id)), 1)
            self.assertEqual(len([t for t in channel.sent_texts if "同意" in t]), 1)

    def test_question_event_renders_numbered_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, channel = build_runtime(tmp)
            runtime.handle_inbound(inbound("你好", peer="u-owner", message_id="m-1"))
            session_id = host.submitted[0]["session_id"]
            rows = [{
                "interaction_id": "i-1",
                "questions": [{"question_id": "q1", "header": "部署方式",
                               "question": "选哪种？",
                               "options": [{"option_id": "q1o1", "label": "本地"},
                                           {"option_id": "q1o2", "label": "云端"}]}],
            }]
            relay = EventRelay(runtime, question_source=lambda sid: rows)
            relay.handle_event(session_id, {"type": "question_requested"})
            self.assertEqual(len(runtime.prompts.pending(session_id)), 1)
            self.assertTrue(any("1" in t and "本地" in t for t in channel.sent_texts))
            # 重复事件不再发第二遍
            relay.handle_event(session_id, {"type": "question_requested"})
            self.assertEqual(len(runtime.prompts.pending(session_id)), 1)


class FeishuParseTests(unittest.TestCase):
    """飞书事件解析：口径沿用 feishu-transport，不重写协议。"""

    def _payload(self, *, chat_type="p2p", text="你好", mentions=None, thread=None):
        return {
            "event": {
                "sender": {"sender_id": {"open_id": "ou_1", "union_id": "on_1"}, "sender_type": "user"},
                "message": {
                    "message_id": "om_1",
                    "chat_id": "oc_1",
                    "chat_type": chat_type,
                    "message_type": "text",
                    "content": '{"text": "%s"}' % text,
                    "mentions": mentions or [],
                    "thread_id": thread,
                },
            }
        }

    def test_p2p_text(self) -> None:
        inbound = parse_event(self._payload())
        self.assertEqual(inbound.text, "你好")
        self.assertEqual(inbound.conversation.kind, "p2p")
        self.assertEqual(inbound.sender.user_id, "on_1")
        self.assertEqual(inbound.channel.channel, "feishu")

    def test_group_with_thread(self) -> None:
        inbound = parse_event(self._payload(chat_type="group", thread="omt_9"))
        self.assertEqual(inbound.conversation.kind, "group")
        self.assertEqual(inbound.conversation.thread_id, "omt_9")

    def test_mention_is_stripped(self) -> None:
        payload = self._payload(chat_type="group", text="@_user_1 帮我看下",
                                mentions=[{"key": "@_user_1", "name": "小助手"}])
        inbound = parse_event(payload)
        self.assertEqual(inbound.text, "帮我看下")
        self.assertTrue(inbound.raw["mentions"])

    def test_missing_sender_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_event({"event": {"message": {}}})

    def test_channel_is_a_subprocess_adapter(self) -> None:
        """飞书长连接跑在 worker 子进程里，宿主侧只是一个 SidecarChannel。"""
        channel = build_channel(FeishuSettings(enabled=True, app_id="a", app_secret="s"))
        argv = channel.spec.argv()
        self.assertIn("feishu_worker.py", " ".join(argv))
        self.assertEqual(channel.id, "feishu")
        self.assertEqual(channel.capabilities.quota, "rate")
        self.assertEqual(channel.spec.env["FEISHU_APP_ID"], "a")

    def test_long_reply_is_split_into_fitting_chunks(self) -> None:
        text = "\n".join(f"第{i}行" + "内容" * 30 for i in range(60))
        chunks = split_reply(text, 500)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 500 for chunk in chunks))
        self.assertEqual("\n".join(chunks), text.rstrip("\n"))

    def test_single_long_line_is_hard_split(self) -> None:
        chunks = split_reply("字" * 1200, 500)
        self.assertEqual([len(c) for c in chunks], [500, 500, 200])

    def test_adapter_only_built_when_enabled(self) -> None:
        disabled = build_config()
        disabled.channels["feishu"] = ChannelConfig(name="feishu", enabled=False)
        self.assertEqual(build_adapters(disabled), {})

        enabled = build_config()
        enabled.channels["feishu"] = ChannelConfig(name="feishu", enabled=True)
        built = build_adapters(enabled)
        self.assertIn("feishu", built)
        self.assertEqual(built["feishu"].capabilities.quota, "rate")

        both = build_config()
        both.channels["qq"] = ChannelConfig(name="qq", enabled=True)
        built_both = build_adapters(both)
        self.assertIn("qq", built_both)
        self.assertFalse(built_both["qq"].capabilities.group)  # 与 dsh-qq 一致：只做私聊


class CliAndMcpTests(unittest.TestCase):
    """CLI 的四档权限与常用命令；MCP 工具只是它们的薄包装。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._old_state = cli.STATE_DIR
        cli.STATE_DIR = self._tmp.name

    def tearDown(self) -> None:
        cli.STATE_DIR = self._old_state
        self._tmp.cleanup()

    def test_level_gate(self) -> None:
        with self.assertRaises(cli.PermissionDenied):
            cli.require("person.add", 1)
        cli.require("person.add", 2)  # 不抛就是通过

    def test_read_command_allowed_at_level_one(self) -> None:
        cli.require("status", 1)
        cli.require("person.list", 1)

    def test_person_add_then_lookup(self) -> None:
        cli.person_add("阿鱼", "主人", "小鱼", "测试")
        found = cli.person_lookup("小鱼")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["relation"], "主人")
        self.assertEqual(len(cli.person_lookup("阿鱼")), 1)

    def test_persona_roundtrip(self) -> None:
        cli.persona_set(name="Sugar Assistant", tone="简短")
        self.assertIn("Sugar Assistant", cli.store().persona()["prompt"])
        cli.persona_set(rules="别乱承诺")
        self.assertIn("说话风格：简短", cli.store().persona()["prompt"])

    def test_history_filters_by_session(self) -> None:
        cli.store().log("accepted", session_id="s-1", channel="fake")
        cli.store().log("accepted", session_id="s-2", channel="fake")
        self.assertEqual(len(cli.history("s-1")), 1)


class PathsTests(unittest.TestCase):
    """数据目录在插件包外；旧位置的文件要能迁过去。"""

    def test_env_override_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("SUGAR_DATA_DIR")
            os.environ["SUGAR_DATA_DIR"] = tmp
            try:
                self.assertEqual(paths.data_dir(), os.path.abspath(tmp))
                self.assertEqual(paths.config_path(), os.path.join(os.path.abspath(tmp), "config.json"))
            finally:
                if old is None:
                    os.environ.pop("SUGAR_DATA_DIR", None)
                else:
                    os.environ["SUGAR_DATA_DIR"] = old

    def test_default_lives_under_host_storage(self) -> None:
        if os.getenv("SUGAR_DATA_DIR"):
            self.skipTest("SUGAR_DATA_DIR 已设置，跳过默认路径断言")
        self.assertIn(os.path.join(".config", "plugins", "sugar-assistant", "data"), paths.data_dir())

    def test_migration_moves_legacy_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            legacy = os.path.join(tmp, "legacy")
            target = os.path.join(tmp, "data")
            os.makedirs(legacy)
            with open(os.path.join(legacy, "persona.json"), "w", encoding="utf-8") as fh:
                fh.write('{"name":"x"}')
            old_env = os.environ.get("SUGAR_DATA_DIR")
            old_legacy = (paths.LEGACY_STATE_DIR, paths.LEGACY_CONFIG)
            os.environ["SUGAR_DATA_DIR"] = target
            paths.LEGACY_STATE_DIR = legacy
            paths.LEGACY_CONFIG = os.path.join(tmp, "nope.json")
            try:
                moved = paths.migrate_legacy()
                self.assertIn("persona.json", moved)
                self.assertTrue(os.path.exists(os.path.join(target, "persona.json")))
            finally:
                paths.LEGACY_STATE_DIR, paths.LEGACY_CONFIG = old_legacy
                if old_env is None:
                    os.environ.pop("SUGAR_DATA_DIR", None)
                else:
                    os.environ["SUGAR_DATA_DIR"] = old_env


class ConfigTests(unittest.TestCase):
    """配置只放"谁算白名单"这种证据，不放权限；密钥不许进文件。"""

    def _write(self, tmp: str, payload: dict) -> str:
        path = os.path.join(tmp, "config.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        return path

    def test_channels_and_allow_lists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, {
                "channels": {
                    "feishu": {"enabled": True, "allow": ["ou_1"], "allow_groups": ["oc_vip"],
                               "group_members": {"oc_team": 30}},
                    "qq": {"enabled": False},
                }
            })
            config = Config.load(path)
            self.assertEqual(config.enabled_channels(), {"feishu"})
            self.assertIn("feishu:ou_1", config.allowed_principals())
            self.assertIn("ou_1", config.allowed_principals())
            self.assertEqual(config.allowed_groups(), {"oc_vip"})
            self.assertEqual(config.group_members(), {"oc_team": 30})

    def test_plaintext_secret_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, {"channels": {"feishu": {"app_secret": "s3cr3t"}}})
            with self.assertRaises(ValueError):
                Config.load(path)

    def test_missing_file_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Config.load(os.path.join(tmp, "nope.json"))
            self.assertTrue(config.enabled)
            self.assertEqual(config.channels, {})


class PromptReplyTests(unittest.TestCase):
    """卡片发出后，用户的"1"要回填到提问，而不是开新话题。"""

    def _runtime_with_question(self, tmp: str):
        runtime, host, channel = build_runtime(tmp)
        runtime.handle_inbound(inbound("你好", peer="u-owner", message_id="m-1"))
        session_id = host.submitted[0]["session_id"]
        runtime.prompts.add(
            build_prompt(
                kind="question",
                session_id=session_id,
                questions=[Question("q1", "标题", "选哪个", [Option("q1o1", "甲"), Option("q1o2", "乙")])],
            )
        )
        return runtime, host, channel, session_id

    def test_numeric_reply_fills_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, _channel, _sid = self._runtime_with_question(tmp)
            result = runtime.handle_inbound(inbound("2", peer="u-owner", message_id="m-2"))
            self.assertEqual(result.status, "prompt")
            self.assertEqual(len(host.submitted), 1)  # 没有开新一轮
            self.assertEqual(host.resolved[0][1]["answers"][0]["selected_option_ids"], ["q1o2"])

    def test_unrelated_text_still_reaches_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, _channel, _sid = self._runtime_with_question(tmp)
            result = runtime.handle_inbound(inbound("先别管这个，帮我查下天气", peer="u-owner", message_id="m-3"))
            self.assertEqual(result.status, "accepted")
            self.assertEqual(len(host.submitted), 2)

    def test_out_of_range_reply_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, _channel, _sid = self._runtime_with_question(tmp)
            result = runtime.handle_inbound(inbound("9", peer="u-owner", message_id="m-4"))
            self.assertEqual(result.status, "prompt_invalid")
            self.assertEqual(len(host.submitted), 1)


class ChannelStartupTests(unittest.TestCase):
    """没有凭据时要干净降级：坏通道只进 failures，不影响其它通道。"""

    def test_bad_channel_is_isolated(self) -> None:
        started = []

        class Good:
            async def start(self, sink):
                started.append("good")

        class Bad:
            async def start(self, sink):
                raise ValueError("缺少 FEISHU_APP_ID")

        failures = asyncio.run(start_channels({"feishu": Bad(), "fake": Good()}, lambda m: None))
        self.assertEqual(started, ["good"])
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0][0], "feishu")
        self.assertIn("FEISHU_APP_ID", failures[0][1])


class SidecarContractTests(unittest.TestCase):
    """sidecar 契约：JSON Lines 双向，入站能进 Core、出站能拿到回执。"""

    def test_inbound_and_send_roundtrip(self) -> None:
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_sidecar.py")
        self.assertTrue(os.path.exists(script))

        async def scenario():
            received = []

            async def sink(msg):
                received.append(msg)

            channel = SidecarChannel(SidecarSpec(name="fake", script=script, node=sys.executable, send_timeout=5))
            await channel.start(sink)
            for _ in range(50):
                if received:
                    break
                await asyncio.sleep(0.05)
            from sugar_assistant.models import ConversationRef, Delivery

            base = inbound("x")
            ok = channel.send(Delivery(id="d1", channel=base.channel,
                                       conversation=ConversationRef(chat_id="wx-1"), text="收到"))
            bad = channel.send(Delivery(id="d2", channel=base.channel,
                                        conversation=ConversationRef(chat_id="wx-1"), text="失败"))
            await channel.stop()
            return received, ok, bad, channel.health()

        received, ok, bad, health = asyncio.run(scenario())
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].text, "帮我看看这个文件")
        self.assertEqual(received[0].sender.user_id, "wx-1")
        self.assertEqual(ok.outcome.value, "acked")
        self.assertEqual(bad.outcome.value, "unreachable")
        self.assertEqual(health["sent"], 1)


class ServiceTests(unittest.TestCase):
    """Adapter 只需要 await handle(inbound)。"""

    def test_handle_runs_core_and_spawns_relay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, _channel = build_runtime(tmp)
            service = SugarAssistantService(runtime, relay_timeout=0.2)

            async def scenario():
                result = await service.handle(inbound("你好", peer="u-owner", message_id="m-1"))
                await asyncio.sleep(0.05)
                await service.close()
                return result

            result = asyncio.run(scenario())
            self.assertTrue(result.ok)
            self.assertEqual(result.status, "accepted")
            self.assertEqual(len(host.submitted), 1)

    def test_messages_within_window_are_merged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime, host, _channel = build_runtime(tmp)
            service = SugarAssistantService(runtime, relay_timeout=0.1, merge_window_ms=60)

            async def scenario():
                await service.handle(inbound("一", peer="u-owner", message_id="m-1"))
                await service.handle(inbound("二", peer="u-owner", message_id="m-2"))
                await asyncio.sleep(0.25)
                await service.close()

            asyncio.run(scenario())
            self.assertEqual(len(host.submitted), 1)
            self.assertEqual(host.submitted[0]["text"], "一\n\n二")


class BridgeTests(unittest.TestCase):
    """桥接契约：字段名必须和宿主 session_control/service.py 一致。"""

    def test_create_uses_name_and_subject_only(self) -> None:
        service = FakeService()
        host = SugarAgentHost(service)
        session_id = host.create_session(title="你好", subject="fake:u-1")
        self.assertEqual(session_id, "s-bridge")
        call = service.calls[0]
        self.assertEqual(call["method"], "session.create")
        self.assertEqual(call["params"]["name"], "你好")
        self.assertEqual(call["params"]["_subject"], "sugar:fake:u-1")  # 与 created_by 同源
        # 权限不落会话：不能出现 tools / read_only
        self.assertNotIn("tools", call["params"])
        self.assertNotIn("read_only", call["params"])

    def test_send_carries_turn_actor(self) -> None:
        service = FakeService()
        host = SugarAgentHost(service)
        host.submit("s-1", "在吗", op_id="op-9", actor={"_level": "group", "_subject": "fake:u-2", "_source": {"id": "fake"}})
        call = service.calls[0]
        self.assertEqual(call["method"], "session.send")
        self.assertEqual(call["params"]["session_id"], "s-1")
        self.assertEqual(call["params"]["message"], "在吗")
        self.assertEqual(call["params"]["mode"], "queue")
        self.assertEqual(call["params"]["_level"], "group")
        # _subject 必须是主体 id（与 created_by 一致），不是原始用户 key
        self.assertEqual(call["params"]["_subject"], "sugar:fake:u-2")
        self.assertEqual(call["key"], "op-9")

    def test_create_and_send_share_same_subject_key(self) -> None:
        service = FakeService()
        host = SugarAgentHost(service)
        host.create_session(title="hi", subject="feishu:on_1")
        host.submit("s-bridge", "hi", op_id="op-1",
                    actor={"_level": "private", "_subject": "feishu:on_1"})
        create_subject = service.calls[0]["params"]["_subject"]
        send_subject = service.calls[1]["params"]["_subject"]
        self.assertEqual(create_subject, send_subject)
        self.assertEqual(create_subject, "sugar:feishu:on_1")

    def test_create_without_session_id_raises(self) -> None:
        class Broken(FakeService):
            async def execute(self, principal, method, params, *, idempotency_key=""):
                return {}, False

        with self.assertRaises(HostBridgeError):
            SugarAgentHost(Broken()).create_session(title="x")

    def test_question_resolve_is_reported_missing(self) -> None:
        service = FakeService()
        def boom(*_args):
            raise RuntimeError("宿主缺少 human_interaction")

        host = SugarAgentHost(service, resolve_question=boom)
        prompt = _build_prompt(kind="question", session_id="s-1", questions=[])
        with self.assertRaises(HostBridgeError):
            host.resolve_prompt(prompt, {"answers": []})

    def test_question_resolve_calls_host_service(self) -> None:
        calls = []
        host = SugarAgentHost(FakeService(), resolve_question=lambda sid, iid, answers: calls.append((sid, iid, answers)))
        prompt = _build_prompt(kind="question", session_id="s-1", prompt_id="i-1", questions=[])
        host.resolve_prompt(prompt, {"answers": [{"question_id": "q1", "selected_option_ids": ["q1o2"]}]})
        self.assertEqual(calls[0][0], "s-1")
        self.assertEqual(calls[0][1], "i-1")
        self.assertEqual(calls[0][2][0]["selected_option_ids"], ["q1o2"])

    def test_revoked_source_is_refreshed_once(self) -> None:
        """热重载后旧代理被判授权撤销：换新代理重试，而不是整条消息失败。"""

        class RevokedOnce:
            def __init__(self):
                self.calls = 0

            async def execute(self, principal, method, params, *, idempotency_key=""):
                self.calls += 1
                raise RuntimeError("Plugin authorization was revoked")

        fresh = FakeService()
        host = SugarAgentHost(RevokedOnce(), service_factory=lambda: fresh)
        host.create_session(title="x")
        self.assertEqual(len(fresh.calls), 1)

    def test_approval_uses_approve_flag(self) -> None:
        service = FakeService()
        host = SugarAgentHost(service)
        prompt = _build_prompt(kind="approval", session_id="s-1", prompt_id="a-1",
                               approval_options=[Option("allow_once", "同意"), Option("deny", "拒绝")])
        host.resolve_prompt(prompt, {"decision": "approve"})
        call = service.calls[0]
        self.assertEqual(call["method"], "approval.resolve")
        self.assertEqual(call["params"]["approval_id"], "a-1")
        self.assertIs(call["params"]["approve"], True)
        self.assertNotIn("decision", call["params"])

    def test_in_loop_call_fails_fast(self) -> None:
        service = FakeService()
        host = SugarAgentHost(service)

        async def scenario():
            return host.create_session(title="x")

        with self.assertRaises(HostBridgeError):
            asyncio.run(scenario())

    def test_call_uses_bound_host_loop(self) -> None:
        """Core 在 worker 线程里跑，必须把协程交回宿主 loop，而不是新开一个。"""
        service = FakeService()
        host = SugarAgentHost(service)
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        try:
            host.bind_loop(loop)
            self.assertEqual(host.create_session(title="x"), "s-bridge")
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=2)
            loop.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
