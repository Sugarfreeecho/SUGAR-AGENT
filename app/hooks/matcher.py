"""Deterministic regex matching for hook registrations."""
from __future__ import annotations

import re
from typing import Any, Mapping


_MATCH_FIELDS = (
    "matcher_value",
    "tool_name",
    "tool",
    "agent_name",
    "subagent_name",
    "name",
    "goal_status",
    "status",
    "session_id",
)


def hook_match_value(payload: Mapping[str, Any]) -> str:
    """Choose the stable subject used by a hook's matcher regex."""

    for field in _MATCH_FIELDS:
        value = payload.get(field)
        if value is not None and str(value):
            return str(value)
    return ""


def hook_matches(matcher: str, payload: Mapping[str, Any]) -> bool:
    """Return true for an empty matcher or a regex search match.

    ``*`` is accepted as a friendly alias for ``.*`` because it is commonly
    used by plugin formats even though it is not a standalone valid regex.
    Regex validation normally happens at configuration-load time.
    """

    matcher = str(matcher or "")
    if not matcher or matcher == "*":
        return True
    return re.search(matcher, hook_match_value(payload)) is not None
