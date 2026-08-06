from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

from trusted_domains import normalize_host

from .models import (
    CapabilityRequest,
    DecisionOutcome,
    PERMISSION_PRESETS,
    PermissionContext,
    PermissionMode,
    SandboxProfile,
    SecurityDecision,
    normalize_permission_mode,
)
from .policy import (
    FORCED_APPROVAL_RULES,
    PolicyEngine,
    canonical_path,
    is_within,
    patch_paths,
    protected_path,
    suggest_rule_pattern,
    validate_rule_pattern,
    unsafe_windows_path,
)
from .store import SecurityStore


_ACTIVE_CONTEXT: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "myagent_security_context", default=None
)
_STORE: SecurityStore | None = None
SECURITY_ENABLED_ENV_VAR = "SECURITY_ENABLED"

# Policy ASK categories that the one-time "workspace-outside handling
# permission" (write / delete / shell) may auto-allow once the user grants it.
# Read (fs.read), network, dynamic/destructive shell, credential export and
# policy tampering stay on their own paths and are never covered by it.
EXTERNAL_OPS_GRANTABLE_RULES = frozenset(
    {"external.write", "delete.review", "process.external"}
)

_NETWORK_COMMAND = re.compile(
    r"(?i)(?:https?://|\b(?:curl|wget|invoke-webrequest|invoke-restmethod|iwr|irm)\b|"
    r"\bgit\s+(?:clone|fetch|pull|push)\b|\b(?:pip|pip3|npm|pnpm|yarn)\s+install\b|"
    r"\b(?:ssh|scp|sftp|ftp|telnet|nc|ncat)\b)"
)
_POLICY_TAMPER = re.compile(
    r"(?i)(?:app[\\/]+security|security\.sqlite3|windows-sandbox\.json|"
    r"hooks\.json|HOOKS_(?:PATH|CONFIG_PATH|ENABLED)|"
    r"permission_mode|full_access_enabled|auto_review_enabled|security_enabled|"
    r"disable[^\r\n]*(?:security|approval|firewall|defender)|"
    r"set-mppreference|add-mppreference)"
)
_CREDENTIAL_TOKEN = re.compile(
    r"(?i)(?:^|[\s\"'/\\])(?:\.env(?:\.[\w.-]+)?|id_rsa|id_ed25519|"
    r"credentials\.json|login data)(?:$|[\s\"']|[\\/])|"
    r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password)\b"
)
# Reading credential-bearing files is treated as an ordinary read: allowed
# inside the workspace, approval-required outside. Only *export* remains an
# unconditional denial (copy out, upload, network send, credential-store dump).
_CREDENTIAL_READ_COMMAND = re.compile(
    r"(?i)"
    r"(?:"
    r"(?:^|[\s\"'@/\\])(?:\.env(?:\.[\w.-]+)?|id_rsa|id_ed25519|"
    r"credentials\.json|login data)(?:$|[\s\"']|[\\/])[^\r\n;&|]{0,60}"
    r"\b(?:echo|print|type|get-content|cat|more|less|head|tail)\b"
    r")|"
    r"(?:"
    r"\b(?:cat|type|get-content|echo|print|more|less|head|tail)\b[^\r\n]{0,400}"
    r"(?:^|[\s\"'@/\\])(?:\.env(?:\.[\w.-]+)?|id_rsa|id_ed25519|"
    r"credentials\.json|login data)(?:$|[\s\"']|[\\/])"
    r")|"
    r"(?:"
    r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password)\b[^\r\n]{0,60}"
    r"\b(?:echo|print|type|get-content|cat)\b"
    r")|"
    r"(?:"
    r"\b(?:echo|print|type|get-content|cat)\b[^\r\n]{0,400}"
    r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password)\b"
    r")"
)
_CREDENTIAL_EXPORT_COMMAND = re.compile(
    r"(?i)"
    r"(?:"
    r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password)\b[^\r\n]{0,120}"
    r"\b(?:copy|upload|send|curl|wget|invoke-webrequest|invoke-restmethod|iwr|irm|"
    r"scp|sftp|ftp|telnet|nc|ncat|out-file|set-content)\b"
    r")|"
    r"(?:"
    r"(?:^|[\s\"'@/\\])(?:\.env(?:\.[\w.-]+)?|id_rsa|id_ed25519|"
    r"credentials\.json|login data)(?:$|[\s\"']|[\\/])[^\r\n]{0,120}"
    r"\b(?:copy|upload|send|scp|sftp|ftp|telnet|nc|ncat|out-file|set-content)\b"
    r")|"
    r"(?:"
    r"\b(?:curl|wget|invoke-webrequest|invoke-restmethod|iwr|irm|scp|sftp|ftp|nc|ncat)\b"
    r"[^\r\n]{0,400}"
    r"(?:^|[\s\"'@/\\])(?:\.env(?:\.[\w.-]+)?|id_rsa|id_ed25519|"
    r"credentials\.json|login data)(?:$|[\s\"']|[\\/])"
    r")|"
    r"(?:"
    r"\b(?:copy|upload|send|out-file|set-content)\b[^\r\n]{0,400}"
    r"(?:^|[\s\"'@/\\])(?:\.env(?:\.[\w.-]+)?|id_rsa|id_ed25519|"
    r"credentials\.json|login data)(?:$|[\s\"']|[\\/])"
    r")|"
    r"\b(?:cmdkey|credential\s*manager|security\s+find-generic-password)\b"
)
_DELETE_COMMAND = re.compile(
    r"(?i)(?:^|[;&|])\s*(?:rm|rmdir|del|erase|remove-item)\b|"
    r"\b(?:os\.(?:remove|unlink)|shutil\.rmtree|pathlib\.[^\r\n]*\.unlink)\s*\("
)


