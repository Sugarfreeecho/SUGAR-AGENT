"""Exercise pointer ownership and geometry with real Dock and iframe content."""
import pytest

from tests.test_details_pages_browser import details_page, plugin_frame
from tests.test_llm_stream_full_text_browser import browser_page

pytestmark = pytest.mark.parametrize('details_page', ['resizing'], indirect=True)


def open_details(details_page, plugin=False):
    page, _calls, _errors, _rows = details_page
    page.evaluate("MyAgentDock.openPluginPage('demo')" if plugin else "MyAgentDock.openDetailsTab('guide')")
    if plugin:
        plugin_frame(page)
    page.wait_for_timeout(350)
    return page


def geometry(page):
    return page.evaluate("""() => {
      const h=dockRightState.host.getBoundingClientRect();
      const s=dockRightState.surface.el.getBoundingClientRect();
      const r=dockRightState.sash.getBoundingClientRect();
      return {width:dockRightState.width, host:h.width, surface:s.width,
        edge:r.x+r.width/2, left:s.left, main:document.querySelector('.main').getBoundingClientRect().width,
        dragging:dockRightState.dragging, mode:MyAgentDock.detailsState().mode,
        expanded:MyAgentDock.detailsState().expanded};
    }""")


def test_drag_tracks_pointer_and_regrab_does_not_jump(details_page):
    page = open_details(details_page)
    x = geometry(page)['edge']
    page.mouse.move(x, 300)
    page.mouse.down()
    page.mouse.move(x-160, 300)
    moved = geometry(page)
    assert moved['width'] == moved['host'] == moved['surface'] == 620
    assert moved['edge'] == moved['left'] == x-160
    page.mouse.up()
    page.mouse.down()
    page.mouse.move(x-161, 300)
    assert geometry(page)['width'] == 621
    page.mouse.up()
    assert page.evaluate("localStorage.getItem(DOCK_RIGHT_WIDTH_KEY)") == '621'


def test_iframe_release_ends_drag_and_persists_attachment_page(details_page):
    page = open_details(details_page, plugin=True)
    frame = plugin_frame(page)
    identity = frame.evaluate('window.instance')
    x = geometry(page)['edge']
    page.mouse.move(x, 300)
    page.mouse.down()
    page.mouse.move(x+130, 300)
    assert geometry(page)['width'] == 330
    page.mouse.up()
    page.mouse.move(x-80, 300)
    assert geometry(page)['width'] == 330
    assert not geometry(page)['dragging']
    assert frame.evaluate('window.instance') == identity
    assert page.evaluate("localStorage.getItem(DOCK_RIGHT_WIDTH_KEY)") == '330'


@pytest.mark.parametrize('end', ['pointercancel', 'lostpointercapture', 'blur', 'collapse'])
def test_interrupted_gesture_stops_and_ignores_other_pointer(details_page, end):
    page = open_details(details_page)
    x = geometry(page)['edge']
    page.mouse.move(x, 300)
    page.mouse.down()
    page.mouse.move(x-1, 300)
    page.evaluate("window.dispatchEvent(new PointerEvent('pointermove',{pointerId:99,clientX:100,buttons:1}))")
    assert geometry(page)['width'] == 461
    if end == 'collapse':
        page.evaluate('MyAgentDock.closeDetails()')
    elif end == 'blur':
        page.evaluate("window.dispatchEvent(new Event('blur'))")
    elif end == 'lostpointercapture':
        page.evaluate('dockRightState.sash.releasePointerCapture(1)')
    else:
        page.evaluate("window.dispatchEvent(new PointerEvent('pointercancel',{pointerId:1}))")
    page.mouse.move(x-100, 300)
    assert geometry(page)['width'] == 461
    assert not geometry(page)['dragging']
    page.mouse.up()


def test_width_limits_preserve_workspace_and_preferred_width(details_page):
    page = open_details(details_page)
    x = geometry(page)['edge']
    page.mouse.move(x, 300)
    page.mouse.down()
    page.mouse.move(100, 300)
    page.mouse.up()
    assert geometry(page)['width'] == 660
    assert geometry(page)['main'] >= 560
    page.set_viewport_size({'width': 760, 'height': 900})
    page.wait_for_timeout(350)
    assert geometry(page)['mode'] == 'fullscreen'
    page.set_viewport_size({'width': 1000, 'height': 900})
    page.wait_for_timeout(350)
    assert geometry(page)['mode'] == 'fullscreen'
    page.set_viewport_size({'width': 1200, 'height': 900})
    page.wait_for_timeout(350)
    assert geometry(page)['mode'] == 'push'
    assert geometry(page)['main'] >= 560
    assert page.evaluate("localStorage.getItem(DOCK_RIGHT_WIDTH_KEY)") == '660'
    page.set_viewport_size({'width': 1600, 'height': 900})
    page.wait_for_timeout(350)
    assert geometry(page)['width'] == 660
    page.evaluate("document.getElementById('sidebar').style.width='480px'")
    page.wait_for_timeout(350)
    assert geometry(page)['main'] >= 560


def test_manual_fullscreen_survives_resize_and_half_screen_stays_collapsed(details_page):
    page = open_details(details_page)
    page.locator('[data-dock-rightbar-fullscreen]').click()
    page.set_viewport_size({'width': 1438, 'height': 900})
    page.wait_for_timeout(350)
    assert geometry(page)['mode'] == 'fullscreen'
    page.locator('[data-dock-rightbar-fullscreen]').click()
    assert geometry(page)['mode'] == 'push'
    page.set_viewport_size({'width': 1000, 'height': 900})
    page.wait_for_timeout(350)
    assert not geometry(page)['expanded']
    page.evaluate('MyAgentDock.openDetails()')
    page.wait_for_timeout(350)
    assert geometry(page)['mode'] == 'fullscreen'
