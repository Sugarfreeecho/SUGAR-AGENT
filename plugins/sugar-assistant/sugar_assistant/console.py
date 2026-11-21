"""控制台的后端数据：人设、人物卡片、状态日志。

全部落在插件自己的 `state/` 下，不碰宿主配置：

    state/persona.json   {"name": "", "tone": "", "rules": ""}
    state/persons.json   [{"id","name","alias","relation","note","created_at"}]
    state/events.jsonl   最近的运行事件（环形保留 500 条）

日志只记「哪个通道、哪个会话、发生了什么」，不记消息正文。
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import deque
from typing import Any


class ConsoleStore:
    def __init__(self, state_dir: str, *, keep: int = 500) -> None:
        self.dir = state_dir
        os.makedirs(self.dir, exist_ok=True)
        self.persona_path = os.path.join(self.dir, "persona.json")
        self.persons_path = os.path.join(self.dir, "persons.json")
        self.events_path = os.path.join(self.dir, "events.jsonl")
        self._lock = threading.Lock()
        self._events: deque[dict] = deque(maxlen=keep)
        self._load_events()

    # ------------------------------------------------------------------ 人设
    def persona(self) -> dict:
        data = self._read_json(self.persona_path, {"prompt": "", "modes": {}})
        if not isinstance(data, dict):
            data = {"prompt": "", "modes": {}}
        data.setdefault("modes", {})
        # 旧格式（name/tone/rules）迁移成一段全局提示词，避免历史配置丢失
        if not data.get("prompt") and (data.get("name") or data.get("tone") or data.get("rules")):
            lines = []
            if data.get("name"):
                lines.append(f"你是{data['name']}。")
            if data.get("tone"):
                lines.append(f"说话风格：{data['tone']}")
            if data.get("rules"):
                lines.append("硬规则：")
                lines.extend(f"- {r.strip('- ').strip()}" for r in str(data["rules"]).splitlines() if r.strip())
            data["prompt"] = "\n".join(lines)
        return data

    def save_persona(self, payload: dict) -> dict:
        data = {
            "prompt": str(payload.get("prompt") or "")[:4000],
            "modes": {
                str(mode): {
                    "identity": str((cfg or {}).get("identity") or "")[:60],
                    "tone": str((cfg or {}).get("tone") or "")[:400],
                    "rules": str((cfg or {}).get("rules") or "")[:2000],
                }
                for mode, cfg in (payload.get("modes") or {}).items()
                if mode in {"private", "group", "comment"} and isinstance(cfg, dict)
            },
            "updated_at": time.time(),
        }
        self._write_json(self.persona_path, data)
        return data

    # ------------------------------------------------------------------ 人物
    def persons(self) -> list[dict]:
        data = self._read_json(self.persons_path, [])
        return data if isinstance(data, list) else []

    def add_person(self, payload: dict) -> dict:
        person = {
            "id": f"p-{uuid.uuid4().hex[:8]}",
            "name": str(payload.get("name") or "").strip()[:40],
            "alias": str(payload.get("alias") or "").strip()[:40],
            "relation": str(payload.get("relation") or "朋友")[:20],
            "note": str(payload.get("note") or "").strip()[:400],
            "created_at": time.time(),
        }
        if not person["name"]:
            raise ValueError("name 不能为空")
        with self._lock:
            items = self.persons()
            items.append(person)
            self._write_json(self.persons_path, items)
        return person

    def remove_person(self, person_id: str) -> bool:
        with self._lock:
            items = self.persons()
            kept = [item for item in items if item.get("id") != person_id]
            if len(kept) == len(items):
                return False
            self._write_json(self.persons_path, kept)
            return True

    # ------------------------------------------------------------------ 日志
    def log(self, kind: str, **fields: Any) -> None:
        record = {"ts": time.time(), "kind": kind, **fields}
        with self._lock:
            self._events.append(record)
            try:
                with open(self.events_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError:
                pass

    def events(self, limit: int = 100) -> list[dict]:
        with self._lock:
            return list(self._events)[-limit:]

    def _load_events(self) -> None:
        if not os.path.exists(self.events_path):
            return
        try:
            with open(self.events_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self._events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

    # ------------------------------------------------------------------ 文件
    @staticmethod
    def _read_json(path: str, default):
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return default

    @staticmethod
    def _write_json(path: str, payload) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
