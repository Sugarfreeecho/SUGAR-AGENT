import base64
import binascii
from io import BytesIO

from .errors import AttachmentError

# 质量阶梯：三级足够覆盖 4MB 预算，避免最坏情况做六轮全量编码。
# 对齐 Deepseek Harness 的 [85, 75, 60]：「每级都能买到真实体积下降」。
QUALITIES = (85, 75, 60)

# WebP 压缩effort：0 最快。method=6 会多花 3-4 倍时间只换约 5% 体积，
# 对读图链路（同步等结果）不划算；alpha 图仍用 WebP 以保留透明度。
WEBP_EFFORT = 0


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
        image.save(out, format="WEBP" if alpha else "JPEG", quality=quality,
                   **({"method": WEBP_EFFORT} if alpha else {}))
        data = out.getvalue()
        if smallest is None or len(data) < len(smallest):
            smallest = data
        if len(data) <= max_bytes:
            return data, "image/webp" if alpha else "image/jpeg"
    return smallest, "image/webp" if alpha else "image/jpeg"
