import test from 'node:test';
import assert from 'node:assert/strict';
import {createStreamWatch} from '../src/stream-watch.mjs';
function fixture(){let time=0;return {watch:createStreamWatch({now:()=>time}),advance:ms=>time+=ms};}
test('a healthy socket heartbeat cannot hide missing visible progress while the durable cursor advances',()=>{
  const {watch,advance}=fixture();watch.snapshot('s',{last_runtime_seq:10});advance(12000);
  for(const type of ['context_tokens','process_metrics','lifecycle_changed','sse_keepalive','cache_stats','status'])watch.event('s',{type,runtime_seq:99});
  assert.ok(watch.witness('s'));assert.equal(watch.behind(watch.witness('s'),{last_runtime_seq:12}),true);
});
test('a quiet long tool with an unchanged journal does not resubscribe, and empty probes back off',()=>{
  const {watch,advance}=fixture();watch.snapshot('s',{last_runtime_seq:10});advance(12000);
  assert.equal(watch.behind(watch.witness('s'),{last_runtime_seq:10}),false);assert.equal(watch.witness('s'),null);
  advance(12000);assert.ok(watch.witness('s'));
});
test('fresh frames fence an older probe and update the applied cursor',()=>{
  const {watch,advance}=fixture();watch.snapshot('s',{last_runtime_seq:10});advance(12000);const observed=watch.witness('s');
  watch.event('s',{type:'llm_reasoning_delta',execution_runtime_seq:15});
  assert.equal(watch.behind(observed,{last_runtime_seq:20}),false);assert.equal(watch.witness('s'),null);
  advance(12000);assert.equal(watch.behind(watch.witness('s'),{last_runtime_seq:15}),false);
});
test('session changes and authoritative recovery fence late probes without confusing replay for fresh output',()=>{
  const {watch,advance}=fixture();watch.snapshot('s',{last_runtime_seq:10});advance(12000);const observed=watch.witness('s');
  watch.snapshot('other',{last_runtime_seq:1});assert.equal(watch.behind(observed,{last_runtime_seq:20}),false);
  watch.event('other',{type:'run_started',replayed_recent:true});advance(12000);
  const before=watch.witness('other');watch.restored('other',[{execution_runtime_seq:5}]);
  assert.equal(watch.behind(before,{last_runtime_seq:5}),false);assert.equal(watch.witness('other'),null);
});
test('the history frontier includes buffered deltas beyond the canonical page',()=>{
  const {watch,advance}=fixture();watch.snapshot('s',{last_runtime_seq:10,events:[{execution_runtime_seq:15}]});advance(12000);
  assert.equal(watch.behind(watch.witness('s'),{last_runtime_seq:15}),false);
});
