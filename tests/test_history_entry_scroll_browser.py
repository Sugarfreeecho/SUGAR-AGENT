"""Real scroll geometry: cold entry animates without gating readiness."""
import os
from pathlib import Path

import pytest

playwright = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def page():
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True, **({'channel': 'msedge'} if os.name == 'nt' else {}))
        page = browser.new_page(viewport={'width': 1000, 'height': 800})
        page.set_content('<style>#chat{height:500px;overflow:auto;scroll-behavior:smooth}</style>'
                         '<div id="chat"><div style="height:200000px"></div></div>')
        scroll = (ROOT / 'frontend/src/app/modules/session-scroll-history.js').read_text(encoding='utf-8')
        render = (ROOT / 'frontend/src/app/modules/message-rendering.js').read_text(encoding='utf-8')
        page.add_script_tag(content='''var chatContainer=document.getElementById('chat'),currentSessionId='s',
            switchSessionEpoch=1,streamChatNearBottom=false,streamProcNearBottom=false,liveAutoFollow=false;
            function cancelSmoothStreamFollowForHistoryLoad() {}
            function isSessionRunning() {return false;}
            function isServerStreamActive() {return false;}
        ''' + scroll[scroll.index('function setScrollTopImmediate('):scroll.index('/** 当前运行会话')]
            + render[render.index('var historySmoothScrollSessionId'):render.index("window.addEventListener('beforeunload'")]
            + render[render.index('function historyLoadScrollsToBottom('):render.index('function setWelcome(')])
        yield page
        browser.close()


def test_long_history_entry_is_bounded_and_ready_before_motion_ends(page):
    result = page.evaluate('''async () => {
        applyChatScrollAfterHistoryLoad('s','entry-bottom');
        const gap=()=>chatContainer.scrollHeight-chatContainer.clientHeight-chatContainer.scrollTop;
        const initialGap=gap(),samples=[initialGap],started=performance.now();
        await waitForChatScrollAfterHistoryLoad('s','entry-bottom');
        const readyMs=performance.now()-started,activeAtReady=isHistorySmoothScrollActive();
        while(isHistorySmoothScrollActive()) {
            await new Promise(requestAnimationFrame);samples.push(gap());
        }
        return {initialGap,readyMs,activeAtReady,samples,elapsed:performance.now()-started,gap:gap()};
    }''')
    assert 200 <= result['initialGap'] <= 320
    assert result['activeAtReady']
    assert result['readyMs'] < 150
    assert len(set(result['samples'])) > 3
    assert 200 <= result['elapsed'] < 800
    assert abs(result['gap']) <= 1


@pytest.mark.parametrize('interrupt', ['wheel', 'touchstart', 'pointerdown', 'keydown', 'switch'])
def test_reader_and_switch_cancel_entry_without_late_reposition(page, interrupt):
    result = page.evaluate('''async interrupt => {
        applyChatScrollAfterHistoryLoad('s','entry-bottom');
        await new Promise(requestAnimationFrame);
        if(interrupt==='switch') {switchSessionEpoch+=2;endHistorySmoothScroll();}
        else chatContainer.dispatchEvent(new Event(interrupt));
        setScrollTopImmediate(chatContainer,1234);
        await new Promise(resolve=>setTimeout(resolve,350));
        return {top:chatContainer.scrollTop,active:isHistorySmoothScrollActive()};
    }''', interrupt)
    assert result == {'top': 1234, 'active': False}


def test_reduced_motion_opens_at_bottom_without_frames(page):
    page.emulate_media(reduced_motion='reduce')
    result = page.evaluate('''() => {
        applyChatScrollAfterHistoryLoad('s','entry-bottom');
        return {gap:chatContainer.scrollHeight-chatContainer.clientHeight-chatContainer.scrollTop,
            active:isHistorySmoothScrollActive()};
    }''')
    assert result == {'gap': 0, 'active': False}


def test_new_generation_takes_over_entry_on_next_frame(page):
    result = page.evaluate('''async () => {
        applyChatScrollAfterHistoryLoad('s','entry-bottom');
        isSessionRunning=()=>true;
        await new Promise(requestAnimationFrame);
        return {gap:chatContainer.scrollHeight-chatContainer.clientHeight-chatContainer.scrollTop,
            active:isHistorySmoothScrollActive()};
    }''')
    assert result == {'gap': 0, 'active': False}


def test_history_readiness_does_not_depend_on_animation_frames(page):
    result = page.evaluate('''async () => {
        requestAnimationFrame=()=>1;cancelAnimationFrame=()=>{};
        const started=performance.now();
        const ready=await waitForChatScrollAfterHistoryLoad('s','entry-bottom');
        return {ready,elapsed:performance.now()-started};
    }''')
    assert result['ready']
    assert result['elapsed'] < 500


def test_late_workspace_metadata_cannot_resize_reserved_history_image(page):
    css = (ROOT / 'frontend/src/styles/app.css').read_text(encoding='utf-8')
    page.add_style_tag(content=css)
    source = (ROOT / 'frontend/src/app/modules/workspace-media.js').read_text(encoding='utf-8')
    for name in ['normalizeWorkspaceImageMetadata', 'applyWorkspaceImageMetadata']:
        start = source.index('function '+name+'(')
        end = source.index('\n}', start) + 2
        page.add_script_tag(content=source[start:end])
    result = page.evaluate('''async () => {
        const block=document.createElement('div');block.className='message';
        const img=document.createElement('img');img.className='msg-workspace-image';
        img.src='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="2000" height="20"></svg>');
        block.append(img);chatContainer.append(block);
        const ready=await waitForHistoryImageLayout('s','entry-bottom',chatContainer);
        const before=img.getBoundingClientRect().height;
        applyWorkspaceImageMetadata(img,{width:2000,height:20});
        await new Promise(requestAnimationFrame);
        return {ready,reserved:img.getAttribute('data-history-image-fallback'),
            before,after:img.getBoundingClientRect().height};
    }''')
    assert result['ready'] and result['reserved'] == '1'
    assert result['before'] > 0
    assert abs(result['after'] - result['before']) < 1
