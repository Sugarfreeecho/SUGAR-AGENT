"""Loopback-only, bearer-protected Responses compatibility adapter."""
from __future__ import annotations

import copy
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import threading
import time
from urllib.parse import parse_qs, urlsplit

import httpx

from .auth import Accounts, PlanError, RESOURCE
from .storage import Vault

ERROR_MESSAGES = {
    "subscription_sharing_usage_limit_exceeded": "ChatGPT 订阅额度已达上限，请到 ChatGPT 设置查看用量。",
    "subscription_sharing_usage_unavailable": "ChatGPT 订阅额度暂不可用，请检查套餐与应用授权。",
    "subscription_sharing_user_not_eligible": "当前账号或工作区不支持订阅调用。",
    "invalid_api_key": "ChatGPT 授权已失效，请重新登录。",
}


def request_body(source):
    if not isinstance(source, dict) or not isinstance(source.get("model"), str) or not source["model"]:
        raise PlanError("请求缺少 model。", "invalid_request")
    if source.get("previous_response_id"):
        raise PlanError("订阅模型必须启用“禁止服务端存储”，并发送完整历史。", "continuation_unsupported")
    # Allowlist avoids leaking unsupported/privileged fields through extra_body.
    body = {key: copy.deepcopy(source[key]) for key in (
        "model", "input", "instructions", "reasoning", "text", "include",
        "tool_choice", "parallel_tool_calls", "prompt_cache_key") if key in source}
    if isinstance(body.get("input"), str):
        body["input"] = [{"role": "user", "content": body["input"]}]
    if not isinstance(body.get("input"), list):
        raise PlanError("input 必须包含完整消息历史。", "invalid_request")
    instructions = [body.get("instructions", "")]
    inputs = []
    for item in body["input"]:
        if isinstance(item, dict) and item.get("role") == "system":
            content = item.get("content", "")
            if isinstance(content, list):
                content = "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
            instructions.append(str(content))
        else:
            inputs.append(item)
    body["input"] = inputs
    body["instructions"] = "\n\n".join(str(x) for x in instructions if x)
    tools = source.get("tools") or []
    if not isinstance(tools, list) or any(not isinstance(t, dict) or t.get("type") != "function" for t in tools):
        raise PlanError("订阅插件仅支持由 SugarAgent 执行的 function 工具。", "unsupported_tool")
    if tools:
        body["tools"] = [{"type": "namespace", "name": "sugaragent",
                          "description": "Tools executed locally by SugarAgent.", "tools": copy.deepcopy(tools)}]
        if isinstance(body.get("tool_choice"), dict):
            choice = body["tool_choice"]
            if choice.get("type") != "function":
                raise PlanError("不支持该 tool_choice。", "unsupported_tool")
            choice["namespace"] = "sugaragent"
    body.update(store=False, stream=True)
    return body


def events(response):
    """Validate SSE data even when upstream omits its Content-Type header.

    Callers still require a terminal response event before declaring success.
    """
    data, size = [], 0
    output_items = {}
    seen_event = False
    for line in response.iter_lines():
        if line == "":
            if data:
                value = "\n".join(data)
                if value != "[DONE]":
                    try:
                        event = json.loads(value)
                    except ValueError:
                        raise PlanError("OpenAI 返回了无效事件。", "invalid_upstream_stream", 502) from None
                    if not isinstance(event, dict) or not isinstance(event.get("type"), str) or not event["type"]:
                        raise PlanError("OpenAI 返回了无效事件。", "invalid_upstream_stream", 502)
                    if event["type"] == "response.output_item.done":
                        index, item = event.get("output_index"), event.get("item")
                        if type(index) is not int or index < 0 or not isinstance(item, dict):
                            raise PlanError("OpenAI 返回了无效输出项。", "invalid_upstream_stream", 502)
                        output_items[index] = item
                    elif event["type"] in {"response.completed", "response.incomplete"}:
                        final = event.get("response")
                        if not isinstance(final, dict):
                            raise PlanError("OpenAI 返回了无效完成事件。", "invalid_upstream_stream", 502)
                        # The subscription endpoint can omit final.output even
                        # after sending full output_item.done snapshots. Restore
                        # those items, preserving order, tool calls and usage.
                        if not final.get("output") and output_items:
                            final["output"] = [output_items[index] for index in sorted(output_items)]
                    seen_event = True
                    yield event
                data, size = [], 0
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
            size += len(line)
            if size > 16 * 1024 * 1024:
                raise PlanError("OpenAI 事件超出大小限制。", "upstream_event_too_large", 502)
    if data:
        # A missing SSE frame terminator is a truncated stream, even if JSON parses.
        raise PlanError("OpenAI 响应流意外中断。", "upstream_interrupted", 502)
    if not seen_event:
        raise PlanError("OpenAI 响应中没有有效事件。", "invalid_upstream_stream", 502)


