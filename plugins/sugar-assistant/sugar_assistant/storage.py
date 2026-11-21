"""极小的 JSON 持久化：原子写 + 容错读。

不用数据库：这一层的状态都是"小而热"的（绑定、幂等表、待答映射），
单文件足够；坏文件也只丢一次写，不会让插件起不来。
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from typing import Any


class JsonStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.RLock()

    def read(self) -> dict[str, Any]:
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                return {}
            return data if isinstance(data, dict) else {}

    def write(self, data: dict[str, Any]) -> None:
        with self._lock:
            directory = os.path.dirname(os.path.abspath(self.path))
            os.makedirs(directory, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
                os.replace(tmp, self.path)
            finally:
                if os.path.exists(tmp):
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass

    def update(self, mutate):
        with self._lock:
            data = self.read()
            result = mutate(data)
            self.write(data)
            return result
