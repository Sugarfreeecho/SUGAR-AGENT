from __future__ import annotations

import os
import re
import fnmatch
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

from .models import (
    CapabilityRequest,
    DecisionOutcome,
    PermissionContext,
    SandboxProfile,
    SecurityDecision,
)


_PROTECTED_NAMES = {
    ".env",
    ".git",
    ".agents",
    ".myagent",
    "hooks.json",
}
_SENSITIVE_PARTS = {
    ".ssh",
    ".aws",
    ".azure",
    ".gnupg",
    "credentials",
    "credential manager",
    "browser",
    "cookies",
}
_DYNAMIC_SHELL = re.compile(
    r"(?i)(?:\beval\b|invoke-expression|\biex\b|-(?:enc|encodedcommand)\b|"
    r"\b(?:python|python3|node|ruby|perl)\s+(?:-c|-e)\b|\$\(|`[^`]+`)"
)
_ENV_ASSIGN_PREFIX = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*=[A-Za-z0-9_./:+-]+[ \t]+"
)
_SUBCOMMAND_TOKEN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")

# Prefixes that may never become an *allow* rule for process.exec: matching
# them would be approximately "allow arbitrary code execution". Mirrors
# Claude Code's BARE_SHELL_PREFIXES (bashPermissions.ts). Deny/ask rules on
# these prefixes remain useful and are allowed.
_DANGEROUS_ALLOW_PREFIXES = frozenset(
    {
        "sh", "bash", "zsh", "fish", "csh", "tcsh", "ksh", "dash",
        "cmd", "powershell", "pwsh",
        "env", "xargs", "nice", "stdbuf", "nohup", "timeout", "time",
        "sudo", "doas", "pkexec",
        "eval", "invoke-expression", "iex",
    }
)

# Dangerous command categories that can never be auto-allowed by a grant or by
# the automatic reviewer: they must surface a fresh human approval every time.
FORCED_APPROVAL_RULES = frozenset({"process.destructive", "process.dynamic"})


def canonical_path(raw: object, workspace: Path) -> Path:
    text = str(raw or "").strip()
    if not text or text == "/":
        candidate = workspace
    else:
        p = Path(text).expanduser()
        if os.name == "nt" and text.startswith("/") and not re.match(r"^/[A-Za-z]:", text):
            candidate = workspace / text.lstrip("/\\")
        elif not p.is_absolute():
            candidate = workspace / p
        else:
            candidate = p
    return Path(os.path.realpath(str(candidate))).resolve(strict=False)


def is_within(path: Path, root: Path) -> bool:
    try:
        os.path.commonpath((os.path.normcase(str(path)), os.path.normcase(str(root))))
        return path == root or root in path.parents
    except (ValueError, OSError):
        return False


def protected_path(path: Path, workspace: Path) -> bool:
    configured_hooks = os.getenv("HOOKS_PATH") or os.getenv("HOOKS_CONFIG_PATH")
    if configured_hooks:
        configured_path = canonical_path(configured_hooks, workspace)
        if path == configured_path or configured_path in path.parents:
            return True
    try:
        rel_parts = [part.lower() for part in path.relative_to(workspace).parts]
    except ValueError:
        rel_parts = [part.lower() for part in path.parts]
    return any(part in _PROTECTED_NAMES or part.startswith(".env.") for part in rel_parts)


def sensitive_path(path: Path) -> bool:
    lowered = {part.lower() for part in path.parts}
    if lowered & _SENSITIVE_PARTS:
        return True
    name = path.name.lower()
    return (
        name == ".env"
        or name.startswith(".env.")
        or name in {"id_rsa", "id_ed25519", "credentials.json", "login data"}
    )


def unsafe_windows_path(path: Path) -> bool:
    if os.name != "nt":
        return False
    text = str(path)
    lowered = text.lower()
    if lowered.startswith(("\\\\?\\", "\\\\.\\", "\\??\\", "\\globalroot\\")):
        return True
    # Keep the drive separator, reject any additional colon (NTFS ADS).
    tail = text[2:] if len(text) >= 2 and text[1] == ":" else text
    if ":" in tail:
        return True
    reserved = {
        "con", "prn", "aux", "nul", "clock$",
        *(f"com{i}" for i in range(1, 10)),
        *(f"lpt{i}" for i in range(1, 10)),
    }
    return any(part.split(".", 1)[0].lower() in reserved for part in path.parts)


