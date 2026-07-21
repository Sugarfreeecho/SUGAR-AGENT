# Runtime V2 Closure Status

## Optimization update — 2026-07-17

- Event corruption and unsupported schemas fail closed; model/context/subagent failures no longer become empty histories.
- Snapshots and indexes are versioned rebuildable caches; normal projection updates are incremental and copy-on-write.
- Disk snapshot checkpoints are coalesced with bounded tail recovery; reconnect and recent-turn reads use sparse Runtime V2 seq offsets.
- Live reattach performs one UI-index catch-up and then advances by Runtime V2 seq.
- Legacy migration is batched, rollback storage is disk-backed, and on-open/manual jobs receive queue priority.
- Token UI keeps the previous provider scale while a post-rewrite checkpoint is stale; blob writes are atomic and reads verify SHA-256.
- A copied 38 MB real-session benchmark measured steady-state append at 6–12.5 ms (first old-cache upgrade about 94 ms). A 10,000-row legacy UI migration completed in 1.98 seconds.
- Final regression for this optimization pass: `522 passed, 1 skipped in 68.01s`; frontend dist-sync and commit-policy gates also pass.
- The isolated Runtime V2 HTTP smoke returned 200. No controllable browser was exposed in the current automation environment, so the prior repository-native Chromium run remains the latest interactive browser evidence.

See `docs/runtime_v2_optimization_20260717.md` for implementation and operational details.

Date: 2026-07-16

## Verified State

- Final full Python suite after isolation, migration, stream recovery, steer modes, upload, Hooks/Plugins and frontend-race patches: `465 passed, 1 skipped in 56.10s`.
- Final frontend release gate passed: `npm run build`, `npm run verify:dist`, and `npm run verify:commit`. The committed bundle is reproducible from the source tree.
- Final repository-native Chromium smoke passed against Runtime V2. It covered snapshot open, TOC scroll, refresh recovery, online reconnect, subagent display, clipboard file/image paste, optimistic stop-before-preflight, explicit follow-up consumption, interrupt process alignment, real branch, truncate and rewrite.
- The final browser smoke completed snapshot open in `71 ms`; branch round trip and session switch was `460.3 ms`. Interrupt takeover produced separate old/new process groups, exactly one steer row, and the ordered new-group rows `user-steer -> llm-reasoning -> llm-response`. Materializing branches from repaired copies of real histories previously took `1.225 s` for 5,160 events and `3.245 s` for 7,220 events, all below the 10-second acceptance limit.
- Workspace audit command:

```powershell
python scripts\audit_runtime_versions.py --output .tmp-runtime-v2-audit.json
```

- Final workspace audit after explicit repair and automatic-migration validation: `checked=146`, `ui_mismatch=3`, `model_mismatch=4`, `ui_v2_only=63`, `model_v2_only=64`, `ui_v2_ahead=2`, `model_v2_ahead=0`, `runtime_v2_active_runs=0`, `bad_lines=0`, `duplicate_seqs=0`, `non_monotonic_seqs=0`, `errors=0`.
- The latest 102 MB mixed-runtime benchmark measured V2 UI cold-full median `694 ms` versus V1 `1.645 s`, V2 cold-page median `757 ms` versus V1 `1.652 s`, and V2 warm-full median below `1 ms`. Default on-demand migration left `/sessions/state` at `56-64 ms` after a `120 ms` first request in five repeated local checks.
- Historical root-log repair was applied to the three affected sessions with backup, manifest and semantic projection verification. The final audit reports `bad_lines=0`, `duplicate_seqs=0`, and `non_monotonic_seqs=0`; a separate root repair dry-run reports `checked=120`, `dirty=0`, `refused=0`.
- Subagent split-storage repair applied `31` repairs from `92` inspected children with `refused=0`, `pending_archive=0`, and `failed=0`. The final dry-run reports `checked=92`, `split_brain=0`, and `repaired=0`.
- `v2_only` means the session has Runtime V2 projection data and no legacy file history. This is expected for pure V2 sessions and is not a failure.
- `v2_ahead` means legacy is a prefix and Runtime V2 has newer tail events. This is expected after normal V2 operation stopped implicit legacy writes.
- Remaining `mismatch` rows are old divergent sessions and must not be auto-overwritten by legacy repair. They need explicit migration/repair review using `ui_first_mismatch` / `model_first_mismatch` from the audit output.

## Closed In This Pass

