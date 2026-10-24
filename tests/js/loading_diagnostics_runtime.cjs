const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const root=path.resolve(__dirname,'../..');
const source=fs.readFileSync(path.join(root,'frontend/src/app/modules/session-management.js'),'utf8');
const fetchHelper=source.match(/^async function fetchWithTimeout\([^]*?^}/m)[0];
const diagnostics=fs.readFileSync(path.join(root,'frontend/src/app/modules/session-loading-diagnostics.js'),'utf8');
function setup(fetcher) {
  const timers=new Map();let seq=0;
  const c=vm.createContext({Date,Math,AbortController,performance:{now:()=>Date.now()},
    console:{info(){},warn(){}}, localStorage:{setItem(){}},
    setTimeout:(run,ms)=>{const timer=setTimeout(()=>{timers.delete(timer);run();},ms);timer.unref();timers.set(timer,run);return timer;},
    clearTimeout:timer=>{clearTimeout(timer);timers.delete(timer);},
    crypto:{randomUUID:()=>`request-${++seq}`},fetch:fetcher});
  vm.runInContext(fetchHelper+'\n'+diagnostics+'\nthis.diagnostics=sessionLoadingDiagnostics;',c);
  return {c,dispose(){for(const timer of timers.keys())clearTimeout(timer);},rows:()=>c.__MYAGENT_LOADING_DIAGNOSTICS__.snapshot()};
}

test('request and load logs share identifiers and never include message bodies',async()=>{
  let url,headers;
  const rt=setup(async(u,o)=>{url=u;headers=o.headers;return {ok:true,status:200,json:async()=>({messages:['SECRET BODY'],timing:{total:8}})};});
  try {
    const span=rt.c.diagnostics.start('session','history');
    await rt.c.diagnostics.fetchJSON(span,'/sessions/session/history_snapshot',{},30000);
    rt.c.diagnostics.phase(span,'hydrate');rt.c.diagnostics.end(span,'success');
    const rows=rt.rows(),request=rows.find(r=>r.event==='request_end'),end=rows.find(r=>r.event==='load_end');
    assert.equal(request.load_id,end.load_id);assert.equal(request.request_id,end.request_id);
    assert.equal(headers['X-Request-ID'],request.request_id);assert(url.includes('ui_request_id='+request.request_id));
    assert.equal(request.server_ms,8);assert.equal(end.status,'success');assert.equal(end.phase,'hydrate');
    assert(!JSON.stringify(rows).includes('SECRET BODY'));
  } finally {rt.dispose();}
});

test('header timeout, body timeout, cancellation, HTTP and JSON failures are distinct',async()=>{
  for(const mode of ['header-timeout','body-timeout','cancelled','http','json']) {
    const rt=setup(async(_u,o)=>{
      const stalled=()=>new Promise((_resolve,reject)=>o.signal.addEventListener('abort',()=>{
        const e=new Error('aborted');e.name='AbortError';reject(e);
      },{once:true}));
      if(mode==='header-timeout'||mode==='cancelled')return stalled();
      return {ok:mode!=='http',status:mode==='http'?503:200,json:()=>mode==='body-timeout'?stalled()
        :mode==='json'?Promise.reject(new SyntaxError('SECRET JSON')):Promise.resolve({})};
    });
    try {
      const controller=new AbortController(),span=rt.c.diagnostics.start('session','history');
      const promise=rt.c.diagnostics.fetchJSON(span,'/sessions/session/history_snapshot',{signal:controller.signal},15);
      if(mode==='cancelled')controller.abort();
      if(mode==='http')await promise;
      else await assert.rejects(promise);
      const row=rt.rows().find(r=>r.event==='request_end');
      assert.equal(row.reason,mode.endsWith('timeout')?'timeout':mode==='json'?'json_parse':mode==='http'?'http':'cancelled');
      assert.equal(row.phase,mode==='header-timeout'||mode==='cancelled'?'headers':'body');
      assert(row.elapsed_ms>=0);assert(!JSON.stringify(rt.rows()).includes('SECRET JSON'));
    } finally {rt.dispose();}
  }
});

test('local records and uploads are bounded and reporting failure never blocks loading',async()=>{
  let upload;
  const rt=setup((_url,opts)=>{upload=JSON.parse(opts.body);return Promise.reject(new Error('offline'));});
  try {
    for(let i=0;i<80;i++){const span=rt.c.diagnostics.start('session','history');rt.c.diagnostics.end(span,'cancelled');}
    assert.equal(rt.rows().length,128);
    rt.c.__MYAGENT_LOADING_DIAGNOSTICS__.flush();
    assert.equal(upload.records.length,32);
    await new Promise(resolve=>setImmediate(resolve));
  } finally {rt.dispose();}
});

test('background sidebar refreshes are traced and owned loads end only once',async()=>{
  const rt=setup(async()=>({ok:true,status:200,json:async()=>({sessions:[]})}));
  try {
    rt.c.sessionStore={snapshotRequestSeq:0};
    vm.runInContext(source.match(/^async function fetchSessionsStateSnapshot\([^]*?^}/m)[0],rt.c);
    const first=await rt.c.fetchSessionsStateSnapshot({includeArchived:true});
    assert.equal(first.client_request_seq,1);assert.equal(first.include_archived,true);
    assert.equal(rt.rows().filter(row=>row.event==='load_end').length,1);
    const owned=rt.c.diagnostics.start('','session_list');
    await rt.c.fetchSessionsStateSnapshot({loadingTrace:owned});
    assert.equal(rt.rows().filter(row=>row.event==='load_end').length,1);
    rt.c.diagnostics.end(owned,'success');
    assert.equal(rt.rows().filter(row=>row.event==='load_end').length,2);
    assert(rt.rows().filter(row=>row.event==='request_end').every(row=>row.route==='state'&&row.status==='success'));
  } finally {rt.dispose();}
});
