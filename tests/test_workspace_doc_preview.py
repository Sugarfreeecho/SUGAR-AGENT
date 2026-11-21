"""Inline office previews for the details column.

The builders are tested against real OOXML packages produced by python-docx,
openpyxl and python-pptx, so namespace handling and inheritance rules are
exercised rather than mocked. The HTTP routes are covered for path gating and
response shape; the column's rendering is covered by the browser test.
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from pptx import Presentation
from pptx.util import Inches as PInches
from pptx.util import Pt as PPt

APP = str(Path(__file__).resolve().parents[1] / "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

import workspace_doc_preview as preview


@pytest.fixture(autouse=True)
def clear_cache():
    preview.clear_preview_cache()
    yield
    preview.clear_preview_cache()


@pytest.fixture
def image_path(tmp_path):
    path = tmp_path / "pixel.png"
    Image.new("RGB", (40, 24), (30, 120, 220)).save(path)
    return path


def _docx(tmp_path, image_path):
    doc = Document()
    doc.add_heading("季度报告", level=1)
    paragraph = doc.add_paragraph()
    bold = paragraph.add_run("加粗")
    bold.bold = True
    coloured = paragraph.add_run(" 彩色")
    coloured.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
    coloured.font.size = Pt(14)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("第一项", style="List Bullet")
    doc.add_paragraph("第二步", style="List Number")
    table = doc.add_table(rows=2, cols=3)
    table.cell(0, 0).text = "合并表头"
    table.cell(0, 0).merge(table.cell(0, 2))
    table.cell(1, 0).text = "A"
    table.cell(1, 1).text = "B"
    table.cell(1, 2).text = "C"
    doc.add_picture(str(image_path), width=Inches(2))
    doc.add_paragraph("<script>alert(1)</script>")
    path = tmp_path / "report.docx"
    doc.save(path)
    return path


def test_docx_preview_keeps_structure_and_escapes_text(tmp_path, image_path):
    path = _docx(tmp_path, image_path)
    assert preview.preview_kind(path) == "docx"
    payload = preview.build_preview(path)
    html = payload["document"]["html"]
    assert payload["kind"] == "docx" and payload["ok"] is True
    assert "<h1>季度报告</h1>" in html
    assert "<ul><li>第一项</li></ul>" in html
    assert "<ol><li>第二步</li></ol>" in html
    assert 'colspan="3"' in html and 'class="dp-table"' in html
    assert 'color:#C00000' in html and "text-align:center" in html
    assert 'data-doc-part="word/media/image1.png"' in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>" not in html


def test_docx_media_parts_are_served_one_at_a_time(tmp_path, image_path):
    path = _docx(tmp_path, image_path)
    data, media_type = preview.read_preview_media(path, "word/media/image1.png")
    assert data.startswith(b"\x89PNG") and media_type == "image/png"
    for part in ("word/document.xml", "../word/media/image1.png", "/word/media/image1.png"):
        with pytest.raises(preview.PreviewError):
            preview.read_preview_media(path, part)


def test_xlsx_preview_returns_sheets_styles_and_merged_cells(tmp_path):
    workbook = Workbook()
    summary = workbook.active
    summary.title = "汇总"
    summary["A1"] = "项目"
    summary["B1"] = "金额"
    summary["A1"].font = Font(bold=True)
    summary["A1"].fill = PatternFill("solid", fgColor="FFF2CC")
    summary.merge_cells("A1:B1")
    summary["A2"] = "日期"
    summary["B2"] = datetime(2026, 11, 18)
    summary["B2"].number_format = "yyyy-mm-dd"
    summary["A3"] = "占比"
    summary["B3"] = 0.256
    summary["B3"].number_format = "0.00%"
    summary["A4"] = "长文本"
    summary["B4"] = "第一行\n第二行"
    summary["B4"].alignment = Alignment(wrap_text=True)
    summary.freeze_panes = "A2"
    workbook.create_sheet("明细")["A1"] = 1
    path = tmp_path / "book.xlsx"
    workbook.save(path)

    payload = preview.build_preview(path)
    sheets = payload["workbook"]["sheets"]
    assert [sheet["name"] for sheet in sheets] == ["汇总", "明细"]
    assert payload["workbook"]["active"] == "汇总"
    first = sheets[0]
    assert first["freezeRow"] == 1 and first["freezeCol"] == 0
    html = first["html"]
    assert 'colspan="2"' in html
    assert "background:#FFF2CC" in html and "font-weight:600" in html
    assert "2026-11-18" in html and "25.6%" in html
    assert "第一行<br>第二行" in html
    assert 'class="dp-frozen-row"' in html


def test_csv_preview_handles_quotes_encodings_and_limits(tmp_path, monkeypatch):
    quoted = tmp_path / "quoted.csv"
    quoted.write_text(
        '名称,金额,备注\n"含,逗号",12,"第一行\n第二行"\n普通,3.5,\n',
        encoding="utf-8", newline="")
    payload = preview.build_preview(quoted)
    assert payload["kind"] == "csv"
    table = payload["table"]
    assert table["rows"] == 3 and table["cols"] == 3
    assert table["delimiter"] == "," and table["encoding"] == "utf-8"
    assert "含,逗号" in table["html"] and "第一行<br>第二行" in table["html"]
    assert 'class="dp-csv-head"' in table["html"]

    gbk = tmp_path / "gbk.csv"
    gbk.write_bytes("名称,金额\n报表,3\n".encode("gbk"))
    gbk_payload = preview.build_preview(gbk)
    assert gbk_payload["table"]["encoding"] == "gb18030"
    assert "报表" in gbk_payload["table"]["html"]

    semicolon = tmp_path / "semi.csv"
    semicolon.write_text("a;b;c\n1;2;3\n", encoding="utf-8")
    assert preview.build_preview(semicolon)["table"]["delimiter"] == ";"

    tsv = tmp_path / "data.tsv"
    tsv.write_text("a\tb\n1\t2\n", encoding="utf-8")
    tsv_payload = preview.build_preview(tsv)
    assert tsv_payload["kind"] == "csv" and tsv_payload["table"]["cols"] == 2

    monkeypatch.setattr(preview, "MAX_CSV_ROWS", 2)
    preview.clear_preview_cache()
    capped = preview.build_preview(quoted)
    assert capped["table"]["rows"] == 2 and "rows-truncated" in capped["notes"]

    monkeypatch.setattr(preview, "MAX_CSV_ROWS", 500)
    monkeypatch.setattr(preview, "MAX_CSV_COLUMNS", 2)
    preview.clear_preview_cache()
    wide = preview.build_preview(quoted)
    assert wide["table"]["cols"] == 2 and "columns-truncated" in wide["notes"]


def test_pptx_preview_inherits_placeholder_geometry_and_builds_sliders(tmp_path, image_path):
    deck = Presentation()
    title_slide = deck.slides.add_slide(deck.slide_layouts[0])
    title_slide.shapes.title.text = "年度汇报"
    title_slide.placeholders[1].text = "副标题"
    content = deck.slides.add_slide(deck.slide_layouts[1])
    content.shapes.title.text = "要点"
    content.placeholders[1].text = "第一条\n第二条"
    content.shapes.add_picture(str(image_path), PInches(1), PInches(4), width=PInches(1.2))
    table = content.shapes.add_table(2, 2, PInches(4), PInches(4), PInches(3), PInches(1))
    table.table.cell(0, 0).text = "表头"
    table.table.cell(0, 1).text = "数值"
    path = tmp_path / "deck.pptx"
    deck.save(path)

    payload = preview.build_preview(path)
    slides = payload["deck"]["slides"]
    assert payload["deck"]["width"] == 960 and payload["deck"]["height"] == 720
    assert len(slides) == 2
    first = slides[0]["html"]
    # Title placeholders carry no xfrm in the slide; 44pt and centring come
    # from the master's txStyles.
    assert "text-align:center" in first
    assert "font-size:58.7px" in first
    assert "年度汇报" in first
    second = slides[1]["html"]
    # The title-and-content layout inherits its box from the master placeholder.
    assert "left:48.0px" in second and "top:28.8px" in second
    assert "justify-content:center" in second
    assert 'data-doc-part="ppt/media/image1.png"' in second
    assert "dp-table" in second and "表头" in second
    assert 'class="dp-bullet"' in second


def test_preview_rejects_unsupported_and_broken_documents(tmp_path, monkeypatch):
    text = tmp_path / "note.txt"
    text.write_text("plain", encoding="utf-8")
    with pytest.raises(preview.PreviewError) as unsupported:
        preview.build_preview(text)
    assert unsupported.value.status_code == 415

    broken = tmp_path / "broken.docx"
    broken.write_bytes(b"not a zip")
    with pytest.raises(preview.PreviewError) as invalid:
        preview.build_preview(broken)
    assert invalid.value.status_code == 422

    path = _docx(tmp_path, _image(tmp_path))
    monkeypatch.setattr(preview, "MAX_DOCUMENT_BYTES", 10)
    with pytest.raises(preview.PreviewError) as too_large:
        preview.build_preview(path)
    assert too_large.value.status_code == 413


def _image(tmp_path):
    path = tmp_path / "tiny.png"
    Image.new("RGB", (8, 8), (0, 0, 0)).save(path)
    return path


def test_preview_cache_tracks_the_file_mtime(tmp_path, image_path):
    path = _docx(tmp_path, image_path)
    first = preview.build_preview(path)
    assert first is preview.build_preview(path)
    doc = Document()
    doc.add_paragraph("changed")
    doc.save(path)
    second = preview.build_preview(path)
    assert second is not first
    assert "changed" in second["document"]["html"]


def test_routes_gate_paths_and_return_the_payload(tmp_path, image_path):
    webui = pytest.importorskip("webui")
    path = _docx(tmp_path, image_path)

    response = asyncio.run(webui.workspace_doc_preview(rel=path.name, work_dir=str(tmp_path)))
    assert response.status_code == 200
    payload = json.loads(response.body)
    assert payload["kind"] == "docx" and payload["document"]["html"]

    unsupported = asyncio.run(webui.workspace_doc_preview(rel="pixel.png", work_dir=str(tmp_path)))
    assert unsupported.status_code == 415

    media = asyncio.run(webui.workspace_doc_media(
        rel=path.name, part="word/media/image1.png", work_dir=str(tmp_path)))
    assert media.status_code == 200 and media.body.startswith(b"\x89PNG")

    bad_part = asyncio.run(webui.workspace_doc_media(
        rel=path.name, part="word/document.xml", work_dir=str(tmp_path)))
    assert bad_part.status_code == 400

    missing = asyncio.run(webui.workspace_doc_preview(rel="missing.docx", work_dir=str(tmp_path)))
    assert missing.status_code == 404
