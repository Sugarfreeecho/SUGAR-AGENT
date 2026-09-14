"""I/O belongs at the event repository boundary, not in event value objects."""
from .event_schema import RuntimeEvent


def migrate_payload(event_type, payload):
    try:
        from attachments.content import durable_content, needs_image_migration, redact_image_payloads
    except ModuleNotFoundError:
        from app.attachments.content import durable_content, needs_image_migration, redact_image_payloads

    # Nearly all historical events are text-only. Avoid rebuilding large model
    # history snapshots unless the payload contains an image form that can
    # actually be migrated or redacted.
    if not needs_image_migration(payload):
        return payload

    def visit(value):
        if isinstance(value, dict):
            return {key: durable_content(item) if key == "content" and isinstance(item, (str, list))
                    else visit(item) for key, item in value.items()}
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value

    if event_type in {"message_user", "user_turn_committed", "model_user", "model_tool",
                      "model_messages_appended", "model_history_replaced", "runtime_snapshot_compacted"}:
        payload = visit(payload)
    return redact_image_payloads(payload)


def event_from_record(record):
    if isinstance(record, dict) and isinstance(record.get("payload"), dict):
        record = {**record, "payload": migrate_payload(record.get("type"), record["payload"])}
    return RuntimeEvent.from_dict(record)
