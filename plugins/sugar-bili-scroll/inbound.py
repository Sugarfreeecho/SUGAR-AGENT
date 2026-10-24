"""inbound.py —— 入站消息：谁在私聊 / 回复 / @ 这个账号，以及该怎么回。

和值班那套的区别要说清楚：
  · 值班是「**我们**按计划去逛」—— 由谷时窗口 + 配额驱动，模型主动去找视频；
  · 这里是「**别人**找上门」—— 由消息驱动，一次只处理一条，且必须封顶。

三条硬规则（都是踩过或会踩的）：
  ① **第一次运行只记游标，不回历史**。否则插件一启动就对着几十条旧消息逐条回，
     账号当场像发疯，代码额度也当场见底。
  ② 自己的消息、官方系统号、非文本消息（图片/撤回/系统提示）一律跳过。
  ③ 每个 sender 有冷却、全局有小时上限 —— 陌生人可以刷你，模型额度刷的是你的钱。

这个模块只负责"**看见**"和"**该不该回**"，真正发出去由 host 决定（它才知道会话和工具）。
"""
from __future__ import annotations

import json
import os
import re
import sys
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

# 官方「系统消息」会话：它是 B站 自己发的，回它等于自言自语
SYSTEM_TALKERS = {844424930131964}
TEXT_MSG_TYPE = 1
BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
CHANNELS = ("dm", "at", "reply")


def store(data_dir):
    name = "myagent_plugin_sugar_bili_scroll_store"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("store.py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module.Store(data_dir)


# ── 状态 ────────────────────────────────────────────────────────────────

def state_path(data_dir: Path) -> Path:
    return Path(data_dir) / "inbound" / "state.json"


def thread_path(data_dir: Path, uid: str) -> Path:
    return Path(data_dir) / "inbound" / "threads" / f"{uid}.json"


def load_thread(data_dir: Path, uid: str, limit: int = 6) -> list[dict]:
    """最近几条来回，给"白名单那位"当上下文。

    为什么不用会话：会话会把**所有**人搅在一起，而且白名单会话拿的是全量宿主工具。
       按 uid 存一小段对话，既能接着聊，又不会串人、也不会把别人说过的话带进来。
    """
    path = thread_path(data_dir, uid)
    if not path.is_file():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict) and r.get("role") in {"user", "assistant"}][-limit:]


def append_turn(data_dir: Path, uid: str, role: str, text: str) -> None:
    path = thread_path(data_dir, uid)
    rows = load_thread(data_dir, uid, limit=12)
    rows.append({"role": role, "content": str(text or "")[:300]})
    rows = rows[-6:]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def load_state(data_dir: Path) -> dict:
    persisted = store(data_dir).get("inbound")
    if isinstance(persisted, dict):
        return {"version": 2, "bootstrapped": False, "dm": {}, "at": {"id": 0, "ts": 0},
                "reply": {"id": 0, "ts": 0}, "recent": [], "last_uid": {}, **persisted}
    path = state_path(data_dir)
    if not path.is_file():
        return {"version": 1, "bootstrapped": False, "dm": {}, "at": {"id": 0, "ts": 0},
                "reply": {"id": 0, "ts": 0}, "recent": [], "last_uid": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 1, "bootstrapped": False, "dm": {}, "at": {"id": 0, "ts": 0},
                "reply": {"id": 0, "ts": 0}, "recent": [], "last_uid": {}}
    data.setdefault("dm", {})
    data.setdefault("at", {"id": 0, "ts": 0})
    data.setdefault("reply", {"id": 0, "ts": 0})
    data.setdefault("recent", [])
    data.setdefault("last_uid", {})
    return data


def save_state(data_dir: Path, state: dict) -> None:
    store(data_dir).put("inbound", state)


def credential_stamp(data_dir: Path) -> str:
    try:
        stat = (Path(data_dir) / "bili_credential.json").stat()
        return f"{stat.st_mtime_ns}:{stat.st_size}"
    except OSError:
        return ""


def auth_expired(data_dir: Path, state=None) -> bool:
    state = load_state(data_dir) if state is None else state
    return bool(state.get("auth_error") and state.get("credential_stamp") == credential_stamp(data_dir))


# ── 白名单 ──────────────────────────────────────────────────────────────

def parse_whitelist(raw: Any) -> dict[str, str]:
    """`123456789 老王` 一行一个；`#` 之后是注释。

    返回 {uid: 备注}。uid 写错（非数字）就跳过 —— 白名单宁可少一个人，
    也不能因为一行手滑把陌生人当成可信账号。
    """
    out: dict[str, str] = {}
    for line in str(raw or "").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split(None, 1)
        uid = parts[0].strip()
        if not uid.isdigit():
            continue
        out[uid] = (parts[1].strip() if len(parts) > 1 else "")[:40]
    return out


def channel_enabled(raw: Any, channel: str) -> bool:
    picked = {p.strip().lower() for p in str(raw or "").replace("，", ",").split(",") if p.strip()}
    if "all" in picked or "全部" in picked:
        return True
    return channel in picked


