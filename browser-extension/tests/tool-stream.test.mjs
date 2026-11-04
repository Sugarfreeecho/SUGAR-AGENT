import test from 'node:test';
import assert from 'node:assert/strict';
import {applyTimeline,initialTimeline,prependTimeline,timelineFromHistory} from '../src/timeline.mjs';
import {toolSnapshotEvent,toolOutput,outputCoveredByResult} from '../src/tool-stream.mjs';

function fixture(){
  let state=initialTimeline();
  return {emit(event){state=applyTimeline(state,{run_id:'r',react_iter:1,stream_seq:8,...event},undefined,{now:100000});return state;},get state(){return state;},get tools(){return state.turns[0].process.filter(row=>row.kind==='tool');}};
}
test('argument fragments promote a draft to its call identity without remounting or duplicating',()=>{
  const f=fixture();f.emit({type:'llm_reasoning_delta',delta:'计划'});
  f.emit({type:'tool_call_delta',index:0,delta_seq:1,name_delta:'run_',arguments_delta:'{"command":"echo '});
  const id=f.tools[0].id;assert.equal(f.tools[0].commandText,'echo ');assert.equal(f.state.turns[0].process[0].active,false);
  f.emit({type:'tool_call_delta',index:0,id:'shell',delta_seq:2,name_delta:'shell',arguments_delta:'hello"}'});
  assert.equal(f.tools.length,1);assert.equal(f.tools[0].id,id);assert.equal(f.tools[0].toolCallId,'shell');assert.equal(f.tools[0].title,'run_shell');
  assert.equal(f.tools[0].argsText,'{"command":"echo hello"}');assert.equal(f.tools[0].commandText,'echo hello');
  f.emit({type:'tool_pending',tool_call_index:0,tool_call_id:'shell',tool:'run_shell',args:{command:'echo hello'}});
  assert.equal(f.tools.length,1);assert.equal(f.tools[0].argumentsCommitted,true);assert.deepEqual(JSON.parse(f.tools[0].argsText),{command:'echo hello'});
});
test('interleaved parallel argument streams and later calls keep independent entries',()=>{
  const f=fixture();
  f.emit({type:'tool_call_delta',index:0,delta_seq:1,name_delta:'read_',arguments_delta:'{"path":"'});
  f.emit({type:'tool_call_delta',index:1,id:'b',delta_seq:2,name_delta:'write_file',arguments_delta:'{"path":"b"}'});
  f.emit({type:'tool_call_delta',index:0,id:'a',delta_seq:3,name_delta:'file',arguments_delta:'a"}'});
  assert.equal(f.tools.length,2);assert.equal(f.tools[0].title,'read_file');assert.equal(f.tools[1].title,'write_file');
  assert.equal(f.tools[0].argsText,'{"path":"a"}');assert.equal(f.tools[1].argsText,'{"path":"b"}');
  f.emit({type:'tool_call_delta',react_iter:2,stream_seq:9,index:0,id:'c',delta_seq:1,name_delta:'read_file',arguments_delta:'{}'});
  assert.equal(f.tools.length,3);
});
test('stdout and stderr append in order with counters independent of argument generation',()=>{
  const f=fixture();f.emit({type:'tool_call_delta',id:'a',index:0,delta_seq:10,name_delta:'run_shell',arguments_delta:'{"command":"test"}'});
  const output={type:'tool_command_delta',tool_call_id:'a',tool_call_index:0,tool:'run_shell'};
  f.emit({...output,delta_seq:1,stream:'stdout',raw_delta:'first\n',delta:'\n实时输出\nfirst\n'});
  f.emit({...output,delta_seq:2,stream:'stderr',raw_delta:'warning\n',delta:'\nSTDERR:\nwarning\n'});
  f.emit({...output,delta_seq:2,delta:'DUPLICATE'});
  assert.equal(f.tools.length,1);assert.equal(toolOutput(f.tools[0]),'\n实时输出\nfirst\n\nSTDERR:\nwarning\n');
  assert.equal(f.tools[0].active,true);assert.equal(f.tools[0].commandText,'test');assert.equal(f.tools[0].hasResult,undefined);
});
test('compacted replay replaces partial arguments and output then accepts new chunks once',()=>{
  const f=fixture();const args={type:'tool_call_delta',id:'a',index:0,name_delta:'',arguments_delta:'{"x":',delta_seq:1};
  f.emit(args);f.emit({...args,replayed_snapshot:true,arguments_delta:'{"x":1}',name_delta:'read_file',delta_seq:3});
  assert.equal(f.tools[0].argsText,'{"x":1}');assert.equal(f.tools[0].title,'read_file');
  const output={type:'tool_command_delta',tool_call_id:'a',delta_seq:1,delta:'a'};f.emit(output);
  f.emit({...output,replayed_snapshot:true,delta_seq:4,delta:'abcd'});f.emit({...output,delta_seq:5,delta:'e'});
  assert.equal(toolOutput(f.tools[0]),'abcde');
});
test('durable recovery restores generated arguments and output with replay cursors',()=>{
  const f=fixture();f.emit(toolSnapshotEvent({kind:'tool',execution_id:'e',run_id:'r',react_iter:1,stream_seq:8,tool_call_id:'a',tool_call_index:0,
    tool:'run_shell',arguments_raw:'{"command":"echo hi"}',status:'running',executed:true,output:'first\n',last_runtime_seq:20,
    last_tool_call_delta_delta_seq:8,last_tool_command_delta_delta_seq:2,execution_started_at:90}));
  f.emit({type:'tool_command_delta',execution_id:'e',execution_runtime_seq:19,tool_call_id:'a',delta_seq:2,delta:'first\n'});
  f.emit({type:'tool_command_delta',execution_id:'e',execution_runtime_seq:21,tool_call_id:'a',delta_seq:3,delta:'second\n'});
  assert.equal(f.tools.length,1);assert.equal(f.tools[0].argsText,'{"command":"echo hi"}');assert.equal(toolOutput(f.tools[0]),'first\nsecond\n');
  assert.equal(f.tools[0].startedAt,90000);
  f.emit(toolSnapshotEvent({execution_id:'e',status:'running',output:'STALE',last_runtime_seq:20}));
  assert.equal(toolOutput(f.tools[0]),'first\nsecond\n');
});
test('authoritative final results keep parameters, output and duration while rejecting late active events',()=>{
  const f=fixture();f.emit({type:'tool_pending',tool_call_id:'a',args:{command:'echo hi'}});
  f.emit({type:'tool_command_delta',tool_call_id:'a',delta_seq:1,delta:'hi\n'});
  f.emit({type:'tool_call',tool_call_id:'a',result:'hi\n',status:{ok:true,duration_ms:1234}});
  f.emit({type:'tool_command_delta',tool_call_id:'a',delta_seq:2,delta:'late'});
  f.emit({type:'tool_execution_state',tool_call_id:'a',status:'running',args:{command:'wrong'}});
  const tool=f.tools[0];assert.equal(tool.active,false);assert.equal(tool.status,'已完成');assert.equal(tool.durationMs,1234);
  assert.equal(tool.content,'hi\n');assert.equal(tool.commandText,'echo hi');assert.equal(toolOutput(tool),'hi\n');assert.equal(outputCoveredByResult(tool),true);
});
test('interruption freezes incomplete generated parameters and timers',()=>{
  const f=fixture();f.emit({type:'tool_call_delta',id:'a',index:0,name_delta:'run_shell',arguments_delta:'{"command":"'});
  f.emit({type:'run_interrupted'});f.emit({type:'tool_call_delta',id:'a',index:0,arguments_delta:'late'});
  assert.equal(f.tools[0].active,false);assert.equal(f.tools[0].timingActive,false);assert.equal(f.tools[0].status,'已停止');
  assert.equal(f.tools[0].argsText,'{"command":"');assert.equal(f.tools[0].executed,false);
});
test('history prepend reconciles draft and committed call aliases without deleting another tool',()=>{
  const f=fixture();f.emit({type:'tool_call_delta',index:0,id:'a',name_delta:'read_file',arguments_delta:'{}'});
  const old=timelineFromHistory([{type:'user',run_id:'r',content:'hello'},{type:'tool_call',run_id:'r',tool_call_id:'a',result:'ok'}]);
  assert.equal(prependTimeline(f.state,old).turns[0].process.filter(row=>row.kind==='tool').length,1);
});
test('late pending events and recovery never restart a completed turn',()=>{
  const f=fixture();f.emit({type:'final',content:'done'});f.emit({type:'run_finished',result_status:'succeeded'});
  f.emit({type:'tool_pending',tool_call_id:'late',args:{command:'late'}});
  f.emit(toolSnapshotEvent({execution_id:'late',status:'running',output:'late',last_runtime_seq:30}));
  assert.equal(f.tools.length,0);assert.equal(f.state.running,false);assert.equal(f.state.turns[0].status,'succeeded');
});
test('output coverage compares both decorated streams consistently and preserves distinct logs',()=>{
  const outputText='\n实时输出\nfirst\n\nSTDERR:\nwarning\n\nSTDOUT:\nlast\n';
  assert.equal(outputCoveredByResult({outputText,content:outputText+'result metadata'}),true);
  assert.equal(outputCoveredByResult({outputText,content:'Summary only'}),false);
});
