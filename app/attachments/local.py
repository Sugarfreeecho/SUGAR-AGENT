import asyncio
import hashlib
import json
import os
import re
import stat
import uuid
from pathlib import Path
from config_paths import config_path

from .errors import AttachmentError
from .normalization import EXTENSIONS, decode_image, normalize_image
from .types import ImageAttachmentLimits, ImageRequestPolicy, SaveImageAttachment, StoredImageAttachment

from .locking import attachment_lock
from .metrics import count, measure
from .validation import verify_once


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def checked_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise AttachmentError("Invalid attachment identity", "INVALID_ATTACHMENT_REF")
    return value[7:]


def atomic_write(path, data, readonly=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_bytes(data)
        if path.exists():
            path.chmod(stat.S_IWRITE | stat.S_IREAD)
        os.replace(temporary, path)
        if readonly:
            path.chmod(stat.S_IREAD)
    finally:
        temporary.unlink(missing_ok=True)


def safe_name(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name or "file").replace("\\", "/").rsplit("/", 1)[-1])
    return (name.strip(" .")[:120] or "file")


class LocalAttachmentStore:
    def __init__(self, work_dir, limits=None, normalization_policy=None, normalization_max_dimension=8192):
        self.root = config_path(work_dir, "attachments", "v1")
        self.cache_root = config_path(work_dir, "cache", "attachments", "request-images")
        self.limits = limits or ImageAttachmentLimits()
        self.normalization_policy = normalization_policy or ImageRequestPolicy()
        self.normalization_max_dimension = normalization_max_dimension

    def validate_image(self, data, media_type):
        decode_image(data, media_type, self.limits)

    def occupied_bytes(self):
        images = (p for p in self.root.glob("*/*/image.*") if p.suffix != ".json")
        files = self.root.glob("*/*/files/*")
        return sum(p.stat().st_size for group in (images, files) for p in group if p.is_file())

    def _object_dir(self, attachment_id):
        key = checked_id(attachment_id)
        return self.root / key[:2] / key

    def image_host_path(self, ref):
        try:
            directory = self._object_dir(ref["attachmentId"])
            ext = EXTENSIONS[ref["mediaType"]]
            if any(type(ref[k]) is not int or ref[k] <= 0 for k in ("bytes", "width", "height")):
                raise ValueError()
            return str(directory / ("image" + ext))
        except (KeyError, TypeError, ValueError):
            raise AttachmentError("Invalid image attachment reference", "INVALID_ATTACHMENT_REF") from None

    def file_host_path(self, ref):
        if ref.get("name") != safe_name(ref.get("name")):
            raise AttachmentError("Invalid file name", "INVALID_ATTACHMENT_REF")
        return str(self._object_dir(ref["attachmentId"]) / "files" / ref["name"])

    def _source_index_path(self, source_id):
        """源字节哈希 -> 已归一化 ref 的小索引，避免重复读图二次编码。

        放在 ``_sources`` 命名空间，对象目录只接受 64 位十六进制 id，二者不会冲突，
        ``occupied_bytes`` 的 ``image.*`` 扫描也不会把索引计入配额。
        """
        key = checked_id(source_id)
        return self.root / "_sources" / key[:2] / (key[2:] + ".json")

    def _source_hit(self, source_id):
        """返回命中且对象完好的 ref；任何异常都视为未命中并回退到归一化。"""
        path = self._source_index_path(source_id)
        try:
            payload = json.loads(path.read_text())
            if payload.get("sourceId") != source_id:
                return None
            ref = payload["ref"]
            host = Path(self.image_host_path(ref))
            if not host.is_file() or host.stat().st_size != ref["bytes"]:
                return None
            return ref
        except (OSError, ValueError, KeyError, TypeError, AttachmentError):
            return None

    def save_images_sync(self, inputs):
        if len(inputs) > self.limits.max_images_per_message:
            raise AttachmentError("Too many images in message", "TOO_MANY_IMAGES")
        if sum(len(i.data) for i in inputs) > self.limits.max_message_image_bytes:
            raise AttachmentError("Message images exceed byte limit", "IMAGES_TOO_LARGE")
        refs = [None] * len(inputs)
        pending = []
        for index, source in enumerate(inputs):
            hit = self._source_hit(digest(source.data))
            if hit is None:
                pending.append(index)
                continue
            refs[index] = {**hit, "name": safe_name(source.name)} if source.name else dict(hit)
        # Validate and normalize the complete batch before committing any object.
        normalized = {}
        if pending:
            with measure("normalization"):
                for index in pending:
                    source = inputs[index]
                    normalized[index] = normalize_image(
                        source.data, source.media_type, self.limits,
                        self.normalization_policy, self.normalization_max_dimension,
                    )
        created = []
        with attachment_lock(self.root.parent, "catalog"):
            quota = int(os.getenv("ATTACHMENT_STORE_MAX_BYTES", str(10 * 1024 ** 3)))
            occupied = self.occupied_bytes()
            additions = {digest(item[0]): len(item[0]) for item in normalized.values() if not (self._object_dir(digest(item[0])) / "image.json").exists()}
            if occupied + sum(additions.values()) > quota:
                raise AttachmentError("Attachment storage quota exceeded", "ATTACHMENT_QUOTA_EXCEEDED")
            try:
                for index, source in enumerate(inputs):
                    if refs[index] is not None:
                        continue
                    data, media_type, size, original = normalized[index]
                    ref = {"attachmentId": digest(data), "mediaType": media_type, "bytes": len(data), "width": size[0], "height": size[1]}
                    if source.name:
                        ref["name"] = safe_name(source.name)
                    if source.source:
                        ref["source"] = dict(source.source)
                    if original != size:
                        ref["originalDimensions"] = {"width": original[0], "height": original[1]}
                    path = Path(self.image_host_path(ref))
                    metadata = path.parent / "image.json"
                    if not path.exists():
                        created.append(path)
                        atomic_write(path, data, readonly=True)
                    elif digest(path.read_bytes()) != ref["attachmentId"]:
                        raise AttachmentError("Stored image digest mismatch", "ATTACHMENT_CORRUPT")
                    if not metadata.exists():
                        created.append(metadata)
                        atomic_write(metadata, json.dumps({k: v for k, v in ref.items() if k not in {"name", "originalDimensions", "source"}}).encode(), readonly=True)
                    refs[index] = ref
                # 索引最后落盘：任何失败都会连同对象一起回滚，不留下悬挂映射。
                for index in pending:
                    source_id = digest(inputs[index].data)
                    index_path = self._source_index_path(source_id)
                    if index_path.exists():
                        continue
                    created.append(index_path)
                    atomic_write(index_path, json.dumps({"sourceId": source_id, "ref": refs[index]}).encode(), readonly=True)
            except Exception as exc:
                for path in reversed(created):
                    if path.exists():
                        path.chmod(stat.S_IWRITE | stat.S_IREAD)
                        path.unlink()
                if isinstance(exc, AttachmentError):
                    raise
                raise AttachmentError("Could not commit attachment batch", "ATTACHMENT_WRITE_FAILED") from None
        count("images.saved", len(refs))
        return refs

    async def save_images(self, inputs):
        return await asyncio.to_thread(self.save_images_sync, inputs)

    def save_file_sync(self, name, data):
        ref = {"attachmentId": digest(data), "name": safe_name(name), "bytes": len(data)}
        with attachment_lock(self.root.parent, "catalog"):
            path = Path(self.file_host_path(ref))
            try:
                if not path.exists():
                    occupied = self.occupied_bytes()
                    if occupied + len(data) > int(os.getenv("ATTACHMENT_STORE_MAX_BYTES", str(10 * 1024 ** 3))):
                        raise AttachmentError("Attachment storage quota exceeded", "ATTACHMENT_QUOTA_EXCEEDED")
                    atomic_write(path, data, readonly=True)
                elif digest(path.read_bytes()) != ref["attachmentId"]:
                    raise AttachmentError("Stored file digest mismatch", "ATTACHMENT_CORRUPT")
            except OSError:
                raise AttachmentError("Could not save file", "ATTACHMENT_WRITE_FAILED") from None
        return ref

    async def save_file(self, name, data):
        return await asyncio.to_thread(self.save_file_sync, name, data)

    def ref_by_id(self, attachment_id):
        try:
            ref = json.loads((self._object_dir(attachment_id) / "image.json").read_text())
            if ref["attachmentId"] != attachment_id:
                raise ValueError()
            self.read_image_sync(ref)
            return ref
        except AttachmentError:
            raise
        except (OSError, ValueError, KeyError):
            raise AttachmentError("Attachment missing or corrupt", "ATTACHMENT_CORRUPT") from None

    def read_image_sync(self, ref):
        path = self.image_host_path(ref)
        try:
            data = Path(path).read_bytes()
            if len(data) != ref["bytes"] or digest(data) != ref["attachmentId"]:
                raise ValueError()
            def validate():
                image, _ = decode_image(data, ref["mediaType"], self.limits)
                if image.size != (ref["width"], ref["height"]) or image.mode not in {"RGB", "RGBA"} or getattr(image, "n_frames", 1) != 1:
                    raise ValueError()
            verify_once(("source", ref["attachmentId"], ref["mediaType"], ref["width"], ref["height"], self.limits), validate)
            return StoredImageAttachment(dict(ref), data)
        except Exception:
            raise AttachmentError("Attachment missing or corrupt", "ATTACHMENT_CORRUPT") from None

    async def read_image(self, ref):
        return await asyncio.to_thread(self.read_image_sync, ref)

    def read_request_image_sync(self, ref, policy):
        from .request_image import read_request_image
        with measure("request_image"):
            return read_request_image(self, ref, policy)

    async def read_request_image(self, ref, policy):
        return await asyncio.to_thread(self.read_request_image_sync, ref, policy)

    def prepare_path(self, path):
        path = Path(path)
        if path.stat().st_size > self.limits.max_image_bytes:
            raise AttachmentError("Image exceeds byte limit", "IMAGES_TOO_LARGE")
        data = path.read_bytes()
        # Local legacy tool output may be BMP; MCP and uploads stay strict.
        if path.suffix.lower() == ".bmp":
            from PIL import Image
            from io import BytesIO
            with Image.open(BytesIO(data)) as image:
                if image.width * image.height > self.limits.max_image_pixels or max(image.size) > self.limits.max_image_dimension:
                    raise AttachmentError("Image exceeds dimension limit", "IMAGES_TOO_LARGE")
                out = BytesIO()
                image.save(out, format="PNG")
                data = out.getvalue()
        _, media_type = decode_image(data, limits=self.limits)
        return SaveImageAttachment(data, media_type, path.name)

    def save_path(self, path):
        path = Path(path)
        if path.parent.parent.parent == self.root and path.name.startswith("image."):
            return self.ref_by_id("sha256:" + path.parent.name)
        if path.stat().st_size > self.limits.max_image_bytes:
            raise AttachmentError("Image exceeds byte limit", "IMAGES_TOO_LARGE")
        # 先按源字节判重：命中时连解码都省掉（重复读图从秒级降到几十毫秒）。
        hit = self._source_hit(digest(path.read_bytes()))
        if hit is not None:
            ref = dict(hit)
            if path.name:
                ref["name"] = safe_name(path.name)
            return ref
        return self.save_images_sync([self.prepare_path(path)])[0]
