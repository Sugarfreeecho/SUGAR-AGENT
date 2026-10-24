"""Plugin-owned full system templates, independent from host prompt templates."""
from __future__ import annotations

import json
import re
import threading
import uuid
from pathlib import Path

KINDS = ("duty", "dm", "reply")
MAX_BYTES = 240 * 1024  # Leave room for per-task facts under the host's 256 KiB limit.
LOCK = threading.RLock()


def load(home):
    path = Path(home) / "system-prompts.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise ValueError("插件系统提示词文件格式无效")
    return validate(raw.get("prompts"))


def validate(values):
    if not isinstance(values, dict) or any(key not in KINDS for key in values):
        raise ValueError("系统提示词只接受 duty、dm、reply 三类")
    for value in values.values():
        if not isinstance(value, str) or len(value.encode("utf-8")) > MAX_BYTES:
            raise ValueError("每份系统提示词必须是文字，且不超过240 KiB")
    return {key: value if value.strip() else "" for key, value in values.items()}


def save(home, changes):
    changes = validate(changes)
    with LOCK:
        values = {**load(home), **changes}
        path = Path(home) / "system-prompts.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        temp.write_text(json.dumps({"version": 1, "prompts": values}, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
    return values


def view(home, defaults):
    values = load(home)
    return {"ok": True, "mode": "replace", "max_bytes": MAX_BYTES, "prompts": {
        key: {"text": values.get(key) or defaults[key], "custom": bool(values.get(key))}
        for key in KINDS}}


def render(template, variables):
    # JSON/code braces are ordinary text; only explicit {{name}} tokens expand.
    return re.sub(r"\{\{([a-z_]+)\}\}", lambda match: str(variables.get(match[1], match[0])), template)
