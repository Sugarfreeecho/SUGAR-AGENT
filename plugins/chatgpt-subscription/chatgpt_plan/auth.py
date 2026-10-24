"""Sign in with ChatGPT public-client OAuth; no Codex credential reuse."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from urllib.parse import urlencode, urlsplit

import httpx

AUTH = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
SCOPES = "openid profile email offline_access resource.invoke " + PLAN_SCOPE


class PlanError(Exception):
    def __init__(self, message: str, code: str = "chatgpt_error", status: int = 400):
        super().__init__(message)
        self.code, self.status = code, status


def official_url(value: str) -> str:
    if not isinstance(value, str):
        raise PlanError("OpenAI 身份服务元数据无效。", "invalid_metadata", 502)
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.netloc != "auth.openai.com" or parsed.fragment:
        raise PlanError("OpenAI 身份服务元数据无效。", "invalid_metadata", 502)
    return value


class Accounts:
    def __init__(self, vault, client=None, clock=time.time):
        self.vault = vault
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)
        self.clock = clock
        self.pending = None
        self.login_status = {"state": "idle", "message": ""}
        self.login_lock = threading.RLock()
        self.metadata = None
        with vault.locked():
            vault.write(vault.read())

    def _json(self, method, url, **kwargs):
        try:
            response = self.client.request(method, url, **kwargs)
            if response.status_code >= 400:
                # Never reflect OAuth bodies, URLs, codes or tokens in errors.
                code = "oauth_request_failed"
                try:
                    candidate = response.json().get("error")
                    if candidate in {"invalid_grant", "invalid_client", "access_denied"}:
                        code = candidate
                except (ValueError, TypeError):
                    pass
                raise PlanError("OpenAI 授权失败，请重新登录。", code, 401)
            value = response.json()
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (httpx.HTTPError, ValueError):
            raise PlanError("无法连接 OpenAI 身份服务，请检查网络后重试。", "auth_unavailable", 502) from None

    def discovery(self):
        if self.metadata is None:
            metadata = self._json("GET", AUTH + "/.well-known/openid-configuration")
            if metadata.get("issuer") != AUTH:
                raise PlanError("OpenAI 身份服务 issuer 无效。", "invalid_metadata", 502)
            official_url(metadata.get("jwks_uri", ""))
            official_url(metadata.get("revocation_endpoint", ""))
            self.metadata = metadata
        return self.metadata

    def verify_identity(self, token, client_id, nonce=None):
        try:
            import jwt
        except ImportError:
            raise PlanError("缺少 PyJWT[crypto]，请先安装插件 requirements.txt。", "missing_dependency", 503) from None
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in {"RS256", "ES256"}:
                raise ValueError()
            keys = self._json("GET", official_url(self.discovery()["jwks_uri"]))
            key = next(k for k in keys.get("keys", []) if k.get("kid") == header.get("kid")
                       and k.get("use", "sig") == "sig")
            claims = jwt.decode(token, jwt.PyJWK.from_dict(key).key,
                                algorithms=[header["alg"]], audience=client_id, issuer=AUTH,
                                options={"require": ["exp", "iat", "iss", "aud", "sub"]}, leeway=30)
            if not isinstance(claims.get("sub"), str) or not claims["sub"]:
                raise ValueError()
            if nonce is not None and not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
                raise ValueError()
            if claims.get("azp", client_id) != client_id:
                raise ValueError()
            if isinstance(claims["aud"], list) and len(claims["aud"]) > 1 and claims.get("azp") != client_id:
                raise ValueError()
            return claims
        except PlanError:
            raise
        except Exception:
            raise PlanError("ChatGPT 身份验证失败，未保存新凭据。", "invalid_identity", 401) from None

    def public_status(self):
        with self.vault.locked():
            data = self.vault.read()
            accounts = [{"id": aid, "label": row.get("email") or row.get("subject") or "待完成注册",
                         "connected": bool(row.get("access_token")),
                         "plan_enabled": bool(row.get("access_token")) and PLAN_SCOPE in row.get("scopes", []),
                         "renewable": bool(row.get("refresh_token")),
                         "expires_at": row.get("expires_at", 0)} for aid, row in data["accounts"].items()]
            show_notice = not data.get("plan_notice_acknowledged", False) and any(row["plan_enabled"] for row in accounts)
        with self.login_lock:
            if self.pending and self.pending["expires_at"] <= self.clock():
                self.pending = None
                self.login_status = {"state": "expired", "message": "登录已超时，请重新开始。"}
            login = dict(self.login_status)
            if self.pending:
                login["expires_at"] = self.pending["expires_at"]
            return {"accounts": accounts, "login": login, "show_plan_notice": show_notice}

    def acknowledge_plan_notice(self):
        with self.vault.locked():
            data = self.vault.read()
            data["plan_notice_acknowledged"] = True
            self.vault.write(data)

    def begin(self, redirect_uri, account_id=""):
        # Lazy dependency check before opening a browser.
        try:
            import jwt  # noqa: F401
            import cryptography  # noqa: F401
        except ImportError:
            raise PlanError("请先安装插件 requirements.txt 中的 PyJWT[crypto]。", "missing_dependency", 503) from None
        with self.login_lock, self.vault.locked():
            data = self.vault.read()
            selected = data["accounts"].get(account_id) if account_id else None
            if account_id and selected is None:
                raise PlanError("找不到该账号。", "account_not_found", 404)
            verifier = secrets.token_urlsafe(48)
            pending = {"state": secrets.token_urlsafe(32), "nonce": secrets.token_urlsafe(32),
                       "verifier": verifier, "redirect_uri": redirect_uri,
                       "account_id": account_id, "client_id": selected["client_id"] if selected else "",
                       "expires_at": self.clock() + 600}
            params = {"client_id": pending["client_id"] or "dynamic_agent_client",
                      "ext_agent_host_id": data["host_id"], "response_type": "code",
                      "redirect_uri": redirect_uri, "scope": SCOPES, "resource": RESOURCE,
                      "state": pending["state"], "nonce": pending["nonce"], "code_challenge_method": "S256",
                      "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()}
            if selected:
                if selected.get("email"):
                    params["login_hint"] = selected["email"]
            else:
                params["agent_name_hint"] = "SugarAgent"
            self.pending = pending
            self.login_status = {"state": "waiting", "message": "请在系统浏览器完成 ChatGPT 授权。"}
            return AUTH + "/api/accounts/authorize?" + urlencode(params)

    def finish(self, query):
        with self.login_lock:
            pending = self.pending
            if not pending or self.clock() >= pending["expires_at"]:
                raise PlanError("登录已超时，请重新开始。", "login_expired")
            if not hmac.compare_digest(str(query.get("state", "")), pending["state"]):
                raise PlanError("登录 state 不匹配。", "invalid_state")
            # A valid callback is one-use, including user-declined callbacks.
            self.pending = None
            try:
                if query.get("error"):
                    raise PlanError("你取消了 ChatGPT 授权。", "access_denied")
                client_id = str(query.get("client_id") or pending["client_id"])
                if not client_id or client_id == "dynamic_agent_client" or (
                    pending["client_id"] and client_id != pending["client_id"]
                ):
                    raise PlanError("授权返回的 client_id 无效。", "invalid_client")
                account_id = pending["account_id"] or hashlib.sha256(client_id.encode()).hexdigest()[:24]
                # Retain registration even if the one-use code exchange fails.
                with self.vault.locked():
                    data = self.vault.read()
                    old = data["accounts"].get(account_id, {})
                    data["accounts"][account_id] = {**old, "client_id": client_id}
                    self.vault.write(data)
                if not query.get("code"):
                    raise PlanError("授权返回缺少 code。", "missing_code")
                tokens = self._json("POST", AUTH + "/api/accounts/oauth/token", data={
                    "grant_type": "authorization_code", "client_id": client_id,
                    "code": query["code"], "code_verifier": pending["verifier"],
                    "redirect_uri": pending["redirect_uri"], "resource": RESOURCE})
                claims = self.verify_identity(tokens.get("id_token", ""), client_id, pending["nonce"])
                with self.vault.locked():
                    data = self.vault.read()
                    old = data["accounts"].get(account_id, {})
                    if old.get("subject") and old["subject"] != claims["sub"]:
                        raise PlanError("登录账号与已保存身份不一致。", "account_mismatch", 401)
                    row = {**old, "issuer": AUTH, "subject": claims["sub"], "email": claims.get("email", "")}
                    self._update_tokens(row, tokens, initial=True)
                    data["accounts"][account_id] = row
                    self.vault.write(data)
                enabled = PLAN_SCOPE in row["scopes"]
                self.login_status = {"state": "connected", "account_id": account_id,
                    "message": "ChatGPT 订阅已连接。" if enabled else "账号已登录，但未授权使用订阅额度。"}
            except PlanError as exc:
                self.login_status = {"state": "error", "message": str(exc)}
                raise

    def cancel(self):
        with self.login_lock:
            self.pending = None
            self.login_status = {"state": "idle", "message": "已取消登录。"}

    def _update_tokens(self, row, tokens, initial=False):
        if str(tokens.get("token_type", "")).lower() != "bearer" or not tokens.get("access_token"):
            raise PlanError("OpenAI 返回了无效的令牌。", "invalid_token_response", 502)
        try:
            expires = int(tokens["expires_in"])
            if expires <= 0:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise PlanError("OpenAI 返回了无效的令牌有效期。", "invalid_token_response", 502) from None
        if initial and not tokens.get("refresh_token"):
            raise PlanError("未取得可续期授权，请重新登录。", "missing_refresh_token", 401)
        for key in ("access_token", "refresh_token", "id_token"):
            if tokens.get(key):
                row[key] = tokens[key]
        if "scope" in tokens or initial:
            row["scopes"] = str(tokens.get("scope", "")).split()
        row["expires_at"] = self.clock() + expires

    def access_token(self, account_id):
        with self.vault.locked():
            data = self.vault.read()
            row = data["accounts"].get(account_id)
            if not row or not row.get("access_token"):
                raise PlanError("请先连接 ChatGPT 账号。", "not_connected", 401)
            if PLAN_SCOPE not in row.get("scopes", []):
                raise PlanError("该账号尚未授权使用订阅额度。", "plan_not_enabled", 403)
            if row.get("expires_at", 0) <= self.clock() + 60:
                if not row.get("refresh_token"):
                    raise PlanError("登录已过期，请重新登录。", "reauth_required", 401)
                try:
                    tokens = self._json("POST", AUTH + "/api/accounts/oauth/token", data={
                        "grant_type": "refresh_token", "client_id": row["client_id"],
                        "refresh_token": row["refresh_token"], "resource": RESOURCE})
                    if tokens.get("id_token"):
                        claims = self.verify_identity(tokens["id_token"], row["client_id"])
                        if claims["sub"] != row["subject"]:
                            raise PlanError("续期返回的身份不一致。", "account_mismatch", 401)
                    self._update_tokens(row, tokens)
                except PlanError as exc:
                    if exc.code in {"invalid_grant", "invalid_client", "account_mismatch"}:
                        for key in ("access_token", "refresh_token", "id_token"):
                            row.pop(key, None)
                        self.vault.write(data)
                    raise
                self.vault.write(data)
                if PLAN_SCOPE not in row.get("scopes", []):
                    raise PlanError("订阅调用授权已撤销，请重新登录。", "plan_not_enabled", 403)
            return row["access_token"]

    def sign_out(self, account_id):
        # Cancel a pending reauthorization so its late callback cannot sign back in.
        self.cancel()
        with self.vault.locked():
            data = self.vault.read()
            row = data["accounts"].get(account_id)
            if not row:
                raise PlanError("找不到该账号。", "account_not_found", 404)
            confirmed = not bool(row.get("refresh_token"))
            if row.get("refresh_token"):
                try:
                    endpoint = official_url(self.discovery()["revocation_endpoint"])
                    for attempt in range(2):
                        try:
                            response = self.client.post(endpoint, data={"token": row["refresh_token"],
                                "token_type_hint": "refresh_token", "client_id": row["client_id"]})
                            if response.status_code == 200:
                                confirmed = True
                                break
                            if response.status_code < 500:
                                break
                        except httpx.HTTPError:
                            pass
                        if attempt == 0:
                            time.sleep(0.2)
                except (httpx.HTTPError, PlanError):
                    pass
            for key in ("access_token", "refresh_token", "id_token"):
                row.pop(key, None)
            self.vault.write(data)
            return {"revoked": confirmed, "message": "已退出登录。" if confirmed else
                    "本地已退出，远程撤销未确认；请在 ChatGPT 设置中断开此应用。"}

    def close(self):
        self.cancel()
        self.client.close()
