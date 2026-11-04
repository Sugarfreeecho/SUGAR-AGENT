// Presentation only. Canonical messages, delivery state and tool sequences are
// never delayed or modified by character playback.
import {turnKey} from './conversation-turns.mjs';
export function settleTimelineReveal(timeline){
  let changed=false;
  const turns=timeline.turns.map(turn=>{
    const process=turn.process.map(block=>block.reveal?{...block,reveal:false}:block);
    if(turn.bodyReveal || process.some((block,index)=>block!==turn.process[index])){
      changed=true;return {...turn,bodyReveal:false,process};
    }
    return turn;
  });
  return changed?{...timeline,turns}:timeline;
}

export function createTimelineReveal({computeSmoothRevealCount,takeSmoothTextPrefix}){
  const streams=new Map();
  let boundary,pending=false;
  function sync(timeline,options={}){
    const reset=boundary!==undefined && boundary!==options.boundary;
    if(reset)streams.clear();
    boundary=options.boundary;
    const present=new Set();pending=false;
    function text(key,target,animate){
      if(typeof target!=='string')return target;
      present.add(key);
      let entry=streams.get(key);
      if(reset || !animate || options.instant){
        if(!entry || entry.target!==target || entry.visible!==target)streams.set(key,{target,visible:target});
        return target;
      }
      if(!entry){
        // Preserve immediate first output while spreading the remaining chunk
        // over frames using exactly the main UI's adaptive Unicode algorithm.
        const first=takeSmoothTextPrefix(target,computeSmoothRevealCount(target.length,16.67)).segment;
        entry={target,visible:first};streams.set(key,entry);
      }else if(!target.startsWith(entry.target)){
        entry.target=target;entry.visible=target;
      }else entry.target=target;
      if(entry.visible!==target)pending=true;
      return entry.visible;
    }
    const turns=timeline.turns.map(turn=>{
      const key=turnKey(turn),live=turn.status==='running';
      const body=text(key+':body:'+turn.bodyPhase,turn.body,live && turn.bodyReveal);
      let changed=body!==turn.body;
      const process=turn.process.map(block=>{
        const active=live && block.reveal && (block.kind==='answer' || block.active);
        const fields=block.kind==='tool'?['argsText','commandText','outputText','stdoutText','stderrText','content']:['content'];
        let copy=block;
        for(const field of fields){
          const value=text(key+':'+block.id+':'+field,block[field],active);
          if(value!==block[field]){if(copy===block)copy={...block};copy[field]=value;}
        }
        if(copy!==block)changed=true;
        return copy;
      });
      return changed?{...turn,body,process}:turn;
    });
    for(const key of streams.keys())if(!present.has(key))streams.delete(key);
    return turns.every((turn,index)=>turn===timeline.turns[index])?timeline:{...timeline,turns};
  }
  function advance(dtMs){
    pending=false;
    for(const entry of streams.values()){
      const tail=entry.target.slice(entry.visible.length);
      const take=takeSmoothTextPrefix(tail,computeSmoothRevealCount(tail.length,Math.max(1,Math.min(120,dtMs))));
      entry.visible+=take.segment;
      if(take.rest)pending=true;
    }
  }
  return {sync,advance,get pending(){return pending;},clear(){streams.clear();pending=false;}};
}