def security_control_path(path: Path) -> bool:
    controller_root = Path(__file__).resolve().parent
    app_root = controller_root.parent
    try:
        from .store import security_state_dir

        state_root = security_state_dir()
    except Exception:
        state_root = None
    return (
        is_within(path, controller_root)
        or path == (app_root / ".env")
        or bool(state_root is not None and is_within(path, state_root))
    )


def normalize_rule_command(command: object) -> str:
    """Trim a shell command for rule matching, skipping safe env assignments."""
    text = str(command or "").strip()
    while True:
        match = _ENV_ASSIGN_PREFIX.match(text)
        if not match:
            break
        text = text[match.end():].strip()
    return " ".join(text.split())


def safe_command_prefix(command: object) -> str | None:
    """Stable command+subcommand prefix used for 'allow same kind' rules.

    Returns None for dangerous wrappers or prefixes that cannot round-trip
    safely (mirrors Claude Code's getSimpleCommandPrefix restrictions).
    """
    tokens = normalize_rule_command(command).split()
    if not tokens:
        return None
    first = tokens[0].lower()
    if first in _DANGEROUS_ALLOW_PREFIXES:
        return None
    prefix = first
    if (
        len(tokens) >= 2
        and _SUBCOMMAND_TOKEN.fullmatch(tokens[1].lower())
    ):
        prefix = f"{first} {tokens[1].lower()}"
    if re.search(r"""[;&|><`$(){}*?"'\\]""", prefix):
        return None
    return prefix


def validate_rule_pattern(action: str, pattern: str, behavior: str) -> None:
    action = str(action or "").strip().lower()
    pattern = str(pattern or "").strip()
    behavior = str(behavior or "").strip().lower()
    if not action or not pattern:
        raise ValueError("action 与 pattern 不能为空")
    if behavior == "allow" and action == "process.exec":
        prefix = pattern[:-2].strip() if pattern.endswith(":*") else pattern
        prefix_lower = prefix.lower()
        if prefix_lower in _DANGEROUS_ALLOW_PREFIXES:
            raise ValueError(f"不允许为危险命令前缀创建放行规则：{prefix}")
        if re.search(r"""[;&|><`$(){}]""", pattern):
            raise ValueError("放行规则不能包含命令连接符或动态代码标记")


def _command_matches(command: object, pattern: str) -> bool:
    text = normalize_rule_command(command).lower()
    pat = str(pattern or "").strip().lower()
    if not pat or pat == "*":
        return False
    prefix = pat[:-2].strip() if pat.endswith(":*") else pat
    if not prefix or prefix == "*":
        return False
    if text == prefix:
        return True
    return text.startswith(prefix + " ")


def _norm_rule_path(path: Path) -> str:
    text = str(path)
    if os.name == "nt":
        return text.lower().replace("/", "\\").rstrip("\\") or "\\"
    return text.rstrip("/") or "/"


def _path_matches(canonical: Path, pattern: str) -> bool:
    target = _norm_rule_path(canonical)
    pat = _norm_rule_path(Path(str(pattern or "")))
    recursive = pat.endswith("**")
    direct = (not recursive) and pat.endswith("*")
    if recursive:
        base = pat[:-2].rstrip("\\/")
    elif direct:
        base = pat[:-1].rstrip("\\/")
        return bool(base) and _norm_rule_path(canonical.parent) == base
    else:
        base = pat
    if not base:
        return False
    if target == base:
        return True
    sep = "\\" if os.name == "nt" else "/"
    return target.startswith(base + sep)


def _url_matches(url: object, pattern: str) -> bool:
    try:
        parsed = urlsplit(str(url or ""))
    except ValueError:
        return False
    if not parsed.scheme or not parsed.netloc:
        return False
    raw_pat = str(pattern or "").strip().lower()
    target_host = parsed.netloc.lower()
    if "://" in raw_pat:
        try:
            p = urlsplit(raw_pat)
        except ValueError:
            return False
        if not p.scheme or not p.netloc:
            return False
        if p.scheme != parsed.scheme.lower() or p.netloc != target_host:
            return False
        if p.path in ("", "/", "/*"):
            return True
        if p.path.endswith("*"):
            head = p.path[:-1]
            return not head or parsed.path.lower().startswith(head)
        return parsed.path.lower().startswith(p.path.lower())
    return target_host == raw_pat or target_host.endswith("." + raw_pat)


