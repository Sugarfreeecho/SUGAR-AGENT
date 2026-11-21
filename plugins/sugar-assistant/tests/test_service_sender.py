import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sugar_assistant.channels.feishu_worker import is_service_sender  # noqa: E402


class ServiceSenderTests(unittest.TestCase):
    def test_app_sender_filtered(self):
        self.assertTrue(is_service_sender({"sender_type": "app", "name": "账号安全中心"}))

    def test_agent_flag_filtered(self):
        self.assertTrue(is_service_sender({"sender_type": "user", "is_agent": True}))

    def test_human_sender_kept(self):
        self.assertFalse(is_service_sender({"sender_type": "user", "name": "王影"}))

    def test_bot_sender_kept(self):
        self.assertFalse(is_service_sender({"sender_type": "bot", "name": "小Sugar助手"}))
