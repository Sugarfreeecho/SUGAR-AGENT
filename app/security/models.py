from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class _ValueEnum(str, Enum):
    """str-mixin enum whose str()/format()/f-string always return the value.

    CPython <=3.10 formats mixed-in enums as their value while str() returns
    the qualified name; CPython 3.11+ changed format()/f-strings to match
    str(). This base pins all three to the member value so behavior is
    identical on every supported Python version.
    """

    def __str__(self) -> str:
        return self.value

    def __format__(self, format_spec: str) -> str:
        return format(self.value, format_spec)


class SandboxProfile(_ValueEnum):
    APP_RESTRICTED = "app_restricted"
    NO_RESTRICTION = "no_restriction"
    # Legacy aliases kept for persisted/API compatibility.
    WORKSPACE = "app_restricted"
    DANGER_FULL_ACCESS = "no_restriction"
    READ_ONLY = "read_only"


class ApprovalPolicy(_ValueEnum):
    ON_REQUEST = "on_request"
    NEVER = "never"


class ApprovalReviewer(_ValueEnum):
    USER = "user"
    AUTO_REVIEW = "auto_review"
    NONE = "none"


class PermissionMode(_ValueEnum):
    ASK_FOR_APPROVAL = "ask_for_approval"
    APPROVE_FOR_ME = "approve_for_me"
    FULL_ACCESS = "full_access"


class DecisionOutcome(_ValueEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class EgressIntent(_ValueEnum):
    NONE = "none"
    READ = "read"
    UPLOAD = "upload"
    INTERACTIVE = "interactive"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EgressDestination:
    host: str
    port: int | None = None
    scheme: str = ""
    resource: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "scheme": self.scheme,
            "resource": self.resource,
        }


@dataclass(frozen=True)
class CommandSegment:
    text: str
    executable: str = ""
    family: str = ""
    operation: str = ""
    intent: EgressIntent = EgressIntent.NONE
    destinations: tuple[EgressDestination, ...] = ()
    data_sources: tuple[str, ...] = ()
    dynamic: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "executable": self.executable,
            "family": self.family,
            "operation": self.operation,
            "intent": self.intent.value,
            "destinations": [item.as_dict() for item in self.destinations],
            "data_sources": list(self.data_sources),
            "dynamic": self.dynamic,
        }


@dataclass(frozen=True)
class ShellAnalysis:
    intent: EgressIntent
    segments: tuple[CommandSegment, ...] = ()
    destinations: tuple[EgressDestination, ...] = ()
    data_sources: tuple[str, ...] = ()
    confidence: str = "high"
    command_family: str = ""
    operation: str = ""
    sensitive_source: bool = False
    unknown_target: bool = False
    parse_errors: tuple[str, ...] = ()

    @property
    def network(self) -> bool:
        return self.intent != EgressIntent.NONE

    def as_metadata(self) -> dict[str, Any]:
        return {
            "egress_intent": self.intent.value,
            "network": self.network,
            "destinations": [item.as_dict() for item in self.destinations],
            "data_sources": list(self.data_sources),
            "analysis_confidence": self.confidence,
            "command_family": self.command_family,
            "egress_operation": self.operation,
            "sensitive_source": self.sensitive_source,
            "unknown_target": self.unknown_target,
            "segments": [item.as_dict() for item in self.segments],
            "parse_errors": list(self.parse_errors),
        }


@dataclass(frozen=True)
class EgressConstraint:
    mode: str
    destinations: tuple[EgressDestination, ...] = ()
    wildcard: bool = False


@dataclass(frozen=True)
class SandboxHealth:
    level: str
    backend: str
    available: bool
    reason: str = ""
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class PermissionContext:
    sandbox_profile: SandboxProfile
    approval_policy: ApprovalPolicy
    reviewer: ApprovalReviewer
    mode: PermissionMode | None = None

    def __post_init__(self) -> None:
        if self.mode is not None:
            return
        if self.sandbox_profile == SandboxProfile.NO_RESTRICTION:
            inferred = PermissionMode.FULL_ACCESS
        elif self.reviewer == ApprovalReviewer.AUTO_REVIEW:
            inferred = PermissionMode.APPROVE_FOR_ME
        else:
            inferred = PermissionMode.ASK_FOR_APPROVAL
        object.__setattr__(self, "mode", inferred)


PERMISSION_PRESETS = {
    PermissionMode.ASK_FOR_APPROVAL: PermissionContext(
        SandboxProfile.APP_RESTRICTED,
        ApprovalPolicy.ON_REQUEST,
        ApprovalReviewer.USER,
        PermissionMode.ASK_FOR_APPROVAL,
    ),
    PermissionMode.APPROVE_FOR_ME: PermissionContext(
        SandboxProfile.APP_RESTRICTED,
        ApprovalPolicy.ON_REQUEST,
        ApprovalReviewer.AUTO_REVIEW,
        PermissionMode.APPROVE_FOR_ME,
    ),
    PermissionMode.FULL_ACCESS: PermissionContext(
        SandboxProfile.NO_RESTRICTION,
        # NEVER applies to ordinary capability approvals. Forced destructive
        # approval and controller-integrity denial are cross-mode invariants.
        ApprovalPolicy.NEVER,
        ApprovalReviewer.NONE,
        PermissionMode.FULL_ACCESS,
    ),
}


def normalize_permission_mode(value: object) -> PermissionMode:
    if isinstance(value, PermissionMode):
        return value
    raw = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "ask": PermissionMode.ASK_FOR_APPROVAL,
        "request_approval": PermissionMode.ASK_FOR_APPROVAL,
        "auto_review": PermissionMode.APPROVE_FOR_ME,
        "approve": PermissionMode.APPROVE_FOR_ME,
        "danger_full_access": PermissionMode.FULL_ACCESS,
        "yolo": PermissionMode.FULL_ACCESS,
    }
    if raw in aliases:
        return aliases[raw]
    try:
        return PermissionMode(raw)
    except ValueError:
        return PermissionMode.ASK_FOR_APPROVAL


@dataclass(frozen=True)
class CapabilityRequest:
    action: str
    resource: str
    effect: str
    principal: str = "core"
    args_digest: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        action: str,
        resource: object,
        effect: str,
        principal: str = "core",
        arguments: object = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "CapabilityRequest":
        canonical = json.dumps(
            arguments if arguments is not None else {},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return cls(
            action=str(action or "").strip().lower(),
            resource=str(resource or "").strip(),
            effect=str(effect or "").strip().lower(),
            principal=str(principal or "core").strip(),
            args_digest=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            metadata=dict(metadata or {}),
        )

    def digest(self, policy_version: int) -> str:
        payload = {
            "action": self.action,
            "resource": self.resource,
            "effect": self.effect,
            "principal": self.principal,
            "args_digest": self.args_digest,
            "policy_version": int(policy_version),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SecurityDecision:
    outcome: DecisionOutcome
    reason: str
    rule_id: str
    request_digest: str
    constraints: Mapping[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.outcome == DecisionOutcome.ALLOW
