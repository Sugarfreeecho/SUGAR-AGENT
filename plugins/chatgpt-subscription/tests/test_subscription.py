from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1] / "app"))
from chatgpt_plan.auth import AUTH, PLAN_SCOPE, Accounts, PlanError
from chatgpt_plan.adapter import Runtime, request_body
from chatgpt_plan.storage import Vault


@pytest.fixture
def identity():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    jwk.update(kid="test-key", use="sig", alg="RS256")

    def sign(client_id, nonce="nonce", **extra):
        return jwt.encode({"iss": AUTH, "aud": client_id, "sub": "user-one", "email": "user@example.com",
                           "iat": int(time.time()), "exp": int(time.time()) + 600,
                           "nonce": nonce, **extra}, private, algorithm="RS256", headers={"kid": "test-key"})

    def oidc(request):
        if request.url.path == "/.well-known/openid-configuration":
            return httpx.Response(200, json={"issuer": AUTH, "jwks_uri": AUTH + "/jwks",
                                           "revocation_endpoint": AUTH + "/revoke"})
        if request.url.path == "/jwks":
            return httpx.Response(200, json={"keys": [jwk]})
        raise AssertionError(f"Unexpected identity request: {request.url.path}")

    return sign, oidc


def save_account(vault, *, expires=3600, scopes=None):
    aid = "a" * 24
    with vault.locked():
        data = vault.read()
        data["accounts"][aid] = {"client_id": "oaiapp_test", "subject": "user-one", "issuer": AUTH,
            "email": "user@example.com", "access_token": "oauth-access-secret", "refresh_token": "refresh-secret",
            "id_token": "identity-secret", "scopes": [PLAN_SCOPE] if scopes is None else scopes,
            "expires_at": time.time() + expires}
        vault.write(data)
    return aid


def test_pkce_callback_and_real_signature_validation(tmp_path, identity):
    sign, oidc = identity
    requests = []
    accounts = None

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/oauth/token"):
            form = parse_qs(request.content.decode())
            assert form["client_id"] == ["oaiapp_registered"]
            assert form["redirect_uri"] == ["http://127.0.0.1:14559/auth/callback"]
            assert "client_secret" not in form
            assert form["code_verifier"] == [accounts.pending_verifier]
            return httpx.Response(200, json={"access_token": "new-access", "refresh_token": "new-refresh",
                "id_token": sign("oaiapp_registered", nonce=accounts.pending_nonce), "token_type": "Bearer",
                "expires_in": 3600, "scope": PLAN_SCOPE + " openid offline_access resource.invoke"})
        return oidc(request)

    vault = Vault(tmp_path)
    accounts = Accounts(vault, httpx.Client(transport=httpx.MockTransport(handler)))
    url = accounts.begin("http://127.0.0.1:14559/auth/callback")
    params = parse_qs(urlsplit(url).query)
    pending = accounts.pending.copy()
    accounts.pending_verifier, accounts.pending_nonce = pending["verifier"], pending["nonce"]
    assert params["client_id"] == ["dynamic_agent_client"]
    assert params["agent_name_hint"] == ["SugarAgent"]
    import base64
    assert params["code_challenge"] == [base64.urlsafe_b64encode(hashlib.sha256(pending["verifier"].encode()).digest()).rstrip(b"=").decode()]
    with pytest.raises(PlanError, match="state"):
        accounts.finish({"state": "forged", "code": "one-use", "client_id": "oaiapp_registered"})
    assert accounts.pending is not None
    accounts.finish({"state": pending["state"], "code": "one-use", "client_id": "oaiapp_registered"})
    status = accounts.public_status()
    aid = status["accounts"][0]["id"]
    assert status["accounts"][0]["plan_enabled"] is True
    serialized = json.dumps(status)
    assert all(secret not in serialized for secret in ["new-access", "new-refresh", "id_token", "proxy_key"])
    # Returning login reuses the issued client and stable host, never dynamic registration.
    returning = parse_qs(urlsplit(accounts.begin("http://127.0.0.1:14559/auth/callback", aid)).query)
    assert returning["client_id"] == ["oaiapp_registered"]
    assert returning["ext_agent_host_id"] == params["ext_agent_host_id"]
    assert "agent_name_hint" not in returning and "id_token_hint" not in returning
    accounts.close()