def _tool_name_matches(name: object, pattern: str) -> bool:
    return fnmatch.fnmatchcase(
        str(name or "").lower(), str(pattern or "").lower()
    )


def match_rule_for_request(
    request: "CapabilityRequest",
    rule: dict[str, object],
    workspace: Path,
) -> bool:
    action = str(rule.get("action") or "").strip().lower()
    pattern = str(rule.get("pattern") or "").strip()
    if not action or not pattern or action != request.action:
        return False
    if action == "process.exec":
        return _command_matches(request.resource, pattern)
    if action.startswith("fs."):
        raw = request.metadata.get("paths")
        if not isinstance(raw, (list, tuple)) or not raw:
            raw = [request.resource]
        try:
            canonical = [canonical_path(item, workspace) for item in raw]
        except Exception:
            return False
        return bool(canonical) and all(
            _path_matches(path, pattern) for path in canonical
        )
    if action == "network.connect":
        return _url_matches(request.resource, pattern)
    if action == "web.search":
        return _tool_name_matches(
            request.metadata.get("tool") or request.resource, pattern
        )
    if action in {"mcp.call", "plugin.call", "tool.call"}:
        name = request.metadata.get("tool") or request.resource
        return _tool_name_matches(name, pattern)
    return _tool_name_matches(request.resource, pattern)


def suggest_rule_pattern(
    request: "CapabilityRequest",
    workspace: Path,
) -> dict[str, str] | None:
    """Generate a safe, reusable pattern for the 'allow same kind' button."""
    action = str(request.action or "")
    if action == "process.exec":
        prefix = safe_command_prefix(request.resource)
        if prefix is None:
            return None
        return {"action": action, "pattern": f"{prefix}:*"}
    if action.startswith("fs."):
        raw = request.metadata.get("paths")
        if not isinstance(raw, (list, tuple)) or not raw:
            raw = [request.resource]
        if len(raw) != 1:
            # A reusable rule for one path must never authorize sibling paths
            # that happened to share the same multi-file request.
            return None
        try:
            path = canonical_path(raw[0], workspace)
        except Exception:
            return None
        if path.is_dir():
            pattern = f"{path}{os.sep}**"
        elif action == "fs.read":
            pattern = f"{path.parent}{os.sep}**"
        else:
            pattern = str(path)
        return {"action": action, "pattern": pattern}
    if action == "network.connect":
        try:
            parsed = urlsplit(str(request.resource or ""))
        except ValueError:
            return None
        if not parsed.scheme or not parsed.netloc:
            return None
        return {"action": action, "pattern": f"{parsed.scheme}://{parsed.netloc}/*"}
    if action == "web.search":
        name = str(request.metadata.get("tool") or request.resource or "")
        if not name:
            return None
        return {"action": action, "pattern": name}
    if action in {"mcp.call", "plugin.call", "tool.call"}:
        name = str(request.metadata.get("tool") or request.resource or "")
        if not name:
            return None
        if action in {"mcp.call", "plugin.call"} and name.count("__") >= 2:
            pattern = f"{name.rsplit('__', 1)[0]}__*"
        else:
            pattern = name
        return {"action": action, "pattern": pattern}
    return None


