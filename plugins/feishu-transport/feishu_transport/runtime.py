from __future__ import annotations

import threading

from remote_control.service import ControlDependencies, SessionControlService
from remote_control.store import RemoteControlStore

from .adapter import FeishuTransportAdapter
from .config import FeishuConfig
from .store import FeishuStateStore


class FeishuRuntimeManager:
    """Owns Feishu transport lifecycle without import-time network activity."""

    def __init__(
        self,
        config: FeishuConfig,
        dependencies: ControlDependencies,
        *,
        shared_service: SessionControlService | None = None,
    ):
        self.config = config
        self.dependencies = dependencies
        self.shared_service = shared_service
        self._adapter: FeishuTransportAdapter | None = None
        self._lock = threading.RLock()

    @property
    def adapter(self) -> FeishuTransportAdapter | None:
        return self._adapter

    def start(self) -> FeishuTransportAdapter | None:
        if not self.config.enabled:
            return None
        self.config.validate()
        with self._lock:
            if self._adapter is not None:
                return self._adapter
            service = self.shared_service
            if service is None:
                control_store = RemoteControlStore(self.config.state_dir / "control-plane")
                service = SessionControlService(self.dependencies, control_store)
            adapter = FeishuTransportAdapter(
                self.config,
                service,
                FeishuStateStore(self.config.state_dir),
            )
            adapter.start()
            self._adapter = adapter
            return adapter

    def stop(self) -> None:
        with self._lock:
            adapter = self._adapter
            self._adapter = None
        if adapter is not None:
            adapter.stop()
