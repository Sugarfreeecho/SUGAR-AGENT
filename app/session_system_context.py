"""Session-owned instructions, kept outside the compressible model history."""

import hashlib
from typing import Any, Iterable, Mapping


MAX_SYSTEM_CONTEXT_BYTES = 256 * 1024
SYSTEM_CONTEXT_HEADING = "## Session system context\n\n"


def normalize_system_context(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("system_context must be a string")
    if len(value.encode("utf-8")) > MAX_SYSTEM_CONTEXT_BYTES:
        raise ValueError("system_context must not exceed 256 KiB of UTF-8 text")
    return value if value.strip() else ""


def effective_system_context(metadata: Mapping[str, Any]) -> str:
    inherited = metadata.get("fork_runtime_config")
    fallback = inherited.get("system_context", "") if isinstance(inherited, dict) else ""
    return normalize_system_context(metadata.get("system_context", fallback))


def normalize_system_context_mode(value: Any) -> str:
    if value not in ("append", "replace"):
        raise ValueError("system_context_mode must be append or replace")
    return value


def effective_system_context_mode(metadata: Mapping[str, Any]) -> str:
    inherited = metadata.get("fork_runtime_config")
    fallback = inherited.get("system_context_mode", "append") if isinstance(inherited, dict) else "append"
    return normalize_system_context_mode(metadata.get("system_context_mode", fallback))


def validate_system_context(context: Any, mode: Any) -> tuple[str, str]:
    context, mode = normalize_system_context(context), normalize_system_context_mode(mode)
    if mode == "replace" and not context:
        raise ValueError("replacement system context must not be empty")
    return context, mode


def system_context_revision(metadata: Mapping[str, Any]) -> str:
    value = effective_system_context_mode(metadata) + "\0" + effective_system_context(metadata)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def assemble_session_system_segments(
    base_segments: Iterable[str], env_static: str, metadata: Mapping[str, Any],
) -> tuple[str, ...]:
    """Use the same session prefix for model requests and token previews.

    Fork snapshots include their original session context. Remove that exact
    segment before applying the child's current value, including explicit clear.
    """
    context, mode = validate_system_context(effective_system_context(metadata), effective_system_context_mode(metadata))
    if mode == "replace":
        segments = (context, env_static) if env_static.strip() else (context,)
        if metadata.get("is_subagent"):
            from agent_subagent import SUBAGENT_RUN_INSTRUCTION
            segments = ("## Subagent 运行约束\n\n" + SUBAGENT_RUN_INSTRUCTION.strip(), *segments)
        return segments
    segments = tuple(base_segments)
    fork = metadata.get("fork_runtime_config")
    inherited = fork.get("system_segments") if isinstance(fork, dict) else None
    if (isinstance(inherited, list) and inherited and all(isinstance(x, str) for x in inherited)
            and effective_system_context_mode(fork) != "replace"):
        old_context = normalize_system_context(fork.get("system_context", ""))
        old_segment = SYSTEM_CONTEXT_HEADING + old_context if old_context else None
        segments = tuple(
            env_static if item.lstrip().startswith("## Environment") else item
            for item in inherited if item != old_segment
        )
    elif metadata.get("is_subagent"):
        from agent_subagent import SUBAGENT_RUN_INSTRUCTION

        segments = ("## Subagent 运行约束\n\n" + SUBAGENT_RUN_INSTRUCTION.strip(), *segments)
    return (*segments, SYSTEM_CONTEXT_HEADING + context) if context else segments
