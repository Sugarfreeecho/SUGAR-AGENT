"""宿主内浏览器桥（方案 B）。

只对已授权插件开放四个语义方法：
  open_chat / send_text / send_media / read_recent
底层复用浏览器插件已配对的浏览器（用户现有登录态），不做裸 CDP 暴露。
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Any

ALLOWED = {"open_chat", "send_text", "send_media", "read_recent", "capture_send",
           "capture_begin", "capture_end"}
CALLERS = {"sugar-assistant"}

_REF = re.compile(r"\[ref=([A-Za-z0-9]+)\]")
_TEXTBOX = re.compile(r"textbox[^\n]*?\[ref=([A-Za-z0-9]+)\]", re.IGNORECASE)
_TAB_LINE = re.compile(r"^\s*-?\s*(\d+):\s*.*next/messenger", re.MULTILINE)
MESSENGER_SUFFIX = "next/messenger/"
_LOOP: asyncio.AbstractEventLoop | None = None
_MANAGER: Any = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _LOOP
    _LOOP = loop


def set_manager(manager: Any) -> None:
    global _MANAGER
    _MANAGER = manager


def call_sync(caller: str, method: str, params: dict, timeout: int = 120) -> Any:
    """给非事件循环线程用的同步入口。"""
    if _LOOP is None:
        raise RuntimeError("浏览器桥尚未就绪（宿主循环未绑定）")
    future = asyncio.run_coroutine_threadsafe(execute(caller, method, params), _LOOP)
    return future.result(timeout)


def _manager():
    if _MANAGER is not None:
        return _MANAGER
    import sys

    for module in list(sys.modules.values()):
        if callable(getattr(module, "bridge_endpoint", None)) and hasattr(module, "_manager"):
            return getattr(module, "_manager")
    return None


def _runtime():
    manager = _manager()
    if not manager or not manager.active:
        raise RuntimeError("浏览器插件未启用")
    browser_id = manager.default_browser
    runtime = manager.runtimes.get(browser_id) if browser_id else None
    if runtime is None:
        raise RuntimeError("没有已配对的浏览器，请先在设置里连接")
    return runtime


async def _call(tool: str, arguments: dict[str, Any], timeout: int = 90) -> str:
    runtime = _runtime()
    payload = {
        "session_id": "sugar-assistant-bridge",
        "run_id": "sugar-assistant-bridge",
        "tool": tool,
        "arguments": arguments,
        "workspace": os.environ.get("SUGAR_WEB_WORKSPACE") or os.getcwd(),
        "browser_context": None,
    }
    async with runtime.tool_gate:
        raw = await runtime.request("call", payload, timeout=timeout)
    if isinstance(raw, dict) and raw.get("isError"):
        raise RuntimeError(str(raw)[:300])
    content = raw.get("content") if isinstance(raw, dict) else raw
    if isinstance(content, list):
        parts = [str(item.get("text") or "") for item in content
                 if isinstance(item, dict) and item.get("type") == "text"]
        content = "\n".join(parts)
    return str(content or "")


def _first_ref(text: str) -> str:
    match = _REF.search(text or "")
    return match.group(1) if match else ""


def _first_textbox(text: str) -> str:
    match = _TEXTBOX.search(text or "")
    return match.group(1) if match else ""


def _chat_row_ref(found: str, name: str) -> str:
    """在 find 结果里找“会话行”的可点击祖先：名字往上最近的 cursor=pointer 节点。"""
    lines = (found or "").splitlines()
    for index, line in enumerate(lines):
        if name not in line:
            continue
        for back in range(index, max(-1, index - 10), -1):
            current = lines[back]
            if "cursor=pointer" in current:
                match = _REF.search(current)
                if match:
                    return match.group(1)
    return _first_ref(found)


async def _find_ref(text: str, attempts: int = 3) -> str:
    found = ""
    for _ in range(attempts):
        found = await _call("browser_find", {"text": text})
        ref = _first_ref(found)
        if ref:
            return ref
        await asyncio.sleep(2)
    raise RuntimeError(f"找不到：{text}；find 返回：{found[:160] or '<空>'}")


async def open_chat(tenant: str, chat_name: str) -> dict:
    url = f"https://{tenant}/{MESSENGER_SUFFIX}"
    reused = await _ensure_tab(url)
    if not reused:
        await _call("browser_navigate", {"url": url})
    marker = f"发送给 {chat_name}"

    # 直接点左侧会话行（18:48 已验证的路径），不碰搜索页
    found = await _call("browser_find", {"text": chat_name})
    ref = _chat_row_ref(found, chat_name)
    if not ref:
        raise RuntimeError(f"会话列表里没有：{chat_name}")
    await _call("browser_click", {"element": chat_name, "target": ref})
    await asyncio.sleep(1.5)
    snap = await _call("browser_snapshot", {})
    if marker not in snap:
        await asyncio.sleep(2)
        snap = await _call("browser_snapshot", {})
    if marker not in snap:
        raise RuntimeError(f"会话未切换成功，缺少「{marker}」")
    return {"ok": True, "marker": marker}


async def _ensure_tab(url: str) -> bool:
    """优先复用任何已打开的飞书标签页；没有才新建。不碰其它标签。"""
    listing = await _call("browser_tabs", {"action": "list"})
    match = _TAB_LINE.search(listing or "")
    if not match:
        await _call("browser_tabs", {"action": "new", "url": url})
        await asyncio.sleep(2.5)
        listing = await _call("browser_tabs", {"action": "list"})
        match = _TAB_LINE.search(listing or "")
        if not match:
            raise RuntimeError("专用标签页创建失败")
        await _call("browser_tabs", {"action": "select", "index": int(match.group(1))})
        return False
    await _call("browser_tabs", {"action": "select", "index": int(match.group(1))})
    return True


COMPOSER = ".zone-container"
SEND_BUTTON = ".submit__button > .ud__button"


async def _composer_ref() -> str:
    # 直接用选择器：飞书输入框是 contenteditable，文本匹配容易命中外层容器
    return COMPOSER


async def _click_send() -> None:
    try:
        await _call("browser_click", {"element": "发送按钮", "target": SEND_BUTTON})
    except Exception:
        await _call("browser_press_key", {"key": "Enter"})


async def send_text(tenant: str, chat_name: str, text: str) -> dict:
    if not text.strip():
        raise ValueError("文本为空")
    await open_chat(tenant, chat_name)
    box = await _composer_ref()
    await _call("browser_type", {"element": "消息输入框", "target": box, "text": text})
    snap = await _call("browser_find", {"text": text[:20]})
    if text[:20] not in snap:
        raise RuntimeError("输入框内容与待发文本不一致")
    await _click_send()
    return {"ok": True, "chars": len(text)}


async def send_media(tenant: str, chat_name: str, path: str, kind: str = "file") -> dict:
    if not path or not os.path.exists(path):
        raise RuntimeError(f"附件不存在：{path}")
    await open_chat(tenant, chat_name)
    ext = os.path.splitext(path)[1].lower()
    image = ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
    if image:
        # 图片入口藏在“展开”后的工具栏里；先展开再点图片，才会弹出文件选择框
        try:
            await _call("browser_click", {"element": "展开工具栏",
                                          "target": "svg[data-icon=ExpandOutlined]"})
            await asyncio.sleep(1)
        except Exception:
            pass
        await _call("browser_click", {"element": "图片", "target": "svg[data-icon=ImageOutlined]"})
        await asyncio.sleep(1.5)
    await _call("browser_file_upload", {"paths": [path]})
    await asyncio.sleep(3.5)
    await _click_send()
    return {"ok": True, "path": os.path.basename(path), "kind": kind}


async def read_recent(tenant: str, chat_name: str) -> dict:
    await open_chat(tenant, chat_name)
    snap = await _call("browser_snapshot", {})
    return {"ok": True, "text": snap[-4000:]}


async def capture_send(tenant: str, chat_name: str, text: str) -> dict:
    """发一条消息并抓取期间的 POST 请求，用于还原 Web 内部接口。"""
    runtime = _runtime()
    run_id = "capture-send"
    await runtime.request("capture_start", {"run_id": run_id}, timeout=30)
    try:
        result = await send_text(tenant, chat_name, text)
    finally:
        records = await runtime.request("capture_stop", {"run_id": run_id}, timeout=30)
    return {"ok": True, "send": result, "capture": records}


async def capture_begin(tenant: str, run_id: str = "manual") -> dict:
    runtime = _runtime()
    await runtime.request("capture_start", {"run_id": run_id}, timeout=30)
    return {"ok": True, "run_id": run_id}


async def capture_end(tenant: str, run_id: str = "manual") -> dict:
    runtime = _runtime()
    records = await runtime.request("capture_stop", {"run_id": run_id}, timeout=30)
    return {"ok": True, "capture": records}


async def execute(caller: str, method: str, params: dict) -> dict:
    if caller not in CALLERS:
        raise PermissionError(f"插件 {caller} 未获授权使用浏览器桥")
    if method not in ALLOWED:
        raise PermissionError(f"方法 {method} 不在白名单")
    tenant = str(params.get("tenant") or "")
    chat_name = str(params.get("chat_name") or "")
    if not tenant or not chat_name:
        raise ValueError("tenant/chat_name 必填")
    if method == "open_chat":
        return await open_chat(tenant, chat_name)
    if method == "send_text":
        return await send_text(tenant, chat_name, str(params.get("text") or ""))
    if method == "send_media":
        return await send_media(tenant, chat_name, str(params.get("path") or ""),
                                str(params.get("kind") or "file"))
    if method == "capture_begin":
        return await capture_begin(tenant)
    if method == "capture_end":
        return await capture_end(tenant)
    if method == "capture_send":
        return await capture_send(tenant, chat_name, str(params.get("text") or ""))
    return await read_recent(tenant, chat_name)
