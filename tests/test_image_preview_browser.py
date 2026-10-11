"""Verify original-image detail and viewer gestures in a real browser."""
import io
import math
import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
Image = pytest.importorskip("PIL.Image")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def preview_browser():
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True, **({"channel": "msedge"} if os.name == "nt" else {}))
        yield browser
        browser.close()


@pytest.fixture
def preview_page(preview_browser, request):
    pixel_ratio = getattr(request, "param", 1)
    context = preview_browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=pixel_ratio)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    # Alternating single-pixel lines disappear if a fitted bitmap is enlarged.
    stripe = Image.new("RGB", (4800, 1))
    stripe.putdata([(0, 0, 0) if x % 2 else (255, 255, 255) for x in range(4800)])
    image = stripe.resize((4800, 1600), Image.Resampling.NEAREST)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    page.route("http://image-preview.test/original.png", lambda route: route.fulfill(
        status=200, content_type="image/png", body=buffer.getvalue()))
    page.route("http://image-preview.test/broken.png", lambda route: route.fulfill(status=404))
    page.route("http://image-preview.test/", lambda route: route.fulfill(
        status=200, content_type="text/html", body="<!doctype html><html></html>"))
    page.goto("http://image-preview.test/")
    css = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    page.set_content(f'''<!doctype html><html><head><style>{css}</style></head><body>
        <div class="message"><img id="thumbnail" src="/original.png" alt="高分辨率细节测试.png"
        style="width:240px;height:80px"></div></body></html>''')
    page.add_script_tag(content=(ROOT / "frontend/src/app/modules/workspace-media.js").read_text(encoding="utf-8"))
    page.locator("#thumbnail").click()
    page.wait_for_function("durableAttachmentPreviewDialog._previewFitSize !== null && !!durableAttachmentPreviewDialog._previewFitSize")
    yield page
    assert not errors, errors
    context.close()


def settled(page):
    page.wait_for_function("""() => {const d = durableAttachmentPreviewDialog;
        return !d._previewZoomFrame && !d._previewFitFrame && !d._previewSettleTimer;}""")
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")


def test_continuous_zoom_keeps_layout_stable_then_restores_detail(preview_page):
    page = preview_page
    result = page.evaluate("""async () => {
        const d = durableAttachmentPreviewDialog, image = d._previewImage;
        const startWidth = image.style.width, startHeight = image.style.height;
        const mutations = [];
        const observer = new MutationObserver(() => mutations.push({width:image.style.width,height:image.style.height}));
        observer.observe(image, {attributes:true,attributeFilter:['style']});
        for (let frame = 0; frame < 20; frame++) {
            d._previewStage.dispatchEvent(new WheelEvent('wheel', {deltaY:-25,bubbles:true,cancelable:true,clientX:640,clientY:400}));
            await new Promise(resolve => requestAnimationFrame(resolve));
        }
        observer.disconnect();
        return {startWidth,startHeight,mutations,transform:image.style.transform,willChange:image.style.willChange};
    }""")
    assert all(value["width"] == result["startWidth"] and value["height"] == result["startHeight"] for value in result["mutations"])
    assert result["willChange"] == "transform"
    assert "scale(" in result["transform"]
    settled(page)
    assert page.locator(".attachment-image-viewer-canvas img").evaluate("image => image.style.transform") == "none"
    assert page.locator(".attachment-image-viewer-canvas img").evaluate("image => image.style.width") != result["startWidth"]


@pytest.mark.parametrize("preview_page", [1, 2], indirect=True)
def test_native_size_preserves_single_pixel_detail_after_wheel_zoom(preview_page):
    page = preview_page
    stage = page.locator(".attachment-image-viewer-canvas").bounding_box()
    page.mouse.move(stage["x"] + stage["width"] / 2, stage["y"] + stage["height"] / 2)
    for _ in range(5):
        page.mouse.wheel(0, -180)
    settled(page)
    page.get_by_role("button", name="原始尺寸", exact=True).click()
    settled(page)
    assert page.locator(".attachment-image-viewer-zoom").inner_text() == "100%"
    assert page.locator(".attachment-image-viewer-canvas img").bounding_box()["width"] == pytest.approx(4800)
    # At DPR 2, 100% CSS size interpolates each source pixel across two screen pixels.
    # Inspect at one source pixel per physical screen pixel to test lost detail unambiguously.
    pixel_ratio = page.evaluate("devicePixelRatio")
    page.mouse.move(stage["x"] + stage["width"] / 2, stage["y"] + stage["height"] / 2)
    if pixel_ratio != 1:
        page.mouse.wheel(0, pixel_ratio * math.log(pixel_ratio) / 0.0016)
        settled(page)
    assert page.locator(".attachment-image-viewer-canvas img").bounding_box()["width"] == pytest.approx(4800 / pixel_ratio)
    crop = page.screenshot(clip={"x": 560, "y": 350, "width": 160, "height": 80}, animations="disabled")
    pixels = Image.open(io.BytesIO(crop)).convert("RGB")
    values = [pixels.getpixel((x, pixels.height // 2))[0] for x in range(pixels.width)]
    assert sum(value < 10 or value > 245 for value in values) / len(values) > 0.95, "Original pixel detail was blurred during zoom"
    assert min(values) < 10 and max(values) > 245


def test_pointer_anchor_pan_fit_and_reopen(preview_page):
    page = preview_page
    box = page.locator(".attachment-image-viewer-canvas").bounding_box()
    x, y = box["x"] + box["width"] * 0.65, box["y"] + box["height"] / 2
    fitted = page.locator(".attachment-image-viewer-canvas img").bounding_box()
    page.mouse.move(x, y)
    page.mouse.wheel(0, -900)
    settled(page)
    assert page.evaluate("durableAttachmentPreviewDialog._previewOffsetX") < 0
    before = page.locator(".attachment-image-viewer-canvas img").bounding_box()
    assert (x - before["x"]) / before["width"] == pytest.approx((x - fitted["x"]) / fitted["width"], abs=0.001)
    page.mouse.down()
    page.mouse.move(x + 80, y + 40, steps=4)
    page.mouse.up()
    settled(page)
    after = page.locator(".attachment-image-viewer-canvas img").bounding_box()
    assert after["x"] - before["x"] == pytest.approx(80, abs=1)
    assert after["y"] - before["y"] == pytest.approx(40, abs=1)
    page.get_by_role("button", name="适应窗口", exact=True).click()
    settled(page)
    image = page.locator(".attachment-image-viewer-canvas img").bounding_box()
    assert image["width"] <= box["width"]
    assert image["height"] <= box["height"]
    assert page.evaluate("durableAttachmentPreviewDialog._previewOffsetX") == 0
    page.keyboard.press("Escape")
    page.locator("#thumbnail").click()
    page.wait_for_function("!!durableAttachmentPreviewDialog._previewFitSize")
    assert page.evaluate("durableAttachmentPreviewDialog._previewScale") == 1


def test_small_window_controls_and_load_error(preview_page):
    page = preview_page
    page.set_viewport_size({"width": 390, "height": 700})
    settled(page)
    for label in ("缩小图片", "放大图片", "原始尺寸", "适应窗口", "关闭图片预览"):
        button = page.get_by_role("button", name=label, exact=True)
        assert button.is_visible()
        box = button.bounding_box()
        assert 0 <= box["x"] < box["x"] + box["width"] <= 390
    page.evaluate("openChatImagePreview({src:'http://image-preview.test/broken.png',alt:'broken'})")
    page.get_by_role("status").filter(has_text="图片加载失败").wait_for()
    assert page.get_by_role("button", name="原始尺寸", exact=True).is_disabled()
