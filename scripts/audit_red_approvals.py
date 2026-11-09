"""Full-coverage red-approval audit across every storage generation.

Coverage matrix:
  * raw Runtime V2 logs        -> approval_requested / approval_resolved events
  * compacted Runtime V2 logs  -> baseline snapshot's approvals dict
  * legacy sessions            -> ui_events.json / work_messages.json records
  * subagent logs              -> same as raw logs

Red means ``approval_level == "danger"`` (frontend renders ``is-danger``).
"""
from __future__ import annotations

import argparse
import collections
import json
import os
from pathlib import Path


def classify(record: dict) -> str:
    """Human-readable outcome for one approval record."""
    decision = str(record.get("decision") or "").lower()
    status = str(record.get("status") or "").lower()
    if decision == "deny":
        return "denied"
    if decision:
        return "allowed"
    if status in {"pending", "waiting"}:
        return "pending"
    if status == "expired":
        return "expired"
    if status in {"cancelled", "canceled"}:
        return "cancelled"
    if status in {"resolved"}:
        return "resolved(no decision field)"
    return status or "unknown"


def iter_sessions(sessions_dir: Path):
    """Yield (label, events.jsonl path) for root sessions and subagents."""
    for child in sorted(sessions_dir.iterdir()):
        if not child.is_dir():
            continue
        log = child / "events.jsonl"
        if log.is_file():
            yield child.name, log
        sub = child / "subagents"
        if sub.is_dir():
            for agent in sorted(sub.iterdir()):
                alog = agent / "events.jsonl"
                if alog.is_file():
                    yield f"{child.name[:8]}/subagents/{agent.name[:8]}", alog


def rule_of(record: dict) -> str:
    return str(record.get("security_rule_id") or record.get("rule_id") or "").strip()


def bucket(record: dict) -> str:
    rule = rule_of(record).lower()
    text = " ".join(
        str(record.get(k) or "")
        for k in ("intercept_reason", "reason", "subtitle", "rejection_reason")
    ).lower()
    table = {
        "process.destructive": "破坏性 Shell 命令",
        "session.workspace_switch": "切换会话工作目录",
        "process.dynamic": "动态构造 Shell 代码",
        "process.interactive_stdin": "持久终端交互输入",
        "process.network.upload": "数据外发",
        "process.network.unknown": "未知网络访问",
        "process.network.read": "网络读取",
        "process.external": "工作区外访问",
        "external.write": "工作区外写入",
        "delete.review": "工作区外永久删除",
        "process.workspace_delete": "工作区内删除",
        "delete.workspace": "工作区内删除",
        "process.credential": "凭据导出",
        "process.credential_read": "经 Shell 读凭据",
        "credential.read": "读取凭据文件",
        "process.policy_change": "策略/控制器篡改",
    }
    if rule in table:
        return table[rule]
    if "危险" in text or "destructive" in text:
        return "破坏性 Shell 命令"
    if not rule and not text.strip():
        return "未记录原因"
    return f"其他（{rule or 'no-rule'}）"


def from_events(path: Path, since: str):
    """Yield records from a raw (uncompacted) Runtime V2 log."""
    requests: list[tuple[str, int, dict]] = []
    resolutions: dict[str, dict] = {}
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "approval_" not in line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            etype = event.get("type")
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            if etype == "approval_requested":
                ts = str(event.get("timestamp") or "")
                if ts and ts[:10] < since:
                    continue
                requests.append((ts, event.get("seq"), payload))
            elif etype == "approval_resolved":
                aid = str(payload.get("approval_id") or "")
                if aid:
                    resolutions[aid] = payload
    for ts, seq, req in requests:
        aid = str(req.get("approval_id") or "")
        merged = {**req, **{k: v for k, v in (resolutions.get(aid) or {}).items() if v not in (None, "")}}
        yield ts, seq, merged


