"""Admission/migration and transient request projection, shared by all adapters."""
import base64
import os
import re

from . import budget_policy, get_attachment_store, prompt_language, request_policy
from .messages_text import file_handle_text, offloaded_image_text, request_image_handle_text, text_only_image_text
from .request_budget import offload_request_images_with_policy, walk_images

IMAGE_PATH_RE = re.compile(
    r'(?P<q>["\'])(?P<qp>.+?\.(?:png|jpe?g|gif|webp|bmp))(?P=q)|'
    r'(?P<up>(?:[A-Za-z]:[\\/]|/|\.{1,2}[\\/])[^\s<>"\']+?\.(?:png|jpe?g|gif|webp|bmp))', re.I)
DATA_IMAGE_RE = re.compile(r'data:(image/[a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=]+)')


def scan_enabled():
    return os.getenv("MULTIMODAL_TEXT_PATH_SCAN", "on").strip().lower() not in {"off", "0", "false", "no"}


def map_text_parts(content, transform):
    """Transform text without stringifying, truncating or reordering image refs."""
    if isinstance(content, str):
        return transform(content)
    if isinstance(content, list):
        return [({**block, "text": transform(str(block.get("text") or ""))}
                 if isinstance(block, dict) and block.get("type") == "text"
                 else {**block, "content": map_text_parts(block["content"], transform)}
                 if isinstance(block, dict) and isinstance(block.get("content"), list)
                 else block) for block in content]
    return content


def durable_content(content, store=None, scan=False, *, remote=False, strict=False):
    """Compatibility facade; new ingress calls the explicit admission service."""
    from .admission import AdmissionContext, admit_content
    return admit_content(content, AdmissionContext(store or get_attachment_store(), verify_refs=False),
                         scan_paths=scan, scan_remote=remote, strict=strict)


def project_request_images(messages, *, image_enabled=True, client=None, store=None, language=None, image_states=None):
    store = store or get_attachment_store()
    language = language or prompt_language()
    versions = {}
    occurrences = [block["attachment"] for message in messages for block in walk_images(message.get("content"))]
    if image_enabled:
        for message in messages:
            for block in walk_images(message.get("content")):
                ref = block["attachment"]
                if ref["attachmentId"] not in versions:
                    versions[ref["attachmentId"]] = store.read_request_image_sync(ref, request_policy(client))
        if image_states is not None:
            from .request_budget import offloaded_image_prefix_count
            policy = budget_policy(client)
            sizes = [versions[ref["attachmentId"]].bytes for ref in occurrences]
            lengths = [4 * ((size + 2) // 3) for size in sizes] if policy.representation == "base64" else sizes
            omitted = offloaded_image_prefix_count(lengths, policy)
            for index, ref in enumerate(occurrences):
                version = versions[ref["attachmentId"]]
                image_states.append({"attachmentId": ref["attachmentId"], "state": "omitted_budget" if index < omitted else "prepared",
                                     "requestWidth": version.width, "requestHeight": version.height})
        messages = offload_request_images_with_policy(
            messages, budget_policy(client), lambda ref: versions[ref["attachmentId"]].bytes,
            lambda ref: offloaded_image_text(ref, store.image_host_path(ref), language))
        from .metrics import count
        count("request.images", len(occurrences))
        count("request.images_omitted_budget", len(occurrences) - sum(1 for message in messages for _ in walk_images(message.get("content"))))
    elif image_states is not None:
        image_states.extend({"attachmentId": ref["attachmentId"], "state": "omitted_capability"} for ref in occurrences)

    def project(content):
        if not isinstance(content, list):
            return content
        out = []
        for block in content:
            if block.get("type") == "image" and block.get("attachment"):
                ref = block["attachment"]
                if not image_enabled:
                    out.append({"type": "text", "text": text_only_image_text(ref, language)})
                else:
                    version = versions[ref["attachmentId"]]
                    out.extend([
                        {"type": "text", "text": request_image_handle_text(ref, version, store.image_host_path(ref), language)},
                        {"type": "image_url", "image_url": {"url": f"data:{version.media_type};base64," + base64.b64encode(version.data).decode("ascii")}},
                    ])
            elif block.get("type") == "file" and block.get("attachment"):
                ref = block["attachment"]
                out.append({"type": "text", "text": file_handle_text(ref, store.file_host_path(ref), language)})
            elif isinstance(block.get("content"), list):
                out.append({**block, "content": project(block["content"])})
            else:
                out.append(block)
        return out
    return [{**message, "content": project(message.get("content"))} for message in messages]


def chat_tool_images(messages):
    """Chat tool messages must be strings. Flush images after the tool batch."""
    out, pending = [], []

    def flush():
        if pending:
            out.append({"role": "user", "content": [{"type": "text", "text": "Attached image(s) from tool result:"}, *pending]})
            pending.clear()

    for message in messages:
        if message.get("role") != "tool":
            flush()
        content = message.get("content")
        if message.get("role") == "tool" and isinstance(content, list):
            texts = []
            for index, block in enumerate(content):
                if block.get("type") == "image_url":
                    pending.append(block)
                elif block.get("type") == "text":
                    if index + 1 < len(content) and content[index + 1].get("type") == "image_url":
                        pending.append(block)
                    else:
                        texts.append(block.get("text") or "")
            out.append({**message, "content": "\n".join(texts)})
        else:
            out.append(message)
    flush()
    return out


def needs_image_migration(value) -> bool:
    """Cheap scan: does anything in ``value`` need redaction at all?

    Runtime events are constructed per row; rebuilding every dict/list on the
    hot path (even when no images exist) made large branch materialization and
    legacy migration pathologically slow. This detector walks the structure
    without allocating replacements and stops at the first hit.
    """

    if isinstance(value, dict):
        if value.get("type") in {"image", "image_url", "input_image"} and not value.get("attachment"):
            return True
        if value.get("type") == "base64":
            return True
        return any(needs_image_migration(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(needs_image_migration(item) for item in value)
    if isinstance(value, str):
        return bool(DATA_IMAGE_RE.search(value))
    return False


# Backward-compatible alias for diagnostics written before the public name was
# introduced. Runtime code should use ``needs_image_migration``.
_has_image_payload = needs_image_migration


def redact_image_payloads(value):
    """Log/event defense: never serialize raw provider image blocks.

    未命中（无图片内容）时原样返回同一个对象，避免每个事件全量深拷贝；
    命中时才走重建路径。
    """
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if not needs_image_migration(value):
        return value
    return _redact_image_payloads_deep(value)


def _redact_image_payloads_deep(value):
    if isinstance(value, dict):
        if value.get("type") in {"image", "image_url", "input_image"} and not value.get("attachment"):
            return {"type": "text", "text": "[image payload omitted from log]"}
        if value.get("type") == "base64":
            return {"type": "text", "text": "[image payload omitted from log]"}
        return {k: redact_image_payloads(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_image_payloads(v) for v in value]
    if isinstance(value, str):
        return DATA_IMAGE_RE.sub("[image payload omitted from log]", value)
    return value
