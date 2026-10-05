from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from execution_services.jobs import ExecutionService  # noqa: E402
from execution_services.notifications import _initialize_owner  # noqa: E402


class FakeManager:
    def __init__(self, root):
        self.repository = SimpleNamespace(sessions_dir=root)

    def _resolve_session_path(self, owner):
        return self.repository.sessions_dir / owner

    def is_interrupt_requested(self, owner, run_id=""):
        return False


def _events(session_dir: Path):
    path = session_dir / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _panel_rows(session_dir: Path):
    return [
        event
        for event in _events(session_dir)
        if event.get("type") == "extension_state_changed"
        and (event.get("payload") or {}).get("namespace") == "panel"
    ]


def test_panel_bootstrap_writes_state_once_per_session(tmp_path):
    """宿主（重新）启动只补齐缺失的面板状态。

    回归：每次启动都为每个会话重写一次面板状态，控制事件把事件日志变成「刚活动」，
    侧栏所有会话被顶成「今天」并重排。
    """
    owner = "owner"
    (tmp_path / owner).mkdir()
    service = ExecutionService(FakeManager(tmp_path))
    try:
        asyncio.run(_initialize_owner(service, owner))
        asyncio.run(_initialize_owner(service, owner))  # 模拟下一次宿主启动
        rows = _panel_rows(tmp_path / owner)
        assert [row["payload"]["revision"] for row in rows] == [1]
        assert rows[0]["payload"]["value"] == {"enabled": True}
    finally:
        asyncio.run(service.shutdown())


def test_panel_bootstrap_keeps_existing_session_state(tmp_path):
    """会话已有面板状态时保持原值与 revision，不再追加事件。"""
    owner = "owner"
    session_dir = tmp_path / owner
    session_dir.mkdir()
    service = ExecutionService(FakeManager(tmp_path))

    async def preload():
        await service.call(service.persist, owner, "panel", {"enabled": True, "pinned": True})

    try:
        asyncio.run(preload())
        before = _panel_rows(session_dir)
        assert [row["payload"]["revision"] for row in before] == [1]
        asyncio.run(_initialize_owner(service, owner))
        after = _panel_rows(session_dir)
        assert [row["payload"]["revision"] for row in after] == [1]
        assert after[0]["payload"]["value"] == {"enabled": True, "pinned": True}
    finally:
        asyncio.run(service.shutdown())


def test_panel_bootstrap_without_session_manager_is_noop():
    """没有会话管理器（纯进程内执行服务）时不写任何事实。"""
    service = ExecutionService()

    async def run():
        try:
            await _initialize_owner(service, "owner")
        finally:
            await service.shutdown()

    asyncio.run(run())
