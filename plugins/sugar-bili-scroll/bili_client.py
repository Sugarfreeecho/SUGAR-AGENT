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
import sys
import importlib.util
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

import aiohttp

from bilibili_api import Credential, comment, favorite_list, search, session, user, video
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

async def search_videos(keyword: str, num: int = 10, order: str = "totalrank") -> dict:
    order_map = {
        "totalrank": search.OrderVideo.TOTALRANK,
        "click": search.OrderVideo.CLICK,
        "pubdate": search.OrderVideo.PUBDATE,
        "dm": search.OrderVideo.DM,
    }
    result = await search.search_by_type(
        keyword=keyword,
        search_type=search.SearchObjectType.VIDEO,
        page=1,
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
    return {"keyword": keyword, "count": len(videos), "videos": videos}


async def video_info(data_dir: Path, bvid: str) -> dict:
    cred = get_cred(data_dir)
    info = await video.Video(bvid=bvid, credential=cred).get_info()
    stat = info.get("stat", {})
    return {
        "bvid": info.get("bvid"),
        "aid": info.get("aid"),
        "title": info.get("title"),
        "description": str(info.get("desc") or "")[:800],
        "author": (info.get("owner") or {}).get("name"),
        "duration": info.get("duration"),
        "pubdate": info.get("pubdate"),
        "pages": len(info.get("pages") or []),
        "tags": [t.get("tag_name") for t in (info.get("tag") or []) if t.get("tag_name")],
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


async def comments(data_dir: Path, bvid: str, num: int = 30) -> dict:
    """抓顶层评论。

    ⭐ 除了正文，还带两样「表情相关的证据」：
      · `emotes`   —— 正文里的 B站 表情码（`[doge]` 这种），模型据此知道"评论区在用哪些码"
      · `pictures` —— 评论带图时的图床地址，模型据此知道"这张图长什么样、值不值得收藏"
    两样都只在存在时才出现，避免把每条评论都撑大。
    """
    cred = get_cred(data_dir)
    info = await video.Video(bvid=bvid, credential=cred).get_info()
    aid = info["aid"]

    collected: list[dict] = []
    page = 1
    fetch_error = ""
    limit = max(1, min(int(num or 30), 100))
    while len(collected) < limit:
        try:
            resp = await comment.get_comments(
                oid=aid,
                type_=comment.CommentResourceType.VIDEO,
                page_index=page,
                order=comment.OrderType.LIKE,
                credential=cred,
            )
            replies = resp.get("replies") or []
            if not replies:
                break
            for r in replies:
                member = r.get("member") or {}
                content = r.get("content") or {}
                row = {
                    "rpid": r.get("rpid", 0),
                    "user": member.get("uname", ""),
                    "content": str(content.get("message") or ""),
                    "like": r.get("like", 0),
                    "reply_count": r.get("rcount", 0),
                    "time": r.get("ctime", 0),
                }
                codes = EMOTE_CODE_RE.findall(row["content"])
                if codes:
                    row["emotes"] = list(dict.fromkeys(codes))[:4]
                pictures = content.get("pictures") or []
                if pictures:
                    row["pictures"] = [
                        {
                            "url": str(pic.get("img_src") or ""),
                            "width": int(pic.get("img_width") or 0),
                            "height": int(pic.get("img_height") or 0),
                        }
                        for pic in pictures[:3]
                        if pic.get("img_src")
                    ]
                subs = [
                    {
                        "user": (sub.get("member") or {}).get("uname", ""),
                        "content": str((sub.get("content") or {}).get("message") or ""),
                        "like": sub.get("like", 0),
                    }
                    for sub in (r.get("replies") or [])[:2]
                ]
                if subs:
                    row["top_replies"] = subs
                collected.append(row)
            page += 1
            await asyncio.sleep(0.5)
        except Exception as exc:  # noqa: BLE001
            # 抓取失败不能吞成「这条视频 0 条评论」，否则日报静默失真。
            fetch_error = f"{type(exc).__name__}: {exc}"
            break

    out = {"bvid": bvid, "count": len(collected[:limit]), "comments": collected[:limit]}
    if fetch_error:
        out["error"] = fetch_error
    return out


async def danmaku(data_dir: Path, bvid: str, num: int = 100) -> dict:
    cred = get_cred(data_dir)
    items = await video.Video(bvid=bvid, credential=cred).get_danmakus(page_index=0)
    limit = max(1, min(int(num or 100), 500))
    rows = [{"text": d.text, "time": d.dm_time} for d in items[:limit]]
    return {"bvid": bvid, "count": len(rows), "danmakus": rows}


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


# ── 写入工具（默认不注册，见 host.py 的闸门） ───────────────────────────

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
        return {"success": False, "error": str(exc), "uncertain": not isinstance(exc, ResponseCodeException)}

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
        return {"success": False, "error": str(exc), "uncertain": not isinstance(exc, ResponseCodeException)}


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
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/",
               "Cookie": cookie_header(cred)}

    meta = await _jget(
        f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", headers
    )
    if meta.get("code") != 0:
        return {"bvid": bvid, "rpid": int(rpid), "visible": None,
                "how": "取视频信息失败", "note": "视频可能已删/不可见"}
    aid = meta["data"]["aid"]

    if not root:
        data = await _jget(
            f"https://api.bilibili.com/x/v2/reply/main?type=1&oid={aid}&mode=2&next=0&ps=20",
            headers,
        )
        rows = (data.get("data") or {}).get("replies") or []
        hit = next((r for r in rows if r.get("rpid") == int(rpid)), None)
        if hit:
            return {"bvid": bvid, "rpid": int(rpid), "visible": True,
                    "likes": hit.get("like", 0), "how": "顶层·最新一页"}
        return {"bvid": bvid, "rpid": int(rpid), "visible": None, "how": "顶层·最新一页",
                "note": "最新一页里没找到 —— 可能还在审核，也可能只是翻页看不到（不等于没发出去）"}

    data = await _jget(
        f"https://api.bilibili.com/x/v2/reply/reply?type=1&oid={aid}&root={int(root)}&ps=20&pn=1",
        headers,
    )
    rows = (data.get("data") or {}).get("replies") or []
    hit = next((r for r in rows if r.get("rpid") == int(rpid)), None)
    if hit:
        return {"bvid": bvid, "rpid": int(rpid), "visible": True,
                "likes": hit.get("like", 0), "how": f"楼中楼·root={int(root)}"}
    note = (
        f"那一串里有 {len(rows)} 条，但没有我们这条 —— 可能还在审核（不等于没发出去）"
        if rows
        else "那一串暂时拉不到内容 —— 可能还在审核（不等于没发出去）"
    )
    return {"bvid": bvid, "rpid": int(rpid), "visible": None,
            "how": f"楼中楼·root={int(root)}", "note": note}


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