# ── 限流 ────────────────────────────────────────────────────────────────

def throttled(state: dict, uid: str, cooldown_minutes: int, max_per_hour: int, now: float) -> str:
    """该不该因为限流放弃这条。返回空串表示放行。"""
    last = float((state.get("last_uid") or {}).get(str(uid)) or 0.0)
    if cooldown_minutes > 0 and now - last < cooldown_minutes * 60:
        left = cooldown_minutes * 60 - (now - last)
        # 冷却只有一两分钟时，说"还要等 1 分钟"会显得比实际久，改成报秒
        wait = f"{int(left)} 秒" if left < 120 else f"{int(left / 60) + 1} 分钟"
        return f"同一个人刚回过，还要等 {wait}"
    hour_ago = now - 3600
    recent = [float(t) for t in (state.get("recent") or []) if float(t) > hour_ago]
    if max_per_hour > 0 and len(recent) >= max_per_hour:
        return f"这一小时已经回了 {len(recent)} 条，到上限了"
    return ""


def note_replied(state: dict, uid: str, now: float) -> None:
    state.setdefault("recent", []).append(now)
    state["recent"] = [float(t) for t in state["recent"] if float(t) > now - 3 * 3600][-60:]
    state.setdefault("last_uid", {})[str(uid)] = now


# ── 拉取 ────────────────────────────────────────────────────────────────

def _dm_text(msg: dict) -> str:
    """私信正文是个 JSON 字符串（`{"content": "你好"}`），不是裸文本。"""
    raw = str(msg.get("content") or "")
    if not raw:
        return ""
    try:
        payload = json.loads(raw)
    except ValueError:
        return raw.strip()
    if isinstance(payload, dict):
        return str(payload.get("content") or "").strip()
    return raw.strip()


def _event(channel: str, uid: Any, nickname: str, text: str, ts: Any, target: dict, key: str) -> dict:
    return {
        "channel": channel,
        "uid": str(uid),
        "nickname": nickname or "",
        "text": str(text or "").strip()[:4000],
        "ts": int(ts or 0),
        "target": target,
        "key": key,
    }


