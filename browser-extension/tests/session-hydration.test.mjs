import test from 'node:test';
import assert from 'node:assert/strict';
import {replaySessionBuffer} from '../src/session-hydration.mjs';
import {initialTimeline} from '../src/timeline.mjs';
test('failed foreign snapshot never replays its buffered events into current session',()=>{
  const state=initialTimeline(),events=[{type:'llm_response_delta',run_id:'b-run',delta:'foreign'}];
  assert.equal(replaySessionBuffer(state,events,'b','a'),state);
  assert.equal(replaySessionBuffer(state,events,'b',''),state);
});
test('same-session refresh replays buffered events once after snapshot failure',()=>{
  const event={type:'llm_response_delta',run_id:'a-run',delta:'kept',runtime_seq:2};
  const once=replaySessionBuffer(initialTimeline(),[event],'a','a');
  const twice=replaySessionBuffer(once,[event],'a','a');
  assert.deepEqual(twice,once);assert.equal(once.turns.length,1);
});
