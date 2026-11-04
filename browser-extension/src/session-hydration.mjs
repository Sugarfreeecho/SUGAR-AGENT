import {applyTimeline} from './timeline.mjs';
import {eventKey} from './shared.mjs';
export function replaySessionBuffer(state,events,owner,current){
  if(!owner || owner!==current)return state;
  return events.reduce((next,event)=>applyTimeline(next,event,eventKey(event,owner)),state);
}
