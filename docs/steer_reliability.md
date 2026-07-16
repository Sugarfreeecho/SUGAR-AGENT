# Agent Steer Reliability Contract

Agent steer is a durable user turn, not a best-effort UI command. The server is
the source of truth and stores each operation in `steer_inbox.json` with a stable
`id`, `client_id`, `mode`, source/replacement run IDs, state, version, and timestamps.

## Delivery modes

- `interrupt` is the existing takeover mode. It aborts interruptible LLM/tool
  work, preserves completed output, removes only an unclosed tool tail, commits
  the steer, and replans.
- `append` never requests an abort. The UI appends an optimistic follow-up row
  to the end of the active process block after server acceptance. The ReAct loop
  claims and durably commits it only after the current round is complete: after
  all tool results are persisted, or after a no-tool model response, and before
  constructing the next model request.

Old inbox rows without `mode` normalize to `interrupt` for compatibility.
New steers default to `MYAGENT_STEER_MODE` (`append` when unset or invalid).
An explicit per-item browser selection overrides the environment default.

## State transitions

Normal native takeover:

`queued -> interrupting -> claimed -> consumed`

Replacement-run takeover:

`queued -> restarting -> claimed -> consumed`

`queued` and `interrupting` may be cancelled. A claimed operation cannot be
withdrawn because its Runtime V2 user-turn commit may already be in progress.
Terminal records are retained in a bounded journal so retries with the same
`client_id` remain idempotent after consumption.

The Runtime V2 `operation_id` is the steer ID. The inbox is acknowledged only
after the atomic user-turn commit succeeds. A crash after commit but before UI
delivery is recovered through Runtime V2 projection plus the steer status API;
the user turn is not submitted a second time.

## Recovery API

- `POST /sessions/{session_id}/steer` queues or deduplicates an operation.
- `GET /sessions/{session_id}/steer` lists authoritative pending operations.
- `GET /sessions/{session_id}/steer/{steer_id}` returns one operation.
- `POST /sessions/{session_id}/steer/{steer_id}/recover` assigns a stable
  replacement run to an orphaned operation.
- `DELETE /sessions/{session_id}/steer` cancels only an unclaimed operation.

The browser persists a presentation queue but reconciles it with these APIs on
session activation and while an operation is accepted. Unknown status is never
treated as permission to create a new operation.

Text entered while a run is active is first a local pending next turn. Refresh,
server reconciliation, and run completion only restore or refresh the queue;
they never transmit a pending item. The user must click “Send now” on that row,
which creates a durable steer in the selected mode while a run is active. A
failed request keeps the queue item instead of deleting it optimistically, and
consuming one item never automatically sends the next pending row.

## Run and content fencing

Each active run owns a process-local control object and a cross-process
`active_run_fence.json` token. A replacement run atomically replaces that token.
Late events, model-history writes, and final commits from the old run are then
suppressed. This prevents a cancelled request from overwriting or appending to
the replacement run.

Native replanning uses a non-recursive outer loop. Confirmed assistant text and
completed tool results remain in history. Rollback removes only an unclosed tool
tail and its unfinished UI events. Serialized write tools are not cancelled once
started; their real result is checkpointed and the steer is applied at the next
safe point, because cancelling an awaitable cannot undo an external side effect.

## Required invariants

1. One `client_id` maps to one durable steer ID.
2. One steer ID commits at most one Runtime V2 user turn.
3. Only the active fence owner may publish or persist run output.
4. A replacement run must claim the matching steer ID and replacement run ID.
5. Missing SSE delivery must be recoverable through projection and status APIs.
6. Confirmed output is retained; only unfinished execution artifacts are pruned.
7. Append mode is invisible to interruption polling and is consumed only at a
   completed ReAct boundary before the next model request.
8. Interrupt mode seals the prior process block exactly once. Its durable event
   reuses the optimistic operation-keyed row and reserved UI index; replacement
   reasoning/response rows may only be upserted inside the new process block.