@pytest.mark.parametrize("change", [{"iss": "https://evil.example"}, {"aud": "another-client"},
                                   {"nonce": "forged"}, {"exp": 1}, {"azp": "another-client"}])
def test_identity_claims_fail_closed(tmp_path, identity, change):
    sign, oidc = identity
    accounts = Accounts(Vault(tmp_path), httpx.Client(transport=httpx.MockTransport(oidc)))
    token = sign("oaiapp_test", **change)
    with pytest.raises(PlanError) as error:
        accounts.verify_identity(token, "oaiapp_test", nonce="nonce")
    assert error.value.code == "invalid_identity"
    accounts.close()


def test_tampered_signature_rejected(tmp_path, identity):
    sign, oidc = identity
    accounts = Accounts(Vault(tmp_path), httpx.Client(transport=httpx.MockTransport(oidc)))
    token = sign("oaiapp_test")
    head, body, signature = token.split(".")
    token = head + "." + body + "." + ("A" if signature[0] != "A" else "B") + signature[1:]
    with pytest.raises(PlanError):
        accounts.verify_identity(token, "oaiapp_test", nonce="nonce")
    accounts.close()


def test_refresh_is_serialized_and_rotated_atomically(tmp_path):
    calls = []

    def handler(request):
        calls.append(parse_qs(request.content.decode()))
        time.sleep(0.03)
        return httpx.Response(200, json={"access_token": "rotated-access", "refresh_token": "rotated-refresh",
                                        "token_type": "Bearer", "expires_in": 3600})

    vault = Vault(tmp_path)
    accounts = Accounts(vault, httpx.Client(transport=httpx.MockTransport(handler)))
    aid = save_account(vault, expires=-1)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: accounts.access_token(aid), range(6)))
    assert results == ["rotated-access"] * 6
    assert len(calls) == 1 and "scope" not in calls[0]
    assert calls[0]["refresh_token"] == ["refresh-secret"]
    with vault.locked():
        row = vault.read()["accounts"][aid]
        assert row["refresh_token"] == "rotated-refresh" and PLAN_SCOPE in row["scopes"]
    accounts.close()


def test_refresh_is_serialized_across_separate_vault_instances(tmp_path):
    calls = []

    def handler(request):
        calls.append(request)
        time.sleep(0.05)
        return httpx.Response(200, json={"access_token": "rotated", "refresh_token": "rotated-refresh",
                                        "token_type": "Bearer", "expires_in": 3600})

    first = Accounts(Vault(tmp_path), httpx.Client(transport=httpx.MockTransport(handler)))
    second = Accounts(Vault(tmp_path), httpx.Client(transport=httpx.MockTransport(handler)))
    aid = save_account(first.vault, expires=-1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda account: account.access_token(aid), [first, second]))
    assert results == ["rotated", "rotated"] and len(calls) == 1
    first.close()
    second.close()


def test_identity_only_login_cannot_infer_and_invalid_grant_clears_tokens(tmp_path):
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(400, json={"error": "invalid_grant"})))
    vault = Vault(tmp_path)
    accounts = Accounts(vault, client)
    aid = save_account(vault, scopes=["openid"])
    with pytest.raises(PlanError) as error:
        accounts.access_token(aid)
    assert error.value.code == "plan_not_enabled"
    save_account(vault, expires=-1)
    with pytest.raises(PlanError):
        accounts.access_token(aid)
    with vault.locked():
        row = vault.read()["accounts"][aid]
        assert "access_token" not in row and "refresh_token" not in row
        assert row["client_id"] == "oaiapp_test"
    accounts.close()


