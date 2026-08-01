from __future__ import annotations

import contextlib
import contextvars
import re
from pathlib import Path
from typing import Any, Iterator

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
_NETWORK_COMMAND = re.compile(
    r"(?i)(?:https?://|\b(?:curl|wget|invoke-webrequest|invoke-restmethod|iwr|irm)\b|"
    r"\bgit\s+(?:clone|fetch|pull|push)\b|\b(?:pip|pip3|npm|pnpm|yarn)\s+install\b|"
    r"\b(?:ssh|scp|sftp|ftp|telnet|nc|ncat)\b)"
)
_POLICY_TAMPER = re.compile(
    r"(?i)(?:app[\\/]+security|security\.sqlite3|windows-sandbox\.json|"
    r"permission_mode|full_access_enabled|auto_review_enabled|"
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


def permission_context_for_mode(mode: object) -> PermissionContext:
    return PERMISSION_PRESETS[normalize_permission_mode(mode)]


def forced_approval_for(decision: SecurityDecision) -> bool:
    """Dangerous commands always require a fresh human approval.

    Rules in ``FORCED_APPROVAL_RULES`` can never be satisfied by a stored
    grant (allow_once / allow_session / allow_always) or by the automatic
    reviewer; the approval UI must show every time with only
    "allow once" / "deny" options.
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
    try:
        return normalize_permission_mode(security_store().get_global_permission_mode())
    except Exception:
        return PermissionMode.ASK_FOR_APPROVAL


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
                _text_mentions_sensitive_tool_resource,
            )

            external = not _paths_inside_workspace(command, workspace)
            workdir = str(args.get("workdir") or args.get("working_dir") or "").strip()
            if workdir:
                external = external or not is_within(canonical_path(workdir, workspace), workspace)
            destructive = bool(_is_dangerous(command) or _DELETE_COMMAND.search(command))
            credential_export = bool(
                _text_mentions_sensitive_tool_resource(command)
                or _text_mentions_sensitive_tool_resource(workdir)
                or _CREDENTIAL_EXPORT_COMMAND.search(command)
            )
            # Reading a credential-bearing file inside the workspace is an
            # ordinary read (matches Claude Code's default). Only reads that
            # also touch paths outside the workspace need approval.
            credential_read = bool(
                _CREDENTIAL_READ_COMMAND.search(command)
                and external
            )
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
        return CapabilityRequest.create(
            action=action, resource=resource, effect=effect, arguments=args,
            metadata={"tool": name, "paths": paths},
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


def authorize_tool(
    *,
    session_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    workspace: Path,
) -> tuple[CapabilityRequest, SecurityDecision, PermissionContext]:
    context = permission_context_for_mode(session_permission_mode(session_id))
    store = security_store()
    request = classify_tool(tool_name, arguments, workspace)
    engine = PolicyEngine(workspace, store.policy_version())
    decision = engine.decide(request, context)
    # User rules never override the base policy's unconditional denials
    # (credential export, policy tampering, protected paths). Otherwise
    # deny > ask > allow, and an allow rule cannot override forced approval
    # for destructive/dynamic commands.
    if decision.outcome != DecisionOutcome.DENY:
        rules = store.active_permission_rules(
            session_id=session_id, workspace=workspace
        )
        rule_decision = engine.rule_decision(request, rules, workspace)
        if rule_decision is not None:
            if rule_decision.outcome == DecisionOutcome.DENY:
                decision = rule_decision
            elif rule_decision.outcome == DecisionOutcome.ASK:
                decision = rule_decision
            elif not always_ask_for(decision):
                decision = rule_decision
            # else: forced approval (destructive/dynamic) wins over the rule.
    if (
        decision.outcome == DecisionOutcome.ASK
        and not always_ask_for(decision)
        and not decision.constraints.get("user_rule")
    ):
        grant = store.consume_matching_grant(session_id, decision.request_digest)
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
        payload={"tool": tool_name, "action": request.action, "resource": request.resource, "rule": decision.rule_id},
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
        host = str(item).strip().lower().rstrip(".")
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
    mode = session_permission_mode(session_id)
    context = permission_context_for_mode(mode)
    return {
        "mode": mode.value,
        "mode_scope": "global",
        "sandbox_profile": context.sandbox_profile.value,
        "effective_profile": context.sandbox_profile.value,
        "approval_policy": context.approval_policy.value,
        "reviewer": context.reviewer.value,
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
            "ask_for_approval": True,
            "approve_for_me": True,
            "full_access": True,
        },
    }


def security_settings() -> dict[str, bool]:
    store = security_store()
    return {
        "auto_review_enabled": store.get_setting("auto_review_enabled"),
        "full_access_enabled": True,
    }


def update_security_settings(**values: bool) -> dict[str, bool]:
    store = security_store()
    for key in ("auto_review_enabled",):
        if key in values:
            store.set_setting(key, bool(values[key]))
    return security_settings()
