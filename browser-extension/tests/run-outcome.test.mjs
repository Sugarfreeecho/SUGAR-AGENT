import test from 'node:test';
import assert from 'node:assert/strict';
import {initialTimeline,applyTimeline,timelineFromHistory,mergeSteerSnapshot} from '../src/timeline.mjs';
import {runOutcome,activeRunTurn} from '../src/run-outcome.mjs';
import {recoverStoppedRun} from '../src/run-recovery.mjs';

const start=()=>applyTimeline(initialTimeline('s'),{type:'run_started',run_id:'r'});
const notices=state=>state.turns.at(-1).process.filter(block=>block.kind==='error');
for(const error of ['provider connection lost',{code:'connection_error',message:'provider connection lost'}])test('terminal error field produces a visible failure: '+typeof error,()=>{
  const state=applyTimeline(start(),{type:'run_failed',run_id:'r',error});
  assert.equal(state.running,false);assert.equal(state.turns[0].status,'failed');
  assert.equal(notices(state)[0].content,'provider connection lost');
});
test('bare interruption is visible without any earlier thought or tool',()=>{
  const state=applyTimeline(start(),{type:'run_interrupted',run_id:'r'});
  assert.equal(notices(state)[0].title,'执行已中断');assert.ok(notices(state)[0].content);
  assert.equal(state.running,false);
});
test('manual stop is informational while internal handoffs stay quiet',()=>{
  assert.equal(runOutcome({type:'run_interrupted',reason:'control_stop'}).notice.title,'已停止');
  for(const reason of ['process_restart','followup','superseded_by_new_run'])assert.equal(runOutcome({type:'run_interrupted',reason}).notice,null);
  assert.match(runOutcome({type:'run_interrupted',reason:'backend_shutdown'}).notice.content,/后端/);
});
test('structured backend error card survives terminal detail and duplicate delivery',()=>{
  const content='__ERR_CARD__'+JSON.stringify({t:'模型请求失败',m:'连接已断开',s:'检查模型服务',d:'socket reset'});
  let state=applyTimeline(start(),{type:'error',run_id:'r',content});
  assert.equal(state.running,true);
  for(let i=0;i<2;i++)state=applyTimeline(state,{type:'run_failed',run_id:'r',error:'socket reset'});
  assert.equal(notices(state).length,1);assert.equal(notices(state)[0].content,'模型请求失败：连接已断开');
  assert.match(notices(state)[0].detail,/检查模型服务/);assert.match(notices(state)[0].detail,/socket reset/);
});
test('failed and unknown result statuses have notices even without reasons',()=>{
  for(const result_status of ['failed','unknown']){
    const state=applyTimeline(start(),{type:'run_finished',run_id:'r',result_status});
    assert.equal(state.running,false);assert.equal(notices(state)[0].outcome,result_status);
  }
  assert.equal(runOutcome({type:'run_finished'}).notice,null);
});
test('terminal closes a live tool and thought without losing partial text or mutating prior state',()=>{
  for(const type of ['llm_reasoning_delta','tool_call_delta']){
    const before=applyTimeline(start(),{type,run_id:'r',delta:'partial',name_delta:'run_shell',arguments_delta:'{"command":"echo'},null,{now:1000});
    const after=applyTimeline(before,{type:'run_failed',run_id:'r',error:'connection lost'},null,{now:2000});
    assert.equal(before.turns[0].process[0].active,true);assert.equal(after.turns[0].process[0].active,false);
    assert.equal(after.turns[0].process[0].timingActive,false);
    assert.equal(after.turns[0].process[0].content,before.turns[0].process[0].content);
  }
});
test('late failure belongs to its own run and leaves the newer run active',()=>{
  let state=applyTimeline(start(),{type:'run_started',run_id:'next'});
  state=applyTimeline(state,{type:'run_failed',run_id:'r',error:'old failure'});
  assert.equal(state.running,true);assert.equal(activeRunTurn(state).runId,'next');
  assert.equal(state.turns[0].process[0].content,'old failure');assert.equal(notices(state).length,0);
});
test('inactivity recovery finds the durable terminal omitted from live delivery',()=>{
  const state=start(),owner=activeRunTurn(state);
  const next=recoverStoppedRun(state,[{type:'run_failed',run_id:'r',error:'lost terminal',runtime_seq:8}],owner,'s');
  assert.equal(next.running,false);assert.equal(notices(next)[0].content,'lost terminal');
});
test('missing durable terminal is reported as unconfirmed rather than successful',()=>{
  const state=start(),owner=activeRunTurn(state),next=recoverStoppedRun(state,[],owner,'s');
  assert.equal(next.running,false);assert.equal(next.turns[0].status,'unknown');
  assert.match(notices(next)[0].content,/未收到完成状态/);
  const late=applyTimeline(next,{type:'llm_reasoning_delta',run_id:'r',delta:'stale'});
  assert.equal(late.running,false);
});
test('recovery cannot overwrite newly arrived progress, a different run or another session',()=>{
  const state=start(),owner=activeRunTurn(state);
  const progressed=applyTimeline(state,{type:'llm_response_delta',run_id:'r',delta:'new progress'});
  const newer=applyTimeline(state,{type:'run_started',run_id:'next'});
  for(const current of [progressed,newer])assert.equal(recoverStoppedRun(current,[],owner,'s'),current);
  assert.equal(recoverStoppedRun(state,[],owner,'other'),state);
});
test('a terminal already seen in history still clears an older active-runtime snapshot',()=>{
  const events=[{type:'run_started',run_id:'r',runtime_seq:10},{type:'run_finished',run_id:'r',runtime_seq:11}];
  const state={...timelineFromHistory(events,0,'s'),running:true},owner=activeRunTurn(state);
  const next=recoverStoppedRun(state,events,owner,'s');
  assert.equal(next.running,false);assert.equal(next.turns[0].status,'succeeded');assert.equal(notices(next).length,0);
});
test('repeated consumed-steer snapshots do not look like fresh progress or postpone terminal recovery',()=>{
  const rows=[{id:'steer',client_id:'client',state:'consumed',version:2,consumed_by:'r',ui_content:'steer input'}];
  const state=mergeSteerSnapshot(start(),rows),owner=activeRunTurn(state);
  const refreshed=mergeSteerSnapshot(state,rows);
  assert.equal(activeRunTurn(refreshed),owner);assert.equal(refreshed.turns[0].process.filter(block=>block.kind==='steer').length,1);
  const next=recoverStoppedRun(refreshed,[{type:'run_interrupted',run_id:'r',reason:'control_stop'}],owner,'s');
  assert.equal(next.running,false);assert.equal(notices(next)[0].title,'已停止');
});
