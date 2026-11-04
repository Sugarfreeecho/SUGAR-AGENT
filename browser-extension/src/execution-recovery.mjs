import {toolSnapshotEvent} from './tool-stream.mjs';

export function executionSnapshotEvent(row){
  if(row.kind==='tool')return toolSnapshotEvent(row);
  if(!['reasoning','response'].includes(row.kind) || row.ui_committed)return null;
  const base=row.kind==='reasoning'?'llm_reasoning':'llm_response';
  const active=row.status==='generating';
  return {...row,type:base+(active?'_delta':''),content:row.content || '',delta:row.content || '',
    delta_seq:row['last_'+base+'_delta_delta_seq'] ?? row['last_'+base+'_delta_seq'],
    execution_runtime_seq:row.last_runtime_seq,replayed_snapshot:true};
}

// Replayed cumulative chunks replace partial text; counters fence late fragments
// that were already included by the durable recovery read.
export function acceptLlmFrame(turn,event,kind){
  const key=kind+':'+(event.execution_id || `${event.stream_seq ?? ''}:${event.react_iter ?? event.step ?? event.iteration ?? ''}`);
  const prior=turn.llmCursors?.[key] || {},seq=Number(event.delta_seq),execution=Number(event.execution_runtime_seq);
  if(Number.isFinite(execution) && execution<Number(prior.execution || 0))return false;
  if(event.type.endsWith('_delta') && !event.replayed_snapshot && Number.isFinite(seq) && seq<=Number(prior.delta || 0))return false;
  turn.llmCursors={...turn.llmCursors,[key]:{delta:Number.isFinite(seq)?Math.max(seq,prior.delta || 0):prior.delta,
    execution:Number.isFinite(execution)?Math.max(execution,prior.execution || 0):prior.execution}};
  return true;
}
