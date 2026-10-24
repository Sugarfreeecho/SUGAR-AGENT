"""Local UI fixture. Uses real settings/plugin assets and disposable mock data."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit, parse_qs

PLUGIN = Path(__file__).resolve().parents[1]
PROJECT = PLUGIN.parents[1]
sys.path.insert(0, str(PROJECT / "app"))
from plugins.loader import load_plugin
from plugins.ui import plugin_ui_contributions

AID, BID = "a" * 24, "b" * 24
state = {"connected": True, "waiting": False, "polls": 0, "notice": True, "profiles": [],
         "requests": [], "model_error": False, "test_error": False, "account_id": AID}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def reply(self, value, content_type="application/json", status=200):
        raw = json.dumps(value, ensure_ascii=False).encode() if isinstance(value, (dict, list)) else value.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == "/host":
            return self.reply('''<!doctype html><meta charset="utf-8"><title>SugarAgent · 界面测试</title>
              <style>body{margin:0;background:#eff1f4;font:14px sans-serif}p{padding:0 20px;color:#667085}
              iframe{position:fixed;inset:35px 0 0;width:100%;height:calc(100% - 35px);border:0}</style>
              <p>SugarAgent · 界面测试（模拟账号，不使用订阅额度）</p>
              <iframe title="SugarAgent 设置" src="/settings?embedded=1#plugin:chatgpt-subscription:accounts"></iframe>''', "text/html; charset=utf-8")
        if path == "/settings":
            text = (PROJECT / "app/templates/settings_center.html").read_text(encoding="utf-8")
            return self.reply(text.replace("__SETTINGS_BOOTSTRAP__", json.dumps({"section": "general", "embedded": True}))
                .replace("__SETTINGS_ASSET_VERSION__", "preview"), "text/html; charset=utf-8")
        if path == "/plugins/chatgpt-subscription":
            return self.reply((PLUGIN / "web/index.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        if path.startswith("/plugin-assets/chatgpt-subscription/"):
            name = path.rsplit("/", 1)[-1]
            if name in {"app.js", "theme.js", "app.css"}:
                return self.reply((PLUGIN / "web/assets" / name).read_text(encoding="utf-8"), "text/css" if name.endswith(".css") else "application/javascript")
        if path.startswith("/static/settings/"):
            name = path.rsplit("/", 1)[-1]
            if name in {"core.js", "plugin_sections.js", "sections_basic.js", "sections_ext.js", "sections_ops.js", "package_import.js", "settings.css"}:
                return self.reply((PROJECT / "app/templates/static/settings" / name).read_text(encoding="utf-8"), "text/css" if name.endswith(".css") else "application/javascript")
        if path == "/static/myagent_path_picker.js":
            return self.reply((PROJECT / "app/templates/static/myagent_path_picker.js").read_text(encoding="utf-8"), "application/javascript")
        if path == "/api/extensions":
            return self.reply({"plugins": [], "ui_contributions": list(plugin_ui_contributions(load_plugin(PLUGIN)))})
        if path == "/api/model_profiles":
            return self.reply({"profiles": state["profiles"]})
        if path == "/api/chatgpt-subscription/status":
            if state["waiting"]:
                state["polls"] += 1
                if state["polls"] >= 3:
                    state["waiting"] = False
                    state["connected"] = True
                    state["notice"] = False
            login = {"state": "waiting", "message": "请在系统浏览器中完成授权。（模拟）"} if state["waiting"] else {
                "state": "connected" if state["connected"] else "idle", "account_id": AID, "message": ""}
            return self.reply({"accounts": [
                {"id": AID, "label": "demo@example.com", "connected": state["connected"], "plan_enabled": state["connected"], "renewable": True, "expires_at": 1},
                {"id": BID, "label": "second@example.com", "connected": True, "plan_enabled": True, "renewable": True, "expires_at": 1}],
                "profiles": state["profiles"], "show_plan_notice": not state["notice"], "login": login})
        if path == "/api/chatgpt-subscription/models":
            if state["model_error"]:
                return self.reply({"detail": {"message": "模型读取失败（模拟网络故障）", "code": "models_unavailable"}}, status=502)
            aid = parse_qs(parsed.query).get("account_id", [AID])[0]
            prefix = "demo" if aid == AID else "second"
            return self.reply({"models": [{"id": prefix + "-fast", "name": "Fast"},
                {"id": prefix + "-reasoning", "name": "Reasoning"}, {"id": prefix + "-vision", "name": "Vision"}]})
        if path == "/fixture/state":
            return self.reply(state)
        if path.startswith("/api/"):
            return self.reply({})
        self.send_error(404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        state["requests"].append({"path": self.path, "body": body})
        if self.path == "/fixture/state":
            state.update(body)
        elif self.path.endswith("/profiles"):
            name = body.get("name") or "ChatGPT · " + body["model"]
            profile = {"id": "fixture-" + body["account_id"] + body["model"], "name": name, "model": body["model"],
                       "account_id": body["account_id"], "enabled": True}
            state["profiles"] = [row for row in state["profiles"] if row["id"] != profile["id"]] + [profile]
            return self.reply({"profile": profile})
        elif self.path.endswith("/login"):
            state.update(waiting=True, connected=False, polls=0)
            return self.reply({"authorization_url": "https://auth.openai.com/api/accounts/authorize?fixture=1", "browser_opened": False})
        elif self.path.endswith("/logout"):
            state.update(waiting=False, connected=False)
            return self.reply({"revoked": True, "message": "已退出连接。"})
        elif self.path.endswith("/notice"):
            state["notice"] = True
        elif self.path.endswith("/cancel"):
            state["waiting"] = False
        elif self.path.endswith("/test"):
            if state["test_error"]:
                return self.reply({"detail": {"message": "订阅额度已达上限（模拟）", "code": "subscription_sharing_usage_limit_exceeded"}}, status=502)
            return self.reply({"ok": True, "latency_ms": 246, "model": body["model"]})
        self.reply({"ok": True})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    print(f"PREVIEW_URL=http://127.0.0.1:{server.server_port}/host", flush=True)
    server.serve_forever()
