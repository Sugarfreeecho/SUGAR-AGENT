"""B站 能力层 —— 从 vendor/bilibili-mcp/mcp_server.py 平移过来。

和上游的差别只有一处：**去掉了 MCP 的 @tool() 装饰器**，这些函数直接作为
宿主进程里的普通 async 函数被 host.py 调用。原先靠 `BILI_MCP_TOOLS` 环境变量做的
白名单闸门，改由 host.py 在「注册工具时」用配置判断（未开启的写工具干脆不注册）。

保留的上游关键修补（重新 vendor 时不要丢）：
  ① 凭证读取容错 + encoding="utf-8" + isinstance(data, dict)
  ② 登录成功后凭证**原子写**（先写 .tmp 再 os.replace）
  ③ `bili_comments` 把抓取异常带进返回（风控 -412 不再伪装成"这条视频 0 条评论"）
  ④ `bili_reply` 回执带上 `rpid` / `root` / `parent`（判重表与评论复核要用）
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import importlib.util
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.parse import urlsplit

import aiohttp

from bilibili_api import Credential, comment, dynamic, favorite_list, hot, rank, search, session, user, video
from bilibili_api.login_v2 import QrCodeLogin, QrCodeLoginEvents
from bilibili_api.utils.network import Api, ResponseCodeException

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# B站 表情码就长这样：`[doge]`、`[热词系列_干杯]`、`[tv_白眼]`。
# 不匹配空白（`[ 都不是表情 ]` 这种不是码），长度上限 12 防止把整段方括号文本吃掉。
EMOTE_CODE_RE = re.compile(r"\[[^\[\]\s]{1,12}\]")


class NotLoggedIn(RuntimeError):
    """没有可用凭证 —— 调用方应提示用户去设置页扫码。"""


# ── 凭证 ────────────────────────────────────────────────────────────────

def credential_path(data_dir: Path) -> Path:
    return Path(data_dir) / "bili_credential.json"


def _account_store(data_dir: Path):
    name = "myagent_plugin_sugar_bili_scroll_store"
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("store.py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module.Store(data_dir)


def _credential_payload(cred: Credential) -> dict:
    return {key: str(getattr(cred, key, "") or "")
            for key in ("sessdata", "bili_jct", "buvid3", "dedeuserid", "ac_time_value")}


def remember_credential(data_dir: Path) -> None:
    """Import the legacy active credential without printing or returning it."""
    cred = load_credential(data_dir)
    if cred is not None:
        payload = _credential_payload(cred)
        if payload["dedeuserid"].isdigit() and int(payload["dedeuserid"]) > 0 and payload["sessdata"]:
            _account_store(data_dir).save_account(cred.dedeuserid, payload)


def saved_accounts(data_dir: Path) -> list[dict]:
    remember_credential(data_dir)
    active = load_credential(data_dir)
    uid = str(getattr(active, "dedeuserid", "") or "")
    return [{**row, "active": row["uid"] == uid} for row in _account_store(data_dir).accounts()]


def load_credential(data_dir: Path) -> Optional[Credential]:
    path = credential_path(data_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # 文件写坏一次会让所有工具一起炸：退化成「没登录」，重扫一次码即可恢复。
        return None
    if not isinstance(data, dict) or not str(data.get("sessdata") or "").strip():
        return None
    return Credential(
        sessdata=str(data.get("sessdata") or ""),
        bili_jct=str(data.get("bili_jct") or ""),
        buvid3=str(data.get("buvid3") or ""),
        dedeuserid=str(data.get("dedeuserid") or ""),
        ac_time_value=str(data.get("ac_time_value") or ""),
    )


def save_credential(data_dir: Path, cred: Credential) -> Path:
    path = credential_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _credential_payload(cred)
    # ⭐ 绝不写空凭证：写进去会让 load_credential 判成"未登录"，
    #    而文件明明在 —— 用户看到的现象是"扫了码还是未登录"。
    if not str(payload.get("sessdata") or "").strip():
        raise ValueError("凭证里没有 SESSDATA，拒绝写入")
    # Archive the previous identity before replacing the active file.
    remember_credential(data_dir)
    _account_store(data_dir).save_account(cred.dedeuserid, payload)
    _account_store(data_dir).account_error(cred.dedeuserid, "")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


def get_cred(data_dir: Path) -> Credential:
    cred = load_credential(data_dir)
    if cred is None:
        raise NotLoggedIn("未登录B站：请打开「刷B站」设置页扫码登录。")
    return cred


def cookie_header(cred: Credential) -> str:
    return (
        f"SESSDATA={cred.sessdata}; bili_jct={cred.bili_jct}; buvid3={cred.buvid3}"
    )


# ── 扫码登录（给设置页用，不给模型） ────────────────────────────────────

_login_session: Optional[QrCodeLogin] = None
_login_key: str = ""
_login_png: bytes = b""
_login_generation: int = 0

# B 站扫码状态码（poll 接口 data.code）
QR_NOT_SCANNED = 86101
QR_WAIT_CONFIRM = 86090
QR_EXPIRED = 86038

QR_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"


def login_cancel() -> dict:
    """Cancel this plugin's QR attempt, including any in-flight poll."""
    global _login_session, _login_key, _login_png, _login_generation
    _login_generation += 1
    _login_session, _login_key, _login_png = None, "", b""
    return {"ok": True, "status": "cancelled", "message": "已取消扫码"}


def logout(data_dir: Path) -> dict:
    """Deactivate this plugin while retaining the saved account for later use."""
    remember_credential(data_dir)
    credential_path(data_dir).unlink(missing_ok=True)
    login_cancel()
    return {"ok": True, "status": "logged_out", "message": "已退出当前账号，登录态已保留，可从账号列表重新启用"}


def forget_account(data_dir: Path, uid: str) -> bool:
    uid = str(uid or "")
    if not uid.isdigit():
        raise ValueError("UID 必须为数字")
    remember_credential(data_dir)
    if _account_store(data_dir).account(uid) is None:
        return False
    active = load_credential(data_dir)
    if str(getattr(active, "dedeuserid", "") or "") == uid:
        logout(data_dir)
    else:
        login_cancel()
    return _account_store(data_dir).remove_account(uid)


async def select_account(data_dir: Path, uid: str) -> dict:
    """Validate one saved account, then atomically replace the single active file."""
    remember_credential(data_dir)
    payload = _account_store(data_dir).account(uid)
    if payload is None:
        return {"ok": False, "code": "account_not_found", "error": "没有保存这个账号，请先扫码添加"}
    login_cancel()
    generation = _login_generation
    cred = Credential(**payload)
    try:
        info = await user.get_self_info(credential=cred)
    except Exception as exc:
        if generation != _login_generation:
            return {"ok": False, "code": "cancelled", "error": "账号切换已取消"}
        if getattr(exc, "code", None) == -101:
            _account_store(data_dir).account_error(uid, "登录态失效，请重新扫码")
            return {"ok": False, "code": "credential_expired", "error": "该账号登录态已失效，请重新扫码"}
        return {"ok": False, "code": "check_failed", "error": "暂时无法验证该账号，请稍后重试"}
    if generation != _login_generation:
        return {"ok": False, "code": "cancelled", "error": "账号切换已取消"}
    if str(info.get("mid") or "") != str(uid):
        return {"ok": False, "code": "account_mismatch", "error": "凭证对应的账号与所选 UID 不一致，请重新扫码"}
    save_credential(data_dir, cred)
    _account_store(data_dir).account_error(uid, "")
    return {"ok": True, "uid": str(uid), "username": str(info.get("name") or ""), "message": "已启用所选账号"}


async def login_start(data_dir: Path, *, force: bool = False) -> dict:
    """生成二维码；已登录则直接返回 already_logged_in。"""
    global _login_session, _login_png, _login_key
    if not force and load_credential(data_dir) is not None and (await check_credential(data_dir)).get("logged_in"):
        return {"status": "already_logged_in", "message": "已登录B站，无需重复扫码"}
    login_cancel()
    generation = _login_generation
    qr_session = QrCodeLogin()
    await qr_session.generate_qrcode()
    if generation != _login_generation:
        return {"status": "cancelled", "message": "已取消扫码"}
    _login_session = qr_session
    # 记下 key：库内部是私有名，poll 失败时我们要能自己再问一次 B 站。
    _login_key = str(getattr(_login_session, "_QrCodeLogin__qr_key", "") or "")
    pic = _login_session.get_qrcode_picture()
    _login_png = bytes(pic.content)
    return {
        "status": "qrcode_ready",
        "message": "请用 B站 App 扫码（180 秒内有效）",
        "qrcode_image": "data:image/png;base64," + base64.b64encode(_login_png).decode("ascii"),
        "qrcode_key": _login_key,
        "next_step": "扫码后轮询 /login/poll",
    }


