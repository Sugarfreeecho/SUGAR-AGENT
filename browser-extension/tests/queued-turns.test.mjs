import test from 'node:test';
import assert from 'node:assert/strict';
import {initialTimeline,applyTimeline,timelineFromHistory,prependTimeline,mergeLiveTurns} from '../src/timeline.mjs';
import {turnKey,humanTurnKey} from '../src/conversation-turns.mjs';
import {groupConversationTurns} from '../src/turn-groups.mjs';
import {reconcilePendingTurns} from '../src/pending-messages.mjs';
import {createUserBackfill} from '../src/user-backfill.mjs';
const user=(index,text='任务 '+index)=>({type:'user',run_id:'shared',turn_id:'input-'+index,operation_id:'input-'+index,runtime_seq:index*10,queued_followup:index>1,content:text,created_at:'2026-11-01T00:00:0'+index+'Z'});
const response=index=>({type:'llm_response_delta',run_id:'shared',process_group_id:'turn:'+index*10,react_iter:index,delta:'回答 '+index});
const final=index=>({type:'final',run_id:'shared',runtime_seq:index*10,content:'回答 '+index});
const history=[user(1),final(1),user(2),response(2),final(2),user(3),response(3)];
const live=events=>events.reduce((state,event)=>applyTimeline(state,event),initialTimeline());
test('official queued inputs in one run have independent user bubbles, answers and process groups',()=>{
  const state=live(history);
  assert.equal(state.turns.length,3);assert.deepEqual(state.turns.map(turn=>turn.user),['任务 1','任务 2','任务 3']);
  assert.deepEqual(state.turns.map(turn=>turn.final || turn.body),['回答 1','回答 2','回答 3']);
  assert.equal(new Set(state.turns.map(turnKey)).size,3);assert.equal(groupConversationTurns(state.turns).length,3);
  assert.equal(state.turns[0].process.length,0);assert.equal(state.turns[1].status,'succeeded');assert.equal(state.running,true);
});
test('identical queued text remains separate while replayed live and history facts deduplicate',()=>{
  let state=live([user(1,'相同'),final(1),user(2,'相同'),final(2),user(3,'相同')]);
  for(let index=1;index<=3;index++)state=applyTimeline(state,{...user(index,'相同'),runtime_seq:index*10,attachments:index===2?[{attachmentId:'image',name:'参考.png'}]:[]},'history:'+index,{history:true});
  assert.equal(state.turns.length,3);assert.deepEqual(state.turns[1].images,['image']);assert.equal(state.turns[1].imageMeta.image.name,'参考.png');
  assert.equal(state.turns[2].user,'相同');assert.equal(new Set(state.turns.map(turnKey)).size,3);
});
test('late results for an earlier phase do not replace the active queued answer',()=>{
  let state=live([user(1),{type:'tool_pending',run_id:'shared',process_group_id:'turn:10',react_iter:1,tool_call_id:'old',tool:'run_shell'},final(1),user(2),response(2)]);
  state=applyTimeline(state,{type:'tool_call',run_id:'shared',process_group_id:'turn:10',react_iter:1,tool_call_id:'old',tool:'run_shell',result:'done',status:{ok:true}});
  state=applyTimeline(state,final(1));
  assert.equal(state.turns[0].process.length,1);assert.equal(state.turns[1].process.length,0);assert.equal(state.turns[1].body,'回答 2');assert.equal(state.turns[1].final,'');
});
test('a queued user boundary finishes the prior phase without mutating earlier state',()=>{
  const before=live([user(1),{type:'llm_reasoning_delta',run_id:'shared',react_iter:1,delta:'thought'},final(1)]),saved=JSON.stringify(before);
  const after=applyTimeline(before,user(2));
  assert.equal(JSON.stringify(before),saved);assert.equal(after.turns[0].status,'succeeded');assert.equal(after.turns[1].status,'running');
});
test('missing queued user recovery targets its group, not the first user of the same run',async()=>{
  let state=live([user(1),final(1),response(2)]);
  assert.equal(state.turns.length,2);assert.equal(state.turns[1].user,'');const key=turnKey(state.turns[1]);
  const backfill=createUserBackfill({read:async()=>({events:[user(1),user(2)]}),isCurrent:()=>true,apply:fact=>state=applyTimeline(state,fact,'backfilled',{history:true})});
  backfill.sync({sessionId:'s',epoch:1,turns:state.turns});await new Promise(resolve=>setImmediate(resolve));
  assert.equal(state.turns.length,2);assert.equal(state.turns[1].user,'任务 2');assert.equal(turnKey(state.turns[1]),key);assert.equal(state.turns[1].body,'回答 2');backfill.dispose();
});
test('paging and snapshot replacement keep shared-run turns separate and retain the live tail',()=>{
  const older=timelineFromHistory(history.slice(0,3)),newer=timelineFromHistory(history.slice(2));
  const keys=newer.turns.map(turnKey),whole=prependTimeline(newer,older);
  assert.equal(whole.turns.length,3);assert.deepEqual(whole.turns.slice(1).map(turnKey),keys);
  const active=live(history),merged=mergeLiveTurns(timelineFromHistory(history.slice(0,5)),active);
  assert.equal(merged.turns.length,3);assert.equal(merged.turns[2].body,'回答 3');assert.equal(merged.turns[0].user,'任务 1');
});
test('pending operation text is provisional and is replaced by canonical user text and images',()=>{
  const started=applyTimeline(initialTimeline(),{type:'run_started',run_id:'shared'});
  let state=reconcilePendingTurns(started,[{runId:'shared',content:'队列摘要',images:[]}]);
  assert.equal(state.turns[0].pendingUser,true);
  state=applyTimeline(state,{...user(1,'完整用户内容'),attachments:[{attachmentId:'image',name:'图片.png'}]});
  assert.equal(state.turns.length,1);assert.equal(state.turns[0].user,'完整用户内容');assert.equal(state.turns[0].process.length,0);assert.equal(state.turns[0].hasUserMessage,true);
  assert.equal(reconcilePendingTurns(state,[{runId:'shared',content:'旧摘要'}]),state);
});
test('questions in a shared run anchor to one user turn rather than appearing under each bubble',()=>{
  const turns=timelineFromHistory(history).turns;
  assert.equal(humanTurnKey({run_id:'shared',process_group_id:'turn:20'},turns),turnKey(turns[1]));
  assert.equal(humanTurnKey({run_id:'shared',created_at:'2026-11-01T00:00:02.500Z'},turns),turnKey(turns[1]));
});
test('partial user timestamps do not attach a new question to an earlier queued turn',()=>{
  const turns=timelineFromHistory(history.slice(0,3)).turns;delete turns[1].userCreatedAt;
  assert.equal(humanTurnKey({run_id:'shared',created_at:'2026-11-01T00:00:02.500Z'},turns),turnKey(turns[1]));
});
test('replayed queued users never revive a completed run after reconnect',()=>{
  let state=live([...history,final(3),{type:'run_finished',run_id:'shared',ephemeral:true}]);
  for(const index of [2,3])state=applyTimeline(state,{...user(index),replayed_recent:true},'replay:'+index);
  assert.equal(state.running,false);assert.equal(state.turns.length,3);assert.ok(state.turns.every(turn=>turn.status==='succeeded'));
});
