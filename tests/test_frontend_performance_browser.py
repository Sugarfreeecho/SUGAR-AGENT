"""Behavior and bounded-work checks for the UI performance changes."""
import os
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def page():
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(
                headless=True, **({"channel": "msedge"} if os.name == "nt" else {})
            )
        except playwright.Error as error:
            pytest.skip(f"Local Chromium browser unavailable: {error}")
        yield browser.new_page(viewport={"width": 1100, "height": 800})
        browser.close()


def test_process_height_updates_on_resize_without_work_on_scroll(page):
    source = (ROOT / "frontend/src/app/modules/message-rendering.js").read_text(encoding="utf-8")
    page.set_content(
        "<style>#chat-container{height:300px;overflow:auto;}"
        ".process-aggregate-body{max-height:min(72vh,41.6rem);overflow:auto;}</style>"
        "<div id='chat-container'><div class='process-aggregate' id='agg'>"
        "<div class='process-aggregate-body' id='body'><div style='height:2000px'></div>"
        "</div></div><div style='height:1000px'></div></div>"
    )
    page.add_script_tag(content=source[
        source.index("function applyProcessBodyViewportClamp("):
        source.index("function scheduleProcessAggregateHeightUi(")
    ])
    page.evaluate("ensureProcessViewportClampBinding();applyProcessBodyViewportClamp(agg)")
    page.wait_for_function("body.clientHeight===292")
    page.wait_for_function("processViewportClampHeight===300")
    page.evaluate("""() => {
      window.sweeps=0;window.styleWrites=0;
      const query=document.querySelectorAll.bind(document);
      document.querySelectorAll=selector=>{if(selector==='.process-aggregate')sweeps++;return query(selector);};
      new MutationObserver(rows=>{styleWrites+=rows.length;}).observe(body,{attributes:true,attributeFilter:['style']});
    }""")
    # Allow the initial ResizeObserver notification to finish before measuring scroll work.
    page.wait_for_timeout(50)
    page.evaluate("""() => {
      sweeps=0;styleWrites=0;
      for(let i=0;i<20;i++)applyProcessBodyViewportClamp(agg);
      const port=document.getElementById('chat-container');
      port.scrollTop=100;port.dispatchEvent(new Event('scroll'));
    }""")
    page.wait_for_timeout(50)
    assert page.evaluate("({sweeps,styleWrites})") == {"sweeps": 0, "styleWrites": 0}
    page.evaluate("document.getElementById('chat-container').style.height='200px'")
    page.wait_for_function("body.clientHeight===192")
    page.evaluate("document.getElementById('chat-container').style.height='1000px'")
    page.wait_for_function("body.clientHeight===576")  # Original 72vh limit still applies.


def test_viewed_turn_uses_bounded_geometry_reads_and_preserves_selection(page):
    source = (ROOT / "plugins/change-review/web/change-review.js").read_text(encoding="utf-8")
    page.set_content(
        "<style>#port{height:400px;overflow:auto;}"
        ".msg-wrap--user{height:30px}</style><div id='port'><div id='chat-stream'>"
        + "".join(f"<div class='msg-wrap--user' data-event-index='{i}'>turn {i}</div>" for i in range(4096))
        + "</div></div>"
    )
    page.add_script_tag(content=source.replace("export ", ""))
    result = page.evaluate("""() => {
      const port=document.getElementById('port'),users=document.querySelectorAll('.msg-wrap--user');
      const original=Element.prototype.getBoundingClientRect;
      const samples=[];
      for(const top of [0,20000,90000,port.scrollHeight]) {
        port.scrollTop=top;
        const rect=port.getBoundingClientRect(),pivot=rect.top+rect.height/2;
        const nearBottom=port.scrollTop+port.clientHeight>=port.scrollHeight-24;
        let expected=users[0];
        for(const user of users) {if(user.getBoundingClientRect().top<=pivot)expected=user;else break;}
        if(nearBottom)expected=users[users.length-1];
        let reads=0;
        Element.prototype.getBoundingClientRect=function(){
          if(this.classList.contains('msg-wrap--user'))reads++;return original.call(this);
        };
        const viewed=viewedTurnRange();
        Element.prototype.getBoundingClientRect=original;
        samples.push({correct:viewed.key===expected.dataset.eventIndex,reads,nearBottom});
      }
      return samples;
    }""")
    assert all(sample["correct"] and sample["reads"] <= 13 for sample in result)
    assert result[-1]["reads"] == 0 and result[-1]["nearBottom"]