def test_code_exchange_failure_retains_client_registration(tmp_path):
    accounts = Accounts(Vault(tmp_path), httpx.Client(transport=httpx.MockTransport(
        lambda req: httpx.Response(400, json={"error": "invalid_grant"}))))
    accounts.begin("http://127.0.0.1:14559/auth/callback")
    with pytest.raises(PlanError):
        accounts.finish({"state": accounts.pending["state"], "code": "expired", "client_id": "oaiapp_retained"})
    with accounts.vault.locked():
        assert next(iter(accounts.vault.read()["accounts"].values()))["client_id"] == "oaiapp_retained"
    accounts.close()


def test_signout_clears_secrets_even_if_remote_revocation_fails(tmp_path, identity):
    _, oidc = identity

    def handler(request):
        if request.url.path == "/revoke":
            return httpx.Response(503)
        return oidc(request)

    vault = Vault(tmp_path)
    accounts = Accounts(vault, httpx.Client(transport=httpx.MockTransport(handler)))
    aid = save_account(vault)
    result = accounts.sign_out(aid)
    assert result["revoked"] is False and "未确认" in result["message"]
    with vault.locked():
        assert all(key not in vault.read()["accounts"][aid] for key in ("access_token", "refresh_token", "id_token"))
    accounts.close()


def test_request_contract_namespaces_and_full_history():
    source = {"model": "account-model", "store": True, "stream": False, "temperature": 0.7,
        "max_output_tokens": 1000, "metadata": {"secret": "local"},
        "input": [{"role": "system", "content": "Follow instructions"}, {"role": "user", "content": "hello"}],
        "tools": [{"type": "function", "name": "run_shell", "parameters": {"type": "object"}}],
        "tool_choice": {"type": "function", "name": "run_shell"}}
    body = request_body(source)
    assert body["store"] is False and body["stream"] is True
    assert all(key not in body for key in ("temperature", "max_output_tokens", "metadata"))
    assert body["instructions"] == "Follow instructions" and len(body["input"]) == 1
    assert body["tools"][0]["type"] == "namespace"
    assert body["tool_choice"]["namespace"] == "sugaragent"
    assert source["tools"][0]["type"] == "function"  # no mutation of host history
    with pytest.raises(PlanError):
        request_body({**source, "previous_response_id": "suffix-only"})
    with pytest.raises(PlanError):
        request_body({**source, "tools": [{"type": "tool_search"}]})


def sse(*values):
    return "".join("data: " + json.dumps(value) + "\n\n" for value in values)


