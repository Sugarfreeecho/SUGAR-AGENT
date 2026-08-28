"""Pure continuation decisions for the OpenAI Responses protocol."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .items import (
    CanonicalResponseItem,
    canonical_item_hash,
    canonical_items_hash,
    canonical_json,
)


REQUEST_SHAPE_SCHEMA_VERSION = 1
CONTINUATION_ANCHOR_SCHEMA_VERSION = 1

_EPHEMERAL_REQUEST_FIELDS = {
    "input",
    "messages",
    "metadata",
    "request_context",
    "stream",
    "timeout",
    "trace_id",
}


@dataclass(frozen=True)
class RequestShape:
    """Normalized fields whose change conservatively invalidates continuation."""

    issuer: str
    model: str
    instructions: str
    prompt_cache_key: str
    store: bool
    request_fields: Mapping[str, Any]
    serializer_version: int = 1
    schema_version: int = REQUEST_SHAPE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if int(self.schema_version) != REQUEST_SHAPE_SCHEMA_VERSION:
            raise ValueError("unsupported Responses request-shape schema")
        normalized = {
            str(key): value
            for key, value in self.request_fields.items()
            if str(key) not in _EPHEMERAL_REQUEST_FIELDS
        }
        # Round-trip through canonical JSON to detach mutable caller objects.
        import json

        object.__setattr__(self, "request_fields", json.loads(canonical_json(normalized)))

    @classmethod
    def from_request(
        cls,
        request: Mapping[str, Any],
        *,
        issuer: str,
        instructions: str,
        prompt_cache_key: str,
        store: bool,
        serializer_version: int = 1,
    ) -> "RequestShape":
        return cls(
            issuer=str(issuer or ""),
            model=str(request.get("model") or ""),
            instructions=str(instructions or ""),
            prompt_cache_key=str(prompt_cache_key or ""),
            store=bool(store),
            request_fields={
                str(key): value
                for key, value in request.items()
                if str(key) not in _EPHEMERAL_REQUEST_FIELDS
            },
            serializer_version=int(serializer_version),
        )

    @property
    def digest(self) -> str:
        return canonical_item_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "serializer_version": self.serializer_version,
            "issuer": self.issuer,
            "model": self.model,
            "instructions": self.instructions,
            "prompt_cache_key": self.prompt_cache_key,
            "store": self.store,
            "request_fields": dict(self.request_fields),
        }


@dataclass(frozen=True)
class ContinuationAnchor:
    schema_version: int
    issuer: str
    model: str
    response_id: str
    history_generation: int
    request_shape_hash: str
    covered_item_count: int
    covered_prefix_hash: str
    covered_item_hashes: tuple[str, ...]
    response_output_items: tuple[CanonicalResponseItem, ...]
    completed: bool
    server_stored: bool
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        response_id: str,
        history_generation: int,
        request_shape: RequestShape,
        request_items: Iterable[Mapping[str, Any]],
        response_output_items: Iterable[CanonicalResponseItem],
        completed: bool = True,
        server_stored: bool = True,
        created_at: str = "",
    ) -> "ContinuationAnchor":
        outputs = tuple(response_output_items)
        covered = [dict(item) for item in request_items]
        covered.extend(dict(item.raw_item) for item in outputs)
        return cls(
            schema_version=CONTINUATION_ANCHOR_SCHEMA_VERSION,
            issuer=request_shape.issuer,
            model=request_shape.model,
            response_id=str(response_id or ""),
            history_generation=int(history_generation),
            request_shape_hash=request_shape.digest,
            covered_item_count=len(covered),
            covered_prefix_hash=canonical_items_hash(covered),
            covered_item_hashes=tuple(canonical_item_hash(item) for item in covered),
            response_output_items=outputs,
            completed=bool(completed),
            server_stored=bool(server_stored),
            created_at=created_at
            or datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
        )

    @property
    def usable(self) -> bool:
        return bool(
            self.response_id
            and self.completed
            and self.server_stored
            and self.covered_item_count >= 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "issuer": self.issuer,
            "model": self.model,
            "response_id": self.response_id,
            "history_generation": self.history_generation,
            "request_shape_hash": self.request_shape_hash,
            "covered_item_count": self.covered_item_count,
            "covered_prefix_hash": self.covered_prefix_hash,
            "covered_item_hashes": list(self.covered_item_hashes),
            "response_output_items": [item.to_dict() for item in self.response_output_items],
            "completed": self.completed,
            "server_stored": self.server_stored,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ContinuationAnchor":
        version = int(value.get("schema_version") or 0)
        if version != CONTINUATION_ANCHOR_SCHEMA_VERSION:
            raise ValueError("unsupported Responses continuation-anchor schema")
        return cls(
            schema_version=version,
            issuer=str(value.get("issuer") or ""),
            model=str(value.get("model") or ""),
            response_id=str(value.get("response_id") or ""),
            history_generation=int(value.get("history_generation") or 0),
            request_shape_hash=str(value.get("request_shape_hash") or ""),
            covered_item_count=int(value.get("covered_item_count") or 0),
            covered_prefix_hash=str(value.get("covered_prefix_hash") or ""),
            covered_item_hashes=tuple(
                str(item) for item in value.get("covered_item_hashes") or []
            ),
            response_output_items=tuple(
                CanonicalResponseItem.from_dict(item)
                for item in value.get("response_output_items") or []
            ),
            completed=bool(value.get("completed")),
            server_stored=bool(value.get("server_stored")),
            created_at=str(value.get("created_at") or ""),
        )


@dataclass(frozen=True)
class ContinuationDecision:
    use_previous_response: bool
    reason: str
    suffix_items: tuple[Mapping[str, Any], ...] = ()


def evaluate_continuation(
    anchor: ContinuationAnchor | None,
    *,
    current_items: Iterable[Mapping[str, Any]],
    request_shape: RequestShape,
    history_generation: int,
) -> ContinuationDecision:
    items = tuple(dict(item) for item in current_items)
    if anchor is None:
        return ContinuationDecision(False, "no_anchor")
    if not anchor.usable:
        return ContinuationDecision(False, "anchor_not_usable")
    if anchor.issuer != request_shape.issuer or anchor.model != request_shape.model:
        return ContinuationDecision(False, "issuer_changed")
    if anchor.history_generation != int(history_generation):
        return ContinuationDecision(False, "history_generation_changed")
    if anchor.request_shape_hash != request_shape.digest:
        return ContinuationDecision(False, "request_shape_changed")
    if len(items) < anchor.covered_item_count:
        return ContinuationDecision(False, "history_shortened")
    prefix = items[: anchor.covered_item_count]
    if canonical_items_hash(prefix) != anchor.covered_prefix_hash:
        return ContinuationDecision(False, "prefix_mismatch")
    if tuple(canonical_item_hash(item) for item in prefix) != anchor.covered_item_hashes:
        return ContinuationDecision(False, "prefix_structure_mismatch")
    return ContinuationDecision(
        True,
        "matched",
        tuple(items[anchor.covered_item_count :]),
    )


__all__ = [
    "CONTINUATION_ANCHOR_SCHEMA_VERSION",
    "REQUEST_SHAPE_SCHEMA_VERSION",
    "ContinuationAnchor",
    "ContinuationDecision",
    "RequestShape",
    "evaluate_continuation",
]