def upstream_error(response):
    code = "upstream_error"
    try:
        raw = response.json().get("error", {})
        candidate = raw.get("code") if isinstance(raw, dict) else ""
        if isinstance(candidate, str) and re.fullmatch(r"[a-z0-9_]{1,100}", candidate):
            code = candidate
    except (ValueError, TypeError, AttributeError):
        pass
    return PlanError(ERROR_MESSAGES.get(code, "OpenAI 请求失败，请检查账号授权、模型和额度。"), code, response.status_code)


class Runtime:
    def __init__(self, vault=None, client=None, enabled=lambda: True):
        self.vault = vault or Vault()
        self.accounts = Accounts(self.vault, client=client)
        self.client = self.accounts.client
        self.enabled = enabled
        self.server = None
        self.thread = None
        self.lock = threading.RLock()
        self.slots = threading.BoundedSemaphore(12)

    def start(self):
        with self.lock:
            if self.server:
                return
            with self.vault.locked():
                data = self.vault.read()
                try:
                    server = ThreadingHTTPServer(("127.0.0.1", int(data.get("port", 0))), self._handler())
                except OSError:
                    raise PlanError("订阅插件的本机端口被占用；请关闭其他 SugarAgent 实例后重试。", "port_unavailable", 503) from None
                server.daemon_threads = True
                server.block_on_close = False
                data["port"] = server.server_port
                try:
                    self.vault.write(data)
                except Exception:
                    server.server_close()
                    raise
            self.server = server
            self.thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True,
                                           name="chatgpt-subscription")
            self.thread.start()

    def base_url(self, account_id):
        self.start()
        return f"http://127.0.0.1:{self.server.server_port}/accounts/{account_id}/v1"

    def sign_in(self, account_id=""):
        self.start()
        return self.accounts.begin(f"http://127.0.0.1:{self.server.server_port}/auth/callback", account_id)

    def models(self, account_id):
        token = self.accounts.access_token(account_id)
        try:
            response = self.client.get(RESOURCE + "/models", headers={"Authorization": "Bearer " + token})
            if response.status_code != 200:
                raise upstream_error(response)
            catalog = response.json().get("models")
            if not isinstance(catalog, list):
                raise PlanError("OpenAI 模型目录格式无效。", "invalid_catalog", 502)
            return [{"id": row["slug"], "name": str(row.get("display_name") or row["slug"])}
                    for row in catalog if isinstance(row, dict) and row.get("visibility") == "list"
                    and isinstance(row.get("slug"), str) and row["slug"]]
        except (httpx.HTTPError, ValueError):
            raise PlanError("获取 ChatGPT 模型失败，请检查网络后重试。", "models_unavailable", 502) from None

    def profile(self, account_id, model, name=""):
        import hashlib
        if model not in {row["id"] for row in self.models(account_id)}:
            raise PlanError("请从当前账号的模型目录中选择模型。", "model_unavailable")
        with self.vault.locked():
            key = self.vault.read()["proxy_key"]
        return {"id": "chatgpt-" + account_id + "-" + hashlib.sha256(model.encode()).hexdigest()[:10],
                "name": name or "ChatGPT · " + model + " · " + account_id[:6], "model": model,
                "llm_type": "openai-responses", "base_url": self.base_url(account_id),
                "api_key": key, "responses_store_disabled": True, "enabled": True}

    def test_model(self, account_id, model):
        """Explicit user action only: one tiny inference, never on page load."""
        if model not in {row["id"] for row in self.models(account_id)}:
            raise PlanError("请先选择当前账号的可用模型。", "model_unavailable")
        token = self.accounts.access_token(account_id)
        started = time.monotonic()
        try:
            with self.client.stream("POST", RESOURCE + "/responses",
                    headers={"Authorization": "Bearer " + token, "Accept": "text/event-stream"},
                    json={"model": model, "input": [{"role": "user", "content": "Reply with OK only."}],
                          "store": False, "stream": True}, timeout=httpx.Timeout(90, connect=30)) as upstream:
                if upstream.status_code != 200:
                    upstream.read()
                    raise upstream_error(upstream)
                for event in events(upstream):
                    if event.get("type") == "response.completed" and event.get("response", {}).get("status") == "completed":
                        return {"ok": True, "model": model, "latency_ms": round((time.monotonic() - started) * 1000)}
                    if event.get("type") in {"response.failed", "error"}:
                        error = event.get("response", {}).get("error", {}) if event.get("type") == "response.failed" else event
                        code = str(error.get("code", "upstream_error"))
                        raise PlanError(ERROR_MESSAGES.get(code, "模型调用失败，请检查账号授权和额度。"), code, 502)
                    if event.get("type") in {"response.incomplete", "response.completed"}:
                        break
        except httpx.HTTPError:
            raise PlanError("测试调用未完成，请检查网络后重试。", "upstream_unavailable", 502) from None
        raise PlanError("模型未返回完整响应，请稍后重试。", "response_incomplete", 502)

    def stop(self):
        with self.lock:
            server, self.server = self.server, None
            if server:
                server.shutdown()
                server.server_close()
                self.thread.join(timeout=2)
            self.accounts.close()

    def _handler(self):
        runtime = self

        class Handler(BaseHTTPRequestHandler):
            # HTTP/1.0 delimits SSE by closing the connection, without buffering.
            server_version = "SugarAgent-ChatGPT/1.0"

            def setup(self):
                super().setup()
                self.connection.settimeout(300)

            def log_message(self, *_args):
                pass  # Callback URLs carry one-use OAuth codes.

            def reply(self, status, body, content_type="application/json; charset=utf-8"):
                raw = json.dumps(body, ensure_ascii=False).encode() if isinstance(body, dict) else body.encode()
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(raw)

            def error_reply(self, exc):
                self.reply(exc.status, {"error": {"message": str(exc), "type": "chatgpt_subscription", "code": exc.code}})

            def check(self, callback=False):
                if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                    raise PlanError("Invalid loopback Host", "invalid_host", 403)
                if not runtime.enabled():
                    raise PlanError("ChatGPT 订阅插件已停用。", "plugin_disabled", 503)
                if not callback:
                    with runtime.vault.locked():
                        key = runtime.vault.read()["proxy_key"]
                    if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + key):
                        raise PlanError("本机适配服务需要认证。", "unauthorized", 401)

            def account_id(self, path, suffix):
                match = re.fullmatch(r"/accounts/([a-f0-9]{24})/v1/" + suffix, path)
                if not match:
                    raise PlanError("Not found", "not_found", 404)
                return match[1]

            def do_GET(self):
                try:
                    parsed = urlsplit(self.path)
                    callback = parsed.path == "/auth/callback"
                    self.check(callback=callback)
                    if callback:
                        query = parse_qs(parsed.query, keep_blank_values=True)
                        if any(len(value) != 1 for value in query.values()):
                            raise PlanError("无效的授权回调。", "invalid_callback")
                        runtime.accounts.finish({key: value[0] for key, value in query.items()})
                        self.reply(200, "<!doctype html><meta charset=utf-8><title>ChatGPT</title>授权处理完成。请关闭此页，返回 SugarAgent。", "text/html; charset=utf-8")
                    else:
                        aid = self.account_id(parsed.path, "models")
                        self.reply(200, {"object": "list", "data": [{"id": row["id"], "object": "model",
                            "owned_by": "chatgpt"} for row in runtime.models(aid)]})
                except PlanError as exc:
                    self.error_reply(exc)
                except (BrokenPipeError, ConnectionError):
                    pass
                except Exception:
                    self.error_reply(PlanError("插件内部错误，请返回 SugarAgent 重试。", "internal_error", 500))

            def do_POST(self):
                streaming = False
                acquired = False
                try:
                    self.check()
                    aid = self.account_id(urlsplit(self.path).path, "responses")
                    acquired = runtime.slots.acquire(blocking=False)
                    if not acquired:
                        raise PlanError("订阅插件并发请求过多，请稍后重试。", "local_rate_limit", 429)
                    if self.headers.get("Transfer-Encoding"):
                        raise PlanError("Unsupported transfer encoding", "invalid_request")
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                    except ValueError:
                        length = 0
                    if not 0 < length <= 32 * 1024 * 1024:
                        raise PlanError("Invalid request size", "request_too_large", 413)
                    try:
                        source = json.loads(self.rfile.read(length))
                    except (ValueError, UnicodeError):
                        raise PlanError("Invalid JSON", "invalid_request") from None
                    body = request_body(source)
                    token = runtime.accounts.access_token(aid)
                    with runtime.client.stream("POST", RESOURCE + "/responses", json=body,
                            headers={"Authorization": "Bearer " + token, "Accept": "text/event-stream"},
                            timeout=httpx.Timeout(300, connect=30)) as upstream:
                        if upstream.status_code != 200:
                            upstream.read()
                            raise upstream_error(upstream)
                        terminal = False
                        for event in events(upstream):
                            kind = event.get("type")
                            if kind == "response.completed" and event.get("response", {}).get("status") != "completed":
                                raise PlanError("OpenAI 响应状态与完成事件不一致。", "invalid_upstream_stream", 502)
                            if kind in {"response.failed", "error"}:
                                raw = event.get("response", {}).get("error", {}) if kind == "response.failed" else event
                                code = raw.get("code", "upstream_error") if isinstance(raw, dict) else "upstream_error"
                                raise PlanError(ERROR_MESSAGES.get(code, "OpenAI 响应失败，请检查账号授权和额度。"), str(code), 502)
                            # Some subscription responses contain valid SSE without
                            # a MIME header. Inspect an event before committing the
                            # downstream 200; HTML/JSON error pages must still fail.
                            if source.get("stream") and not streaming:
                                self.send_response(200)
                                self.send_header("Content-Type", "text/event-stream")
                                self.send_header("Cache-Control", "no-store")
                                self.send_header("X-Accel-Buffering", "no")
                                self.end_headers()
                                streaming = True
                            if streaming:
                                self.wfile.write(("data: " + json.dumps(event, ensure_ascii=False) + "\n\n").encode())
                                self.wfile.flush()
                            if kind in {"response.completed", "response.incomplete"}:
                                terminal = True
                                if not streaming:
                                    if kind != "response.completed" or event.get("response", {}).get("status") != "completed":
                                        raise PlanError("OpenAI 响应未完成。", "response_incomplete", 502)
                                    self.reply(200, event["response"])
                                break
                        if not terminal:
                            raise PlanError("OpenAI 响应流意外中断。", "upstream_interrupted", 502)
                except (BrokenPipeError, ConnectionError):
                    pass
                except Exception as exc:
                    if not isinstance(exc, PlanError):
                        exc = PlanError("订阅请求失败，请检查网络或重新登录。", "upstream_unavailable", 502)
                    try:
                        if streaming:
                            event = {"type": "error", "code": exc.code, "message": str(exc)}
                            self.wfile.write(("data: " + json.dumps(event, ensure_ascii=False) + "\n\n").encode())
                            self.wfile.flush()
                        else:
                            self.error_reply(exc)
                    except (BrokenPipeError, ConnectionError):
                        pass
                finally:
                    if acquired:
                        runtime.slots.release()

        return Handler
