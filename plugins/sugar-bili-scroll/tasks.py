"""tasks.py —— 多任务：一个插件里跑多条互相独立的值班任务。

为什么要单独一层：原来插件只有"一条值班任务"，配置散在 `plugin.json` 的
25 个设置项里（关键词、配额、窗口、会话 id…），`plugin.json` 的 schema
只支持标量，装不下"一组任务"这种结构。

存哪儿：`data/tasks.json`（数组），每条的目录 `data/tasks/<id>/`
（放 out/、digest/、duty.log）。

⭐ 判重表**故意不按任务分**（用户 2026-10-22 定的）：
   `data/seen.md` 一张全局表 —— A 任务看过的视频 B 任务不再看，
   免得两个任务把同一条视频各评论一遍。
"""
from __future__ import annotations

import json
import re
import time
import uuid
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

TASK_FILE = "tasks.json"
SEEN_FILE = "seen.md"
DEFAULT_WINDOWS = "12:00-14:00,18:00-09:00"

_BV_RE = re.compile(r"BV[0-9A-Za-z]{10}")
LOCK = threading.RLock()
EDITABLE = {"name", "enabled", "keywords", "daily_quota", "valley_windows", "min_interval_minutes",
            "round_budget_minutes", "report_level", "auto_comment", "mention_name", "comment_per_round",
            "image_comment", "dm_mode", "dm_uid", "reply_to_comments"}


def edit_values(body: Mapping[str, Any]) -> dict:
    if not isinstance(body, dict):
        raise ValueError("任务内容必须是对象")
    values = {key: value for key, value in body.items() if key in EDITABLE}
    for key, value in values.items():
        if key in {"enabled", "auto_comment", "image_comment", "reply_to_comments"}:
            if not isinstance(value, bool):
                raise ValueError(f"{key} 必须是开关值")
        elif key in {"daily_quota", "min_interval_minutes", "round_budget_minutes", "comment_per_round", "dm_uid"}:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{key} 必须是整数")
            maximum = {"daily_quota": 100, "min_interval_minutes": 1440, "round_budget_minutes": 60,
                       "comment_per_round": 5, "dm_uid": 2**63-1}[key]
            if not 0 <= value <= maximum:
                raise ValueError(f"{key} 必须在 0 到 {maximum} 之间")
        elif not isinstance(value, str):
            raise ValueError(f"{key} 必须是文字")
    if values.get("report_level", "brief") not in {"brief", "full", "off"}:
        raise ValueError("日报详细程度无效")
    if values.get("dm_mode", "off") not in {"off", "only", "both"}:
        raise ValueError("私信模式无效")
    if "valley_windows" in values:
        for item in str(values["valley_windows"]).replace("，", ",").split(","):
            start, _, end = item.partition("-")
            if _minutes(start) is None or _minutes(end) is None:
                raise ValueError("谷时窗口格式应为 12:00-14:00,18:00-09:00")
    return values


def tasks_file(home: Path) -> Path:
    return Path(home) / TASK_FILE


def seen_file(home: Path) -> Path:
    """全局判重表（所有任务共用一张）。"""
    return Path(home) / SEEN_FILE


def task_home(home: Path, row: Mapping[str, Any]) -> Path:
    ident = str(row.get("id") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", ident):
        raise ValueError("任务 ID 无效")
    path = Path(home) / "tasks" / ident
    path.mkdir(parents=True, exist_ok=True)
    return path


def _minutes(text: str) -> Optional[int]:
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(text or ""))
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def parse_windows(spec: Any) -> list[tuple[int, int]]:
    """'12:00-14:00,18:00-09:00' → [(720,840),(1080,540)]；非法项直接丢。"""
    items = (
        [str(x) for x in spec]
        if isinstance(spec, (list, tuple))
        else [p.strip() for p in str(spec or "").split(",") if p.strip()]
    )
    windows: list[tuple[int, int]] = []
    for item in items:
        start_text, _, end_text = item.partition("-")
        start, end = _minutes(start_text), _minutes(end_text)
        if start is None or end is None:
            continue
        windows.append((start, end))
    return windows or parse_windows(DEFAULT_WINDOWS)


