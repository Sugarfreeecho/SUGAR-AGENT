import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sugar_assistant.channels.feishu_worker import card_payload_10  # noqa: E402


class CardPayloadTests(unittest.TestCase):
    def test_header_and_actions(self):
        payload = card_payload_10({"title": "确认", "body": "要执行吗",
                                   "options": [{"label": "是", "value": "q1:1"},
                                               {"label": "否", "value": "q1:2"}]})
        self.assertEqual(payload["header"]["title"]["content"], "确认")
        tags = [element["tag"] for element in payload["elements"]]
        self.assertIn("markdown", tags)
        self.assertIn("action", tags)
        actions = next(e for e in payload["elements"] if e["tag"] == "action")["actions"]
        self.assertEqual([a["value"]["choice"] for a in actions], ["q1:1", "q1:2"])
        self.assertEqual(actions[0]["type"], "primary")

    def test_sections_shape(self):
        payload = card_payload_10({"title": "t", "sections": [
            {"body": "a", "options": []}, {"body": "b", "options": [{"label": "x", "value": "y"}]}]})
        markdowns = [e for e in payload["elements"] if e["tag"] == "markdown"]
        self.assertEqual(len(markdowns), 2)
        self.assertEqual(len([e for e in payload["elements"] if e["tag"] == "action"]), 1)
