"""Host-owned declarative settings and secret-reference resolution for plugins."""
from __future__ import annotations

import copy
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .models import PluginDefinition
from .security import PluginStateError, PluginValidationError, normalize_namespace
from .storage import default_plugin_storage_root


_FIELD_ID_RE = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
_SECRET_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
_SUPPORTED_TYPES = frozenset({"string", "boolean", "integer", "number"})
_MAX_FIELDS = 64
_MAX_FILE_BYTES = 2 * 1024 * 1024
_MAX_STRING_LENGTH = 4000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def default_plugin_settings_path(storage_root: Path | str | None = None) -> Path:
    root = Path(storage_root or default_plugin_storage_root()).expanduser().resolve()
    return root / "_host" / "settings.json"


def _raw_schema(plugin: PluginDefinition) -> Any:
    manifest = plugin.raw_manifest
    for key in ("settings_schema", "settingsSchema"):
        if key in manifest:
            return manifest.get(key)
    capabilities = manifest.get("capabilities")
    if isinstance(capabilities, Mapping):
        return capabilities.get("settings")
    return None


def _declared_secret_names(plugin: PluginDefinition) -> frozenset[str]:
    raw = plugin.permissions.get("secrets") if isinstance(plugin.permissions, Mapping) else None
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, (list, tuple, set, frozenset)):
        values = raw
    else:
        values = []
    return frozenset(str(item).strip() for item in values if _SECRET_NAME_RE.fullmatch(str(item).strip()))


def _validate_scalar(value: Any, field: Mapping[str, Any]) -> Any:
    field_type = str(field["type"])
    if field_type == "string":
        if not isinstance(value, str):
            raise PluginValidationError(f"Setting {field['id']!r} must be a string")
        minimum = int(field.get("min_length", 0))
        maximum = int(field.get("max_length", _MAX_STRING_LENGTH))
        if not minimum <= len(value) <= maximum:
            raise PluginValidationError(
                f"Setting {field['id']!r} length must be between {minimum} and {maximum}"
            )
    elif field_type == "boolean":
        if not isinstance(value, bool):
            raise PluginValidationError(f"Setting {field['id']!r} must be a boolean")
    elif field_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise PluginValidationError(f"Setting {field['id']!r} must be an integer")
    elif field_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise PluginValidationError(f"Setting {field['id']!r} must be a number")
        if not (-1e308 <= float(value) <= 1e308):
            raise PluginValidationError(f"Setting {field['id']!r} must be finite")
    if field_type in {"integer", "number"}:
        if "minimum" in field and value < field["minimum"]:
            raise PluginValidationError(f"Setting {field['id']!r} is below its minimum")
        if "maximum" in field and value > field["maximum"]:
            raise PluginValidationError(f"Setting {field['id']!r} is above its maximum")
    enum = field.get("enum")
    if isinstance(enum, list) and value not in enum:
        raise PluginValidationError(f"Setting {field['id']!r} is not an allowed value")
    return copy.deepcopy(value)


