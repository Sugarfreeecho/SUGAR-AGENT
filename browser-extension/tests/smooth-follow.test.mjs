import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {mainFollowModuleSource} from '../scripts/main-smooth-follow.mjs';

const source=(await mainFollowModuleSource()).replace(/export \{[^}]+\};\s*$/,'globalThis.api={createSmoothFollowController,computeSmoothFollowSpringStep,SMOOTH_STREAM_CONFIG};');
function fixture(reduced=false){
  let now=0,id=0;const frames=new Map(),listeners={},attrs=new Map();
  const context=vm.createContext({matchMedia:()=>({matches:reduced}),performance:{now:()=>now},setTimeout:()=>1,clearTimeout(){},
    requestAnimationFrame(fn){frames.set(++id,fn);return id;},cancelAnimationFrame(key){frames.delete(key);}});
  vm.runInContext(source,context);const controller=context.api.createSmoothFollowController();
  let top=0;
  const node={isConnected:true,get scrollTop(){return top;},set scrollTop(value){top=Math.max(0,Math.min(value,this.scrollHeight-this.clientHeight));},scrollHeight:1000,clientHeight:200,style:{},
    addEventListener(type,fn){listeners[type]=fn;},setAttribute(key,value){attrs.set(key,value);},removeAttribute(key){attrs.delete(key);}};
  return {controller,node,listeners,frames,api:context.api,frame(){now+=16.67;const pending=[...frames.values()];frames.clear();pending.forEach(fn=>fn(now));}};
}
test('extension imports the main UI spring and keeps velocity continuous during retargeting',()=>{
  const f=fixture();assert.equal(f.api.SMOOTH_STREAM_CONFIG.followStiffness,180);
  f.controller.request(f.node);f.frame();assert.ok(f.node.scrollTop>0 && f.node.scrollTop<=3);
  let previous=f.node.scrollTop;
  for(let i=0;i<180;i++){
    if(i<20){f.node.scrollHeight+=5;f.controller.request(f.node);}
    f.frame();assert.ok(f.node.scrollTop>=previous && f.node.scrollTop-previous<=20.001);previous=f.node.scrollTop;
  }
  assert.ok(Math.abs(f.node.scrollTop-(f.node.scrollHeight-f.node.clientHeight))<.25);
  f.controller.cancel(f.node);assert.equal(f.frames.size,0);
});
test('intentional upward gesture releases follow even near the bottom until explicitly resumed',()=>{
  const f=fixture();f.node.scrollTop=780;f.controller.request(f.node);f.frame();
  f.listeners.wheel({deltaY:-8});f.controller.request(f.node);
  assert.equal(f.controller.isFollowing(f.node),false);assert.equal(f.controller.isReaderDetached(f.node),true);
  assert.equal(f.controller.snapToBottom(f.node),false);
  f.controller.clearReaderDetached(f.node);f.controller.request(f.node);assert.equal(f.controller.isFollowing(f.node),true);
});
test('pointer, keyboard and touch readers can release the shared follower',()=>{
  for(const gesture of ['pointer','keyboard','touch']){
    const f=fixture();f.node.scrollTop=700;f.controller.request(f.node);f.frame();
    if(gesture==='pointer'){f.listeners.pointerdown();f.node.scrollTop-=10;f.listeners.scroll();}
    if(gesture==='keyboard')f.listeners.keydown({key:'PageUp'});
    if(gesture==='touch'){f.listeners.touchstart({touches:[{clientY:100}]});f.listeners.touchmove({touches:[{clientY:112}]});}
    assert.equal(f.controller.isReaderDetached(f.node),true,gesture);
  }
});
test('layout shrink, session reset and disconnected viewports do not leave old scroll animations',()=>{
  const f=fixture();f.controller.request(f.node);for(let i=0;i<20;i++)f.frame();
  f.node.scrollHeight=250;f.frame();assert.ok(f.node.scrollTop<=50);
  f.controller.reset(f.node);assert.equal(f.frames.size,0);assert.equal(f.controller.isReaderDetached(f.node),false);
  f.controller.request(f.node);f.node.isConnected=false;f.frame();assert.equal(f.frames.size,0);
});
test('reduced motion follows immediately without scheduling an animation loop',()=>{
  const f=fixture(true);f.controller.request(f.node);assert.equal(f.node.scrollTop,800);assert.equal(f.frames.size,0);
});
