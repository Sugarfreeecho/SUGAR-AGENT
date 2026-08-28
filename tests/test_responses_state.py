from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


from llm.responses import (
    CanonicalResponseItem,
    ContinuationAnchor,
    Replayability,
    RequestShape,
    ResponsesCompactionCheckpoint,
    canonicalize_response_items,
    evaluate_continuation,
)
from llm.types import LLMRequestContext, LLMRequestPurpose


def _shape(**overrides):
    request = {
        "model": "gpt-test",
        "tools": [{"type": "function", "name": "ls"}],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
        "max_tokens": 256,
        "timeout": 30,
    }
    request.update(overrides.pop("request", {}))
    return RequestShape.from_request(
        request,
        issuer=overrides.pop("issuer", "issuer-1"),
        instructions=overrides.pop("instructions", "rules"),
        prompt_cache_key=overrides.pop("prompt_cache_key", "session-key"),
        store=overrides.pop("store", True),
        **overrides,
    )


def _anchor():
    output = CanonicalResponseItem(
        raw_item={
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "first answer"}],
        },
        issuer="issuer-1",
    )
    return ContinuationAnchor.create(
        response_id="resp_1",
        history_generation=4,
        request_shape=_shape(),
        request_items=[{"role": "user", "content": "first"}],
        response_output_items=[output],
        created_at="2026-08-25T00:00:00.000Z",
    )


def test_canonical_item_preserves_unknown_provider_shape_and_round_trips():
    item = CanonicalResponseItem(
        raw_item={"type": "future.provider_item", "nested": {"b": 2, "a": 1}},
        issuer="issuer-1",
        replayability=Replayability.UNSUPPORTED,
    )

    restored = CanonicalResponseItem.from_dict(item.to_dict())

    assert restored == item
    assert restored.item_type == "future.provider_item"
    assert restored.replayability is Replayability.UNSUPPORTED
    assert restored.digest == item.digest


def test_canonicalize_response_items_rejects_silent_item_loss():
    with pytest.raises(ValueError, match="without type"):
        canonicalize_response_items([{"id": "missing-type"}], issuer="issuer-1")


def test_continuation_accepts_only_strict_append_and_returns_suffix():
    anchor = _anchor()
    current = [
        {"role": "user", "content": "first"},
        dict(anchor.response_output_items[0].raw_item),
        {"role": "user", "content": "second"},
    ]

    decision = evaluate_continuation(
        anchor,
        current_items=current,
        request_shape=_shape(),
        history_generation=4,
    )

    assert decision.use_previous_response is True
    assert decision.reason == "matched"
    assert decision.suffix_items == ({"role": "user", "content": "second"},)


@pytest.mark.parametrize(
    ("current", "shape", "generation", "reason"),
    [
        (
            [
                {"role": "user", "content": "rewritten"},
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "first answer"}],
                },
            ],
            None,
            4,
            "prefix_mismatch",
        ),
        (None, _shape(instructions="new rules"), 4, "request_shape_changed"),
        (None, None, 5, "history_generation_changed"),
        (None, _shape(issuer="issuer-2"), 4, "issuer_changed"),
    ],
)
def test_continuation_rejects_mutation_shape_generation_and_issuer_changes(
    current, shape, generation, reason
):
    anchor = _anchor()
    if current is None:
        current = [
            {"role": "user", "content": "first"},
            dict(anchor.response_output_items[0].raw_item),
        ]

    decision = evaluate_continuation(
        anchor,
        current_items=current,
        request_shape=shape or _shape(),
        history_generation=generation,
    )

    assert decision.use_previous_response is False
    assert decision.reason == reason


def test_anchor_round_trip_preserves_prefix_proof_and_output_items():
    anchor = _anchor()

    restored = ContinuationAnchor.from_dict(anchor.to_dict())

    assert restored == anchor
    assert restored.usable is True


