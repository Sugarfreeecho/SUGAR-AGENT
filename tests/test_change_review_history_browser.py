"""Read long change history while real-time events update the details page."""
from pathlib import Path

import pytest

from tests.test_llm_stream_full_text_browser import browser_page

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def history_page(browser_page):
    page = browser_page.context.browser.new_page(viewport={'width': 1100, 'height': 800})
    errors = []
    def on_error(error):
        errors.append(error)
    page.on('pageerror', on_error)
    page.set_content('<div id="chat-stream"></div><div id="host"></div>')
    page.add_style_tag(content=(ROOT / 'frontend/src/styles/dock.css').read_text(encoding='utf-8'))
    page.add_style_tag(content='''
      :root { --ui-text-xs:12px; --ui-text-sm:13px; --mono:monospace; }
      #host { width:360px; height:600px; }
      .dock-changes { display:flex; flex-direction:column; height:100%; }
      * { transition:none !important; }
    ''')
    page.evaluate("window.MyAgentIcons = {svg:()=>'<svg></svg>'}")
    page.add_script_tag(content=(ROOT / 'frontend/src/app/config.js').read_text(
        encoding='utf-8').replace('export function', 'function'))
    # Exercise the page body without starting the full Dock application shell.
    page.evaluate('window.dockSyncPluginPages=()=>{};window.dockInitPageNavigation=()=>{}')
    page.add_script_tag(content=(ROOT / 'frontend/src/app/modules/dock/embedder/right-column.js').read_text(
        encoding='utf-8'))
    page.evaluate(r'''() => {
      window.currentSessionId='session';
      window.longDiff=Array.from({length:3000},(_,i)=>'+'+i+' '+ 'content '.repeat(35)).join('\n');
      window.originalRow={path:'src/very/long/directory/nested/reviewed-file.js',snapshot_id:'reviewed',
        revision:1,added:3000,removed:0,diff:longDiff};
      dockRightFetchJSON=async()=>({response:{ok:true},data:{ok:true,
        user_turns:[{event_index:0,preview:'First'}],messages:{range_start:0,has_older:false,events:[
          {type:'user',content:'First'},
          {type:'tool_result',ui:{changes:[originalRow,...Array.from({length:16},(_,i)=>({
            path:'other/file-'+i+'.js',snapshot_id:'other-'+i,added:1,removed:0,diff:'+file'}))]}}
        ]}}});
      document.getElementById('host').appendChild(dockRightChangesBody({id:'changes'}));
      window.send=(event,index=10)=>document.dispatchEvent(new CustomEvent('myagent:ui-event',
        {detail:{sessionId:'session',event,eventIndex:index}}));
      window.setRunning=running=>{
        document.getElementById('chat-stream').innerHTML=running?'<div class="process-aggregate is-running"></div>':'';
        send({type:running?'run_started':'run_finished'});
      };
    }''')
    page.wait_for_selector('[data-dock-snapshot-id="reviewed"]')
    yield page
    page.evaluate('dockRightDisposeTab("changes")')
    page.remove_listener('pageerror', on_error)
    page.close()
    assert not errors, [str(error) for error in errors]


