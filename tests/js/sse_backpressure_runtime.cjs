const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.resolve(__dirname,'../../frontend/src/app/modules/sse-handling.js'),'utf8');
const fn=source.slice(source.indexOf('async function consumeAgentSseResponseInner('),source.indexOf('\nfunction latestVisibleUserEventIndex('));
let now=0,yields=0,inSlice=0,maxSlice=0;
const ordered=new Map();
const context=vm.createContext({console,TextDecoder,Date:{now:()=>now},SSE_IDLE_TIMEOUT_MS:30000,
  setTimeout(resolve){yields++;return setTimeout(()=>{maxSlice=Math.max(maxSlice,inSlice);inSlice=0;resolve();},0);},
  sessionStore:{shouldAcceptSseEvent:()=>true},
  consumeExtensionControlEvent:()=>false,shouldSkipRecoveredEphemeralEvent:()=>false,
  shouldApplySseSeqFilter:()=>false,
  readSseChunkWithIdleTimeout:r=>r.read(), updateExecutionRecord:(_sid,event)=>event,
  renderExecutionRecord(_ctx,event,sid){now+=5;inSlice++;ordered.get(sid).push(event.id);},
  scheduleFinalVisibleAfterRunIfEnabled(){},
});
vm.runInContext(fn,context);
const text=new TextEncoder();
function response(sid){
  let read=false;ordered.set(sid,[]);
  const data=Array.from({length:100},(_,id)=>'data: '+JSON.stringify({type:'execution_update',session_id:sid,update:{id}})+'\n').join('');
  return {ok:true,headers:{get:()=> 'text/event-stream'},body:{getReader:()=>({read:async()=>{
    if(read)return {done:true};read=true;return {done:false,value:text.encode(data)};
  }})}};
}
(async()=>{
  await Promise.all(['a','b','c','d'].map(sid=>context.consumeAgentSseResponseInner(response(sid),null,sid,0)));
  for(const events of ordered.values())assert.deepEqual(events,Array.from({length:100},(_,i)=>i));
  assert(yields>50,'burst streaming yields across multiple sessions');
  assert(maxSlice<=3,'a stream burst cannot monopolize input behind hundreds of costly events');
  console.log('4 concurrent streams, 400 ordered events, bounded render slices passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
