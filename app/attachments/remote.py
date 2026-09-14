"""Bounded, credential-free image downloads with DNS addresses pinned per hop."""
import http.client
import ipaddress
import os
import socket
import ssl
import time
import threading
from queue import Queue, Empty
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from .errors import AttachmentError
from .types import SaveImageAttachment


@dataclass(frozen=True)
class RemoteImagePolicy:
    mode: str = "ingest"
    timeout: float = 20.0
    redirects: int = 3
    allowed_hosts: tuple[str, ...] = ()

    def __post_init__(self):
        if self.mode not in {"ingest", "passthrough", "disabled"}:
            raise ValueError("Invalid remote image mode")
        if self.timeout <= 0 or self.redirects < 0:
            raise ValueError("Invalid remote image download limits")

    @classmethod
    def from_env(cls):
        return cls(os.getenv("MULTIMODAL_REMOTE_IMAGE_MODE", "ingest"),
                   float(os.getenv("ATTACHMENT_REMOTE_TIMEOUT_SECONDS", "20")),
                   int(os.getenv("ATTACHMENT_REMOTE_MAX_REDIRECTS", "3")),
                   tuple(h.strip().lower() for h in os.getenv("ATTACHMENT_REMOTE_ALLOWED_HOSTS", "").split(",") if h.strip()))


_dns_slots = threading.BoundedSemaphore(4)


def _addresses(host, port, timeout):
    if not _dns_slots.acquire(blocking=False):
        raise AttachmentError("Image DNS resolver is busy", "ATTACHMENT_BUSY")
    result = Queue(maxsize=1)
    def resolve():
        try:
            result.put((socket.getaddrinfo(host, port, type=socket.SOCK_STREAM), None))
        except Exception as exc:
            result.put((None, exc))
        finally:
            _dns_slots.release()
    threading.Thread(target=resolve, daemon=True, name="image-dns").start()
    try:
        rows, error = result.get(timeout=timeout)
    except Empty:
        raise AttachmentError("Image DNS lookup timed out", "REMOTE_IMAGE_TIMEOUT") from None
    if error:
        raise error
    return rows


def resolve_target(url, policy, timeout=None):
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError()
        host = parsed.hostname.encode("idna").decode("ascii").lower()
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = list(dict.fromkeys(row[4][0] for row in _addresses(host, port, timeout or policy.timeout)))
        if not addresses:
            raise OSError()
        if host not in policy.allowed_hosts and any(not ipaddress.ip_address(ip).is_global for ip in addresses):
            raise AttachmentError("Remote image destination is not permitted", "REMOTE_IMAGE_BLOCKED")
        return parsed, host, port, addresses[0]
    except AttachmentError:
        raise
    except (ValueError, OSError, UnicodeError):
        raise AttachmentError("Remote image URL cannot be resolved", "REMOTE_IMAGE_UNAVAILABLE") from None


def _open(url, policy, timeout):
    deadline = time.monotonic() + timeout
    parsed, host, port, address = resolve_target(url, policy, timeout)
    timeout = deadline - time.monotonic()
    if timeout <= 0:
        raise TimeoutError()
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    sock = socket.create_connection((address, port), timeout=timeout)
    live_socket = [sock]
    def expire():
        try:
            live_socket[0].shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    timer = threading.Timer(max(.001, deadline - time.monotonic()), expire)
    timer.daemon = True
    timer.start()
    conn._image_deadline_timer = timer
    try:
        if parsed.scheme == "https":
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
            live_socket[0] = sock
        conn.sock = sock
        conn.request("GET", (parsed.path or "/") + ("?" + parsed.query if parsed.query else ""),
                     headers={"Accept": "image/png,image/jpeg,image/webp,image/gif", "Accept-Encoding": "identity"})
        return conn, conn.getresponse()
    except Exception:
        timer.cancel()
        sock.close()
        conn.close()
        raise


def download_image(url, limits, policy=None, *, cancelled=lambda: False):
    policy = policy or RemoteImagePolicy.from_env()
    deadline = time.monotonic() + policy.timeout
    current = url
    try:
        for hop in range(policy.redirects + 1):
            remaining = deadline - time.monotonic()
            if cancelled():
                raise AttachmentError("Image download cancelled", "ATTACHMENT_CANCELLED")
            if remaining <= 0:
                raise TimeoutError()
            conn, response = _open(current, policy, remaining)
            try:
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader("Location")
                    if hop >= policy.redirects or not location:
                        raise AttachmentError("Image redirect limit exceeded", "REMOTE_IMAGE_UNAVAILABLE")
                    current = urljoin(current, location)
                    continue
                if response.status != 200:
                    raise AttachmentError("Remote image request failed", "REMOTE_IMAGE_UNAVAILABLE")
                media = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
                if media not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
                    raise AttachmentError("Remote response is not a supported image", "UNSUPPORTED_IMAGE_TYPE")
                declared = response.getheader("Content-Length")
                if declared and int(declared) > limits.max_image_bytes:
                    raise AttachmentError("Remote image exceeds byte limit", "IMAGES_TOO_LARGE")
                data = bytearray()
                while True:
                    if cancelled():
                        raise AttachmentError("Image download cancelled", "ATTACHMENT_CANCELLED")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError()
                    if conn.sock:
                        conn.sock.settimeout(remaining)
                    chunk = response.read1(min(65536, limits.max_image_bytes + 1 - len(data)))
                    if time.monotonic() >= deadline:
                        raise TimeoutError()
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data) > limits.max_image_bytes:
                        raise AttachmentError("Remote image exceeds byte limit", "IMAGES_TOO_LARGE")
                from .metrics import count
                count("remote.completed")
                count("remote.bytes", len(data))
                return SaveImageAttachment(bytes(data), media, "remote-image", {"kind": "remote", "host": urlsplit(url).hostname})
            finally:
                response.close()
                conn.close()
                timer = getattr(conn, "_image_deadline_timer", None)
                if timer:
                    timer.cancel()
    except AttachmentError:
        raise
    except (TimeoutError, socket.timeout):
        raise AttachmentError("Remote image download timed out", "REMOTE_IMAGE_TIMEOUT") from None
    except (OSError, ValueError, http.client.HTTPException):
        if time.monotonic() >= deadline:
            raise AttachmentError("Remote image download timed out", "REMOTE_IMAGE_TIMEOUT") from None
        raise AttachmentError("Remote image download failed", "REMOTE_IMAGE_UNAVAILABLE") from None
