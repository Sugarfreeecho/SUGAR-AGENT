import test from 'node:test';
import assert from 'node:assert/strict';
import {initialTimeline,applyTimeline,stageSteerMessage,acknowledgeSteerMessage,rejectSteerMessage,mergeSteerSnapshot,timelineFromHistory} from '../src/timeline.mjs';
const running=()=>applyTimeline(applyTimeline(initialTimeline(),{type:'user',run_id:'run',content:'开始'}),{type:'run_started',run_id:'run'});
const receipt={operation_id:'op',accepted:true,item:{id:'steer',state:'queued',ui_content:'补充'}};
const consumed={type:'user_steer',run_id:'run',client_id:'op',steer_id:'steer',content:'补充'};

test('steer acceptance keeps the current run and only consumption marks it applied',()=>{
  let state=stageSteerMessage(running(),'local','补充');
  state=acknowledgeSteerMessage(state,'local',receipt);
  assert.equal(state.running,true);assert.equal(state.turns.length,1);
  assert.equal(state.pendingSteers[0].status,'queued');assert.equal(state.turns[0].process.length,0);
  state=applyTimeline(state,{type:'llm_response_delta',run_id:'run',react_iter:1,delta:'先前输出'});
  state=applyTimeline(state,consumed,'live');
  assert.equal(state.pendingSteers.length,0);
  assert.deepEqual(state.turns[0].process.map(x=>x.kind),['answer','steer']);
  assert.equal(state.turns[0].process[0].content,'先前输出');
  state=applyTimeline(state,consumed,'history');
  assert.equal(state.turns[0].process.filter(x=>x.kind==='steer').length,1);
});
test('consumption and recovery may arrive before the HTTP receipt',()=>{
  let state=stageSteerMessage(running(),'local','补充');
  state=applyTimeline(state,consumed);
  state=acknowledgeSteerMessage(state,'local',receipt);
  state=mergeSteerSnapshot(state,[{id:'steer',client_id:'op',ui_content:'补充',state:'queued'}]);
  assert.equal(state.pendingSteers.length,0);assert.equal(state.turns.length,1);
});
test('distinct identical steers remain distinct while replays deduplicate',()=>{
  let state=applyTimeline(running(),consumed);
  state=stageSteerMessage(state,'local2','补充');
  state=acknowledgeSteerMessage(state,'local2',{...receipt,operation_id:'op2',item:{...receipt.item,id:'steer2'}});
  state=applyTimeline(state,{...consumed,client_id:'op2',steer_id:'steer2'});
  assert.equal(state.turns[0].process.filter(x=>x.kind==='steer').length,2);
  assert.equal(state.pendingSteers.length,0);
});
test('reload recovers queued steers and a missed consumption without extra runs',()=>{
  let state=timelineFromHistory([{type:'user',run_id:'run',content:'开始'}]);
  state=mergeSteerSnapshot(state,[{id:'steer',client_id:'op',ui_content:'补充',state:'queued'}]);
  assert.equal(state.pendingSteers.length,1);
  state=mergeSteerSnapshot(state,[{id:'steer',client_id:'op',ui_content:'补充',state:'consumed',consumed_by:'run'}]);
  assert.equal(state.pendingSteers.length,0);assert.equal(state.turns[0].process[0].kind,'steer');
  state=mergeSteerSnapshot(state,[{id:'ancient',client_id:'old',ui_content:'不在本页的旧记录',state:'consumed',consumed_by:'oldrun'}]);
  assert.equal(state.turns.length,1);
});
test('a completed-run fallback reconciles the next turn in either receipt order',()=>{
  const next={operation_id:'next',run_id:'next-run',accepted:true};
  let state=stageSteerMessage(running(),'local','下一条');
  state=acknowledgeSteerMessage(state,'local',next);
  state=applyTimeline(state,{type:'run_started',run_id:'next-run',operation_id:'next'});
  state=applyTimeline(state,{type:'user',run_id:'next-run',content:'下一条'});
  assert.equal(state.pendingSteers.length,0);assert.equal(state.turns.length,2);assert.equal(state.turns[1].user,'下一条');
  state=stageSteerMessage(running(),'local','下一条');
  state=applyTimeline(state,{type:'user',run_id:'next-run',content:'下一条'});
  state=acknowledgeSteerMessage(state,'local',next);
  assert.equal(state.turns.length,2);assert.equal(state.pendingSteers.length,0);
});
test('rejected sends remove only the optimistic steer',()=>{
  let state=stageSteerMessage(running(),'local','重试内容');
  state=rejectSteerMessage(state,'local');
  assert.equal(state.pendingSteers.length,0);assert.equal(state.turns[0].user,'开始');assert.equal(state.running,true);
});

