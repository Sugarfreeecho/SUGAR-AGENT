"""Session-scoped progressive tool disclosure without provider extensions.

Schemas are hidden only after authorization/profile filtering. The call bridge
never executes a tool itself: the loop decodes it before policy selection and
uses the existing hooks, approval, audit and invocation pipeline.
"""
from __future__ import annotations

import json
import copy
import logging
import math
import os
import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from tool_registry import ToolInvocationKind, ToolRegistry

logger = logging.getLogger(__name__)
BRIDGE_NAMES = frozenset({"tool_search", "tool_describe", "tool_call"})
CONFIG_PATH = Path(__file__).resolve().parents[1] / ".sugaragent" / "tool_search.json"
_config_lock = threading.RLock()
_config_cache: tuple[Any, Any] | None = None


@dataclass(frozen=True)
class ToolSearchConfig:
    # Missing/deleted config restores the original tool catalog.
    enabled: str = "off"
    threshold_pct: float = 10.0
    threshold_tokens: int = 20_000
    search_default_limit: int = 5
    max_search_limit: int = 20
    defer_plugin_tools: bool = False
    pinned_tools: tuple[str, ...] = ()

    @classmethod
    def parse(cls, raw: Any) -> "ToolSearchConfig":
        if not isinstance(raw, dict):
            raise ValueError("tool search config must be an object")
        unknown = set(raw) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError("unknown tool search setting: " + ", ".join(sorted(unknown)))
        value = asdict(cls()) | raw
        if value["enabled"] not in {"on", "off", "auto"}:
            raise ValueError("enabled must be on, off or auto")
        pct = value["threshold_pct"]
        if isinstance(pct, bool) or not isinstance(pct, (int, float)) or not math.isfinite(pct) or not 0 < pct <= 100:
            raise ValueError("threshold_pct must be between 0 and 100")
        for key in ("threshold_tokens", "search_default_limit", "max_search_limit"):
            if type(value[key]) is not int or value[key] <= 0:
                raise ValueError(key + " must be a positive integer")
        if not 1 <= value["search_default_limit"] <= value["max_search_limit"] <= 50:
            raise ValueError("search limits must satisfy 1 <= default <= max <= 50")
        if type(value["defer_plugin_tools"]) is not bool:
            raise ValueError("defer_plugin_tools must be boolean")
        pins = value["pinned_tools"]
        if not isinstance(pins, (list, tuple)) or any(not isinstance(name, str) or not name.strip() for name in pins):
            raise ValueError("pinned_tools must be an array of non-empty tool names")
        value["pinned_tools"] = tuple(dict.fromkeys(name.strip() for name in pins))
        return cls(**value)


def config_revision() -> tuple[Any, ...]:
    try:
        stat = CONFIG_PATH.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        signature = None
    return (str(CONFIG_PATH), signature, os.getenv("MYAGENT_TOOL_SEARCH", ""))


def load_config() -> ToolSearchConfig:
    global _config_cache
    revision = config_revision()
    with _config_lock:
        if _config_cache is not None and _config_cache[0] == revision:
            return _config_cache[1]
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            config = ToolSearchConfig.parse(raw)
        except FileNotFoundError:
            config = ToolSearchConfig()
        except (OSError, ValueError, TypeError):
            logger.warning("Invalid tool search config; using full catalog", exc_info=True)
            config = ToolSearchConfig()
        # Explicit off in the file wins even over an environment override.
        override = revision[-1].strip().lower()
        if override in {"on", "off", "auto"} and config.enabled != "off":
            config = ToolSearchConfig.parse(asdict(config) | {"enabled": override})
        _config_cache = (revision, config)
        return config


def save_config(raw: Any) -> ToolSearchConfig:
    global _config_cache
    config = ToolSearchConfig.parse(raw)
    with _config_lock:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_PATH.with_name(f".tool-search-{os.getpid()}-{threading.get_ident()}.tmp")
        try:
            tmp.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            tmp.replace(CONFIG_PATH)
        finally:
            tmp.unlink(missing_ok=True)
        _config_cache = None
    return config


def should_activate(config: ToolSearchConfig, tokens: int, context_window: int | None) -> bool:
    if config.enabled == "off" or tokens <= 0:
        return False
    if config.enabled == "on":
        return True
    # A large context window should not force tens of thousands of schema
    # tokens into every request. The absolute budget caps the relative budget.
    threshold = config.threshold_tokens
    if context_window and context_window > 0:
        threshold = min(threshold, max(1, math.ceil(context_window * config.threshold_pct / 100)))
    return tokens >= threshold


def bridge_definitions() -> list[dict]:
    def definition(name, description, properties, required):
        return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required,
                           "additionalProperties": False}}}
    name = {"type": "string", "description": "Exact name returned by tool_search."}
    return [
        definition("tool_search", "Find enabled external tools by task keywords. Use select:name1,name2 for exact names or +term for required words. Returns names and summaries; use tool_describe to obtain the complete schema before calling.",
                   {"query": {"type": "string"}, "max_results": {"type": "integer", "minimum": 1, "maximum": 50}}, ["query"]),
        definition("tool_describe", "Get the full input schema of an enabled deferred tool. Then invoke it through tool_call.", {"name": name}, ["name"]),
        definition("tool_call", "Invoke an enabled deferred tool using its exact name and arguments matching tool_describe. The target tool's normal permissions and approvals apply. Cannot invoke these bridge tools.",
                   {"name": name, "arguments": {"type": "object", "additionalProperties": True}}, ["name", "arguments"]),
    ]


