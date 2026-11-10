"""PageUp in the composer must not scroll the app shell sideways.

The collapsed details column parks its 460px surface just past the viewport
edge.  While the shell only clipped overflow (`overflow: hidden`) it stayed a
scroll container, so a PageUp with focus in the composer (a textarea with no
scroll range of its own) was taken by the shell and dragged the whole layout
left -- the session list ended up outside the operable area.  The shell must
clip without offering a scroll range.
"""
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from tests.test_llm_stream_full_text_browser import browser_page

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def shell_page(browser_page):
    page = browser_page
    styles = (ROOT / "frontend/src/styles/app.css").read_text(encoding="utf-8")
    dock_styles = (ROOT / "frontend/src/styles/dock.css").read_text(encoding="utf-8")
    page.set_content(
        f"<!doctype html><style>{styles}</style><style>{dock_styles}</style>"
        '<div class="app">'
        '<aside class="sidebar" id="sidebar"></aside>'
        '<section class="main"><div class="main-center"><div class="workbench">'
        '<div class="chat-stage"><div id="chat-container" class="chat-container"></div></div>'
        "</div>"
        '<div class="panel"><div class="panel-inner"><div class="composer-row">'
        '<div class="input-wrapper"><textarea id="message-input" rows="1"></textarea></div>'
        "</div></div></div>"
        "</div></section>"
        '<div class="dock-rightbar is-collapsed"><div class="dock-surface"></div></div>'
        "</div>"
    )
    return page


def shell_geometry(page):
    return page.evaluate("""() => {
      const app = document.querySelector('.app');
      const sidebar = document.getElementById('sidebar').getBoundingClientRect();
      const input = document.getElementById('message-input').getBoundingClientRect();
      return {scrollLeft: app.scrollLeft, scrollWidth: app.scrollWidth,
              clientWidth: app.clientWidth, sidebarX: sidebar.x, inputX: input.x};
    }""")


def test_pageup_in_composer_keeps_the_shell_in_place(shell_page):
    page = shell_page
    page.locator("#message-input").fill("hello")
    before = shell_geometry(page)
    assert before["scrollWidth"] > before["clientWidth"], "collapsed dock should overhang the shell"

    page.keyboard.press("PageUp")
    page.wait_for_timeout(120)
    after = shell_geometry(page)

    assert after["scrollLeft"] == 0
    assert after["sidebarX"] == before["sidebarX"] == 0
    assert after["inputX"] == pytest.approx(before["inputX"])
