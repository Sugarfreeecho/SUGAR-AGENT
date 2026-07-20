"""Agent Team control-plane primitives.

The package is intentionally isolated from the existing ``task`` subagent
runtime.  Importing it never enables Agent Team; every mutating entrypoint must
pass through :func:`require_agent_team_enabled`.
"""

from .config import (
    AGENT_TEAM_ENV_VAR,
    AgentTeamDisabledError,
    agent_team_enabled,
    require_agent_team_enabled,
)
from .models import (
    AgentTeamConflictError,
    AgentTeamError,
    AgentTeamNotFoundError,
    AgentTeamValidationError,
    TeamLimits,
)
from .service import AgentTeamService
from .store import RuntimeTeamStore

__all__ = [
    "AGENT_TEAM_ENV_VAR",
    "AgentTeamDisabledError",
    "agent_team_enabled",
    "require_agent_team_enabled",
    "AgentTeamError",
    "AgentTeamValidationError",
    "AgentTeamNotFoundError",
    "AgentTeamConflictError",
    "TeamLimits",
    "AgentTeamService",
    "RuntimeTeamStore",
]