def plugin_settings_schema(plugin: PluginDefinition) -> Optional[Dict[str, Any]]:
    """Validate and normalize the intentionally small host-rendered schema subset."""

    raw = _raw_schema(plugin)
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or str(raw.get("type") or "object") != "object":
        raise PluginValidationError("Plugin settings schema must be an object schema")
    properties = raw.get("properties")
    if not isinstance(properties, Mapping) or len(properties) > _MAX_FIELDS:
        raise PluginValidationError("Plugin settings schema properties must contain at most 64 fields")
    raw_required = raw.get("required") or []
    if not isinstance(raw_required, list) or any(not isinstance(item, str) for item in raw_required):
        raise PluginValidationError("Plugin settings schema required must be an array of field names")
    required = set(raw_required)
    if not required.issubset(properties):
        raise PluginValidationError("Plugin settings schema requires an unknown field")
    allowed_secrets = _declared_secret_names(plugin)
    fields = []
    for field_id, raw_field in properties.items():
        field_id = str(field_id or "").strip()
        if not _FIELD_ID_RE.fullmatch(field_id) or not isinstance(raw_field, Mapping):
            raise PluginValidationError(f"Invalid plugin setting field {field_id!r}")
        field_type = str(raw_field.get("type") or "string").strip().lower()
        title = str(raw_field.get("title") or field_id).strip()
        description = str(raw_field.get("description") or "").strip()
        value_format = str(raw_field.get("format") or "").strip().lower()
        if field_type not in _SUPPORTED_TYPES or not title or len(title) > 64 or len(description) > 200:
            raise PluginValidationError(f"Invalid schema for plugin setting {field_id!r}")
        field: Dict[str, Any] = {
            "id": field_id,
            "type": field_type,
            "title": title,
            "description": description,
            "required": field_id in required,
        }
        if value_format == "secret":
            secret_ref = str(raw_field.get("secret_ref") or "").strip()
            if field_type != "string" or secret_ref not in allowed_secrets:
                raise PluginValidationError(
                    f"Secret setting {field_id!r} must reference a permissions.secrets entry"
                )
            if "default" in raw_field or "enum" in raw_field:
                raise PluginValidationError(f"Secret setting {field_id!r} cannot declare a value")
            field.update({"format": "secret", "secret_ref": secret_ref})
            fields.append(field)
            continue
        if value_format and value_format not in {"text", "multiline"}:
            raise PluginValidationError(f"Unsupported format for plugin setting {field_id!r}")
        if field_type != "string" and value_format:
            raise PluginValidationError(f"Only string settings can declare a text format")
        if value_format:
            field["format"] = value_format
        if field_type == "string":
            minimum = int(raw_field.get("minLength", 0))
            maximum = int(raw_field.get("maxLength", _MAX_STRING_LENGTH))
            if not 0 <= minimum <= maximum <= _MAX_STRING_LENGTH:
                raise PluginValidationError(f"Invalid length bounds for plugin setting {field_id!r}")
            field.update({"min_length": minimum, "max_length": maximum})
        if field_type in {"integer", "number"}:
            for source, target in (("minimum", "minimum"), ("maximum", "maximum")):
                if source in raw_field:
                    number = raw_field[source]
                    if isinstance(number, bool) or not isinstance(number, (int, float)):
                        raise PluginValidationError(f"Invalid numeric bound for {field_id!r}")
                    field[target] = number
            if "minimum" in field and "maximum" in field and field["minimum"] > field["maximum"]:
                raise PluginValidationError(f"Invalid numeric range for {field_id!r}")
        if "enum" in raw_field:
            enum = raw_field["enum"]
            if not isinstance(enum, list) or not 1 <= len(enum) <= 32:
                raise PluginValidationError(f"Invalid enum for plugin setting {field_id!r}")
            normalized_enum = []
            for item in enum:
                normalized_enum.append(_validate_scalar(item, field))
            if len({json.dumps(item, sort_keys=True) for item in normalized_enum}) != len(normalized_enum):
                raise PluginValidationError(f"Duplicate enum value for plugin setting {field_id!r}")
            field["enum"] = normalized_enum
        if "default" in raw_field:
            field["default"] = _validate_scalar(raw_field["default"], field)
        fields.append(field)
    return {
        "schema_version": int(raw.get("schema_version", 1)),
        "title": str(raw.get("title") or plugin.name).strip()[:64],
        "description": str(raw.get("description") or "").strip()[:200],
        "fields": fields,
    }


