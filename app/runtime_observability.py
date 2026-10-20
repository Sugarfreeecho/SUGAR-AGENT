"""Shared run observability for root agents, ordinary subagents, and team members.

The store is deliberately independent from the UI/runtime event projection.  It
provides one durable source for liveness, file changes, and token accounting,
and restart/stale reconciliation while Runtime V2 remains the conversation
event source of truth.
"""

from __future__ import annotations

import atexit
import copy
import hashlib
import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from proc_flags import hidden_flags


_lock = threading.RLock()
_sessions_root: Optional[Path] = None
_path_resolver: Optional[Callable[[str], str | Path]] = None
_MAX_RUNS = max(1, int(os.getenv("RUNTIME_OBSERVABILITY_MAX_RUNS", "100")))
_TERMINAL = {"finished", "failed", "interrupted", "orphaned", "stale"}
_cache: Dict[str, dict] = {}
_versions: Dict[str, int] = {}
_configuration_epoch = 0
_flush_timers: Dict[str, threading.Timer] = {}
_active_runs: set[tuple[str, str]] = set()
_FLUSH_DELAY_SEC = max(
    0.05,
    min(1.0, float(os.getenv("RUNTIME_OBSERVABILITY_FLUSH_DELAY_MS", "200")) / 1000.0),
)
_FULL_SCAN_INTERVAL_SEC = max(
    10.0,
    float(os.getenv("RUNTIME_OBSERVABILITY_FULL_SCAN_SECONDS", "60")),
)
_last_full_scan_monotonic = 0.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")



def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def configure(
    sessions_root: str | Path,
    *,
    path_resolver: Optional[Callable[[str], str | Path]] = None,
) -> None:
    global _sessions_root, _path_resolver, _last_full_scan_monotonic, _configuration_epoch
    with _lock:
        _flush_all_locked()
        for timer in _flush_timers.values():
            timer.cancel()
        _flush_timers.clear()
        _cache.clear()
        _versions.clear()
        _configuration_epoch += 1
        _active_runs.clear()
        _sessions_root = Path(sessions_root)
        _path_resolver = path_resolver
        _last_full_scan_monotonic = 0.0


def _session_dir(session_id: str) -> Path:
    sid = str(session_id or "").strip()
    if not sid:
        raise ValueError("session_id is required")
    if _path_resolver is not None:
        return Path(_path_resolver(sid))
    if _sessions_root is None:
        raise RuntimeError("runtime_observability is not configured")
    return _sessions_root / sid


def _path(session_id: str) -> Path:
    return _session_dir(session_id) / "runtime_observability.json"


def _read(session_id: str) -> dict:
    cached = _cache.get(str(session_id))
    if cached is not None:
        return cached
    path = _path(session_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("runs"), list):
            _cache[str(session_id)] = data
            return data
    except (OSError, ValueError, TypeError):
        pass
    data = {"version": 1, "session_id": str(session_id), "runs": []}
    _cache[str(session_id)] = data
    return data


def _write(session_id: str, data: dict) -> None:
    path = _path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _flush_locked(session_id: str) -> None:
    timer = _flush_timers.pop(session_id, None)
    if timer is not None and timer is not threading.current_thread():
        timer.cancel()
    data = _cache.get(session_id)
    if data is not None:
        _write(session_id, data)


def _flush_all_locked() -> None:
    for session_id in list(_flush_timers):
        _flush_locked(session_id)


def _flush_timer_fired(session_id: str) -> None:
    with _lock:
        _flush_locked(session_id)


def _schedule_write(session_id: str, data: dict, *, force: bool = False) -> None:
    sid = str(session_id)
    _cache[sid] = data
    _versions[sid] = _versions.get(sid, 0) + 1
    if force:
        _flush_locked(sid)
        return
    if sid in _flush_timers:
        return
    timer = threading.Timer(_FLUSH_DELAY_SEC, _flush_timer_fired, args=(sid,))
    timer.daemon = True
    _flush_timers[sid] = timer
    try:
        timer.start()
    except RuntimeError:
        # Diagnostics must never make an agent run fail when the process is
        # temporarily unable to allocate another native thread.
        _flush_timers.pop(sid, None)
        _write(sid, data)


def flush(session_id: Optional[str] = None) -> None:
    with _lock:
        if session_id is None:
            _flush_all_locked()
        else:
            _flush_locked(str(session_id))