def security_store() -> SecurityStore:
    global _STORE
    if _STORE is None:
        _STORE = SecurityStore()
    return _STORE


def security_enabled(source: Any = None) -> bool:
    """Return whether application-level security controls are enabled.

    Missing or empty values default to ``0`` (full access with permission
    controls hidden). Any configured non-zero value enables the normal
    three-mode permission system.
    """

    env = os.environ if source is None else source
    return str(env.get(SECURITY_ENABLED_ENV_VAR, "0") or "0").strip() != "0"


def permission_context_for_mode(mode: object) -> PermissionContext:
    return PERMISSION_PRESETS[normalize_permission_mode(mode)]


def forced_approval_for(decision: SecurityDecision) -> bool:
    """Dangerous commands always require a fresh human approval.

    Rules in ``FORCED_APPROVAL_RULES`` cannot be satisfied by reusable rules,
    session/always grants, or the automatic reviewer. A human-created atomic
    ``allow_once`` grant may authorize exactly one final execution attempt.
    """
    return decision.rule_id in FORCED_APPROVAL_RULES


def always_ask_for(decision: SecurityDecision) -> bool:
    """Operations that must surface a fresh human approval every time.

    Covers dangerous commands (red-box, with consequences) only. Credential
    reads inside the workspace are ordinary reads; credential reads outside
    the workspace are ordinary approvals and may be covered by rules.
    """
    return forced_approval_for(decision)


def session_permission_mode(session_id: str) -> PermissionMode:
    """The single global permission mode (shared by all sessions)."""
    if not security_enabled():
        return PermissionMode.FULL_ACCESS
    # Do not disguise a store or migration failure as a mode change. Callers
    # must fail the operation; the persisted global mode remains untouched.
    return normalize_permission_mode(security_store().get_global_permission_mode())


def set_session_permission_mode(session_id: str, mode: object) -> PermissionMode:
    """Switch the single global permission mode.

    All three modes are directly selectable; switching to "approve for me"
    does not require a separate settings enablement (the explicit mode switch
    is itself the opt-in).
    """
    normalized = normalize_permission_mode(mode)
    sid = str(session_id or "").strip()
    if not sid:
        raise ValueError("missing session_id")
    from agent_harness import session_manager

    with session_manager._lock:
        meta = session_manager._load_metadata_unlocked(sid)
        if not meta:
            raise ValueError("session not found")
    if not security_enabled():
        # SECURITY_ENABLED=0 is an environment-level override. Do not overwrite
        # the persisted global choice, so setting it back to 1 restores the
        # user's previous three-mode selection.
        return PermissionMode.FULL_ACCESS
    security_store().set_session_mode(sid, normalized.value)
    return normalized


