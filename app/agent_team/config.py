"""Feature configuration for the experimental Agent Team runtime."""

from __future__ import annotations

import os
from collections.abc import Mapping


AGENT_TEAM_ENV_VAR = "AGENT_TEAM_ENABLED"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


class AgentTeamDisabledError(RuntimeError):
    """Raised when an Agent Team operation is attempted while disabled."""


def agent_team_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Return whether Agent Team is explicitly enabled.

    The feature is fail-closed: unset, empty, malformed, and unexpected values
    all mean disabled.  ``environ`` is injectable to keep policy tests isolated
    from the process environment.
    """

    source = os.environ if environ is None else environ
    raw = source.get(AGENT_TEAM_ENV_VAR, "0")
    return str(raw or "").strip().lower() in _TRUE_VALUES


def require_agent_team_enabled(environ: Mapping[str, str] | None = None) -> None:
    """Reject an Agent Team operation unless the feature is explicitly on."""

    if not agent_team_enabled(environ):
        raise AgentTeamDisabledError(
            "Agent Team is disabled. Set AGENT_TEAM_ENABLED=1 to enable it."
        )