def in_window(now: datetime, windows: Iterable[tuple[int, int]]) -> bool:
    current = now.hour * 60 + now.minute
    for start, end in windows:
        if start <= end:
            if start <= current < end:
                return True
        elif current >= start or current < end:  # 跨零点
            return True
    return False


def new_row(**kwargs: Any) -> dict:
    """一条新任务。字段名和 plugin.json 里那套保持同名，便于整体迁移。"""
    row = {
        "id": uuid.uuid4().hex[:8],
        "name": "新任务",
        "enabled": True,
        "keywords": "",
        "daily_quota": 3,
        "valley_windows": DEFAULT_WINDOWS,
        "min_interval_minutes": 45,
        "round_budget_minutes": 0,
        "report_level": "brief",
        "auto_comment": False,
        "mention_name": "",
        "comment_per_round": 1,
        "image_comment": False,
        "dm_mode": "off",
        "dm_uid": 0,
        "reply_to_comments": False,
        "session_id": "",
        "created_at": time.time(),
    }
    row.update({k: v for k, v in kwargs.items() if k in row})
    return normalise(row)


def normalise(row: Mapping[str, Any]) -> dict:
    out = dict(row)
    out["id"] = str(out.get("id") or uuid.uuid4().hex[:8])
    out["name"] = str(out.get("name") or "未命名任务").strip()[:40]
    out["enabled"] = bool(out.get("enabled", True))
    out["keywords"] = str(out.get("keywords") or "").strip()
    out["daily_quota"] = max(0, int(out.get("daily_quota") or 0))
    out["valley_windows"] = str(out.get("valley_windows") or DEFAULT_WINDOWS)
    out["min_interval_minutes"] = max(0, int(out.get("min_interval_minutes") or 0))
    out["round_budget_minutes"] = max(0, int(out.get("round_budget_minutes") or 0))
    level = str(out.get("report_level") or "brief")
    out["report_level"] = level if level in ("full", "brief", "off") else "brief"
    out["auto_comment"] = bool(out.get("auto_comment"))
    out["mention_name"] = str(out.get("mention_name") or "").strip()
    out["comment_per_round"] = max(0, int(out.get("comment_per_round", 1)))
    out["image_comment"] = bool(out.get("image_comment"))
    mode = str(out.get("dm_mode") or "off")
    out["dm_mode"] = mode if mode in ("off", "only", "both") else "off"
    out["dm_uid"] = max(0, int(out.get("dm_uid") or 0))
    out["reply_to_comments"] = bool(out.get("reply_to_comments"))
    out["session_id"] = str(out.get("session_id") or "")
    return out


def load(home: Path) -> list[dict]:
    """读任务表；没有文件就用旧的单任务设置迁一条出来（只迁一次）。"""
    path = tasks_file(home)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw.get("tasks") if isinstance(raw, dict) else raw
        if isinstance(rows, list):
            return [normalise(row) for row in rows if isinstance(row, dict)]
    except (OSError, ValueError):
        pass
    return []