def classify_tool(tool_name: str, arguments: dict[str, Any], workspace: Path) -> CapabilityRequest:
    name = str(tool_name or "").strip()
    args = dict(arguments or {})
    if name.startswith("mcp_"):
        try:
            from agent_mcp import get_tool_contract

            contract = get_tool_contract(name)
        except Exception:
            contract = {}
        effect = str(contract.get("effect") or "unknown").strip().lower()
        return CapabilityRequest.create(
            action="mcp.call",
            resource=_declared_resource(name, args, contract, workspace),
            effect=effect,
            principal="mcp",
            arguments=args,
            metadata={
                "tool": name,
                "declared": bool(contract.get("declared") and effect),
                "network": bool(contract.get("network")),
                "server_source": str(contract.get("server_source") or ""),
                "paths": _declared_paths(args, contract, workspace),
                "contract": contract,
            },
        )
    if name.startswith("plugin_"):
        try:
            from agent_extensions import get_plugin_tool_contract

            contract = get_plugin_tool_contract(name)
        except Exception:
            contract = {}
        effect = str(contract.get("effect") or "unknown").strip().lower()
        return CapabilityRequest.create(
            action="plugin.call",
            resource=_declared_resource(name, args, contract, workspace),
            effect=effect,
            principal="plugin",
            arguments=args,
            metadata={
                "tool": name,
                "declared": bool(contract.get("declared") and effect),
                "network": bool(contract.get("network")),
                "permissions": dict(contract.get("permissions") or {}),
                "paths": _declared_paths(args, contract, workspace),
                "contract": contract,
            },
        )
    if name == "run_shell":
        command = str(args.get("command") or "")
        try:
            from agent_tools import (
                _agent_self_protection_reason,
                _is_dangerous,
                _paths_inside_workspace,
                _readonly_git_scope_ok,
                _text_mentions_sensitive_tool_resource,
            )

            external = not _paths_inside_workspace(command, workspace)
            # Read-only git invocations (log/status/rev-parse/...) may point at
            # a repository outside the workspace via -C/--git-dir/--work-tree.
            # That is a pure read and should not count as external access.
            if external and _readonly_git_scope_ok(command, workspace):
                external = False
            workdir = str(args.get("workdir") or args.get("working_dir") or "").strip()
            if workdir:
                external = external or not is_within(canonical_path(workdir, workspace), workspace)
            destructive = bool(_is_dangerous(command) or _DELETE_COMMAND.search(command))
            credential_export = bool(
                _text_mentions_sensitive_tool_resource(command)
                or _text_mentions_sensitive_tool_resource(workdir)
                or _CREDENTIAL_EXPORT_COMMAND.search(command)
            )
            # Reading credential-bearing files (cat/Get-Content/... a .env,
            # key, credentials file) requires approval regardless of location,
            # so shell cannot bypass the read-tool policy.
            credential_read = bool(_CREDENTIAL_READ_COMMAND.search(command))
            policy_change = bool(_agent_self_protection_reason(command))
        except Exception:
            external = True
            destructive = False
            credential_export = False
            credential_read = False
            policy_change = False
        policy_change = policy_change or bool(_POLICY_TAMPER.search(command))
        return CapabilityRequest.create(
            action="process.exec",
            resource=command,
            effect="policy_change" if policy_change else ("destructive" if destructive else "workspace_write"),
            arguments=args,
            metadata={
                "tool": name,
                # restrict_to_workspace is intentionally ignored. Old callers
                # may still send it, but the central policy derives scope from
                # the final command and working directory.
                "external_workspace": external,
                "network": bool(_NETWORK_COMMAND.search(command)),
                "destructive": destructive,
                "credential_export": credential_export,
                "credential_read": credential_read,
                "policy_change": policy_change,
            },
        )
    if name == "web_search":
        # web_search is read-only and always hits a configured search provider
        # (DuckDuckGo/Brave/Tavily/SearXNG/Jina). It gets its own action so
        # the "always allow same kind" suggestion is a tool-level rule
        # (pattern "web_search") instead of an un-parseable query string.
        return CapabilityRequest.create(
            action="web.search",
            resource=str(args.get("query") or args.get("q") or "web_search"),
            effect="read",
            arguments=args,
            metadata={"tool": name, "network": True},
        )
    if name in {"web_fetch", "web_download"}:
        metadata: dict[str, Any] = {"tool": name, "network": True}
        if name == "web_download":
            raw_path = (
                args.get("path")
                or args.get("target_directory")
                or args.get("file_path")
            )
            if raw_path:
                metadata["paths"] = [str(canonical_path(raw_path, workspace))]
            metadata["allow_workspace_path"] = True
        return CapabilityRequest.create(
            action="network.connect",
            resource=str(args.get("url") or args.get("query") or name),
            effect="workspace_write" if name == "web_download" else "read",
            arguments=args,
            metadata=metadata,
        )
    action = None
    effect = "read"
    if name in {"read_file", "ls", "list_dir", "glob", "grep"}:
        action = "fs.read"
    elif name in {"write_file", "edit_file", "apply_patch"}:
        action, effect = "fs.write", "workspace_write"
    elif name == "delete_file":
        action, effect = "fs.delete", "destructive"
    if action:
        raw = args.get("path") or args.get("file_path") or args.get("root") or "/"
        paths = [str(canonical_path(raw, workspace))]
        if name == "apply_patch":
            patch_text = str(args.get("patch") or "")
            patch_resources = list(patch_paths(patch_text))
            paths = [
                str(canonical_path(item, workspace)) for item in patch_resources
            ] or [str(workspace.resolve())]
            if any(
                line.startswith("*** Delete File:")
                for line in patch_text.splitlines()
            ):
                action, effect = "fs.delete", "destructive"
        resource = paths[0]
        metadata: dict[str, Any] = {"tool": name, "paths": paths}
        if name == "delete_file":
            # delete_file is a recoverable soft delete (moves the target into
            # WORK_DIR/.trash/). Mark it so the policy can auto-allow it even
            # outside the workspace; apply_patch deletions stay permanent and
            # keep asking outside.
            metadata["soft_delete"] = True
        return CapabilityRequest.create(
            action=action, resource=resource, effect=effect, arguments=args,
            metadata=metadata,
        )
    if name in {
        "ask_user",
        "activate_skill",
        "update_todo",
        "context_manage",
        "task",
        "team",
        "create_goal",
        "get_goal",
        "update_goal",
    }:
        return CapabilityRequest.create(
            action="tool.call",
            resource=name,
            effect="read",
            arguments=args,
            metadata={"tool": name, "declared": True},
        )
    return CapabilityRequest.create(
        action="tool.call", resource=name, effect="unknown",
        arguments=args, metadata={"tool": name},
    )


