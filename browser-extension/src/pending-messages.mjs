export function mergePendingMessages(previous,items){
  return [...items,...previous.filter(row=>(row.status==='sending' || row.recovery) && !items.some(item=>item.clientId===row.clientId || row.operationId && item.operationId===row.operationId))];
}
export function reconcilePendingTurns(state,items){
  let changed=false;
  const turns=state.turns.map(turn=>{
    const item=items.find(item=>item.runId && item.runId===turn.runId && !item.recovery);
    if(!item || turn.hasUserMessage || turn.user || turn.pendingUser || state.turns.some(other=>other!==turn && other.runId===turn.runId && other.hasUserMessage))return turn;
    changed=true;return {...turn,user:item.content,images:item.images || [],pendingUser:true};
  });
  return changed?{...state,turns}:state;
}
async function recoveryKey(sessionId){const saved=(await chrome.storage.local.get('sugar.connection'))['sugar.connection'];return 'sugar.pendingRecovery.'+saved?.browserId+'.'+sessionId;}
export async function pendingRecovery(sessionId,item,remove=false){
  const key=await recoveryKey(sessionId),rows=(await chrome.storage.local.get(key))[key] || [];
  if(item){const next=rows.filter(row=>row.operationId!==item.operationId);if(!remove)next.push({...item,recovery:true,status:'recovery'});await chrome.storage.local.set({[key]:next});return next;}
  return rows;
}
export function steerDelivery(item,running){
  const prefix=item.mode==='interrupt'?'打断插话':'插话';
  if(item.status==='sending')return prefix+' · 正在发送…';
  if(item.status==='failed')return prefix+'未采纳：'+(item.error || '提交失败');
  if(item.status==='cancelled')return prefix+' · 已取消';
  if(item.status==='interrupting' || item.status==='restarting')return prefix+' · 正在接管当前生成';
  if(item.status==='deferred')return prefix+' · 等待当前操作安全结束';
  return prefix+(running?' · 待采纳':' · 待采纳，当前任务已结束');
}
