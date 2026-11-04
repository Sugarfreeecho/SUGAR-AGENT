import asyncio
import time

import pytest

from tests.test_ui_attention_notifications import _isolate_attention_delivery


@pytest.mark.parametrize('reason', ['completed', 'failed', 'pending'])
def test_focused_sidebar_suppresses_attention_until_blurred(monkeypatch, reason):
    import webui
    async def scenario():
        delivered = _isolate_attention_delivery(monkeypatch)
        webui.update_ui_attention_surface('sidebar:a', True)
        webui._schedule_ui_attention_notify('session-1', reason)
        assert webui._ui_attention_notify_task is None and delivered == []
        assert webui._ui_presence_has_open_pages() is False
        assert webui._ui_presence_has_reusable() is False
        webui.update_ui_attention_surface('sidebar:a', False)
        if reason == 'pending':
            monkeypatch.setattr(webui, '_session_pending_human_count', lambda _: 1)
        webui._schedule_ui_attention_notify('session-1', reason)
        await webui._ui_attention_notify_task
        assert delivered == [(reason, 'session-1')]
    asyncio.run(scenario())


def test_focus_during_notification_grace_cancels_attention_and_closed_ui_toast(monkeypatch):
    import webui
    async def scenario():
        delivered = _isolate_attention_delivery(monkeypatch)
        monkeypatch.setattr(webui, '_UI_CLOSED_NOTIFY_GRACE_SEC', 10)
        webui._schedule_ui_attention_notify('session-1', 'completed')
        pending = webui._ui_attention_notify_task
        await asyncio.sleep(0)
        webui.update_ui_attention_surface('sidebar:a', True)
        await pending
        assert delivered == [] and webui._ui_attention_notify_reasons == {}
        webui.update_ui_attention_surface('sidebar:a', False)
        await webui._schedule_ui_closed_notify()
        closed = webui._ui_closed_notify_task
        await asyncio.sleep(0)
        webui.update_ui_attention_surface('sidebar:a', True)
        await closed
        assert delivered == []
    asyncio.run(scenario())


def test_sidebar_leases_expire_and_do_not_remove_another_focused_surface(monkeypatch):
    import webui
    _isolate_attention_delivery(monkeypatch)
    webui.update_ui_attention_surface('sidebar:a', True)
    webui.update_ui_attention_surface('sidebar:b', True)
    webui.update_ui_attention_surface('sidebar:a', False)
    assert webui._ui_presence_has_active()
    monkeypatch.setattr(webui, '_ui_attention_surfaces', {'stale': time.time()-31})
    assert not webui._ui_presence_has_active()
    assert webui._ui_attention_surfaces == {}


def test_focused_sidebar_also_blocks_generic_closed_window_toast(monkeypatch):
    import webui
    async def scenario():
        delivered = _isolate_attention_delivery(monkeypatch)
        webui.update_ui_attention_surface('sidebar:a', True)
        await webui._schedule_ui_closed_notify()
        await webui._ui_closed_notify_task
        assert delivered == []
    asyncio.run(scenario())
