import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sugar_assistant import web_api  # noqa: E402

_TMP = tempfile.mkdtemp(prefix="sugar-test-")
web_api.data_dir = lambda path="": os.path.join(_TMP, path) if path else _TMP  # noqa: E731

# 与 cv-cat/OpenFeiShuApis 的 ProtoBuilder 输出逐字节一致（cid/request_id 固定）
EXPECTED = (
    "100118052a530804122a72280a0a434944303030303030311201581a170a150a0a43494430303030303031"
    "120708011a030a01581a1337373039303536363233373932303938343838320a4349443030303030303138"
    "0148013206726964313233"
)


class WebApiPacketTests(unittest.TestCase):
    def test_text_packet_matches_reference(self):
        body = web_api.build_text_packet("X", "7709056623792098488", "rid123", cid="CID0000001")
        self.assertEqual(body.hex(), EXPECTED)

    def test_missing_mapping_fails_fast(self):
        result = web_api.send_text("oc_unknown", "hi", "无名", {"tenant": "x.feishu.cn"})
        self.assertEqual(result["status"], "failed")
        self.assertIn("映射", result["detail"])

    def test_rate_limit(self):
        import time as _time
        web_api._SENT.clear()
        for _ in range(web_api.RATE_LIMIT):
            web_api._SENT.append(_time.time())
        result = web_api.send_text("oc_unknown", "hi", "", {"tenant": "x.feishu.cn"})
        self.assertEqual(result["status"], "failed")
        self.assertIn("限流", result["detail"])
        web_api._SENT.clear()

    def test_sticker_packet(self):
        body = web_api.build_sticker_packet("img_v3_x", "7709", "rid123", cid="CID0000001")
        self.assertIn(b"img_v3_x", body)
        self.assertIn(bytes([0x08, 0x0A]), body)  # type=10 STICKER

    def test_post_packet(self):
        body = web_api.build_post_packet("hello", "7709", "rid123", cid="CID0000001")
        self.assertIn(b"hello", body)
        self.assertIn(bytes([0x08, 0x02]), body)  # type=2 POST
