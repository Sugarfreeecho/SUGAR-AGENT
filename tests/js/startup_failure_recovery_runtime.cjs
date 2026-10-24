const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(process.env.STARTUP_SOURCE_PATH || path.join(__dirname, '../../frontend/src/app/modules/session-management.js'), 'utf8');
const fn = name => source.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'))[0];
const deferred = () => { let resolve; const promise = new Promise(r => resolve = r); return {promise, resolve}; };
const tick = () => new Promise(resolve => setImmediate(resolve));

test('an HTTP error fallback cannot replace the sidebar with an empty successful snapshot', async () => {
  let applied=0, retries=0;
  const c=vm.createContext({console:{error(){}},sessionListLoadEpoch:0,pendingQuerySession:'',archivedSessionsCount:0,
    sessionStore:{ui:{},snapshotRequestSeq:0,list:()=>[],setArchivedCount(){}},
    fetchSessionsStateSnapshot:async()=>{throw new Error('cold startup');},
    fetchWithTimeout:async(_url,_opts,_ms,consume)=>{
      const response={ok:false,status:503,headers:{get:()=>null},json:async()=>({error:'temporarily unavailable'})};
      return consume?consume(response):response;
    },
    applySessionSnapshot:()=>applied++,sessionUnreadComplete:new Set(),sessionsList:{dataset:{}},
    scheduleSessionListRetry:()=>retries++,
  });
  for(const name of ['updateSidebarRuntimeStatus','syncArchivedSessionStateFromStore','persistSessionUnread',
    'renderSessionListIfChanged','clearSessionListError','renderSessionListError','resetSessionListRetry'])c[name]=()=>{};
  vm.runInContext(fn('loadSessionsInner'),c);
  assert.equal(await c.loadSessionsInner({}),false);
  assert.equal(applied,0,'a failed request must not turn into authoritative empty history');
  assert.equal(retries,1,'transient startup failures must recover without reloading the page');
});

test('completion of an older forced load cannot clear the newer shared request', async () => {
  const calls=[];
  const c=vm.createContext({sessionListLoadPromise:null,loadSessionsInner:()=>{const d=deferred();calls.push(d);return d.promise;}});
  vm.runInContext(fn('loadSessions'),c);
  const first=c.loadSessions(),second=c.loadSessions({force:true});
  calls[0].resolve(true);await first;
  const third=c.loadSessions();
  assert.equal(calls.length,2,'the third reader must join the newer in-flight request');
  calls[1].resolve(true);await Promise.all([second,third]);
});

test('a JSON body remains covered by the fetch deadline after headers arrive', async () => {
  let aborted=false;
  const c=vm.createContext({AbortController,setTimeout,clearTimeout,
    fetch:async(_url,opts)=>({json:()=>new Promise((_resolve,reject)=>{
      opts.signal.addEventListener('abort',()=>{aborted=true;reject(new Error('body aborted'));},{once:true});
    })}),
  });
  vm.runInContext(fn('fetchWithTimeout'),c);
  await assert.rejects(c.fetchWithTimeout('/state',{},10,response=>response.json()),/body aborted/);
  assert.equal(aborted,true);
});

test('automatic sidebar recovery has one timer and a bounded retry budget', async () => {
  const name='scheduleSessionListRetry';
  assert(source.includes('function '+name),'startup failures need a recovery scheduler');
  const jobs=[];let loads=0;
  const c=vm.createContext({sessionListRetryTimer:null,sessionListRetryAttempts:0,
    setTimeout:(run,ms)=>{jobs.push({run,ms});return jobs.length;},
    loadSessions:async()=>{loads++;},
  });
  vm.runInContext(fn(name),c);
  c.scheduleSessionListRetry();c.scheduleSessionListRetry();assert.equal(jobs.length,1);
  for(let i=0;i<3;i++){
    jobs[i].run();await tick();c.scheduleSessionListRetry();
  }
  assert.equal(jobs.length,3);assert.equal(loads,3);
});

test('clicking the opening session again cannot cancel its history request', async () => {
  const controller=new AbortController();
  const c=vm.createContext({globalThis:{}, currentSessionId:'s', sessionHistoryLoadController:controller,
    getVisibleChatStream:()=>({dataset:{}}), clearSessionUnreadState(){}});
  vm.runInContext(fn('switchSession'),c);
  assert.equal(await c.switchSession('s'),true);
  assert.equal(controller.signal.aborted,false);
});

test('a brief history 503 recovers once, while cancellation stops the backoff', async () => {
  let calls=0;
  const c=vm.createContext({setTimeout,clearTimeout,fetchWithTimeout:async()=>{
    calls++; return {response:{status:calls===1?503:200},data:{messages:[]}};
  }});
  vm.runInContext(fn('fetchSessionHistoryJSON'),c);
  assert.equal((await c.fetchSessionHistoryJSON('/history')).response.status,200);
  assert.equal(calls,2);
  calls=0;
  const controller=new AbortController();
  const pending=c.fetchSessionHistoryJSON('/history',controller.signal);
  await tick();controller.abort();
  await assert.rejects(pending,{name:'AbortError'});
  assert.equal(calls,1);
});
