import test from 'node:test';
import assert from 'node:assert/strict';
import {noteFrame,markCommitted,streamTrace} from '../src/stream-diagnostics.mjs';
test('diagnostics correlate receipt/reduction/commit without retaining messages, commands or credentials',()=>{
 const e={type:'tool_pending',run_id:'r',execution_id:'x',event_bus_seq:12,created_at:'2026-11-02T15:14:34Z',content:'private message',args:{command:'private command'},token:'private token'};
 for(const stage of ['background_received','sidebar_received','reduced'])noteFrame(stage,'diag-s',e,{outcome:'applied',token:'private token'});
 markCommitted();const rows=streamTrace('diag-s');assert.equal(rows.length,3);assert.ok(rows.find(row=>row.stage==='reduced').committed_at);
 const json=JSON.stringify(rows);for(const secret of ['private message','private command','private token'])assert.equal(json.includes(secret),false);
 assert.equal(rows[0].bus_seq,12);
});
test('recovery provenance and ignored frame outcomes are explicit and session scoped',()=>{
 noteFrame('recovery_triggered','diag-other',{type:'stream_recovery'},{reason:'durable_cursor_advanced',observed_cursor:10,head_cursor:20});
 noteFrame('reduced','diag-other',{type:'tool_pending',run_id:'r',replayed_recent:true},{outcome:'ignored',status_before:'failed'});
 assert.equal(streamTrace('diag-other').find(row=>row.stage==='recovery_triggered').head_cursor,20);
 assert.equal(streamTrace('diag-other').find(row=>row.stage==='reduced').source,'cached');
 assert.equal(streamTrace('diag-s').some(row=>row.session_id==='diag-other'),false);
});
test('history and execution recovery are never mislabeled as live frames',()=>{
 noteFrame('history_installed','diag-source',{type:'history'},{reason:'automatic_repair'});
 noteFrame('execution_snapshot','diag-source',{kind:'tool',execution_id:'x'});
 const rows=streamTrace('diag-source');assert.equal(rows[0].source,'history');assert.equal(rows[1].source,'snapshot');
});
test('repeated frames aggregate with bounded memory and returned diagnostics cannot mutate the trace',()=>{
 for(let i=0;i<300;i++)noteFrame('test','diag-bounded',{type:'tool_pending',run_id:'r',execution_id:String(i)});
 assert.equal(streamTrace().length,256);const copy=streamTrace('diag-bounded');copy[0].type='changed';assert.notEqual(streamTrace('diag-bounded')[0].type,'changed');
 noteFrame('test','diag-bounded',{type:'tool_pending',run_id:'r',execution_id:'299',event_bus_seq:50});
 assert.equal(streamTrace('diag-bounded').at(-1).count,2);
});
