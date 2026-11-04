const labels = {
  generating:'正在生成',pending:'等待执行',queued:'排队中',running:'执行中',waiting_input:'等待输入',waiting_approval:'等待审批',
  completed:'已完成',failed:'执行失败',timed_out:'已超时',interrupted:'已停止',cancelled:'已取消',
  denied:'已拒绝',blocked:'已拦截',skipped:'已跳过',not_executed:'未执行',unknown:'状态未知',
};
const aliases={succeeded:'completed',success:'completed',done:'completed',error:'failed',timeout:'timed_out',canceled:'cancelled',rejected:'denied',executing:'running',waiting:'pending',waiting_execution:'pending',requires_approval:'waiting_approval'};
const activeCodes=new Set(['generating','pending','queued','running','waiting_input','waiting_approval']);
export function processStatus(event,previous='') {
  const raw=[event.execution_status,event.state,event.status].find(value=>typeof value==='string' && value);
  let code=raw ? labels[raw] ? raw : aliases[raw] || Object.keys(labels).find(key=>labels[key]===raw) || 'unknown' : '';
  const status=event.status && typeof event.status==='object' ? event.status : event.tool_status || {};
  if(status.timed_out)code='timed_out';
  else if(status.ok===false && !['denied','blocked','interrupted','cancelled','not_executed'].includes(code))code='failed';
  else if(!code && status.ok===true)code='completed';
  if(!code)code=event.type==='tool_call' ? 'completed' : event.type==='tool_pending' ? 'pending' : previous || 'unknown';
  if(previous && previous!=='unknown' && !activeCodes.has(previous) && activeCodes.has(code))code=previous;
  if(code==='generating' && previous && previous!=='generating')code=previous;
  return {code,label:labels[code],active:activeCodes.has(code)};
}
const finite=value=>value!==undefined && value!==null && value!=='' && Number.isFinite(Number(value)) && Number(value)>=0 ? Number(value) : null;
function timestamp(value) {
  const number=finite(value);
  if(number!==null)return number<1e12 ? number*1000 : number;
  const parsed=typeof value==='string' ? Date.parse(value) : NaN;
  return Number.isFinite(parsed) ? parsed : null;
}
export function updateProcessTiming(block,event,active,{history=false,now=Date.now()}={}) {
  const started=timestamp(event.started_at),finished=timestamp(event.finished_at);
  const duration=finite(event.duration_ms ?? event.status?.duration_ms ?? event.tool_status?.duration_ms);
  if(started!==null)block.startedAt=started;
  if(active) {
    if(block.startedAt==null && !history)block.startedAt=now;
    block.timingActive=true;
    return;
  }
  if(duration!==null)block.durationMs=duration;
  if(finished!==null)block.endedAt=finished;
  else if(block.timingActive && block.endedAt==null && !history)block.endedAt=now;
  if(duration===null && block.durationMs==null && block.startedAt!=null && block.endedAt!=null)block.durationMs=Math.max(0,block.endedAt-block.startedAt);
  block.timingActive=false;
}
export function elapsedMilliseconds(block,now=Date.now()) {
  if(block.timingActive && block.startedAt!=null)return Math.max(0,now-block.startedAt);
  if(block.durationMs!=null)return block.durationMs;
  if(block.startedAt!=null && block.endedAt!=null)return Math.max(0,block.endedAt-block.startedAt);
  return null;
}
export function formatElapsed(milliseconds) {
  if(milliseconds===null || !Number.isFinite(milliseconds))return '—';
  const seconds=Math.max(0,milliseconds)/1000;
  if(seconds<60)return seconds.toFixed(1)+'s';
  if(seconds<3600)return Math.floor(seconds/60)+'m '+String(Math.floor(seconds%60)).padStart(2,'0')+'s';
  return Math.floor(seconds/3600)+'h '+String(Math.floor(seconds/60)%60).padStart(2,'0')+'m';
}
