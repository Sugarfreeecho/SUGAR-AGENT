// Offline browser geometry checks against the production history paging helpers.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
let chromium = null;
try {
  ({ chromium } = require('playwright'));
} catch (err) {
  try {
    ({ chromium } = require(path.join(root, 'frontend/node_modules/playwright')));
  } catch (err2) {
    console.log('history_paging_browser: playwright not installed - skipping browser geometry checks');
    process.exit(0);
  }
}
const source = fs.readFileSync(path.join(root, 'frontend/src/app/modules/session-scroll-history.js'), 'utf8');
const wiring = fs.readFileSync(path.join(root, 'frontend/src/app/modules/sse-handling.js'), 'utf8');
function between(text, start, end) {
  const a = text.indexOf(start), b = text.indexOf(end, a);
  assert(a >= 0 && b > a);
  return text.slice(a, b);
}
const helpers = between(source, 'var HISTORY_AUTO_LOAD_TOP_PX', 'function insertNewEmptyChatStream');
const events = between(wiring, '// 捕获阶段也记录嵌套滚动区的阅读意图', "sendBtn.addEventListener('click'");

async function fixture(page) {
  await page.setContent(`<style>
    #chat-container { height:320px; width:600px; overflow:auto; overflow-anchor:none; scroll-behavior:smooth; }
    .msg-wrap { height:80px; } #history-load-sentinel { height:36px; }
    .process-aggregate { padding:0; } .feed-item { height:80px; }
  </style><div id="chat-container"><div id="chat-stream">
    <div id="history-load-sentinel"><button class="history-load-older-btn">加载更早记录</button></div>
    ${Array.from({ length: 20 }, (_, i) => `<div class="msg-wrap" id="old${i}">old ${i}</div>`).join('')}
  </div></div>`);
  await page.addScriptTag({ content: `
    var currentSessionId='s',replayingMessages=false,historyOlderLoading=false;
    var sessionStore={ui:{loadingMessages:false}},active=true;
    var HISTORY_DIALOGUES_PER_PAGE=5,HISTORY_EVENT_BUDGET=500;
    var chatContainer=document.getElementById('chat-container');
    var sessionHistoryPaging={sessionId:'s',range_start:10,range_end:30,has_older:true,manual_history:true};
    var calls=0,finishFetch=null;
    function getVisibleChatStream(){return document.getElementById('chat-stream');}
    function getSessionHistoryPaging(){return sessionHistoryPaging;}
    function sessionHasLiveHistoryOwner(){return active;}
    function isHistorySmoothScrollActive(){return false;}
    function ensureHistorySentinel(){}
    function newDomContext(stream){return {stream:stream};}
    function reduceAndRenderMessageEvent(ctx,ev){
      var row=document.createElement('div');row.className='msg-wrap';row.id=ev.id;
      row.style.height=ev.height+'px';ctx.stream.appendChild(row);
    }
    function setSessionHistoryPaging(value){sessionHistoryPaging=value;updateHistorySentinelVisibility();}
    function bindExistingLogs(){}
    function rebuildToc(){}
    function scheduleTocActiveUpdate(){}
    function refreshLiveAutoFollowPins(){}
    function fetchWithTimeout(){calls++;return new Promise(resolve=>{finishFetch=()=>resolve({
      ok:true,json:async()=>({events:[{type:'user',id:'older',height:180}],range_start:5,total:30,has_older:true})
    });});}
    ${between(source, 'function setScrollTopImmediate', '/** 当前运行会话对应')}
    ${helpers}
    ${events}
    function frames(){return new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));}
    function offset(id){return document.getElementById(id).getBoundingClientRect().top-chatContainer.getBoundingClientRect().top;}
  ` });
}

async function main() {
  const browser = await chromium.launch({ headless: true, ...(process.platform === 'win32' ? { channel: 'msedge' } : {}) });
  const page = await browser.newPage();
  try {
    await fixture(page);
    const auto = await page.evaluate(async () => {
      sessionStore.ui.loadingMessages=true;
      chatContainer.dispatchEvent(new Event('scroll'));
      sessionStore.ui.loadingMessages=false;
      chatContainer.dispatchEvent(new Event('scroll'));
      var initial=calls;
      chatContainer.dispatchEvent(new WheelEvent('wheel',{deltaY:-80,bubbles:true}));
      var afterGesture=calls;
      finishFetch();await frames();
      cancelHistoryPrependViewport(getVisibleChatStream());
      return {initial,afterGesture,manual:sessionHistoryPaging.manual_history};
    });
    assert.equal(auto.initial, 0, 'opening a current turn must not eagerly fetch history');
    assert.equal(auto.afterGesture, 1, 'upward reading at the top must fetch history');
    assert.equal(auto.manual, false, 'after reading older history automatic pagination remains available');

    await fixture(page);
    const geometry = await page.evaluate(async () => {
      setScrollTopImmediate(chatContainer,200);await frames();
      var pending=loadOlderHistoryChunk();
      // The reader moves while the network request is still pending.
      setScrollTopImmediate(chatContainer,350);await frames();
      var before=offset('old4');finishFetch();await pending;await frames();
      var inserted=offset('old4');
      document.getElementById('older').style.height='280px';await frames();
      var lateAbove=offset('old4');
      document.getElementById('old19').style.height='380px';await frames();
      var growthBelow=offset('old4');
      // Hiding the sentinel has a negative height delta and must also be compensated.
      document.getElementById('history-load-sentinel').hidden=true;await frames();
      var removedStrip=offset('old4');
      chatContainer.dispatchEvent(new WheelEvent('wheel',{deltaY:-80,bubbles:true}));
      var stopped=!getVisibleChatStream()._historyPrependViewport;
      document.getElementById('older').style.height='340px';await frames();
      return {before,inserted,lateAbove,growthBelow,removedStrip,stopped,afterGesture:offset('old4')};
    });
    for (const key of ['inserted', 'lateAbove', 'growthBelow', 'removedStrip']) {
      assert(Math.abs(geometry[key] - geometry.before) < 1, `${key}: ${JSON.stringify(geometry)}`);
    }
    assert(geometry.stopped, 'new reader input must cancel the layout correction');
    assert(Math.abs(geometry.afterGesture - geometry.removedStrip) >= 59, 'correction must not pull back after the reader takes control');

    await fixture(page);
    const merge = await page.evaluate(async () => {
      var stream=getVisibleChatStream();
      stream.innerHTML='<div class="process-aggregate" id="oldGroup"><div class="feed-item" id="keptRow"></div></div>'
        +'<div class="msg-wrap" style="height:1600px"></div>';
      setScrollTopImmediate(chatContainer,20);await frames();
      var before=offset('keptRow');var state=captureHistoryPrependViewport(stream,chatContainer,'s');
      var group=document.createElement('div');group.className='process-aggregate';
      group.innerHTML='<div class="feed-item" style="height:180px"></div>';stream.prepend(group);
      group.appendChild(document.getElementById('keptRow'));document.getElementById('oldGroup').remove();
      settleHistoryPrependViewport(state);await frames();
      var after=offset('keptRow');
      currentSessionId='another';
      group.firstChild.style.height='240px';await frames();
      return {before,after,stopped:!stream._historyPrependViewport};
    });
    assert(Math.abs(merge.after - merge.before) < 1, 'a transferred execution row must remain at its previous viewport offset');
    assert(merge.stopped, 'changing sessions must stop all old layout correction');
    process.stdout.write(JSON.stringify({ auto, geometry, merge }, null, 2) + '\n');
    process.stdout.write('history paging browser checks passed\n');
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
