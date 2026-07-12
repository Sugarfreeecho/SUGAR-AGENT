# Agent Steer Reliability Contract

Agent steer is a durable user turn, not a best-effort UI command. The server is
the source of truth and stores each operation in `steer_inbox.json` with a stable
`id`, `client_id`, source/replacement run IDs, state, version, and timestamps.

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
