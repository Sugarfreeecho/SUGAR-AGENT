"""Owned scratch and retained tool results below the global WORK_DIR/TempOutput."""
from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import threading
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path, PureWindowsPath

logger = logging.getLogger(__name__)
DIRECTORY = "TempOutput"
MARKER = ".owner.json"
_current: ContextVar[RunFiles | None] = ContextVar("runtime_files", default=None)
_lock = threading.RLock()
_fallback: dict[tuple[str, str], RunFiles] = {}


def _segment(value: str, default: str) -> str:
    value = str(value or default)
    if re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        return value
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def _link(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _directory(parent: Path, name: str) -> Path:
    path = parent / name
    if _link(path):
        raise ValueError(f"Runtime directory cannot be a link: {path}")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.resolve().parent != parent.resolve():
        raise ValueError(f"Runtime directory escaped its owner: {path}")
    return path


def output_root(work_dir: Path | str) -> Path:
    return _directory(Path(work_dir).resolve(), DIRECTORY)


def _identity(pid: int | None = None) -> dict:
    import psutil
    process = psutil.Process(pid or os.getpid())
    return {"pid": process.pid, "created": process.create_time()}


def _alive(identity: dict) -> bool:
    import psutil
    try:
        process = psutil.Process(int(identity["pid"]))
        return abs(process.create_time() - float(identity["created"])) < .01
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return False
    except (psutil.AccessDenied, KeyError, ValueError, TypeError):
        return True  # Unknown ownership must never authorize deletion.


def _atomic_json(path: Path, value: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".owner-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _remove_owned(path: Path, scratch: Path) -> bool:
    # 根因：会话 cwd 可改变，清理必须验证分配根，不能按当前项目或文件名递归删除。
    if any(_link(item) for item in (scratch.parent, scratch, path.parent, path)):
        return False
    if not path.resolve().is_relative_to(scratch.resolve()) or path.resolve() == scratch.resolve():
        return False
    try:
        # Verification above uses ordinary canonical paths. Native children
        # can create long filenames below this owned directory; Windows Python
        # also needs the extended spelling when recursively removing them.
        target = str(path.resolve())
        if os.name == "nt" and not target.startswith("\\\\?\\"):
            target = "\\\\?\\UNC\\" + target[2:] if target.startswith("\\\\") else "\\\\?\\" + target
        shutil.rmtree(target)
        try:
            path.parent.rmdir()
        except OSError:
            pass  # Other runs may still own this session directory.
        return True
    except FileNotFoundError:
        return True
    except OSError:
        logger.warning("Scratch cleanup deferred: %s", path, exc_info=True)
        return False


class ScratchLease:
    def __init__(self, owner: RunFiles):
        self.owner = owner
        self.id = uuid.uuid4().hex
        self.closed = False
        with _lock:
            owner.scratch_dir
            owner.leases[self.id] = None
            try:
                owner._save()
            except BaseException:
                owner.leases.pop(self.id, None)
                raise

    def track_process(self, pid: int) -> None:
        import psutil
        with _lock:
            try:
                self.owner.leases[self.id] = _identity(pid)
            except psutil.NoSuchProcess:
                self.owner.leases[self.id] = {"pid": pid, "created": -1}
            self.owner._save()

    def release(self) -> None:
        with _lock:
            if self.closed:
                return
            self.closed = True
            self.owner.leases.pop(self.id, None)
            try:
                self.owner._save()
            except OSError:
                logger.warning("Scratch lease persistence deferred", exc_info=True)
            self.owner._cleanup()


class RunFiles:
    def __init__(self, work_dir: Path | str, session_id: str, run_id: str):
        self.work_dir = Path(work_dir).resolve()
        self.session_id = _segment(session_id, "standalone")
        self.run_id = _segment(run_id, "run")
        self.path: Path | None = None
        self.closed = False
        self.leases: dict[str, dict | None] = {}

    @property
    def scratch_dir(self) -> Path:
        with _lock:
            if self.path is None:
                scratch = _directory(output_root(self.work_dir), "scratch")
                parent = _directory(scratch, self.session_id)
                self.path = Path(tempfile.mkdtemp(prefix=self.run_id + "-", dir=parent))
                try:
                    self._save()
                except BaseException:
                    _remove_owned(self.path, scratch)
                    self.path = None
                    raise
            return self.path

    def _save(self) -> None:
        if self.path is not None and self.path.exists():
            _atomic_json(self.path / MARKER, {
                "version": 1, "host": _identity(), "closed": self.closed,
                "pending": sum(value is None for value in self.leases.values()),
                "processes": [value for value in self.leases.values() if value],
            })

    def temporary_path(self, raw: str) -> Path:
        root = self.scratch_dir
        text = str(raw or "output.txt")
        parts = PureWindowsPath(text).parts
        if ".." in parts:
            raise ValueError("Temporary filenames cannot contain '..'")
        candidate = Path(text)
        if candidate.is_absolute() and candidate.resolve().is_relative_to(root):
            result = candidate
        else:
            # Absolute project paths are names only; temporary=True never overwrites project files.
            relative = PureWindowsPath(text).name if candidate.is_absolute() or PureWindowsPath(text).is_absolute() else text
            result = root.joinpath(*PureWindowsPath(relative).parts)
        if not result.resolve().is_relative_to(root) or result.resolve() == root:
            raise ValueError("Temporary file escaped its allocated scratch directory")
        if result == root / MARKER:
            raise ValueError("Scratch ownership metadata is reserved")
        return result

    def hold(self) -> ScratchLease:
        return ScratchLease(self)

    def finish(self) -> None:
        with _lock:
            self.closed = True
            self._save()
            self._cleanup()

    def _cleanup(self) -> None:
        if self.closed and not self.leases and self.path is not None:
            _remove_owned(self.path, self.work_dir / DIRECTORY / "scratch")


def current_run(work_dir: Path | str, session_id: str = "") -> RunFiles:
    bound = _current.get()
    if bound is not None:
        return bound
    key = (str(Path(work_dir).resolve()), str(session_id or "standalone"))
    with _lock:
        owner = _fallback.get(key)
        if owner is None or owner.closed:
            owner = _fallback[key] = RunFiles(work_dir, session_id, "standalone")
        return owner


def authorized_scratch_dirs(directories: list[Path], session_id: str = "") -> list[Path]:
    """Add only the current run's allocated scratch, never the shared output root."""
    owner = _current.get()
    if owner is None or owner.path is None or owner.closed:
        return list(directories)
    if session_id and owner.session_id != _segment(session_id, "standalone"):
        return list(directories)
    return [*directories, owner.path]


@contextmanager
def run_scope(work_dir: Path | str, session_id: str, run_id: str = "", *, cleanup: bool = True):
    owner = RunFiles(work_dir, session_id, run_id)
    token = _current.set(owner)
    try:
        yield owner
    finally:
        _current.reset(token)
        if cleanup:
            try:
                owner.finish()
            except OSError:
                logger.warning("Scratch ownership cleanup deferred", exc_info=True)


def save_tool_result(work_dir: Path | str, session_id: str, call_id: str, text: str) -> Path:
    parent = _directory(output_root(work_dir), "tool-results")
    parent = _directory(parent, _segment(session_id, "standalone"))
    name = _segment(call_id or uuid.uuid4().hex, "result")
    path = parent / name
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        path = Path(tempfile.mkdtemp(prefix=name + "-", dir=parent))
    result = path / "result.txt"
    try:
        with result.open("x", encoding="utf-8") as stream:
            if os.name != "nt":
                os.chmod(result, 0o600)
            stream.write(text)
    except BaseException:
        try:
            result.unlink(missing_ok=True)
            path.rmdir()
        except OSError:
            logger.warning("Incomplete tool result cleanup deferred: %s", path, exc_info=True)
        raise
    return result.resolve()


def cleanup_stale_scratch(work_dir: Path | str) -> int:
    scratch = Path(work_dir).resolve() / DIRECTORY / "scratch"
    if not scratch.is_dir() or _link(scratch) or _link(scratch.parent):
        return 0
    removed = 0
    try:
        sessions = list(scratch.iterdir())
    except OSError:
        logger.warning("Scratch recovery scan deferred", exc_info=True)
        return 0
    for session in sessions:
        if not session.is_dir() or _link(session):
            continue
        try:
            runs = list(session.iterdir())
        except OSError:
            logger.warning("Scratch session recovery deferred: %s", session, exc_info=True)
            continue
        for path in runs:
            marker = path / MARKER
            if not path.is_dir() or _link(path) or _link(marker):
                continue
            try:
                if marker.stat().st_size > 65536:
                    continue
                record = json.loads(marker.read_text(encoding="utf-8"))
                if record.get("version") != 1 or not isinstance(record.get("processes"), list):
                    continue
                if record.get("pending", 0):
                    continue  # A startup handoff without a process identity is not proven idle.
                if (record.get("closed") is not True and _alive(record.get("host", {}))) or any(_alive(value) for value in record["processes"]):
                    continue
                removed += int(_remove_owned(path, scratch))
            except (OSError, ValueError, TypeError, AttributeError):
                logger.warning("Skipped unreadable scratch owner: %s", marker, exc_info=True)
    return removed


def _shutdown() -> None:
    for owner in tuple(_fallback.values()):
        try:
            owner.finish()
        except OSError:
            logger.debug("Standalone scratch cleanup deferred", exc_info=True)


atexit.register(_shutdown)
