"""Local browser experiment for long-lived HTTP streams; no Agent runs started."""
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

from playwright.async_api import async_playwright

stop=threading.Event()
class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*_args): pass
    def handle(self):
        try: super().handle()
        except ConnectionError: pass  # Browser teardown closes retained HTTP/1 sockets.
    def do_GET(self):
        if self.path.startswith('/stream'):
            self.send_response(200)
            self.send_header('Content-Type','text/event-stream')
            self.send_header('Transfer-Encoding','chunked')
            self.end_headers()
            while not stop.is_set():
                try: self.wfile.write(b'9\r\n: ready\n\n\r\n');self.wfile.flush()
                except (OSError,ConnectionError): break
                stop.wait(0.1)
        else:
            data=b'<!doctype html><title>Local connection experiment</title>'
            self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers()
            try: self.wfile.write(data)
            except OSError: pass

async def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    records=[]
    try:
        async with async_playwright() as runtime:
            browser=await runtime.chromium.launch(channel='msedge',headless=True)
            for count, managed in ((3,False),(6,False),(9,True)):
                context=await browser.new_context()
                page=await context.new_page()
                await page.goto(f'http://127.0.0.1:{server.server_port}/')
                if managed:
                    await page.evaluate('''() => {
                      window.currentSessionId='';
                      window.sessionStore={runsBySession:new Map(),
                        setRun(sid,run){if(run)this.runsBySession.set(sid,run);else this.runsBySession.delete(sid);},
                        getRun(sid){return this.runsBySession.get(sid);}};
                      window.setSessionServerStreamActive=()=>{};
                    }''')
                    await page.add_script_tag(content=Path('frontend/src/app/state/session-actions.js').read_text(encoding='utf8'))
                    await page.evaluate('''async count => {
                      window.streamControllers=[];
                      for(let i=0;i<count;i++){
                        const sid='s'+i,ac=new AbortController();streamControllers.push(ac);
                        currentSessionId=sid;
                        setSessionRunState(sid,{controller:ac,submitted:true,ctx:{streamConsuming:true,stream:{dataset:{}}}});
                        const response=await fetch('/stream?i='+i,{signal:ac.signal});
                        const reader=response.body.getReader();
                        void(async()=>{try{while(!(await reader.read()).done){}}catch(e){}})();
                      }
                    }''',count)
                await page.evaluate('''async count=>{
                  if(!window.streamControllers)window.streamControllers=[];
                  await Promise.all(Array.from({length:count},(_,i)=>{
                    const ac=new AbortController();streamControllers.push(ac);
                    return fetch('/stream?i='+i,{signal:ac.signal}).then(async r=>{
                      const reader=r.body.getReader();
                      void (async()=>{try{while(!(await reader.read()).done){}}catch(e){}})();
                    });
                  }));
                  window.pingMs=null;const start=performance.now();
                  void fetch('/ping').then(r=>r.text()).then(()=>pingMs=Math.round(performance.now()-start));
                }''',0 if managed else count)
                await asyncio.sleep(0.5)
                blocked=await page.evaluate('pingMs===null')
                if blocked:
                    await page.evaluate('streamControllers.slice(0,3).forEach(c=>c.abort())')
                    await page.wait_for_function('pingMs!==null',timeout=5000)
                latency=await page.evaluate('pingMs')
                records.append({'sessions':count,'managed':managed,
                    'liveReaders':await page.evaluate('streamControllers.filter(c=>!c.signal.aborted).length'),
                    'blockedAfter500Ms':blocked,'pingMs':latency})
                await context.close()
            await browser.close()
    finally:
        stop.set();server.shutdown();server.server_close()
    target=Path('.analysis/stream-connections.json');target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(records,indent=2),encoding='utf8')
    print(json.dumps(records),flush=True)

asyncio.run(main())
