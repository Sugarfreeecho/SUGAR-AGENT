"""One unclaimed server draft, independent of users' in-progress drafts."""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


class SessionDraftReserve:
    def __init__(self, manager):
        self.manager = manager
        self.condition = threading.Condition()
        self.ready_id = None
        self.stopped = False
        self.thread = threading.Thread(target=self._run, name="session-draft-reserve", daemon=True)

    def start(self):
        self.thread.start()

    def take(self):
        # Transfer ownership before any caller does filesystem I/O. A second
        # request must never receive the same ID, even while refill is running.
        with self.condition:
            sid, self.ready_id = self.ready_id, None
            self.condition.notify_all()
            return sid

    def stop(self):
        with self.condition:
            self.stopped = True
            self.condition.notify_all()
        self.thread.join(timeout=5)

    def _recover(self):
        for row in list(self.manager.index):
            if not row.get("draft"):
                continue
            sid = row["id"]
            metadata = self.manager._load_metadata(sid)
            if metadata.get("draft") and metadata.get("standby_draft") and not metadata.get("archived"):
                return sid
        return None

    def _run(self):
        recover = True
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.stopped or self.ready_id is None)
                if self.stopped:
                    return
            try:
                sid = self._recover() if recover else None
                recover = False
                if not sid:
                    sid = self.manager._create_new_session(draft=True, standby=True)[0]
                with self.condition:
                    self.ready_id = sid
                    self.condition.notify_all()
            except Exception:
                logger.warning("Session draft reserve refill failed; creation will fall back", exc_info=True)
                with self.condition:
                    if self.stopped:
                        return
                    self.condition.wait(timeout=5)