def _parse_credential_from_url(url: str) -> dict:
    """从 B 站回传的 crossDomain 链接里抠出凭证。

    ⭐ 坑：SESSDATA 的**值本身是 URL 编码过的**（`a%2Cb%2Cc`），Cookie 头要送
    的就是这个编码形态 —— 所以这里**不要 unquote**。
    （库构造 Credential 时会判断"值里有没有 %"，有就原样保留，没有才补编码，
      先解再让它补编码，遇到值里本来带 % 的（`100%`）反而会漏编码。）
    """
    if not url:
        return {}
    try:
        query = urlsplit(url).query
    except ValueError:
        return {}
    if not query:
        return {}
    out: dict = {}
    for part in query.split("&"):
        if not part:
            continue
        # 只按第一个 = 切，值里可能还有 =（base64 尾巴）
        name, _, value = part.partition("=")
        name = name.strip()
        if not name:
            continue
        if name.lower() == "sessdata":
            out["sessdata"] = value
        elif name.lower() == "bili_jct":
            out["bili_jct"] = value
        elif name.lower() == "dedeuserid":
            out["dedeuserid"] = value
        elif name.lower() == "buvid3":
            out["buvid3"] = value
    return out


def _parse_credential_from_cookies(raw_cookies: list) -> dict:
    """从 Set-Cookie 响应头里抠凭证（B 站另一条下发路径）。

    同样保留原始编码形态 —— 理由见 _parse_credential_from_url。
    """
    out: dict = {}
    for raw in raw_cookies or []:
        pair = str(raw).split(";", 1)[0]
        name, _, value = pair.partition("=")
        name = name.strip().lower()
        if not name:
            continue
        value = value.strip()
        if name == "sessdata":
            out["sessdata"] = value
        elif name == "bili_jct":
            out["bili_jct"] = value
        elif name == "dedeuserid":
            out["dedeuserid"] = value
        elif name == "buvid3":
            out["buvid3"] = value
    return out


def _merge_credential(parts: dict) -> dict:
    """合并多路来源；任一路拿到非空值就以它为准。"""
    merged = {"sessdata": "", "bili_jct": "", "buvid3": "", "dedeuserid": ""}
    for key, value in (parts or {}).items():
        if key in merged and str(value or "").strip():
            merged[key] = str(value)
    return merged


async def _poll_raw(key: str) -> dict:
    """直接问 B 站 poll 接口，拿到原始 data + Set-Cookie。

    为什么不用库的 check_state：库只在 `data.url` 里找凭证，而 B 站改版后
    成功态可能把凭证放在 Set-Cookie 头里 —— 实测库会把这种情况解析成**空串**，
    于是凭证文件写出来是 `{"sessdata": "", ...}`，读回来判定"未登录"。
    """
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
    async with aiohttp.ClientSession(headers=headers) as sess:
        async with sess.get(
            QR_POLL_URL,
            params={"qrcode_key": key, "source": "main-fe-header"},
        ) as resp:
            try:
                payload = await resp.json(content_type=None)
            except Exception:  # noqa: BLE001
                payload = {}
            cookies = resp.headers.getall("Set-Cookie", [])
    data = payload.get("data") if isinstance(payload, dict) else None
    return {"data": data if isinstance(data, dict) else {}, "cookies": cookies}


async def _poll_login_state(key: str) -> dict:
    """问一次 B 站，返回 {status, credential}。

    status ∈ {not_scanned, wait_confirm, expired, done, unknown}
    """
    raw = await _poll_raw(key)
    data = raw.get("data") or {}
    code = data.get("code")
    message = str(data.get("message") or "")

    if code == QR_EXPIRED:
        return {"status": "expired", "message": message or "二维码已过期"}
    if code == QR_NOT_SCANNED:
        return {"status": "not_scanned", "message": message or "未扫码"}
    if code == QR_WAIT_CONFIRM:
        return {"status": "wait_confirm", "message": message or "已扫码，等待手机确认"}

    # 到这里：要么 code==0（成功），要么是别的码 —— 两条路都试着取凭证。
    parts = {}
    parts.update(_parse_credential_from_url(str(data.get("url") or "")))
    parts.update(_parse_credential_from_cookies(raw.get("cookies") or []))
    merged = _merge_credential(parts)

    if merged["sessdata"]:
        return {
            "status": "done",
            "credential": merged,
            "ac_time_value": str(data.get("refresh_token") or ""),
            "message": message or "登录成功",
        }

    return {
        "status": "unknown",
        "message": f"扫码状态异常（code={code}）：{message or 'B站 没有下发凭证'}",
        "code": code,
    }


async def login_poll(data_dir: Path) -> dict:
    """检查扫码状态；done 时原子落盘凭证。"""
    global _login_session, _login_key
    if _login_session is None:
        if load_credential(data_dir) is not None and (await check_credential(data_dir)).get("logged_in"):
            return {"status": "already_logged_in", "message": "已登录B站"}
        return {"status": "no_session", "message": "没有进行中的登录，请先获取二维码"}

    generation = _login_generation
    try:
        state = await _poll_login_state(_login_key)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "poll_error",
            "message": f"查询扫码状态失败：{type(exc).__name__}: {exc}",
        }

    if generation != _login_generation:
        return {"status": "no_session", "message": "扫码已取消，请重新获取二维码"}
    status = state.get("status")
    if status == "not_scanned":
        return {"status": "waiting", "message": "等待扫码…"}
    if status == "wait_confirm":
        return {"status": "scanning", "message": "已扫码，等待手机确认"}
    if status == "expired":
        _login_session = None
        _login_key = ""
        return {"status": "timeout", "message": "二维码已过期，请重新获取"}
    if status == "done":
        merged = state.get("credential") or {}
        cred = Credential(
            sessdata=merged.get("sessdata") or "",
            bili_jct=merged.get("bili_jct") or "",
            buvid3=merged.get("buvid3") or None,
            dedeuserid=merged.get("dedeuserid") or None,
            ac_time_value=state.get("ac_time_value") or "",
        )
        save_credential(data_dir, cred)
        _login_session = None
        _login_key = ""
        return {
            "status": "done",
            "message": "登录成功，凭证已保存",
            "uid": merged.get("dedeuserid") or "",
        }
    return {
        "status": "unknown",
        "message": state.get("message") or "未知状态",
    }


async def check_credential(data_dir: Path) -> dict:
    cred = load_credential(data_dir)
    if cred is None:
        return {"logged_in": False, "message": "未登录"}
    try:
        # Public profile reads can succeed with an expired cookie.
        info = await user.get_self_info(credential=cred)
        return {
            "logged_in": True,
            "uid": str(info.get("mid") or cred.dedeuserid),
            "username": info.get("name", ""),
            "message": "凭证有效",
        }
    except Exception as exc:  # noqa: BLE001
        return {"logged_in": False, "message": f"凭证可能已过期: {exc}"}


# ── 只读工具 ────────────────────────────────────────────────────────────

async def search_videos(keyword: str, num: int = 10, order: str = "totalrank", page: int = 1) -> dict:
    order_map = {
        "totalrank": search.OrderVideo.TOTALRANK,
        "click": search.OrderVideo.CLICK,
        "pubdate": search.OrderVideo.PUBDATE,
        "dm": search.OrderVideo.DM,
    }
    page = max(1, min(_as_int(page, 1), 50))
    result = await search.search_by_type(
        keyword=keyword,
        search_type=search.SearchObjectType.VIDEO,
        page=page,
        order_type=order_map.get(order, search.OrderVideo.TOTALRANK),
    )
    videos = []
    for item in (result.get("result") or [])[: max(1, min(int(num or 10), 50))]:
        videos.append(
            {
                "bvid": item.get("bvid", ""),
                "aid": item.get("aid", 0),
                "title": str(item.get("title", ""))
                .replace('<em class="keyword">', "")
                .replace("</em>", ""),
                "author": item.get("author", ""),
                "play": item.get("play", 0),
                "review": item.get("review", 0),
                "danmaku": item.get("video_review", 0),
                "duration": item.get("duration", ""),
                "pubdate": item.get("pubdate", 0),
                "description": str(item.get("description", ""))[:200],
            }
        )
    return {"keyword": keyword, "page": page, "count": len(videos), "videos": videos}


