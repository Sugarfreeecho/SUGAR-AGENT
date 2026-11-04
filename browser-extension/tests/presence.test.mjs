import test from 'node:test';
import assert from 'node:assert/strict';
import {createPresenceBridge,installSidepanelPresence} from '../src/presence.mjs';

const report={type:'ui.presence',windowId:7,visible:true,focused:true};
function fixture(readWindow=async()=>({focused:true})){
  const sent=[],probes=[];let count=0;
  const bridge=createPresenceBridge({send:value=>sent.push(value),readWindow,id:()=>String(++count)});
  const port={postMessage:value=>probes.push(value)};bridge.attach(port);return{bridge,port,sent,probes};
}
test('only a focused visible sidebar in its focused browser window suppresses notifications',async()=>{
  const f=fixture();await f.bridge.report(f.port,report);assert.equal(f.sent.at(-1).active,true);
  for(const change of [{visible:false},{focused:false},{windowId:null}]){await f.bridge.report(f.port,{...report,...change});assert.equal(f.sent.at(-1).active,false);}
  const unfocused=fixture(async()=>({focused:false}));await unfocused.bridge.report(unfocused.port,report);assert.equal(unfocused.sent.at(-1).active,false);
});
test('late window checks cannot override a newer blur or window switch',async()=>{
  let release;const f=fixture(()=>new Promise(resolve=>release=resolve));
  let pending=f.bridge.report(f.port,report);await f.bridge.report(f.port,{...report,focused:false});release({focused:true});await pending;assert.equal(f.sent.at(-1).active,false);
  pending=f.bridge.report(f.port,report);f.bridge.focusChanged(-1);release({focused:true});await pending;assert.equal(f.sent.at(-1).active,false);
});
test('port closure clears its lease and reconnect asks live documents for fresh evidence',async()=>{
  let release;const f=fixture(()=>new Promise(resolve=>release=resolve));
  const pending=f.bridge.report(f.port,report);f.bridge.detach(f.port);release({focused:true});await pending;assert.equal(f.sent.at(-1).active,false);
  f.bridge.attach(f.port);const before=f.sent.length;f.bridge.ready();assert.equal(f.sent.length,before);assert.equal(f.probes.at(-1).type,'presence.probe');
});
test('multiple sidebars have separate identities and window refocus probes only its own surface',async()=>{
  const f=fixture(),other={postMessage:message=>f.probes.push({...message,other:true})};f.bridge.attach(other);
  await f.bridge.report(f.port,report);await f.bridge.report(other,{...report,windowId:8});assert.notEqual(f.sent[0].id,f.sent[1].id);
  f.bridge.focusChanged(7);assert.equal(f.sent.at(-1).active,false);assert.equal(f.probes.length,1);assert.equal(f.probes[0].other,undefined);
});
test('sidebar focus, visibility, heartbeat and unload report through its trusted port',async()=>{
  const document=new EventTarget(),window=new EventTarget(),sent=[],listeners=new Set();let focused=true,tick,cleared=false;
  document.visibilityState='visible';document.hasFocus=()=>focused;
  const port={postMessage:value=>sent.push(value),onMessage:{addListener:fn=>listeners.add(fn),removeListener:fn=>listeners.delete(fn)}};
  const stop=installSidepanelPresence(port,{document,window,readWindow:async()=>({id:7}),setInterval:fn=>{tick=fn;return 1;},clearInterval:()=>{cleared=true;}});
  await new Promise(resolve=>setImmediate(resolve));assert.equal(sent.at(-1).focused,true);assert.equal(sent.at(-1).windowId,7);
  window.dispatchEvent(new Event('blur'));tick();assert.equal(sent.at(-1).focused,false,'A delayed hasFocus value must not renew a blurred surface');
  focused=false;window.dispatchEvent(new Event('blur'));assert.equal(sent.at(-1).focused,false);
  focused=true;window.dispatchEvent(new Event('focus'));assert.equal(sent.at(-1).focused,true);
  document.visibilityState='hidden';document.dispatchEvent(new Event('visibilitychange'));assert.equal(sent.at(-1).visible,false);
  document.visibilityState='visible';tick();assert.equal(sent.at(-1).visible,true);
  window.dispatchEvent(new Event('pagehide'));assert.equal(sent.at(-1).focused,false);
  stop();assert.equal(cleared,true);assert.equal(listeners.size,0);const count=sent.length;window.dispatchEvent(new Event('focus'));assert.equal(sent.length,count);
});
