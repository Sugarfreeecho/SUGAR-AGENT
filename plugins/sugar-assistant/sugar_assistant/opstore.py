"""幂等与操作状态机。

一条入站消息 = 一个 op。规则：
  * `(channel, account, message_id)` 唯一索引，重复到达直接返回 None；
  * 状态只往前走：received → admitted → queued → running → done|failed|cancelled；
  * 执行幂等比消息幂等更重要：宁可漏发一条，不可重复跑一轮。
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Literal

from .models import Inbound
from .storage import JsonStore

OpStatus = Literal["received", "admitted", "queued", "running", "waiting", "done", "failed", "cancelled", "expired"]

_ORDER = {
    "received": 0,
    "admitted": 1,
    "queued": 2,
    "running": 3,
    "waiting": 3,
    "done": 9,
    "failed": 9,
    "cancelled": 9,
    "expired": 9,
}


@dataclass
class Op:
    id: str
    key: str
    session_id: str
    status: OpStatus
    attempts: int
    created_at: float
    updated_at: float
    channel: str
    account: str
    chat_id: str
    principal: str
    text: str = ""

    def to_json(self) -> dict:
        return self.__dict__.copy()


class OpStore:
    def __init__(self, store: JsonStore) -> None:
        self._store = store

    # ------------------------------------------------------------------ 写
    def claim(self, inbound: Inbound, *, session_id: str = "") -> Op | None:
        """占位。返回 None 表示这条消息已经处理过（重复投递）。"""
        key = inbound.dedupe_key()
        now = time.time()

        def mutate(data: dict) -> Op | None:
            index = data.setdefault("index", {})
            if key in index:
                return None
            op_id = uuid.uuid4().hex[:12]
            record = {
                "id": op_id,
                "key": key,
                "session_id": session_id,
                "status": "received",
                "attempts": 1,
                "created_at": now,
                "updated_at": now,
                "channel": inbound.channel.channel,
                "account": inbound.channel.account,
                "chat_id": inbound.conversation.chat_id,
                "principal": inbound.sender.key(),
                "text": (inbound.text or "")[:200],
            }
            data.setdefault("ops", {})[op_id] = record
            index[key] = op_id
            return Op(**record)

        return self._store.update(mutate)

    def transition(self, op: Op, status: OpStatus, *, session_id: str | None = None) -> Op:
        if _ORDER.get(status, 0) < _ORDER.get(op.status, 0):
            raise ValueError(f"状态不能回退：{op.status} -> {status}")

        def mutate(data: dict) -> Op:
            record = (data.get("ops") or {}).get(op.id)
            if not isinstance(record, dict):
                record = op.to_json()
                data.setdefault("ops", {})[op.id] = record
            record["status"] = status
            record["updated_at"] = time.time()
            if session_id is not None:
                record["session_id"] = session_id
            return Op(**record)

        updated = self._store.update(mutate)
        op.status = updated.status
        op.session_id = updated.session_id
        op.updated_at = updated.updated_at
        return updated

    # ------------------------------------------------------------------ 读
    def get(self, op_id: str) -> Op | None:
        record = (self._store.read().get("ops") or {}).get(op_id)
        return Op(**record) if isinstance(record, dict) else None

    def by_session(self, session_id: str) -> Op | None:
        ops = self._store.read().get("ops") or {}
        matches = [Op(**raw) for raw in ops.values() if isinstance(raw, dict) and raw.get("session_id") == session_id]
        if not matches:
            return None
        return max(matches, key=lambda item: item.updated_at)

    def stale(self, seconds: float = 600.0) -> list[Op]:
        """超过 seconds 还没走到终态的操作：进程被杀就会留下这种记录。"""
        cutoff = time.time() - seconds
        ops = self._store.read().get("ops") or {}
        return [Op(**raw) for raw in ops.values()
                if isinstance(raw, dict) and raw.get("status") in {"queued", "running", "waiting"}
                and float(raw.get("updated_at") or 0) < cutoff]

    def force(self, op_id: str, status: OpStatus) -> Op | None:
        """对账用：允许越过顺序约束直接定终态。"""
        def mutate(data: dict) -> Op | None:
            record = (data.get("ops") or {}).get(op_id)
            if not isinstance(record, dict):
                return None
            record["status"] = status
            record["updated_at"] = time.time()
            return Op(**record)

        return self._store.update(mutate)

    def active_by_session(self, session_id: str) -> Op | None:
        op = self.by_session(session_id)
        if op and op.status in {"received", "admitted", "queued", "running", "waiting"}:
            return op
        return None

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for raw in (self._store.read().get("ops") or {}).values():
            if isinstance(raw, dict):
                status = str(raw.get("status") or "unknown")
                result[status] = result.get(status, 0) + 1
        return result
