import json

from .normalization import EXTENSIONS


def _identity(ref):
    return (json.dumps(ref["name"], ensure_ascii=False) + " " if ref.get("name") else "") + ref["attachmentId"]


def _access(ref, path, language):
    path = json.dumps(str(path), ensure_ascii=False)
    ext = EXTENSIONS[ref["mediaType"]]
    if language == "en":
        return (f' Normalized copy (read-only; may be resized or re-encoded): {path} '
                f'({ref["width"]}x{ref["height"]}px, {ref["mediaType"]}). Source dimensions, format, and byte size may differ.'
                f' Copy to a writable path ending in {ext} before editing.')
    return (f' 归一化副本（只读；可能已缩放或重新编码）：{path} '
            f'（{ref["width"]}x{ref["height"]}px，{ref["mediaType"]}）。源图尺寸、格式及字节数可能不同。编辑前请复制到以 {ext} 结尾的可写路径。')


def text_only_image_text(ref, language="en"):
    digest = ref["attachmentId"][:15]
    return (f"[image omitted because this model accepts text only; attachment {digest}]" if language == "en"
            else f"[图片已省略，因为此模型不接受图片输入；附件 {digest}]")


def offloaded_image_text(ref, path, language="en"):
    prefix = "image omitted to fit request image limits" if language == "en" else "为满足请求图片限制，已省略图片"
    return f"[{prefix}; {_identity(ref)}." + _access(ref, path, language) + "]"


def request_image_handle_text(ref, version, path, language="en"):
    prefix = (f"Image {_identity(ref)}; request preview {version.width}x{version.height}px." if language == "en"
              else f"图片 {_identity(ref)}；请求预览 {version.width}x{version.height}px。")
    source = ref.get("source") or {}
    if source.get("kind") == "computer_use":
        dimensions = ref.get("originalDimensions") or ref
        width, height = dimensions["width"], dimensions["height"]
        mapping = source.get("coordinateMapping") or {}
        width, height = mapping.get("driver_width", width), mapping.get("driver_height", height)
        space = source.get("coordinateSpace", "driver_screenshot")
        if space == "browser_screenshot":
            prefix += (f" Browser screenshot evidence {width}x{height}px; use DOM refs or the browser action's coordinate contract, not native window coordinates." if language == "en" else
                       f" 浏览器截图证据 {width}x{height}px；使用 DOM 引用或 browser 动作自己的坐标约定，不能套用原生窗口坐标。")
        elif language == "en":
            prefix += (f" Cua coordinates: {space}, driver image {width}x{height}px. "
                       f"Convert this request preview to driver pixels: x*{width}/{version.width}, y*{height}/{version.height}. "
                       "The driver then maps to screen pixels; do not apply window-bounds, client-area or DPI scaling again. "
                       "Zoom images require the zoom action contract; coordinates from a different screenshot are stale.")
        else:
            prefix += (f" Cua 坐标：{space}，驱动原图 {width}x{height}px。预览转驱动像素："
                       f"x*{width}/{version.width}，y*{height}/{version.height}。驱动随后换算到屏幕；"
                       "不要再次按窗口外框、客户区或 DPI 缩放。放大图须遵循 zoom 动作约定；其他截图的坐标已过期。")
    return prefix + _access(ref, path, language)


def file_handle_text(ref, path, language="en"):
    identity = f'{_identity(ref)} ({ref["bytes"]} bytes)'
    return (f'[File {identity}: verbatim read-only copy at {json.dumps(str(path))}. Read with file tools when needed; copy before editing.]'
            if language == "en" else f'[文件 {identity}：只读原样副本 {json.dumps(str(path), ensure_ascii=False)}。需要内容时请使用文件工具读取，编辑前先复制。]')