@pytest.fixture
def proxy(tmp_path):
    captured = []
    output = {"id": "resp_test", "object": "response", "status": "completed", "model": "test-model",
        "output": [{"type": "message", "id": "msg_test", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": "Hello", "annotations": []}]}],
        "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}}
    state = {"events": sse({"type": "response.output_text.delta", "delta": "Hello"},
                            {"type": "response.completed", "response": output})}

    def handler(request):
        captured.append(request)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"models": [
                {"slug": "test-model", "display_name": "Test Model", "visibility": "list"},
                {"slug": "hidden-model", "visibility": "hidden"}]})
        assert request.url.path == "/v1/responses"
        assert request.headers["Authorization"] == "Bearer oauth-access-secret"
        return httpx.Response(state.get("status", 200), content=state["events"],
                              headers=state.get("headers", {"content-type": "text/event-stream"}))

    runtime = Runtime(Vault(tmp_path), httpx.Client(transport=httpx.MockTransport(handler)))
    aid = save_account(runtime.vault)
    runtime.start()
    with runtime.vault.locked():
        key = runtime.vault.read()["proxy_key"]
    client = httpx.Client(base_url=runtime.base_url(aid), headers={"Authorization": "Bearer " + key}, trust_env=False)
    try:
        yield runtime, aid, client, captured, state, output
    finally:
        client.close()
        runtime.stop()


def test_loopback_auth_host_and_disable_checks(proxy):
    runtime, aid, client, captured, _, _ = proxy
    url = runtime.base_url(aid) + "/responses"
    request = {"model": "test-model", "input": "hi", "stream": True}
    assert httpx.post(url, json=request, trust_env=False).status_code == 401
    assert client.post("responses", json=request, headers={"Host": "evil.example"}).status_code == 403
    runtime.enabled = lambda: False
    assert client.post("responses", json=request).status_code == 503
    assert not captured


def test_proxy_stream_and_nonstream_summary_keep_usage(proxy):
    _, _, client, captured, _, output = proxy
    response = client.post("responses", json={"model": "test-model", "input": "hi", "stream": True,
                                             "store": True, "max_output_tokens": 100})
    assert response.status_code == 200 and "response.completed" in response.text
    body = json.loads(captured[-1].content)
    assert body["stream"] is True and body["store"] is False and "max_output_tokens" not in body
    summary = client.post("responses", json={"model": "test-model", "input": "title", "stream": False})
    assert summary.json() == output
    assert json.loads(captured[-1].content)["stream"] is True


@pytest.mark.parametrize("headers", [{}, {"Content-Type": "application/octet-stream"},
                                     {"Content-Type": "Text/Event-Stream; charset=utf-8"}])
def test_valid_sse_is_recognized_by_events_instead_of_mime_header(proxy, headers):
    _, _, client, _, state, output = proxy
    state["headers"] = headers
    request = {"model": "test-model", "input": "hi"}
    streamed = client.post("responses", json={**request, "stream": True})
    assert streamed.status_code == 200
    assert streamed.headers["content-type"] == "text/event-stream"
    assert "response.completed" in streamed.text and '"delta": "Hello"' in streamed.text
    assert '"type": "error"' not in streamed.text
    summary = client.post("responses", json={**request, "stream": False})
    assert summary.status_code == 200 and summary.json() == output


@pytest.mark.parametrize("stream", [True, False])
@pytest.mark.parametrize("body", ["", "<html>untrusted upstream detail</html>",
    json.dumps({"error": {"message": "untrusted upstream detail"}}),
    sse([]), sse({}), sse({"type": 1}), "data: invalid\n\n", "data: [DONE]\n\n"])
def test_headerless_invalid_bodies_remain_errors_before_stream_starts(proxy, stream, body):
    runtime, aid, client, _, state, _ = proxy
    state.update(headers={}, events=body)
    result = client.post("responses", json={"model": "test-model", "input": "hi", "stream": stream})
    assert result.status_code == 502
    assert result.json()["error"]["code"] == "invalid_upstream_stream"
    assert "untrusted upstream detail" not in result.text
    with pytest.raises(PlanError) as error:
        runtime.test_model(aid, "test-model")
    assert error.value.code == "invalid_upstream_stream"


def test_truncated_and_failed_stream_never_succeed(proxy):
    _, _, client, _, state, _ = proxy
    state["headers"] = {}
    state["events"] = sse({"type": "response.output_text.delta", "delta": "partial"})
    request = {"model": "test-model", "input": "hi", "stream": True}
    streamed = client.post("responses", json=request)
    assert '"type": "error"' in streamed.text and "upstream_interrupted" in streamed.text
    assert "response.completed" not in streamed.text
    assert client.post("responses", json={**request, "stream": False}).status_code == 502
    state["events"] = sse({"type": "response.failed", "response": {"error": {
        "code": "subscription_sharing_usage_limit_exceeded", "message": "untrusted detail"}}})
    failure = client.post("responses", json=request)
    assert "subscription_sharing_usage_limit_exceeded" in failure.text
    assert "untrusted detail" not in failure.text


def test_malformed_terminal_status_and_partial_sse_frames_fail(proxy):
    _, _, client, _, state, output = proxy
    state["headers"] = {}
    request = {"model": "test-model", "input": "hi", "stream": True}
    state["events"] = sse({"type": "response.completed", "response": {**output, "status": "in_progress"}})
    assert "invalid_upstream_stream" in client.post("responses", json=request).text
    state["events"] = 'data: {"type":"response.completed"}'
    assert "upstream_interrupted" in client.post("responses", json=request).text


@pytest.mark.parametrize("headers", [{}, {"content-type": "text/event-stream"}])
@pytest.mark.parametrize("omit_terminal_output", [True, False])
def test_real_host_responses_transport_tool_round_trip(proxy, headers, omit_terminal_output):
    from openai import OpenAI
    from llm.transport import OpenAIResponsesTransport
    runtime, aid, client, captured, state, output = proxy
    state["headers"] = headers
    openai_client = OpenAI(base_url=runtime.base_url(aid), api_key=client.headers["Authorization"][7:],
                           http_client=httpx.Client(trust_env=False), max_retries=0)
    transport = OpenAIResponsesTransport(openai_client, base_url=runtime.base_url(aid),
                                         storage_disabled=True, websocket_mode="disabled")
    call = {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "run_shell",
            "namespace": "sugaragent", "arguments": '{"command":"pwd"}', "status": "completed"}
    state["events"] = sse({"type": "response.output_item.added", "output_index": 0, "item": call},
                          {"type": "response.output_item.done", "output_index": 0, "item": call},
                          {"type": "response.completed", "response": {**output, "output": [] if omit_terminal_output else [call]}})
    results = list(transport.stream_completion(model="test-model", messages=[{"role": "user", "content": "where"}],
        tools=[{"type": "function", "function": {"name": "run_shell", "parameters": {"type": "object"}}}], max_tokens=100))
    assert any(row.kind == "tool_call_delta" and row.tool_name == "run_shell" for row in results)
    assert any(row.kind == "finish" and row.finish_reason == "tool_calls" for row in results)
    state["events"] = sse({"type": "response.output_item.done", "output_index": 0, "item": output["output"][0]},
                          {"type": "response.completed", "response": {**output, "output": []} if omit_terminal_output else output})
    followup = list(transport.stream_completion(model="test-model", max_tokens=100, messages=[
        {"role": "user", "content": "where"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "call_1", "type": "function",
          "function": {"name": "run_shell", "arguments": '{"command":"pwd"}'}}]},
        {"role": "tool", "tool_call_id": "call_1", "content": "/workspace"}]))
    sent = json.loads(captured[-1].content)
    assert any(item.get("type") == "function_call_output" and item["call_id"] == "call_1" for item in sent["input"])
    assert any(item.get("type") == "function_call" and item["name"] == "run_shell" for item in sent["input"])
    assert "previous_response_id" not in sent
    assert any(row.kind == "finish" and row.finish_reason == "stop" for row in followup)
    assert "".join(row.text for row in followup if row.kind == "content_delta") == "Hello"
    summary = transport.complete_text(model="test-model", messages=[{"role": "user", "content": "title"}], max_tokens=100)
    assert summary["text"] == "Hello" and summary["usage"]["completion_tokens"] == 2
    openai_client.close()


