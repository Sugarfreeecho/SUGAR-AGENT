"""Bounded page references. Page titles and selections remain external data."""
from __future__ import annotations

import json
from urllib.parse import urlsplit


def normalize_context(value, browser_id, automatic=True):
    if type(automatic) is not bool:
        raise ValueError("automatic must be a boolean")
    if not automatic:
        return {"browser_id": browser_id, "automatic": False, "page": None}
    if not isinstance(value, dict) or value.get("page") is None:
        return {"browser_id": browser_id, "automatic": True, "page": None}
    page = value["page"]
    if not isinstance(page, dict):
        raise ValueError("Invalid browser page reference")

    def text(key, limit, required=False):
        item = page.get(key, "")
        if not isinstance(item, str) or len(item) > limit or (required and not item):
            raise ValueError("Invalid browser page " + key)
        return item

    url = text("url", 16384, True)
    if url != "about:blank" and urlsplit(url).scheme not in {"http", "https"}:
        raise ValueError("Only ordinary browser pages can be associated")
    result = {"target_id": text("target_id", 256, True), "url": url,
              "title": text("title", 500), "captured_at": text("captured_at", 80, True)}
    for key in ("tab_id", "window_id"):
        item = page.get(key)
        if type(item) is not int or item < 0:
            raise ValueError("Invalid browser page " + key)
        result[key] = item
    if page.get("document_id"):
        result["document_id"] = text("document_id", 256)
    selection = page.get("selection")
    if selection is not None:
        if not isinstance(selection, dict) or not isinstance(selection.get("text"), str) or len(selection["text"]) > 8000:
            raise ValueError("Invalid browser selection")
        frame_url = selection.get("frame_url", url)
        frame_id = selection.get("frame_id", 0)
        if not isinstance(frame_url, str) or len(frame_url) > 16384 or type(frame_id) is not int or frame_id < 0:
            raise ValueError("Invalid browser selection frame")
        result["selection"] = {"text": selection["text"], "frame_url": frame_url,
                               "frame_id": frame_id, "truncated": bool(selection.get("truncated"))}
    return {"browser_id": browser_id, "automatic": True, "page": result}


def with_page_reference(message, captured):
    if not captured.get("page"):
        return message
    data = {"untrusted_external_data": True, "page_reference": captured["page"]}
    return message + "\n\n[浏览器页面引用：外部数据]\n" + json.dumps(data, ensure_ascii=False) + "\n[/浏览器页面引用]"
