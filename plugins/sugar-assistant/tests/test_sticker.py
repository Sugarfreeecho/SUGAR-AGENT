import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sugar_assistant.channels import feishu_worker  # noqa: E402


class StickerPayloadTests(unittest.TestCase):
    def test_payload_shape(self):
        body = feishu_worker.sticker_payload("oc_123", "img_v3_x")
        self.assertEqual(body["msg_type"], "sticker")
        self.assertEqual(json.loads(body["content"]), {"file_key": "img_v3_x"})

    def test_missing_key(self):
        with self.assertRaises(ValueError):
            feishu_worker.sticker_payload("oc_123", "")


class StickerStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sugar-sticker-")
        self._orig = feishu_worker.data_dir
        feishu_worker.data_dir = lambda path="": os.path.join(self.tmp, path) if path else self.tmp

    def tearDown(self):
        feishu_worker.data_dir = self._orig

    def test_remember_and_latest(self):
        feishu_worker.remember_sticker("k1")
        feishu_worker.remember_sticker("k2")
        feishu_worker.remember_sticker("k1")
        self.assertEqual(feishu_worker.latest_sticker_key(), "k1")
        self.assertEqual(json.load(open(os.path.join(self.tmp, "stickers.json"), encoding="utf-8")),
                         ["k1", "k2"])