def test_empty_terminal_output_restores_completed_snapshots_in_output_order(proxy):
    _, _, client, _, state, output = proxy
    reasoning = {"id": "rs_1", "type": "reasoning", "summary": []}
    state.update(headers={}, events=sse(
        {"type": "response.output_item.done", "output_index": 1, "item": output["output"][0]},
        {"type": "response.output_item.done", "output_index": 0, "item": reasoning},
        {"type": "response.completed", "response": {**output, "output": []}}))
    request = {"model": "test-model", "input": "hi"}
    expected = {**output, "output": [reasoning, *output["output"]]}
    result = client.post("responses", json={**request, "stream": False})
    assert result.status_code == 200 and result.json() == expected
    streamed = client.post("responses", json={**request, "stream": True})
    frames = [json.loads(line[6:]) for line in streamed.text.splitlines() if line.startswith("data: ")]
    assert frames[-1]["response"] == expected
    # Explicit terminal output remains authoritative.
    state["events"] = sse(
        {"type": "response.output_item.done", "output_index": 0, "item": reasoning},
        {"type": "response.completed", "response": output})
    assert client.post("responses", json={**request, "stream": False}).json() == output
    # Completed items alone cannot turn a truncated stream into a success.
    state["events"] = sse({"type": "response.output_item.done", "output_index": 0, "item": output["output"][0]})
    truncated = client.post("responses", json={**request, "stream": False})
    assert truncated.status_code == 502 and truncated.json()["error"]["code"] == "upstream_interrupted"


