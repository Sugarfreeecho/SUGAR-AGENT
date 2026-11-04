import test from 'node:test';
import assert from 'node:assert/strict';
import {processStatus,elapsedMilliseconds,formatElapsed} from '../src/process-display.mjs';
import {applyTimeline,initialTimeline,timelineFromHistory} from '../src/timeline.mjs';

test('string and structured tool states share localized labels and preserve failures',()=>{
  for(const status of [{execution_status:'completed'},{state:'succeeded'},{status:'completed'},{status:{ok:true}}]) {
    assert.equal(processStatus({type:'tool_call',...status}).label,'已完成');
  }
  assert.equal(processStatus({execution_status:'completed',status:{ok:false}}).label,'执行失败');
  assert.equal(processStatus({status:{timed_out:true,ok:false}}).label,'已超时');
  assert.equal(processStatus({status:'running'}).active,true);
  assert.equal(processStatus({status:'custom-provider-state'}).label,'状态未知');
  assert.equal(processStatus({status:'running'},'completed').label,'已完成');
});

test('live item timers start once, stop on completion and use the authoritative duration',()=>{
  let state=initialTimeline();
  const emit=(event,now)=>state=applyTimeline(state,{run_id:'r',react_iter:1,...event},undefined,{now});
  emit({type:'llm_reasoning_delta',delta:'第一段'},1000);
  emit({type:'llm_reasoning_delta',delta:'第二段'},2000);
  assert.equal(elapsedMilliseconds(state.turns[0].process[0],2500),1500);
  emit({type:'llm_response_delta',delta:'说明'},3000);
  const reason=state.turns[0].process[0];
  assert.equal(elapsedMilliseconds(reason,10000),2000);
  emit({type:'llm_reasoning',content:'完整思考',duration_ms:1750},4000);
  assert.equal(elapsedMilliseconds(state.turns[0].process[0],10000),1750);
  emit({type:'tool_pending',tool_call_id:'t',tool:'run_shell'},5000);
  emit({type:'tool_execution_state',tool_call_id:'t',status:'running'},8000);
  const tool=state.turns[0].process.find(block=>block.kind==='tool');
  assert.equal(elapsedMilliseconds(tool,9000),1000);
  emit({type:'tool_call',tool_call_id:'t',status:{ok:true,duration_ms:1200},result:'ok'},10000);
  assert.equal(elapsedMilliseconds(state.turns[0].process.find(block=>block.kind==='tool'),20000),1200);
  emit({type:'tool_execution_state',tool_call_id:'t',status:'running'},12000);
  const completed=state.turns[0].process.find(block=>block.kind==='tool');
  assert.equal(completed.status,'已完成');assert.equal(completed.timingActive,false);
  assert.equal(elapsedMilliseconds(completed,30000),1200);
});

test('historical durations survive hydration while unmeasured old entries remain unknown',()=>{
  const state=timelineFromHistory([
    {type:'llm_reasoning',run_id:'r',react_iter:1,content:'思考',duration_ms:2400},
    {type:'tool_call',run_id:'r',react_iter:1,tool_call_id:'t',status:{ok:true,duration_ms:0}},
    {type:'llm_reasoning',run_id:'r',react_iter:2,content:'旧记录'},
  ]);
  assert.deepEqual(state.turns[0].process.map(block=>elapsedMilliseconds(block)),[2400,0,null]);
  assert.equal(formatElapsed(null),'—');assert.equal(formatElapsed(0),'0.0s');
  assert.equal(formatElapsed(1250),'1.3s');assert.equal(formatElapsed(65000),'1m 05s');assert.equal(formatElapsed(3661000),'1h 01m');
});

test('terminal events stop every item timer without a completed tool result',()=>{
  let state=applyTimeline(initialTimeline(),{type:'tool_pending',run_id:'r',tool_call_id:'t'},undefined,{now:1000});
  state=applyTimeline(state,{type:'run_interrupted',run_id:'r'},undefined,{now:3500});
  assert.equal(elapsedMilliseconds(state.turns[0].process[0],10000),2500);
  assert.equal(state.turns[0].process[0].timingActive,false);
  assert.equal(state.turns[0].process[0].status,'已停止');
});