test('old cancelled and failed inbox records never become new bubbles below current history',()=>{
  const history=[{type:'user',run_id:'old',content:'旧问题'},{type:'final',run_id:'old',content:'已有回答'}];
  const initial=timelineFromHistory(history),state=mergeSteerSnapshot(initial,[
    {id:'cancel-one',client_id:'old-one',ui_content:'请改为1.5.1吧',state:'cancelled',version:2},
    {id:'cancel-two',client_id:'old-two',ui_content:'和上次迁移包相比是不是只有packing文件夹改了',state:'cancelled',version:2},
    {id:'old-failure',client_id:'old-three',ui_content:'历史失败插话',state:'failed',version:3},
  ]);
  assert.equal(state.pendingSteers.length,0);assert.deepEqual(state.turns,initial.turns);assert.equal(state.running,false);
});
test('cancellation withdraws an accepted pending steer and stale snapshots or receipts cannot revive it',()=>{
  let state=acknowledgeSteerMessage(stageSteerMessage(running(),'local','补充'),'local',receipt);
  state=mergeSteerSnapshot(state,[{id:'steer',client_id:'op',ui_content:'补充',state:'cancelled',version:2}]);
  assert.equal(state.pendingSteers.length,0);
  for(const version of [1,3])state=mergeSteerSnapshot(state,[{id:'steer',client_id:'op',ui_content:'补充',state:'queued',version}]);
  state=stageSteerMessage(state,'retry-receipt','补充');
  state=acknowledgeSteerMessage(state,'retry-receipt',receipt);
  assert.equal(state.pendingSteers.length,0);assert.equal(state.turns.length,1);assert.equal(state.running,true);
});
test('an old terminal record with identical text cannot cancel an unrelated optimistic send',()=>{
  let state=stageSteerMessage(running(),'local','补充');
  state=mergeSteerSnapshot(state,[{id:'different-steer',client_id:'different-op',ui_content:'补充',state:'cancelled',version:2}]);
  assert.equal(state.pendingSteers[0].clientId,'local');assert.equal(state.pendingSteers[0].status,'sending');
  state=acknowledgeSteerMessage(state,'local',receipt);
  assert.equal(state.pendingSteers[0].operationId,'op');assert.equal(state.pendingSteers[0].status,'queued');
});
test('only a known current failure gets inline delivery feedback and consumed history is preserved',()=>{
  let state=acknowledgeSteerMessage(stageSteerMessage(running(),'local','补充'),'local',receipt);
  state=mergeSteerSnapshot(state,[{id:'steer',client_id:'op',ui_content:'补充',state:'failed',version:2,error:'无法采纳'}]);
  assert.equal(state.pendingSteers.length,1);assert.equal(state.pendingSteers[0].status,'failed');assert.equal(state.pendingSteers[0].error,'无法采纳');
  const applied=applyTimeline(running(),consumed);
  state=mergeSteerSnapshot(applied,[{id:'steer',client_id:'op',ui_content:'补充',state:'cancelled',version:1}]);
  assert.equal(state.pendingSteers.length,0);assert.deepEqual(state.turns,applied.turns);
});