async def video_info(data_dir: Path, bvid: str, detail: bool = False) -> dict:
    """视频详情。

    ⚠️ 标签以前读 `info["tag"]`，但 17.4.2 的 get_info() 不返回这个键 —— 所以 tags 一直是空数组。
    真正的标签要走 `get_tags()`，这里顺手修掉。
    """
    cred = get_cred(data_dir)
    handle = video.Video(bvid=bvid, credential=cred)
    info = await handle.get_info()
    stat = info.get("stat", {})
    pages = [row for row in (info.get("pages") or []) if isinstance(row, dict)]
    tags: list[str] = []
    try:
        for row in await handle.get_tags() or []:
            name = row.get("tag_name") if isinstance(row, dict) else ""
            if name:
                tags.append(str(name))
    except Exception:  # noqa: BLE001
        tags = [str(t.get("tag_name")) for t in (info.get("tag") or [])
                if isinstance(t, dict) and t.get("tag_name")]
    cid = _as_int(info.get("cid")) or (_as_int(pages[0].get("cid")) if pages else 0)
    out: dict[str, Any] = {
        "bvid": info.get("bvid"),
        "aid": info.get("aid"),
        "cid": cid,
        "title": info.get("title"),
        "description": str(info.get("desc") or "")[:800],
        "author": (info.get("owner") or {}).get("name"),
        "author_uid": _as_int((info.get("owner") or {}).get("mid")),
        "duration": info.get("duration"),
        "pubdate": info.get("pubdate"),
        "tname": str(info.get("tname") or ""),
        # 有些视频 tname 是空串（B站自己没填），留个 tid 让上层至少能归类。
        "tid": _as_int(info.get("tid")),
        "dimension": info.get("dimension") or {},
        "cover": _https(info.get("pic") or ""),
        "page_count": len(pages),
        "pages": [
            {"page": _as_int(row.get("page")), "cid": _as_int(row.get("cid")),
             "title": str(row.get("part") or ""), "duration": _as_int(row.get("duration"))}
            for row in pages[:50]
        ],
        "tags": tags,
        "stat": {
            "view": stat.get("view", 0),
            "danmaku": stat.get("danmaku", 0),
            "reply": stat.get("reply", 0),
            "favorite": stat.get("favorite", 0),
            "coin": stat.get("coin", 0),
            "like": stat.get("like", 0),
            "share": stat.get("share", 0),
        },
    }
    if detail:
        try:
            online = await handle.get_online()
            out["online"] = {"count": _as_int(online.get("count")), "total": _as_int(online.get("total"))}
        except Exception as exc:  # noqa: BLE001
            out["online_error"] = _risk_error(exc)
        try:
            conclusion = await handle.get_ai_conclusion(cid=cid) if cid else {}
            model = (conclusion or {}).get("model_result") or {}
            out["ai_summary"] = {
                "summary": str(model.get("summary") or "")[:600],
                "outline": [
                    {"title": str(row.get("title") or ""), "timestamp": _as_int(row.get("timestamp"))}
                    for row in (model.get("outline") or []) if isinstance(row, dict)
                ][:8],
            }
        except Exception as exc:  # noqa: BLE001
            out["ai_summary_error"] = _risk_error(exc)
    return out


# ── 封面与画面截图 ──────────────────────────────────────────────────────

SHOT_KEEP_HOURS = 24


def _https(url: str) -> str:
    text = str(url or "").strip()
    if text.startswith("//"):
        return "https:" + text
    if text.startswith("http://"):
        return "https://" + text[len("http://"):]
    return text


def shots_dir(data_dir: Path, bvid: str) -> Path:
    folder = Path(data_dir) / "shots" / str(bvid)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _fresh(path: Path, hours: int = SHOT_KEEP_HOURS) -> bool:
    try:
        return path.is_file() and (time.time() - path.stat().st_mtime) < hours * 3600
    except OSError:
        return False


async def _fetch_bytes(url: str, *, limit: int = 12 * 1024 * 1024) -> bytes:
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
    async with aiohttp.ClientSession(headers=headers) as sess:
        async with sess.get(url, timeout=aiohttp.ClientTimeout(total=40)) as resp:
            if resp.status != 200:
                raise RuntimeError(f"下载失败：HTTP {resp.status}")
            body = await resp.read()
    if len(body) > limit:
        raise RuntimeError(f"文件太大（{len(body) // 1024} KB），不下载")
    return body


def _image_meta(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.width, image.height
    except Exception:  # noqa: BLE001
        return 0, 0


def ffmpeg_path() -> str:
    """和 asr.py 同一套查找顺序：环境变量 → 宿主自带 → PATH。"""
    root = Path(__file__).resolve().parents[2]
    for candidate in (
        os.environ.get("BILI_FFMPEG") or "",
        str(root / "tools" / "ffmpeg-8.1-essentials_build" / "bin" / "ffmpeg.exe"),
        str(root / "tools" / "ffmpeg-8.1-essentials_build" / "bin" / "ffmpeg"),
    ):
        if candidate and Path(candidate).is_file():
            return candidate
    return shutil.which("ffmpeg") or ""


def _parse_times(at: Any) -> Optional[list[int]]:
    """'highlights' 返回 None（表示去取弹幕峰值）；否则解析 '120,3:30' 这种写法。"""
    text = str(at or "").strip().lower()
    if not text or text in {"highlights", "auto", "峰值"}:
        return None
    times: list[int] = []
    for part in re.split(r"[,，\s]+", text):
        if not part:
            continue
        if ":" in part:
            minutes, _, seconds = part.partition(":")
            times.append(max(0, _as_int(minutes) * 60 + int(float(seconds or 0))))
        else:
            times.append(max(0, int(float(part))))
    return times


async def cover(data_dir: Path, bvid: str, size: str = "original") -> dict:
    """视频封面。同一条视频 24 小时内复用本地文件，不重复下载。"""
    size = "small" if str(size or "").lower() == "small" else "original"
    folder = shots_dir(data_dir, bvid)
    target = folder / ("cover_small.jpg" if size == "small" else "cover.jpg")
    if _fresh(target):
        width, height = _image_meta(target)
        return {"ok": True, "bvid": bvid, "cached": True, "size": size,
                "file": {"path": str(target), "width": width, "height": height,
                         "bytes": target.stat().st_size}}
    cred = get_cred(data_dir)
    info = await video.Video(bvid=bvid, credential=cred).get_info()
    source = _https(info.get("pic") or "")
    if not source:
        return {"ok": False, "bvid": bvid, "error": "这条视频没有封面"}
    try:
        body = await _fetch_bytes(source, limit=24 * 1024 * 1024)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "bvid": bvid, "error": _risk_error(exc), "source_url": source}
    target.write_bytes(body)
    if size == "small":
        try:
            from PIL import Image

            with Image.open(target) as image:
                rgb = image.convert("RGB")
                if rgb.width > 672:
                    rgb = rgb.resize((672, max(1, round(rgb.height * 672 / rgb.width))), Image.LANCZOS)
                rgb.save(target, "JPEG", quality=85)
        except Exception:  # noqa: BLE001
            # 没有 Pillow 就保留原图，别把封面弄丢。
            size = "original"
    width, height = _image_meta(target)
    return {"ok": True, "bvid": bvid, "title": info.get("title"), "size": size,
            "file": {"path": str(target), "width": width, "height": height,
                     "bytes": target.stat().st_size},
            "source_url": source}


