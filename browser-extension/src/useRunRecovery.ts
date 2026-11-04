import {useEffect,useRef} from 'react';
import {rpc} from './api';
import {activeRunTurn} from './run-outcome.mjs';
import {recoverStoppedRun} from './run-recovery.mjs';
import {createStreamWatch} from './stream-watch.mjs';
import {noteFrame} from './stream-diagnostics.mjs';

export function useRunRecovery(timeline:any,enabled:boolean,setTimeline:(update:(state:any)=>any)=>void,onError:(message:string)=>void,onRecover:(sessionId:string)=>Promise<void>){
  const latest=useRef(timeline);latest.current=timeline;
  const watch=useRef(createStreamWatch()),recover=useRef(onRecover);recover.current=onRecover;
  const sessionId=timeline.sessionId || '';
  useEffect(()=>{
    if(!enabled || !sessionId)return;
    let cancelled=false,timer:ReturnType<typeof setTimeout>,idleOwner:any=null,failures=0;
    async function check(){
      try{
        const observed=activeRunTurn(latest.current);
        const info=await rpc('session.get',{session_id:sessionId,include_runtime:true});
        if(cancelled)return;
        if(info.session?.id===sessionId && info.session.stream_active===true){
          idleOwner=null;
          const witness=watch.current.witness(sessionId);
          if(witness){
            const head=await rpc('session.history',{session_id:sessionId,limit:1});
            if(!cancelled && watch.current.behind(witness,head)){
              noteFrame('recovery_triggered',sessionId,{type:'stream_recovery'},{reason:'durable_cursor_advanced',observed_cursor:witness.seq,head_cursor:head.last_runtime_seq});
              await recover.current(sessionId);
            }
          }
        }
        else if(!observed?.runId || info.session?.id!==sessionId || info.session.stream_active!==false || activeRunTurn(latest.current)!==observed){idleOwner=null;}
        else if(idleOwner!==observed)idleOwner=observed;
        else {
          const history=await rpc('session.history',{session_id:sessionId,turns:15});
          const confirmed=await rpc('session.get',{session_id:sessionId,include_runtime:true});
          if(!cancelled && confirmed.session?.id===sessionId && confirmed.session.stream_active===false){
            setTimeline(state=>recoverStoppedRun(state,history.events || [],observed,sessionId));
          }
          idleOwner=null;
        }
        failures=0;
      }catch(error){if(!cancelled && ++failures===3)onError('无法核对会话执行状态：'+(error as Error).message);}
      if(!cancelled)timer=setTimeout(check,3000);
    }
    timer=setTimeout(check,3000);
    return()=>{cancelled=true;clearTimeout(timer);};
  },[sessionId,enabled,setTimeline,onError]);
  return watch.current;
}