atexit.register(flush)


def _run(data: dict, run_id: str, *, create: bool = False) -> Optional[dict]:
    rid = str(run_id or "").strip()
    for row in reversed(data.get("runs") or []):
        if isinstance(row, dict) and str(row.get("run_id") or "") == rid:
            return row
    if not create:
        return None
    row = {
        "run_id": rid,
        "status": "running",
        "started_at": _now(),
        "heartbeat_at": _now(),
        "usage": {},
        "file_changes": [],
    }
    data.setdefault("runs", []).append(row)
    data["runs"] = data["runs"][-_MAX_RUNS:]
    return row


def start_run(
    session_id: str,
    run_id: str,
    *,
    kind: str = "agent",
) -> dict:
    with _lock:
        data = _read(session_id)
        row = _run(data, run_id, create=True)
        assert row is not None
        row.update(
            {
                "status": "running",
                "kind": str(kind or "agent"),
                "heartbeat_at": _now(),
                "finished_at": None,
                "stale_reason": "",
            }
        )
        _active_runs.add((str(session_id), str(run_id)))
        _schedule_write(session_id, data, force=True)
        return json.loads(json.dumps(row))


def heartbeat_run(session_id: str, run_id: str, *, stage: str = "") -> Optional[dict]:
    with _lock:
        data = _read(session_id)
        row = _run(data, run_id)
        if row is None or str(row.get("status") or "") in _TERMINAL:
            return None
        row["heartbeat_at"] = _now()
        if stage:
            row["stage"] = str(stage)[:300]
        _active_runs.add((str(session_id), str(run_id)))
        _schedule_write(session_id, data)
        return json.loads(json.dumps(row))


def finish_run(session_id: str, run_id: str, status: str, *, reason: str = "") -> Optional[dict]:
    with _lock:
        data = _read(session_id)
        row = _run(data, run_id)
        if row is None:
            return None
        if str(row.get("status") or "") not in {"stale", "orphaned"}:
            row["status"] = str(status or "finished")
        row["finished_at"] = _now()
        row["heartbeat_at"] = row["finished_at"]
        if reason:
            row["terminal_reason"] = str(reason)[:4000]
        _active_runs.discard((str(session_id), str(run_id)))
        _schedule_write(session_id, data, force=True)
        return json.loads(json.dumps(row))


def mark_runs_resolved(session_id: str) -> int:
    """Mark failed/interrupted runs as resolved after a history rewrite.

    Called when the user deletes the leftover of an interrupted/failed run
    (session truncate). The runtime status probe must stop alerting on that
    stale terminal state once the user has cleaned it up.
    """
    with _lock:
        data = _read(session_id)
        changed = False
        for row in data.get("runs") or []:
            if not isinstance(row, dict):
                continue
            if (
                str(row.get("status") or "") in {"failed", "interrupted"}
                and not row.get("resolved")
            ):
                row["resolved"] = True
                row["resolved_at"] = _now()
                changed = True
        if changed:
            _schedule_write(session_id, data, force=True)
        return sum(
            1
            for row in data.get("runs") or []
            if isinstance(row, dict) and row.get("resolved")
        )


def record_usage(
    session_id: str,
    run_id: str,
    usage: Optional[dict],
) -> Optional[dict]:
    with _lock:
        data = _read(session_id)
        row = _run(data, run_id)
        if row is None:
            return None
        current = row.setdefault("usage", {})
        clean_usage = {
            str(key): _int(value)
            for key, value in (usage or {}).items()
            if isinstance(value, (int, float)) and not str(key).startswith("_")
        }
        for key, value in clean_usage.items():
            current[key] = _int(current.get(key)) + value
        row["heartbeat_at"] = _now()
        _schedule_write(session_id, data)
        return json.loads(json.dumps(row))


def record_file_changes(
    session_id: str,
    run_id: str,
    changes: Iterable[dict],
    *,
    tool: str = "",
) -> Optional[dict]:
    with _lock:
        data = _read(session_id)
        row = _run(data, run_id)
        if row is None:
            return None
        existing = {
            (str(item.get("path") or ""), str(item.get("operation") or "")): item
            for item in (row.get("file_changes") or [])
            if isinstance(item, dict)
        }
        for raw in changes or ():
            if not isinstance(raw, dict):
                continue
            path = str(raw.get("path") or "").strip()
            if not path:
                continue
            operation = str(raw.get("operation") or "modified")
            item = {
                "path": path[:4000],
                "operation": operation[:80],
                "tool": str(tool or raw.get("tool") or "")[:200],
                "observed_at": _now(),
            }
            if raw.get("source"):
                item["source"] = str(raw.get("source"))[:80]
            existing[(item["path"], item["operation"])] = item
        row["file_changes"] = list(existing.values())[-2000:]
        row["heartbeat_at"] = _now()
        _schedule_write(session_id, data)
        return json.loads(json.dumps(row))