def _terms(text: str) -> list[str]:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return re.findall(r"[a-z0-9]+|[\u3400-\u9fff]", text.lower())


class ToolDisclosure:
    def __init__(self, registry: ToolRegistry, names: frozenset[str], config: ToolSearchConfig):
        self.names = names
        self.config = config
        self.catalog = {name: registry.require(name).openai_definition() for name in sorted(names)}
        self.sources = {name: registry.require(name).owner for name in names}
        self.stats: dict[str, int] = {}

    def search(self, arguments: Mapping[str, Any]) -> dict:
        query = arguments.get("query")
        limit = arguments.get("max_results", self.config.search_default_limit)
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if type(limit) is not int or limit <= 0:
            raise ValueError("max_results must be a positive integer")
        limit = min(limit, self.config.max_search_limit)
        query = query.strip()
        if query.startswith("select:"):
            requested = list(dict.fromkeys(n.strip() for n in query[7:].split(",") if n.strip()))
            matches = [n for n in requested if n in self.catalog]
        else:
            required = [_terms(term) for term in re.findall(r"\+([^\s]+)", query)]
            terms = _terms(query)
            scores = []
            for name, definition in self.catalog.items():
                function = definition["function"]
                name_terms = set(_terms(name))
                text_terms = set(_terms(function.get("description", "") + " " + self.sources[name]))
                all_terms = name_terms | text_terms
                if any(not set(term).issubset(all_terms) for term in required):
                    continue
                score = sum(6 * (term in name_terms) + (term in text_terms) for term in terms)
                if score:
                    scores.append((-score, name))
            matches = [name for _, name in sorted(scores)]
        return {"tools": [{"name": name, "description": self.catalog[name]["function"].get("description", "")[:400],
                           "source": self.sources[name]} for name in matches[:limit]],
                "total_matches": len(matches), "next": "Use tool_describe(name), then tool_call(name, arguments)."}

    def describe(self, arguments: Mapping[str, Any]) -> dict:
        name = arguments.get("name")
        if not isinstance(name, str) or name not in self.names:
            raise ValueError("Unknown or unavailable deferred tool; use tool_search to find enabled tools")
        return json.loads(json.dumps(self.catalog[name], ensure_ascii=False))


def assemble(registry: ToolRegistry, *, context_window: int | None, pinned_names=(), config=None) -> None:
    from agent_tokenizer import count_tool_definition_tokens

    config = config or load_config()
    if config.enabled == "off":
        return
    if any(name in registry for name in BRIDGE_NAMES):
        logger.warning("Tool search bridge name conflict; retaining full catalog")
        return
    pinned = frozenset(pinned_names) | frozenset(config.pinned_tools)
    names = frozenset(d.name for d in registry.descriptors() if d.executable and d.name not in pinned and (
        d.invocation_kind is ToolInvocationKind.MCP or
        d.owner == "computer-use" or
        (config.defer_plugin_tools and (d.invocation_kind is ToolInvocationKind.PLUGIN or
            (d.invocation_kind is ToolInvocationKind.HOST_SERVICE and not d.owner.startswith("core."))))
    ))
    deferred = [registry.require(name).openai_definition() for name in sorted(names)]
    deferred_tokens = count_tool_definition_tokens(deferred)
    if not names or not should_activate(config, deferred_tokens, context_window):
        return
    before = count_tool_definition_tokens(registry.definitions())
    disclosure = ToolDisclosure(registry, names, config)
    for definition in bridge_definitions():
        name = definition["function"]["name"]
        registry.register_definition(definition, invocation_kind=ToolInvocationKind.HOST_SERVICE,
            owner="core.tool_search", invoker_id=name, effect="read" if name != "tool_call" else "control",
            parallel_safe=name != "tool_call", early_stream_safe=False,
            interruptibility="safe" if name != "tool_call" else "non_interruptible")
    registry.model_names = registry.names() - names
    after = count_tool_definition_tokens(registry.definitions())
    disclosure.stats = {"deferred_tools_count": len(names), "deferred_tools_tokens": deferred_tokens,
                        "saved_tools_tokens": max(0, before - after)}
    registry.disclosure = disclosure


def resolve_call(registry: ToolRegistry, tool_call: Mapping[str, Any]) -> dict:
    """Return an execution copy; preserve the original assistant tool message."""
    call = dict(tool_call)
    if call.get("name") != "tool_call":
        return call
    disclosure = registry.disclosure
    if disclosure is None:
        raise ValueError("Tool search is inactive")
    args = call.get("args")
    if not isinstance(args, dict):
        raise ValueError("tool_call arguments must be an object")
    name = args.get("name")
    if not isinstance(name, str) or name in BRIDGE_NAMES or name not in disclosure.names:
        raise ValueError("Unknown or unavailable deferred tool; use tool_search to find enabled tools")
    arguments = args.get("arguments")
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object matching tool_describe")
    descriptor = registry.resolve(name)
    if descriptor is None or not descriptor.executable:
        raise ValueError("Deferred tool is unavailable")
    call.update(name=name, args=copy.deepcopy(arguments), _bridge_call={"name": "tool_call", "target": name})
    return call


def call_descriptor(registry: ToolRegistry, tool_call: Mapping[str, Any]):
    if registry.disclosure is None:
        return registry.resolve(str(tool_call.get("name") or ""))
    try:
        return registry.resolve(str(resolve_call(registry, tool_call).get("name") or ""))
    except ValueError:
        return None
