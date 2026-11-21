"""The details column's PDF / Word / PowerPoint / Excel previews."""
import base64
from urllib.parse import parse_qs, urlsplit

import pytest

from tests.test_details_pages_browser import details_page  # noqa: F401
from tests.test_llm_stream_full_text_browser import browser_page  # noqa: F401

PNG_1PX = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
)

DECK = {
    'ok': True,
    'kind': 'pptx',
    'notes': [],
    'deck': {
        'width': 960,
        'height': 540,
        'notes': [],
        'slides': [
            {'background': '#ffffff', 'html':
             '<div class="dp-shape" style="left:10px;top:10px;width:400px;height:60px">'
             '<p class="dp-para"><span style="font-size:32px">年度汇报</span></p></div>'},
            {'background': '#123456', 'html':
             '<div class="dp-shape" style="left:10px;top:10px;width:400px;height:60px">'
             '<p class="dp-para"><span style="font-size:32px">第二页</span></p></div>'},
        ],
    },
}

WORKBOOK = {
    'ok': True,
    'kind': 'xlsx',
    'notes': ['rows-truncated'],
    'workbook': {
        'active': '汇总',
        'notes': ['rows-truncated'],
        'sheets': [
            {'name': '汇总', 'hidden': False, 'truncated': False,
             'html': '<div class="dp-sheet-wrap"><table class="dp-sheet"><tbody>'
                     '<tr><td>项目</td><td>金额</td></tr></tbody></table></div>'},
            {'name': '明细', 'hidden': False, 'truncated': False,
             'html': '<div class="dp-sheet-wrap"><table class="dp-sheet"><tbody>'
                     '<tr><td>明细值</td><td>42</td></tr></tbody></table></div>'},
        ],
    },
}

DOCUMENT = {
    'ok': True,
    'kind': 'docx',
    'notes': ['media-skipped'],
    'document': {
        'html': '<h1>季度报告</h1><p>正文段落</p>'
                '<p><img class="dp-image" data-doc-part="word/media/image1.png" alt=""></p>',
        'notes': ['media-skipped'],
    },
}

CSV = {
    'ok': True,
    'kind': 'csv',
    'name': 'report.csv',
    'notes': ['columns-truncated'],
    'table': {
        'html': '<div class="dp-sheet-wrap"><table class="dp-sheet dp-csv"><tbody>'
                '<tr class="dp-csv-head"><td>名称</td><td>金额</td></tr>'
                '<tr><td>报表</td><td>3</td></tr></tbody></table></div>',
        'rows': 2,
        'cols': 2,
        'delimiter': ',',
        'encoding': 'utf-8',
        'truncated': True,
    },
}


@pytest.fixture
def office_page(details_page):
    page, calls, errors, rows = details_page
    seen = []

    def preview(route):
        rel = parse_qs(urlsplit(route.request.url).query).get('rel', [''])[0]
        seen.append(rel)
        name = rel.replace('\\', '/').rsplit('/', 1)[-1]
        payload = {
            'deck.pptx': DECK,
            'book.xlsx': WORKBOOK,
            'report.docx': DOCUMENT,
            'report.csv': CSV,
        }.get(name)
        if payload is None:
            route.fulfill(status=404, json={'ok': False, 'error': 'file not found'})
            return
        route.fulfill(status=200, json=payload)

    def media(route):
        seen.append(route.request.url)
        route.fulfill(status=200, content_type='image/png', body=PNG_1PX)

    def source(route):
        route.fulfill(status=200, json={
            'ok': True, 'text': '名称,金额\n报表,3\n', 'truncated': False, 'size': 24})

    page.route('**/api/workspace-doc-preview**', preview)
    page.route('**/api/workspace-doc-media**', media)
    page.route('**/api/workspace-file-text**', source)
    yield page, seen, errors
    page.unroute('**/api/workspace-doc-preview**', preview)
    page.unroute('**/api/workspace-doc-media**', media)
    page.unroute('**/api/workspace-file-text**', source)


