"""Public message attachment admission using host-issued upload identities."""
from __future__ import annotations

from .errors import ControlError


def prepare_message_attachments(principal, params, control_store):
    attachments = params.get("attachments")
    if "attachments" not in params:
        return params
    if not isinstance(attachments, list) or len(attachments) > 32:
        raise ControlError("invalid_attachments", "attachments must contain at most 32 upload identities")
    if not attachments:
        return params
    from agent_harness import WORK_DIR
    from attachments import get_attachment_store
    from attachments.admission import AdmissionContext, admit_content
    store = get_attachment_store(WORK_DIR)
    blocks = [{"type": "text", "text": params["message"]}]
    for identity in attachments:
        if not isinstance(identity, dict) or set(identity) != {"id"} or not isinstance(identity["id"], str):
            raise ControlError("invalid_attachments", "Each attachment requires a host-issued id")
        record = control_store.get("message_uploads", identity["id"])
        if not record or record.get("owner") != principal.id:
            raise ControlError("attachment_not_found", "Attachment is unavailable to this caller", status=404)
        if record.get("attachment"):
            blocks.append({"type": "image", "attachment": record["attachment"]})
        else:
            blocks.append({"type": "local_file", "local_file": {"path": record["path"], "name": record["name"]}})
    content = admit_content(blocks, AdmissionContext(store), scan_paths=False, scan_remote=False, strict=True)
    return {**params, "_legacy_user_content": content}
