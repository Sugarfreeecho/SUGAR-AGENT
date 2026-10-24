"""emotes.py —— 本地表情库：收藏、搜索、发图评论的物料层。

对应三件事：
  ① **收藏**：把 B站 表情面板里的码（411 个）或任意图片 URL / 本地文件收进本地库；
  ② **搜索**：本地库按 码 / 名字 / 标签 / 包名 做 AND 匹配；面板侧按 码 / alias / 包名 搜；
  ③ **发送**：发评论时既可以直接甩文本码（`[doge]`），也可以带本地库里的图（真·图片评论）。

存储布局（都在插件数据目录里，跟着凭证走）：
    emotes/index.json        # {"version":1,"items":[...]}
    emotes/files/<sha>.<ext> # 按内容哈希存，天然去重
    emotes/panel.json        # B站 面板码表缓存（6 小时）

为什么按 sha256 存文件：同一张图从 URL 收一次、又从上传收一次，不该占两份；
而且"收藏"这件事最容易重复点。
"""
from __future__ import annotations

import threading
import base64
import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

INDEX_VERSION = 1
PANEL_TTL = 6 * 3600.0
# 两个上限要分开，别混：
#   · **存**进本地库：6MB。评论区的表情图常见 3~5MB 的 GIF（实测抓到一张 4.8MB 的），
#     按 2MB 卡会把正经想收藏的图挡在门外。
#   · **发**进评论：2MB 兜底。B站 侧没公开写死，但超了接口会拒；
#     所以发送前在 bili_client.reply 里单独卡，不在收藏时卡。
MAX_BYTES = 6 * 1024 * 1024
UPLOAD_MAX_BYTES = 2 * 1024 * 1024
ALLOW_EXT = ("png", "jpg", "jpeg", "gif", "webp")

_index_lock = threading.RLock()


def _lock():
    return _index_lock


# ── 路径 ────────────────────────────────────────────────────────────────

def emote_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "emotes"


def files_dir(data_dir: Path) -> Path:
    path = emote_dir(data_dir) / "files"
    path.mkdir(parents=True, exist_ok=True)
    return path


def index_path(data_dir: Path) -> Path:
    return emote_dir(data_dir) / "index.json"


def panel_path(data_dir: Path) -> Path:
    return emote_dir(data_dir) / "panel.json"


# ── 索引读写 ────────────────────────────────────────────────────────────

def _load_index(data_dir: Path) -> dict:
    path = index_path(data_dir)
    if not path.is_file():
        return {"version": INDEX_VERSION, "items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # 索引坏了就当空库：宁可让用户重新收一遍，也别让整个设置页 500
        return {"version": INDEX_VERSION, "items": []}
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return {"version": INDEX_VERSION, "items": []}
    return data


def _save_index(data_dir: Path, data: dict) -> None:
    path = index_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:16]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _dimensions(content: bytes) -> tuple[int, int]:
    """能拿到尺寸就拿（PIL），拿不到填 0 —— 尺寸只用于展示，不该阻塞收藏。"""
    try:
        from io import BytesIO

        from PIL import Image

        with Image.open(BytesIO(content)) as image:
            return int(image.width), int(image.height)
    except Exception:  # noqa: BLE001
        return 0, 0


def _guess_ext(content_type: str, url: str) -> str:
    ctype = (content_type or "").lower()
    if "png" in ctype:
        return "png"
    if "jpeg" in ctype or "jpg" in ctype:
        return "jpg"
    if "gif" in ctype:
        return "gif"
    if "webp" in ctype:
        return "webp"
    tail = str(url or "").split("?")[0].rsplit(".", 1)[-1].lower()
    return tail if tail in ALLOW_EXT else "png"


# ── 收藏 ────────────────────────────────────────────────────────────────

async def add_bytes(
    data_dir: Path,
    content: bytes,
    *,
    ext: str = "png",
    name: str = "",
    code: str = "",
    tags: Optional[Iterable[str]] = None,
    source: str = "upload",
    package: str = "",
) -> dict:
    """把一段图片字节收进本地库（按内容哈希去重）。"""
    if not content:
        return {"ok": False, "error": "图片是空的"}
    if len(content) > MAX_BYTES:
        return {
            "ok": False,
            "error": f"图片 {len(content) // 1024} KB，超过 {MAX_BYTES // 1024 // 1024} MB 上限",
        }
    suffix = (ext or "png").lower().lstrip(".")
    if suffix == "jpeg":
        suffix = "jpg"
    if suffix not in ALLOW_EXT:
        return {"ok": False, "error": f"不支持的格式：{suffix}"}

    digest = _sha(content)
    width, height = _dimensions(content)
    with _lock():
        index = _load_index(data_dir)
        for item in index["items"]:
            if item.get("sha") == digest:
                # 已经收过：把新信息并进去（标签是要累加的，别覆盖掉手工标过的）
                merged = False
                for tag in tags or []:
                    tag = str(tag).strip()
                    if tag and tag not in (item.get("tags") or []):
                        item.setdefault("tags", []).append(tag)
                        merged = True
                if code and not item.get("code"):
                    item["code"] = code
                    merged = True
                if merged:
                    _save_index(data_dir, index)
                return {"ok": True, "duplicate": True, "item": item}

        path = files_dir(data_dir) / f"{digest}.{suffix}"
        if not path.is_file():
            path.write_bytes(content)

        item = {
            "id": digest,
            "sha": digest,
            "file": path.name,
            "ext": suffix,
            "bytes": len(content),
            "width": width,
            "height": height,
            "code": str(code or ""),
            "name": str(name or "").strip() or str(code or "").strip() or digest,
            "package": str(package or ""),
            "tags": [str(t).strip() for t in (tags or []) if str(t).strip()],
            "source": source,
            "created_at": _now(),
            "used_count": 0,
            "last_used_at": "",
        }
        index["items"].append(item)
        _save_index(data_dir, index)
        return {"ok": True, "duplicate": False, "item": item}


