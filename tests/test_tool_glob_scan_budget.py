"""Regression tests for glob junction cycles and scan budgets."""
from __future__ import annotations

import os
import subprocess
import time
import asyncio
import threading

import pytest

import agent_tools
import tool_cancel


def _mklink_junction(link, target) -> bool:
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
    )
    return result.returncode == 0 and os.path.isdir(str(link))


@pytest.fixture(autouse=True)
def _no_windows_index(monkeypatch):
    monkeypatch.setenv("GLOB_USE_WINDOWS_INDEX", "0")
    monkeypatch.delenv("GLOB_INCLUDE_IGNORED", raising=False)


def test_glob_prunes_dependency_trees_by_default(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "real-image.ts").write_text("", encoding="utf-8")
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "dep-image.ts").write_text("", encoding="utf-8")

    result = agent_tools.glob("**/*[Ii]mage*.ts", path=str(tmp_path))

    assert "real-image.ts" in result
    assert "dep-image.ts" not in result

    monkeypatch.setenv("GLOB_INCLUDE_IGNORED", "1")
    with_ignored = agent_tools.glob("**/*[Ii]mage*.ts", path=str(tmp_path))
    assert "dep-image.ts" in with_ignored


@pytest.mark.skipif(os.name != "nt", reason="junctions are Windows-only")
def test_glob_does_not_follow_junction_cycles(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    link_ab = a / "loop"
    link_ba = b / "loop"
    if not (_mklink_junction(link_ab, b) and _mklink_junction(link_ba, a)):
        pytest.skip("cannot create directory junctions in this environment")

    try:
        (a / "wanted-image.ts").write_text("", encoding="utf-8")
        started = time.monotonic()
        result = agent_tools.glob("**/*[Ii]mage*.ts", path=str(tmp_path))
        elapsed = time.monotonic() - started

        assert "wanted-image.ts" in result
        assert elapsed < 10, f"glob followed the junction cycle for {elapsed:.1f}s"
    finally:
        for link in (link_ab, link_ba):
            subprocess.run(["cmd", "/c", "rmdir", str(link)], capture_output=True)


def test_glob_stops_at_match_cap(tmp_path, monkeypatch):
    for name in ("a", "b", "c"):
        (tmp_path / f"{name}-image.ts").write_text("", encoding="utf-8")
    monkeypatch.setenv("GLOB_MAX_MATCHES", "2")

    result = agent_tools.glob("**/*[Ii]mage*.ts", path=str(tmp_path))

    assert "more paths omitted" in result
    assert "GLOB_MAX_MATCHES=2" in result


def test_glob_reports_scan_budget(tmp_path, monkeypatch):
    (tmp_path / "a-image.ts").write_text("", encoding="utf-8")
    (tmp_path / "b-image.ts").write_text("", encoding="utf-8")
    monkeypatch.setenv("GLOB_MAX_SCAN_ENTRIES", "1")

    result = agent_tools.glob("**/*[Ii]mage*.ts", path=str(tmp_path))

    assert "scan stopped early: entries" in result


def test_cancel_event_reaches_worker_threads():
    event = threading.Event()

    async def scenario():
        token = tool_cancel.set_cancel_event(event)
        try:
            return await asyncio.to_thread(tool_cancel.current_cancel_event)
        finally:
            tool_cancel.reset_cancel_event(token)

    assert asyncio.run(scenario()) is event


def test_glob_stops_when_cancel_event_is_set(tmp_path):
    (tmp_path / "a-image.ts").write_text("", encoding="utf-8")
    event = threading.Event()
    event.set()
    token = tool_cancel.set_cancel_event(event)
    try:
        result = agent_tools.glob("**/*[Ii]mage*.ts", path=str(tmp_path))
    finally:
        tool_cancel.reset_cancel_event(token)

    assert "scan stopped early: cancelled" in result


def test_read_tool_timeout_returns_failure_result(monkeypatch):
    import agent_loop

    async def slow_tool():
        await asyncio.sleep(5)

    monkeypatch.setattr(agent_loop, "READ_TOOL_TIMEOUT_SEC", 0.05)
    result = asyncio.run(
        agent_loop._await_read_tool({"name": "glob", "id": "call_1"}, slow_tool())
    )

    assert result["tool_failed"] is True
    assert "timed out after 0.05s" in result["result"]
    assert tool_cancel.current_cancel_event() is None
