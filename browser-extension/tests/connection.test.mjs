import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
import {loopbackUrl,ordinaryTab} from '../src/shared.mjs';
import {controlResult} from '../src/control.mjs';
import {applicationMethod} from '../src/application-api.mjs';
import {verifyPairing,isCurrentConnection} from '../src/connection.mjs';
test('a delayed state reply cannot roll back newer live connection status; a fresh worker has its own revision',()=>{
  assert.equal(isCurrentConnection({generation:'old',revision:4},{generation:'old',revision:2}),false);
  assert.equal(isCurrentConnection({generation:'old',revision:4},{generation:'old',revision:4}),true);
  assert.equal(isCurrentConnection({generation:'old',revision:4},{generation:'new',revision:1}),true);
});
const source=ts.transpileModule(await readFile(new URL('../src/background.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const original={baseUrl:'http://127.0.0.1:8192',token:'saved-credential',browserId:'saved-browser'};
const flush=async()=>{for(let i=0;i<12;i++)await new Promise(resolve=>setImmediate(resolve));};
function fixture({delayed=false,stored={...original}}={}){
  const timers=new Set(),intervals=[],requests=[],messages=[],alarms=new Set();
  let clock=0,releaseRead,probeStatus=200,claimStatus=200,probeGate;
  const event=()=>({listeners:[],addListener(fn){this.listeners.push(fn);}});
  const data={'sugar.connection':stored},session={};
  const area=values=>({async get(key){if(delayed && values===data)await new Promise(resolve=>releaseRead=resolve);return typeof key==='string'?{[key]:structuredClone(values[key])}:structuredClone(values);},async set(items){Object.assign(values,structuredClone(items));},async remove(key){delete values[key];},async setAccessLevel(){}});
  const chrome={storage:{local:area(data),session:area(session)},runtime:{id:'fixture',getURL:path=>'chrome-extension://fixture/'+path,onMessage:event(),onConnect:event(),onInstalled:event()},
    action:{async setBadgeText(){}},alarms:{async create(name){alarms.add(name);},async clear(name){alarms.delete(name);},onAlarm:event()},
    tabs:{async query(){return[];},onCreated:event(),onUpdated:event(),onRemoved:event()},windows:{onFocusChanged:event()},debugger:{async detach(){}},
    sidePanel:{async setPanelBehavior(){}},contextMenus:{removeAll(fn){fn();},create(){},onClicked:event()},commands:{onCommand:event()}};
  class Socket{
    static CONNECTING=0;static OPEN=1;static instances=[];
    constructor(url){this.url=url;this.readyState=0;this.sent=[];Socket.instances.push(this);}
    open(){this.readyState=1;this.onopen?.();}
    receive(value){this.onmessage?.({data:JSON.stringify(value)});}
    send(value){this.sent.push(JSON.parse(value));}
    async close(code=1000){this.readyState=3;await this.onclose?.({code});}
  }
  async function request(url,options){requests.push({url,options});const claim=url.endsWith('/claim');if(!claim && probeGate)await probeGate;
    const status=claim?claimStatus:probeStatus;return{status,ok:status===200,async json(){return status!==200 ? {detail:'fixture failure'} : claim?{token:'new-credential',browser_id:'new-browser'}:{paired:true,browser_id:original.browserId};}};}
  const imports={'./upstream/relayConnection':{RelayConnection:class{}},'./shared.mjs':{loopbackUrl,ordinaryTab},'./control.mjs':{controlResult},'./application-api.mjs':{applicationMethod},'./browser-context':{readBrowserContext:async()=>({})},'./presence.mjs':{createPresenceBridge:()=>({ready(){},attach(){},detach(){},report(){},focusChanged(){}})},'./connection.mjs':{verifyPairing:connection=>verifyPairing(connection,request)}};
  const context={exports:{},require:name=>imports[name],chrome,WebSocket:Socket,fetch:request,URL,crypto:globalThis.crypto,Date:class extends Date{static now(){return clock;}},
    setTimeout(fn,ms){const timer={fn,ms};timers.add(timer);return timer;},clearTimeout(timer){timers.delete(timer);},setInterval(fn){intervals.push(fn);return intervals.length;},clearInterval(){}};
  new vm.Script(source).runInNewContext(context);
  async function message(value){return new Promise(resolve=>chrome.runtime.onMessage.listeners[0](value,{id:'fixture',url:'chrome-extension://fixture/sidepanel.html'},resolve));}
  const port={sender:{id:'fixture',url:'chrome-extension://fixture/sidepanel.html'},name:'fixture',postMessage:value=>messages.push(value),onDisconnect:event(),onMessage:event()};
  chrome.runtime.onConnect.listeners[0](port);
  return{data,alarms,requests,Socket,timers,messages,intervals,message,async state(){return(await message({type:'state'})).result;},release(){delayed=false;releaseRead?.();},setProbe(status){probeStatus=status;},setClaim(status){claimStatus=status;},holdProbe(){let release;probeGate=new Promise(resolve=>release=resolve);return()=>{probeGate=null;release();};},advance(ms){clock+=ms;},async ready(){await flush();const socket=Socket.instances.at(-1);socket.open();socket.receive({type:'ready'});await flush();return socket;},async retry(){const timer=[...timers].find(item=>item.ms<=30000 && item.ms!==10000);assert.ok(timer,'Reconnect was not scheduled');timers.delete(timer);timer.fn();await flush();return Socket.instances.at(-1);}};
}
test('worker wake waits for persistent credentials before answering the sidebar',async()=>{
  const f=fixture({delayed:true});let answered=false;const pending=f.state().then(value=>{answered=true;return value;});await flush();assert.equal(answered,false);assert.equal(f.Socket.instances.length,0);
  f.release();await flush();assert.equal((await pending).paired,true);assert.ok(f.messages.every(row=>row.status!=='unpaired'));
  const socket=await f.ready();assert.equal(socket.sent[0].token,original.token);
});
test('temporary disconnect and worker restart retain the pairing and reconnect automatically',async()=>{
  const f=fixture();const first=await f.ready();await first.close(1006);assert.equal((await f.state()).paired,true);assert.deepEqual(f.data['sugar.connection'],original);
  const next=await f.retry();next.open();next.receive({type:'ready'});assert.equal(next.sent[0].token,original.token);assert.equal((await f.state()).status,'connected');
  const restarted=fixture({stored:f.data['sugar.connection']});await restarted.ready();assert.equal((await restarted.state()).paired,true);
});
test('4401 is confirmed over HTTP and a host error never clears saved credentials',async()=>{
  for(const httpStatus of [200,503]){
    const f=fixture();const socket=await f.ready();f.setProbe(httpStatus);await socket.close(4401);
    assert.equal((await f.state()).status,'disconnected');assert.deepEqual(f.data['sugar.connection'],original);await f.retry();
  }
  const f=fixture();const socket=await f.ready();f.setProbe(401);await socket.close(4401);
  assert.equal((await f.state()).status,'auth-required');assert.equal((await f.state()).paired,true);assert.deepEqual(f.data['sugar.connection'],original);assert.equal(f.alarms.has('sugar-reconnect'),false);
});
test('disabled plugin preserves pairing and an invalid new pairing code preserves the old connection',async()=>{
  const f=fixture();const socket=await f.ready();f.setClaim(401);assert.equal((await f.message({type:'pair',code:'bad'})).ok,false);
  assert.equal((await f.state()).status,'connected');assert.deepEqual(f.data['sugar.connection'],original);
  await socket.close(4403);assert.equal((await f.state()).status,'disconnected');assert.equal((await f.state()).paired,true);await f.retry();
});
test('a late rejected socket or authentication probe cannot overwrite a newer successful pairing',async()=>{
  const f=fixture();const socket=await f.ready();f.setProbe(401);const release=f.holdProbe();const closing=socket.close(4401);
  assert.equal((await f.message({type:'pair',code:'new',baseUrl:original.baseUrl})).ok,true);release();await closing;
  const next=f.Socket.instances.at(-1);next.open();next.receive({type:'ready'});socket.receive({type:'ready'});await socket.close(4401);
  assert.equal((await f.state()).status,'connected');assert.equal(f.data['sugar.connection'].token,'new-credential');assert.equal(next.sent[0].token,'new-credential');
});
test('silent handshake and heartbeat stalls reconnect, while only explicit disconnect clears pairing',async()=>{
  const f=fixture();await flush();const first=f.Socket.instances[0];first.open();[...f.timers].find(timer=>timer.ms===10000).fn();await flush();assert.equal(first.readyState,3);await f.retry();
  const socket=await f.ready();f.advance(70000);f.intervals[0]();await flush();assert.equal(socket.readyState,3);assert.deepEqual(f.data['sugar.connection'],original);
  await f.message({type:'disconnect'});assert.equal(f.data['sugar.connection'],undefined);assert.equal((await f.state()).status,'unpaired');
});
