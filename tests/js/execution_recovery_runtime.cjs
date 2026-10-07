const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const root = path.resolve(__dirname, '../..');
const rendering = fs.readFileSync(path.join(root, 'frontend/src/app/modules/message-rendering.js'), 'utf8');
const sse = fs.readFileSync(path.join(root, 'frontend/src/app/modules/sse-handling.js'), 'utf8');
const interactions = fs.readFileSync(path.join(root, 'frontend/src/app/modules/human-interactions.js'), 'utf8');
function section(source, start, end) { return source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start))); }
function node(classes, attrs = {}) {
  const names = new Set(classes.split(' '));
  return {dataset: {...attrs}, children: [], isConnected: true,
    classList: {contains: name => names.has(name), toggle: (name, on) => on ? names.add(name) : names.delete(name)},
    getAttribute(name) { return this.dataset[name.replace(/^data-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase())]; },
    removeAttribute(name) { delete this.dataset[name.replace(/^data-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase())]; },
    remove() { this.removed = true; },
  };
}
async function main() {
  const group = node('process-aggregate', {processGroupId:'turn:1'});
  const rows = [];
  const stream = {children:[group], querySelectorAll(selector) {
    return selector === '.process-aggregate' ? [group] : rows;
  }};
  const ctx = {stream, currentProcessGroup:group};
  const c = vm.createContext({Map, Object, String, Number, Array, JSON, replayingMessages:true,
    findToolCallRow: (_ctx,id) => rows.find(row => row.dataset.toolCallId === id),
    createProcessFeedRow: (_ctx,_type,text) => {
      const row = node('feed-item');
      const sc = {textContent:text, closest: () => row};
      const chunk = node('feed-chunk');
      row.querySelector = selector => selector === '.feed-chunk-scroller' ? sc : chunk;
      row.sc = sc;
      rows.push(row);
      return sc;
    },
    discardPendingToolRowRender(){}, rememberToolStreamRow(){}, truncateLogTextForUi:t=>t,
    removeTemporaryStatus(){},
    refreshFeedChunkOverflow(){}, refreshAggregateStatsSmart(){}, reactGenerationForContext:()=>0, attached:[],
    attachHumanInteractionCardsForToolCall:(_stream,id)=>c.attached.push(id),
  });
  vm.runInContext(section(rendering, 'var executionRecordsBySession', 'function ensureProcessGroup'), c);
  vm.runInContext(section(rendering, 'function formatToolDraftLine', 'function formatToolDoneLine'), c);
  c.renderExecutionEvent(ctx, {type:'tool_call_delta', execution_id:'exec', process_group_id:'turn:1', id:'call', name_delta:'run_shell', arguments_delta:'{"command":', execution_runtime_seq:2}, 's');
  c.renderExecutionEvent(ctx, {type:'tool_pending', execution_id:'exec', process_group_id:'turn:1', tool_call_id:'call', tool:'run_shell', args:{command:'test'}, execution_runtime_seq:3}, 's');
  c.renderExecutionEvent(ctx, {type:'tool_command_delta', execution_id:'exec', process_group_id:'turn:1', tool_call_id:'call', delta:'progress\n', execution_runtime_seq:4}, 's');
  assert.equal(rows.length, 1);
  assert(rows[0].sc.textContent.includes('progress'));
  c.renderExecutionEvent(ctx, {type:'tool_command_delta', execution_id:'exec', process_group_id:'turn:1', tool_call_id:'call', delta:'progress\n', execution_runtime_seq:4}, 's');
  assert.equal(c.executionRecordsBySession.get('s').get('exec').output, 'progress\n');
  c.renderExecutionEvent(ctx, {type:'tool_call', execution_id:'exec', process_group_id:'turn:1', tool_call_id:'call', tool:'run_shell', result:'interrupted result', execution_status:'interrupted', execution_runtime_seq:5,
    run_id:'scope-run', react_iter:2, stream_seq:4}, 's');
  assert.equal(rows.length, 1);
  assert(rows[0].sc.textContent.includes('progress'));
  assert(rows[0].sc.textContent.includes('已中断'));
  assert(c.attached.includes('call'));
  assert.equal(rows[0]._toolCallEvent.run_id, 'scope-run');
  assert.equal(rows[0]._toolCallEvent.react_iter, 2);
  assert.equal(rows[0]._toolCallEvent.stream_seq, 4);
  c.renderExecutionEvent(ctx, {type:'tool_command_delta', execution_id:'exec', process_group_id:'turn:1', tool_call_id:'call', delta:'late output', execution_runtime_seq:6}, 's');
  assert.equal(c.executionRecordsBySession.get('s').get('exec').status, 'interrupted');
  assert(rows[0].sc.textContent.includes('late output'));
  // A fresh DOM/context restores the full record without duplicate output.
  const saved = c.executionRecordsBySession.get('s').get('exec');
  rows.length = 0;
  c.renderExecutionRecord(ctx, saved, 's');
  assert.equal(rows.length, 1);
  assert.equal(rows[0].dataset.executionId, 'exec');
  c.renderExecutionEvent(ctx, {type:'tool_pending', execution_id:'new-exec', process_group_id:'turn:1',
    tool_call_id:'call', tool:'run_shell', args:{command:'second'}, execution_runtime_seq:7}, 's');
  assert.equal(rows.length, 2, 'reusing a provider call ID cannot overwrite another execution');
  assert.equal(rows[0].dataset.executionId, 'exec');
  assert.equal(rows[1].dataset.executionId, 'new-exec');

  // Approval/ask cards follow their execution identity even when call IDs repeat.
  const cards = [{dataset:{toolCallId:'call',executionId:'first'}},
    {dataset:{toolCallId:'call',executionId:'second'}}];
  const humanRows = cards.map(card => ({dataset:{toolCallId:'call',executionId:card.dataset.executionId},
    querySelector() { return this.slot || null; }, appendChild(slot) { this.slot=slot; }}));
  const humanStream = {querySelectorAll:selector => selector === '.feed-item.feed--tool' ? humanRows
    : selector.startsWith('.human-interaction-card') ? cards : []};
  const hc = vm.createContext({Array,String,CSS:{escape:value=>value},window:{CSS:{escape:value=>value}},
    document:{createElement:()=>({children:[],appendChild(card) { this.children.push(card);card.parentNode=this; }})}});
  vm.runInContext(section(interactions, 'function humanInteractionToolRow', 'function humanInteractionFallbackHost'), hc);
  assert.strictEqual(hc.humanInteractionToolRow(humanStream,'call',{execution_id:'second'}),humanRows[1]);
  assert.equal(hc.humanInteractionToolRow(humanStream,'call',{execution_id:'missing'}),null);
  hc.attachHumanInteractionCardsForToolCall(humanStream,'call');
  assert.strictEqual(cards[0].parentNode,humanRows[0].slot);
  assert.strictEqual(cards[1].parentNode,humanRows[1].slot);

  // Adjacent retries/restarts merge, but a user/final boundary never does.
  let registered=0;
  c.unregisterProcessAggregateRow=()=>{};
  c.registerProcessAggregateRow=()=>registered++;
  c.refreshProcessAggregateStats=()=>{};
  const mergedStream={children:[]};
  function aggregate(id, count, duration) {
    const agg=node('process-aggregate',{processGroupId:id,procDurationMs:String(duration)});
    const body={children:Array.from({length:count},()=>node('feed-item')),appendChild(row) {
      this.children.push(row);
    }};
    agg.querySelector=()=>body;
    agg.remove=()=>{mergedStream.children=mergedStream.children.filter(item=>item!==agg);};
    agg.body=body;
    return agg;
  }
  const first=aggregate('turn:1',1,6), retry=aggregate('turn:1',1,4), user=node('msg-wrap--user'),
    afterUser=aggregate('turn:1',1,8), final=node('msg-wrap--assistant'), afterFinal=aggregate('after-final:7',1,9);
  mergedStream.children=[first,retry,user,afterUser,final,afterFinal];
  c.mergeAdjacentExecutionGroups(mergedStream);
  assert.equal(mergedStream.children.length,5);
  assert.equal(first.body.children.length,2);
  assert.equal(first.dataset.procDurationMs,'10');
  assert.equal(registered,1);
  assert(mergedStream.children.includes(afterUser));
  assert(mergedStream.children.includes(afterFinal));
  const restarted={stream:{querySelectorAll:()=>[first,afterFinal]},currentProcessGroup:null};
  c.selectExecutionProcessGroup(restarted,'turn:1');
  assert.strictEqual(restarted.currentProcessGroup,first);
  c.selectExecutionProcessGroup(restarted,'after-final:7');
  assert.strictEqual(restarted.currentProcessGroup,afterFinal);

  const parent = {lastRuntimeSeq:10, streamEventIndex:1};
  let reductions=0, terminals=0, lifecycle=0, updates=0;
  Object.assign(c, {
    TextDecoder, SSE_IDLE_TIMEOUT_MS:1000, readSseChunkWithIdleTimeout: reader => reader.read(),
    sessionStore:{shouldAcceptSseEvent:()=>true},
    consumeExtensionControlEvent:()=>false, shouldApplySseSeqFilter:()=>false,
    noteSubagentLifecycleFrame:()=>lifecycle++, applySessionEvent:()=>{reductions++;return {};},
    updateExecutionRecord:(_sid,update)=>update, renderExecutionRecord:()=>updates++,
    streamHistoryRecoveryBySession:new Set(), endRunForClient:()=>terminals++,
    finalizeLlmStreamChunks(){}, renderMessageRecord(){}, renderExecutionEvent:()=>false,
    scheduleFinalVisibleAfterRunIfEnabled(){},
  });
  vm.runInContext(section(sse, 'async function consumeAgentSseResponseInner', 'function latestVisibleUserEventIndex'), c);
  const events = [
    {type:'run_finished', session_id:'child', agent_id:'child', _subagent_forward:true, run_id:'child-run'},
    {type:'tool_call', session_id:'child', agent_id:'child', _subagent_forward:true, runtime_seq:999, run_id:'child-run'},
    {type:'llm_response_delta', session_id:'other-child', agent_id:'other-child', ephemeral:true, runtime_seq:1000},
    {protocol:'runtime_v2', type:'run_finished', session_id:'child', agent_id:'child', _subagent_forward:true, seq:2000, skip_ui:true},
    {type:'execution_update', session_id:'s', ephemeral:true, runtime_seq:11, update:{execution_id:'exec', output_delta:'saved'}},
  ];
  let read=false;
  const response={ok:true,headers:{get:()=> 'text/event-stream'},body:{getReader:()=>({read:async()=> {
    if(read)return {done:true};read=true;
    return {done:false,value:new TextEncoder().encode(events.map(e=>'data: '+JSON.stringify(e)+'\n').join(''))};
  }})}};
  const endIndex = await c.consumeAgentSseResponseInner(response,parent,'s',1);
  assert.equal(lifecycle,4);
  assert.equal(terminals,0);
  assert.equal(reductions,0);
  assert.equal(updates,1);
  assert.equal(endIndex,1,'execution updates and forwarded events do not occupy UI indexes');
  assert.equal(parent.lastRuntimeSeq,11);
  c.applySessionEvent=()=>({runStateChanged:true});
  let terminalRead=false;
  const terminalResponse={ok:true,headers:{get:()=> 'text/event-stream'},body:{getReader:()=>({read:async()=> {
    if(terminalRead)return {done:true};terminalRead=true;
    return {done:false,value:new TextEncoder().encode('data: '+JSON.stringify({type:'run_finished',session_id:'s',run_id:'root',ephemeral:true})+'\n')};
  }})}};
  assert.equal(await c.consumeAgentSseResponseInner(terminalResponse,parent,'s',1),1,
    'ephemeral parent lifecycle frames do not advance the UI history index');
  assert.equal(terminals,1);
  console.log('execution recovery runtime checks passed');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
