import math
from io import BytesIO

from PIL import Image, ImageCms, ImageOps

from .encoding import encode_image
from .errors import AttachmentError
from .types import ImageAttachmentLimits, ImageRequestPolicy

MEDIA_TYPES = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp", "GIF": "image/gif"}
EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}


def decode_image(data, media_type=None, limits=None):
    limits = limits or ImageAttachmentLimits()
    if len(data) > limits.max_image_bytes:
        raise AttachmentError("Image exceeds encoded byte limit", "IMAGES_TOO_LARGE")
    try:
        image = Image.open(BytesIO(data))
        actual = MEDIA_TYPES.get(image.format)
        if actual is None or (media_type is not None and actual != media_type):
            raise AttachmentError("Unsupported or mismatched image type", "UNSUPPORTED_IMAGE_TYPE")
        if image.width * image.height > limits.max_image_pixels or max(image.size) > limits.max_image_dimension:
            raise AttachmentError("Image exceeds pixel or dimension limit", "IMAGES_TOO_LARGE")
        image.load()
        return image, actual
    except AttachmentError:
        raise
    except Exception:
        raise AttachmentError("Image cannot be decoded", "UNSUPPORTED_IMAGE_TYPE") from None


def dimensions(width, height, max_pixels, max_dimension=8192):
    ratio = min(1.0, math.sqrt(max_pixels / (width * height)), max_dimension / max(width, height))
    return max(1, math.floor(width * ratio)), max(1, math.floor(height * ratio))


def normalize_image(data, media_type, limits=None, policy=None, max_dimension=8192):
    image, _ = decode_image(data, media_type, limits)
    policy = policy or ImageRequestPolicy()
    image = ImageOps.exif_transpose(image)
    original = image.size
    alpha = "A" in image.getbands() or "transparency" in image.info
    mode = "RGBA" if alpha else "RGB"
    icc = image.info.get("icc_profile")
    try:
        if icc:
            image = ImageCms.profileToProfile(image, ImageCms.ImageCmsProfile(BytesIO(icc)), ImageCms.createProfile("sRGB"), outputMode=mode)
        elif image.mode.startswith("I;16") or image.mode == "I":
            image = image.point(lambda value: value * (255 / 65535)).convert("L").convert(mode)
        else:
            image = image.convert(mode)
        size = dimensions(*image.size, policy.max_pixels, max_dimension)
        if image.size != size:
            image = image.resize(size, Image.Resampling.LANCZOS)
        if alpha and image.getchannel("A").getextrema()[0] == 255:
            image = image.convert("RGB")
            alpha = False
        image.info.clear()
        encoded, actual = encode_image(image, policy.max_bytes)
        verify_normalized(encoded, actual, size, alpha)
        return encoded, actual, size, original
    except AttachmentError:
        raise
    except Exception:
        raise AttachmentError("Could not normalize image to 8-bit sRGB", "ATTACHMENT_WRITE_FAILED") from None


def verify_normalized(data, media_type, size, alpha):
    try:
        with Image.open(BytesIO(data)) as image:
            image.load()
            if (image.size != size or MEDIA_TYPES.get(image.format) != media_type
                    or getattr(image, "n_frames", 1) != 1 or image.mode not in {"RGB", "RGBA"}
                    or (alpha and image.mode != "RGBA") or image.getexif() or image.info.get("icc_profile")):
                raise ValueError()
    except Exception:
        raise AttachmentError("Encoded image failed normalization verification", "ATTACHMENT_CORRUPT") from None
