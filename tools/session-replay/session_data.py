"""Read-only SugarAgent journal import and lazy replay ranges; stdlib only.

UI projection/order follows app/runtime_v2/ui_projection.py. No application
backend is imported, so opening a session never rebuilds or writes its caches.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import zipfile
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


class ImportProblem(ValueError):
    pass


class ChooseSession(ImportProblem):
    def __init__(self, candidates):
        super().__init__("找到多个会话，请选择其中一个")
        self.candidates = candidates


def safe_name(value):
    name = PurePosixPath(str(value).replace("\\", "/"))
    if name.is_absolute() or ".." in name.parts or any(":" in p for p in name.parts):
        raise ImportProblem("文件路径超出会话目录")
    if name.as_posix() == ".":
        raise ImportProblem("文件路径为空")
    return name.as_posix()


class SessionSource:
    def __init__(self, location, candidate=None):
        self.archive = None
        try:
            self._open(location, candidate)
        except Exception:
            self.close()
            raise

    def _open(self, location, candidate=None):
        self.location = Path(location).expanduser().resolve()
        self.archive = None
        if self.location.is_file() and self.location.suffix.lower() == ".zip":
            self.archive = zipfile.ZipFile(self.location)
            self.entries = {}
            total = 0
            for entry in self.archive.infolist():
                name = safe_name(entry.filename)
                if entry.is_dir():
                    continue
                if name in self.entries:
                    raise ImportProblem("ZIP 中有重复文件路径")
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ImportProblem("会话 ZIP 不支持符号链接")
                total += entry.file_size
                if entry.file_size > 512 * 1024 * 1024 or total > 2 * 1024**3:
                    raise ImportProblem("ZIP 解压后的会话材料超过 2GB")
                self.entries[name] = entry
            candidates = sorted({n.rsplit("/", 1)[0] if "/" in n else ""
                                 for n in self.entries if n.rsplit("/", 1)[-1] == "events.jsonl"})
        elif self.location.is_dir():
            candidates = []
            if (self.location / "events.jsonl").is_file():
                candidates = [""]
            else:
                for depth in (1, 2, 3):
                    candidates.extend(p.parent.relative_to(self.location).as_posix()
                                      for p in self.location.glob("*/" * depth + "events.jsonl"))
                candidates = sorted(set(candidates))
        else:
            raise ImportProblem("请选择包含 events.jsonl 的会话目录，或会话 ZIP")
        if not candidates:
            self.close()
            raise ImportProblem("未找到 events.jsonl；请选择会话目录或应用导出的会话 ZIP")
        if candidate is None and len(candidates) > 1:
            self.close()
            raise ChooseSession(candidates)
        self.prefix = candidate if candidate is not None else candidates[0]
        if self.prefix not in candidates:
            self.close()
            raise ImportProblem("选择的会话不在导入材料中")

    def close(self):
        if self.archive:
            self.archive.close()

    def read(self, name, optional=False):
        relative = safe_name(name)
        if self.archive:
            key = (self.prefix + "/" + relative).lstrip("/")
            entry = self.entries.get(key)
            if not entry:
                if optional:
                    return None
                raise ImportProblem("会话缺少引用文件：" + relative)
            return self.archive.read(entry)
        root = (self.location / self.prefix).resolve()
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ImportProblem("引用文件位于会话目录之外")
        if not path.is_file():
            if optional:
                return None
            raise ImportProblem("会话缺少引用文件：" + relative)
        return path.read_bytes()


def decode_json(data):
    return json.loads(data.decode("utf-8-sig"))


def hydrate(value, source, cache):
    if isinstance(value, list):
        return [hydrate(v, source, cache) for v in value]
    if not isinstance(value, dict):
        return value
    row = {k: hydrate(v, source, cache) for k, v in value.items()}
    for key, ref in list(row.items()):
        if not key.endswith("_ref") or not isinstance(ref, dict) or not ref.get("blob_ref"):
            continue
        target = key[:-4]
        if target in row:
            continue
        name = safe_name(ref["blob_ref"])
        if name not in cache:
            cache[name] = source.read(name)
        data = cache[name]
        if ref.get("sha256") and hashlib.sha256(data).hexdigest() != ref["sha256"]:
            raise ImportProblem("引用文件校验失败：" + name)
        try:
            row[target] = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ImportProblem("文本引用不是 UTF-8：" + name) from exc
    return row


def load_session(location, candidate=None):
    source = SessionSource(location, candidate)
    try:
        raw = source.read("events.jsonl")
        digest = hashlib.sha256(raw).hexdigest()
        cache, events, warnings = {}, [], []
        lines = raw.decode("utf-8-sig").splitlines()
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                if index == len(lines) - 1 and not raw.endswith(b"\n"):
                    warnings.append("日志末行未写完，已跳过该行；这是导入时的快照")
                    continue
                raise ImportProblem(f"events.jsonl 第 {index + 1} 行 JSON 损坏") from exc
            if not isinstance(event, dict):
                raise ImportProblem(f"events.jsonl 第 {index + 1} 行不是事件对象")
            event = hydrate(event, source, cache)
            event.setdefault("seq", index + 1)
            if not isinstance(event.get("payload"), dict):
                # Legacy UI journals remain replayable as full events. We do not
                # invent per-character timing when the source lacks deltas.
                ui = dict(event)
                event = {"seq": index + 1, "type": "legacy_ui_event", "payload": ui,
                         "timestamp": ui.get("created_at") or ui.get("timestamp") or ""}
            events.append(event)
        seqs = [int(e["seq"]) for e in events]
        if seqs != sorted(set(seqs)):
            raise ImportProblem("日志 seq 必须唯一且递增")
        if not events:
            raise ImportProblem("会话没有可重放事件")
        metadata_raw = source.read("metadata.json", optional=True)
        metadata = decode_json(metadata_raw) if metadata_raw else {}
        name = str(metadata.get("name") or source.prefix or source.location.stem)
        sid = str(next((e.get("session_id") for e in events if e.get("session_id")), source.location.stem))
        index_raw = source.read("snapshots/ui_projection_index.json", optional=True)
        snapshot_rows = []
        if index_raw:
            index = decode_json(index_raw)
            # Only use the exact existing prefix cache. History mutations need
            # the chronological projector so an earlier round is not rewritten
            # by deletions/rewrites that happened later.
            signature = index.get("source", {}).get("sha256")
            if not index.get("has_history_ops") and (not signature or signature == digest):
                for file in index.get("row_files", []):
                    contents = source.read("snapshots/" + safe_name(file), optional=True)
                    if contents is None:
                        snapshot_rows = []
                        warnings.append("历史缓存不完整，已直接从事件日志恢复历史")
                        break
                    if contents:
                        snapshot_rows.extend(hydrate(json.loads(line), source, cache)
                                             for line in contents.decode("utf-8-sig").splitlines() if line.strip())
        if hashlib.sha256(source.read("events.jsonl")).hexdigest() != digest:
            raise ImportProblem("会话仍在写入，请先复制目录或导出 ZIP 后再导入")
        return {"format_version": 1, "session_id": sid, "name": name,
                "journal_sha256": digest, "events": events, "snapshot_rows": snapshot_rows,
                "warnings": warnings, "source_label": source.location.name}
    finally:
        source.close()


def normalize_order(rows):
    rows = list(rows)
    groups, scope, previous = defaultdict(list), 0, ""
    phases = {"llm_reasoning": 0, "llm_response": 1, "tool_call": 2, "tool_result": 2}
    for index, row in enumerate(rows):
        kind = row.get("type")
        if kind in {"user", "final", "interaction_requested", "interaction_resolved",
                    "approval_requested", "approval_resolved"} or (kind == "user_steer" and row.get("steer_mode") == "interrupt"):
            scope, previous = scope + 1, ""
        if kind in phases and row.get("react_iter") is not None:
            run = str(row.get("run_id") or "")
            if run and run != previous and groups[scope]:
                scope += 1
            phase = phases[kind]
            order = row.get("tool_call_index") if phase == 2 else index
            key = (int(row["react_iter"]), phase, int(order if order is not None else index), index)
            groups[scope].append((index, row, key))
            if run:
                previous = run
        if kind == "final":
            scope, previous = scope + 1, ""
    for entries in groups.values():
        for (target, _, _), (_, row, _) in zip(entries, sorted(entries, key=lambda x: x[2])):
            rows[target] = row
    return rows


def event_ui(event):
    kind, p = event.get("type", ""), dict(event.get("payload") or {})
    if p.get("ephemeral") and (str(p.get("type", "")).endswith("_delta") or p.get("type") == "context_summary_reasoning_end"):
        return None
    timestamp = event.get("timestamp") or p.get("created_at") or ""
    if kind in {"message_user", "user_turn_committed"}:
        p.update(type="user_steer" if p.get("ui_type") == "user_steer" else "user",
                 content=p.get("ui_content") or p.get("content") or "")
    elif kind in {"message_assistant_final", "assistant_final_committed"}:
        p.update(type="final", content=p.get("ui_content") or p.get("content") or "")
    elif kind in {"tool_started", "tool_finished"}:
        p["type"] = p.get("type") or "tool_call"
    elif kind == "context_tokens":
        p["type"] = p.get("type") or "context_tokens"
    elif kind == "extension_event":
        p["type"] = kind
    elif kind.startswith(("interaction_", "approval_", "hook_", "subagent_")):
        p["type"] = kind if not kind.startswith("subagent_") else p.get("type") or kind
    elif kind in {"ui_event", "legacy_ui_event"}:
        if not p.get("type"):
            p.update(type="log", content=p.get("content") or p.get("message") or p.get("text") or "")
        if p["type"] in {"llm_reasoning", "llm_response"} and not str(p.get("content") or p.get("text") or "").strip():
            return None
    else:
        return None
    p.setdefault("created_at", timestamp)
    p.update(runtime_seq=int(event["seq"]), runtime_event_type=kind)
    p.setdefault("run_id", event.get("run_id") or "")
    return p


def project_history(events):
    rows, active_run = [], ""
    for event in events:
        kind, p = event.get("type"), event.get("payload") or {}
        run = event.get("run_id") or p.get("run_id") or ""
        if kind == "run_started":
            active_run = run
        elif kind in {"run_finished", "run_interrupted", "run_failed"} and active_run == run:
            active_run = ""
        if kind == "runtime_snapshot_compacted":
            rows = copy.deepcopy(p.get("ui_events") or [])
        elif kind == "legacy_truncate_observed":
            count = p.get("new_event_count", p.get("before_index"))
            if count is not None:
                rows = normalize_order(rows)[:max(0, int(count))]
        elif kind == "visible_range_changed":
            rows = normalize_order(rows)
            if p.get("to_ui_index") is not None:
                rows = rows[:max(0, int(p["to_ui_index"]))]
            else:
                rows = [r for r in rows if (p.get("from_seq") is None or int(r.get("runtime_seq") or 0) >= int(p["from_seq"]))
                        and (p.get("to_seq") is None or int(r.get("runtime_seq") or 0) <= int(p["to_seq"]))]
        elif kind in {"message_deleted", "message_rewritten"}:
            rows = normalize_order(rows)
            if kind == "message_deleted":
                rows = [r for r in rows if r.get("runtime_seq") != p.get("target_seq")]
            else:
                rows = [dict(r, content=p.get("content") or "", rewritten=True) if r.get("runtime_seq") == p.get("target_seq") else r for r in rows]
        else:
            row = event_ui(event)
            if row is not None:
                if not row.get("run_id"):
                    row["run_id"] = run or active_run
                rows.append(row)
    return normalize_order(rows)


DELTA_TARGETS = {"text_delta": "content", "name_delta": "tool", "arguments_delta": "arguments_raw",
                 "output_delta": "output", "stdout_delta": "stdout", "stderr_delta": "stderr"}


def merge_record(prior, update, seq):
    row = dict(prior)
    for key, value in update.items():
        if key not in DELTA_TARGETS:
            row[key] = value
    for key, target in DELTA_TARGETS.items():
        if key in update:
            row[target] = str(row.get(target) or "") + str(update[key] or "")
    terminal = {"completed", "failed", "timed_out", "interrupted", "unknown"}
    if prior.get("executed"):
        row["executed"] = True
    if prior.get("status") in terminal and update.get("status") not in terminal:
        row["status"] = prior["status"]
        if "executed" in prior:
            row["executed"] = prior["executed"]
    elif update.get("status") == "generating" and prior.get("status") and prior["status"] != "generating":
        row["status"] = prior["status"]
    row.update(last_runtime_seq=seq)
    row.setdefault("first_runtime_seq", seq)
    return row


def timestamp_ms(value):
    if not value:
        return None
    try:
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        return date.timestamp() * 1000
    except (ValueError, TypeError):
        return None


class ReplaySession:
    def __init__(self, document):
        self.document = document
        self.events = document["events"]
        self.id = document["journal_sha256"][:24]
        self.units, self.unit_events, self.run_numbers = [], {}, {}
        self.cache = OrderedDict()
        runs, steps, texts = defaultdict(list), defaultdict(list), defaultdict(list)
        active_run, implicit_run = "", 0
        for event in self.events:
            p = event.get("payload") or {}
            run = str(event.get("run_id") or p.get("run_id") or "")
            ui = event_ui(event)
            if event.get("type") == "run_started" and run:
                active_run = run
            if ui and ui.get("type") == "user" and not run:
                implicit_run += 1
                active_run = f"legacy-run-{implicit_run}"
            run = run or active_run or "legacy-run-1"
            event["_replay_run"] = run
            self.run_numbers.setdefault(run, len(self.run_numbers) + 1)
            runs[run].append(event)
            iteration = p.get("react_iter")
            if iteration is not None:
                steps[(run, str(iteration))].append(event)
            if event.get("type") == "execution_recorded" and p.get("kind") in {"reasoning", "response"}:
                texts[(run, str(p.get("execution_id") or ""))].append(event)
        # Legacy full LLM entries and their optional recorded deltas.
        native_parts = {(run, str((events[0].get("payload") or {}).get("react_iter")),
                         "llm_reasoning" if (events[0].get("payload") or {}).get("kind") == "reasoning" else "llm_response")
                        for (run, _), events in texts.items()}
        for key, events in steps.items():
            for part in ("llm_reasoning", "llm_response"):
                selected = [e for e in events if (e.get("payload") or {}).get("type") in {part, part + "_delta"}]
                if selected and (key[0], key[1], part) not in native_parts:
                    texts[(key[0], f"legacy:{key[1]}:{part}")] = selected
        for run, events in runs.items():
            self.add_unit("run", run, events)
        for (run, iteration), events in steps.items():
            self.add_unit("step", run, events, iteration=iteration)
        for (run, identity), events in texts.items():
            if identity:
                iteration = (events[0].get("payload") or {}).get("react_iter")
                self.add_unit("text", run, events, iteration=iteration, identity=identity)
        self.units.sort(key=lambda u: (u["first_seq"], u["scope"]))
        if not self.units:
            raise ImportProblem("会话没有可显示的事件")

    def add_unit(self, scope, run, events, iteration=None, identity=None):
        first, last = int(events[0]["seq"]), int(events[-1]["seq"])
        # Whole step includes intervening metrics/chrome, not unrelated steps.
        selected = events if scope == "text" else [e for e in self.events if first <= int(e["seq"]) <= last and e["_replay_run"] == run]
        uid = hashlib.sha256(f"{scope}:{run}:{iteration}:{identity}:{first}".encode()).hexdigest()[:20]
        updates = [e.get("payload") or {} for e in events]
        deltas = sum("text_delta" in p or str(p.get("type", "")).endswith("_delta") for p in updates)
        start, end = timestamp_ms(events[0].get("timestamp")), timestamp_ms(events[-1].get("timestamp"))
        unit = {"id": uid, "scope": scope, "run_id": run, "run_number": self.run_numbers[run],
                "iteration": iteration, "execution_id": identity, "first_seq": first, "last_seq": last,
                "started_at": events[0].get("timestamp") or "", "delta_count": deltas,
                "duration_ms": max(0, end - start) if start is not None and end is not None else 0,
                "kind": updates[0].get("kind") or updates[0].get("type") or scope,
                "timing_source": "durable_server_journal" if all(timestamp_ms(e.get("timestamp")) is not None for e in selected) else "missing_timestamps"}
        self.units.append(unit)
        self.unit_events[uid] = selected

    def catalog(self):
        return {k: self.document[k] for k in ("session_id", "name", "journal_sha256", "warnings", "source_label")} | {
            "id": self.id, "events": len(self.events), "run_count": len(self.run_numbers), "units": self.units}

    def segment(self, uid):
        if uid in self.cache:
            self.cache.move_to_end(uid)
            return self.cache[uid]
        unit = next((u for u in self.units if u["id"] == uid), None)
        if not unit:
            raise ImportProblem("重放轮次不存在")
        first = unit["first_seq"]
        before = [e for e in self.events if int(e["seq"]) < first]
        snapshot = self.document.get("snapshot_rows") or []
        if snapshot and not any(e.get("type") in {"message_deleted", "message_rewritten", "visible_range_changed", "legacy_truncate_observed", "runtime_snapshot_compacted"} for e in self.events):
            history = [r for r in snapshot if int(r.get("runtime_seq") or 0) < first]
        else:
            history = project_history(before)
        records, context = {}, {}
        for e in before:
            p = e.get("payload") or {}
            if e.get("type") == "execution_recorded" and p.get("execution_id"):
                key = p["execution_id"]
                records[key] = merge_record(records.get(key, {}), p, int(e["seq"]))
            elif e.get("type") == "context_tokens":
                context = p
            elif e.get("type") == "runtime_snapshot_compacted":
                base = p.get("executions") or p.get("execution_records") or []
                if isinstance(base, dict):
                    records = copy.deepcopy(base)
                elif isinstance(base, list):
                    records = {r["execution_id"]:copy.deepcopy(r) for r in base if r.get("execution_id")}
            elif e.get("type") == "message_deleted":
                records = {k:r for k,r in records.items() if int(r.get("ui_runtime_seq") or 0) != int(p.get("target_seq") or 0)}
            elif e.get("type") == "visible_range_changed" and p.get("to_seq") is not None:
                records = {k:r for k,r in records.items() if int(r.get("first_runtime_seq") or 0) <= int(p["to_seq"])}
        packets, expected, warnings = [], {}, list(self.document.get("warnings") or [])
        clock = timestamp_ms(unit["started_at"])
        prior_offset = 0
        for e in self.unit_events[uid]:
            p = dict(e.get("payload") or {})
            if e.get("type") == "execution_recorded":
                wire = {"type": "execution_update", "update": p, "ephemeral": True}
                key = p.get("execution_id")
                if key and p.get("kind") in {"reasoning", "response"}:
                    if key not in expected and key in records:
                        expected[key] = copy.deepcopy(records[key])
                    expected[key] = merge_record(expected.get(key, {}), p, int(e["seq"]))
            elif e.get("type") in {"run_started", "run_finished", "run_interrupted", "run_failed"}:
                # Replay does not end/seal the app midrange: the viewer owns its
                # playback lifecycle. Final/user/chrome events are preserved.
                continue
            else:
                wire = p if str(p.get("type", "")).endswith("_delta") else event_ui(e)
                if not wire:
                    continue
                if wire.get("type") in {"llm_reasoning", "llm_response", "llm_reasoning_delta", "llm_response_delta"}:
                    identity = p.get("execution_id") or f"legacy:{p.get('react_iter')}:{str(wire['type']).removesuffix('_delta')}"
                    row = expected.setdefault(identity, {"execution_id": identity, "kind": "reasoning" if "reasoning" in wire["type"] else "response", "react_iter": p.get("react_iter"), "content": "", "run_id": e["_replay_run"], "process_group_id": p.get("process_group_id")})
                    if wire["type"].endswith("_delta"):
                        row["content"] += str(wire.get("delta") or "")
                    else:
                        row["content"] = str(wire.get("content") or "")
            stamp = timestamp_ms(e.get("timestamp"))
            if clock is not None and stamp is not None:
                offset = max(prior_offset, stamp - clock, 0)
            else:
                offset = prior_offset
            prior_offset = offset
            wire.update(session_id="replay-session", run_id=e["_replay_run"], runtime_seq=int(e["seq"]), seq=int(e["seq"]))
            packets.append({"at_ms": round(offset, 3), "timestamp": e.get("timestamp") or "", "seq": int(e["seq"]), "wire": wire})
        if not packets:
            raise ImportProblem("该轮次没有可显示事件，请选择其它轮次")
        if not unit["delta_count"]:
            warnings.append("该范围未保存流式增量，仅按整条历史事件重放，无法还原当时逐字节奏")
        if unit["timing_source"] == "missing_timestamps":
            warnings.append("部分事件缺少时间戳，缺失部分按日志顺序立即播放")
        expected_texts = [{"execution_id": k, "kind": r.get("kind"), "iteration": r.get("react_iter"),
                           "run_id": r.get("run_id"), "process_group_id": r.get("process_group_id"),
                           "text": str(r.get("content") or ""), "sha256": hashlib.sha256(str(r.get("content") or "").encode()).hexdigest()}
                          for k, r in expected.items()]
        group = next((p["wire"].get("update", {}).get("process_group_id") or p["wire"].get("process_group_id") for p in packets if p["wire"].get("update", {}).get("process_group_id") or p["wire"].get("process_group_id")), "")
        result = dict(unit, history=history, history_records=list(records.values()), packets=packets,
                      expected_texts=expected_texts, process_group_id=group, warnings=warnings,
                      context_tokens=int(context.get("input_tokens") or context.get("estimated") or 0),
                      context_threshold=int(context.get("threshold") or 512000), model=str(context.get("model") or ""),
                      history_characters=sum(len(str(r.get("content") or r.get("result") or "")) for r in history),
                      packet_count=len(packets), duration_ms=packets[-1]["at_ms"])
        self.cache[uid] = result
        while len(self.cache) > 3:
            self.cache.popitem(last=False)
        return result