def test_profile_uses_only_local_key_and_current_account_catalog(proxy):
    runtime, aid, client, _, _, _ = proxy
    profile = runtime.profile(aid, "test-model")
    assert profile["api_key"] == client.headers["Authorization"][7:]
    assert "oauth-access-secret" not in json.dumps(profile)
    assert profile["base_url"].endswith("/accounts/" + aid + "/v1")
    assert profile["responses_store_disabled"] is True
    assert runtime.profile(aid, "test-model")["id"] == profile["id"]
    with pytest.raises(PlanError):
        runtime.profile(aid, "hidden-model")


def load_host():
    name = "chatgpt_subscription_test_host"
    spec = importlib.util.spec_from_file_location(name, ROOT / "host.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_plugin_manifest_settings_and_host_api_origin(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from plugins.loader import load_plugin
    from plugins.ui import plugin_ui_contributions
    from plugins.host import is_bundled_trusted_host_plugin
    plugin = load_plugin(ROOT)
    assert plugin.compatibility.status == "native"
    assert is_bundled_trusted_host_plugin(plugin)
    assert any(row["slot"] == "settings.section" for row in plugin_ui_contributions(plugin))
    host = load_host()
    monkeypatch.setattr(host, "_enabled", lambda: True)
    runtime = Runtime(Vault(tmp_path))
    aid = save_account(runtime.vault)
    monkeypatch.setattr(host, "_get_runtime", lambda: runtime)
    monkeypatch.setattr(host, "PlanError", PlanError)
    app = FastAPI()
    host.install(app, {"project_root": tmp_path}, plugin)
    client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))
    response = client.get("/api/chatgpt-subscription/status")
    assert response.status_code == 200 and response.json()["accounts"][0]["id"] == aid
    assert "oauth-access-secret" not in response.text and "refresh-secret" not in response.text
    assert client.post("/api/chatgpt-subscription/cancel", json={}).status_code == 403
    assert client.post("/api/chatgpt-subscription/cancel", json={}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/chatgpt-subscription/cancel", json={}, headers={"Origin": "http://127.0.0.1"}).status_code == 200
    assert client.get("/api/chatgpt-subscription/status", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/chatgpt-subscription/status", headers={"Host": "evil.example"}).status_code == 403
    runtime.stop()


def test_plugin_reload_replaces_previous_settings_routes(tmp_path, monkeypatch):
    import model_profiles
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from types import SimpleNamespace

    monkeypatch.setattr(model_profiles, "load_store", lambda _: {"profiles": []})
    app = FastAPI()

    @app.get("/api/chatgpt-subscription-extra")
    def unrelated():
        return {"preserved": True}

    client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))
    for generation in ("previous", "current"):
        host = load_host()
        runtime = SimpleNamespace(accounts=SimpleNamespace(
            public_status=lambda value=generation: {"accounts": [], "generation": value}))
        monkeypatch.setattr(host, "_enabled", lambda: True)
        monkeypatch.setattr(host, "_get_runtime", lambda value=runtime: value)
        host.install(app, {"project_root": tmp_path}, None)
        result = client.get("/api/chatgpt-subscription/status")
        assert result.status_code == 200 and result.json()["generation"] == generation
    paths = [route.path for route in app.routes if route.path.startswith("/api/chatgpt-subscription/")]
    assert len(paths) == len(set(paths))
    assert client.get("/api/chatgpt-subscription-extra").json() == {"preserved": True}


def test_host_profile_creation_uses_real_profile_validation_without_exposing_key(proxy, tmp_path, monkeypatch):
    import copy
    import model_profiles
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    runtime, aid, _, _, _, _ = proxy
    host = load_host()
    monkeypatch.setattr(host, "_enabled", lambda: True)
    monkeypatch.setattr(host, "_get_runtime", lambda: runtime)
    store = {"profiles": []}
    monkeypatch.setattr(model_profiles, "load_store", lambda root: copy.deepcopy(store))
    monkeypatch.setattr(model_profiles, "save_store", lambda root, data: store.update(copy.deepcopy(data)))
    app = FastAPI()
    host.install(app, {"project_root": tmp_path}, None)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as browser:
        result = browser.post("/api/chatgpt-subscription/profiles", json={"account_id": aid, "model": "test-model"},
                              headers={"Origin": "http://127.0.0.1"})
    assert result.status_code == 200
    profile = result.json()["profile"]
    assert profile["usable"] and profile["responses_store_disabled"]
    assert "api_key" not in profile and "oauth-access-secret" not in result.text
    assert store["profiles"][0]["api_key"] != "oauth-access-secret"