async def poll(
    data_dir: Path,
    credential,
    own_uid: str,
    channels: Iterable[str] = ("dm", "at", "reply"),
    *,
    dry_run: bool = False,
) -> dict:
    """拉一遍入站消息，推进游标，返回新事件。

    `dry_run=True` 时不写状态（"立刻检查一次"按钮用，不想把游标吃掉）。
    """
    from bilibili_api import session

    if not dry_run:
        store(data_dir).activate_account(own_uid)
    state = load_state(data_dir)
    if state.get("account_uid") and state["account_uid"] != str(own_uid):
        state = {"bootstrapped": False, "dm": {}, "at": {"id": 0, "ts": 0}, "reply": {"id": 0, "ts": 0}}
    state["account_uid"] = str(own_uid)
    wanted = {c for c in channels if c in CHANNELS}
    events: list[dict] = []
    errors: list[str] = []
    first_run = not state.get("bootstrapped")
    initialized = dict(state.get("channels_ready") or {c: bool(state.get("bootstrapped")) for c in CHANNELS})
    succeeded = set()
    auth_failed = False
    stamp = credential_stamp(data_dir)

    if "dm" in wanted:
        try:
            rows = (await session.get_sessions(credential=credential, session_type=4) or {}).get("session_list") or []
            for row in rows:
                talker = str(row.get("talker_id") or "")
                if not talker.isdigit() or talker in {str(t) for t in SYSTEM_TALKERS} or int(row.get("session_type") or 1) != 1:
                    continue
                last = row.get("last_msg") or {}
                cursor = int((state["dm"].get(talker) or {}).get("seqno") or 0)
                if int(last.get("msg_seqno") or 0) and int(last["msg_seqno"]) <= cursor:
                    continue
                # get_sessions uses 4 for all channels; fetch uses 1 for a DM.
                # Even an outgoing/non-text last message may follow unread text.
                data = await session.fetch_session_msgs(talker_id=int(talker), credential=credential, session_type=1, begin_seqno=cursor)
                msgs = [m for m in (data or {}).get("messages") or []]
                fresh = [
                    m for m in msgs
                    if str(m.get("sender_uid") or "") != str(own_uid)
                    and int(m.get("msg_type") or 0) == TEXT_MSG_TYPE
                    and int(m.get("msg_seqno") or 0) > cursor
                ]
                fresh.sort(key=lambda m: int(m.get("msg_seqno") or 0))
                for msg in fresh:
                    seq = int(msg.get("msg_seqno") or 0)
                    state["dm"][talker] = {"seqno": seq}
                    events.append(_event(
                        "dm", msg.get("sender_uid") or talker, "",
                        _dm_text(msg), msg.get("timestamp"),
                        {"kind": "dm", "uid": talker},
                        f"dm:{talker}:{seq}",
                    ))
                state["dm"][talker] = {"seqno": max([cursor] + [int(m.get("msg_seqno") or 0) for m in msgs])}
            succeeded.add("dm")
        except Exception as exc:  # noqa: BLE001
            auth_failed = auth_failed or getattr(exc, "code", None) == -101
            errors.append(f"私信：{type(exc).__name__}: {str(exc)[:120]}")

    if "at" in wanted:
        try:
            data = await session.get_at(credential=credential)
            items = (data or {}).get("items") or []
            cursor = state["at"]
            fresh = [it for it in items if (int(it.get("at_time") or 0), int(it.get("id") or 0)) > (int(cursor.get("ts") or 0), int(cursor.get("id") or 0))]
            fresh.sort(key=lambda it: (int(it.get("at_time") or 0), int(it.get("id") or 0)))
            for it in fresh:
                item = it.get("item") or {}
                user = it.get("user") or {}
                uri = str(item.get("uri") or item.get("native_uri") or "")
                match = BV_RE.search(uri)
                rpid = int(item.get("source_id") or 0)
                target = {
                    "kind": "comment",
                    "bvid": match.group(1) if match else "",
                    "rpid": rpid,
                    "root": int(item.get("root_id") or 0) or rpid,
                }
                state["at"] = {"id": int(it.get("id") or 0), "ts": int(it.get("at_time") or 0)}
                events.append(_event(
                    "at", user.get("mid"), str(user.get("nickname") or ""),
                    str(item.get("source_content") or ""), it.get("at_time"),
                    target, f"at:{it.get('id')}",
                ))
            succeeded.add("at")
        except Exception as exc:  # noqa: BLE001
            auth_failed = auth_failed or getattr(exc, "code", None) == -101
            errors.append(f"@我：{type(exc).__name__}: {str(exc)[:120]}")

    if "reply" in wanted:
        try:
            data = await session.get_replies(credential=credential)
            items = (data or {}).get("items") or []
            cursor = state["reply"]
            fresh = [it for it in items if (int(it.get("reply_time") or 0), int(it.get("id") or 0)) > (int(cursor.get("ts") or 0), int(cursor.get("id") or 0))]
            fresh.sort(key=lambda it: (int(it.get("reply_time") or 0), int(it.get("id") or 0)))
            for it in fresh:
                item = it.get("item") or {}
                user = it.get("user") or {}
                uri = str(item.get("uri") or item.get("native_uri") or "")
                match = BV_RE.search(uri)
                rpid = int(item.get("business_id") or 0) or int(item.get("source_id") or 0)
                state["reply"] = {"id": int(it.get("id") or 0), "ts": int(it.get("reply_time") or 0)}
                events.append(_event(
                    "reply", user.get("mid"), str(user.get("nickname") or ""),
                    str(item.get("source_content") or ""), it.get("reply_time"),
                    {"kind": "comment", "bvid": match.group(1) if match else "",
                     "rpid": rpid, "root": int(item.get("root_id") or 0) or rpid},
                    f"reply:{it.get('id')}",
                ))
            succeeded.add("reply")
        except Exception as exc:  # noqa: BLE001
            auth_failed = auth_failed or getattr(exc, "code", None) == -101
            errors.append(f"回复我：{type(exc).__name__}: {str(exc)[:120]}")

    # Logging out or switching while the network request was pending invalidates it.
    if stamp != credential_stamp(data_dir):
        return {"ok": False, "events": [], "errors": ["登录状态已变化，本次读取已丢弃"], "first_run": first_run}
    for ev in events:
        ev["account_uid"] = str(own_uid)
        ev["key"] = str(own_uid) + ":" + ev["key"]

    if first_run and not dry_run:
        # 第一次只落游标：把上面攒的事件全丢掉，一条都不回。
        # ⚠️ dry_run 例外 —— "立刻检查一次"按钮的意义就是让你**看见**积压了什么。
        events = [ev for ev in events if initialized.get(ev["channel"])]

    if not dry_run:
        # A channel whose first request failed must still bootstrap silently
        # when it becomes reachable on a later poll.
        events = [ev for ev in events if initialized.get(ev["channel"])]
        initialized.update({channel: True for channel in succeeded})
        state["channels_ready"] = initialized

    if not dry_run:
        state["bootstrapped"] = all(initialized.get(channel) for channel in wanted)
        state["last_poll_at"] = datetime.now().isoformat(timespec="seconds")
        state["last_errors"] = errors
        state["auth_error"] = auth_failed or (not succeeded and auth_expired(data_dir, state))
        state["credential_stamp"] = stamp
        usable_events = [ev for ev in events if str(ev["uid"]).isdigit() and ev["uid"] != str(own_uid) and ev["text"]]
        store(data_dir).poll_commit(state, usable_events)

    usable = [ev for ev in events if str(ev["uid"]).isdigit() and ev["uid"] != str(own_uid) and ev["text"]]
    dropped = len(events) - len(usable)
    return {
        "ok": not errors,
        "first_run": first_run,
        "events": usable,
        "dropped": dropped,
        "errors": errors,
        "auth_error": auth_failed,
        "channels": sorted(wanted),
    }