class PluginSettingsStore:
    """Atomic host state containing non-secret values only."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or default_plugin_settings_path()).expanduser()
        self._lock = threading.RLock()

    def _read_unlocked(self) -> Dict[str, Any]:
        if not self.path.is_file():
            return {"version": 1, "plugins": {}}
        try:
            if self.path.stat().st_size > _MAX_FILE_BYTES:
                raise PluginStateError("Plugin settings store is too large")
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PluginStateError(f"Cannot read plugin settings {self.path}: {exc}") from exc
        if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("plugins"), dict):
            raise PluginStateError("Plugin settings must be a version 1 JSON object")
        return raw

    def _write_unlocked(self, data: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        if len(encoded) > _MAX_FILE_BYTES:
            raise PluginStateError("Plugin settings store is too large")
        temporary = self.path.with_name(
            f".{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        try:
            with temporary.open("wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise PluginStateError(f"Cannot write plugin settings {self.path}: {exc}") from exc

    def values(self, plugin: PluginDefinition) -> Dict[str, Any]:
        schema = plugin_settings_schema(plugin)
        if schema is None:
            return {}
        fields = {field["id"]: field for field in schema["fields"] if field.get("format") != "secret"}
        with self._lock:
            entry = self._read_unlocked()["plugins"].get(plugin.plugin_id, {})
            stored = entry.get("values", {}) if isinstance(entry, Mapping) else {}
            if not isinstance(stored, Mapping):
                raise PluginStateError(f"Invalid settings entry for plugin {plugin.plugin_id!r}")
            result = {
                field_id: copy.deepcopy(field["default"])
                for field_id, field in fields.items()
                if "default" in field
            }
            for field_id, value in stored.items():
                field = fields.get(str(field_id))
                if field is None:
                    continue
                result[str(field_id)] = _validate_scalar(value, field)
            return result

    def update(self, plugin: PluginDefinition, changes: Mapping[str, Any]) -> Dict[str, Any]:
        schema = plugin_settings_schema(plugin)
        if schema is None:
            raise PluginValidationError(f"Plugin {plugin.plugin_id!r} has no settings schema")
        if not isinstance(changes, Mapping) or len(changes) > _MAX_FIELDS:
            raise PluginValidationError("Plugin settings update must be an object with at most 64 fields")
        fields = {field["id"]: field for field in schema["fields"]}
        with self._lock:
            data = self._read_unlocked()
            entry = data["plugins"].get(plugin.plugin_id, {})
            current = dict(entry.get("values") or {}) if isinstance(entry, Mapping) else {}
            for raw_id, value in changes.items():
                field_id = str(raw_id or "")
                field = fields.get(field_id)
                if field is None:
                    raise PluginValidationError(f"Unknown plugin setting {field_id!r}")
                if field.get("format") == "secret":
                    raise PluginValidationError("Secret references are manifest-owned and cannot be updated here")
                if value is None:
                    current.pop(field_id, None)
                else:
                    current[field_id] = _validate_scalar(value, field)
            namespace = normalize_namespace(plugin.plugin_id)
            data["plugins"][namespace] = {
                "schema_version": schema["schema_version"],
                "values": current,
                "updated_at": _now_iso(),
            }
            self._write_unlocked(data)
        return self.values(plugin)


def public_plugin_settings(
    plugin: PluginDefinition,
    *,
    store: PluginSettingsStore | None = None,
    environment: Mapping[str, str] | None = None,
) -> Optional[Dict[str, Any]]:
    schema = plugin_settings_schema(plugin)
    if schema is None:
        return None
    values = (store or PluginSettingsStore()).values(plugin)
    env = os.environ if environment is None else environment
    fields = []
    missing_required = []
    for field in schema["fields"]:
        public = copy.deepcopy(field)
        if field.get("format") == "secret":
            public["reference"] = public.pop("secret_ref")
            public["configured"] = bool(str(env.get(str(field["secret_ref"])) or ""))
            if field["required"] and not public["configured"]:
                missing_required.append(field["id"])
        else:
            public["value"] = copy.deepcopy(values.get(field["id"]))
            if field["required"] and field["id"] not in values:
                missing_required.append(field["id"])
        fields.append(public)
    return {
        "plugin_id": plugin.plugin_id,
        "schema_version": schema["schema_version"],
        "title": schema["title"],
        "description": schema["description"],
        "valid": not missing_required,
        "missing_required": missing_required,
        "fields": fields,
    }


def resolve_plugin_settings_context(
    plugin: PluginDefinition,
    *,
    storage_root: Path | str | None = None,
    environment: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    schema = plugin_settings_schema(plugin)
    if schema is None:
        return {"settings": {}, "secrets": {}}
    values = PluginSettingsStore(default_plugin_settings_path(storage_root)).values(plugin)
    env = os.environ if environment is None else environment
    secrets = {
        field["id"]: str(env.get(str(field["secret_ref"])) or "")
        for field in schema["fields"]
        if field.get("format") == "secret" and str(env.get(str(field["secret_ref"])) or "")
    }
    return {"settings": values, "secrets": secrets}


__all__ = [
    "PluginSettingsStore",
    "default_plugin_settings_path",
    "plugin_settings_schema",
    "public_plugin_settings",
    "resolve_plugin_settings_context",
]