def test_custom_names_saved_profile_status_and_notice_are_private(proxy, tmp_path, monkeypatch):
    import copy
    import model_profiles
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    runtime, aid, _, _, _, _ = proxy
    host = load_host()
    monkeypatch.setattr(host, "_enabled", lambda: True)
    monkeypatch.setattr(host, "_get_runtime", lambda: runtime)
    store = {"profiles": []}
    monkeypatch.setattr(model_profiles, "load_store", lambda root: copy.deepcopy(store))
    monkeypatch.setattr(model_profiles, "save_store", lambda root, data: store.update(copy.deepcopy(data)))
    app = FastAPI()
    host.install(app, {"project_root": tmp_path}, None)
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)) as browser:
        origin = {"Origin": "http://127.0.0.1"}
        first = browser.post("/api/chatgpt-subscription/profiles", json={"account_id": aid, "model": "test-model", "name": "我的订阅模型"}, headers=origin)
        assert first.status_code == 200 and first.json()["profile"]["name"] == "我的订阅模型"
        status = browser.get("/api/chatgpt-subscription/status")
        row = status.json()["profiles"][0]
        assert row["account_id"] == aid and row["name"] == "我的订阅模型"
        assert "api_key" not in row and "oauth-access-secret" not in status.text
        assert status.json()["show_plan_notice"] is True
        assert browser.post("/api/chatgpt-subscription/notice", json={}, headers=origin).status_code == 200
        assert browser.get("/api/chatgpt-subscription/status").json()["show_plan_notice"] is False
        bad = browser.post("/api/chatgpt-subscription/profiles", json={"name": "x" * 81}, headers=origin)
        assert bad.status_code == 422


@pytest.mark.parametrize("headers", [{}, {"content-type": "text/event-stream"}])
def test_explicit_model_test_uses_one_inference_and_requires_completed_event(proxy, headers):
    runtime, aid, _, captured, state, _ = proxy
    state["headers"] = headers
    result = runtime.test_model(aid, "test-model")
    assert result["ok"] and result["latency_ms"] >= 0
    inference = [row for row in captured if row.url.path.endswith("/responses")]
    assert len(inference) == 1
    body = json.loads(inference[0].content)
    assert body["store"] is False and body["stream"] is True and "tools" not in body
    state["events"] = sse({"type": "response.output_text.delta", "delta": "partial"})
    with pytest.raises(PlanError) as error:
        runtime.test_model(aid, "test-model")
    assert error.value.code == "response_incomplete"


def test_stable_port_is_restored_after_plugin_restart(tmp_path):
    first = Runtime(Vault(tmp_path))
    first.start()
    port = first.server.server_port
    first.stop()
    second = Runtime(Vault(tmp_path))
    second.start()
    try:
        assert second.server.server_port == port
    finally:
        second.stop()


def test_protected_storage_and_stable_host_identity(tmp_path):
    vault = Vault(tmp_path)
    with vault.locked():
        data = vault.read()
        vault.write(data)
    with Vault(tmp_path).locked():
        again = Vault(tmp_path).read()
    assert again["host_id"] == data["host_id"] and again["proxy_key"] == data["proxy_key"]
    import os
    if os.name == "nt":
        assert data["proxy_key"] not in vault.path.read_text()
        assert json.loads(vault.path.read_text())["protection"] == "windows-dpapi"
    else:
        assert vault.path.stat().st_mode & 0o777 == 0o600
        assert tmp_path.stat().st_mode & 0o777 == 0o700