def from_baseline(path: Path, since: str):
    """Yield records from a compacted baseline plus anything appended after it.

    Compaction folds history into one ``runtime_snapshot_compacted`` event, but
    the session may keep running afterwards. Reading only the first line would
    silently drop every later approval (one session had 127,966 events after
    its baseline).
    """
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        first = fh.readline()
        try:
            event = json.loads(first)
        except ValueError:
            return
        if event.get("type") != "runtime_snapshot_compacted":
            return
        snap = (event.get("payload") or {}).get("snapshot") or {}
        seen: set[str] = set()
        for aid, row in (snap.get("approvals") or {}).items():
            if not isinstance(row, dict):
                continue
            ts = str(row.get("created_at") or "")
            if ts and ts[:10] < since:
                continue
            seen.add(str(aid))
            yield ts, row.get("seq"), dict(row)

        # Approvals recorded after the baseline supersede the snapshot copy.
        requests: list[tuple[str, int, dict]] = []
        resolutions: dict[str, dict] = {}
        for line in fh:
            if "approval_" not in line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            etype = ev.get("type")
            payload = ev.get("payload")
            if not isinstance(payload, dict):
                continue
            if etype == "approval_requested":
                ts = str(ev.get("timestamp") or "")
                if ts and ts[:10] < since:
                    continue
                requests.append((ts, ev.get("seq"), payload))
            elif etype == "approval_resolved":
                aid = str(payload.get("approval_id") or "")
                if aid:
                    resolutions[aid] = payload
        for ts, seq, req in requests:
            aid = str(req.get("approval_id") or "")
            if aid in seen:
                continue
            merged = {**req, **{k: v for k, v in (resolutions.get(aid) or {}).items() if v not in (None, "")}}
            yield ts, seq, merged


def from_legacy(session_dir: Path, since: str):
    """Yield approval-like records from pre-Runtime-V2 session files."""
    for name in ("ui_events.json", "work_messages.json"):
        path = session_dir / name
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
        except (ValueError, OSError):
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, dict):
                if item.get("approval_level") and item.get("approval_id"):
                    ts = str(item.get("created_at") or item.get("timestamp") or "")
                    if not ts or ts[:10] >= since:
                        yield ts, item.get("seq"), dict(item)
                stack.extend(v for v in item.values() if isinstance(v, (dict, list)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sessions_dir", type=Path)
    ap.add_argument("--since", default="2026-10-01")
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args()

    root = args.sessions_dir.resolve()
    sources = collections.Counter()
    levels = collections.Counter()
    red_outcome = collections.Counter()
    red_bucket = collections.Counter()
    red_by_session = collections.Counter()
    red_rows = []
    all_ids = set()

    def absorb(scope: str, session_label: str, records):
        for ts, seq, rec in records:
            sources[scope] += 1
            level = str(rec.get("approval_level") or "unknown")
            levels[level] += 1
            aid = str(rec.get("approval_id") or "")
            if aid:
                all_ids.add(aid)
            if level != "danger":
                continue
            outcome = classify(rec)
            red_outcome[outcome] += 1
            red_bucket[bucket(rec)] += 1
            red_by_session[session_label] += 1
            red_rows.append({
                "scope": scope,
                "session": session_label,
                "timestamp": ts,
                "seq": seq,
                "approval_id": aid,
                "outcome": outcome,
                "decision": rec.get("decision"),
                "rule": rule_of(rec),
                "reason": bucket(rec),
                "tool": rec.get("tool"),
                "subtitle": str(rec.get("subtitle") or "")[:200],
                "message": " ".join(str(rec.get("message") or "").split())[:300],
            })

    for session_dir in sorted(root.iterdir()):
        if not session_dir.is_dir():
            continue
        sid = session_dir.name
        log = session_dir / "events.jsonl"
        if log.is_file():
            with log.open("r", encoding="utf-8", errors="replace") as fh:
                head = fh.readline()
            if '"runtime_snapshot_compacted"' in head:
                absorb("compacted", sid, from_baseline(log, args.since))
            else:
                absorb("runtime_v2", sid, from_events(log, args.since))
        else:
            absorb("legacy", sid, from_legacy(session_dir, args.since))
        sub = session_dir / "subagents"
        if sub.is_dir():
            for agent in sorted(sub.iterdir()):
                alog = agent / "events.jsonl"
                if not alog.is_file():
                    continue
                # Subagent logs are compacted too; treat them like any other log.
                with alog.open("r", encoding="utf-8", errors="replace") as fh:
                    sub_head = fh.readline()
                gen = from_baseline(alog, args.since) if '"runtime_snapshot_compacted"' in sub_head \
                    else from_events(alog, args.since)
                absorb("subagent", f"{sid[:8]}/{agent.name[:8]}", gen)

    print(json.dumps({
        "since": args.since,
        "approval_records_seen": dict(sources),
        "distinct_approval_ids": len(all_ids),
        "by_level": dict(levels),
        "red_total": len(red_rows),
        "red_by_outcome": dict(red_outcome),
        "red_by_reason": dict(red_bucket),
        "red_by_session": dict(red_by_session.most_common()),
    }, ensure_ascii=False, indent=1))

    if args.json_out:
        args.json_out.write_text(json.dumps(red_rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
