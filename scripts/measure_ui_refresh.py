"""Measure real browser navigation, sidebar/content readiness and HTTP waits.

Records timings and URL paths only; never stores response bodies or message text.
Run with the project's Python runtime (Playwright and a local Edge are required).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

from playwright.async_api import async_playwright


PROBE = """(() => {
  const probe = window.__loadingProbe = {sidebarMs:null, contentMs:null, usableMs:null,
    pluginsMs:null, longTasks:[]};
  const stamp = () => Math.round(performance.now());
  document.addEventListener('myagent:plugin-ui-ready', () => {probe.pluginsMs=stamp();}, {once:true});
  new PerformanceObserver(list => {
    for(const e of list.getEntries()) if(probe.longTasks.length<100)
      probe.longTasks.push({start:Math.round(e.startTime),ms:Math.round(e.duration)});
  }).observe({type:'longtask',buffered:true});
  let scheduled=false;
  const inspect = () => {
    scheduled=false;
    const sidebarList=document.getElementById('sessions-list');
    const sidebar=sidebarList && sidebarList.dataset.snapshotReady==='1' && sidebarList.querySelector('.session-item');
    const stream=document.getElementById('chat-stream');
    const loaded=!document.getElementById('chat-loading');
    if(sidebar && probe.sidebarMs===null)probe.sidebarMs=stamp();
    const content=loaded && stream && !stream.hidden &&
      (stream.dataset.sessionLoadOk==='1' || !!stream.querySelector('.welcome'));
    if(content && probe.contentMs===null)probe.contentMs=stamp();
    const composer=document.getElementById('message-input');
    if(sidebar && content && composer && !composer.disabled && probe.usableMs===null)probe.usableMs=stamp();
  };
  const observer=new MutationObserver(() => {
    if(!scheduled){scheduled=true;requestAnimationFrame(inspect);}
  });
  observer.observe(document,{childList:true,subtree:true,attributes:true,
    attributeFilter:['hidden','disabled','class','data-session-load-ok','data-snapshot-ready']});
  document.addEventListener('DOMContentLoaded',inspect,{once:true});
})();"""


async def measure_panels(page, readings):
    """Open read-only menus/settings twice to observe first and cached opens."""
    async def record(name, action, ready, frame=None, started_at=None):
        target = frame or page
        started = started_at if started_at is not None else await page.evaluate('performance.now()')
        try:
            await target.evaluate('''() => {
              window.__panelFeedbackMs=null;
              document.addEventListener('click', () => {
                const start=performance.now();
                requestAnimationFrame(()=>{window.__panelFeedbackMs=Math.round(performance.now()-start);});
              }, {once:true,capture:true});
            }''')
            await action()
            await target.wait_for_function(ready, timeout=15000, polling='raf')
            await page.evaluate('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
            readings.append({'panel':name, 'ms':round(await page.evaluate('performance.now()')-started),
                             'clickNextFrameMs':await target.evaluate('window.__panelFeedbackMs')})
        except Exception as error:
            readings.append({'panel':name, 'error':str(error)[:250]})
            raise

    for visit in ('first', 'cached'):
        async def open_models():
            await page.locator('#model-profile-trigger').click()
            pane = page.locator('#model-profile-menu.is-open [data-model-pane="model"]')
            if await pane.count(): await pane.click()
        await record('models-'+visit,
            open_models,
            "document.querySelector('#model-profile-menu.is-open [data-profile-id]')")
        await page.locator('#model-profile-trigger').click()
        for tab in ('skills', 'mcp', 'hooks', 'plugins'):
            if tab == 'skills':
                async def open_skills():
                    await page.locator('#skill-picker-btn').click()
                    active = page.locator('[data-skill-picker-tab="skills"]')
                    if await active.get_attribute('aria-selected') != 'true': await active.click()
                action = open_skills
            else:
                action = lambda tab=tab: page.locator('[data-skill-picker-tab="'+tab+'"]').click()
            await record(tab+'-'+visit, action, """() => {
              const p=document.querySelector('#skill-picker-popover.is-open');
              return p && !!p.querySelector('.skill-picker-list') &&
                !/正在加载|加载失败/.test(p.querySelector('.skill-picker-list').textContent);
            }""")
        await page.locator('#skill-picker-btn').click()
        settings_started = await page.evaluate('performance.now()')
        await page.locator('#sidebar-settings-btn').click()
        await page.locator('#settings-center-frame').wait_for(state='visible')
        frame = page.frame_locator('#settings-center-frame')
        settings = await (await page.locator('#settings-center-frame').element_handle()).content_frame()
        await record('settings-'+visit, lambda: asyncio.sleep(0), """() => {
          const b=document.querySelector('#st-body');
          return b && b.children.length && !/加载中|加载失败|渲染失败/.test(b.textContent);
        }""", frame=settings, started_at=settings_started)
        for section in ('models', 'skills', 'mcp', 'hooks', 'plugins'):
            await record('settings-'+section+'-'+visit,
                lambda section=section: frame.locator('[data-act="nav"][data-id="'+section+'"]').click(),
                """() => {
                  const b=document.querySelector('#st-body');
                  return b && b.children.length && !/加载中|加载失败|渲染失败/.test(b.textContent);
                }""", frame=settings)
        await frame.locator('[data-act="nav"][data-id="general"]').click()
        await settings.wait_for_function("document.querySelector('#st-body .st-card')", timeout=15000)
        # Clicking the exposed backdrop closes without editing or saving fields.
        await page.locator('#settings-center-overlay').click(position={'x':2,'y':2})
        await page.locator('#settings-center-overlay').wait_for(state='hidden')
        await record('settings-reopen-'+visit, lambda: page.locator('#sidebar-settings-btn').click(),
                     "!document.querySelector('#settings-center-overlay').hidden")
        await record('settings-close-'+visit,
                     lambda: page.locator('#settings-center-overlay').click(position={'x':2,'y':2}),
                     "document.querySelector('#settings-center-overlay').hidden")
    return readings


async def measure(args):
    args.output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as runtime:
        browser = await runtime.chromium.launch(headless=True, **({'channel':'msedge'} if os.name=='nt' else {}))
        try:
            context = await browser.new_context(viewport={'width':1280,'height':900})
            await context.add_init_script(PROBE)
            if args.session:
                value = json.dumps(args.session)
                await context.add_init_script("localStorage.setItem('lastSessionId'," + value + ");")
            page = await context.new_page()
            if args.cpu_rate != 1:
                devtools = await context.new_cdp_session(page)
                if not args.cpu_after_ready:
                    await devtools.send('Emulation.setCPUThrottlingRate', {'rate':args.cpu_rate})
            results = []
            pending, requests, errors = {}, [], []
            def started(request):
                pending[request] = {'path':urlsplit(request.url).path, 'type':request.resource_type, 'started':time.perf_counter()}
            def response_received(response):
                entry = pending.get(response.request)
                if entry is not None: entry['status'] = response.status
            def finished(request):
                entry = pending.pop(request, None)
                if entry is not None:
                    entry['ms'] = round((time.perf_counter()-entry.pop('started'))*1000,1)
                    timing = request.timing
                    if timing.get('requestStart', -1) >= 0:
                        entry['requestStartMs'] = round(timing['requestStart'], 1)
                    if timing.get('responseStart', -1) >= 0 and timing.get('requestStart', -1) >= 0:
                        entry['waitingHeadersMs'] = round(timing['responseStart'] - timing['requestStart'], 1)
                    if request.failure: entry['failure'] = request.failure
                    if len(requests)<1000: requests.append(entry)
            page.on('request',started)
            page.on('response',response_received)
            page.on('requestfinished',finished)
            page.on('requestfailed',finished)
            page.on('pageerror',lambda error: errors.append(str(error)[:250]) if len(errors)<20 else None)
            for index in range(args.rounds):
                pending.clear(); requests.clear(); errors.clear()
                wall = time.perf_counter()
                result = {'case':'fresh' if index==0 else 'refresh-'+str(index), 'cpuRate':args.cpu_rate,
                          'cpuAfterReady':args.cpu_after_ready}
                try:
                    if index==0: await page.goto(args.url,wait_until='domcontentloaded',timeout=args.timeout*1000)
                    else: await page.reload(wait_until='domcontentloaded',timeout=args.timeout*1000)
                    # Readiness is measured in the page at its first rendered frame,
                    # rather than reporting this polling interval as the load time.
                    deadline = wall+args.timeout
                    while time.perf_counter()<deadline:
                        ready = await asyncio.wait_for(page.evaluate('window.__loadingProbe && window.__loadingProbe.usableMs'),timeout=20)
                        if ready is not None: break
                        await asyncio.sleep(0.25)
                    result.update(await asyncio.wait_for(page.evaluate("""() => ({
                      ...window.__loadingProbe,
                      sessions:document.querySelectorAll('#sessions-list .session-item').length,
                      messages:document.querySelectorAll('#chat-stream .msg-wrap').length,
                      domElements:document.getElementsByTagName('*').length,
                      loading:!!document.getElementById('chat-loading'),
                      uiTimings:window.__MYAGENT_UI_PERF__?.snapshot().reports.slice(-1)[0]?.sessions,
                      navigation:performance.getEntriesByType('navigation').map(e=>({
                        htmlTtfbMs:Math.round(e.responseStart),domContentLoadedMs:Math.round(e.domContentLoadedEventEnd),
                        loadMs:Math.round(e.loadEventEnd)}))
                    })"""),timeout=5))
                    if args.screenshots:
                        await page.screenshot(path=str(args.output/(result['case']+'.png')),timeout=10000)
                except Exception as error:
                    result['error'] = str(error)[:400]
                result['observedMs'] = round((time.perf_counter()-wall)*1000)
                if args.panels and index == args.rounds-1 and result.get('usableMs') is not None:
                    result['panels'] = []
                    try:
                        if args.cpu_after_ready and args.cpu_rate != 1:
                            await devtools.send('Emulation.setCPUThrottlingRate', {'rate':args.cpu_rate})
                        await measure_panels(page, result['panels'])
                    except Exception as error:
                        result['panelError'] = str(error)[:400]
                result['slowRequests'] = sorted(requests,key=lambda r:r['ms'],reverse=True)[:30]
                result['pendingRequests'] = [{'path':r['path'],'ms':round((time.perf_counter()-r['started'])*1000)} for r in pending.values()]
                result['pageErrors'] = list(errors)
                results.append(result)
                (args.output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
                summary = {k:result.get(k) for k in ('case','sidebarMs','contentMs','usableMs','pluginsMs','sessions','observedMs','error')}
                print(json.dumps(summary,ensure_ascii=False),flush=True)
            return 0 if all(r.get('usableMs') is not None and not r.get('panelError') for r in results) else 1
        finally:
            await browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8192/')
    parser.add_argument('--session',help='Restore this existing session; use __new_session_draft__ for the draft view')
    parser.add_argument('--rounds',type=int,default=2)
    parser.add_argument('--timeout',type=float,default=45)
    parser.add_argument('--output',type=Path,default=Path('.analysis/ui-refresh'))
    parser.add_argument('--screenshots',action='store_true',help='Also save local screenshots (may contain conversation text)')
    parser.add_argument('--panels',action='store_true',help='Also time read-only model/extension menus and settings, opened twice')
    parser.add_argument('--cpu-rate',type=float,default=1,help='Chromium CPU slowdown factor (1 = no simulated slowdown)')
    parser.add_argument('--cpu-after-ready',action='store_true',help='Apply CPU slowdown only to panel interactions, after startup')
    args = parser.parse_args()
    if not 1<=args.rounds<=10 or not 1<=args.timeout<=120 or not 1<=args.cpu_rate<=20:
        parser.error('rounds must be 1..10, timeout 1..120 seconds and cpu-rate 1..20')
    return asyncio.run(measure(args))


if __name__=='__main__':
    raise SystemExit(main())