def test_failed_or_unstored_anchor_is_never_used():
    base = _anchor().to_dict()
    base["completed"] = False
    failed = ContinuationAnchor.from_dict(base)
    decision = evaluate_continuation(
        failed,
        current_items=[],
        request_shape=_shape(),
        history_generation=4,
    )
    assert decision.reason == "anchor_not_usable"

    base["completed"] = True
    base["server_stored"] = False
    unstored = ContinuationAnchor.from_dict(base)
    decision = evaluate_continuation(
        unstored,
        current_items=[],
        request_shape=_shape(),
        history_generation=4,
    )
    assert decision.reason == "anchor_not_usable"


def test_session_prompt_cache_key_is_stable_across_generation_but_namespaced():
    first = LLMRequestContext(
        session_id="session-1",
        history_generation=1,
        purpose=LLMRequestPurpose.MAIN,
    )
    rewritten = LLMRequestContext(
        session_id="session-1",
        history_generation=9,
        purpose=LLMRequestPurpose.MAIN,
    )

    key = first.prompt_cache_key(issuer="issuer-1", model="gpt-test")

    assert key == rewritten.prompt_cache_key(issuer="issuer-1", model="gpt-test")
    assert key != first.prompt_cache_key(issuer="issuer-2", model="gpt-test")
    assert key != LLMRequestContext(
        session_id="session-1",
        purpose=LLMRequestPurpose.GOAL_JUDGE,
    ).prompt_cache_key(issuer="issuer-1", model="gpt-test")


def test_compaction_checkpoint_round_trip_matches_only_strict_append():
    source = [{"role": "user", "content": "first"}]
    checkpoint = ResponsesCompactionCheckpoint.create(
        issuer="issuer-1",
        model="gpt-test",
        source_history_generation=4,
        source_items=source,
        compacted_output_items=[
            {"type": "message", "role": "user", "content": "first"},
            {"type": "compaction", "encrypted_content": "opaque"},
        ],
        usage={"completion_tokens": 24},
        source_estimated_tokens=120,
        created_at="2026-08-25T00:00:00.000Z",
    )

    restored = ResponsesCompactionCheckpoint.from_dict(checkpoint.to_dict())
    match = restored.match(
        issuer="issuer-1",
        model="gpt-test",
        history_generation=4,
        current_items=[*source, {"role": "user", "content": "second"}],
    )

    assert restored == checkpoint
    assert match.matched is True
    assert match.suffix_items == ({"role": "user", "content": "second"},)
    assert restored.compacted_output_items[-1].replayability is Replayability.OPAQUE
    assert restored.wire_items(match.suffix_items)[-1]["content"] == "second"


@pytest.mark.parametrize(
    ("issuer", "model", "generation", "items", "reason"),
    [
        ("issuer-2", "gpt-test", 4, None, "issuer_changed"),
        ("issuer-1", "other", 4, None, "issuer_changed"),
        ("issuer-1", "gpt-test", 5, None, "history_generation_changed"),
        (
            "issuer-1",
            "gpt-test",
            4,
            [{"role": "user", "content": "rewritten"}],
            "prefix_mismatch",
        ),
    ],
)
def test_compaction_checkpoint_rejects_wrong_scope_or_mutated_prefix(
    issuer, model, generation, items, reason
):
    checkpoint = ResponsesCompactionCheckpoint.create(
        issuer="issuer-1",
        model="gpt-test",
        source_history_generation=4,
        source_items=[{"role": "user", "content": "first"}],
        compacted_output_items=[{"type": "compaction", "encrypted_content": "opaque"}],
    )

    match = checkpoint.match(
        issuer=issuer,
        model=model,
        history_generation=generation,
        current_items=items or [{"role": "user", "content": "first"}],
    )

    assert match.matched is False
    assert match.reason == reason


def test_compaction_checkpoint_requires_opaque_compaction_item():
    with pytest.raises(ValueError, match="no compaction item"):
        ResponsesCompactionCheckpoint.create(
            issuer="issuer-1",
            model="gpt-test",
            source_history_generation=1,
            source_items=[],
            compacted_output_items=[
                {"type": "message", "role": "user", "content": "only replay"}
            ],
        )
