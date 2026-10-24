"""Wake sidebar long polls when a committed session summary changes."""

import asyncio
import threading


class SessionStateSignal:
    def __init__(self, revision=0):
        self.revision = revision
        self.lock = threading.Lock()
        self.waiters = set()

    def publish(self, revision):
        with self.lock:
            self.revision = max(self.revision, revision)
            waiters = list(self.waiters)
        for loop, event in waiters:
            try:
                loop.call_soon_threadsafe(event.set)
            except RuntimeError:  # The browser's request loop has closed.
                pass

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
