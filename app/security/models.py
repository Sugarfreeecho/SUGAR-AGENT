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