async def _storyboard_frames(data_dir: Path, bvid: str, times: list[int]) -> list[dict]:
    """官方 storyboard：一次请求拿全片预览图，按时间点裁格子。不下载视频。"""
    try:
        from PIL import Image
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("缺少 Pillow，无法裁剪预览图") from exc

    cred = get_cred(data_dir)
    handle = video.Video(bvid=bvid, credential=cred)
    info = await handle.get_info()
    pages = [row for row in (info.get("pages") or []) if isinstance(row, dict)]
    cid = _as_int(info.get("cid")) or (_as_int(pages[0].get("cid")) if pages else 0)
    if not cid:
        raise RuntimeError("拿不到 cid")
    snap = await handle.get_video_snapshot(cid=cid, json_index=True, pvideo=False)
    images = [_https(url) for url in (snap.get("image") or [])]
    index = [_as_int(value) for value in (snap.get("index") or [])]
    if not images or not index:
        raise RuntimeError("这条视频没有预览图")
    grid_x = _as_int(snap.get("img_x_len")) or 10
    grid_y = _as_int(snap.get("img_y_len")) or 10
    cell_w = _as_int(snap.get("img_x_size")) or 480
    cell_h = _as_int(snap.get("img_y_size")) or 270
    per_sheet = max(1, grid_x * grid_y)
    folder = shots_dir(data_dir, bvid)

    out: list[dict] = []
    for wanted in times:
        position = min(range(len(index)), key=lambda i: abs(index[i] - wanted))
        sheet_no, cell = divmod(position, per_sheet)
        if sheet_no >= len(images):
            sheet_no, cell = len(images) - 1, per_sheet - 1
        sheet_path = folder / f"sprite-{sheet_no}.jpg"
        if not _fresh(sheet_path, hours=24 * 7):
            sheet_path.write_bytes(await _fetch_bytes(images[sheet_no], limit=32 * 1024 * 1024))
        x = (cell % grid_x) * cell_w
        y = (cell // grid_x) * cell_h
        target = folder / f"s{index[position]:05d}.jpg"
        with Image.open(sheet_path) as sheet:
            sheet.crop((x, y, x + cell_w, y + cell_h)).convert("RGB").save(target, "JPEG", quality=88)
        out.append({"at": index[position], "clock": _clock(index[position]), "path": str(target),
                    "width": cell_w, "height": cell_h, "bytes": target.stat().st_size})
    return out


def _grab_frame(binary: str, url: str, at: int, target: Path, width: int):
    command = [
        binary, "-y", "-loglevel", "error",
        "-headers", f"Referer: https://www.bilibili.com/\r\nUser-Agent: {UA}\r\n",
        "-ss", str(int(at)), "-i", url,
        "-frames:v", "1", "-vf", f"scale={int(width)}:-2", "-q:v", "3", str(target),
    ]
    return subprocess.run(command, capture_output=True, text=True, timeout=120)


async def _stream_frames(data_dir: Path, bvid: str, times: list[int], width: int) -> list[dict]:
    """DASH 视频流 + ffmpeg 抽原画帧。吃带宽，但清晰度是原画。"""
    binary = ffmpeg_path()
    if not binary:
        raise RuntimeError("找不到 ffmpeg（tools/ffmpeg-8.1-essentials_build 或 PATH）")
    cred = get_cred(data_dir)
    handle = video.Video(bvid=bvid, credential=cred)
    info = await handle.get_info()
    pages = [row for row in (info.get("pages") or []) if isinstance(row, dict)]
    cid = _as_int(info.get("cid")) or (_as_int(pages[0].get("cid")) if pages else 0)
    if not cid:
        raise RuntimeError("拿不到 cid")
    play = await handle.get_download_url(cid=cid, html5=True)
    dash = (play or {}).get("dash") or {}
    streams = [row for row in (dash.get("video") or []) if isinstance(row, dict)]
    url = ""
    if streams:
        best = max(streams, key=lambda row: _as_int(row.get("height")))
        url = str(best.get("baseUrl") or best.get("base_url") or "")
    if not url:
        durl = (play or {}).get("durl") or []
        if durl:
            url = str((durl[0] or {}).get("url") or "")
    if not url:
        raise RuntimeError("拿不到播放地址（可能需要大会员、付费或受地区限制）")

    folder = shots_dir(data_dir, bvid)
    out: list[dict] = []
    for at in times:
        target = folder / f"f{int(at):05d}.jpg"
        if not _fresh(target):
            result = await asyncio.to_thread(_grab_frame, binary, url, int(at), target, width)
            if result.returncode != 0 or not target.exists():
                raise RuntimeError(f"{int(at)}s 抽帧失败：{(result.stderr or '').strip()[:160]}")
        image_w, image_h = _image_meta(target)
        out.append({"at": int(at), "clock": _clock(at), "path": str(target),
                    "width": image_w, "height": image_h, "bytes": target.stat().st_size})
    return out


async def frame(
    data_dir: Path,
    bvid: str,
    at: Any = "",
    source: str = "storyboard",
    width: int = 1280,
    top: int = 3,
) -> dict:
    """按时间点截图。at 留空或 'highlights' 时自动用弹幕峰值。

    默认走官方 storyboard（快、不下载视频，480×270）；要原画就传 source='stream'。
    storyboard 拿不到时自动降级成 stream，并在结果里标 degraded。
    """
    source = "stream" if str(source or "").lower() == "stream" else "storyboard"
    width = max(320, min(_as_int(width, 1280), 1920))
    top = max(1, min(_as_int(top, 3), 5))
    times = _parse_times(at)
    notes: list[str] = []
    if times is None:
        peaks = await highlights(data_dir, bvid, 30, top)
        times = [_as_int(row.get("at")) for row in (peaks.get("highlights") or [])]
        if not times:
            return {"ok": False, "bvid": bvid,
                    "error": "没有弹幕峰值可截；请直接给 at（秒数），例如 at='120,510'"}
    times = sorted({max(0, int(value)) for value in times})[:5]

    degraded = False
    if source == "storyboard":
        try:
            files = await _storyboard_frames(data_dir, bvid, times)
        except Exception as exc:  # noqa: BLE001
            degraded = True
            notes.append("官方预览图不可用，已改用视频流抽帧：" + _risk_error(exc))
            try:
                files = await _stream_frames(data_dir, bvid, times, width)
            except Exception as inner:  # noqa: BLE001
                return {"ok": False, "bvid": bvid, "error": _risk_error(inner), "notes": notes}
    else:
        try:
            files = await _stream_frames(data_dir, bvid, times, width)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "bvid": bvid, "error": _risk_error(exc)}

    return {
        "ok": True,
        "bvid": bvid,
        "source": "stream" if (source == "stream" or degraded) else "storyboard",
        "degraded": degraded,
        "requested": times,
        "files": files,
        "notes": notes,
    }


async def subtitles(data_dir: Path, bvid: str) -> dict:
    """取字幕原文。空字幕是一种结果（视频没语音），不是错误。"""
    cred = get_cred(data_dir)
    v = video.Video(bvid=bvid, credential=cred)
    info = await v.get_info()
    cid = info.get("cid", 0)
    if not cid and info.get("pages"):
        cid = (info["pages"][0] or {}).get("cid", 0)
    if not cid:
        return {"bvid": bvid, "error": "无法获取 cid"}

    subtitle_list = await v.get_subtitle(cid=cid)
    subs = subtitle_list.get("subtitles") or []
    if not subs:
        return {"bvid": bvid, "title": info.get("title", ""), "segments": 0,
                "text": "", "note": "该视频没有字幕"}

    target = None
    for s in subs:
        if s.get("lan") in {"ai-zh", "zh-CN", "zh"}:
            target = s
            break
    target = target or subs[0]

    url = str(target.get("subtitle_url") or "")
    if url.startswith("//"):
        url = "https:" + url
    if not url:
        return {"bvid": bvid, "title": info.get("title", ""), "segments": 0,
                "text": "", "note": "字幕地址为空"}

    async with aiohttp.ClientSession(headers={"User-Agent": UA}) as sess:
        async with sess.get(url) as resp:
            data = await resp.json(content_type=None)

    texts = [str(item.get("content") or "") for item in (data.get("body") or [])]
    return {
        "bvid": bvid,
        "title": info.get("title", ""),
        "language": target.get("lan_doc", ""),
        "segments": len(texts),
        "text": "\n".join(texts),
    }


def _comment_row(row: Mapping[str, Any]) -> dict:
    """把一条评论压成统一长相；表情码和评论图只在存在时才出现。"""
    member = row.get("member") or {}
    content = row.get("content") or {}
    item = {
        "rpid": row.get("rpid", 0),
        "user": member.get("uname", ""),
        "content": str(content.get("message") or ""),
        "like": row.get("like", 0),
        "reply_count": row.get("rcount", 0),
        "time": row.get("ctime", 0),
    }
    codes = EMOTE_CODE_RE.findall(item["content"])
    if codes:
        item["emotes"] = list(dict.fromkeys(codes))[:4]
    pictures = content.get("pictures") or []
    if pictures:
        item["pictures"] = [
            {"url": str(pic.get("img_src") or ""),
             "width": _as_int(pic.get("img_width")),
             "height": _as_int(pic.get("img_height"))}
            for pic in pictures[:3] if pic.get("img_src")
        ]
    subs = [
        {"user": (sub.get("member") or {}).get("uname", ""),
         "content": str((sub.get("content") or {}).get("message") or ""),
         "like": sub.get("like", 0)}
        for sub in (row.get("replies") or [])[:2]
    ]
    if subs:
        item["top_replies"] = subs
    return item


async def _sub_replies(cred: Credential, aid: int, root: int, limit: int = 30) -> tuple[list[dict], str]:
    """取某条评论下面的楼中楼。

    ⚠️ 别用裸 aiohttp 打这个接口：缺 buvid 的请求会回 412 HTML（以前复核工具就栽在这），
    走库里的 `Api` 会话是正常的。
    """
    rows: list[dict] = []
    error = ""
    page = 1
    while len(rows) < limit:
        try:
            api = Api(url="https://api.bilibili.com/x/v2/reply/reply", method="GET",
                      verify=True, credential=cred)
            data = await api.update_params(type=1, oid=aid, root=root, ps=20, pn=page).result
        except ResponseCodeException as exc:
            error = str(exc)[:160]
            break
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {str(exc)[:160]}"
            break
        batch = data.get("replies") or []
        if not batch:
            break
        for row in batch:
            item = _comment_row(row)
            item["root"] = root
            item["parent"] = row.get("parent", 0)
            rows.append(item)
        if len(batch) < 20:  # 不满一页就是最后一页，别再打一次空请求
            break
        page += 1
        await asyncio.sleep(0.4)
    return rows[:limit], error


