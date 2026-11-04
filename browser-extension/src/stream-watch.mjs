const progress=type=>/^(user$|user_steer$|run_|llm_|tool_|error$|warning$|context_trim_|context_summary_)/.test(type || '');
const cursor=page=>Math.max(Number(page?.last_runtime_seq)||0,...(page?.events || []).map(event=>Number(event.execution_runtime_seq || event.runtime_seq)||0));
export function createStreamWatch({now=()=>Date.now(),quietMs=12000}={}){
  let state={sessionId:'',seq:0,version:0,lastFrame:now(),nextProbe:0};
  function snapshot(sessionId,page){state={sessionId,seq:cursor(page),version:state.version+1,lastFrame:now(),nextProbe:0};}
  function event(sessionId,event){
    if(!sessionId || !progress(event.type) || event.replayed_recent || event.replayed_snapshot)return;
    if(state.sessionId!==sessionId)snapshot(sessionId,{});
    state={...state,seq:Math.max(state.seq,Number(event.execution_runtime_seq || event.runtime_seq)||0),lastFrame:now(),version:state.version+1};
  }
  function witness(sessionId){return state.sessionId===sessionId && now()-state.lastFrame>=quietMs && now()>=state.nextProbe?{...state}:null;}
  function behind(observed,page){
    if(!observed || observed.sessionId!==state.sessionId || observed.version!==state.version)return false;
    state={...state,nextProbe:now()+quietMs};
    return cursor(page)>state.seq;
  }
  function restored(sessionId,events){
    if(state.sessionId!==sessionId)return;
    const seq=cursor({events});
    if(seq>state.seq)state={...state,seq,version:state.version+1,lastFrame:now()};
  }
  return {snapshot,event,witness,behind,restored};
}
