"""盘点并清理 logs/ 下的会话日志。

默认 dry-run：只打印候选文件、释放空间与保护名单，不删除任何东西。
加 ``--delete`` 才会真正删除。

用法：
    python scripts/prune_agent_logs.py
    python scripts/prune_agent_logs.py --days 7 --max-mb 256
    python scripts/prune_agent_logs.py --delete
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_DIR = Path(os.getenv("LOG_DIR") or (PROJECT_ROOT / "logs"))
PROTECTED = frozenset({"agent_terminal.log", "agent_update.log", "launcher_console.log"})


def _iter_logs(log_dir: Path):
    for path in log_dir.iterdir():
        if not path.is_file() or path.name in PROTECTED:
            continue
        if path.name.endswith(".log") or ".log." in path.name:
            yield path


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def collect(log_dir: Path, days: int, max_mb: int) -> list[Path]:
    files = list(_iter_logs(log_dir))
    if not files:
        return []
    now = time.time()
    expired: list[Path] = []
    if days > 0:
        cutoff = now - days * 86400
        expired = [p for p in files if _mtime(p) < cutoff]
    remaining = [p for p in files if p not in expired]
    oversize: list[Path] = []
    if max_mb > 0:
        total = sum(_size(p) for p in remaining)
        limit = max_mb * 1024 * 1024
        if total > limit:
            for path in sorted(remaining, key=_mtime):
                if total <= limit:
                    break
                oversize.append(path)
                total -= _size(path)
    return expired + oversize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="盘点并清理 Agent 会话日志")
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR), help="日志目录，默认 LOG_DIR 或 <repo>/logs")
    parser.add_argument("--days", type=int, default=int(os.getenv("LOG_RETENTION_DAYS", "14")),
                        help="保留天数，0 表示不按时间清理")
    parser.add_argument("--max-mb", type=int, default=int(os.getenv("LOG_TOTAL_MAX_MB", "512")),
                        help="目录总量上限（MB），0 表示不按总量清理")
    parser.add_argument("--delete", action="store_true", help="真正删除；缺省只打印候选")
    args = parser.parse_args(argv)

    log_dir = Path(args.log_dir)
    if not log_dir.is_dir():
        print(f"日志目录不存在: {log_dir}")
        return 1

    files = list(_iter_logs(log_dir))
    total_mb = sum(_size(p) for p in files) / 1048576
    candidates = collect(log_dir, args.days, args.max_mb)
    freed_mb = sum(_size(p) for p in candidates) / 1048576
    print(f"日志目录: {log_dir}")
    print(f"会话日志: {len(files)} 个文件, {total_mb:.1f} MiB")
    print(f"保留策略: days={args.days} max_mb={args.max_mb}")
    print(f"候选: {len(candidates)} 个文件, {freed_mb:.1f} MiB")
    for path in candidates[:50]:
        print(f"  {path.name}  {_size(path) / 1024:.0f} KiB")
    if len(candidates) > 50:
        print(f"  … 其余 {len(candidates) - 50} 个")
    if not args.delete:
        print("\n[dry-run] 未删除任何文件；确认后加 --delete 执行。")
        return 0
    removed = 0
    for path in candidates:
        try:
            path.unlink()
            removed += 1
        except OSError as exc:
            print(f"跳过 {path.name}: {exc}")
    print(f"\n已删除 {removed} 个文件，释放 {freed_mb:.1f} MiB。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