async def comments(data_dir: Path, bvid: str, num: int = 30, sort: str = "hot",
                   root: int = 0, page: int = 1) -> dict:
    """抓评论。

    sort=hot 按热度（默认）、time 按时间；root>0 时改抓那条评论下面的楼中楼。
    ⭐ 除了正文，还带两样「表情相关的证据」：`emotes`（正文里的表情码）和
    `pictures`（评论图地址 + 宽高），两样都只在存在时才出现。
    """
    cred = get_cred(data_dir)
    info = await video.Video(bvid=bvid, credential=cred).get_info()
    aid = info["aid"]
    limit = max(1, min(_as_int(num, 30), 100))
    target_root = _as_int(root)
    if target_root > 0:
        rows, error = await _sub_replies(cred, aid, target_root, limit)
        out = {"bvid": bvid, "root": target_root, "sort": "time",
               "count": len(rows), "comments": rows}
        if error:
            out["error"] = error
        return out

    order = comment.OrderType.TIME if str(sort or "").lower() in {"time", "new", "最新"} else comment.OrderType.LIKE
    collected: list[dict] = []
    fetch_error = ""
    current = max(1, _as_int(page, 1))
    while len(collected) < limit:
        try:
            resp = await comment.get_comments(
                oid=aid,
                type_=comment.CommentResourceType.VIDEO,
                page_index=current,
                order=order,
                credential=cred,
            )
            replies = resp.get("replies") or []
            if not replies:
                break
            collected.extend(_comment_row(row) for row in replies)
            current += 1
            await asyncio.sleep(0.5)
        except Exception as exc:  # noqa: BLE001
            # 抓取失败不能吞成「这条视频 0 条评论」，否则日报静默失真。
            fetch_error = f"{type(exc).__name__}: {exc}"
            break

    out = {"bvid": bvid, "sort": "time" if order is comment.OrderType.TIME else "hot",
           "page": page, "count": len(collected[:limit]), "comments": collected[:limit]}
    if fetch_error:
        out["error"] = fetch_error
    return out


async def danmaku(data_dir: Path, bvid: str, num: int = 100) -> dict:
    cred = get_cred(data_dir)
    items = await video.Video(bvid=bvid, credential=cred).get_danmakus(page_index=0)
    limit = max(1, min(int(num or 100), 500))
    rows = [{"text": d.text, "time": d.dm_time} for d in items[:limit]]
    return {"bvid": bvid, "count": len(rows), "danmakus": rows}


def account_credential(data_dir: Path, uid: Any) -> Optional[Credential]:
    """取某个**已保存账号**的凭证，但**不切换**当前生效账号。

    用途：小号负责跑任务，挑中的视频收藏进大号的收藏夹。
    写操作必须用大号凭证，可全局 active 账号又不能来回切 ——
    一切换，值班、入站、工具全都跟着换人，风险太大。
    """
    key = str(uid or "").strip()
    if not key.isdigit():
        return None
    remember_credential(data_dir)
    payload = _account_store(data_dir).account(key)
    if not payload:
        return None
    try:
        return Credential(**payload)
    except Exception:  # noqa: BLE001
        return None


def activate_local(data_dir: Path, uid: Any) -> dict:
    """把已保存账号切成当前生效账号，**不联网验证**（值班开跑前用，省一次请求）。

    要严格校验就用 `select_account()`（它会调 `get_self_info` 验活）。
    """
    cred = account_credential(data_dir, uid)
    if cred is None:
        return {"ok": False, "error": f"没有保存账号 {uid}，请先扫码添加"}
    save_credential(data_dir, cred)
    return {"ok": True, "uid": str(uid)}


async def favorite_folders_as(data_dir: Path, uid: Any) -> dict:
    """列某个已保存账号的收藏夹（给设置页选目标夹用）。"""
    cred = account_credential(data_dir, uid)
    if cred is None:
        return {"ok": False, "error": f"没有保存账号 {uid}，请先扫码添加"}
    target = int(str(uid) if str(uid).isdigit() else 0)
    try:
        data = await favorite_list.get_video_favorite_list(uid=target, credential=cred)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    rows = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "media_count": item.get("media_count", 0),
        }
        for item in (data.get("list") or [])
    ]
    return {"ok": True, "uid": target, "count": len(rows), "folders": rows}


async def favorite_add_as(data_dir: Path, uid: Any, bvid: str, fid: int) -> dict:
    """用指定账号把视频收进它的收藏夹（跨账号收藏的写操作）。"""
    cred = account_credential(data_dir, uid)
    if cred is None:
        return {"ok": False, "error": f"没有保存账号 {uid}，请先扫码添加", "bvid": bvid}
    folder = int(fid or 0)
    if folder <= 0:
        return {"ok": False, "error": "没有指定收藏夹 id", "bvid": bvid}
    info = await video.Video(bvid=bvid, credential=cred).get_info()
    aid = int(info.get("aid") or 0)
    if not aid:
        return {"ok": False, "error": "拿不到 aid", "bvid": bvid}
    api = Api(
        url="https://api.bilibili.com/x/v3/fav/resource/deal",
        method="POST",
        verify=True,
        credential=cred,
    )
    api.data = {"rid": aid, "type": 2, "add_media_ids": str(folder), "del_media_ids": ""}
    try:
        await api.request()
    except ResponseCodeException as exc:
        message = str(exc)
        if "已经" in message or "already" in message.lower():
            return {"ok": True, "already": True, "bvid": bvid, "fid": folder, "uid": str(uid)}
        return {"ok": False, "error": message[:200], "bvid": bvid, "fid": folder, "uid": str(uid)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}", "bvid": bvid, "fid": folder}
    return {"ok": True, "bvid": bvid, "fid": folder, "aid": aid, "uid": str(uid)}


async def favorite_folders(data_dir: Path, uid: int = 0) -> dict:
    cred = get_cred(data_dir)
    target = int(uid or 0) or int(cred.dedeuserid or 0)
    if not target:
        return {"error": "缺少 uid"}
    data = await favorite_list.get_video_favorite_list(uid=target, credential=cred)
    rows = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "media_count": item.get("media_count", 0),
            "fav_state": item.get("fav_state", 0),
        }
        for item in (data.get("list") or [])
    ]
    return {"uid": target, "count": len(rows), "folders": rows}


async def favorite_add(data_dir: Path, bvid: str, fid: int) -> dict:
    """把一条视频收进指定收藏夹。

    ⚠️ 为什么不用库的封装：`bilibili_api 17.4.2` **没有**这个能力
    （上游 favops.py 用的 `FavoriteListResource(...).add()` 是更新版本才有的类，
    17.4.2 里连这个类都不存在）。所以这里直接打 `/x/v3/fav/resource/deal`，
    由 `Api(verify=True)` 自动补 csrf（= bili_jct）。
    实测该接口对未登录请求回 `-101 账号未登录`，说明地址与参数形态是对的。
    """
    cred = get_cred(data_dir)
    folder = int(fid or 0)
    if folder <= 0:
        return {"ok": False, "error": "没有指定收藏夹 id"}
    info = await video.Video(bvid=bvid, credential=cred).get_info()
    aid = int(info.get("aid") or 0)
    if not aid:
        return {"ok": False, "error": "拿不到 aid"}
    api = Api(
        url="https://api.bilibili.com/x/v3/fav/resource/deal",
        method="POST",
        verify=True,
        credential=cred,
    )
    api.data = {
        "rid": aid,
        "type": 2,  # 2 = 视频
        "add_media_ids": str(folder),
        "del_media_ids": "",
    }
    try:
        await api.request()
    except ResponseCodeException as exc:
        message = str(exc)
        # 已经收藏过不算失败（否则每天重跑都会报一堆假错误）
        if "已经" in message or "already" in message.lower():
            return {"ok": True, "already": True, "bvid": bvid, "fid": folder}
        return {"ok": False, "error": message[:200], "bvid": bvid, "fid": folder}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}", "bvid": bvid, "fid": folder}
    return {"ok": True, "bvid": bvid, "fid": folder, "aid": aid}


