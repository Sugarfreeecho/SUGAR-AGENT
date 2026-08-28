"""Canonical, lossless envelopes for Responses input and output items."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


CANONICAL_ITEM_SCHEMA_VERSION = 1


class Replayability(str, Enum):
    """How safely a captured provider item can be sent as future input."""

    NATIVE = "native"
    RECONSTRUCTED = "reconstructed"
    OPAQUE = "opaque"
    UNSUPPORTED = "unsupported"


def _plain_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _plain_json(asdict(value))
    if isinstance(value, Mapping):
        return {
            str(key): _plain_json(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _plain_json(model_dump(exclude_none=True))
        except TypeError:
            return _plain_json(model_dump())
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _plain_json(to_dict())
    if hasattr(value, "__dict__"):
        return {
            str(key): _plain_json(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(
        _plain_json(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_item_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def canonical_items_hash(values: Iterable[Any]) -> str:
    return canonical_item_hash([_plain_json(value) for value in values])


@dataclass(frozen=True)
class CanonicalResponseItem:
    """A provider item plus the metadata needed for safe future replay.

    ``raw_item`` is the durable fact.  ``replayability`` is a serializer
    decision and must never cause an unsupported item to be silently dropped.
    """

    raw_item: Mapping[str, Any]
    issuer: str = ""
    replayability: Replayability = Replayability.NATIVE
    schema_version: int = CANONICAL_ITEM_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if int(self.schema_version) != CANONICAL_ITEM_SCHEMA_VERSION:
            raise ValueError("unsupported canonical Responses item schema")
        plain = _plain_json(self.raw_item)
        if not isinstance(plain, dict) or not str(plain.get("type") or "").strip():
            raise ValueError("canonical Responses item requires an object with type")
        object.__setattr__(self, "raw_item", plain)
        object.__setattr__(self, "issuer", str(self.issuer or ""))
        object.__setattr__(
            self,
            "replayability",
            Replayability(self.replayability),
        )

    @property
    def item_type(self) -> str:
        return str(self.raw_item.get("type") or "")

    @property
    def digest(self) -> str:
        return canonical_item_hash(self.raw_item)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "issuer": self.issuer,
            "replayability": self.replayability.value,
            "raw_item": dict(self.raw_item),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CanonicalResponseItem":
        return cls(
            schema_version=int(value.get("schema_version") or 0),
            issuer=str(value.get("issuer") or ""),
            replayability=Replayability(
                str(value.get("replayability") or Replayability.NATIVE.value)
            ),
            raw_item=value.get("raw_item") or {},
        )


def canonicalize_response_items(
    values: Iterable[Any],
    *,
    issuer: str,
    replayability: Replayability = Replayability.NATIVE,
) -> tuple[CanonicalResponseItem, ...]:
    items = []
    for value in values:
        plain = _plain_json(value)
        if not isinstance(plain, dict) or not plain.get("type"):
            raise ValueError("Responses item list contains an item without type")
        items.append(
            CanonicalResponseItem(
                raw_item=plain,
                issuer=issuer,
                replayability=replayability,
            )
        )
    return tuple(items)


__all__ = [
    "CANONICAL_ITEM_SCHEMA_VERSION",
    "CanonicalResponseItem",
    "Replayability",
    "canonical_item_hash",
    "canonical_items_hash",
    "canonicalize_response_items",
    "canonical_json",
]
