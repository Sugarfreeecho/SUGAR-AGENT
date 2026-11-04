import {applyTimeline} from './timeline.mjs';
import {eventKey} from './shared.mjs';
import {activeRunTurn} from './run-outcome.mjs';

// The caller confirms inactivity twice and again after reading history. Keep
// this conditional on the same immutable turn so a late HTTP read cannot end
// a newer run or overwrite live progress that arrived during recovery.
export function recoverStoppedRun(state,events,owner,sessionId){
  if(state.sessionId!==sessionId || !owner?.runId || activeRunTurn(state)!==owner)return state;
  let next=state;
  for(const event of events){
    if(event.run_id===owner.runId){
      // A history terminal may already be in seen while an older runtime read
      // still claimed activity. Reapply its idempotent state to clear that flag.
      const terminal=['run_finished','run_failed','run_interrupted'].includes(event.type);
      next=applyTimeline(next,event,terminal?null:eventKey(event,sessionId),{history:true});
    }
  }
  if(activeRunTurn(next)?.runId===owner.runId){
    next=applyTimeline(next,{type:'run_finished',run_id:owner.runId,result_status:'unknown',replayed_snapshot:true},null,{history:true});
  }
  return next;
}