def snapshot(session_id: str) -> dict:
    with _lock:
        return json.loads(json.dumps(_read(session_id)))


def _parse_time(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _observability_paths(root: Optional[Path]) -> list[Path]:
    """Walk session containers and their subagents, excluding task file trees.

    Runtime V2 stores child sessions only under ``subagents/<id>``. Recursing
    through every task's checkout, downloads and node_modules adds unrelated
    filesystem work to the watchdog even when the lock itself is released.
    """
    if root is None:
        return []

    def children(container):
        try:
            with os.scandir(container) as entries:
                return [Path(entry.path) for entry in entries
                        if entry.is_dir(follow_symlinks=False)
                        and not (getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400)]
        except OSError:
            return []

    pending, paths = children(root), []
    while pending:
        session = pending.pop()
        path = session / "runtime_observability.json"
        if path.is_file():
            paths.append(path)
        # Do not follow a linked subagent container into an unrelated tree.
        container = session / "subagents"
        try:
            linked = container.is_symlink() or bool(
                getattr(container.lstat(), "st_file_attributes", 0) & 0x400)
            if not linked:
                pending.extend(children(container))
        except OSError:
            pass
    return paths


def _stale_scan_paths() -> list[Path]:
    """Scan active sessions normally and periodically reconcile all files."""
    global _last_full_scan_monotonic
    with _lock:
        now = time.monotonic()
        full_scan = (
            _last_full_scan_monotonic <= 0
            or now - _last_full_scan_monotonic >= _FULL_SCAN_INTERVAL_SEC
        )
        if full_scan:
            _last_full_scan_monotonic = now
        root = _sessions_root
        active = tuple(_active_runs)
    if full_scan:
        return _observability_paths(root)
    paths: list[Path] = []
    seen: set[Path] = set()
    for session_id, _ in active:
        path = _path(session_id)
        if path not in seen and path.exists():
            seen.add(path)
            paths.append(path)
    return paths


def _scan_states(paths, epoch):
    """Read scan inputs without blocking live heartbeats on filesystem work.

    Pending process-local updates win over disk. A version check at publication
    rejects a scan if a heartbeat, usage update or terminal commit overtook it.
    Do not force-flush all sessions just to reconcile one background scan.
    """
    for path in paths:
        sid = path.parent.name
        with _lock:
            version_before_read = _versions.get(sid, 0)
            pending_before_read = sid in _flush_timers
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
            continue
        sid = str(data.get("session_id") or sid)
        with _lock:
            if epoch != _configuration_epoch:
                return
            if _versions.get(sid, 0) != version_before_read:
                continue  # A live update overtook this filesystem read.
            if sid in _cache and (pending_before_read or sid in _flush_timers):
                data = _cache[sid]
            else:
                _cache[sid] = data
                # Also invalidate another scanner's captured view.
                _versions[sid] = _versions.get(sid, 0) + 1
            version = _versions.get(sid, 0)
            captured = copy.deepcopy(data)
        yield sid, captured, version


def _publish_scan_state(sid, data, version, epoch, *, changed, active, inactive):
    with _lock:
        if epoch != _configuration_epoch or _versions.get(sid, 0) != version:
            return False
        _active_runs.update(active)
        _active_runs.difference_update(inactive)
        if changed:
            _schedule_write(sid, data, force=True)
        return True


def _scan_timing(operation, started, enumeration_ms, candidates, skipped):
    elapsed_ms = (time.perf_counter() - started) * 1000
    if elapsed_ms >= 100:
        try:
            logging.getLogger("agent_harness").info(
                "observability_scan_timing op=%s total_ms=%.3f enumeration_ms=%.3f "
                "candidates=%d concurrent_updates_skipped=%d",
                operation, elapsed_ms, enumeration_ms, candidates, skipped,
            )
        except Exception:
            pass  # A failed diagnostic sink must not stop the watchdog.


def scan_stale_runs(
    max_age_seconds: float,
    *,
    live_checker: Optional[Callable[[str, str], bool]] = None,
    mark: bool = True,
    terminal_status: str = "stale",
) -> list[dict]:
    if _sessions_root is None or not _sessions_root.exists():
        return []
    cutoff = max(1.0, float(max_age_seconds))
    now = datetime.now(timezone.utc)
    stale: list[dict] = []
    started = time.perf_counter()
    with _lock:
        epoch = _configuration_epoch
    paths = _stale_scan_paths()
    enumeration_ms = (time.perf_counter() - started) * 1000
    candidates = skipped = 0
    try:
        for sid, data, version in _scan_states(paths, epoch):
            candidates += 1
            changed = False
            found, active, inactive = [], set(), set()
            for row in data.get("runs") or []:
                if not isinstance(row, dict) or str(row.get("status") or "") != "running":
                    continue
                rid = str(row.get("run_id") or "")
                if live_checker is not None:
                    try:
                        if live_checker(sid, rid):
                            active.add((sid, rid))
                            continue
                    except Exception:
                        pass
                stamp = _parse_time(row.get("heartbeat_at") or row.get("started_at"))
                age = cutoff + 1 if stamp is None else max(0.0, (now - stamp).total_seconds())
                if age <= cutoff:
                    active.add((sid, rid))
                    continue
                item = {
                    "session_id": sid,
                    "run_id": rid,
                    "age_seconds": round(age, 3),
                    "kind": str(row.get("kind") or "agent"),
                }
                found.append(item)
                if mark:
                    row["status"] = terminal_status
                    row["finished_at"] = _now()
                    row["stale_reason"] = f"heartbeat older than {cutoff:g}s"
                    changed = True
                    inactive.add((sid, rid))
            if _publish_scan_state(sid, data, version, epoch, changed=changed,
                                   active=active, inactive=inactive):
                stale.extend(found)
            else:
                skipped += 1
    finally:
        _scan_timing("stale", started, enumeration_ms, candidates, skipped)
    return stale


def reconcile_orphaned_runs(
    *,
    live_checker: Optional[Callable[[str, str], bool]] = None,
    owner_checker: Optional[Callable[[str, str], bool]] = None,
    grace_seconds: float = 0,
) -> list[dict]:
    """Mark orphaned rows, preserving externally owned and recent runs."""
    if _sessions_root is None or not _sessions_root.exists():
        return []
    orphaned: list[dict] = []
    started = time.perf_counter()
    with _lock:
        epoch, root = _configuration_epoch, _sessions_root
    paths = _observability_paths(root)
    enumeration_ms = (time.perf_counter() - started) * 1000
    candidates = skipped = 0
    try:
        for sid, data, version in _scan_states(paths, epoch):
            candidates += 1
            changed = False
            found, active, inactive = [], set(), set()
            for row in data.get("runs") or []:
                if not isinstance(row, dict) or str(row.get("status") or "") != "running":
                    continue
                rid = str(row.get("run_id") or "")
                if live_checker is not None:
                    try:
                        if live_checker(sid, rid):
                            active.add((sid, rid))
                            continue
                    except Exception:
                        pass
                if owner_checker is not None:
                    try:
                        if owner_checker(sid, rid):
                            # Foreign ownership is not process-local activity.
                            continue
                    except Exception:
                        pass
                if grace_seconds > 0:
                    stamp = _parse_time(row.get("heartbeat_at") or row.get("started_at"))
                    if stamp is not None and (
                        datetime.now(timezone.utc) - stamp
                    ).total_seconds() <= grace_seconds:
                        continue
                found.append(
                    {
                        "session_id": sid,
                        "run_id": rid,
                        "kind": str(row.get("kind") or "agent"),
                    }
                )
                row["status"] = "orphaned"
                row["finished_at"] = _now()
                row["stale_reason"] = "process restarted before run completion"
                changed = True
                inactive.add((sid, rid))
            if _publish_scan_state(sid, data, version, epoch, changed=changed,
                                   active=active, inactive=inactive):
                orphaned.extend(found)
            else:
                skipped += 1
    finally:
        _scan_timing("orphaned", started, enumeration_ms, candidates, skipped)
    return orphaned


def _git_output(root: Path, args: list[str]) -> Optional[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=True,
            creationflags=hidden_flags(),
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def _file_audit_mode() -> str:
    """Resolve the file audit mode: off (default), git, or full."""
    raw = os.getenv("FILE_AUDIT_MODE", "").strip().lower()
    if raw:
        key = raw.replace("-", "_").replace(" ", "_")
        if key in {"0", "false", "no", "off", "disabled", "none"}:
            return "off"
        if key in {"git", "git_status"}:
            return "git"
        if key in {
            "1",
            "true",
            "yes",
            "on",
            "full",
            "full_snapshot",
            "snapshot",
            "walk",
            "workspace",
        }:
            return "full"
    return "off"


def capture_workspace_state(work_dir: str | Path | None) -> dict:
    """Capture a workspace state used to audit arbitrary tool writes.

    FILE_AUDIT_MODE selects the audit depth:
      - off: file audit is disabled and no state is captured (default);
      - git: only the Git worktree status is used;
      - full: additionally walks the whole workspace, bounded by
        FILE_AUDIT_MAX_FILES.
    """
    if not work_dir or _file_audit_mode() == "off":
        return {"root": "", "files": {}}
    root_raw = Path(work_dir).resolve()
    top = _git_output(root_raw, ["rev-parse", "--show-toplevel"])
    root = (
        Path(top.decode("utf-8", errors="replace").strip()).resolve()
        if top is not None
        else root_raw
    )
    status = (
        _git_output(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
        if top is not None
        else b""
    )
    files: Dict[str, dict] = {}
    if status is None:
        status = b""
    chunks = status.decode("utf-8", errors="replace").split("\0")
    index = 0
    while index < len(chunks):
        item = chunks[index]
        index += 1
        if not item:
            continue
        code = item[:2]
        rel = item[3:] if len(item) > 3 else ""
        if code and code[0] in {"R", "C"} and index < len(chunks):
            rel = chunks[index] or rel
            index += 1
        if not rel:
            continue
        target = root / rel
        fingerprint = "missing"
        try:
            stat = target.stat()
            if target.is_file():
                digest = hashlib.sha256()
                with target.open("rb") as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(block)
                fingerprint = f"{stat.st_size}:{stat.st_mtime_ns}:{digest.hexdigest()}"
            else:
                fingerprint = f"dir:{stat.st_mtime_ns}"
        except OSError:
            pass
        files[rel.replace("\\", "/")] = {"status": code, "fingerprint": fingerprint}
    if _file_audit_mode() == "full":
        excluded = {
            ".git",
            ".hg",
            ".svn",
            ".venv",
            "venv",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".trash",
            "sessions",
        }
        limit = max(1000, int(os.getenv("FILE_AUDIT_MAX_FILES", "100000")))
        seen_count = 0
        for current_root, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                name
                for name in dirnames
                if name not in excluded and not name.startswith(".myagent-worktrees")
            ]
            current = Path(current_root)
            for filename in filenames:
                seen_count += 1
                if seen_count > limit:
                    return {
                        "root": str(root),
                        "files": files,
                        "truncated": True,
                    }
                target = current / filename
                try:
                    rel = target.relative_to(root).as_posix()
                    stat = target.stat()
                except OSError:
                    continue
                if rel in files:
                    continue
                files[rel] = {
                    "status": "FS",
                    "fingerprint": f"{stat.st_size}:{stat.st_mtime_ns}",
                }
    return {"root": str(root), "files": files}


def diff_workspace_states(before: Optional[dict], after: Optional[dict]) -> list[dict]:
    left = (before or {}).get("files") if isinstance(before, dict) else {}
    right = (after or {}).get("files") if isinstance(after, dict) else {}
    left = left if isinstance(left, dict) else {}
    right = right if isinstance(right, dict) else {}
    changes: list[dict] = []
    for path in sorted(set(left) | set(right)):
        if left.get(path) == right.get(path):
            continue
        if path not in right:
            operation = "deleted"
        elif path not in left:
            operation = "created"
        else:
            status = str((right.get(path) or {}).get("status") or "")
            operation = "deleted" if "D" in status else "modified"
        status = str(
            ((right if path in right else left).get(path) or {}).get("status") or ""
        )
        changes.append(
            {
                "path": path,
                "operation": operation,
                "source": "filesystem_snapshot" if status == "FS" else "git_worktree",
            }
        )
    return changes
