const quietInterrupts=new Set(['process_restart','followup','superseded_by_new_run']);
const stoppedReasons=new Set(['manual_stop','control_stop','control_cancel','cancelled','canceled','user_stop']);
const text=value=>typeof value==='string'?value.trim():value && typeof value==='object'?text(value.message || value.detail || value.error || value.reason):'';

export function runOutcome(event){
  const type=event.type;
  const status=type==='run_interrupted'?'interrupted':type==='run_failed'?'failed':type==='run_finished'?(event.result_status==='failed'?'failed':event.result_status==='unknown'?'unknown':'succeeded'):null;
  if(status==='succeeded' || type==='run_interrupted' && quietInterrupts.has(event.reason))return {status,notice:null};
  if(!status && type!=='error')return {status,notice:null};
  let message=text(event.content) || text(event.error) || text(event.message),detail='',rich=false;
  if(message.startsWith('__ERR_CARD__')){
    try{
      const card=JSON.parse(message.slice('__ERR_CARD__'.length));
      message=[text(card.t),text(card.m)].filter(Boolean).join('：');
      detail=[text(card.s),text(card.d)].filter(Boolean).join('\n\n');rich=true;
    }catch{message='执行遇到问题';detail=text(event.error) || text(event.reason);}
  }
  let title=status==='interrupted'?'执行已中断':status==='unknown'?'执行状态未确认':'执行失败';
  if(status==='interrupted'){
    if(stoppedReasons.has(event.reason)){title='已停止';message ||= '当前任务已停止。';}
    else if(event.reason==='backend_shutdown')message ||= '后端已关闭，当前任务中断。';
    else message ||= text(event.reason) || '任务在完成前中断，未收到正常完成结果。';
  }else if(status==='unknown')message ||= '后端已停止执行，但未收到完成状态。';
  else message ||= text(event.reason) || '任务未能完成，后端未提供具体原因。';
  return {status,notice:{id:'run-outcome',kind:'error',title,content:message,detail,rich,outcome:status || 'failed'}};
}

export function activeRunTurn(state){
  return state.turns.findLast(turn=>turn.status==='running') || (state.running?state.turns.at(-1):null);
}
