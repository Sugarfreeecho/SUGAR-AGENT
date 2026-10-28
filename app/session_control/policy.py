"""Trusted caller scope. Policy objects never come from RPC model parameters."""
from __future__ import annotations

import hashlib
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ControlError
from .store import encoded


READ = frozenset({"session.list", "session.get", "session.history", "session.search", "session.attach",
                  "session.detach", "session.config.get", "session.config.preview", "tool_catalog.list",
                  "tool_catalog.describe", "operation.get", "operation.wait", "automation.list", "automation.get",
                  "automation.history", "automation.test", "config_preset.list", "config_preset.get",
                  "event_source.list", "event_source.get", "event_source.test", "system.health", "auth.status"})
DEFAULT_CAPABILITIES = ("read", "session.create", "session.fork", "session.send", "session.notice")


def workspace_key(path):
    return os.path.normcase(str(Path(path).expanduser().resolve()))


@dataclass(frozen=True)
class Principal:
    id: str
    name: str = ""
    admin: bool = False
    policy: dict = field(default_factory=dict)
    credential_kind: str = "grant"
    parent_id: str = ""
    runtime_ceiling: dict | None = None
    credential_id: str = ""
    parent_credential: str = ""
    delegated_policies: list = field(default_factory=list)
    source_ancestors: list = field(default_factory=list)

    @property
    def device_id(self):
        return self.id

    def permits(self, method):
        delegated_method = {"session.send_batch": "session.send", "operation.cancel": "session.send"}.get(method, method)
        if any(not Principal("delegation", policy=policy).permits(delegated_method) for policy in self.delegated_policies):
            return False
        caps = self.policy.get("capabilities", DEFAULT_CAPABILITIES)
        return self.admin or method in caps or (method in READ and "read" in caps)


def validate_policy(raw, *, workspace="", current_session=""):
    raw = dict(raw or {})
    unknown = set(raw) - {"scope", "session_ids", "workspaces", "current_session", "workspace", "capabilities"}
    if unknown:
        raise ControlError("invalid_policy", "Unknown policy fields: " + ", ".join(sorted(unknown)))
    scope = raw.get("scope", "workspace")
    if scope not in {"self", "tree", "sessions", "workspace", "workspaces", "all"}:
        raise ControlError("invalid_policy", "Invalid session scope")
    value = {"scope": scope, "workspace": workspace_key(raw.get("workspace") or workspace) if (raw.get("workspace") or workspace) else "",
             "current_session": str(raw.get("current_session") or current_session),
             "session_ids": raw.get("session_ids", []), "workspaces": raw.get("workspaces", []),
             "capabilities": raw.get("capabilities", list(DEFAULT_CAPABILITIES))}
    for key in ("session_ids", "workspaces", "capabilities"):
        if not isinstance(value[key], list) or any(not isinstance(x, str) or not x for x in value[key]):
            raise ControlError("invalid_policy", key + " must be an array of strings")
    value["workspaces"] = [workspace_key(x) for x in value["workspaces"]]
    if scope == "workspace" and not value["workspace"]:
        raise ControlError("invalid_policy", "Workspace scope requires a workspace")
    if scope in {"self", "tree"} and not value["current_session"]:
        raise ControlError("invalid_policy", "Session scope requires current_session")
    return value


def check_session(principal, sid, manager):
    for policy in principal.delegated_policies:
        check_session(Principal("delegation", policy=policy), sid, manager)
    if principal.admin:
        return
    policy = principal.policy
    scope = policy.get("scope", "workspace")
    if scope == "all":
        return
    allowed = set(policy.get("session_ids", [])) if scope == "sessions" else set()
    if scope in {"self", "tree"}:
        root = str(policy.get("current_session") or "")
        allowed.add(root)
        if scope == "tree" and root:
            allowed.update(manager.list_subagent_descendants(root))
    if scope in {"workspace", "workspaces"}:
        from agent_harness import session_work_root
        roots = set(policy.get("workspaces", [])) if scope == "workspaces" else {policy.get("workspace", "")}
        if workspace_key(session_work_root(manager._load_metadata(sid))) in roots:
            return
    elif sid in allowed:
        return
    raise ControlError("scope_denied", "Session is outside the caller's authorized scope", status=403)


class IdentityService:
    def __init__(self, control_store, remote_store):
        self.store, self.remote = control_store, remote_store

    def issue(self, principal, *, ttl=3600):
        token = "sc1_" + secrets.token_urlsafe(36)
        with self.store.transaction() as db:
            db.execute("INSERT INTO grants(token_hash,principal,policy,expires) VALUES (?,?,?,?)",
                       (hashlib.sha256(token.encode()).hexdigest(), encoded({"id": principal.id, "name": principal.name,
                        "admin": principal.admin, "parent_id": principal.parent_id,
                        "parent_credential": principal.parent_credential,
                        "delegated_policies": principal.delegated_policies, "source_ancestors": principal.source_ancestors,
                        "runtime_ceiling": principal.runtime_ceiling}), encoded(principal.policy), time.time() + ttl))
        return token

    def authenticate(self, token):
        if not token:
            raise ControlError("unauthorized", "Authenticate with auth login or a host-issued task token", status=401)
        if token.startswith("sc1_"):
            import json
            with self.store.transaction() as db:
                row = db.execute("SELECT principal,policy FROM grants WHERE token_hash=? AND expires>? AND revoked=0",
                                 (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
            if row:
                p = json.loads(row[0])
                return Principal(**p, policy=json.loads(row[1]), credential_id=hashlib.sha256(token.encode()).hexdigest())
        else:
            p = self.remote.authenticate_device(token)
            if p:
                capabilities = ["read"] if p.permits("read") else []
                # Device write does not imply configuration or automation administration.
                if p.permits("write"):
                    capabilities += ["session.create", "session.send", "session.steer", "session.interrupt"]
                if p.permits("approvals"):
                    capabilities += ["approval.list", "approval.resolve"]
                return Principal(p.device_id, p.name, p.permits("admin"),
                                 {"scope": "all", "capabilities": capabilities}, "device")
        raise ControlError("unauthorized", "Credential is invalid, expired or revoked", status=401)

    def revoke(self, token):
        if token.startswith("sc1_"):
            with self.store.transaction() as db:
                db.execute("UPDATE grants SET revoked=1 WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
        else:
            p = self.remote.authenticate_device(token)
            if p:
                self.remote.revoke_device(p.device_id)

    def ensure_live(self, principal):
        identity = principal.parent_id or principal.id
        with self.store.transaction() as db:
            exact = principal.parent_credential or principal.credential_id
            row = db.execute("SELECT expires,revoked FROM grants WHERE token_hash=?", (exact,)).fetchone() if exact else db.execute("SELECT expires,revoked FROM grants WHERE json_extract(principal,'$.id')=? ORDER BY expires DESC LIMIT 1", (identity,)).fetchone()
        if exact and not row:
            raise ControlError("unauthorized", "Originating credential is unavailable", status=401)
        if row and (row[1] or row[0] <= time.time()):
            raise ControlError("unauthorized", "Originating credential expired or was revoked", status=401)
        for device in self.remote.list_devices():
            if device["device_id"] == identity and device.get("revoked_at"):
                raise ControlError("unauthorized", "Originating device was revoked", status=401)
