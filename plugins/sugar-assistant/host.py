"""小Sugar助手 · 宿主生命周期与设置页后端。

启用后：校验配置 → 装配 Core → 拿宿主会话服务 → 起通道 → 挂 `/api/sugar-assistant/*`。
页面（原 `web/index.html`）已按用户要求移除；这组接口保留给后续实现页面的人复用。
微信扫码登录仍可通过 `install()` 里的接口发起（子进程输出里解析二维码地址）。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import types
import time
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

for _name in [name for name in sys.modules if name == "sugar_assistant" or name.startswith("sugar_assistant.")]:
    del sys.modules[_name]

from sugar_assistant.config import Config  # noqa: E402
from sugar_assistant.console import ConsoleStore  # noqa: E402
from sugar_assistant import paths  # noqa: E402
from sugar_assistant.plugin import build_adapters, create_runtime  # noqa: E402
from sugar_assistant.service import SugarAssistantService, start_channels  # noqa: E402

if str(_PLUGIN_ROOT) in sys.path:
    sys.path.remove(str(_PLUGIN_ROOT))

# 放在模块级：host.py 用了 `from __future__ import annotations`，
# FastAPI 解析注解时要在模块 globals 里找到 Request，否则会把 body 当 query 参数（422）。
try:
    from fastapi import APIRouter, Request  # type: ignore
    from fastapi.responses import JSONResponse  # type: ignore
except Exception:  # pragma: no cover - 没装 fastapi 时插件仍可加载
    APIRouter = None  # type: ignore
    Request = None  # type: ignore
    JSONResponse = None  # type: ignore

LOG = logging.getLogger("sugar_assistant")
_WEB_LOGIN: dict = {}
STATE_DIR = paths.data_dir()
_LOGIN: dict = {"phase": "idle", "qrUrl": "", "error": "", "started_at": 0.0}
def _shared():
    """跨热重载的进程级小抽屉。

    host.py 会被重新 import，模块 globals 会清空；`sys.modules` 里的独立模块不会。
    """
    module = sys.modules.get("sugarstate")
    if module is None:
        module = types.ModuleType("sugarstate")
        sys.modules["sugarstate"] = module
    return module

def _svc():
    """当前 Core 实例。

    热重载会重新 import 本模块：旧模块注册的路由仍指着旧 globals，
    所以真正的实例挂在 `app.state` 上（app 对象跨重载不变）。
    """
    service = getattr(_shared(), "service", None)
    return service or globals().get("_service")

def _state_dir() -> str:
    return STATE_DIR


def _load_host():
    """拿宿主会话控制服务 + 桥。拿不到返回 None（插件仍可加载，只是不跑）。"""
    try:
        from remote_control.public import transport_context  # type: ignore

        from sugar_assistant.bridge.sugaragent import SugarAgentHost

        ctx = transport_context("sugar-assistant")
        service = getattr(ctx, "gateway_service", None)
        if service is None:
            return None
        # 热重载会换 epoch：给桥一个工厂，遇到“授权已撤销”时现场换新代理。
        factory = lambda: transport_context("sugar-assistant").gateway_service  # noqa: E731
        return SugarAgentHost(service, service_factory=factory)
    except Exception as exc:  # 宿主版本差异不该让插件加载失败
        LOG.warning("小Sugar助手：未拿到宿主会话服务（%s），插件以只读状态启动", exc)
        return None


def _inject_bridge_env() -> None:
    """把浏览器桥的地址与进程内令牌交给 worker（只在内存与子进程环境里，不落盘）。"""
    import sys

    if os.environ.get("SUGAR_BROWSER_BRIDGE_TOKEN"):
        return
    for module in list(sys.modules.values()):
        endpoint = getattr(module, "bridge_endpoint", None)
        if not callable(endpoint):
            continue
        try:
            info = endpoint() or {}
            token, path = str(info.get("token") or ""), str(info.get("path") or "")
            if not token or not path:
                continue
            os.environ["SUGAR_BROWSER_BRIDGE_TOKEN"] = token
            os.environ["SUGAR_BROWSER_BRIDGE_URL"] = f"http://127.0.0.1:8192{path}"
            from sugar_assistant import web_sender

            os.environ.setdefault("SUGAR_WEB_TENANT", web_sender.load_config()["tenant"])

            LOG.info("小Sugar助手：浏览器桥已就绪（%s）", path)
            return
        except Exception:
            continue


def _boot() -> tuple[SugarAssistantService | None, dict, ConsoleStore]:
    """装配 Core；拿不到宿主服务时仍返回 console，设置页照样能看状态。"""
    moved = paths.migrate_legacy()
    console: ConsoleStore = globals().get("_console") or ConsoleStore(_state_dir())
    globals()["_console"] = console
    if moved:
        console.log("migrated", files=moved, to=STATE_DIR)
        LOG.info("小Sugar助手：已把旧文件迁到 %s（%s）", STATE_DIR, ", ".join(moved))
    config = Config.load()
    _inject_bridge_env()
    host = _load_host()
    if host is None or not config.enabled:
        return None, {}, console
    bind = getattr(host, "bind_loop", None)
    if callable(bind):
        try:
            bind(asyncio.get_running_loop())
        except RuntimeError:
            pass
    adapters = build_adapters(config)
    runtime = create_runtime(config, host, adapters=adapters, console=console, state_dir=_state_dir())
    runtime.owner_chat_id = os.getenv("SUGAR_OWNER_CHAT_ID", "").strip()
    # 默认不发"收到"：这类中间态对用户没信息量，只回真正的结果或必要的错误
    runtime.ack_enabled = os.getenv("SUGAR_ACK", "0").strip() not in {"", "0", "false", "no"}
    service = SugarAssistantService(runtime, merge_window_ms=int(os.getenv("SUGAR_MERGE_MS", "300") or 300))
    def _reconcile() -> None:
        try:
            report = runtime.reconcile_stale_ops()
            if report:
                logging.getLogger("sugar_assistant").info("启动对账：%s", report)
        except Exception:
            logging.getLogger("sugar_assistant").exception("启动对账失败（不影响消息处理）")

    threading.Thread(target=_reconcile, name="sugar-reconcile", daemon=True).start()
    return service, adapters, console


async def start(context, _plugin):
    # 重载会再次调用 start：先把上一份服务/适配器停掉，
    # 否则旧 sidecar 线程会用已关闭的事件循环继续收消息（分发直接丢）。
    if globals().get("_service") is not None or globals().get("_adapters"):
        try:
            await stop(context, _plugin)
        except Exception as exc:
            LOG.warning("小Sugar助手：旧实例清理失败（%s）", exc)
    _reload_plugin_modules()
    service, adapters, console = _boot()
    globals()["_service"] = service
    globals()["_adapters"] = adapters
    globals()["_started_at"] = time.time()
    _shared().service = service
    _shared().adapters = adapters
    console.log("start", pid=os.getpid(), started=int(time.time()))
    if service is None:
        console.log("boot_skipped", reason="没有宿主会话服务或配置关闭")
        LOG.warning("小Sugar助手：Core 未启动（无宿主服务或 enabled=false）")
        return
    failures = await start_channels(adapters, service.handle)
    for name, reason in failures:
        console.log("channel_failed", channel=name, reason=reason)
    console.log("boot", channels=sorted(adapters), failures=[name for name, _ in failures])
    LOG.info("小Sugar助手：Core 已装配（通道 %s）", sorted(adapters) or "无")


def _reload_plugin_modules() -> None:
    """插件内模块热重载：sys.modules 里的旧对象不换，改代码就等于没改。

    只重载 sugar_assistant.*（含 channels/bridge），不碰宿主模块；
    入口 host.py 自身无法在运行中安全重载，仍需宿主重启才会更新。
    """
    import importlib

    names = [name for name in list(sys.modules) if name.startswith("sugar_assistant")]
    # 先叶子后根：失败也不阻断启动
    for name in sorted(names, key=lambda item: item.count("."), reverse=True):
        module = sys.modules.get(name)
        if module is None:
            continue
        try:
            importlib.reload(module)
        except Exception as exc:  # pragma: no cover - 单模块失败不影响其它
            LOG.warning("小Sugar助手：模块 %s 重载失败（%s）", name, exc)


async def stop(_context, _plugin):
    service = globals().pop("_service", None)
    adapters = globals().pop("_adapters", {}) or {}
    for name, adapter in adapters.items():
        try:
            await adapter.stop()
        except Exception as exc:
            LOG.warning("小Sugar助手：通道 %s 停止失败（%s）", name, exc)
    if service is not None:
        await service.close()


# ---------------------------------------------------------------- 设置页
def _config_path() -> str:
    return paths.config_path()


def _read_config_file() -> dict:
    path = _config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def install(app, context, plugin) -> None:
    """宿主会调用它：注册 /api/sugar-assistant/* 与静态页。"""
    if APIRouter is None:  # pragma: no cover
        LOG.warning("小Sugar助手：宿主没有 fastapi，设置页接口未挂载")
        return

    _shared().app = app
    router = APIRouter(prefix="/api/sugar-assistant")

    def console() -> ConsoleStore:
        store = globals().get("_console")
        if store is None:
            store = ConsoleStore(_state_dir())
            globals()["_console"] = store
        return store

    @router.get("/status")
    async def status():
        from sugar_assistant import panel

        service = _svc()
        return panel.status_payload(service, console(), started_at=globals().get("_started_at") or 0.0,
                                    fallback_adapters=(globals().get("_adapters")
                                                       or getattr(getattr(globals().get("_APP"), "state", None),
                                                                  "sugar_adapters", None)))

    @router.get("/conversations")
    async def conversations():
        from sugar_assistant import panel

        return panel.conversations_payload(_svc())

    @router.get("/logs")
    async def logs(limit: int = 100):
        items = console().events(max(1, min(500, limit)))
        items.reverse()
        return {"items": items}

    @router.get("/persona")
    async def persona_get():
        return console().persona()

    @router.put("/persona")
    async def persona_put(request: Request):
        payload = await request.json()
        return console().save_persona(payload)

    @router.get("/persons")
    async def persons_get():
        return {"items": console().persons()}

    @router.post("/persons")
    async def persons_add(request: Request):
        try:
            return console().add_person(await request.json())
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    @router.delete("/persons/{person_id}")
    async def persons_remove(person_id: str):
        return {"removed": console().remove_person(person_id)}

    @router.get("/config")
    async def config_get():
        from sugar_assistant import identity as identity_mode

        from sugar_assistant import panel

        config = Config.load()
        return {
            "enabled": config.enabled,
            "session_scope": config.session_scope,
            "defaults": config.defaults,
            "host_workspace": panel.host_workspace(),
            "models": panel.list_models(),
            "identity": {"mode": identity_mode.current(), "chats": identity_mode.chats()},
            "channels": {
                name: {"enabled": cfg.enabled, "quota": cfg.quota,
                       "allow": cfg.allow, "allow_groups": cfg.allow_groups}
                for name, cfg in config.channels.items()
            },
            "web": panel.web_status(),
        }

    @router.put("/web")
    async def web_put(request: Request):
        """浏览器兜底通道：只改 web.json，不动主配置。"""
        from sugar_assistant import web_sender

        payload = await request.json()
        current = web_sender.load_config()
        current.update({
            "enabled": bool(payload.get("enabled", current["enabled"])),
            "tenant": str(payload.get("tenant", current["tenant"]) or "").strip(),
            "cdp_url": str(payload.get("cdp_url", current.get("cdp_url", "")) or "").strip(),
            "headless": bool(payload.get("headless", current["headless"])),
            "timeout_ms": int(payload.get("timeout_ms", current["timeout_ms"])),
        })
        if "allow" in payload:
            current["allow"] = [str(x) for x in (payload.get("allow") or [])]
        target = web_sender._config_path()  # noqa: SLF001
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            json.dump(current, fh, ensure_ascii=False, indent=2)
        return {"ok": True, "web": current}

    @router.post("/bridge/probe")
    async def bridge_probe(request: Request):
        """仅回环可用：验证浏览器桥是否真的能驱动已登录浏览器。"""
        import sys

        client = getattr(request, "client", None)
        if client is not None and client.host not in {"127.0.0.1", "::1"}:
            return {"ok": False, "error": "loopback only"}
        payload = await request.json()
        try:
            import plugin_bus
        except Exception:
            return {"ok": False, "error": "插件服务总线未加载"}
        if not plugin_bus.available("browser"):
            return {"ok": False, "error": "浏览器插件尚未注册服务"}
        tenant = str(payload.get("tenant") or os.environ.get("SUGAR_WEB_TENANT") or "")
        chat_name = str(payload.get("chat_name") or "")
        method = str(payload.get("method") or "read_recent")
        if method not in {"read_recent", "open_chat", "send_text", "send_media", "capture_send",
                          "capture_begin", "capture_end"}:
            return {"ok": False, "error": f"probe 不支持 {method}"}
        params = {"tenant": tenant, "chat_name": chat_name}
        if method == "send_text":
            params["text"] = str(payload.get("text") or "")
        if method == "send_media":
            params["path"] = str(payload.get("path") or "")
            params["kind"] = str(payload.get("kind") or "file")
        if method == "capture_send":
            params["text"] = str(payload.get("text") or "")
        try:
            text = await plugin_bus.call("sugar-assistant", "browser", method, params)
            if method != "read_recent":
                return {"ok": True, "result": text}
            body = text.get("text", "") if isinstance(text, dict) else str(text)
            return {"ok": True, "chars": len(body), "head": body[:120]}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @router.post("/web/login")
    async def web_login_start():
        """弹一次可见浏览器让用户扫码；进程独立，接口只负责拉起。"""
        import subprocess
        import sys

        from sugar_assistant import web_login, web_sender

        if _WEB_LOGIN.get("proc") and _WEB_LOGIN["proc"].poll() is None:
            return {"ok": True, "running": True}
        env = {**os.environ, "PYTHONPATH": os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}
        proc = subprocess.Popen([sys.executable, "-m", "sugar_assistant.web_login"],
                                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                env=env)
        _WEB_LOGIN["proc"] = proc
        return {"ok": True, "running": True, "pid": proc.pid}

    @router.get("/web/login")
    async def web_login_status():
        from sugar_assistant import web_login, web_sender

        proc = _WEB_LOGIN.get("proc")
        running = bool(proc and proc.poll() is None)
        marker = {}
        try:
            with open(web_login.marker_path(), "r", encoding="utf-8-sig") as fh:
                marker = json.load(fh)
        except Exception:
            pass
        cfg = web_sender.load_config()
        cookies = os.path.join(cfg["profile"], "Default", "Network", "Cookies")
        return {"running": running, "logged_in": os.path.exists(cookies) and bool(marker.get("ok")),
                "last": marker, "profile": cfg["profile"]}

    @router.put("/config")
    async def config_put(request: Request):
        from sugar_assistant import identity as identity_mode

        payload = await request.json()
        raw = _read_config_file()
        touched = []
        if "enabled" in payload:
            raw["enabled"] = bool(payload["enabled"])
            touched.append("enabled")
        if isinstance(payload.get("defaults"), dict):
            defaults = raw.setdefault("defaults", {})
            for key in ("workspace", "model"):
                change = payload["defaults"].get(key)
                if isinstance(change, dict):
                    entry = defaults.setdefault(key, {})
                    for field in ("mode", "path", "profile_id"):
                        if field in change:
                            entry[field] = str(change[field])
                    touched.append(f"defaults.{key}")
        if payload.get("session_scope") in {"chat", "thread", "user"}:
            raw["session_scope"] = payload["session_scope"]
            touched.append("session_scope")
        channels = raw.setdefault("channels", {})
        for name, change in (payload.get("channels") or {}).items():
            entry = channels.setdefault(name, {})
            for key in ("enabled", "quota"):
                if key in change:
                    entry[key] = change[key]
                    touched.append(f"{name}.{key}")
            for key in ("allow", "allow_groups"):
                if key in change:
                    value = change[key]
                    if isinstance(value, str):
                        value = [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
                    entry[key] = [str(item) for item in (value or [])]
                    touched.append(f"{name}.{key}")
        with open(_config_path(), "w", encoding="utf-8") as fh:
            json.dump(raw, fh, ensure_ascii=False, indent=2)
        identity_payload = payload.get("identity") or {}
        if identity_payload.get("mode") in {"bot", "user"}:
            chats = identity_payload.get("chats")
            if isinstance(chats, str):
                chats = [line.strip() for line in chats.splitlines() if line.strip()]
            identity_mode.set_mode(identity_payload["mode"], chats=chats)
            touched.append("identity")
        console().log("config_saved", fields=touched)
        return {"ok": True, "restart_required": True, "changed": touched}

    # ------------------------------------------------------------ 微信扫码登录
    @router.post("/login/wechat/start")
    async def wechat_login_start():
        if _LOGIN.get("phase") == "running":
            return _LOGIN
        script = os.path.join(str(_PLUGIN_ROOT), "sidecar", "wechat-login.mjs")
        _LOGIN.update({"phase": "starting", "qrUrl": "", "error": "", "started_at": time.time()})
        try:
            proc = await asyncio.create_subprocess_exec(
                "node", script,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                cwd=str(_PLUGIN_ROOT),
                env={**os.environ, "SUGAR_DATA_DIR": STATE_DIR},
            )
        except Exception as exc:
            _LOGIN.update({"phase": "failed", "error": str(exc)})
            return _LOGIN

        async def pump() -> None:
            assert proc.stdout is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", "ignore").strip()
                if text.startswith("http"):
                    _LOGIN.update({"phase": "running", "qrUrl": text})
                elif text.startswith("登录成功"):
                    _LOGIN.update({"phase": "succeeded", "qrUrl": ""})
                elif "登录失败" in text or "没有拿到凭据" in text:
                    _LOGIN.update({"phase": "failed", "error": text})
            code = await proc.wait()
            if _LOGIN["phase"] in {"running", "starting"}:
                _LOGIN.update({"phase": "succeeded" if code == 0 else "failed",
                               "error": "" if code == 0 else f"exit {code}"})

        asyncio.create_task(pump())
        return _LOGIN

    @router.get("/login/wechat/status")
    async def wechat_login_status():
        has_state = os.path.exists(os.path.join(STATE_DIR, "wechat-account.json"))
        return {**_LOGIN, "has_state": has_state}

    @router.post("/selftest")
    async def selftest(request: Request):
        """合成一条飞书入站，走完整链路（准入→会话→起一轮→投递回飞书）。

        用于验证真机链路：不依赖用户真的发消息，也不需要额外凭据。
        """
        import uuid

        from sugar_assistant.models import ChannelId, ConversationRef, Inbound, Principal

        service = _svc()
        if service is None:
            return JSONResponse({"ok": False, "error": "Core 未运行"}, status_code=503)
        payload = await request.json()
        text = str(payload.get("text") or "自检：在吗")
        chat_id = str(payload.get("chat_id") or "")
        principal_id = str(payload.get("principal") or "")
        if not chat_id or not principal_id:
            raw = service.runtime.sessions._store.read().get("sessions") or {}  # noqa: SLF001
            for key, value in raw.items():
                if key.startswith("feishu:"):
                    chat_id = chat_id or key.rsplit(":", 1)[-1]
                    principal_id = principal_id or str(value.get("principal") or "")
        if not chat_id:
            return JSONResponse({"ok": False, "error": "没有可用的飞书对话，请先发一条消息"}, status_code=400)
        inbound = Inbound(
            channel=ChannelId("feishu", "default"),
            conversation=ConversationRef(chat_id=chat_id, kind="p2p"),
            sender=Principal("feishu", principal_id.replace("feishu:", "") or "selftest"),
            message_id=f"selftest-{uuid.uuid4().hex[:10]}",
            text=text,
        )
        result = await service.handle(inbound)
        return {"ok": result.ok, "status": result.status, "reason": result.reason,
                "session_id": result.session_id, "chat_id": chat_id}

    @router.post("/selftest/ask")
    async def selftest_ask(request: Request):
        """造一个真实存在的 ask，让卡片真的发到飞书，用来验证"卡片 + 点击回填"整条链路。"""
        import uuid

        from human_interaction import get_human_interaction_service  # type: ignore
        from sugar_assistant.models import ChannelId, ConversationRef, Inbound, Principal

        service = _svc()
        if service is None:
            return JSONResponse({"ok": False, "error": "Core 未运行"}, status_code=503)
        runtime = service.runtime
        raw = runtime.sessions._store.read().get("sessions") or {}  # noqa: SLF001
        pick = next(((k, v) for k, v in raw.items() if k.startswith("feishu:")), None)
        if pick is None:
            return JSONResponse({"ok": False, "error": "没有绑定的飞书会话，先发一条消息"}, status_code=400)
        key, value = pick
        chat_id = key.rsplit(":", 1)[-1]
        session_id = str(value.get("session_id") or "")
        principal_id = str(value.get("principal") or "").replace("feishu:", "") or "selftest"

        iid = uuid.uuid4().hex
        question = {
            "questions": [
                {"question_id": "q1", "header": "自检 1", "question": "第一题：选一个",
                 "options": [{"option_id": "q1o1", "label": "选项一", "description": "自检选项"},
                             {"option_id": "q1o2", "label": "选项二", "description": "自检选项"}]},
                {"question_id": "q2", "header": "自检 2", "question": "第二题：选一个",
                 "options": [{"option_id": "q2o1", "label": "甲", "description": "自检选项"},
                             {"option_id": "q2o2", "label": "乙", "description": "自检选项"}]},
            ],
            "metadata": {},
        }
        record = get_human_interaction_service().create_question(
            session_id, question, run_id="selftest", tool_call_id="selftest", interaction_id=iid)
        event = {"type": "interaction_requested", "session_id": session_id,
                 "payload": {**record, "questions": record.get("questions") or question["questions"]}}
        import asyncio
        await asyncio.to_thread(service.relay.handle_event, session_id, event)
        return {"ok": True, "interaction_id": iid, "session_id": session_id, "chat_id": chat_id,
                "principal": principal_id}

    # 热重载时旧路由必须先摘掉：include_router 只追加，最先匹配的旧 handler
    # 会一直拿到旧模块的全局变量（表现为改了代码但行为不变）。
    prefix = "/api/sugar-assistant"
    app.routes[:] = [r for r in app.routes
                     if not ((getattr(r, "path", "") or "").startswith(prefix))]
    app.include_router(router)
    LOG.info("小Sugar助手：设置页接口已挂载 /api/sugar-assistant")