def test_deck_renders_slides_with_navigation(office_page):
    page, seen, errors = office_page
    page.evaluate("MyAgentDock.openDetailsFile('deck.pptx')")
    page.wait_for_selector('.dock-deck')
    assert '年度汇报' in page.locator('.dock-deck-slide').inner_text()
    assert page.locator('.dock-deck-select option').count() == 2
    assert page.locator('.dock-deck-counter').inner_text() == '1 / 2'
    assert seen and seen[0].replace('\\', '/').endswith('/deck.pptx')
    page.locator('button[aria-label="下一页"]').click()
    page.wait_for_function("document.querySelector('.dock-deck-counter').textContent === '2 / 2'")
    assert '第二页' in page.locator('.dock-deck-slide').inner_text()
    assert page.evaluate("document.querySelector('.dock-deck-slide').style.background") == 'rgb(18, 52, 86)'
    # The logical canvas is scaled down to the column width, never below it.
    assert page.evaluate("document.querySelector('.dock-deck-stage').style.transform").startswith('scale(')
    assert not errors, [str(error) for error in errors]


def test_workbook_tabs_switch_sheets_and_show_limits(office_page):
    page, _seen, errors = office_page
    page.evaluate("MyAgentDock.openDetailsFile('book.xlsx')")
    page.wait_for_selector('.dock-workbook')
    assert page.locator('.dock-sheet-tab').count() == 2
    assert '项目' in page.locator('.dock-sheet-body').inner_text()
    assert '表格较大' in page.locator('.dock-preview-foot').inner_text()
    page.locator('.dock-sheet-tab').nth(1).click()
    page.wait_for_function("document.querySelector('.dock-sheet-body').textContent.includes('明细值')")
    assert 'is-active' in (page.locator('.dock-sheet-tab').nth(1).get_attribute('class') or '')
    assert not errors, [str(error) for error in errors]


def test_word_preview_hydrates_images_and_notes(office_page):
    page, _seen, errors = office_page
    assert page.evaluate("MyAgentDock.isPreviewPath('report.docx')") is True
    # The shared open policy routes previewable documents into the column.
    page.evaluate("MyAgentDock.openPathSmart('report.docx')")
    page.wait_for_selector('.dock-doc-richtext')
    assert page.locator('.dock-doc-richtext h1').inner_text() == '季度报告'
    page.wait_for_function(
        "() => { const img=document.querySelector('.dock-doc-richtext img');"
        " return !!img && img.src.indexOf('workspace-doc-media') >= 0; }")
    source = page.locator('.dock-doc-richtext img').get_attribute('src')
    assert 'word%2Fmedia%2Fimage1.png' in source or 'word/media/image1.png' in source
    assert '部分图片过大' in page.locator('.dock-preview-foot').inner_text()
    assert not errors, [str(error) for error in errors]


def test_pdf_uses_the_browser_viewer(office_page):
    page, _seen, errors = office_page
    page.evaluate("MyAgentDock.openDetailsFile('report.pdf')")
    page.wait_for_selector('iframe.dock-doc-pdf')
    source = page.locator('iframe.dock-doc-pdf').get_attribute('src')
    assert 'workspace-assets' in source and 'report.pdf' in source
    assert not errors, [str(error) for error in errors]


def test_csv_switches_between_table_and_source(office_page):
    page, _seen, errors = office_page
    page.evaluate("MyAgentDock.openPathSmart('report.csv')")
    page.wait_for_selector('.dock-csv')
    assert page.locator('.dock-csv-meta').inner_text().startswith('CSV')
    assert '报表' in page.locator('.dock-csv-body').inner_text()
    assert '表格列过多' in page.locator('.dock-preview-foot').inner_text()
    page.locator('[data-dock-csv-toggle]').click()
    page.wait_for_selector('.dock-csv-source')
    assert '名称,金额' in page.locator('.dock-csv-source').text_content()
    page.locator('[data-dock-csv-toggle]').click()
    page.wait_for_function(
        "() => document.querySelector('.dock-csv-body').textContent.includes('报表')")
    assert not errors, [str(error) for error in errors]