def save(home: Path, rows: list[dict]) -> None:
    path = tasks_file(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    with LOCK:
        tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        payload = {"tasks": [normalise(row) for row in rows]}
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def update(home: Path, ident: str, changes: Mapping[str, Any]) -> dict:
    with LOCK:
        rows = load(home)
        for index, row in enumerate(rows):
            if row["id"] == ident:
                rows[index] = normalise({**row, **changes, "id": ident})
                save(home, rows)
                return rows[index]
    raise ValueError("任务不存在")


def import_legacy(home: Path, rows: list[dict], settings: Mapping[str, Any]) -> None:
    """Map legacy global facts to the original task once, never to every task."""
    marker = Path(home) / "task-data-migration.json"
    with LOCK:
        if marker.exists():
            return
        sid = str(settings.get("duty_session_id") or "")
        matches = [r for r in rows if sid and r.get("session_id") == sid]
        if not matches and len(rows) == 1 and rows[0].get("name") == "默认任务":
            matches = rows
        if not matches:
            return
        row = matches[0]
        target = task_home(home, row)
        imported = []
        for name in ("out", "digest"):
            source = Path(home) / name
            if source.is_dir():
                for path in source.glob("*.md"):
                    dest = target / name / path.name
                    if not dest.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(path, dest)
                        imported.append(str(dest.relative_to(home)))
        state = Path(home) / "duty-state.json"
        if state.is_file() and not (target / state.name).exists():
            shutil.copy2(state, target / state.name)
        # Preserve a fixed baseline so new structured picks can be added to it.
        baseline = {}
        for report in (target / "out").glob("*.md"):
            baseline[report.stem] = len(set(re.findall(r"^#{2,3}\s*(BV[0-9A-Za-z]{10})", report.read_text(encoding="utf-8"), re.M)))
        if (target / "duty-state.json").is_file():
            old = json.loads((target / "duty-state.json").read_text(encoding="utf-8"))
            if old.get("day"):
                baseline[old["day"]] = max(baseline.get(old["day"], 0), int(old.get("picked") or 0))
        (target / "legacy-picks.json").write_text(json.dumps(baseline), encoding="utf-8")
        marker.write_text(json.dumps({"task_id": row["id"], "files": imported}, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate_from_settings(home: Path, settings: Mapping[str, Any]) -> list[dict]:
    """把老设置迁为默认任务；已存在的空表也表示用户完成了迁移。"""
    if tasks_file(home).exists():
        return load(home)
    if not settings:
        return []
    row = new_row(
        name="默认任务",
        keywords=str(settings.get("keywords") or ""),
        daily_quota=int(settings.get("daily_quota", 3) or 0),
        valley_windows=str(settings.get("valley_windows") or DEFAULT_WINDOWS),
        min_interval_minutes=int(settings.get("min_interval_minutes", 45) or 0),
        round_budget_minutes=int(settings.get("round_budget_minutes") or 0),
        report_level=str(settings.get("report_level") or "brief"),
        auto_comment=bool(settings.get("auto_comment")),
        mention_name=str(settings.get("mention_name") or ""),
        comment_per_round=int(settings.get("comment_per_round") or 1),
        image_comment=bool(settings.get("image_comment")),
        dm_mode=str(settings.get("dm_mode") or "off"),
        dm_uid=int(settings.get("dm_uid") or 0),
        reply_to_comments=bool(settings.get("reply_to_comments")),
        session_id=str(settings.get("duty_session_id") or ""),
    )
    save(home, [row])
    return [row]


def seen_bvids(home: Path) -> set[str]:
    try:
        return set(_BV_RE.findall(seen_file(home).read_text(encoding="utf-8")))
    except OSError:
        return set()


def seen_contains(home: Path, bvid: str) -> bool:
    return str(bvid or "") in seen_bvids(home)


def should_run(
    row: Mapping[str, Any],
    now: datetime,
    *,
    picked_today: int = 0,
    last_round_at: Optional[datetime] = None,
    busy: bool = False,
) -> tuple[bool, str]:
    """这条任务这一刻该不该跑。返回 (要不要跑, 不跑的原因)。"""
    if not row.get("enabled", True):
        return False, "任务已停用"
    if busy:
        return False, "上一轮还在跑"
    if picked_today >= int(row.get("daily_quota") or 0):
        return False, "今天的额度已经用完"
    if not in_window(now, parse_windows(row.get("valley_windows"))):
        return False, "不在这个任务的谷时窗口里"
    gap = int(row.get("min_interval_minutes") or 0)
    if gap and last_round_at is not None:
        waited = (now - last_round_at).total_seconds() / 60.0
        if waited < gap:
            return False, f"距上一轮才 {int(waited)} 分钟（最小间隔 {gap}）"
    return True, ""


def plan(rows: list[dict], now: datetime, state_of) -> list[tuple[dict, str]]:
    """一次调度扫描：返回 (该跑的任务, 原因)。`state_of(row)` 给出该任务的状态。

    `state_of` 返回 `{"picked": int, "last_at": datetime|None, "busy": bool}`。
    任务之间**串行**跑（同一账号、同一 CPU，并发只会互相踩）。
    """
    picked: list[tuple[dict, str]] = []
    for row in rows:
        state = state_of(row) or {}
        ok, why = should_run(
            row,
            now,
            picked_today=int(state.get("picked") or 0),
            last_round_at=state.get("last_at"),
            busy=bool(state.get("busy")),
        )
        if ok:
            picked.append((row, "窗口到点"))
    return picked
