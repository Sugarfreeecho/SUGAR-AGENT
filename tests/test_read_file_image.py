# -*- coding: utf-8 -*-
"""read_file 透明读图：图片文件返回 [文本信封, image 块]；文本路径行为不变。

覆盖：PNG 结构化结果与引用读回、行范围参数忽略、BMP 自动转换、超限可恢复错误、
伪扩展名改名提示、内容寻址去重、缩放坐标提示、工具结果视图管线保留 image 块。
"""
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import agent_tools  # noqa: E402
from attachments import get_attachment_store, invalidate_attachment_env_cache  # noqa: E402


def _image_bytes(fmt="PNG", size=(40, 30), mode="RGB", color=(12, 34, 56)) -> bytes:
    out = BytesIO()
    Image.new(mode, size, color).save(out, format=fmt)
    return out.getvalue()


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("WORK_DIR", str(tmp_path))
    invalidate_attachment_env_cache()
    yield get_attachment_store()
    invalidate_attachment_env_cache()


def test_read_file_returns_image_blocks_for_png(store, tmp_path):
    path = tmp_path / "shot.png"
    path.write_bytes(_image_bytes())
    result = agent_tools.read_file(path=str(path))
    assert isinstance(result, list) and len(result) == 2
    text_block, image_block = result
    assert text_block["type"] == "text"
    assert "<type>image</type>" in text_block["text"]
    assert str(path.resolve()) in text_block["text"]
    assert image_block["type"] == "image"
    ref = image_block["attachment"]
    assert ref["attachmentId"].startswith("sha256:")
    assert ref["width"] == 40 and ref["height"] == 30
    assert ref["mediaType"] == "image/jpeg"  # RGB 归一化为 JPEG
    stored = store.read_image_sync(ref)
    assert len(stored.data) == ref["bytes"]


def test_read_file_still_reads_text(store, tmp_path):
    path = tmp_path / "note.txt"
    path.write_text("hello\nworld\n", encoding="utf-8")
    result = agent_tools.read_file(path=str(path))
    assert isinstance(result, str)
    assert "hello" in result and "world" in result


def test_image_ignores_line_range_parameters(store, tmp_path):
    path = tmp_path / "shot.png"
    path.write_bytes(_image_bytes())
    result = agent_tools.read_file(path=str(path), start_line=5, line_count=3)
    assert isinstance(result, list)
    assert result[1]["type"] == "image"


def test_bmp_is_converted_and_viewable(store, tmp_path):
    path = tmp_path / "legacy.bmp"
    path.write_bytes(_image_bytes(fmt="BMP"))
    result = agent_tools.read_file(path=str(path))
    assert isinstance(result, list)
    ref = result[1]["attachment"]
    assert ref["mediaType"] == "image/jpeg"
    store.read_image_sync(ref)  # 归一化对象可读回


def test_oversized_image_returns_recoverable_error(store, tmp_path):
    path = tmp_path / "huge.png"
    path.write_bytes(_image_bytes(size=(8193, 1)))
    result = agent_tools.read_file(path=str(path))
    assert isinstance(result, str)
    assert "too large" in result
    assert not [p for p in store.root.rglob("*") if p.is_file()]


def test_image_bytes_with_non_image_extension_guides_rename(store, tmp_path):
    path = tmp_path / "shot.txt"
    path.write_bytes(_image_bytes())
    result = agent_tools.read_file(path=str(path))
    assert isinstance(result, str)
    assert "PNG" in result and "rename" in result


def test_same_image_dedupes_to_one_attachment(store, tmp_path):
    path = tmp_path / "shot.png"
    path.write_bytes(_image_bytes())
    first = agent_tools.read_file(path=str(path))
    second = agent_tools.read_file(path=str(path))
    assert first[1]["attachment"]["attachmentId"] == second[1]["attachment"]["attachmentId"]
    assert len(list(store.root.rglob("image.jpg"))) == 1


def test_downscaled_image_reports_original_dimensions(store, tmp_path):
    path = tmp_path / "big.png"
    path.write_bytes(_image_bytes(size=(2400, 2000)))
    result = agent_tools.read_file(path=str(path))
    ref = result[1]["attachment"]
    assert ref.get("originalDimensions") == {"width": 2400, "height": 2000}
    assert "downscaled from 2400x2000" in result[0]["text"]


def test_tool_result_views_preserve_image_blocks(store, tmp_path):
    import agent_loop

    path = tmp_path / "shot.png"
    path.write_bytes(_image_bytes())
    result = agent_tools.read_file(path=str(path))
    log_view, llm_view, ui_view = agent_loop._tool_result_details_for_views(
        result, "read_file", {}
    )
    assert isinstance(log_view, str)
    assert isinstance(llm_view, list)
    assert any(isinstance(b, dict) and b.get("type") == "image" for b in llm_view)
    assert isinstance(ui_view, list)
    assert any(isinstance(b, dict) and b.get("type") == "image" for b in ui_view)