async def favorite_remove(data_dir: Path, bvid: str, fid: int) -> dict:
    """把一条视频从指定收藏夹移出（del_media_ids）。

    实测（2026-11-04，aid=117224505416241）：add_media_ids 留空、del_media_ids 填收藏夹 id，
    视频确实被移出，但响应里的 `success_num` 恒为 0 —— 那个字段不能当结果，只能看有无异常。
    「移动到另一个收藏夹」同一次请求里 add 新夹 + del 旧夹也成立。
    """
    cred = get_cred(data_dir)
    folder = int(fid or 0)
    if folder <= 0:
        return {"ok": False, "error": "没有指定收藏夹 id"}
    info = await video.Video(bvid=bvid, credential=cred).get_info()
    aid = int(info.get("aid") or 0)
    if not aid:
        return {"ok": False, "error": "拿不到 aid"}
    api = Api(
        url="https://api.bilibili.com/x/v3/fav/resource/deal",
        method="POST",
        verify=True,
        credential=cred,
    )
    api.data = {
        "rid": aid,
        "type": 2,  # 2 = 视频
        "add_media_ids": "",
        "del_media_ids": str(folder),
    }
    try:
        await api.request()
    except ResponseCodeException as exc:
        return {"ok": False, "error": str(exc)[:200], "bvid": bvid, "fid": folder}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}", "bvid": bvid, "fid": folder}
    return {"ok": True, "bvid": bvid, "fid": folder, "aid": aid}


# ── 视频标识解析 ────────────────────────────────────────────────────────

# 用户手里的东西从来不是干净的 BV 号：`av170001`、带 `?p=2` 的完整地址、b23.tv 短链
# 都会遇到。以前 BVID 正则直接判"无效"，等于把「贴链接」这条路堵死，先统一在这里收口。
BV_RE = re.compile(r"BV[0-9A-Za-z]{10}")
AV_RE = re.compile(r"av(\d{1,12})", re.IGNORECASE)
SHORT_LINK_RE = re.compile(r"https?://[^\s]*?(?:b23\.tv|bili2233\.cn)/[0-9A-Za-z]+", re.IGNORECASE)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _risk_error(exc: Exception) -> str:
    """把 412 那种整页 HTML 压成一句人话。"""
    text = str(exc)
    if "412" in text:
        return "B站风控（412）：这次请求被拒，隔几分钟再试；别连续重试"
    if "-352" in text or "风控校验" in text:
        return "B站风控校验（-352）：需要先在网页端完成一次验证"
    return f"{type(exc).__name__}: {text[:160]}"


COMMENT_ERRORS = {
    61001: "账号需要先绑定手机号才能发评论（B站限制，插件改不了）",
    -101: "登录已失效，需要重新扫码登录",
    -111: "csrf 校验失败，重新登录一次",
    -412: "B站风控（412），隔几分钟再试",
    12015: "评论发得太频繁，稍后再试",
    12051: "评论内容被判重复，换个说法",
}


def _response_error(exc: Exception) -> tuple[str, bool]:
    """把 B站 的 ResponseCodeException 换成能照着处理的文案：(文案, 是否确定失败)。"""
    if isinstance(exc, ResponseCodeException):
        code = exc.args[0] if exc.args else 0
        if code in COMMENT_ERRORS:
            return COMMENT_ERRORS[code], True
        message = exc.args[1] if len(exc.args) > 1 else str(exc)
        return f"{message}（code {code}）"[:200], True
    return f"{type(exc).__name__}: {str(exc)[:160]}", False


async def _follow_short_link(url: str) -> str:
    async with aiohttp.ClientSession(headers={"User-Agent": UA}) as sess:
        async with sess.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            hit = BV_RE.search(str(resp.url))
            if hit:
                return hit.group(0)
            hit = BV_RE.search(await resp.text())
            return hit.group(0) if hit else ""


async def resolve_bvid(raw: str, data_dir: Optional[Path] = None) -> dict:
    """把 BV 号 / av 号 / 视频链接 / b23.tv 短链 统一解析成 BV 号。

    解析不出来就明确说原因，别让下游用「BV 号无效」糊弄过去。
    """
    text = str(raw or "").strip()
    if not text:
        return {"ok": False, "error": "缺少视频标识"}

    page = 0
    page_hit = re.search(r"[?&#]p=(\d{1,4})", text)
    if page_hit:
        page = max(1, int(page_hit.group(1)))

    hit = BV_RE.search(text)
    if hit:
        return {"ok": True, "bvid": hit.group(0), "page": page, "how": "bvid"}

    short = SHORT_LINK_RE.search(text)
    if short:
        try:
            bvid = await _follow_short_link(short.group(0))
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"短链打不开：{type(exc).__name__}: {str(exc)[:120]}"}
        if bvid:
            return {"ok": True, "bvid": bvid, "page": page, "how": "short_link"}
        return {"ok": False, "error": "短链里没有 BV 号（可能不是视频，或者链接已失效）"}

    av = AV_RE.search(text)
    if av:
        aid = _as_int(av.group(1))
        try:
            # 匿名请求这个接口很容易吃 412，有登录态就带上。
            cred = load_credential(data_dir) if data_dir is not None else None
            info = await video.Video(aid=aid, credential=cred).get_info()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"av{aid} 查不到：{type(exc).__name__}: {str(exc)[:120]}"}
        bvid = str(info.get("bvid") or "")
        if not bvid:
            return {"ok": False, "error": f"av{aid} 没有对应的 BV 号"}
        return {"ok": True, "bvid": bvid, "page": page, "how": "aid"}

    return {"ok": False, "error": "认不出这个视频标识：BV 号、av 号、完整链接、b23.tv 短链都可以"}


# ── 发现与个人列表（只读） ──────────────────────────────────────────────

def _archive_row(item: Mapping[str, Any]) -> dict:
    """把搜索 / 热门 / 排行 / 收藏 / 投稿的条目压成同一副长相。

    B站 各接口字段名不统一（owner vs upper、stat vs cnt_info、pubdate vs pubtime），
    这里统一收口，模型不用记五套字段。
    """
    owner = item.get("owner") if isinstance(item.get("owner"), dict) else {}
    upper = item.get("upper") if isinstance(item.get("upper"), dict) else {}
    stat = item.get("stat") if isinstance(item.get("stat"), dict) else {}
    cnt = item.get("cnt_info") if isinstance(item.get("cnt_info"), dict) else {}
    aid = _as_int(item.get("aid") or item.get("id"))
    bvid = str(item.get("bvid") or "")
    reason = item.get("rcmd_reason")
    if isinstance(reason, dict):
        reason = reason.get("content")
    row = {
        "bvid": bvid,
        "aid": aid,
        "url": f"https://www.bilibili.com/video/{bvid}" if bvid else (f"https://www.bilibili.com/video/av{aid}" if aid else ""),
        "title": str(item.get("title") or "")
        .replace('<em class="keyword">', "")
        .replace("</em>", ""),
        "author": owner.get("name") or upper.get("name") or str(item.get("author") or ""),
        "author_uid": _as_int(owner.get("mid") or upper.get("mid")),
        "duration": _as_int(item.get("duration")),
        "pubdate": _as_int(item.get("pubdate") or item.get("pubtime") or item.get("created")),
        "view": _as_int(stat.get("view") or cnt.get("play") or item.get("play")),
        "like": _as_int(stat.get("like") or item.get("like")),
        "danmaku": _as_int(stat.get("danmaku") or item.get("video_review")),
    }
    if reason:
        row["reason"] = str(reason)[:80]
    if item.get("score") not in (None, ""):
        row["score"] = item.get("score")
    return row


def _history_row(item: Mapping[str, Any]) -> dict:
    """观看历史：新版接口不直接给 bvid，只能从 uri 里抠。"""
    hist = item.get("history") if isinstance(item.get("history"), dict) else {}
    uri = str(item.get("uri") or "")
    hit = BV_RE.search(uri)
    aid = _as_int(hist.get("oid"))
    return {
        "bvid": hit.group(0) if hit else "",
        "aid": aid,
        "url": uri or (f"https://www.bilibili.com/video/av{aid}" if aid else ""),
        "title": str(item.get("title") or item.get("long_title") or ""),
        "author": str(item.get("author_name") or ""),
        "author_uid": _as_int(item.get("author_mid")),
        "duration": _as_int(item.get("duration")),
        "progress": _as_int(item.get("progress") or item.get("current")),
        "finished": bool(item.get("is_finish")),
        "view_at": _as_int(item.get("view_at")),
        "business": str(hist.get("business") or item.get("kid") or ""),
    }


def _rank_type(name: str):
    key = str(name or "all").strip()
    members = {member.lower(): member for member in dir(rank.RankType) if not member.startswith("_")}
    target = members.get(key.lower())
    if target is None:
        return rank.RankType.All
    return getattr(rank.RankType, target)


