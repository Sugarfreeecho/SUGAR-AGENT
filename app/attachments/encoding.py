import base64
import binascii
from io import BytesIO

from .errors import AttachmentError

QUALITIES = (90, 80, 70, 60, 50, 40)


def decode_base64(data: str) -> bytes:
    try:
        decoded = base64.b64decode(data, validate=True)
        if not decoded or base64.b64encode(decoded).decode("ascii") != data:
            raise ValueError()
        return decoded
    except (ValueError, TypeError, binascii.Error):
        raise AttachmentError("Image data must be canonical base64", "UNSUPPORTED_IMAGE_TYPE") from None


def encode_image(image, max_bytes):
    alpha = image.mode == "RGBA"
    smallest = None
    for quality in QUALITIES:
        out = BytesIO()
        image.save(out, format="WEBP" if alpha else "JPEG", quality=quality, **({"method": 6} if alpha else {}))
        data = out.getvalue()
        if smallest is None or len(data) < len(smallest):
            smallest = data
        if len(data) <= max_bytes:
            return data, "image/webp" if alpha else "image/jpeg"
    return smallest, "image/webp" if alpha else "image/jpeg"
