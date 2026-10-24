"""Observe a running UI without sending prompts or recording conversation text."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

from playwright.async_api import async_playwright


async def main(args):
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {'seconds':args.seconds, 'samples':[], 'requests':{}, 'errors':[]}
    async with async_playwright() as runtime:
        browser = await runtime.chromium.launch(headless=True, **({'channel':'msedge'} if os.name=='nt' else {}))
        try:
            context = await browser.new_context(viewport={'width':1280,'height':900})
            if args.session:
                await context.add_init_script('localStorage.setItem("lastSessionId",'+json.dumps(args.session)+')')
            await context.add_init_script('''window.__runtimeLongTasks=[];
                new PerformanceObserver(list=>{for(const e of list.getEntries()){
                  if(__runtimeLongTasks.length<1000)__runtimeLongTasks.push([Math.round(e.startTime),Math.round(e.duration)]);
                }}).observe({type:'longtask',buffered:true});''')
            page = await context.new_page()
            pending, active, counts, peaks, durations = {}, Counter(), Counter(), Counter(), {}
            def begin(request):
                path = urlsplit(request.url).path
                # IDs are unnecessary for aggregate endpoint measurements.
                pieces = path.split('/')
                if len(pieces)>2 and pieces[1]=='sessions': pieces[2]=':session'
                path = '/'.join(pieces)
                pending[request]=(path,time.perf_counter())
                counts[path]+=1;active[path]+=1;peaks[path]=max(peaks[path],active[path])
            def end(request):
                entry = pending.pop(request,None)
                if entry:
                    path,started=entry;active[path]-=1
                    durations.setdefault(path,[]).append(round((time.perf_counter()-started)*1000))
            page.on('request',begin);page.on('requestfinished',end);page.on('requestfailed',end)
            page.on('pageerror',lambda error: result['errors'].append(str(error)[:200]))
            metrics = await context.new_cdp_session(page)
            await metrics.send('Performance.enable')
            started=time.perf_counter()
            await page.goto(args.url,wait_until='domcontentloaded',timeout=90000)
            while time.perf_counter()-started<args.seconds:
                values = {row['name']:row['value'] for row in (await metrics.send('Performance.getMetrics'))['metrics']}
                sample = {'elapsedMs':round((time.perf_counter()-started)*1000),
                    **{key:values.get(key) for key in ('JSHeapUsedSize','Nodes','Documents','JSEventListeners','LayoutCount','RecalcStyleCount','TaskDuration')}}
                sample.update(await page.evaluate('''() => ({
                  sessions:document.querySelectorAll('#sessions-list .session-item').length,
                  running:document.querySelectorAll('#sessions-list .session-item.is-running').length,
                  longTasks:window.__runtimeLongTasks,
                  pendingStreams:performance.getEntriesByType('resource').filter(x=>x.name.includes('/events')).length
                })'''))
                sample['activeRequests']=dict(active)
                result['samples'].append(sample)
                result['requests']={key:{'count':counts[key],'peak':peaks[key],'active':active[key],
                    'maxMs':max(durations.get(key,[0]))} for key in counts}
                args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
                print(json.dumps({key:sample[key] for key in ('elapsedMs','JSHeapUsedSize','Nodes','JSEventListeners','LayoutCount')}) ,flush=True)
                await asyncio.sleep(min(10,max(0,args.seconds-(time.perf_counter()-started))))
        finally:
            await browser.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8192/')
    parser.add_argument('--session')
    parser.add_argument('--seconds',type=int,default=60)
    parser.add_argument('--output',type=Path,default=Path('.analysis/ui-runtime.json'))
    options=parser.parse_args()
    if not 10<=options.seconds<=600: parser.error('seconds must be 10..600')
    asyncio.run(main(options))