@pytest.mark.parametrize('path', [
    'src/very/long/directory/with-a-single-very-long-directory-name/reviewed-file.js',
    r'D:\project\src\very\long\directory\reviewed-file.js',
    '/home/project/src/<literal>/reviewed-file.js',
])
def test_history_keeps_path_tail_and_full_path_tooltip(history_page, path):
    page = history_page
    page.evaluate('path=>send({type:"tool_result",ui:{changes:[{...originalRow,path,revision:2}]}})', path)
    name = page.locator('[data-dock-snapshot-id="reviewed"] .dock-change-name')
    assert name.inner_text() == path
    assert name.get_attribute('title') == path
    for width in [360, 240]:
        page.evaluate('width=>document.getElementById("host").style.width=width+"px"', width)
        assert name.evaluate('el=>getComputedStyle(el).whiteSpace') == 'nowrap'
        assert name.evaluate('el=>getComputedStyle(el).textOverflow') == 'ellipsis'
        bounds = name.evaluate(r'''el=>{
          const text=el.querySelector('bdi').firstChild;
          const range=document.createRange();
          range.setStart(text,Math.max(text.textContent.lastIndexOf('/'),text.textContent.lastIndexOf('\\'))+1);
          range.setEnd(text,text.length);
          const tail=range.getBoundingClientRect();const box=el.getBoundingClientRect();
          range.setStart(text,Math.max(0,text.length-3));
          const suffix=range.getBoundingClientRect();
          range.setStart(text,0);range.setEnd(text,1);
          return {tailVisible:tail.left>=box.left-1 && tail.right<=box.right+1,
            filenameFits:tail.width<=box.width,suffixVisible:suffix.left>=box.left-1 && suffix.right<=box.right+1,
            startClipped:range.getBoundingClientRect().left<box.left,
            overflowing:el.scrollWidth>el.clientWidth};
        }''')
        assert bounds['suffixVisible'], 'the end of the filename stays visible'
        if bounds['filenameFits']:
            assert bounds['tailVisible'], 'show the whole filename when space permits'
        if bounds['overflowing']:
            assert bounds['startClipped'], 'truncate the leading directories'
        assert name.evaluate('''el=>{
          const head=el.closest('.dock-change-head');
          const parts=[...head.children].map(node=>node.getBoundingClientRect());
          const centers=parts.map(rect=>rect.top+rect.height/2);
          return Math.max(...centers)-Math.min(...centers)<=1
            && parts[1].right<=parts[2].left && parts[2].right<=parts[3].left
            && head.scrollWidth<=head.clientWidth+1;
        }'''), 'path, counts and undo stay on one line without overlap'
    assert page.locator('.dock-change-name literal').count() == 0


def test_history_keeps_diff_and_list_scroll_during_live_updates(history_page):
    page = history_page
    page.locator('[data-dock-snapshot-id="reviewed"] .dock-change-toggle').click()
    page.wait_for_function("document.querySelector('[data-dock-snapshot-id=reviewed] .dock-change-diff').children.length===3000")
    page.evaluate('''() => {
      window.article=document.querySelector('[data-dock-snapshot-id=reviewed]');
      window.diff=article.querySelector('.dock-change-diff');
      window.firstLine=diff.firstChild;
      window.list=document.querySelector('.dock-changes-list');
      diff.scrollTop=1650;diff.scrollLeft=240;list.scrollTop=180;
      window.beforeScroll={top:diff.scrollTop,left:diff.scrollLeft,list:list.scrollTop};
    }''')
    assert page.evaluate('beforeScroll.top') > 0
    assert page.evaluate('beforeScroll.left') > 0
    assert page.evaluate('beforeScroll.list') > 0
    for update, expected_count, running in [
        ('setRunning(true)', 3000, True),
        ('send({type:"tool_result",ui:{changes:[{path:"another/new.js",snapshot_id:"new",added:1,removed:0,diff:"+new"}]}})', 3000, True),
        ('send({type:"tool_result",ui:{changes:[{...originalRow,revision:2,diff:longDiff+"\\n+appended",added:3001}]}})', 3001, True),
        ('send({type:"tool_result",ui:{changes:[{...originalRow,revision:3,diff:longDiff.split("\\n").slice(0,500).join("\\n"),added:500}]}})', 500, True),
        ('setRunning(false)', 500, False),
        ('send({type:"file_changes_reverted",snapshot_ids:["reviewed"]})', 500, False),
    ]:
        page.evaluate(update)
        page.wait_for_function('''([count,running])=>{
          const el=document.querySelector('[data-dock-snapshot-id=reviewed]');
          return el.querySelector('.dock-change-diff').children.length===count
            && el.querySelector('.dock-change-action').disabled===running;
        }''', arg=[expected_count, running])
        assert page.evaluate('article===document.querySelector("[data-dock-snapshot-id=reviewed]")')
        assert page.evaluate('diff===article.querySelector(".dock-change-diff") && firstLine===diff.firstChild')
        assert page.evaluate('Math.abs(diff.scrollTop-beforeScroll.top)<=1 && Math.abs(diff.scrollLeft-beforeScroll.left)<=1')
        assert page.evaluate('Math.abs(list.scrollTop-beforeScroll.list)<=1')
    assert page.locator('[data-dock-snapshot-id="reviewed"] .dock-change-action').inner_text() == '恢复'
    assert page.locator('[data-dock-snapshot-id="reviewed"] .dock-change-reverted').inner_text() == '已撤销'
    assert page.locator('[data-dock-snapshot-id="reviewed"] .dock-change-added').inner_text() == '+500'
    # A retained button must act on the updated row, rather than its original closure.
    page.evaluate('''() => {window.fetch=async(url,options)=>{
      window.actionRequest={url,body:JSON.parse(options.body)};
      return {ok:true,json:async()=>({ok:true,snapshot_ids:['reviewed']})};
    }}''')
    page.locator('[data-dock-snapshot-id="reviewed"] .dock-change-action').click()
    page.wait_for_function('window.actionRequest && actionRequest.url.endsWith("/restore")')
    assert page.evaluate('actionRequest.body.snapshot_ids') == ['reviewed']
    assert page.locator('[data-dock-snapshot-id="reviewed"] .dock-change-reverted').count() == 0


