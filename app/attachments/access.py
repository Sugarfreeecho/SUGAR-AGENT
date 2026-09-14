"""Reuse remote-control principals for attachment HTTP access."""
import hmac
from urllib.parse import urlsplit

from fastapi import HTTPException

from remote_control.gateway import _is_direct_loopback_request
from remote_control.store import DevicePrincipal
from .registry import AttachmentRegistry
from .errors import AttachmentError
from .locking import attachment_lock


def principal_for_request(request, gateway=None, scope="read"):
    # None is reserved for in-process callers (including endpoint unit tests).
    if request is None:
        return DevicePrincipal("local", "Local application", frozenset({"admin"}))
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).netloc != request.headers.get("host"):
        allowed = gateway.config.allowed_origins if gateway else ()
        if origin.rstrip("/") not in allowed:
            raise HTTPException(403, "Cross-origin attachment access denied")
    if _is_direct_loopback_request(request):
        return DevicePrincipal("local", "Local application", frozenset({"admin"}))
    token = request.headers.get("authorization", "")
    token = token[7:].strip() if token.lower().startswith("bearer ") else request.cookies.get("sugaragent_remote_token", "")
    actor = None
    if gateway and gateway.config.enabled and token:
        if gateway.config.bootstrap_token and hmac.compare_digest(token, gateway.config.bootstrap_token):
            actor = DevicePrincipal("bootstrap", "Administrator", frozenset({"admin"}))
        elif gateway.store:
            actor = gateway.store.authenticate_device(token)
    if actor is None:
        raise HTTPException(401, "Attachment authentication required")
    if not actor.permits(scope):
        raise HTTPException(403, "Attachment scope denied")
    return actor


def require_attachment(store, actor, identity):
    with attachment_lock(store.root.parent, "catalog"):
        registry = AttachmentRegistry(store)
        try:
            if not actor.permits("admin") and not registry.allowed(actor.device_id, identity):
                raise HTTPException(404, "Attachment not found")
            ref = store.ref_by_id(identity)
            registry.grant(actor.device_id, [identity])
            return ref
        except AttachmentError:
            raise HTTPException(404, "Attachment not found") from None
