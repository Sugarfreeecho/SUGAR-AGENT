"""Trusted adapter for the platform-specific desktop notification provider."""

import asyncio


async def _notify(title, message, session_id="", target=None):
    from desktop_notify import show_desktop_notification

    # Native notification helpers wait for delivery. Keep the ASGI event loop
    # available for focus updates, streaming, and other session completions.
    if target:
        await asyncio.to_thread(show_desktop_notification, title, message, session_id, target)
    else:
        await asyncio.to_thread(show_desktop_notification, title, message, session_id)


def _register(plugin):
    from notification_providers import register_notification_provider

    register_notification_provider(
        plugin.plugin_id, _notify, replace=True
    )


def install(_app, _context, plugin):
    _register(plugin)


async def start(_context, plugin):
    # Lifespan can restart in the same interpreter after stop() removed the sink.
    _register(plugin)


async def stop(_context, plugin):
    from notification_providers import unregister_notification_provider

    unregister_notification_provider(plugin.plugin_id)