def classify_hook(
    definition: Any,
    payload: dict[str, Any],
    workspace: Path,
) -> CapabilityRequest:
    command_spec = getattr(definition, "command", None)
    command = str(
        command_spec.platform_command() if command_spec is not None else ""
    ).strip()
    raw_cwd = str(getattr(command_spec, "cwd", "") or "").strip()
    source_root = Path(getattr(definition, "source_root", workspace)).resolve()
    cwd = canonical_path(raw_cwd, source_root) if raw_cwd else source_root
    config_payload = {
        "hook_id": str(getattr(definition, "id", "")),
        "event": str(getattr(definition, "event", "")),
        "source_id": str(getattr(definition, "source_id", "")),
        "plugin_id": str(getattr(definition, "plugin_id", "") or ""),
        "matcher": str(getattr(definition, "matcher", "") or ""),
        "handler_type": str(getattr(definition, "handler_type", "command") or "command"),
        "failure_policy": str(getattr(definition, "failure_policy", "") or ""),
        "priority": int(getattr(definition, "priority", 100) or 100),
        "command": command,
        "cwd": str(cwd),
        "env_allowlist": list(getattr(command_spec, "env_allowlist", ()) or ()),
        "env": dict(getattr(command_spec, "env", {}) or {}),
        "plugin_signature": str(getattr(definition, "plugin_signature", "") or ""),
    }
    config_digest = hashlib.sha256(
        json.dumps(
            config_payload, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), default=str,
        ).encode("utf-8")
    ).hexdigest()
    return CapabilityRequest.create(
        action="hook.exec",
        resource=command or str(getattr(definition, "id", "hook")),
        effect="unknown",
        principal=(
            f"plugin:{getattr(definition, 'plugin_id', '')}"
            if getattr(definition, "plugin_id", None)
            else "project_hook"
        ),
        arguments=config_payload,
        metadata={
            "hook_id": str(getattr(definition, "id", "")),
            "event": str(getattr(definition, "event", "")),
            "cwd": str(cwd),
            "config_digest": config_digest,
            "session_id": str(payload.get("session_id") or ""),
        },
    )


