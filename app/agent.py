"""
对外入口：ReAct 流式事件 + 会话管理。

供 Web UI、脚本等 `from agent import astream_events, session_manager` 使用。
"""

from agent_loop import (
    astream_events,
    astream_events_continuation,
    is_session_title_generation_pending,
)
from agent_harness import session_manager

__all__ = [
    "astream_events",
    "astream_events_continuation",
    "is_session_title_generation_pending",
    "session_manager",
]
