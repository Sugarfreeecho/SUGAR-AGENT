import asyncio
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sugar_assistant.models import ChannelId, ConversationRef, Delivery  # noqa: E402
from sugar_assistant.runtime import TransportRuntime  # noqa: E402


class BridgeFallbackTests(unittest.IsolatedAsyncioTestCase):
    def _runtime(self):
        runtime = object.__new__(TransportRuntime)
        runtime._log = lambda *a, **k: None
        return runtime

    def _delivery(self, error="[230002] bot not in chat", chat_name="王影"):
        return Delivery(
            id="d-1",
            channel=ChannelId(channel="feishu"),
            conversation=ConversationRef(chat_id="oc_ext"),
            text="你好",
            meta={"chat_name": chat_name},
            last_error=error,
        )

    async def test_bridge_called_for_external_p2p_error(self):
        calls = []

        async def fake_call(caller, service, method, params):
            calls.append((caller, service, method, params))
            return {"ok": True}

        fake = types.SimpleNamespace(available=lambda name: True, call=fake_call)
        sys.modules["plugin_bus"] = fake
        os.environ["SUGAR_WEB_TENANT"] = "x.feishu.cn"
        try:
            self._runtime()._schedule_bridge(self._delivery())
            await asyncio.sleep(0.05)
            self.assertTrue(calls)
            self.assertEqual(calls[0][2], "send_text")
            self.assertEqual(calls[0][3]["chat_name"], "王影")
        finally:
            sys.modules.pop("plugin_bus", None)

    async def test_other_errors_do_not_use_bridge(self):
        calls = []

        async def fake_call(*args):
            calls.append(args)

        fake = types.SimpleNamespace(available=lambda name: True, call=fake_call)
        sys.modules["plugin_bus"] = fake
        try:
            self._runtime()._schedule_bridge(self._delivery(error="[230001] bad param"))
            await asyncio.sleep(0.05)
            self.assertFalse(calls)
        finally:
            sys.modules.pop("plugin_bus", None)