def _declared_paths(
    arguments: dict[str, Any],
    contract: dict[str, Any],
    workspace: Path,
) -> list[str]:
    paths: list[str] = []
    for argument_name in contract.get("path_arguments") or []:
        raw = arguments.get(str(argument_name))
        if raw is not None and str(raw).strip():
            paths.append(str(canonical_path(raw, workspace)))
    return paths


def _declared_resource(
    name: str,
    arguments: dict[str, Any],
    contract: dict[str, Any],
    workspace: Path,
) -> str:
    resources: list[str] = []
    for argument_name in contract.get("resource_arguments") or []:
        raw = arguments.get(str(argument_name))
        if raw is not None and str(raw).strip():
            resources.append(str(raw))
    resources.extend(_declared_paths(arguments, contract, workspace))
    return " | ".join(resources) if resources else name


def _audit_resource(request: CapabilityRequest) -> dict[str, Any]:
    base: dict[str, Any] = {
        "action": request.action,
        "resource_digest": hashlib.sha256(
            str(request.resource or "").encode("utf-8")
        ).hexdigest(),
    }
    if request.action.startswith("fs."):
        base["paths"] = list(request.metadata.get("paths") or [request.resource])
    elif request.action == "process.exec":
        try:
            from .policy import safe_command_prefix

            base["command_prefix"] = safe_command_prefix(request.resource) or "dynamic"
        except Exception:
            base["command_prefix"] = "unknown"
    elif request.action in {"network.connect", "web.search"}:
        try:
            parsed = urlsplit(str(request.resource or ""))
            base["network_target"] = (
                f"{parsed.scheme}://{parsed.hostname or ''}{parsed.path}"
                if parsed.scheme and parsed.hostname
                else str(request.metadata.get("tool") or request.action)
            )
        except ValueError:
            base["network_target"] = str(request.metadata.get("tool") or request.action)
    else:
        base["resource"] = str(request.metadata.get("tool") or request.metadata.get("hook_id") or request.action)
    return base


