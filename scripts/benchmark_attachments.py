"""Reproducible local cold/warm attachment preparation, without model calls."""
import json
import statistics
import sys
import tempfile
import time
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from attachments import LocalAttachmentStore, SaveImageAttachment
from attachments.types import ImageRequestPolicy


def run():
    rows = []
    for quantity in (1, 5, 20):
        with tempfile.TemporaryDirectory(prefix="myagent-image-benchmark-") as root:
            store = LocalAttachmentStore(root)
            inputs = []
            for index in range(quantity):
                image = Image.new("RGBA" if index % 2 else "RGB", (1600, 1200), (20, 40, 60, 120) if index % 2 else (20, 40, 60))
                draw = ImageDraw.Draw(image)
                for stripe in range(12):
                    draw.rectangle((stripe * 130, 100, stripe * 130 + 80, 1100), fill=(index * 9, stripe * 20, 180, 150) if index % 2 else (index * 9, stripe * 20, 180))
                draw.text((50, 50), f"Synthetic image {index}", fill="white")
                output = BytesIO()
                image.save(output, "PNG")
                inputs.append(SaveImageAttachment(output.getvalue(), "image/png"))
            started = time.perf_counter()
            refs = store.save_images_sync(inputs)
            admission_ms = (time.perf_counter() - started) * 1000
            policy = ImageRequestPolicy(512 * 512, 512 * 1024)
            timings = []
            for _ in range(4):
                started = time.perf_counter()
                versions = [store.read_request_image_sync(ref, policy) for ref in refs]
                timings.append((time.perf_counter() - started) * 1000)
            rows.append({"images": quantity, "sourceDimensions": [1600, 1200], "requestMaxPixels": policy.max_pixels,
                         "admissionMs": round(admission_ms, 2), "coldPreparationMs": round(timings[0], 2),
                         "warmPreparationMedianMs": round(statistics.median(timings[1:]), 2),
                         "storedBytes": sum(ref["bytes"] for ref in refs), "requestBytes": sum(len(version.data) for version in versions)})
    return {"scope": "Local synthetic RGB/RGBA; no provider call; warm median of three runs", "results": rows}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
