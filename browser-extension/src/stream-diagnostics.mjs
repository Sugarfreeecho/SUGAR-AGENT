const rows=new Map();const limit=256;
const clean=value=>typeof value==='string'?value.slice(0,180):typeof value==='number' || typeof value==='boolean'?value:undefined;
const fields=['outcome','reason','status_before','status_after','observed_cursor','head_cursor','running_before','running_after','event_count'];
export function noteFrame(stage,sessionId,event={},extra={}){
  const identity=event.execution_id || event.tool_call_id || event.id || event.react_iter || '';
  const type=event.type || event.kind || '',key=[stage,sessionId,event.run_id,identity,type,extra.reason || ''].join(':');
  const at=Date.now(),previous=rows.get(key);
  const row={stage,session_id:clean(sessionId),type:clean(type),run_id:clean(event.run_id),execution_id:clean(event.execution_id),tool_call_id:clean(event.tool_call_id || event.id),react_iter:clean(event.react_iter),
    owner_session:clean(event.session_id || event.sessionId),agent_id:clean(event.agent_id),subagent_forward:!!event._subagent_forward,
    source:stage==='history_installed'?'history':stage==='execution_snapshot' || event.replayed_snapshot?'snapshot':stage==='recovery_triggered'?'control':event.replayed_recent?'cached':'live',
    first_at:previous?.first_at ?? at,last_at:at,count:(previous?.count || 0)+1,
    first_bus_seq:previous?.first_bus_seq ?? clean(event.event_bus_seq),bus_seq:clean(event.event_bus_seq),bus_epoch:clean(event.event_bus_epoch),
    runtime_seq:clean(event.execution_runtime_seq ?? event.runtime_seq ?? event.last_runtime_seq),server_created_at:clean(event.created_at),server_updated_at:clean(event.updated_at),server_started_at:clean(event.started_at),
    committed_at:previous?.committed_at};
  for(const field of fields)if(clean(extra[field])!==undefined)row[field]=clean(extra[field]);
  rows.delete(key);rows.set(key,row);while(rows.size>limit)rows.delete(rows.keys().next().value);
}
export function markCommitted(){const at=Date.now();for(const row of rows.values())if(row.stage==='reduced' && (row.committed_at || 0)<row.last_at)row.committed_at=at;}
export function streamTrace(sessionId=''){return [...rows.values()].filter(row=>!sessionId || row.session_id===sessionId).map(row=>({...row}));}