def test_history_does_not_rebuild_diff_for_repeated_payloads(history_page):
    page = history_page
    page.locator('[data-dock-snapshot-id="reviewed"] .dock-change-toggle').click()
    page.wait_for_function("document.querySelector('.dock-change-diff').children.length===3000")
    result = page.evaluate('''async () => {
      let mutations=0;
      const diff=document.querySelector('.dock-change-diff');
      const observer=new MutationObserver(records=>mutations+=records.length);
      observer.observe(diff,{subtree:true,childList:true,characterData:true});
      for(let i=0;i<30;i++)dockRightRegisterChangeReviewRows({sessionId:'session',rows:[originalRow]});
      await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
      observer.disconnect();return {mutations,same:diff===document.querySelector('.dock-change-diff')};
    }''')
    assert result == {'mutations': 0, 'same': True}


def test_history_resumes_diff_rendering_after_switching_turns(history_page):
    page = history_page
    assert page.locator('.dock-change-diff').count() == 0, 'closed diffs render lazily'
    page.evaluate('''() => {
      document.querySelector('[data-dock-snapshot-id=reviewed] .dock-change-toggle').click();
      send({type:'user',content:'Second'},10);
      send({type:'tool_result',ui:{changes:[{path:'second.js',snapshot_id:'second',diff:'+second'}]}});
    }''')
    scope = page.locator('[data-dock-changes-scope="turn"]')
    scope.select_option('10')
    page.wait_for_function("!document.querySelector('[data-dock-snapshot-id=reviewed]')")
    scope.select_option('0')
    page.wait_for_function("document.querySelector('.dock-change-diff').children.length===3000")
    assert page.locator('[data-dock-snapshot-id="reviewed"] .dock-change-toggle').get_attribute('aria-expanded') == 'true'


@pytest.mark.parametrize('finish', ['seal', 'remove'])
def test_history_unlocks_actions_when_run_ends_without_ui_event(history_page, finish):
    page = history_page
    action = page.locator('[data-dock-snapshot-id="reviewed"] .dock-change-action')
    page.evaluate('''() => {
      window.reviewRequests=[];
      window.fetch=async(url,options)=>{
        const body=JSON.parse(options.body);reviewRequests.push({url,body});
        return {ok:true,json:async()=>({ok:true,snapshot_ids:body.snapshot_ids})};
      };
      setRunning(true);
    }''')
    page.wait_for_function("document.querySelector('.dock-change-action').disabled")
    action.evaluate('button=>button.click()')
    assert page.evaluate('reviewRequests.length') == 0
    # SSE terminal handling seals/removes the process directly and can bypass
    # renderEvent, so no myagent:ui-event is dispatched at this boundary.
    page.evaluate('''finish=>{
      const group=document.querySelector('#chat-stream .process-aggregate');
      if(finish==='seal')group.classList.remove('is-running');else group.remove();
    }''', finish)
    page.wait_for_function("!document.querySelector('.dock-change-action').disabled", timeout=2000)
    assert page.locator('.dock-change-turn-actions button:not([hidden]):disabled').count() == 0
    action.click()
    page.wait_for_function('reviewRequests.length===1')
    assert page.evaluate('reviewRequests[0].url.endsWith("/undo")')
    assert page.evaluate('reviewRequests[0].body.snapshot_ids') == ['reviewed']
    page.wait_for_function("document.querySelector('[data-dock-snapshot-id=reviewed] .dock-change-action').textContent==='恢复'")
    action.click()
    page.wait_for_function('reviewRequests.length===2')
    assert page.evaluate('reviewRequests[1].url.endsWith("/restore")')
