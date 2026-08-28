"""Provider-scoped checkpoints returned by ``POST /responses/compact``."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .items import (
    CanonicalResponseItem,
    Replayability,
    canonical_item_hash,
    canonical_items_hash,
)


COMPACTION_CHECKPOINT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CompactionMatch:
    matched: bool
    reason: str
    suffix_items: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class ResponsesCompactionCheckpoint:
    schema_version: int
    issuer: str
    model: str
    source_history_generation: int
    covered_item_count: int
    covered_prefix_hash: str
    covered_item_hashes: tuple[str, ...]
    compacted_output_items: tuple[CanonicalResponseItem, ...]
    usage: Mapping[str, int]
    source_estimated_tokens: int
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        issuer: str,
        model: str,
        source_history_generation: int,
        source_items: Iterable[Mapping[str, Any]],
        compacted_output_items: Iterable[Mapping[str, Any]],
        usage: Mapping[str, int] | None = None,
        source_estimated_tokens: int = 0,
        created_at: str = "",
    ) -> "ResponsesCompactionCheckpoint":
        source = tuple(dict(item) for item in source_items)
        output = []
        saw_compaction = False
        for item in compacted_output_items:
            raw = dict(item)
            item_type = str(raw.get("type") or "")
            if not item_type:
                raise ValueError("compacted Responses output item requires type")
            is_compaction = item_type == "compaction"
            saw_compaction = saw_compaction or is_compaction
            output.append(
                CanonicalResponseItem(
                    raw_item=raw,
                    issuer=issuer,
                    replayability=(
                        Replayability.OPAQUE if is_compaction else Replayability.NATIVE
                    ),
                )
            )
        if not saw_compaction:
            raise ValueError("compacted Responses output has no compaction item")
        return cls(
            schema_version=COMPACTION_CHECKPOINT_SCHEMA_VERSION,
            issuer=str(issuer or ""),
            model=str(model or ""),
            source_history_generation=int(source_history_generation),
            covered_item_count=len(source),
            covered_prefix_hash=canonical_items_hash(source),
            covered_item_hashes=tuple(canonical_item_hash(item) for item in source),
            compacted_output_items=tuple(output),
            usage={str(key): int(value or 0) for key, value in dict(usage or {}).items()},
            source_estimated_tokens=max(0, int(source_estimated_tokens or 0)),
            created_at=created_at
            or datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
        )

    def match(
        self,
        *,
        issuer: str,
        model: str,
        history_generation: int,
        current_items: Iterable[Mapping[str, Any]],
    ) -> CompactionMatch:
        items = tuple(dict(item) for item in current_items)
        if self.issuer != str(issuer or "") or self.model != str(model or ""):
            return CompactionMatch(False, "issuer_changed")
        if self.source_history_generation != int(history_generation):
            return CompactionMatch(False, "history_generation_changed")
        if len(items) < self.covered_item_count:
            return CompactionMatch(False, "history_shortened")
        prefix = items[: self.covered_item_count]
        if canonical_items_hash(prefix) != self.covered_prefix_hash:
            return CompactionMatch(False, "prefix_mismatch")
        if tuple(canonical_item_hash(item) for item in prefix) != self.covered_item_hashes:
            return CompactionMatch(False, "prefix_structure_mismatch")
        return CompactionMatch(True, "matched", items[self.covered_item_count :])

    def wire_items(self, suffix: Iterable[Mapping[str, Any]] = ()) -> list[dict[str, Any]]:
        return [
            *(dict(item.raw_item) for item in self.compacted_output_items),
            *(dict(item) for item in suffix),
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "issuer": self.issuer,
            "model": self.model,
            "source_history_generation": self.source_history_generation,
            "covered_item_count": self.covered_item_count,
            "covered_prefix_hash": self.covered_prefix_hash,
            "covered_item_hashes": list(self.covered_item_hashes),
            "compacted_output_items": [item.to_dict() for item in self.compacted_output_items],
            "usage": dict(self.usage),
            "source_estimated_tokens": self.source_estimated_tokens,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ResponsesCompactionCheckpoint":
        version = int(value.get("schema_version") or 0)
        if version != COMPACTION_CHECKPOINT_SCHEMA_VERSION:
            raise ValueError("unsupported Responses compaction checkpoint schema")
        return cls(
            schema_version=version,
            issuer=str(value.get("issuer") or ""),
            model=str(value.get("model") or ""),
            source_history_generation=int(value.get("source_history_generation") or 0),
            covered_item_count=int(value.get("covered_item_count") or 0),
            covered_prefix_hash=str(value.get("covered_prefix_hash") or ""),
            covered_item_hashes=tuple(
                str(item) for item in value.get("covered_item_hashes") or []
            ),
            compacted_output_items=tuple(
                CanonicalResponseItem.from_dict(item)
                for item in value.get("compacted_output_items") or []
            ),
            usage={
                str(key): int(item or 0)
                for key, item in dict(value.get("usage") or {}).items()
            },
            source_estimated_tokens=int(value.get("source_estimated_tokens") or 0),
            created_at=str(value.get("created_at") or ""),
        )


__all__ = [
    "COMPACTION_CHECKPOINT_SCHEMA_VERSION",
    "CompactionMatch",
    "ResponsesCompactionCheckpoint",
]
