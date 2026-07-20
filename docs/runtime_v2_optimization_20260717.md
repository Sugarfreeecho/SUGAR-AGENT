# Runtime V2 Optimization Pass — 2026-07-17

## Scope

This pass addresses corruption visibility, large-session append latency, reconnect scans, recent-turn opening, migration complexity, and token-scale stability without adding any legacy read/write to the Runtime V2 normal path. Runtime V1 remains selectable with `RUNTIME_VERSION=1`.

## Implemented

- Event, projector, UI-index, and seq-offset-index versions; future event schemas fail closed.
- Explicit `RuntimeEventLogCorruptionError`; normal readers no longer skip malformed facts.
- Main-agent and subagent model/context reads and writes propagate projection/persistence failures.
- Incremental copy-on-write projector for normal events; semantic history operations retain deterministic full reprojection.
- Compact and coalesced snapshot checkpoints with bounded incremental recovery after restart.
- Versioned sparse seq-to-byte offset index for `after_seq`, latest, and before-seq reads.
- Final-visible UI index with runtime seq mapping and incremental extension after append.
- Reattach stream switches from initial UI catch-up to Runtime V2 seq catch-up for durable live facts.
- Batch V1-to-V2 UI migration, disk-backed rollback, urgent on-open queue priority, and a second urgent worker when a startup migration is already running.
- Atomic SHA-256-verified blob writes/reads.
- Stale provider token checkpoints remain visible on the provider scale until refreshed.

## Local acceptance evidence

- 38 MB real-session-copy append benchmark: steady-state 6–12.5 ms; one-time old-cache upgrade about 94 ms.
- 10,000 UI-row batch migration: 1.98 seconds.
- Recent-turn reads use `runtime_v2_seq_index`; history operations inside the requested window still force full projection.
- Full Python regression: `522 passed, 1 skipped` in `68.01 s`.
- Frontend distribution and commit-policy verification both pass using the embedded Python runtime; the production bundle is in sync.
- The isolated Runtime V2 server returned HTTP 200. The current automation environment exposed no controllable browser, so a fresh interactive browser smoke could not be run in this pass; the previously recorded browser timings below remain the latest browser evidence.

## Operational behavior

- Old snapshots/UI indexes rebuild once because their version metadata is absent or stale.
- Disk snapshot checkpoints may trail the fact log by fewer than `RUNTIME_V2_SNAPSHOT_CHECKPOINT_EVENTS` events (default 32). This is expected; `read_consistent` catches up and checkpoints before returning after process restart.
- `events.jsonl` corruption is never auto-repaired. Use the explicit repair service/tool so backup and semantic verification remain auditable.
- Startup bulk migration stays opt-in. Opening or manually migrating a legacy-only session is prioritized and deduplicated.