async def discover(
    data_dir: Path,
    source: str = "hot",
    limit: int = 10,
    tid: str = "all",
    mid: int = 0,
    bvid: str = "",
    page: int = 1,
) -> dict:
    """统一的发现入口：热门 / 每周必看 / 排行榜 / UP 投稿 / 关注动态 / 相关推荐。

    风控和网络错误在这里收口成一句可读的话，别把整页 412 HTML 丢给模型。
    """
    try:
        return await _discover(data_dir, source, limit, tid, mid, bvid, page)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "source": str(source), "error": _risk_error(exc)}


async def _discover(
    data_dir: Path,
    source: str = "hot",
    limit: int = 10,
    tid: str = "all",
    mid: int = 0,
    bvid: str = "",
    page: int = 1,
) -> dict:
    source = str(source or "hot").strip().lower()
    limit = max(1, min(_as_int(limit, 10), 50))
    page = max(1, _as_int(page, 1))

    if source == "hot":
        raw = await hot.get_hot_videos(pn=page, ps=limit)
        rows = [_archive_row(x) for x in (raw.get("list") or [])[:limit]]
        return {"source": "hot", "count": len(rows), "videos": rows}

    if source == "weekly":
        raw = await hot.get_weekly_hot_videos(week=1)
        rows = [_archive_row(x) for x in (raw.get("list") or [])[:limit]]
        return {"source": "weekly", "count": len(rows), "videos": rows}

    if source == "rank":
        raw = await rank.get_rank(_rank_type(tid))
        rows = [_archive_row(x) for x in (raw.get("list") or [])[:limit]]
        return {"source": "rank", "tid": str(tid or "all"), "count": len(rows), "videos": rows}

    if source == "up":
        if _as_int(mid) <= 0:
            return {"ok": False, "error": "source=up 需要 mid：UP 主 UID 可从 bili_video_info 的 author_uid 拿到"}
        cred = get_cred(data_dir)
        raw = await user.User(_as_int(mid), credential=cred).get_videos(pn=page, ps=limit)
        rows = [_archive_row(x) for x in (((raw.get("list") or {}).get("vlist")) or [])[:limit]]
        return {"source": "up", "mid": _as_int(mid), "count": len(rows), "videos": rows}

    if source == "feed":
        cred = get_cred(data_dir)
        raw = await dynamic.get_dynamic_page_info(cred, _type=dynamic.DynamicType.ALL, pn=page)
        rows: list[dict] = []
        skipped = 0
        for item in raw.get("items") or []:
            modules = item.get("modules") if isinstance(item.get("modules"), dict) else {}
            major = ((modules.get("module_dynamic") or {}) if isinstance(modules.get("module_dynamic"), dict) else {}).get("major") or {}
            archive = major.get("archive") if isinstance(major.get("archive"), dict) else {}
            if not archive.get("bvid"):
                skipped += 1
                continue
            row = _archive_row(archive)
            row["published"] = str(((modules.get("module_author") or {}) if isinstance(modules.get("module_author"), dict) else {}).get("pub_time") or "")
            rows.append(row)
            if len(rows) >= limit:
                break
        out = {"source": "feed", "count": len(rows), "skipped": skipped, "videos": rows}
        if not rows:
            out["note"] = "关注动态里没有视频投稿（关注 0 人，或这段时间没有新投稿）"
        return out

    if source == "related":
        if not bvid:
            return {"ok": False, "error": "source=related 需要 bvid"}
        cred = get_cred(data_dir)
        raw = await video.Video(bvid=bvid, credential=cred).get_related()
        # 17.4.2 的 get_related 直接返回 list，老版本返回 {"list": [...]} —— 两种都收。
        items = raw.get("list") if isinstance(raw, dict) else raw
        rows = [_archive_row(x) for x in ((items or [])[:limit])]
        return {"source": "related", "bvid": bvid, "count": len(rows), "videos": rows}

    return {"ok": False, "error": f"不支持的 source：{source}（hot/weekly/rank/up/feed/related）"}


async def my_list(data_dir: Path, kind: str = "toview", fid: int = 0, limit: int = 20) -> dict:
    """看自己账号里的库：稍后再看 / 某个收藏夹 / 观看历史。"""
    try:
        return await _my_list(data_dir, kind, fid, limit)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "kind": str(kind), "error": _risk_error(exc)}


async def _my_list(data_dir: Path, kind: str = "toview", fid: int = 0, limit: int = 20) -> dict:
    kind = str(kind or "toview").strip().lower()
    limit = max(1, min(_as_int(limit, 20), 50))
    cred = get_cred(data_dir)

    if kind == "toview":
        raw = await user.get_toview_list(cred)
        rows = [_archive_row(x) for x in (raw.get("list") or [])[:limit]]
        return {
            "kind": "toview",
            "total": _as_int(raw.get("count"), len(rows)),
            "count": len(rows),
            "videos": rows,
        }

    if kind == "favorites":
        media = _as_int(fid)
        if media <= 0:
            return {"ok": False, "error": "kind=favorites 需要 fid：先用 bili_favorite_folders 查收藏夹 id"}
        raw = await favorite_list.get_video_favorite_list_content(media_id=media, page=1, credential=cred)
        rows = [_archive_row(x) for x in (raw.get("medias") or [])[:limit]]
        info = raw.get("info") if isinstance(raw.get("info"), dict) else {}
        return {
            "kind": "favorites",
            "fid": media,
            "title": str(info.get("title") or ""),
            "total": _as_int(info.get("media_count"), len(rows)),
            "has_more": bool(raw.get("has_more")),
            "count": len(rows),
            "videos": rows,
        }

    if kind == "history":
        raw = await user.get_self_history_new(cred, ps=limit)
        rows = [_history_row(x) for x in (raw.get("list") or [])[:limit]]
        return {"kind": "history", "count": len(rows), "videos": rows}

    return {"ok": False, "error": f"不支持的 kind：{kind}（toview/favorites/history）"}


def _clock(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 60}:{total % 60:02d}"


async def highlights(data_dir: Path, bvid: str, window: int = 30, top: int = 5, segments: int = 4) -> dict:
    """按弹幕密度找「哪几分钟最热闹」。

    ⚠️ 弹幕按 6 分钟一个分段拉，只取前几段 —— 超长视频的尾部不在样本里，
    结果要按「采样」解释，不能当成全片统计。
    """
    cred = get_cred(data_dir)
    v = video.Video(bvid=bvid, credential=cred)
    info = await v.get_info()
    window = max(10, min(_as_int(window, 30), 120))
    top = max(1, min(_as_int(top, 5), 10))

    samples: list[Any] = []
    error = ""
    for index in range(max(1, min(_as_int(segments, 4), 6))):
        try:
            batch = await v.get_danmakus(page_index=index)
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {str(exc)[:120]}"
            break
        if not batch:
            break
        samples.extend(batch)
        if len(samples) >= 4000:
            break

    buckets: dict[int, dict] = {}
    for item in samples:
        at = float(getattr(item, "dm_time", 0) or 0)
        key = int(at // window) * window
        bucket = buckets.get(key)
        if bucket is None:
            bucket = buckets[key] = {"at": key, "clock": _clock(key), "count": 0, "samples": []}
        bucket["count"] += 1
        text = str(getattr(item, "text", "") or "")
        if text and len(bucket["samples"]) < 3:
            bucket["samples"].append(text[:40])

    ordered = sorted(buckets.values(), key=lambda b: (-b["count"], b["at"]))[:top]
    out: dict[str, Any] = {
        "bvid": bvid,
        "title": info.get("title"),
        "duration": info.get("duration"),
        "window": window,
        "total_danmaku": len(samples),
        "highlights": ordered,
    }
    if error:
        out["error"] = error
    if not samples and not error:
        out["note"] = "这条视频没有弹幕"
    return out


# ── 写入工具（默认不注册，见 host.py 的闸门） ───────────────────────────

async def watch_later_add(data_dir: Path, bvid: str) -> dict:
    """加入稍后再看。比收藏轻，适合「先存着，回头自己看」。"""
    cred = get_cred(data_dir)
    v = video.Video(bvid=bvid, credential=cred)
    info = await v.get_info()
    try:
        await v.add_to_toview()
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "bvid": bvid,
            "error": str(exc)[:200],
            "uncertain": not isinstance(exc, ResponseCodeException),
        }
    return {"ok": True, "bvid": bvid, "title": info.get("title"), "message": "已加入稍后再看"}


