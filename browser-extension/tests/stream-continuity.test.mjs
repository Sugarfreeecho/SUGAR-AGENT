import test from 'node:test';
import assert from 'node:assert/strict';
import {initialTimeline,applyTimeline,timelineFromHistory} from '../src/timeline.mjs';
import {eventKey} from '../src/shared.mjs';
import {executionSnapshotEvent} from '../src/execution-recovery.mjs';

const reduce=events=>events.reduce((state,event)=>applyTimeline(state,event,eventKey(event,'s')),initialTimeline('s'));
const live=(type,run,seq,extra={})=>({type,run_id:run,event_bus_epoch:'epoch',event_bus_seq:seq,ephemeral:true,...extra});

test('a late terminal from a previous run cannot stop the next active run',()=>{
  let state=reduce([live('run_started','old',1),live('user','old',2,{content:'first'}),
    live('run_started','next',3),live('user','next',4,{content:'second'}),live('llm_reasoning_delta','next',5,{delta:'thinking'})]);
  state=applyTimeline(state,live('run_finished','old',6));
  assert.equal(state.running,true);
  state=applyTimeline(state,live('llm_response_delta','next',7,{delta:'second answer'}));
  assert.equal(state.turns.at(-1).body,'second answer');
  state=applyTimeline(state,live('run_finished','next',8));assert.equal(state.running,false);
});

test('a new pending process group can start after a completed continuation with no user in its page',()=>{
  let state=timelineFromHistory([{type:'llm_response',run_id:'shared',process_group_id:'turn:10',react_iter:1,content:'previous'},
    {type:'final',run_id:'shared',process_group_id:'turn:10',runtime_seq:11,content:'previous'}],0,'s');
  state=applyTimeline(state,live('llm_reasoning_delta','shared',20,{process_group_id:'turn:30',react_iter:2,delta:'new thinking'}));
  assert.equal(state.turns.length,2);assert.equal(state.turns.at(-1).process[0].content,'new thinking');assert.equal(state.running,true);
  state=applyTimeline(state,{type:'user',run_id:'shared',process_group_id:'turn:30',runtime_seq:30,queued_followup:true,turn_id:'pending',content:'pending input'});
  assert.equal(state.turns.length,2);assert.equal(state.turns.at(-1).user,'pending input');
});

test('an explicit pending group never falls back to a previous answer with the same phase number',()=>{
  let state=reduce([live('user','shared',1,{runtime_seq:10,content:'first'}),
    live('llm_response_delta','shared',2,{process_group_id:'turn:10',react_iter:1,delta:'first answer'}),
    {type:'final',run_id:'shared',runtime_seq:10,content:'first answer'},
    {type:'user',run_id:'shared',runtime_seq:20,queued_followup:true,turn_id:'pending',content:'second'},
    live('llm_response_delta','shared',3,{process_group_id:'turn:20',react_iter:1,delta:'second answer'})]);
  assert.equal(state.turns.at(-1).body,'second answer');assert.equal(state.turns[0].body,'');
});

test('tool array indexes are not durable event identities across independent runs',()=>{
  const a={type:'tool_pending',run_id:'a',index:0,event_bus_epoch:'epoch',event_bus_seq:1};
  const b={...a,run_id:'b',event_bus_seq:2};
  assert.notEqual(eventKey(a,'s'),eventKey(b,'s'));
  let state=reduce([a,b]);assert.equal(state.turns.length,2);
});

for(const kind of ['reasoning','response'])test(kind+' recovery replaces cumulative text and resumes after its saved cursor',()=>{
  let state=reduce([live('user','run',1,{content:'task',runtime_seq:10}),
    live('llm_'+kind+'_delta','run',2,{delta:'first',delta_seq:1,execution_id:'exec',execution_runtime_seq:11,react_iter:1,process_group_id:'turn:10'})]);
  const saved={kind,status:'generating',run_id:'run',execution_id:'exec',react_iter:1,process_group_id:'turn:10',content:'first second',last_runtime_seq:13,
    ['last_llm_'+kind+'_delta_delta_seq']:2};
  const snapshot=executionSnapshotEvent(saved);
  state=applyTimeline(state,snapshot,'recovered');
  state=applyTimeline(state,live('llm_'+kind+'_delta','run',3,{delta:' second',delta_seq:2,execution_id:'exec',execution_runtime_seq:12,react_iter:1}));
  state=applyTimeline(state,live('llm_'+kind+'_delta','run',4,{delta:' third',delta_seq:3,execution_id:'exec',execution_runtime_seq:14,react_iter:1}));
  const turn=state.turns.at(-1);
  assert.equal(kind==='reasoning'?turn.process[0].content:turn.body,'first second third');
  assert.equal(executionSnapshotEvent({...saved,ui_committed:true}),null);
});

test('a late partial response recovery cannot restore a second answer after the authoritative final',()=>{
  let state=reduce([live('user','run',1,{content:'task',runtime_seq:10}),live('llm_response_delta','run',2,{delta:'answer',react_iter:1}),
    {type:'final',run_id:'run',runtime_seq:20,content:'answer'}]);
  state=applyTimeline(state,executionSnapshotEvent({kind:'response',status:'generating',run_id:'run',react_iter:1,content:'ans',last_runtime_seq:19}));
  assert.equal(state.turns[0].final,'answer');assert.equal(state.turns[0].body,'');
});
