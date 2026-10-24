"""Bounded, single-flight cache for display metadata (never execution policy)."""
from __future__ import annotations

from concurrent.futures import Future
from copy import deepcopy
import logging
from threading import Lock, Thread
from time import monotonic
from typing import Callable


class MetadataCache:
    def __init__(self, ttl: float = 10.0, *, stale_while_revalidate: bool = False):
        self.ttl = ttl
        self.stale_while_revalidate = stale_while_revalidate
        self._lock = Lock()
        self._entry = None
        self._current_key = None
        self._pending: dict[tuple, Future] = {}

    def get(self, key: tuple, build: Callable[[], dict]) -> dict:
        with self._lock:
            self._current_key = key
            entry = self._entry
            fresh = entry and entry[0] == key and monotonic() < entry[1]
            stale = entry and entry[0] == key and self.stale_while_revalidate
            if fresh:
                value = entry[2]
                pending = None
                owner = False
            else:
                pending = self._pending.get(key)
                owner = pending is None
                if owner:
                    pending = self._pending[key] = Future()
        if fresh:
            return deepcopy(value)
        if stale:
            if owner:
                Thread(target=self._refresh, args=(key, build, pending), daemon=True, name='ui-metadata-refresh').start()
            return deepcopy(entry[2])
        if not owner:
            return deepcopy(pending.result())
        return deepcopy(self._build(key, build, pending))

    def _refresh(self, key, build, pending):
        try:
            self._build(key, build, pending)
        except Exception:
            logging.getLogger(__name__).warning('UI metadata refresh failed', exc_info=True)

    def _build(self, key, build, pending):
        try:
            value = build()
            with self._lock:
                if self._current_key == key:
                    self._entry = (key, monotonic() + self.ttl, value)
            pending.set_result(value)
            return value
        except BaseException as error:
            pending.set_exception(error)
            raise
        finally:
            with self._lock:
                if self._pending.get(key) is pending:
                    del self._pending[key]
