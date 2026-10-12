import asyncio

import pytest

from app import notification_providers


@pytest.fixture(autouse=True)
def isolated_providers(monkeypatch):
    monkeypatch.setattr(notification_providers, "_providers", {})


def test_legacy_provider_receives_session_notification_without_extra_argument():
    received = []

    def legacy(title, message):
        received.append((title, message))

    notification_providers.register_notification_provider("legacy", legacy)
    failures = asyncio.run(notification_providers.notify_user("SugarAgent", "Completed", "session-1"))

    assert failures == []
    assert received == [("SugarAgent", "Completed")]


def test_provider_internal_type_error_is_not_retried_and_other_providers_continue():
    received = []

    def broken(title, message, session_id):
        received.append("broken")
        raise TypeError("provider implementation failed")

    async def modern(title, message, session_id):
        received.append(session_id)

    notification_providers.register_notification_provider("broken", broken)
    notification_providers.register_notification_provider("modern", modern)
    failures = asyncio.run(notification_providers.notify_user("SugarAgent", "Completed", "session-1"))

    assert failures == ["broken: provider implementation failed"]
    assert received == ["broken", "session-1"]
