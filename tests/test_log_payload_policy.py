"""静态护栏：日志调用不得把模型/用户/工具正文写进 record。"""
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"

# 只匹配"已知会把 payload 塞进日志"的写法；规则用拼接书写，避免本文件自匹配。
BANNED = (
    (r"工具调用:\s*\{", "工具调用行必须使用结构化摘要，不得拼接参数"),
    (r"str\(\s*res\[[\"']tool_args[\"']\]\s*\)", "不得把 tool_args 原文写进日志"),
    (r"raw_args\[:\s*\d+\]", "不得记录模型生成的参数片段"),
    (r"\bdata\[:200\]", "不得记录模型流式分片原文"),
    (r"logger\.[a-z]+\(f\"用户输入", "用户输入只能记录指纹"),
)


def _iter_sources():
    for path in sorted(APP_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def test_app_log_calls_do_not_embed_payloads():
    violations = []
    for path in _iter_sources():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern, reason in BANNED:
            for match in re.finditer(pattern, text):
                line = text.count("\n", 0, match.start()) + 1
                violations.append(f"{path.relative_to(APP_DIR.parent)}:{line} {reason}")
    assert violations == [], "\n".join(violations)


def test_payload_gate_exists_for_full_trace():
    """完整请求链只能在 LOG_PAYLOAD_MODE=full 下输出。"""
    loop = (APP_DIR / "agent_loop.py").read_text(encoding="utf-8")
    assert "log_safety.payload_enabled()" in loop
    assert loop.count("\">>> Agent to LLM:\"") == 1
