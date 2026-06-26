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

## Compatibility Boundary

- V1 and V2 paths are intentionally still both present. `RUNTIME_VERSION=1` remains supported.
- The main `/chat` live response still emits the legacy UI-shaped stream, while V2 provides source events and projected reattach streams. This is compatible with the current frontend; raw-V2 `/chat` would be a protocol change, not a required data-consistency fix.
