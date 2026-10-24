"""Small provider registry for optional user-notification channels."""
from __future__ import annotations

import inspect
from collections import OrderedDict
from typing import Any, Callable


_providers: "OrderedDict[str, Callable[..., Any]]" = OrderedDict()


def register_notification_provider(
    provider_id: str, callback: Callable[..., Any], *, replace: bool = False
) -> None:
    key = str(provider_id or "").strip()
    if not key or not callable(callback):
        raise ValueError("notification provider requires an id and callable")
    if key in _providers and not replace:
        raise ValueError(f"notification provider already registered: {key}")
    _providers[key] = callback


def unregister_notification_provider(provider_id: str) -> None:
    _providers.pop(str(provider_id or "").strip(), None)


async def notify_user(
    title: str = "",
    message: str = "",
    session_id: str = "",
    *,
    provider_ids: tuple[str, ...] | None = None,
) -> list[str]:
    """Dispatch a notification; ``session_id`` lets providers deep-link to it.

    Providers registered with the legacy two-argument signature keep working:
    the session id is appended only when the callback accepts it.
    ``provider_ids`` selects specific channels; omitted, all providers receive it.
    """
    failures: list[str] = []
    for provider_id, callback in tuple(_providers.items()):
        if provider_ids is not None and provider_id not in provider_ids:
            continue
        try:
            if not (title or message):
                value = callback()
            elif session_id:
                args = (title, message, str(session_id))
                try:
                    signature = inspect.signature(callback)
                except (TypeError, ValueError):
                    signature = None
                if signature is not None:
                    try:
                        signature.bind(*args)
                    except TypeError:
                        # Check compatibility before invoking: a TypeError
                        # raised inside a provider must never cause a retry.
                        signature.bind(title, message)
                        args = (title, message)
                value = callback(*args)
            else:
                value = callback(title, message)
            if inspect.isawaitable(value):
                await value
        except Exception as exc:
            failures.append(f"{provider_id}: {exc}")
    return failures


def notification_provider_ids() -> tuple[str, ...]:
    return tuple(_providers)


__all__ = [
    "notification_provider_ids",
    "notify_user",
    "register_notification_provider",
    "unregister_notification_provider",
]
