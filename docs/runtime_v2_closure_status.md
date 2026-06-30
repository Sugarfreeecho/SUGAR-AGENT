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

## Compatibility Boundary

- V1 and V2 paths are intentionally still both present. `RUNTIME_VERSION=1` remains supported.
- The main `/chat` live response still emits the legacy UI-shaped stream, while V2 provides source events and projected reattach streams. This is compatible with the current frontend; raw-V2 `/chat` would be a protocol change, not a required data-consistency fix.
- Legacy UI file writes from `append_ui_event()` are now limited to the V1 primary path. V2 compatibility export/migration must remain explicit service work rather than an implicit side effect of normal runtime execution.
- Legacy child-session history reads and writes remain part of the V1 subagent path only. V2 subagent resume/collect paths should be guarded by projection-based tests.
- Legacy child `ui_events.json` and `llm_history.json` reads remain part of the V1 subagent display path only. V2 subagent display should use active-runtime UI/model projections.
- Legacy model-history reconcile/load remains part of the V1 primary path only. V2 API preparation must not fall back to legacy files after version-check or projection errors.
