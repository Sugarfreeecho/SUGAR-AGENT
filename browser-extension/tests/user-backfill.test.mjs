import test from 'node:test';
import assert from 'node:assert/strict';
import {createUserBackfill} from '../src/user-backfill.mjs';

const flush=()=>new Promise(resolve=>setImmediate(resolve));
const missing={runId:'run',status:'running'};
function setup(read){
  const timers=new Map(),applied=[],delays=[];let serial=0,current={sessionId:'a',epoch:1};
  const backfill=createUserBackfill({read,apply:(...args)=>applied.push(args),isCurrent:(id,epoch)=>id===current.sessionId&&epoch===current.epoch,
    setTimer:(fn,delay)=>{delays.push(delay);timers.set(++serial,fn);return serial;},clearTimer:id=>timers.delete(id)});
  return {backfill,timers,applied,delays,sync:(turns=[missing],extra={})=>backfill.sync({...current,turns,...extra}),
    select:(id,epoch)=>current={sessionId:id,epoch},tick:async()=>{const [id,fn]=timers.entries().next().value;timers.delete(id);fn();await flush();}};
}
test('stream renders coalesce into one in-flight history read',async()=>{
  let reads=0,finish;const f=setup(()=>{reads++;return new Promise(resolve=>finish=resolve);});
  for(let n=0;n<100;n++)f.sync();assert.equal(reads,1);
  finish({events:[]});await flush();assert.equal(f.timers.size,1);
  for(let n=0;n<100;n++)f.sync();assert.equal(reads,1);
  f.backfill.dispose();assert.equal(f.timers.size,0);
});
test('more than two empty snapshots recover without another stream delta',async()=>{
  let reads=0;const fact={type:'user',run_id:'run',content:'late user'};
  const f=setup(async()=>({events:++reads<5?[]:[fact]}));f.sync();await flush();
  for(let n=0;n<4;n++)await f.tick();
  assert.equal(reads,5);assert.deepEqual(f.applied,[[fact,'a',1]]);assert.equal(f.timers.size,0);
  assert.deepEqual(f.delays,[300,600,1200,2400]);
});
test('transient failures retry with a bounded delay and preserve the real fact',async()=>{
  let reads=0;const f=setup(async()=>{reads++;if(reads<=10)throw Error('offline');return {events:[{type:'user',run_id:'run',images:['image.png']}]};});
  f.sync();await flush();for(let n=0;n<10;n++)await f.tick();
  assert.equal(f.applied.length,1);assert.ok(Math.max(...f.delays)<=8000);
});
test('late response from an old selection cannot mutate a reselected session',async()=>{
  let finish;const f=setup(()=>new Promise(resolve=>finish=resolve));f.sync();
  f.select('b',2);f.sync([]);f.select('a',3);f.sync([]);
  finish({events:[{type:'user',run_id:'run',content:'stale'}]});await flush();
  assert.equal(f.applied.length,0);assert.equal(f.timers.size,0);
});
test('live user arrival, hidden view and disposal cancel scheduled retries',async()=>{
  const f=setup(async()=>({events:[]}));f.sync();await flush();assert.equal(f.timers.size,1);
  f.sync([{...missing,hasUserMessage:true}]);assert.equal(f.timers.size,0);
  f.sync();await flush();f.sync([missing],{enabled:false});assert.equal(f.timers.size,0);
  f.sync();await flush();f.backfill.dispose();assert.equal(f.timers.size,0);
});
test('recovered run sharing a user-bearing process group does not invent a user',async()=>{
  let reads=0;const f=setup(async()=>{reads++;return {events:[]};});
  f.sync([{runId:'original',processGroupId:'turn:1',hasUserMessage:true},{...missing,processGroupId:'turn:1'}]);
  await flush();assert.equal(reads,0);
});