- Runtime audit now distinguishes `match`, `v2_only`, `v2_ahead`, `missing_v2`, and `mismatch`, so pure V2 sessions are not treated as failed legacy parity checks.
- Runtime audit ignores state-only UI events such as `cache_stats`, `context_tokens`, and todo snapshot events when comparing visible UI history.
- Runtime audit reports `ui_first_mismatch` and `model_first_mismatch` for true divergent sessions, making old-session migration review concrete.
- The explicit migration service does not replace an existing V2 UI projection from legacy; existing V2 data is preserved as `match`, `v2_ahead`, or `mismatch`. Normal V2 reads never pass a legacy loader.
- The explicit migration service backfills model history only when the V2 projection is empty; normal V2 model reads never reconcile legacy history.
- `/sessions/{id}/stream` reattach in V2 mode reads `RuntimeUiProjection` instead of resurrecting stale legacy stream state.
- Raw V2 stream is available at `/runtime-v2/sessions/{id}/stream?after_seq=...`.
- Branch creation records the source Runtime seq and seeds branch visible history from Runtime V2 events in V2 primary mode.
- UI projection hydrates `*_ref` blob payloads back to normal UI fields such as `result`, so large tool outputs replay correctly.
- Branch seeding copies referenced blobs into the branch session.
- Audit normalizes legacy LangChain role names (`human`, `llm`, `ai`, `agent`) to Runtime V2 roles before comparing model history.
- In V2 primary mode, `SessionManager.append_ui_event()` now writes only the Runtime V2 event/projection path and no longer reads or writes `ui_events.json` on the normal UI append path.
- The V2 append path still applies required UI side effects such as sidebar preview updates and unread-result state, so cutting the legacy file write does not remove visible session-list behavior.
- In V2 primary mode, subagent execution now loads prior child history from `RuntimeModelProjection`, persists finished child model history through `RuntimeHistoryOps`, and reads collected final output through `RuntimeUiProjection` instead of child `llm_history.json`, `work_messages.json`, or `ui_events.json`.
- In V2 primary mode, subagent creation no longer initializes empty legacy `work_messages.json`, `llm_history.json`, `ui_events.json`, `dialogue_history.json`, or `key_context.md`; subagent fork copies parent model/context through Runtime V2 projection/snapshot instead of parent legacy files.
- In V2 primary mode, subagent tree/status/dialogue/metrics display paths now read child and parent UI history through the active runtime projection, with model-history fallback using `RuntimeModelProjection` instead of child `llm_history.json`.
- The model-history loader now fails closed to the Runtime V2 projection path whenever V2 is primary; only the V1 primary branch may reconcile and read `llm_history.json`.
- In V2 primary mode, run and continuation setup load key context from the Runtime V2 context snapshot instead of `key_context.md` and legacy todo migration.
- Executor model configuration now reuses a short-lived profile catalog cache across sessions and avoids re-reading session metadata when building fallback candidates from already-loaded metadata.
- MCP tool definition setup now reuses a short-lived config-signature cache, reducing repeated config stat/hash work across rapid ReAct iterations while preserving explicit reload.
- Frontend session switching now lets the V2 `history_snapshot` response own the initial TOC build; the legacy early `/user_turns` TOC request is only started when snapshot loading is explicitly disabled.
- V2 `history_snapshot` now reuses the `total` returned by its page read instead of issuing a second count pass when the page already carries total event count.
- Frontend send/reattach paths now prefer the event-count cache populated by snapshot/page loads; local send advances the cache immediately instead of issuing an extra `/messages/count` request during stream startup.
- In V2 primary mode, normal state persistence now commits key context to the Runtime V2 context snapshot and no longer writes legacy `key_context.md` or `dialogue_history` as an implicit side effect.
- V2 branch creation no longer copies legacy sidecar context/todo/compress files into the new branch; branch visible history is seeded from Runtime V2 events only.
- Session deletion now removes subagent descendants recursively from disk, subagent index, and session index so deleted branches/subtrees cannot reappear after refresh.
- Session title generation keeps the original executor `title_generator` behavior; final latency fixes must not change title semantics.
- LLM reasoning/response stream chunks are merged across increasing `stream_seq` values instead of finalizing on every delta, preventing process blocks from fragmenting into many rows.
- In V2 primary mode, todo state is restored from the Runtime V2 snapshot and updated through persistable `todo_plan`/`todo_updated` events; normal run setup and `update_todo` no longer read or write legacy `todo_plan.md`.
- Runtime migration sync now defaults to migrating/backfilling V2 only; exporting Runtime V2 UI/model projections back to legacy files requires an explicit `export_legacy=true` request.
- Live UI cache/stat updates now use the event's owning session id instead of `currentSessionId`, so background runs and recently switched-away sessions cannot overwrite the visible session's token label.
- Follow-up restart messages are recorded and replayed as `user_steer` UI events while remaining normal user input for the model context, so immediate follow-up does not turn into a main user bubble after refresh.
- `/sessions/{id}/context_tokens` is guarded so a Runtime V2 snapshot miss falls through to Runtime V2 projection-based computation, not legacy session history.
- Runtime V2 new-session creation writes V2 metadata/event/snapshot state without creating empty `ui_events.json`, `llm_history.json`, `work_messages.json`, `key_context.md`, `dialogue_history.json`, or todo sidecars.
- Goal, steer-fence, branch/truncate, nested subagent path resolution, blob placement, and subagent indexes now honor the active runtime and resolved nested session path instead of leaking state into the other runtime or a top-level child directory.
- Branch/truncate checkpoints preserve Runtime V2 model history, context summary, todo state, and cached provider token counts; a rewritten/stopped turn no longer has to fall back to a structurally different local-token estimate.
- Explicit migration/export preloads both legacy sources before writing, treats V2 as authoritative during export, handles shorter and equal-length rewrites, and restores V2/legacy files and referenced blobs if verification fails.
- Follow-up queue items auto-continue one FIFO item after a run normally ends, but only after server reconciliation and local-run/server-stream/send-pipeline/dispatcher idle checks. A user-requested stop never auto-continues. Enqueue never triggers transmission; consumed events can only wake the same gated check. Explicit Send now remains available for any pending row, duplicate completion signals are coalesced, and each completion boundary attempts at most one row so failures remain queued without an automatic retry loop.
- Interrupt follow-ups now reserve and reuse one UI event index and one operation-keyed row. The interrupt seals the old process group once, and LLM row lookup is scoped to the current group so a replacement run restarting at `react_iter=1` cannot overwrite the old run's reasoning.
- The send UI enters optimistic stop state in the same frame while preflight is pending; clipboard image/file paste uploads files through the existing endpoint and inserts quoted local paths into the draft.
- The runtime benchmark now ranks sessions by the larger of V1 UI+model or V2 event+snapshot storage, so pure V2 large sessions are included, and reports application-cache cold and warm distributions separately without evicting the OS page cache.

