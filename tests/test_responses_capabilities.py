from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


from llm.responses import (
    ResponsesCapabilityCache,
    ResponsesErrorKind,
    classify_responses_error,
)


class _ProviderError(RuntimeError):
    def __init__(self, message, *, status_code=400, body=None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body or {}


def test_structured_error_classification_separates_state_include_and_transient():
    previous = classify_responses_error(
        _ProviderError(
            "bad request",
            body={
                "error": {
                    "param": "previous_response_id",
                    "code": "response_not_found",
                    "type": "invalid_request_error",
                    "message": "Referenced response not found or expired",
                }
            },
        )
    )
    include = classify_responses_error(
        _ProviderError(
            "bad request",
            body={
                "error": {
                    "param": "include",
                    "type": "invalid_request_error",
                    "message": "Unsupported value reasoning.encrypted_content",
                }
            },
        )
    )
    transient = classify_responses_error(
        _ProviderError("upstream unavailable", status_code=503)
    )

    assert previous.kind is ResponsesErrorKind.INVALID_PREVIOUS
    assert include.kind is ResponsesErrorKind.UNSUPPORTED_ENCRYPTED_REASONING
    assert transient.kind is ResponsesErrorKind.TRANSIENT


def test_capability_cache_updates_independent_fields_and_can_be_cleared():
    cache = ResponsesCapabilityCache(ttl_seconds=60)

    initial = cache.get("issuer-1")
    updated = cache.update(
        "issuer-1",
        store=False,
        previous_response_id=False,
        websocket=False,
    )

    assert initial.store is None
    assert updated.store is False
    assert updated.websocket is False
    assert updated.encrypted_reasoning_replay is None
    cache.clear("issuer-1")
    assert cache.get("issuer-1").store is None
