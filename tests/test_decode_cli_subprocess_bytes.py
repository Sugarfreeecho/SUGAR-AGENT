"""Regression tests for _decode_cli_subprocess_bytes encoding fallbacks.

背景（2026-10 乱码诊断）：旧实现把“UTF-8 解码成功但结果含 U+FFFD”误判为解码失败，
随后整套按 GBK 重解，会把原本合法的 UTF-8 文本改写成 GBK 误码（如 U+FFFD → “锟絓”），
并吞掉相邻标点。修复后：仅当 UTF-8 严格解码失败时才尝试 GBK。
"""
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import agent_tools  # noqa: E402


@pytest.fixture()
def on_windows(monkeypatch):
    monkeypatch.setattr(agent_tools.platform, "system", lambda: "Windows")


def test_utf8_with_replacement_char_is_not_recoded(on_windows):
    # 最小复现用例：反斜杠包裹的 U+FFFD 曾被整套按 GBK 改写（第二个反斜杠被吞）。
    data = "B2 \\\"\ufffd\\\" ENDB\n".encode("utf-8")
    out = agent_tools._decode_cli_subprocess_bytes(data)
    assert out == "B2 \\\"\ufffd\\\" ENDB\n"
    assert "\u951f" not in out
    assert "\u7d53" not in out


def test_plain_utf8_passthrough(on_windows):
    data = "中文测试 utf-8 \u2713".encode("utf-8")
    assert agent_tools._decode_cli_subprocess_bytes(data) == "中文测试 utf-8 \u2713"


def test_replacement_char_with_cjk_excerpt_roundtrip(on_windows):
    text = ' text contains "\ufffd" (U+FFFD) or mojibake like "\u951f\u65a4\u62f7" then'
    assert agent_tools._decode_cli_subprocess_bytes(text.encode("utf-8")) == text


def test_genuine_gbk_bytes_still_decode(on_windows):
    data = "中文GBK".encode("gbk")
    assert agent_tools._decode_cli_subprocess_bytes(data) == "中文GBK"


def test_invalid_for_both_codecs_falls_back_to_replacement(on_windows):
    out = agent_tools._decode_cli_subprocess_bytes(b"\xff\xff")
    assert out == "\ufffd\ufffd"


def test_mixed_gbk_and_utf8_lines_both_decode(on_windows):
    # 混合编码流（如 PowerShell 的 GBK 输出 + Python 的 UTF-8 输出）逐行择优解码。
    data = "日期 2026年10月3日\n".encode("gbk") + "状态 中文测试\n".encode("utf-8")
    out = agent_tools._decode_cli_subprocess_bytes(data)
    assert "日期 2026年10月3日" in out
    assert "状态 中文测试" in out
    assert "\ufffd" not in out


def test_pure_gbk_multiline_still_decodes(on_windows):
    text = "第一行\n第二行 测试GBK\n"
    assert agent_tools._decode_cli_subprocess_bytes(text.encode("gbk")) == text


def test_utf8_line_with_stray_bad_byte_stays_utf8(on_windows):
    # 单行只含个别坏字节时不应整行改写为 GBK；保持可读并以替换符标注坏字节。
    data = b"OK \xff" + "中文测试".encode("utf-8") + b"\n"
    assert agent_tools._decode_cli_subprocess_bytes(data) == "OK \ufffd中文测试\n"
