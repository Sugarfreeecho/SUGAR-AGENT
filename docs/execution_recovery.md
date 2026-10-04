# Durable execution recovery

Runtime V2 `execution_recorded` events retain received reasoning, reply text,
tool argument drafts and tool output independently of provider model messages.
An execution has a stable `execution_id`, `process_group_id`, user `turn_id`,
`run_id`, request `attempt_id`, and optional `tool_call_id`. Assigning a complete
tool ID promotes the draft rather than creating a second row. Delta batches
append to the existing JSONL journal before publication, without rewriting a
snapshot on every token. Terminal presentation waits for preceding batches.

Statuses distinguish generating, waiting for execution/approval/input, running,
completed, failed, timed out, interrupted and unknown. Argument generation does
not imply execution. Late deltas can add received output but cannot reopen a
terminal state. Authoritative results can settle an unknown/interrupted call.
Shell pipe bytes survive reader cancellation; timed-out results include received
stdout/stderr and confirmed exit state. Live output channels are also retained
separately. Existing tool-result files and UI head/tail truncation remain in use.

Human requests keep their existing durable request digest and gain the original
execution/block anchor. Replayed cards attach to restored tool rows. Existing
approval checks continue to bind authorization to the security request. After a
restart, the request digest is revalidated and the execution must prove it has
not started. The decision closes the orphaned call and resumes through the normal
model/tool authorization flow, without directly replaying an operation. Started
or unknown operations cannot use this path. Old requests without an execution
anchor are cancelled. Question answers use the same durable recovery worker.

`GET /sessions/{id}/history_snapshot` includes execution records,
`last_runtime_seq`, `projection_revision` and `last_final_seq`.
`GET /sessions/{id}/stream?after_runtime_seq=N` replays durable execution updates
and UI events after that cursor; `after_index` remains compatible. The snapshot
captures its resume cursor before reading the page so concurrent commits are
replayed safely. History edits invalidate the projection and request one full
reload. Ordinary reconnects and gaps use incremental replay. Child forwarding
is routed before parent lifecycle, message-index and Runtime cursor reduction.

Execution blocks are keyed by the ordinary user-turn/final-answer boundary.
Steer, retry and restart preserve the same block; adjacent blocks with the same
identity merge their rows and card slots. Legacy history infers boundaries from
ordinary user and final events. Data never written by an old version cannot be
recovered.

The UI keeps stable run and execution ordering generations. A replacement run
starts after the previous run even when the observer connected before recovery
registered the new run. Lifecycle frames, legacy live deltas and journal records
all establish the same run scope. Snapshot hydration orders auxiliary drafts by
their first Runtime sequence, including interrupt-steer boundaries. Older record
updates keep their original generation and cannot replace the active process
group or its scroll-follow target. Duplicate journal/event-bus frames do not
rewrite the same text or trigger another follow operation.

Complete interrupted tool calls receive tool results with retained output,
whether execution started, and known/unknown stop state. Missing results are
closed before the next model request. Argument drafts are supplied as progress
context, never formal tool calls or executable JSON. Received reasoning stays in
the journal and model checkpoint; a system progress note covers adapters that
strip historical reasoning fields. Non-interruptible started operations settle
before applying steer; cooperative cancellation has a bounded cleanup window,
after which external state is conservatively unknown.

`OUTPUT_LENGTH_RETRY_MAX` defaults to 2 **additional** requests for one logical
generation. Text fragments continue with exact multi-character overlap removal;
incomplete arguments must be regenerated in smaller calls. Mixed complete and
draft calls retain the real complete-call results and use the same continuation
counter. Exhaustion preserves received content and emits a stop explanation.
The continuation count and text prefix have a durable checkpoint so a replacement
run cannot reset the request allowance. Unknown started operations are blocked
from identical automatic re-execution until their stop state has been checked.
Existing Goal, cost and workflow constraints still run before each request.

Diagnostics record continuation attempts and stream-recovery causes/cursors.
Tests in `tests/test_execution_recovery.py` and
`tests/js/execution_recovery_runtime.cjs` cover durable replay, protocol closure,
timeout output, stable row updates and child/parent isolation.
