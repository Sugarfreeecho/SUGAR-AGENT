# Runtime V2 Closure Status

Date: 2026-06-25

## Verified State

- Runtime V2 tests: `54 passed`.
- Workspace audit: `ui_mismatch=0`, `model_mismatch=0`, `runtime_v2_active_runs=0`, `errors=0`.
- Existing workspace sessions were repaired with:

```powershell
python scripts\audit_runtime_versions.py --repair-model --only-mismatches
```

## Closed In This Pass

- `/sessions/{id}/stream` reattach in V2 mode reads `RuntimeUiProjection` instead of resurrecting stale legacy stream state.
- Raw V2 stream is available at `/runtime-v2/sessions/{id}/stream?after_seq=...`.
- Branch creation records the source Runtime seq and seeds branch visible history from Runtime V2 events in V2 primary mode.
- UI projection hydrates `*_ref` blob payloads back to normal UI fields such as `result`, so large tool outputs replay correctly.
- Branch seeding copies referenced blobs into the branch session.
- Audit normalizes legacy LangChain role names (`human`, `llm`, `ai`, `agent`) to Runtime V2 roles before comparing model history.
- In V2 primary mode, `SessionManager.append_ui_event()` now writes only the Runtime V2 event/projection path and no longer reads or writes `ui_events.json` on the normal UI append path.
- The V2 append path still applies required UI side effects such as sidebar preview updates and unread-result state, so cutting the legacy file write does not remove visible session-list behavior.
- In V2 primary mode, subagent execution now loads prior child history from `RuntimeModelProjection`, persists finished child model history through `RuntimeHistoryOps`, and reads collected final output through `RuntimeUiProjection` instead of child `llm_history.json`, `work_messages.json`, or `ui_events.json`.
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
- Final finish no longer calls a model to generate the session title before emitting final; new-session titles use a local first-user preview on the hot path.
- LLM reasoning/response stream chunks are merged across increasing `stream_seq` values instead of finalizing on every delta, preventing process blocks from fragmenting into many rows.

## Compatibility Boundary

- V1 and V2 paths are intentionally still both present. `RUNTIME_VERSION=1` remains supported.
- The main `/chat` live response still emits the legacy UI-shaped stream, while V2 provides source events and projected reattach streams. This is compatible with the current frontend; raw-V2 `/chat` would be a protocol change, not a required data-consistency fix.
- Legacy UI file writes from `append_ui_event()` are now limited to the V1 primary path. V2 compatibility export/migration must remain explicit service work rather than an implicit side effect of normal runtime execution.
- Legacy child-session history reads and writes remain part of the V1 subagent path only. V2 subagent resume/collect paths should be guarded by projection-based tests.
- Legacy child `ui_events.json` and `llm_history.json` reads remain part of the V1 subagent display path only. V2 subagent display should use active-runtime UI/model projections.
- Legacy model-history reconcile/load remains part of the V1 primary path only. V2 API preparation must not fall back to legacy files after version-check or projection errors.
- Legacy `key_context.md` loading and embedded todo migration remain part of the V1 run setup path only. V2 run setup should use Runtime V2 context snapshots.
- Profile/catalog cache invalidation remains tied to explicit model profile/env updates through `_invalidate_executor_config_cache()`.
- MCP config signature cache is cleared by `force_reload()` so saved MCP settings still rebuild server connections immediately.
- Snapshot-backed session loads must not mark TOC as already started before messages render; otherwise TOC can be skipped or rebuilt out of order. The old early TOC path remains a compatibility path for `useSnapshot === false`.
- Snapshot count fallback remains available only for malformed/legacy projection page payloads that do not include `total`.
- Event-count cache is still refreshed by explicit count reads when no cache exists; stream startup should not add a background count request after the user bubble has already advanced the local event index.
- Legacy `key_context.md` and `dialogue_history` writes are reserved for V1 primary or explicit export/migration; V2 context consumers should read Runtime V2 snapshots.
- The frontend final reconcile path must not fetch `/messages` after run completion; final visibility should be driven by the live SSE final or already-cached message records.
