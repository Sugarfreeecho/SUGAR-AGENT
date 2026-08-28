"""State and serialization primitives for the OpenAI Responses protocol."""

from .items import (
    CanonicalResponseItem,
    Replayability,
    canonical_item_hash,
    canonical_items_hash,
    canonicalize_response_items,
)
from .state import (
    ContinuationAnchor,
    ContinuationDecision,
    RequestShape,
    evaluate_continuation,
)
from .capabilities import (
    ProviderCapabilities,
    ResponsesCapabilityCache,
    ResponsesErrorInfo,
    ResponsesErrorKind,
    classify_responses_error,
    responses_capability_cache,
)
from .compact import CompactionMatch, ResponsesCompactionCheckpoint

__all__ = [
    "CanonicalResponseItem",
    "ContinuationAnchor",
    "ContinuationDecision",
    "Replayability",
    "RequestShape",
    "canonical_item_hash",
    "canonical_items_hash",
    "canonicalize_response_items",
    "evaluate_continuation",
    "ProviderCapabilities",
    "ResponsesCapabilityCache",
    "ResponsesErrorInfo",
    "ResponsesErrorKind",
    "classify_responses_error",
    "responses_capability_cache",
    "CompactionMatch",
    "ResponsesCompactionCheckpoint",
]
