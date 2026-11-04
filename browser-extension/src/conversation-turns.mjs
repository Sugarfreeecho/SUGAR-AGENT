// A runtime run can contain several official user turns (the main UI queue).
// Keep run ownership separate from the identity of each visible exchange.
export const turnKey=turn=>turn.renderKey || turn.runId || turn.id;
export const userIdentity=event=>String(event.operation_id || (event.queued_followup && event.steer_id) || event.turn_id || (event.runtime_seq!=null?'seq:'+event.runtime_seq:'') || '');
export function matchesUser(turn,event){
  const id=userIdentity(event);
  return !!(id && turn.userIdentity===id || event.runtime_seq!=null && turn.userSeq===event.runtime_seq
    || event.turn_id && turn.userTurnId===event.turn_id
    || event.runtime_seq!=null && turn.processGroupId==='turn:'+event.runtime_seq);
}
export function findConversationTurn(turns,incoming){
  const candidates=turns.filter(turn=>turn.runId===incoming.runId);
  const exact=candidates.find(turn=>turnKey(turn)===turnKey(incoming)
    && (!turn.userIdentity || !incoming.userIdentity || turn.userIdentity===incoming.userIdentity)
    && (turn.userSeq==null || incoming.userSeq==null || turn.userSeq===incoming.userSeq));
  return candidates.find(turn=>turn.userIdentity && turn.userIdentity===incoming.userIdentity
    || turn.userSeq!=null && turn.userSeq===incoming.userSeq
    || turn.processGroupId && turn.processGroupId===incoming.processGroupId) || exact
    || (candidates.length===1 && !candidates[0].userIdentity && !incoming.userIdentity ? candidates[0] : undefined);
}
export function eventTurn(turns,event,run){
  const candidates=turns.filter(turn=>turn.runId===run),last=candidates.at(-1);
  if(event.type==='user')return candidates.find(turn=>matchesUser(turn,event))
    || (event.runtime_seq!=null?candidates.find(turn=>turn.processGroupId==='turn:'+event.runtime_seq):undefined) || last;
  if(event.process_group_id){const match=candidates.find(turn=>turn.processGroupId===event.process_group_id);if(match)return match;}
  if(event.turn_id){const match=candidates.find(turn=>turn.userTurnId===event.turn_id || turn.userIdentity===event.turn_id);if(match)return match;}
  if(event.type==='final' && event.runtime_seq!=null){const match=candidates.find(turn=>turn.userSeq===event.runtime_seq || turn.processGroupId==='turn:'+event.runtime_seq);if(match)return match;}
  const call=event.tool_call_id || event.id;
  if(event.execution_id || call){const match=candidates.find(turn=>turn.process.some(block=>block.kind==='tool' &&
    (event.execution_id && block.executionId===event.execution_id || call && block.toolCallId===call)));if(match)return match;}
  const phase=event.react_iter ?? event.step ?? event.iteration;
  if(phase!=null){const match=candidates.findLast(turn=>turn.process.some(block=>block.phase===String(phase)) || turn.bodyPhase===String(phase));if(match)return match;}
  return last;
}
export function humanTurnKey(record,turns){
  const candidates=turns.filter(turn=>turn.runId===record.run_id);
  const group=record.process_group_id;
  let owner=group && candidates.find(turn=>turn.processGroupId===group);
  const created=Date.parse(record.created_at || '');
  if(!owner && Number.isFinite(created) && candidates.every(turn=>Number.isFinite(Date.parse(turn.userCreatedAt))))owner=candidates.findLast(turn=>Date.parse(turn.userCreatedAt)<=created);
  return turnKey(owner || candidates.at(-1) || {});
}