def authorize_request(
    *,
    session_id: str,
    request: CapabilityRequest,
    workspace: Path,
) -> tuple[SecurityDecision, PermissionContext]:
    context = permission_context_for_mode(session_permission_mode(session_id))
    store = security_store()
    engine = PolicyEngine(workspace, store.policy_version())
    decision = engine.decide(request, context)
    if decision.outcome != DecisionOutcome.DENY:
        rules = store.active_permission_rules(
            session_id=session_id, workspace=str(workspace)
        )
        rule_decision = engine.rule_decision(request, rules, workspace)
        if rule_decision is not None:
            if rule_decision.outcome in {DecisionOutcome.DENY, DecisionOutcome.ASK}:
                decision = rule_decision
            elif not always_ask_for(decision):
                decision = rule_decision
    if (
        decision.outcome == DecisionOutcome.ASK
        and not decision.constraints.get("user_rule")
    ):
        if (
            decision.rule_id in EXTERNAL_OPS_GRANTABLE_RULES
            and store.get_setting("allow_external_workspace_ops")
        ):
            # One-time user grant: write / delete / shell operations outside
            # the workspace run automatically from now on. Explicit user rules
            # (deny/ask) and forced approvals already returned above.
            decision = SecurityDecision(
                DecisionOutcome.ALLOW,
                "Allowed by the workspace-outside handling permission (write/delete/shell).",
                "grant.external_workspace_ops",
                decision.request_digest,
            )
        else:
            forced = always_ask_for(decision)
            grant = store.consume_matching_grant(
                session_id,
                decision.request_digest,
                once_only=forced,
            )
            if grant:
                decision = SecurityDecision(
                    DecisionOutcome.ALLOW,
                    f"Approved by {grant} grant.",
                    f"grant.{grant}",
                    decision.request_digest,
                )
    store.audit(
        session_id=session_id,
        event_type="authorization",
        request_digest=decision.request_digest,
        outcome=decision.outcome.value,
        payload={**_audit_resource(request), "rule": decision.rule_id},
    )
    return decision, context


def authorize_tool(
    *,
    session_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    workspace: Path,
) -> tuple[CapabilityRequest, SecurityDecision, PermissionContext]:
    request = classify_tool(tool_name, arguments, workspace)
    decision, context = authorize_request(
        session_id=session_id, request=request, workspace=workspace
    )
    return request, decision, context


def add_permission_rule(
    *,
    behavior: str,
    action: str,
    pattern: str,
    source: str = "user",
    session_id: str = "",
    workspace: Path | str | None = None,
) -> dict[str, Any]:
    """Create a durable allow/deny/ask pattern rule (validated)."""
    validate_rule_pattern(action, pattern, behavior)
    source = str(source or "user").strip().lower()
    if source == "user":
        # User-level rules apply everywhere; session/workspace provenance is
        # irrelevant and would create duplicate rows per session.
        session_id = ""
        ws = ""
    else:
        ws = str(workspace.resolve()) if isinstance(workspace, Path) else str(workspace or "")
    rule_id = security_store().add_permission_rule(
        source=source,
        behavior=behavior,
        action=action,
        pattern=pattern,
        session_id=str(session_id or "").strip(),
        workspace=ws,
    )
    return {
        "id": rule_id,
        "source": source,
        "behavior": str(behavior).strip().lower(),
        "action": str(action).strip().lower(),
        "pattern": str(pattern).strip(),
    }


def list_permission_rules(
    *,
    session_id: str = "",
    workspace: Path | str | None = None,
) -> list[dict[str, Any]]:
    ws = str(workspace.resolve()) if isinstance(workspace, Path) else str(workspace or "")
    return security_store().list_permission_rules(
        session_id=str(session_id or "").strip(), workspace=ws
    )


def delete_permission_rule(rule_id: object) -> bool:
    return security_store().delete_permission_rule(rule_id)


def clear_session_permission_rules(session_id: str) -> int:
    return security_store().clear_session_permission_rules(session_id)


_WEB_FETCH_DOMAINS_KEY = "web_fetch_preapproved_domains"


def _normalize_domain_list(text: str) -> str:
    seen: list[str] = []
    for item in str(text or "").replace(",", "\n").splitlines():
        host = normalize_host(item)
        if not host or host in seen:
            continue
        seen.append(host)
    return "\n".join(seen)


def web_fetch_preapproved_domains() -> list[str]:
    """User-edited pre-approved web_fetch domains (persisted, empty allowed)."""
    raw = security_store().get_text_setting(_WEB_FETCH_DOMAINS_KEY, "")
    return [item for item in _normalize_domain_list(raw).splitlines() if item]


def set_web_fetch_preapproved_domains(domains: list[str]) -> list[str]:
    normalized = _normalize_domain_list("\n".join(str(d) for d in (domains or [])))
    security_store().set_text_setting(_WEB_FETCH_DOMAINS_KEY, normalized)
    return [item for item in normalized.splitlines() if item]


