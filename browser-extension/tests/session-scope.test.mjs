import test from 'node:test';
import assert from 'node:assert/strict';
import {isSessionChatEvent} from '../src/session-scope.mjs';
import {initialTimeline,applyTimeline,timelineFromHistory,mergeLiveTurns,prependTimeline} from '../src/timeline.mjs';
import {replaySessionBuffer} from '../src/session-hydration.mjs';

test('forwarded child events cannot change parent text, tools, lifecycle, usage or replay identities',()=>{
  let state=timelineFromHistory([{type:'user',run_id:'parent-run',content:'主任务'}],0,'parent');
  state=applyTimeline(state,{type:'run_started',run_id:'parent-run'});
  for(const type of ['user','llm_reasoning_delta','llm_response_delta','tool_call','final','run_finished','run_failed','run_interrupted','context_tokens','status','interaction_requested']){
    for(const owner of [{_subagent_forward:true,agent_id:'child'},{session_id:'child'},{agent_id:'child',ephemeral:true}]){
      const child={type,run_id:'parent-run',delta:'子内容',content:'子内容',runtime_seq:90,...owner};
      assert.equal(applyTimeline(state,child,'shared-identity'),state,type+JSON.stringify(owner));
    }
  }
  assert.equal(state.running,true);assert.equal(state.seen.has('shared-identity'),false);
  const own=applyTimeline(state,{type:'llm_response_delta',run_id:'parent-run',delta:'主回答'},'shared-identity');
  assert.equal(own.turns.at(-1).body,'主回答');
});

test('a selected child accepts its direct stream but rejects forwarded grandchildren and parent events',()=>{
  let child=initialTimeline('child');
  child=applyTimeline(child,{type:'user',session_id:'child',agent_id:'child',run_id:'own',content:'子任务'});
  child=applyTimeline(child,{type:'llm_response_delta',session_id:'child',agent_id:'child',run_id:'own',delta:'子回答'});
  assert.equal(child.turns[0].body,'子回答');
  for(const event of [
    {session_id:'parent'}, {session_id:'grandchild'}, {_subagent_forward:true,agent_id:'grandchild'},
    {agent_id:'grandchild',ephemeral:true}, {type:'subagent_start',agent_id:'grandchild'},
  ])assert.equal(applyTimeline(child,{type:'final',run_id:'own',content:'错误内容',...event}),child);
  assert.equal(isSessionChatEvent({type:'tool_call',session_id:'child'},'child'),true);
});

test('history, hydration and live snapshot merging retain the selected session boundary',()=>{
  const events=[{type:'user',session_id:'parent',run_id:'own',content:'主任务'},
    {type:'user',session_id:'child',run_id:'wrong',content:'子任务'},
    {type:'final',agent_id:'child',_subagent_forward:true,run_id:'wrong',content:'子结果'},
    {type:'final',session_id:'parent',run_id:'own',content:'主结果'}];
  const parent=timelineFromHistory(events,0,'parent');
  assert.equal(parent.turns.length,1);assert.equal(parent.turns[0].final,'主结果');
  const child=timelineFromHistory([{type:'user',run_id:'other',content:'子任务'}],0,'child');
  assert.equal(mergeLiveTurns(parent,child),parent);
  assert.equal(prependTimeline(parent,child),parent);
  const replayed=replaySessionBuffer(parent,[{type:'final',session_id:'child',run_id:'new',content:'子结果'}],'parent','parent');
  assert.equal(replayed,parent);
});
