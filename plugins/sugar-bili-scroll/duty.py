"""值班状态 —— 谷时窗口、判重表、配额对账、归档、章程装载。

全部照搬 DSH 原版 lib/state.mjs + index.js 的语义，只把 JS 换成 Python：

  · WINDOWS 的官方口径：**高峰 = 工作日 9:00–12:00 与 14:00–18:00，其余全是谷时**
    ⇒ 12:00–14:00、18:00 之后一整晚、以及整个周末都便宜。
  · 配额数的是日报里 `### BV号` 的**标题行去重数**，不是「报告里出现的所有 BV」。
  · 章程用 sha256 记账制升级：家里那份改过 ⇒ 一个字都不动，新版另存 .new。
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

DEFAULT_WINDOWS = ("12:00-14:00", "18:00-09:00")
LOG_MAX_BYTES = 1024 * 1024
LOG_BACKUPS = 3
_LOG_LOCK = threading.Lock()

# 宿主数配额用的就是这个格式：行首 ## 或 ### 紧跟 BV 号（顶格）
PICK_RE = re.compile(r"^#{2,3}[ \t]*(BV[0-9A-Za-z]{10})", re.MULTILINE)
BV_RE = re.compile(r"BV[0-9A-Za-z]{10}")
FENCE_RE = re.compile(r"```[\s\S]*?```")


# ── 路径 ────────────────────────────────────────────────────────────────

def day_key(now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    return f"{now.year:04d}-{now.month:02d}-{now.day:02d}"


def month_key(now: Optional[datetime] = None) -> str:
    return day_key(now)[:7]


def out_dir(home: Path) -> Path:
    path = Path(home) / "out"
    path.mkdir(parents=True, exist_ok=True)
    return path


def digest_dir(home: Path) -> Path:
    path = Path(home) / "digest"
    path.mkdir(parents=True, exist_ok=True)
    return path


def report_file(home: Path, now: Optional[datetime] = None) -> Path:
    return out_dir(home) / f"{day_key(now)}.md"


def digest_file(home: Path, now: Optional[datetime] = None) -> Path:
    return digest_dir(home) / f"{month_key(now)}.md"


def seen_file(home: Path) -> Path:
    return Path(home) / "seen.md"


def state_file(home: Path) -> Path:
    return Path(home) / "duty-state.json"


def log_file(home: Path) -> Path:
    return Path(home) / "duty.log"


# ── 谷时窗口 ────────────────────────────────────────────────────────────

def parse_windows(spec: Any) -> list[tuple[int, int]]:
    """'12:00-14:00,18:00-09:00' → [(720, 840), (1080, 540)]（分钟，支持跨零点）"""
    if isinstance(spec, (list, tuple)):
        items = [str(x) for x in spec]
    else:
        items = [p.strip() for p in str(spec or "").split(",") if p.strip()]
    if not items:
        items = list(DEFAULT_WINDOWS)
    windows: list[tuple[int, int]] = []
    for item in items:
        start_text, _, end_text = item.partition("-")
        start = _minutes(start_text)
        end = _minutes(end_text)
        if start is None or end is None:
            continue
        windows.append((start, end))
    return windows or [(720, 840), (1080, 540)]


def _minutes(text: str) -> Optional[int]:
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(text or ""))
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour * 60 + minute


def in_window(now: datetime, windows: Iterable[tuple[int, int]]) -> bool:
    current = now.hour * 60 + now.minute
    for start, end in windows:
        if start <= end:
            if start <= current < end:
                return True
        elif current >= start or current < end:  # 跨零点
            return True
    return False


# ── 判重表 / 配额 ───────────────────────────────────────────────────────

def count_picks(home: Path, now: Optional[datetime] = None) -> int:
    """数今天的报告里 `### BV号` 去重后的条数。

    ⚠️ 围栏 ``` 里的内容不看：占位报告会把日志尾部贴进来，那里的 BV 是"看过的"。
    ⚠️ 数不出来就当 0：宁可少算（顶多多跑一轮），也别把"提到过"算成"挑中"。
    """
    path = report_file(home, now)
    try:
        text = FENCE_RE.sub("", path.read_text(encoding="utf-8"))
    except OSError:
        return 0
    return len({m.group(1) for m in PICK_RE.finditer(text)})


def pick_ids(home: Path, now: Optional[datetime] = None) -> list[str]:
    """今天报告里挑中的 BV 号（去重、保持出现顺序）。

    自动收藏要用它：`count_picks` 只数条数，这里要具体是哪几条。
    """
    path = report_file(home, now)
    try:
        text = FENCE_RE.sub("", path.read_text(encoding="utf-8"))
    except OSError:
        return []
    seen: list[str] = []
    for match in PICK_RE.finditer(text):
        bvid = match.group(1)
        if bvid not in seen:
            seen.append(bvid)
    return seen


def seen_bvids(home: Path) -> set[str]:
    try:
        text = seen_file(home).read_text(encoding="utf-8")
    except OSError:
        return set()
    return set(BV_RE.findall(text))


def read_state(home: Path) -> dict:
    try:
        data = json.loads(state_file(home).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(home: Path, value: dict) -> None:
    path = state_file(home)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def picks_today(home: Path, now: Optional[datetime] = None) -> int:
    """报告是事实来源，state 兜住「报告被删/手改」那一下，取两者大的。"""
    state = read_state(home)
    from_state = (
        int(state.get("picked") or 0) if state.get("day") == day_key(now) else 0
    )
    return max(from_state, count_picks(home, now))


def rounds_today(home: Path, now: Optional[datetime] = None) -> int:
    state = read_state(home)
    return int(state.get("count") or 0) if state.get("day") == day_key(now) else 0


def note_round(home: Path, *, picked: int = 0, note: str = "") -> dict:
    now = datetime.now()
    state = read_state(home)
    if state.get("day") != day_key(now):
        state = {"day": day_key(now), "count": 0, "picked": 0}
    state["count"] = int(state.get("count") or 0) + 1
    state["picked"] = max(int(state.get("picked") or 0), int(picked))
    state["last_round_at"] = now.isoformat(timespec="seconds")
    if note:
        state["last_note"] = note[:500]
    write_state(home, state)
    return state


def last_round_at(home: Path) -> Optional[datetime]:
    raw = str(read_state(home).get("last_round_at") or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


# ── 章程 ────────────────────────────────────────────────────────────────

def ensure_charter(shipped: Path, home: Path) -> Path:
    """把随包章程铺到家里，并用 sha256 记账判断「用户改过没有」。"""
    target = Path(home) / "duty.md"
    ledger = Path(home) / "charter.sha256"
    fresh = Path(home) / "duty.md.new"
    try:
        text = Path(shipped).read_text(encoding="utf-8")
    except OSError:
        return target

    shipped_sha = _sha(text)
    if not target.is_file():
        target.write_text(text, encoding="utf-8")
        ledger.write_text(shipped_sha, encoding="utf-8")
        return target

    try:
        home_sha = _sha(target.read_text(encoding="utf-8"))
        last_sha = ledger.read_text(encoding="utf-8").strip()
    except OSError:
        return target

    if home_sha == shipped_sha:
        if last_sha != shipped_sha:
            ledger.write_text(shipped_sha, encoding="utf-8")
        return target

    if not last_sha or home_sha != last_sha:
        # 用户改过（或没账本、分不清）⇒ 只把新版另存，绝不动他那份
        if shipped_sha != last_sha and (
            not fresh.is_file() or fresh.read_text(encoding="utf-8") != text
        ):
            fresh.write_text(text, encoding="utf-8")
        return target

    target.write_text(text, encoding="utf-8")
    ledger.write_text(shipped_sha, encoding="utf-8")
    return target


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


SEEN_HEADER = """# 判重表（看过的视频）

<!-- 每行格式：- BV号 · 日期 · 判定（挑中 / 跳过：原因 / 未判读） -->
<!-- 调度器只会读这张表；往这里追加请保持一条一行。 -->

"""


def ensure_notes(home: Path) -> None:
    """开户即把判重表 / 月摘要铺好。

    不铺的后果实测过：第一轮模型读 `seen.md` 报 "not a file"，得当场停下来
    建文件、还要在日报里解释一遍 —— 白白多花一段推理。空表本身就是
    「还没看过任何东西」这个合法状态，不如一开始就给它一个空表。
    """
    for path, text in (
        (seen_file(home), SEEN_HEADER),
        (digest_file(home), f"# {month_key()} 观察摘要\n\n"),
    ):
        try:
            if not path.is_file():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
        except OSError:
            pass


def read_charter(home: Path) -> str:
    try:
        return (Path(home) / "duty.md").read_text(encoding="utf-8")
    except OSError:
        return ""


def stub_report_if_missing(home: Path, reason: str) -> Optional[Path]:
    """那一轮没写出报告时，宿主自己补一份占位报告。

    起因见 DSH 原版：一轮卡在某个工具上反复重试，最后 out/ 是空的、
    使用者完全看不到发生了什么，也不知道白烧了钱。
    """
    path = report_file(home)
    if path.is_file():
        return None
    tail = ""
    try:
        tail = log_file(home).read_text(encoding="utf-8")[-1500:]
    except OSError:
        pass
    path.write_text(
        "\n".join(
            [
                f"# 刷B站 · {day_key()} —— 这一轮没写出报告",
                "",
                f"> ⚠️ 那一轮结束了，但没有生成正常报告（{reason}）。",
                "> 常见原因是它卡在某个工具上反复重试、或者把预算烧完了。下一轮它会重来。",
                "",
                "```",
                tail.strip(),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def drop_stub(home: Path) -> bool:
    """真报告写出来之后，把开头那段「这一轮没写出报告」的占位删掉。

    实测踩过：前一轮 0 条留了占位，下一轮把报告**追加**在它后面 ——
    打开日报第一眼是"没写出报告"，往下翻却是 8 条，自相矛盾。
    只在占位确实被"追加了内容"时才动手，否则保持原样。
    """
    path = report_file(home)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    head = f"# 刷B站 · {day_key()} —— 这一轮没写出报告"
    if not text.startswith(head):
        return False
    open_fence = text.find("```")
    if open_fence < 0:
        return False
    close_fence = text.find("```", open_fence + 3)
    if close_fence < 0:
        return False
    rest = text[close_fence + 3:].lstrip("\n")
    if not rest.strip():  # 后面没东西 —— 那就是真没写，留着
        return False
    # 模型常顺手写一条 `---` 分隔线，摘掉占位后它就成了文件的第一行，没意义
    while rest.startswith("---"):
        rest = rest[3:].lstrip("\n")
    try:
        path.write_text(rest, encoding="utf-8")
        return True
    except OSError:
        return False
    return path


def append_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip() + "\n")


def log(home: Path, message: str) -> None:
    """所有写日志都包住异常 —— 磁盘满 / 文件被占用不能反过来杀掉宿主。"""
    try:
        with _LOG_LOCK:
            path = log_file(home)
            if path.exists() and path.stat().st_size >= LOG_MAX_BYTES:
                for number in range(LOG_BACKUPS, 0, -1):
                    source = path if number == 1 else path.with_name(path.name + f".{number-1}")
                    if source.exists():
                        source.replace(path.with_name(path.name + f".{number}"))
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            append_line(path, f"[{stamp}] {message}")
    except Exception:  # noqa: BLE001
        pass
