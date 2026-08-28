"""Generic, revisioned state and audit events for optional session features."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from .event_log import SessionEventLog
from .projector import RuntimeProjector
from .snapshot_store import SnapshotStore


_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class ExtensionStateError(ValueError):
    pass


class ExtensionStateConflict(ExtensionStateError):
    def __init__(self, expected_revision: int, actual_revision: int):
        self.expected_revision = int(expected_revision)
        self.actual_revision = int(actual_revision)
        super().__init__(
            f"Extension state revision conflict: expected {expected_revision}, "
            f"actual {actual_revision}"
        )


class ExtensionStateNotFound(ExtensionStateError):
    pass


class SessionExtensionStateStore:
    """Persist optional feature state without teaching Runtime its domain schema."""

    def __init__(
        self,
        sessions_dir: str | Path,
        *,
        path_resolver: Optional[Callable[[str], str | Path]] = None,
        max_state_bytes: int = 256 * 1024,
        max_event_bytes: int = 64 * 1024,
        require_existing_session: bool = True,
    ) -> None:
        self.event_log = SessionEventLog(sessions_dir, path_resolver=path_resolver)
        self.snapshots = SnapshotStore(sessions_dir, path_resolver=path_resolver)
        self.projector = RuntimeProjector()
        self.max_state_bytes = max(1, int(max_state_bytes))
        self.max_event_bytes = max(1, int(max_event_bytes))
        self.require_existing_session = bool(require_existing_session)

    @staticmethod
    def _identifier(value: str, field: str) -> str:
        normalized = str(value or "").strip()
        if not _IDENTIFIER_RE.fullmatch(normalized):
            raise ExtensionStateError(
                f"{field} must use 1-64 ASCII letters, digits, dot, underscore, or hyphen"
            )
        return normalized

    @staticmethod
    def _json_value(value: Any, *, max_bytes: int, field: str) -> Any:
        try:
            encoded = json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ExtensionStateError(f"{field} must be JSON serializable") from exc
        if len(encoded) > max_bytes:
            raise ExtensionStateError(
                f"{field} exceeds the {max_bytes}-byte limit"
            )
        return json.loads(encoded.decode("utf-8"))

    def _ensure_session(self, session_id: str) -> str:
        sid = str(session_id or "").strip()
        if not sid:
            raise ExtensionStateError("session_id is required")
        if self.require_existing_session and not self.event_log.session_dir(sid).is_dir():
            raise ExtensionStateNotFound(f"Session does not exist: {sid}")
        return sid

    def _snapshot_for_update(self, session_id: str) -> dict:
        snapshot = self.snapshots.read_for_update(session_id)
        events = self.event_log.read_all(session_id)
        last_seq = max((int(event.seq) for event in events), default=0)
        if int(snapshot.get("last_seq") or 0) != last_seq:
            snapshot = self.projector.project(events)
        return snapshot

    @staticmethod
    def _row(snapshot: dict, plugin_id: str, namespace: str) -> dict:
        extensions = snapshot.get("extensions") if isinstance(snapshot, dict) else {}
        plugin_state = extensions.get(plugin_id) if isinstance(extensions, dict) else {}
        row = plugin_state.get(namespace) if isinstance(plugin_state, dict) else None
        return copy.deepcopy(row) if isinstance(row, dict) else {
            "revision": 0,
            "value": None,
            "updated_at": None,
            "seq": 0,
        }

    @staticmethod
    def _top_level_patch(before: Any, after: Any) -> list[dict]:
        if not isinstance(before, dict) or not isinstance(after, dict):
            return [{"op": "replace", "path": "", "value": copy.deepcopy(after)}]
        operations: list[dict] = []
        for key in sorted(set(before) - set(after)):
            pointer = str(key).replace("~", "~0").replace("/", "~1")
            operations.append({"op": "remove", "path": f"/{pointer}"})
        for key in sorted(after):
            if key in before and before.get(key) == after.get(key):
                continue
            pointer = str(key).replace("~", "~0").replace("/", "~1")
            operations.append(
                {
                    "op": "replace" if key in before else "add",
                    "path": f"/{pointer}",
                    "value": copy.deepcopy(after.get(key)),
                }
            )
        return operations

    def get(self, session_id: str, plugin_id: str, namespace: str) -> dict:
        sid = self._ensure_session(session_id)
        owner = self._identifier(plugin_id, "plugin_id")
        space = self._identifier(namespace, "namespace")
        snapshot = self.snapshots.read(sid)
        if not snapshot or int(snapshot.get("last_seq") or 0) != max(
            0, self.event_log.next_seq(sid) - 1
        ):
            snapshot = self.projector.project(self.event_log.read_all(sid))
        return self._row(snapshot, owner, space)

    def read_all_lightweight(self, session_id: str) -> dict:
        """Return only extension namespaces without copying the full runtime snapshot."""

        sid = self._ensure_session(session_id)
        snapshot = self.snapshots.read_for_update(sid)
        event_path = self.event_log.event_path(sid)
        if not self.snapshots._signature_matches(snapshot, event_path):
            with self.event_log.session_transaction(sid):
                snapshot = self.snapshots.read_for_update(sid)
                if not self.snapshots._signature_matches(snapshot, event_path):
                    rebuilt = None
                    if self.snapshots._projection_version_matches(snapshot):
                        last_seq = max(0, int(snapshot.get("last_seq") or 0))
                        pending = self.event_log.read_after_seq(sid, last_seq)
                        if all(int(event.seq) > last_seq for event in pending):
                            rebuilt = snapshot
                            for event in pending:
                                rebuilt = self.projector.project_incremental(rebuilt, event)
                    snapshot = rebuilt or self.projector.project(
                        self.event_log.read_all(sid)
                    )
                self.snapshots.stamp_event_log(sid, snapshot, event_path)
                self.snapshots.write_checkpointed(sid, snapshot)
        extensions = snapshot.get("extensions") if isinstance(snapshot, dict) else {}
        return copy.deepcopy(extensions) if isinstance(extensions, dict) else {}

    def compare_and_set(
        self,
        session_id: str,
        plugin_id: str,
        namespace: str,
        *,
        expected_revision: int,
        value: Any,
        run_id: str = "",
    ) -> dict:
        sid = self._ensure_session(session_id)
        owner = self._identifier(plugin_id, "plugin_id")
        space = self._identifier(namespace, "namespace")
        expected = int(expected_revision)
        if expected < 0:
            raise ExtensionStateError("expected_revision cannot be negative")
        clean_value = self._json_value(
            value, max_bytes=self.max_state_bytes, field="extension state"
        )
        with self.event_log.session_transaction(sid):
            snapshot = self._snapshot_for_update(sid)
            current = self._row(snapshot, owner, space)
            actual = int(current.get("revision") or 0)
            if actual != expected:
                raise ExtensionStateConflict(expected, actual)
            event = self.event_log._append_unlocked(
                sid,
                "extension_state_changed",
                payload={
                    "plugin_id": owner,
                    "namespace": space,
                    "revision": actual + 1,
                    "value": clean_value,
                },
                run_id=str(run_id or "").strip() or None,
            )
            snapshot = self.projector.project_incremental(snapshot, event)
            self.snapshots.stamp_event_log(sid, snapshot, self.event_log.event_path(sid))
            self.snapshots.write_checkpointed(sid, snapshot)
            return self._row(snapshot, owner, space)

    def patch(
        self,
        session_id: str,
        plugin_id: str,
        namespace: str,
        *,
        expected_revision: int,
        operations: Iterable[dict],
        run_id: str = "",
    ) -> dict:
        current = self.get(session_id, plugin_id, namespace)
        actual = int(current.get("revision") or 0)
        if actual != int(expected_revision):
            raise ExtensionStateConflict(int(expected_revision), actual)
        value = copy.deepcopy(current.get("value"))
        for operation in list(operations or []):
            value = self._apply_patch_operation(value, operation)
        return self.compare_and_set(
            session_id,
            plugin_id,
            namespace,
            expected_revision=actual,
            value=value,
            run_id=run_id,
        )

    def set_latest(
        self,
        session_id: str,
        plugin_id: str,
        namespace: str,
        value: Any,
        *,
        run_id: str = "",
        max_attempts: int = 8,
    ) -> dict:
        """Replace a namespace while safely retrying concurrent CAS conflicts."""

        attempts = max(1, int(max_attempts))
        last_conflict: Optional[ExtensionStateConflict] = None
        for _ in range(attempts):
            current = self.get(session_id, plugin_id, namespace)
            try:
                return self.compare_and_set(
                    session_id,
                    plugin_id,
                    namespace,
                    expected_revision=int(current.get("revision") or 0),
                    value=value,
                    run_id=run_id,
                )
            except ExtensionStateConflict as exc:
                last_conflict = exc
        assert last_conflict is not None
        raise last_conflict

    def mutate(
        self,
        session_id: str,
        plugin_id: str,
        namespace: str,
        mutator: Callable[[Any], tuple[str, Any, Any]],
        *,
        run_id: str = "",
    ) -> tuple[Optional[Any], Any]:
        """Atomically apply a trusted host mutation to one extension namespace.

        The callback returns ``(action, persisted_value, response_value)``.
        An empty action performs a read-only mutation and appends no event.
        """

        sid = self._ensure_session(session_id)
        owner = self._identifier(plugin_id, "plugin_id")
        space = self._identifier(namespace, "namespace")
        if not callable(mutator):
            raise ExtensionStateError("mutator must be callable")
        with self.event_log.session_transaction(sid):
            snapshot = self._snapshot_for_update(sid)
            current = self._row(snapshot, owner, space)
            current_value = copy.deepcopy(current.get("value"))
            action, persisted_value, response_value = mutator(current_value)
            normalized_action = str(action or "").strip()
            if not normalized_action:
                return None, copy.deepcopy(
                    response_value if response_value is not None else current_value
                )
            clean_value = self._json_value(
                persisted_value,
                max_bytes=self.max_state_bytes,
                field="extension state",
            )
            event_payload = {
                "plugin_id": owner,
                "namespace": space,
                "revision": int(current.get("revision") or 0) + 1,
                "action": normalized_action[:128],
            }
            patch = self._top_level_patch(current_value, clean_value)
            encoded_patch = json.dumps(
                patch, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            ).encode("utf-8")
            encoded_value = json.dumps(
                clean_value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            ).encode("utf-8")
            if int(current.get("revision") or 0) > 0 and len(encoded_patch) < len(encoded_value):
                event_payload["patch"] = patch
            else:
                event_payload["value"] = clean_value
            event = self.event_log._append_unlocked(
                sid,
                "extension_state_changed",
                payload=event_payload,
                run_id=str(run_id or "").strip() or None,
            )
            snapshot = self.projector.project_incremental(snapshot, event)
            self.snapshots.stamp_event_log(sid, snapshot, self.event_log.event_path(sid))
            self.snapshots.write(session_id, snapshot)
            return event, copy.deepcopy(
                response_value if response_value is not None else clean_value
            )

    def append_event(
        self,
        session_id: str,
        plugin_id: str,
        event_name: str,
        data: Any,
        *,
        run_id: str = "",
    ) -> dict:
        sid = self._ensure_session(session_id)
        owner = self._identifier(plugin_id, "plugin_id")
        name = self._identifier(event_name, "event_name")
        clean_data = self._json_value(
            data, max_bytes=self.max_event_bytes, field="extension event"
        )
        with self.event_log.session_transaction(sid):
            snapshot = self._snapshot_for_update(sid)
            event = self.event_log._append_unlocked(
                sid,
                "extension_event",
                payload={"plugin_id": owner, "event_name": name, "data": clean_data},
                run_id=str(run_id or "").strip() or None,
            )
            snapshot = self.projector.project_incremental(snapshot, event)
            self.snapshots.stamp_event_log(sid, snapshot, self.event_log.event_path(sid))
            self.snapshots.write_checkpointed(sid, snapshot)
        return {
            "plugin_id": owner,
            "event_name": name,
            "data": clean_data,
            "seq": event.seq,
            "timestamp": event.timestamp,
        }

    @classmethod
    def _apply_patch_operation(cls, document: Any, operation: dict) -> Any:
        if not isinstance(operation, dict):
            raise ExtensionStateError("patch operation must be an object")
        op = str(operation.get("op") or "").strip().lower()
        path = str(operation.get("path") or "")
        if op not in {"add", "replace", "remove"}:
            raise ExtensionStateError(f"unsupported patch operation: {op}")
        if path == "":
            if op == "remove":
                return None
            if "value" not in operation:
                raise ExtensionStateError(f"{op} requires value")
            return copy.deepcopy(operation.get("value"))
        if not path.startswith("/"):
            raise ExtensionStateError("patch path must be a JSON Pointer")
        tokens = [part.replace("~1", "/").replace("~0", "~") for part in path[1:].split("/")]
        root = copy.deepcopy(document)
        parent = root
        for token in tokens[:-1]:
            if isinstance(parent, dict) and token in parent:
                parent = parent[token]
            elif isinstance(parent, list):
                try:
                    parent = parent[int(token)]
                except (ValueError, IndexError) as exc:
                    raise ExtensionStateError(f"patch path does not exist: {path}") from exc
            else:
                raise ExtensionStateError(f"patch path does not exist: {path}")
        leaf = tokens[-1]
        if isinstance(parent, dict):
            exists = leaf in parent
            if op in {"replace", "remove"} and not exists:
                raise ExtensionStateError(f"patch path does not exist: {path}")
            if op == "remove":
                parent.pop(leaf)
            else:
                if "value" not in operation:
                    raise ExtensionStateError(f"{op} requires value")
                parent[leaf] = copy.deepcopy(operation.get("value"))
            return root
        if isinstance(parent, list):
            if leaf == "-" and op == "add":
                parent.append(copy.deepcopy(operation.get("value")))
                return root
            try:
                index = int(leaf)
            except ValueError as exc:
                raise ExtensionStateError(f"invalid list index in patch path: {path}") from exc
            if op == "add":
                if index < 0 or index > len(parent):
                    raise ExtensionStateError(f"patch path does not exist: {path}")
                parent.insert(index, copy.deepcopy(operation.get("value")))
            elif 0 <= index < len(parent):
                if op == "remove":
                    parent.pop(index)
                else:
                    parent[index] = copy.deepcopy(operation.get("value"))
            else:
                raise ExtensionStateError(f"patch path does not exist: {path}")
            return root
        raise ExtensionStateError(f"patch parent is not a container: {path}")


__all__ = [
    "ExtensionStateConflict",
    "ExtensionStateError",
    "ExtensionStateNotFound",
    "SessionExtensionStateStore",
]