class PolicyEngine:
    def __init__(self, workspace: Path, policy_version: int = 1):
        self.workspace = workspace.resolve()
        self.policy_version = max(1, int(policy_version))

    def rule_decision(
        self,
        request: "CapabilityRequest",
        rules: Iterable[dict[str, object]],
        workspace: Path | None = None,
    ) -> SecurityDecision | None:
        """Apply user rules with deny > ask > allow precedence.

        Only the highest-precedence matching rule is returned. Rules never
        apply to requests the base policy already denied (credential export,
        policy tampering, protected paths); the caller enforces that.
        """
        workspace = workspace or self.workspace
        best: tuple[int, dict[str, object]] | None = None
        rank = {"deny": 3, "ask": 2, "allow": 1}
        for rule in rules or []:
            behavior = str(rule.get("behavior") or "").lower()
            if behavior not in rank:
                continue
            if not match_rule_for_request(request, rule, workspace):
                continue
            if best is None or rank[behavior] > best[0]:
                best = (rank[behavior], rule)
        if best is None:
            return None
        _, rule = best
        behavior = str(rule.get("behavior") or "").lower()
        pattern = str(rule.get("pattern") or "")
        digest = request.digest(self.policy_version)
        if behavior == "deny":
            return SecurityDecision(
                DecisionOutcome.DENY,
                f"已被权限规则拒绝：{pattern}",
                f"rule.deny.{request.action}",
                digest,
                {"user_rule": True, "pattern": pattern},
            )
        if behavior == "ask":
            return SecurityDecision(
                DecisionOutcome.ASK,
                f"权限规则要求审批：{pattern}",
                f"rule.ask.{request.action}",
                digest,
                {"user_rule": True, "pattern": pattern},
            )
        return SecurityDecision(
            DecisionOutcome.ALLOW,
            f"已被权限规则放行：{pattern}",
            f"rule.allow.{request.action}",
            digest,
            {"user_rule": True, "pattern": pattern},
        )

    def decide(
        self,
        request: CapabilityRequest,
        context: PermissionContext,
        *,
        sandbox_available: bool | None = None,
    ) -> SecurityDecision:
        digest = request.digest(self.policy_version)

        def result(outcome: DecisionOutcome, rule: str, reason: str, **constraints):
            return SecurityDecision(outcome, reason, rule, digest, constraints)

        if context.sandbox_profile == SandboxProfile.NO_RESTRICTION:
            return result(
                DecisionOutcome.ALLOW,
                "preset.full_access",
                "Full access bypasses application restrictions and approvals.",
            )

        if request.effect in {"credential", "policy_change"}:
            return result(
                DecisionOutcome.DENY,
                f"effect.{request.effect}.deny",
                f"{request.effect} is denied by the application security policy.",
            )

        resource_path = None
        if request.action.startswith("fs."):
            raw_paths = request.metadata.get("paths")
            if not isinstance(raw_paths, (list, tuple)) or not raw_paths:
                raw_paths = [request.resource]
            resource_paths = [
                canonical_path(raw_path, self.workspace) for raw_path in raw_paths
            ]
            resource_path = resource_paths[0]
            inside = all(is_within(path, self.workspace) for path in resource_paths)
            for path in resource_paths:
                if unsafe_windows_path(path):
                    return result(
                        DecisionOutcome.DENY,
                        "path.windows_unsafe",
                        "Windows device, reserved-name, or alternate-stream paths are denied.",
                    )
                if security_control_path(path):
                    return result(
                        DecisionOutcome.DENY,
                        "security_control.protected",
                        "MyAgent security policy and authorization state cannot be accessed by tools.",
                    )
                if request.action != "fs.read" and protected_path(path, self.workspace):
                    return result(
                        DecisionOutcome.DENY,
                        "protected.write",
                        f"Security-sensitive path is protected: {path}",
                    )
                if request.action == "fs.read" and sensitive_path(path) and not inside:
                    return result(
                        DecisionOutcome.ASK,
                        "credential.read",
                        "Reading credential-bearing files outside the workspace requires approval.",
                    )
        else:
            inside = False

        # Kept only for compatibility with persisted contexts. The normal
        # first-stage profile is APP_RESTRICTED and never becomes READ_ONLY
        # merely because an OS sandbox is absent.
        if context.sandbox_profile == SandboxProfile.READ_ONLY:
            if request.action == "fs.read" and inside and not protected_path(resource_path, self.workspace):
                return result(DecisionOutcome.ALLOW, "read_only.workspace_read", "Workspace read is allowed.")
            return result(DecisionOutcome.DENY, "read_only.deny", "This explicit legacy profile is read-only.")

        if request.action == "fs.read":
            if inside:
                return result(DecisionOutcome.ALLOW, "app_restricted.read", "Workspace read is allowed.")
            return result(DecisionOutcome.ASK, "external.read", "Reading outside the workspace requires approval.")
        if request.action == "fs.write":
            if inside:
                return result(DecisionOutcome.ALLOW, "app_restricted.write", "Workspace write is allowed.")
            return result(DecisionOutcome.ASK, "external.write", "Writing outside the workspace requires approval.")
        if request.action == "fs.delete":
            return result(
                DecisionOutcome.ASK,
                "delete.review",
                "Deletion requires approval.",
                outside_workspace=not inside,
            )
        if request.action == "process.exec":
            if request.metadata.get("credential_export"):
                return result(
                    DecisionOutcome.DENY,
                    "process.credential",
                    "Credential export is denied.",
                )
            if request.metadata.get("policy_change"):
                return result(
                    DecisionOutcome.DENY,
                    "process.policy_change",
                    "Security policy or Agent controller tampering is denied.",
                )
            if request.metadata.get("credential_read"):
                return result(
                    DecisionOutcome.ASK,
                    "process.credential_read",
                    "Reading credential-bearing files via shell requires approval.",
                )
            if request.metadata.get("external_workspace"):
                return result(DecisionOutcome.ASK, "process.external", "Command requests access outside the workspace.")
            if request.metadata.get("network"):
                return result(DecisionOutcome.ASK, "process.network", "Command may access the network.")
            if request.metadata.get("destructive"):
                return result(DecisionOutcome.ASK, "process.destructive", "Destructive command requires approval.")
            if _DYNAMIC_SHELL.search(request.resource):
                return result(DecisionOutcome.ASK, "process.dynamic", "Dynamically constructed shell code requires review.")
            return result(
                DecisionOutcome.ALLOW,
                "process.app_restricted",
                "Workspace command is allowed by the application policy.",
            )
        if request.action == "network.connect":
            if str(request.metadata.get("tool") or "") == "web_fetch":
                from .web_preapproved import is_preapproved_host_with_user_list
                from .runtime import web_fetch_preapproved_domains

                try:
                    _parsed = urlsplit(str(request.resource or ""))
                    _host = _parsed.hostname
                except ValueError:
                    _host = None
                if _host and is_preapproved_host_with_user_list(
                    _host, frozenset(web_fetch_preapproved_domains())
                ):
                    return result(
                        DecisionOutcome.ALLOW,
                        "network.preapproved_web_fetch",
                        "Pre-approved documentation host is allowed for read-only web fetch.",
                    )
            return result(DecisionOutcome.ASK, "network.default_deny", "Network access requires approval.")
        if request.action == "web.search":
            return result(
                DecisionOutcome.ASK,
                "web.search.first_use",
                "Web search is read-only but requires one-time approval.",
            )
        if request.action in {"mcp.call", "plugin.call"}:
            declared = bool(request.metadata.get("declared"))
            effect = str(request.effect or "unknown")
            permissions = request.metadata.get("permissions")
            permissions = permissions if isinstance(permissions, dict) else {}
            declared_paths = request.metadata.get("paths")
            declared_paths = declared_paths if isinstance(declared_paths, (list, tuple)) else []
            external_path = any(
                not is_within(canonical_path(path, self.workspace), self.workspace)
                for path in declared_paths
            )
            if permissions.get("credential") or permissions.get("security_policy"):
                return result(
                    DecisionOutcome.DENY,
                    f"{request.action}.forbidden_capability",
                    "Credential or security-policy capability is denied.",
                )
            if not declared or effect in {"", "unknown"}:
                return result(
                    DecisionOutcome.ASK,
                    f"{request.action}.unknown_effect",
                    "The external tool does not declare a known side effect.",
                )
            if effect in {"credential", "policy_change"}:
                return result(
                    DecisionOutcome.DENY,
                    f"{request.action}.{effect}",
                    f"External tool capability {effect} is denied.",
                )
            if (
                effect in {"external_write", "destructive"}
                or external_path
                or request.metadata.get("network")
                or permissions.get("network")
                or permissions.get("shell")
            ):
                return result(
                    DecisionOutcome.ASK,
                    f"{request.action}.review",
                    "Declared external, network, shell, or destructive capability requires approval.",
                )
            if effect in {"read", "workspace_write"}:
                return result(
                    DecisionOutcome.ALLOW,
                    f"{request.action}.{effect}",
                    f"Declared {effect} capability is allowed.",
                )
            return result(
                DecisionOutcome.ASK,
                f"{request.action}.unsupported_effect",
                f"Unrecognized effect {effect!r} requires approval.",
            )
        if request.action == "hook.exec":
            return result(DecisionOutcome.ASK, "hook.exec.review", "Hook execution requires review.")
        if request.effect in {"destructive", "external_write", "unknown"}:
            return result(DecisionOutcome.ASK, "effect.review", f"{request.effect} requires review.")
        return result(DecisionOutcome.ALLOW, "default.low_risk", "Low-risk operation is allowed.")


def patch_paths(patch: str) -> Iterable[str]:
    for line in str(patch or "").splitlines():
        if line.startswith(("*** Add File: ", "*** Update File: ", "*** Delete File: ")):
            yield line.split(": ", 1)[1].strip()
