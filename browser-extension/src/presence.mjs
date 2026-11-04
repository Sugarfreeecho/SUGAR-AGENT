// Each open sidepanel owns a short focus lease. A connected worker alone is
// never evidence that the user is looking at the extension.
export function createPresenceBridge({send,readWindow,id=()=>crypto.randomUUID()}){
  const surfaces=new Map();
  const publish=(state,active)=>send({type:'ui.presence',id:state.id,active});
  return {
    attach(port){surfaces.set(port,{id:id(),revision:0,windowId:null});},
    async report(port,report){
      const state=surfaces.get(port);if(!state || report?.type!=='ui.presence')return;
      const revision=++state.revision;state.windowId=report.windowId;
      if(report.visible!==true || report.focused!==true || !Number.isInteger(report.windowId) || report.windowId<0){publish(state,false);return;}
      try{
        const window=await readWindow(report.windowId);
        if(surfaces.get(port)===state && state.revision===revision)publish(state,window.focused===true);
      }catch{if(surfaces.get(port)===state && state.revision===revision)publish(state,false);}
    },
    detach(port){const state=surfaces.get(port);if(state){surfaces.delete(port);publish(state,false);}},
    focusChanged(windowId){
      for(const [port,state] of surfaces){state.revision++;publish(state,false);if(windowId>=0 && state.windowId===windowId){try{port.postMessage({type:'presence.probe'});}catch{this.detach(port);}}}
    },
    ready(){for(const [port,state] of surfaces){state.revision++;try{port.postMessage({type:'presence.probe'});}catch{this.detach(port);}}},
  };
}

export function installSidepanelPresence(port,{document=globalThis.document,window=globalThis.window,readWindow=()=>chrome.windows.getCurrent(),setInterval=globalThis.setInterval,clearInterval=globalThis.clearInterval}={}){
  const lifetime=new AbortController();let disposed=false,windowId=null,reading=null,focused=document.hasFocus();
  const post=(visible,focused)=>{try{port.postMessage({type:'ui.presence',windowId,visible,focused});}catch{/* Disconnect releases the worker-owned lease. */}};
  const report=()=>{
    if(disposed)return;
    const visible=document.visibilityState==='visible',active=focused && document.hasFocus();
    if(!visible || !active){post(visible,active);return;}
    if(windowId!==null){post(visible,active);return;}
    if(!reading)reading=readWindow().then(value=>{if(Number.isInteger(value.id))windowId=value.id;}).catch(()=>{}).finally(()=>{reading=null;if(!disposed && windowId!==null)report();});
  };
  const hidden=()=>{focused=false;post(false,false);};
  const focus=()=>{focused=true;report();};
  window.addEventListener('focus',focus,{signal:lifetime.signal});
  window.addEventListener('blur',()=>{focused=false;post(document.visibilityState==='visible',false);},{signal:lifetime.signal});
  window.addEventListener('pageshow',()=>{focused=document.hasFocus();report();},{signal:lifetime.signal});
  window.addEventListener('pagehide',hidden,{signal:lifetime.signal});
  document.addEventListener('focusin',focus,{signal:lifetime.signal});
  document.addEventListener('visibilitychange',()=>{focused=document.hasFocus();report();},{signal:lifetime.signal});
  const probe=message=>{if(message.type==='presence.probe')report();};port.onMessage.addListener(probe);
  const timer=setInterval(report,10000);report();
  return ()=>{hidden();disposed=true;clearInterval(timer);lifetime.abort();port.onMessage.removeListener(probe);};
}
