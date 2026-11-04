import {turnKey} from './conversation-turns.mjs';
import {isSessionChatEvent} from './session-scope.mjs';
// One in-flight read per missing user turn. Empty snapshots and transient failures
// retry on a timer, independent of streaming render frequency.
export function createUserBackfill({read,apply,isCurrent,setTimer=setTimeout,clearTimer=clearTimeout,baseDelay=300,maxDelay=8000}){
  let boundary='',generation=0;const entries=new Map();
  function cancel(){++generation;for(const entry of entries.values())clearTimer(entry.timer);entries.clear();boundary='';}
  function valid(entry){return entry.generation===generation && entries.get(entry.key)===entry && isCurrent(entry.sessionId,entry.epoch);}
  async function attempt(entry){
    if(!valid(entry) || entry.inFlight)return;
    entry.inFlight=true;entry.timer=undefined;
    try{
      const result=await read(entry.sessionId,entry.runId);
      if(!valid(entry))return;
      const facts=(result.events || []).filter(event=>isSessionChatEvent(event,entry.sessionId) && event.type==='user' && String(event.run_id || event.turn_id || '')===entry.runId);
      const fact=entry.groupId?.startsWith('turn:')?facts.find(event=>'turn:'+event.runtime_seq===entry.groupId):facts.at(-1);
      if(fact){entries.delete(entry.key);apply(fact,entry.sessionId,entry.epoch);return;}
    }catch{/* Retry while this selected view still needs the fact. */}
    finally{entry.inFlight=false;}
    if(valid(entry)){
      const delay=Math.min(maxDelay,baseDelay*2**Math.min(entry.attempts++,8));
      entry.timer=setTimer(()=>void attempt(entry),delay);
    }
  }
  function sync({sessionId,epoch,turns,enabled=true}){
    const next=sessionId+':'+epoch;
    if(!enabled || !sessionId){cancel();return;}
    if(boundary!==next){cancel();boundary=next;}
    const last=turns.at(-1),missing=turns.filter(turn=>(turn===last || turn.status==='running') && !turn.hasUserMessage && (turn.pendingUser || !turn.user && !turn.images?.length) && turn.runId
      && !(turn.processGroupId && turns.some(other=>other!==turn && other.processGroupId===turn.processGroupId && (other.hasUserMessage || other.user && !other.pendingUser))));
    const wanted=new Set(missing.map(turnKey));
    for(const [id,entry] of entries)if(!wanted.has(id)){clearTimer(entry.timer);entries.delete(id);}
    for(const turn of missing){
      const key=turnKey(turn),existing=entries.get(key);
      if(existing){existing.groupId=turn.processGroupId;continue;}
      const entry={sessionId,epoch,key,groupId:turn.processGroupId,runId:turn.runId,generation,inFlight:false,attempts:0,timer:undefined};
      entries.set(key,entry);void attempt(entry);
    }
  }
  return {sync,cancel,dispose:cancel};
}
