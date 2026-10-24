"""Exercise plugin category navigation and the compact sidebar browser chrome."""
from tests.test_details_pages_browser import browser_page, details_page, plugin_frame


def test_guide_groups_plugin_contributions_and_catalog_updates(details_page):
    page, _calls, errors, rows = details_page
    pages = [rows[0], {**rows[0], 'id': 'secondary', 'title': 'Another page', 'order': 0},
             {**rows[0], 'plugin_id': 'other', 'href': '/plugins/other', 'title': '<Other>', 'order': 10},
             {**rows[0], 'slot': 'settings.section', 'id': 'settings', 'embedded': True, 'title': 'Config'}]
    page.evaluate('rows=>MyAgentDock.syncPluginPages(rows)', pages)
    page.evaluate("MyAgentDock.openDetailsTab('guide')")
    assert page.locator('[data-dock-guide-entry]').evaluate_all(
        "cards=>cards.map(card=>card.dataset.dockGuideEntry)"
    ) == ['files', 'changes', 'browser', 'plugins']
    assert page.locator('.dock-plugin-page').count() == 0
    page.locator('[data-dock-guide-entry="plugins"]').click()
    catalog = page.locator('[data-dock-plugin-catalog]')
    assert catalog.is_visible()
    assert catalog.locator('[data-dock-plugin-page]').evaluate_all(
        "rows=>rows.map(row=>row.dataset.dockPluginPage)"
    ) == ['demo:secondary', 'other:main', 'demo:main']
    assert catalog.locator('[data-dock-plugin-page="other:main"]').inner_text() == '<Other>'
    assert catalog.locator('other').count() == 0, 'plugin labels remain text'
    catalog.locator('[data-dock-plugin-page="demo:secondary"]').click()
    frame = plugin_frame(page)
    assert frame.evaluate('MyAgentPluginPage.context.pageId') == 'secondary'
    identity = frame.evaluate('window.instance')
    page.evaluate("MyAgentDock.openDetailsTab('plugins')")
    assert catalog.is_visible()
    catalog.locator('[data-dock-plugin-page="demo:secondary"]').click()
    assert plugin_frame(page).evaluate('window.instance') == identity
    page.evaluate("MyAgentDock.openDetailsTab('plugins')")
    # Toggle while the category is floating; both the live list and title update.
    page.evaluate("""() => {
        const surface=dockSurfaceOf(dockRightState.sessionId,DOCK_RIGHT_AREA);
        const tab=Object.values(surface.layout.tabs).find(tab=>tab.kind==='plugins');
        dockRightIntents().floatTab(tab.id,{x:220,y:100,width:420,height:500});
    }""")
    assert page.locator('.dock-float [data-dock-plugin-catalog]').is_visible()
    assert page.locator('.dock-float .dock-page-title-icon svg').count() == 1
    page.evaluate('rows=>MyAgentDock.syncPluginPages(rows)', [])
    assert page.locator('.dock-float .dock-plugin-catalog-empty').is_visible()
    assert page.locator('.dock-plugin-page').count() == 0
    page.evaluate('rows=>MyAgentDock.syncPluginPages(rows)', rows)
    assert page.locator('.dock-float [data-dock-plugin-page="demo:main"]').is_visible()
    assert not errors, [str(error) for error in errors]


def test_browser_chrome_focus_navigation_and_unknown_address(details_page):
    page, _calls, errors, _rows = details_page
    page.add_style_tag(content='*{box-sizing:border-box}')
    page.evaluate("MyAgentDock.openBrowser()")
    browser = page.locator('.dock-browser-page:not([hidden])')
    browser.wait_for()
    assert browser.locator('.dock-browser-placeholder').is_visible()
    assert browser.locator('.dock-browser-toolbar').evaluate('el=>el.getBoundingClientRect().height') == 38
    assert browser.locator('.dock-browser-tool svg').count() == 5
    assert browser.locator('.dock-browser-tool').evaluate_all(
        'buttons=>buttons.every(button=>button.textContent.trim()==="" && button.getBoundingClientRect().width===28)'
    )
    assert page.locator('.dock-chip.is-active .dock-page-title-icon svg').count() == 1
    assert page.locator('.dock-chip.is-active .dock-page-title-label').evaluate('el=>el.clientWidth>=el.scrollWidth')
    go = browser.locator('[aria-label="前往"]')
    assert not go.is_visible()
    address = browser.locator('input')
    address.fill('https://browser.fixture.test/one')
    assert go.is_visible()
    go.click()
    frame = page.frame_locator('.dock-browser-page:not([hidden]) iframe')
    frame.locator('a').wait_for()
    page.wait_for_function("document.querySelector('.dock-browser-page:not([hidden]) .dock-browser-placeholder').hidden")
    assert browser.locator('.dock-browser-placeholder').is_hidden()
    browser_frame = next(frame for frame in page.frames if frame.url.endswith('/one'))
    browser_frame.wait_for_load_state('load')
    frame.locator('a').click()
    badge = browser.locator('.dock-browser-address-changed')
    badge.wait_for()
    assert browser.locator('[aria-label="在系统浏览器中打开"]').is_disabled()
    address.focus()
    assert not badge.is_visible()
    assert go.is_visible()
    address.press('Enter')
    frame.locator('a').wait_for()
    page.wait_for_function("!document.querySelector('.dock-browser-page:not([hidden]) .dock-browser-address-box').classList.contains('is-unknown')")
    assert browser.locator('[aria-label="在系统浏览器中打开"]').is_enabled()
    assert not errors, [str(error) for error in errors]