## Compatibility Boundary

- V1 and V2 paths are intentionally still both present. `RUNTIME_VERSION=1` remains supported.
- The main `/chat` live response still emits the legacy UI-shaped stream, while V2 provides source events and projected reattach streams. This is compatible with the current frontend; raw-V2 `/chat` would be a protocol change, not a required data-consistency fix.
- Legacy UI file writes from `append_ui_event()` are now limited to the V1 primary path. V2 compatibility export/migration must remain explicit service work rather than an implicit side effect of normal runtime execution.
- Legacy child-session history reads and writes remain part of the V1 subagent path only. V2 subagent resume/collect paths should be guarded by projection-based tests.
- Legacy child-session bootstrap files are V1-only; V2 subagent create/fork should seed RuntimeSubagentStore, RuntimeModelProjection, and context snapshots without creating or copying V1 history files.
- Legacy child `ui_events.json` and `llm_history.json` reads remain part of the V1 subagent display path only. V2 subagent display should use active-runtime UI/model projections.
- Legacy model-history reconcile/load remains part of the V1 primary path only. V2 API preparation must not fall back to legacy files after version-check or projection errors.
- Legacy `key_context.md` loading and embedded todo migration remain part of the V1 run setup path only. V2 run setup should use Runtime V2 context snapshots.
- Profile/catalog cache invalidation remains tied to explicit model profile/env updates through `_invalidate_executor_config_cache()`.
- MCP config signature cache is cleared by `force_reload()` so saved MCP settings still rebuild server connections immediately.
- Snapshot-backed session loads must not mark TOC as already started before messages render; otherwise TOC can be skipped or rebuilt out of order. The old early TOC path remains a compatibility path for `useSnapshot === false`.
- Snapshot count fallback remains available only for malformed/legacy projection page payloads that do not include `total`.
- Event-count cache is still refreshed by explicit count reads when no cache exists; stream startup should not add a background count request after the user bubble has already advanced the local event index.
- Legacy `key_context.md` and `dialogue_history` writes are reserved for V1 primary or explicit export/migration; V2 context consumers should read Runtime V2 snapshots.
- Legacy `todo_plan.md` reads/writes are reserved for V1 primary or explicit migration/export; V2 todo consumers should read Runtime V2 snapshots.
- The frontend final reconcile path must not fetch `/messages` after run completion; final visibility should be driven by the live SSE final or already-cached message records.
- Runtime V2 automatically migrates legacy-only sessions on first open/send and returns `migration_pending`; the frontend retries without rendering an empty V2 history. The coordinator uses file fingerprints for idempotency, refuses active runs, migrates UI/model/context/todo atomically, adopts only an exact legacy tail, records unchanged conflicts as blocked manifests, and never writes legacy unless compatibility export is separately requested with `export_legacy=true`. A bulk startup scan remains available through `RUNTIME_V2_AUTO_MIGRATE_STARTUP=1`, but is disabled by default because large in-process JSON migrations can contend with first-screen requests.
- Frontend live event handlers must pass the run/session id into cache and metric reducers; reducers must not infer ownership from the currently selected session.
- Follow-up restart is a UI event-type distinction only. It must not fork a separate model-history format or bypass the normal V2 model projection append path.
