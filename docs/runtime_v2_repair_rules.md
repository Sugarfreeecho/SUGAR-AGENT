# Runtime V2 Repair Rules

Date: 2026-07-04

## Normal Reads

- Do not silently repair old divergent sessions during normal reads.
- `/messages`, `/history_snapshot`, `/messages/count`, `/user_turns`, and projection read paths must not call legacy sync or repair helpers.
- Historical `legacy_ui_sync_on_read` pollution must be handled by explicit repair or migration commands.

## Audit Statuses

- `match`: legacy and Runtime V2 visible/model signatures are identical.
- `v2_only`: pure V2 session; no legacy parity is required.
- `v2_ahead`: legacy is a prefix and Runtime V2 has newer tail events; no implicit legacy export is required.
- `missing_v2`: legacy exists but V2 projection is missing; explicit migration is required.
- `mismatch`: legacy and V2 diverged; inspect `ui_first_mismatch` / `model_first_mismatch` before choosing repair direction.

## Repair Direction

- Do not overwrite Runtime V2 with legacy just because a mismatch exists.
- Do not export Runtime V2 back to legacy unless the user explicitly requests compatibility export.
- For old divergent sessions, first classify whether the Runtime V2 projection or the legacy file is the intended source of truth.
- If the divergence came from old `legacy_ui_sync_on_read` pollution, prefer an explicit migration/repair command that records the chosen source and keeps an audit trail.
