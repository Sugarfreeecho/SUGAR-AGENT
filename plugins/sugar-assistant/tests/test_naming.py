import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sugar_assistant.models import ChannelId, ConversationRef, Inbound, Principal  # noqa: E402
from sugar_assistant.runtime import TransportRuntime  # noqa: E402


def _inbound(kind, chat_id, name=""):
    return Inbound(
        channel=ChannelId("feishu"),
        conversation=ConversationRef(chat_id=chat_id, kind=kind),
        sender=Principal("feishu", "ou_x"),
        message_id="m",
        text="hi",
        raw={"chatName": name} if name else {},
    )


class NamingRuleTests(unittest.TestCase):
    def test_private_title_uses_contact_name(self):
        self.assertEqual(TransportRuntime._title_for(_inbound("p2p", "oc_abc", "王影")),
                         "小Sugar私聊-王影")

    def test_private_title_without_name_keeps_prefix(self):
        self.assertEqual(TransportRuntime._title_for(_inbound("p2p", "oc_123456789abcdef")),
                         "小Sugar私聊")

    def test_group_title_uses_group_name(self):
        self.assertEqual(TransportRuntime._title_for(_inbound("group", "oc_123", "吴淑舸, 王影")),
                         "小Sugar群聊-吴淑舸, 王影")

    def test_group_title_without_name_keeps_prefix(self):
        self.assertEqual(TransportRuntime._title_for(_inbound("group", "oc_123")), "小Sugar群聊")