async def add_from_url(
    data_dir: Path,
    url: str,
    *,
    name: str = "",
    code: str = "",
    tags: Optional[Iterable[str]] = None,
    source: str = "url",
    package: str = "",
    credential=None,
) -> dict:
    """从 http(s) 拉一张图收进库（B站 的图床要带 Referer）。"""
    import aiohttp

    target = str(url or "").strip()
    if not target.lower().startswith(("http://", "https://")):
        return {"ok": False, "error": "只支持 http(s) 链接"}
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com"}
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(target, headers=headers) as response:
                if response.status != 200:
                    return {"ok": False, "error": f"下载失败：HTTP {response.status}"}
                content = await response.read()
                ext = _guess_ext(response.headers.get("Content-Type", ""), target)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"下载失败：{type(exc).__name__}: {str(exc)[:120]}"}
    return await add_bytes(
        data_dir, content, ext=ext, name=name, code=code, tags=tags, source=source, package=package
    )


# ── 搜索 ────────────────────────────────────────────────────────────────

def _tokens(query: str) -> list[str]:
    return [t for t in str(query or "").lower().replace("#", " ").split() if t]


def _haystack(item: dict) -> str:
    bits = [
        item.get("code") or "",
        item.get("name") or "",
        item.get("package") or "",
        " ".join(item.get("tags") or []),
    ]
    return " ".join(bits).lower()


def search_local(data_dir: Path, query: str = "", limit: int = 60) -> list[dict]:
    """本地库搜索：空格分词，**每个词都要命中**（AND），命中的词越多排越前。"""
    tokens = _tokens(query)
    rows = []
    for item in _load_index(data_dir)["items"]:
        hay = _haystack(item)
        if tokens and not all(tok in hay for tok in tokens):
            continue
        score = sum(1 for tok in tokens if tok in hay) if tokens else 0
        rows.append((score, item))
    rows.sort(key=lambda pair: (-pair[0], -int(pair[1].get("used_count") or 0), pair[1].get("created_at") or ""))
    out = []
    for _score, item in rows[: max(1, min(int(limit or 60), 200))]:
        out.append({**item, "url": f"/api/sugar-bili-scroll/emotes/{item['id']}/raw"})
    return out


def get_item(data_dir: Path, ident: str) -> Optional[dict]:
    """按 id 或 code 取一条。"""
    target = str(ident or "").strip()
    if not target:
        return None
    for item in _load_index(data_dir)["items"]:
        if item.get("id") == target or (item.get("code") and item["code"] == target):
            return item
    return None


def file_of(data_dir: Path, item: dict) -> Optional[Path]:
    name = str(item.get("file") or "")
    if not name:
        return None
    path = files_dir(data_dir) / name
    return path if path.is_file() else None


# ── 增改删 ──────────────────────────────────────────────────────────────

async def update_item(
    data_dir: Path,
    ident: str,
    *,
    name: Optional[str] = None,
    tags: Optional[Iterable[str]] = None,
) -> dict:
    with _lock():
        index = _load_index(data_dir)
        for item in index["items"]:
            if item.get("id") != ident:
                continue
            if name is not None:
                item["name"] = str(name).strip() or item.get("name") or item["id"]
            if tags is not None:
                item["tags"] = [str(t).strip() for t in tags if str(t).strip()]
            _save_index(data_dir, index)
            return {"ok": True, "item": item}
    return {"ok": False, "error": "没有这一条"}


async def remove_item(data_dir: Path, ident: str) -> dict:
    with _lock():
        index = _load_index(data_dir)
        keep, dropped = [], None
        for item in index["items"]:
            if item.get("id") == ident:
                dropped = item
            else:
                keep.append(item)
        if dropped is None:
            return {"ok": False, "error": "没有这一条"}
        index["items"] = keep
        _save_index(data_dir, index)
        path = file_of(data_dir, dropped)
        if path is not None:
            try:
                path.unlink()
            except OSError:
                pass  # 文件被占用就留着，索引已经删了，不影响使用
        return {"ok": True, "id": ident}


