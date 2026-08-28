"""Generic workspace-write lease policy for coordinated child sessions."""
from agent_team.policy import acquire_workspace_write_lock, workspace_write_lock

__all__ = ["acquire_workspace_write_lock", "workspace_write_lock"]
