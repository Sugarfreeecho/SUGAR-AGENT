import test from 'node:test';
import assert from 'node:assert/strict';
import {initialTimeline,applyTimeline,timelineFromHistory,prependTimeline} from '../src/timeline.mjs';
import {groupConversationTurns} from '../src/turn-groups.mjs';
const history=[
  {type:'user',run_id:'before',runtime_seq:10,content:'更新后重启'},
  {type:'llm_reasoning',run_id:'before',process_group_id:'turn:10',react_iter:1,content:'before reasoning'},
  {type:'tool_call',run_id:'before',process_group_id:'turn:10',tool_call_id:'restart',tool:'request_restart',react_iter:1,result:'authorized',status:{ok:true}},
  {type:'run_interrupted',run_id:'before',reason:'process_restart'},
  {type:'llm_reasoning',run_id:'resumed',process_group_id:'turn:10',react_iter:1,content:'after reasoning'},
  {type:'tool_call',run_id:'resumed',process_group_id:'turn:10',tool_call_id:'verify',tool:'run_shell',react_iter:1,result:'verified',status:{ok:true}},
  {type:'final',run_id:'resumed',content:'重启后继续完成'},
];
test('restart runs share one presentation group and retain independent tool and thinking identities',()=>{
  const timeline=timelineFromHistory(history),groups=groupConversationTurns(timeline.turns);
  assert.equal(groups.length,1);assert.equal(groups[0].turns.length,2);
  assert.equal(groups[0].turns.flatMap(turn=>turn.process).filter(block=>block.kind==='tool').length,2);
  assert.deepEqual(groups[0].turns.map(turn=>turn.process.find(block=>block.kind==='reason').content),['before reasoning','after reasoning']);
  assert.equal(timeline.turns.length,2);assert.equal(timeline.turns[1].user,'');
});
test('a final reply and every official user message bound the process group, including image-only messages',()=>{
  for(const boundary of [{type:'user',run_id:'another',process_group_id:'turn:10',content:'next'},
    {type:'user',run_id:'another',process_group_id:'turn:10',content:[{type:'image',attachment:{attachmentId:'image'}}]},
    {type:'llm_reasoning',run_id:'another',process_group_id:'turn:10',content:'later'}]){
    const timeline=timelineFromHistory([...history,boundary]);assert.equal(groupConversationTurns(timeline.turns).length,2);
  }
});
test('no text or proximity heuristic joins unrelated runs that lack a durable group identity',()=>{
  const turns=timelineFromHistory([{type:'user',run_id:'a',content:'same'},{type:'llm_reasoning',run_id:'b',content:'same'}]).turns;
  assert.equal(groupConversationTurns(turns).length,2);
});
test('planned process restart retains its run boundary without a false failed-execution card',()=>{
  const before=timelineFromHistory(history.slice(0,4)).turns[0];
  assert.equal(before.status,'interrupted');assert.equal(before.stopReason,'process_restart');
  assert.equal(before.process.filter(block=>block.kind==='error').length,0);
  const stopped=applyTimeline(initialTimeline(),{type:'run_interrupted',run_id:'stopped',reason:'manual_stop'});
  assert.equal(stopped.turns[0].process[0].kind,'error');
});
test('late live process metadata and replayed tool snapshots attach a continuation without merging phases',()=>{
  let timeline=timelineFromHistory(history.slice(0,4));
  timeline=applyTimeline(timeline,{type:'run_started',run_id:'resumed'});
  assert.equal(groupConversationTurns(timeline.turns).length,2);
  timeline=applyTimeline(timeline,{type:'llm_reasoning_delta',run_id:'resumed',process_group_id:'turn:10',react_iter:1,delta:'new thought'});
  assert.equal(groupConversationTurns(timeline.turns).length,1);
  assert.equal(timeline.turns[0].process[0].content,'before reasoning');
  assert.equal(timeline.turns[1].process[0].content,'new thought');
});
test('late user backfill and process metadata preserve an already mounted run and its interaction state',()=>{
  const pending=applyTimeline(initialTimeline(),{type:'run_started',run_id:'live'});
  const first=groupConversationTurns(pending.turns);
  const backfilled=applyTimeline(pending,{type:'user',run_id:'live',runtime_seq:80,content:'user question'});
  const second=groupConversationTurns(backfilled.turns,first);
  assert.equal(second[0].id,first[0].id);
  assert.equal(second[0].processGroupId,'turn:80');
  const streamed=applyTimeline(backfilled,{type:'llm_reasoning_delta',run_id:'live',process_group_id:'turn:80',react_iter:1,delta:'thinking'});
  assert.equal(groupConversationTurns(streamed.turns,second)[0].id,first[0].id);
});
test('loading earlier runs rejoins the same durable group while untouched history preserves memo identities',()=>{
  const older=timelineFromHistory(history.slice(0,4)),newer=timelineFromHistory(history.slice(4));
  const whole=prependTimeline(newer,older);const first=groupConversationTurns(whole.turns);
  assert.equal(first.length,1);assert.equal(first[0].turns.length,2);
  assert.equal(first[0].id,groupConversationTurns(newer.turns)[0].id,'Loading the old run must not remount the current process group');
  const second=groupConversationTurns(whole.turns,first);assert.equal(second[0],first[0]);
  const next=applyTimeline(whole,{type:'user',run_id:'next',content:'new turn'});
  const third=groupConversationTurns(next.turns,second);assert.equal(third[0],second[0]);assert.equal(third.length,2);
});