@contextlib.contextmanager
def execution_scope(
    *,
    session_id: str,
    context: PermissionContext,
    request: CapabilityRequest,
    decision: SecurityDecision,
    workspace: Path,
) -> Iterator[None]:
    token = _ACTIVE_CONTEXT.set(
        {
            "session_id": session_id,
            "context": context,
            "request": request,
            "decision": decision,
            "workspace": workspace.resolve(),
        }
    )
    try:
        yield
    finally:
        _ACTIVE_CONTEXT.reset(token)


def active_security_context() -> dict[str, Any] | None:
    return _ACTIVE_CONTEXT.get()


def enforce_leaf(action: str, resource: object) -> None:
    active = active_security_context()
    if not active:
        return
    context: PermissionContext = active["context"]
    if context.mode == PermissionMode.FULL_ACCESS:
        return
    request: CapabilityRequest = active["request"]
    decision: SecurityDecision = active["decision"]
    if decision.outcome != DecisionOutcome.ALLOW:
        raise PermissionError(decision.reason)
    if action.startswith("fs."):
        workspace: Path = active["workspace"]
        expected = canonical_path(request.resource, workspace)
        actual = canonical_path(resource, workspace)
        if unsafe_windows_path(actual):
            raise PermissionError(f"Unsafe Windows path is denied: {actual}")
        if action != "fs.read" and protected_path(actual, workspace):
            raise PermissionError(f"Security-sensitive path is protected: {actual}")
        declared_paths = {
            canonical_path(item, workspace)
            for item in (request.metadata.get("paths") or [])
        }
        if (
            request.metadata.get("allow_workspace_path")
            and is_within(actual, workspace)
        ):
            return
        if declared_paths and actual in declared_paths:
            return
        if expected != actual:
            raise PermissionError("Tool resource changed after authorization.")


def add_approval_grant(
    session_id: str,
    request_digest: str,
    decision: str,
) -> None:
    mapping = {
        "allow_once": ("once", 300.0),
        "allow_session": ("session", 24 * 3600.0),
        "allow_always": ("always", None),
    }
    if decision not in mapping:
        return
    scope, ttl = mapping[decision]
    owner = "*" if scope == "always" else session_id
    security_store().add_grant(owner, request_digest, scope, ttl_seconds=ttl)


def security_status_for_session(session_id: str) -> dict[str, Any]:
    enabled = security_enabled()
    mode = session_permission_mode(session_id)
    context = permission_context_for_mode(mode)
    return {
        "mode": mode.value,
        "mode_scope": "global",
        "updated_at": security_store().get_global_permission_mode_updated_at(),
        "sandbox_profile": context.sandbox_profile.value,
        "effective_profile": context.sandbox_profile.value,
        "approval_policy": context.approval_policy.value,
        "reviewer": context.reviewer.value,
        "security_enabled": enabled,
        "permission_controls_visible": enabled,
        "restriction": {
            "implementation": (
                "none"
                if context.sandbox_profile == SandboxProfile.NO_RESTRICTION
                else "application-policy"
            ),
            "label": (
                "不受限制"
                if context.sandbox_profile == SandboxProfile.NO_RESTRICTION
                else "应用层受限"
            ),
            "hard_sandbox": False,
            "os_user": "current",
        },
        "available_modes": {
            "ask_for_approval": enabled,
            "approve_for_me": enabled,
            "full_access": enabled,
        },
    }


def security_settings() -> dict[str, bool]:
    store = security_store()
    return {
        "security_enabled": security_enabled(),
        "auto_review_enabled": store.get_setting("auto_review_enabled"),
        "allow_external_workspace_ops": store.get_setting(
            "allow_external_workspace_ops"
        ),
        "full_access_enabled": True,
    }


def update_security_settings(**values: bool) -> dict[str, bool]:
    store = security_store()
    for key in ("auto_review_enabled", "allow_external_workspace_ops"):
        if key in values:
            store.set_setting(key, bool(values[key]))
    return security_settings()
