"""Wake sidebar long polls when a committed session summary changes."""

import asyncio
import threading
from collections import deque


class SessionStateSignal:
    def __init__(self, revision=0):
        self.revision = revision
        self.lock = threading.Lock()
        self.waiters = set()
        self.terminal_events = deque(maxlen=256)

    def publish(self, revision, terminal_event=None):
        with self.lock:
            self.revision = max(self.revision, revision)
            if terminal_event is not None:
                self.terminal_events.append({**terminal_event, "state_revision": revision})
            waiters = list(self.waiters)
        for loop, event in waiters:
            try:
                loop.call_soon_threadsafe(event.set)
            except RuntimeError:  # The browser's request loop has closed.
                pass

    def changes_since(self, after_revision):
        """Return lifecycle facts and their cursor together, without disk reads."""
        with self.lock:
            payload = {"state_revision": self.revision}
            events = [dict(event) for event in self.terminal_events
                      if event["state_revision"] > after_revision]
            if events:
                payload["terminal_events"] = events
            return payload

    async def wait(self, after_revision, timeout=25):
        loop = asyncio.get_running_loop()
        event = asyncio.Event()
        waiter = (loop, event)
        with self.lock:
            if self.revision > after_revision:
                return self.revision
            self.waiters.add(waiter)
        try:
            try:
                await asyncio.wait_for(event.wait(), timeout)
            except asyncio.TimeoutError:
                pass
            with self.lock:
                return self.revision
        finally:
            with self.lock:
                self.waiters.discard(waiter)
