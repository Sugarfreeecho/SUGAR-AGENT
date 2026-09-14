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
    return prefix + _access(ref, path, language)


def file_handle_text(ref, path, language="en"):
    identity = f'{_identity(ref)} ({ref["bytes"]} bytes)'
    return (f'[File {identity}: verbatim read-only copy at {json.dumps(str(path))}. Read with file tools when needed; copy before editing.]'
            if language == "en" else f'[文件 {identity}：只读原样副本 {json.dumps(str(path), ensure_ascii=False)}。需要内容时请使用文件工具读取，编辑前先复制。]')