def note_used(data_dir: Path, ident: str) -> None:
    """记一次使用 —— 搜索排序会用到（常用的排前面）。"""
    with _lock():
        index = _load_index(data_dir)
        changed = False
        for item in index["items"]:
            if item.get("id") == ident:
                item["used_count"] = int(item.get("used_count") or 0) + 1
                item["last_used_at"] = _now()
                changed = True
                break
        if changed:
            try:
                _save_index(data_dir, index)
            except OSError:
                pass


def stats(data_dir: Path) -> dict:
    items = _load_index(data_dir)["items"]
    total_bytes = sum(int(i.get("bytes") or 0) for i in items)
    # ⚠️ 键名别用 count：搜索接口自己也要返回"命中几条"的 count，
    #    两个 count 撞在一起，前端会把库容量当成搜索结果数（实测踩过）。
    return {"total": len(items), "bytes": total_bytes}


def owned_codes(data_dir: Path) -> set[str]:
    """本地库里已经有图的表情码 —— 面板列表要拿它打「已收藏」标。"""
    return {
        str(item.get("code"))
        for item in _load_index(data_dir)["items"]
        if item.get("code")
    }


# ── B站 表情面板（码表） ────────────────────────────────────────────────

async def fetch_panel(data_dir: Path, credential=None, force: bool = False) -> dict:
    """拉 B站 评论表情面板并缓存。返回 {"ok", "packages", "index", "fetched_at"}。

    ⚠️ 这个接口要登录态，未登录时 packages 是空的（code 仍然是 0，不报错）。
    """
    import aiohttp

    cache = panel_path(data_dir)
    if not force and cache.is_file():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            age = time.time() - float(data.get("fetched_ts") or 0)
            if age < PANEL_TTL and data.get("packages"):
                return {**data, "cached": True}
        except (OSError, ValueError):
            pass

    if credential is None:
        return {"ok": False, "packages": [], "index": {}, "error": "未登录，拿不到表情面板"}

    cookie = (
        f"SESSDATA={credential.sessdata}; bili_jct={credential.bili_jct}; buvid3={credential.buvid3}"
    )
    url = "https://api.bilibili.com/x/emote/user/panel/web?business=reply"
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                url,
                headers={"User-Agent": UA, "Referer": "https://www.bilibili.com", "Cookie": cookie},
            ) as response:
                payload = json.loads(await response.text())
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "packages": [], "index": {}, "error": f"拉面板失败：{type(exc).__name__}: {str(exc)[:120]}"}

    packages = ((payload.get("data") or {}).get("packages")) or []
    rows, index = [], {}
    for pkg in packages:
        emotes = []
        for emote in pkg.get("emote") or []:
            code = str(emote.get("text") or "")
            if not code:
                continue
            meta = emote.get("meta") or {}
            item = {
                "code": code,
                "url": emote.get("url") or "",
                "package": str(pkg.get("text") or ""),
                "alias": str(meta.get("alias") or ""),
                "id": emote.get("id"),
            }
            emotes.append(item)
            index[code] = item
        rows.append({"name": str(pkg.get("text") or ""), "count": len(emotes), "emotes": emotes})

    data = {
        "ok": True,
        "packages": rows,
        "index": index,
        "fetched_at": _now(),
        "fetched_ts": time.time(),
    }
    # ⚠️ 空结果不进缓存：B站 对未登录/风控的请求也会回 code=0 + 空包，
    #    缓存 6 小时就等于「面板永远是空的」，比不缓存还糟。
    if not rows:
        return {**data, "cached": False, "ok": False, "error": "面板是空的（可能没登录或被风控）"}
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return {**data, "cached": False}


def search_panel(panel: dict, query: str = "", limit: int = 60) -> list[dict]:
    """在面板码表里搜：码 / alias / 包名，空格分词、AND。"""
    tokens = _tokens(query)
    out = []
    for code, item in (panel.get("index") or {}).items():
        hay = f"{code} {item.get('alias') or ''} {item.get('package') or ''}".lower()
        if tokens and not all(tok in hay for tok in tokens):
            continue
        out.append(item)
    return out[: max(1, min(int(limit or 60), 200))]


def decode_base64_image(payload: str) -> tuple[bytes, str]:
    """接受 `data:image/png;base64,xxx` 或裸 base64，返回 (bytes, ext)。"""
    raw = str(payload or "").strip()
    ext = "png"
    if raw.startswith("data:") and "," in raw:
        header, raw = raw.split(",", 1)
        if "jpeg" in header or "jpg" in header:
            ext = "jpg"
        elif "gif" in header:
            ext = "gif"
        elif "webp" in header:
            ext = "webp"
    return base64.b64decode(raw, validate=False), ext