async def interact(data_dir: Path, action: str, bvid: str = "", uid: int = 0, num: int = 1) -> dict:
    """点赞 / 取消赞 / 三连 / 投币 / 关注。

    投币是真实消耗硬币的动作，额度由宿主控制；这里只管把动作发出去并如实返回。
    """
    action = str(action or "").strip().lower()
    cred = get_cred(data_dir)

    if action in {"like", "unlike", "triple", "coin"}:
        if not bvid:
            return {"ok": False, "error": f"action={action} 需要 bvid"}
        v = video.Video(bvid=bvid, credential=cred)
        info = await v.get_info()
        try:
            if action == "like":
                result = await v.like(True)
            elif action == "unlike":
                result = await v.like(False)
            elif action == "triple":
                result = await v.triple()
            else:
                result = await v.pay_coin(max(1, min(_as_int(num, 1), 2)), like=False)
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "action": action,
                "bvid": bvid,
                "error": str(exc)[:200],
                "uncertain": not isinstance(exc, ResponseCodeException),
            }
        return {"ok": True, "action": action, "bvid": bvid, "title": info.get("title"), "result": result}

    if action == "follow":
        target = _as_int(uid)
        if target <= 0:
            return {"ok": False, "error": "action=follow 需要 uid"}
        account = user.User(target, credential=cred)
        info = await account.get_user_info()
        try:
            result = await account.modify_relation(user.RelationType.SUBSCRIBE)
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "action": action,
                "uid": target,
                "error": str(exc)[:200],
                "uncertain": not isinstance(exc, ResponseCodeException),
            }
        return {"ok": True, "action": action, "uid": target, "name": info.get("name"), "result": result}

    return {"ok": False, "error": f"不支持的动作：{action}（like/unlike/triple/coin/follow）"}


async def reply(
    data_dir: Path,
    bvid: str,
    text: str,
    rpid: int = 0,
    root: int = 0,
    picture: Optional[str] = None,
) -> dict:
    body = str(text or "").strip()
    if len(body) > 150:
        return {"success": False, "error": "评论正文不能超过150字符"}
    sticker = None
    if picture:
        # 图片评论：走 pictures 那条路（send_comment 内部会先 upload_bfs 再带 img_src）。
        # 允许「只有图、没有字」—— B站 上纯图评论是正常用法。
        from bilibili_api.utils.picture import Picture

        path = Path(picture)
        if not path.is_file():
            return {"success": False, "error": f"图片不存在：{picture}"}
        # ⚠️ 收藏上限（6MB）和上传上限（2MB）不是一个数：图能存不代表能发。
        #    这里先卡住，别把 4.8MB 的 GIF 传上去等接口拒 —— 白传一次还浪费带宽。
        size = path.stat().st_size
        if size > 2 * 1024 * 1024:
            return {
                "success": False,
                "error": f"这张图 {size / 1024 / 1024:.1f} MB，超过评论图片上限 2 MB；换一张或用表情码",
            }
        try:
            sticker = Picture.from_file(str(path))
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"图片读不进来：{type(exc).__name__}: {str(exc)[:120]}"}
    if not body and sticker is None:
        return {"success": False, "error": "text 不能为空"}
    if body and not body.strip() and sticker is not None:
        body = ""
    cred = get_cred(data_dir)
    info = await video.Video(bvid=bvid, credential=cred).get_info()
    aid = info["aid"]
    try:
        if rpid == 0:
            result = await comment.send_comment(
                text=body,
                oid=aid,
                type_=comment.CommentResourceType.VIDEO,
                credential=cred,
                pic=sticker,
            )
        else:
            actual_root = root if root != 0 else rpid
            result = await comment.send_comment(
                text=body,
                oid=aid,
                type_=comment.CommentResourceType.VIDEO,
                root=actual_root,
                parent=rpid,
                credential=cred,
                pic=sticker,
            )
    except Exception as exc:  # noqa: BLE001
        message, permanent = _response_error(exc)
        return {"success": False, "error": message, "uncertain": not permanent}

    out: dict[str, Any] = {"success": True, "message": "评论发送成功"}
    if sticker is not None:
        out["picture"] = True
    if isinstance(result, dict):
        for key in ("rpid", "rpid_str", "root", "parent"):
            value = result.get(key)
            if isinstance(value, (int, str)) and str(value).strip() and str(value) != "0":
                out[key] = value
    return out


async def send_message(data_dir: Path, receiver_uid: int, text: str) -> dict:
    body = str(text or "").strip()
    if not body:
        return {"success": False, "error": "text 不能为空"}
    if len(body) > 500:
        return {"success": False, "error": "私信正文不能超过500字符"}
    cred = get_cred(data_dir)
    try:
        result = await session.send_msg(
            credential=cred,
            receiver_id=int(receiver_uid),
            msg_type=session.EventType.TEXT,
            content=body,
        )
        return {
            "success": True,
            "message": f"私信已发送给 UID {int(receiver_uid)}",
            "data": result if isinstance(result, dict) else str(result),
        }
    except Exception as exc:  # noqa: BLE001
        message, permanent = _response_error(exc)
        return {"success": False, "error": message, "uncertain": not permanent}


# ── 评论复核（平移 lib/verify.mjs） ─────────────────────────────────────

async def _jget(url: str, headers: dict[str, str]) -> dict:
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, headers=headers) as resp:
                text = await resp.text()
        try:
            return json.loads(text)
        except ValueError:
            return {"code": -999, "message": "not json"}
    except Exception as exc:  # noqa: BLE001
        return {"code": -998, "message": str(exc)}


async def verify_comment(
    data_dir: Path, bvid: str, rpid: int, root: int = 0
) -> dict:
    """查一条评论是否公开可见。

    ⚠️ 措辞守则：看不到只能写「没查到」，**绝不写「没发出去」** —— 翻页 / 热度排序都会漏。
    """
    cred = load_credential(data_dir)
    if cred is None:
        return {"error": "未登录，无法复核"}
    target = _as_int(rpid)
    # 以前这里用裸 aiohttp 打 x/web-interface/view，回的是 412 HTML，于是**每次都报
    # 「取视频信息失败」**。改成走库里的 get_info（同一套登录会话，实测正常）。
    try:
        info = await video.Video(bvid=bvid, credential=cred).get_info()
        aid = _as_int(info.get("aid"))
    except Exception as exc:  # noqa: BLE001
        return {"bvid": bvid, "rpid": target, "visible": None,
                "how": "取视频信息失败", "error": _risk_error(exc),
                "note": "视频信息取不到，没法复核（通常是风控或视频不可见）"}
    if not aid:
        return {"bvid": bvid, "rpid": target, "visible": None,
                "how": "取视频信息失败", "note": "拿不到 aid"}

    if _as_int(root) > 0:
        rows, error = await _sub_replies(cred, aid, _as_int(root), 60)
        hit = next((row for row in rows if _as_int(row.get("rpid")) == target), None)
        if hit:
            return {"bvid": bvid, "rpid": target, "root": _as_int(root), "visible": True,
                    "likes": hit.get("like", 0),
                    "how": f"楼中楼·root={_as_int(root)}（扫了 {len(rows)} 条）"}
        note = (f"那一串扫了 {len(rows)} 条没找到 —— 可能还在审核，也可能沉在后面（不等于没发出去）"
                if rows else "那一串暂时拉不到内容 —— 可能还在审核（不等于没发出去）")
        out = {"bvid": bvid, "rpid": target, "root": _as_int(root), "visible": None,
               "scanned": len(rows), "how": f"楼中楼·root={_as_int(root)}", "note": note}
        if error:
            out["error"] = error
        return out

    scanned = 0
    for order, label in ((comment.OrderType.TIME, "最新"), (comment.OrderType.LIKE, "热门")):
        page = 1
        while page <= 3:
            try:
                resp = await comment.get_comments(
                    oid=aid, type_=comment.CommentResourceType.VIDEO,
                    page_index=page, order=order, credential=cred)
            except Exception as exc:  # noqa: BLE001
                return {"bvid": bvid, "rpid": target, "visible": None, "scanned": scanned,
                        "how": f"顶层·{label}第 {page} 页", "error": _risk_error(exc),
                        "note": "接口报错，没法判断可见性（不等于没发出去）"}
            rows = resp.get("replies") or []
            if not rows:
                break
            scanned += len(rows)
            hit = next((row for row in rows if _as_int(row.get("rpid")) == target), None)
            if hit:
                return {"bvid": bvid, "rpid": target, "visible": True,
                        "likes": hit.get("like", 0), "how": f"顶层·{label}第 {page} 页"}
            page += 1
            await asyncio.sleep(0.4)

    return {"bvid": bvid, "rpid": target, "visible": None, "scanned": scanned,
            "how": "顶层·最新与热门各 3 页",
            "note": "这几页里没找到 —— 可能还在审核，也可能只是翻不到（不等于没发出去）"}


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
