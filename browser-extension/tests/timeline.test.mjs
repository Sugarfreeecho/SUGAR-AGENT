import test from 'node:test';
import assert from 'node:assert/strict';
import { applyTimeline, buildUserMessage, initialTimeline, timelineFromHistory, prependTimeline, mergeLiveTurns, stageUserMessage, acknowledgeUserMessage, rejectUserMessage } from '../src/timeline.mjs';
import { eventKey } from '../src/shared.mjs';
import { loopbackUrl, ordinaryTab } from '../src/shared.mjs';
import { applicationMethod } from '../src/application-api.mjs';
import { relativeSessionTime } from '../src/session-time.mjs';

test('streaming keeps historical turns and unchanged tools stable without mutating earlier state',()=>{
  let state=timelineFromHistory([
    {type:'user',run_id:'old',content:'历史任务'},
    {type:'final',run_id:'old',content:'历史回答'},
    {type:'run_started',run_id:'live'},
    {type:'tool_call',run_id:'live',tool_call_id:'tool',tool:'run_shell',result:'result',execution_status:'completed'},
  ]);
  const previous=state,historical=state.turns[0],tool=state.turns[1].process[0];
  const snapshot=JSON.stringify(previous);
  Object.freeze(historical);Object.freeze(tool);
  state=applyTimeline(state,{type:'llm_reasoning_delta',run_id:'live',react_iter:2,delta:'思考'});
  assert.equal(state.turns[0],historical);
  assert.notEqual(state.turns[1],previous.turns[1]);
  assert.equal(state.turns[1].process[0],tool);
  assert.equal(JSON.stringify(previous),snapshot);
  const thinking=state,reason=state.turns[1].process.at(-1),reasonBefore=JSON.stringify(reason);
  Object.freeze(reason);
  state=applyTimeline(state,{type:'llm_response_delta',run_id:'live',react_iter:2,delta:'正文'});
  assert.equal(state.turns[0],historical);
  assert.equal(state.turns[1].process[0],tool);
  assert.equal(JSON.stringify(thinking.turns[1].process.at(-1)),reasonBefore);
  assert.equal(state.turns[1].process.at(-1).active,false);
  const metadata=applyTimeline(state,{type:'context_tokens',estimated:1000});
  assert.equal(metadata.turns,state.turns);
});

test('tool and terminal updates copy the affected process state and retain other turns',()=>{
  let state=timelineFromHistory([{type:'user',run_id:'old',content:'历史'}, {type:'final',run_id:'old',content:'完成'}]);
  state=applyTimeline(state,{type:'run_started',run_id:'live'});
  state=applyTimeline(state,{type:'tool_execution_state',run_id:'live',tool_call_id:'tool',tool:'run_shell',status:'running'},undefined,{now:1000});
  const previous=state,snapshot=JSON.stringify(previous),block=state.turns[1].process[0];
  Object.freeze(block);
  state=applyTimeline(state,{type:'run_interrupted',run_id:'live'},undefined,{now:2000});
  assert.equal(state.turns[0],previous.turns[0]);
  assert.notEqual(state.turns[1].process[0],block);
  assert.equal(state.turns[1].process[0].active,false);
  assert.equal(JSON.stringify(previous),snapshot);
});

test('restarting the backend cannot reuse a durable history identity for a new unsequenced live reply',()=>{
  const history=[{type:'user',run_id:'old',content:'old',runtime_seq:2},{type:'final',run_id:'old',content:'old answer',runtime_seq:3}];
  let state=timelineFromHistory(history,0,'session');
  const event={type:'final',run_id:'new',content:'new answer',event_bus_epoch:'new-process',event_bus_seq:3};
  assert.notEqual(eventKey(event,'session'),eventKey(history[1],'session'));
  state=applyTimeline(state,event,eventKey(event,'session'));
  assert.equal(state.turns.at(-1).final,'new answer');
  assert.notEqual(eventKey(event,'session'),eventKey({...event,event_bus_epoch:'another-process'},'session'));
});

test('workspace compatibility uses the same exact endpoints and HTTP methods as the worker', () => {
  assert.equal(applicationMethod('/api/browser/v1/workspaces'), 'GET');
  assert.equal(applicationMethod('/api/browser/v1/workspaces/validate', {path:'D:/test'}), 'POST');
  for (const path of ['/api/control/v1/rpc', '/api/browser/v1/workspaces?other=1', 'http://remote.test']) assert.throws(() => applicationMethod(path));
  assert.throws(() => applicationMethod('/api/browser/v1/workspaces', {}));
  assert.throws(() => applicationMethod('/api/browser/v1/workspaces/pick'));
});

test('session relative times follow the main UI units and activity timestamp priority', () => {
  const now = Date.parse('2026-10-30T02:00:00+08:00');
  assert.equal(relativeSessionTime({updated_at:new Date(now-20000).toISOString()},now),'刚刚');
  assert.equal(relativeSessionTime({updated_at:new Date(now-180000).toISOString()},now),'3分钟');
  assert.equal(relativeSessionTime({last_activity_at:new Date(now-7200000).toISOString(),updated_at:new Date(now).toISOString()},now),'2小时');
  assert.equal(relativeSessionTime({created_at:new Date(now-86400000).toISOString()},now,true),'1d');
});

test('reasoning completion is independent of run completion and full snapshots deduplicate', () => {
  let state=applyTimeline(initialTimeline(),{type:'run_started',run_id:'r'});
  state=applyTimeline(state,{type:'llm_reasoning_delta',run_id:'r',react_iter:2,delta:'思考原文'});
  assert.equal(state.turns[0].process[0].active,true);
  state=applyTimeline(state,{type:'llm_reasoning',run_id:'r',react_iter:2,content:'思考原文'});
  assert.equal(state.turns[0].process.length,1); assert.equal(state.turns[0].process[0].active,false);
  state=applyTimeline(state,{type:'llm_response',run_id:'r',react_iter:2,reasoning:'思考原文',content:'回答'});
  assert.equal(state.turns[0].process.length,1); assert.equal(state.running,true);
  state=applyTimeline(state,{type:'llm_reasoning_delta',run_id:'r',react_iter:3,delta:'下一步'});
  state=applyTimeline(state,{type:'llm_response_delta',run_id:'r',delta:'正文'});
  assert.equal(state.turns[0].process.at(-1).active,false);
});

test('early tool execution and its later committed response share one answer before the tool', () => {
  const text='解压完成，我核对一下源码结构。';
  let state=initialTimeline();
  for(const event of [
    {type:'run_started'},
    {type:'llm_reasoning_delta',react_iter:2,delta:'检查解压结果'},
    {type:'llm_response_delta',react_iter:2,stream_seq:8,delta:text},
    {type:'tool_pending',react_iter:2,tool_call_id:'shell',tool:'run_shell'},
    {type:'llm_response',react_iter:2,content:text,metadata:{live_commit:true}},
    {type:'tool_execution_state',react_iter:2,tool_call_id:'shell',tool:'run_shell',status:'running'},
    {type:'tool_call',react_iter:2,tool_call_id:'shell',tool:'run_shell',result:'src/',execution_status:'completed'},
    {type:'llm_reasoning_delta',react_iter:3,delta:'继续检查'},
  ]) state=applyTimeline(state,{...event,run_id:'r'});
  assert.deepEqual(state.turns[0].process.map(block=>block.kind),['reason','answer','tool','reason']);
  assert.deepEqual(state.turns[0].process.filter(block=>block.kind==='answer').map(block=>block.content),[text]);
  assert.equal(state.turns[0].body,'');
});

test('late snapshots replace the matching phase without moving text after tools or overwriting a newer response', () => {
  let state=initialTimeline();
  for(const event of [
    {type:'llm_response_delta',react_iter:1,delta:'检查'},
    {type:'tool_pending',react_iter:1,tool_call_id:'one',tool:'read_file'},
    {type:'llm_response_delta',react_iter:1,delta:'源码'},
    {type:'llm_response',react_iter:1,content:'检查源码。'},
    {type:'llm_response_delta',react_iter:2,delta:'下一轮正文'},
    {type:'tool_execution_state',react_iter:1,tool_call_id:'one',status:'completed'},
    {type:'llm_response',react_iter:1,content:'检查源码。'},
  ]) state=applyTimeline(state,{...event,run_id:'r'});
  assert.deepEqual(state.turns[0].process.map(block=>block.kind),['answer','tool']);
  assert.equal(state.turns[0].process[0].content,'检查源码。');
  assert.equal(state.turns[0].body,'下一轮正文');
  state=applyTimeline(state,{type:'llm_response_delta',run_id:'r',react_iter:1,delta:'过期增量'});
  assert.equal(state.turns[0].process[0].content,'检查源码。');
  assert.equal(state.turns[0].body,'下一轮正文');
  state=applyTimeline(state,{type:'llm_reasoning_delta',run_id:'r',react_iter:3,delta:'第三轮思考'});
  state=applyTimeline(state,{type:'llm_response',run_id:'r',react_iter:1,content:'检查源码。'});
  assert.equal(state.turns[0].process.at(-1).active,true,'An old response must not collapse newer reasoning');
});

test('identical text from different iterations and runs remains visible and history replay stays stable', () => {
  const text='继续检查。';
  const events=[
    {type:'user',run_id:'r',content:'任务'},
    {type:'llm_response',run_id:'r',react_iter:1,content:text,runtime_seq:1},
    {type:'tool_call',run_id:'r',react_iter:1,tool_call_id:'one',tool:'read_file'},
    {type:'llm_response',run_id:'r',react_iter:2,content:text,runtime_seq:3},
    {type:'tool_call',run_id:'r',react_iter:2,tool_call_id:'two',tool:'run_shell'},
  ];
  let state=timelineFromHistory(events,0,'session');
  state=applyTimeline(state,{...events[1],runtime_seq:20},'recommitted-response');
  assert.deepEqual(state.turns[0].process.filter(block=>block.kind==='answer').map(block=>block.content),[text,text]);
  state=applyTimeline(state,{type:'llm_response',run_id:'other',react_iter:1,content:text});
  assert.equal(state.turns[1].body,text);
});

test('a committed response arriving after the tool is inserted before it during history hydration', () => {
  const state=timelineFromHistory([
    {type:'user',run_id:'r',content:'任务'},
    {type:'tool_call',run_id:'r',react_iter:2,tool_call_id:'shell',tool:'run_shell'},
    {type:'llm_response',run_id:'r',react_iter:2,content:'工具前的说明'},
    {type:'final',run_id:'r',content:'完成'},
  ]);
  assert.deepEqual(state.turns[0].process.map(block=>block.kind),['answer','tool']);
  assert.equal(state.turns[0].process[0].content,'工具前的说明');
});

test('pending user bubble survives admission and reconciles when run starts before the user event', () => {
  let state = stageUserMessage(initialTimeline(), 'client', '立即显示');
  state = acknowledgeUserMessage(state, 'client', { operation_id: 'operation' });
  assert.equal(state.turns[0].user, '立即显示'); assert.equal(state.turns[0].status, 'queued');
  state = applyTimeline(state, { type: 'run_started', run_id: 'run', operation_id: 'operation' });
  state = applyTimeline(state, { type: 'user', run_id: 'run', content: '立即显示' });
  assert.equal(state.turns.length, 1); assert.equal(state.turns[0].pending, false); assert.equal(state.turns[0].user, '立即显示');
});

test('user event before send receipt does not duplicate the optimistic bubble', () => {
  let state = stageUserMessage(initialTimeline(), 'client', '提交消息');
  state = applyTimeline(state, { type: 'user', run_id: 'run', content: '提交消息' });
  state = acknowledgeUserMessage(state, 'client', { operation_id: 'operation' });
  assert.equal(state.turns.length, 1); assert.equal(state.turns[0].pending, false);
});

test('a rejected send removes its pending bubble and retains earlier messages', () => {
  const original = timelineFromHistory([{ type: 'user', run_id: 'old', content: '旧消息' }]);
  const state = rejectUserMessage(stageUserMessage(original, 'client', '拒绝的消息'), 'client');
  assert.equal(state.turns.length, 1); assert.equal(state.turns[0].user, '旧消息');
});

test('production history status objects become renderable labels and retain real tool names', () => {
  let state = timelineFromHistory([
    { type: 'user', run_id: 'r', content: '检查文件' },
    { type: 'tool_call', run_id: 'r', tool: 'read_file', tool_call_id: 'call', result: '文件内容', status: { ok: true, truncated: false, timed_out: false, source: 'tool', duration_ms: 12 } },
    { type: 'final', run_id: 'r', content: '已检查' },
  ]);
  assert.equal(state.turns[0].process[0].title, 'read_file');
  assert.equal(state.turns[0].process[0].status, '已完成');
  state = applyTimeline(state, { type: 'tool_call', run_id: 'r', tool: 'run_shell', tool_call_id: 'failed', result: '未执行', status: { ok: false } }, 'failed');
  assert.equal(state.turns[0].process[1].status, '执行失败');
});

test('final text alone never closes a live turn; only the terminal event folds it', () => {
  let state = initialTimeline();
  for (const [index, event] of [
    { type: 'user', content: '任务', run_id: 'r' },
    { type: 'run_started', run_id: 'r', ephemeral: true },
    { type: 'llm_reasoning_delta', delta: '思考原文', run_id: 'r', ephemeral: true },
    { type: 'final', content: '最终回答', run_id: 'r' },
  ].entries()) state = applyTimeline(state, event, 'e' + index);
  assert.equal(state.turns[0].status, 'running');
  assert.equal(state.turns[0].process[0].content, '思考原文');
  state = applyTimeline(state, { type: 'run_finished', run_id: 'r' }, 'terminal');
  assert.equal(state.turns[0].status, 'succeeded');
  const late = applyTimeline(state, { type: 'llm_response_delta', delta: '旧事件', run_id: 'r', ephemeral: true }, 'late');
  assert.equal(late.running, false);
  assert.equal(late.turns[0].body, '');
});

test('replay of a persisted user fact does not create another user turn', () => {
  let state = timelineFromHistory([{ type: 'user', content: '你好', run_id: 'r' }, { type: 'final', content: '回答', run_id: 'r' }]);
  state = applyTimeline(state, { type: 'user', content: '你好', run_id: 'r' }, 'bus:123');
  assert.equal(state.turns.length, 1);
  assert.equal(state.turns[0].final, '回答');
});

test('an informational error does not claim the running turn has ended', () => {
  let state = applyTimeline(initialTimeline(), { type: 'run_started', run_id: 'r' });
  state = applyTimeline(state, { type: 'error', content: '提供者重试', run_id: 'r' });
  assert.equal(state.running, true);
  assert.equal(state.turns[0].status, 'running');
  state = applyTimeline(state, { type: 'run_failed', reason: '服务失败', run_id: 'r' });
  assert.equal(state.running, false);
  assert.equal(state.turns[0].status, 'failed');
});

test('webpage snapshots are explicit external data and are immutable message text', () => {
  const pages = [{ title: '示例', url: 'https://example.test', text: '正文', capturedAt: '2026-10-29' }];
  const message = buildUserMessage('总结', pages);
  pages[0].text = '之后的网页内容';
  assert.match(message, /外部数据/);
  assert.match(message, /正文/);
  assert.doesNotMatch(message, /之后的网页内容/);
});

test('connection URLs are loopback-only; internal and private tabs stay outside discovery', () => {
  assert.equal(loopbackUrl('http://127.0.0.1:8192').hostname, '127.0.0.1');
  for (const url of ['https://remote.test', 'http://127.0.0.1.attacker.test', 'http://user:pass@127.0.0.1', 'file:///tmp/a']) assert.throws(() => loopbackUrl(url));
  assert.equal(ordinaryTab({ url: 'https://example.test' }), true);
  assert.equal(ordinaryTab({ url: 'chrome://settings' }), false);
  assert.equal(ordinaryTab({ url: 'https://example.test', incognito: true }), false);
});

test('history and live facts deduplicate with the same durable identity', () => {
  const event = { type: 'llm_response', run_id: 'r', runtime_seq: 12, content: '过程文字' };
  const state = timelineFromHistory([event], 0, 'session');
  const replayed = applyTimeline(state, event, eventKey(event, 'session'));
  assert.equal(replayed, state);
});

test('loading older messages preserves the active live draft and terminal state', () => {
  const old = timelineFromHistory([{ type: 'user', run_id: 'old', content: '更早的任务' }, { type: 'final', run_id: 'old', content: '旧结果' }]);
  let live = applyTimeline(initialTimeline(), { type: 'run_started', run_id: 'live' });
  live = applyTimeline(live, { type: 'llm_response_delta', run_id: 'live', delta: '正在输出的正文' });
  const combined = prependTimeline(live, old);
  assert.equal(combined.turns.length, 2);
  assert.equal(combined.turns[1].body, '正在输出的正文');
  assert.equal(combined.running, true);
});

test('structured images survive shared history projection without exposing payloads', () => {
  const content = [{ type: 'text', text: '参考图片' }, { type: 'image', attachment: { attachmentId: 'stored-image' } }];
  const state = timelineFromHistory([{ type: 'user', run_id: 'r', content }, { type: 'tool_call', run_id: 'r', name: 'browser_take_screenshot', content }, { type: 'final', run_id: 'r', content }]);
  assert.equal(state.turns[0].user, '参考图片');
  assert.deepEqual(state.turns[0].images, ['stored-image']);
  assert.deepEqual(state.turns[0].process[0].images, ['stored-image']);
  assert.deepEqual(state.turns[0].finalImages, ['stored-image']);
});

test('transient activity replaces older status and clears when actual output arrives', () => {
  let state = applyTimeline(initialTimeline(), {type:'run_started',run_id:'r'});
  for (let i=0;i<20;i++) state=applyTimeline(state,{type:'status',run_id:'r',content:'正在思考中 '+i});
  assert.equal(state.turns[0].process.length,0);
  assert.equal(state.turns[0].transient,'正在思考中 19');
  state=applyTimeline(state,{type:'llm_response_delta',run_id:'r',delta:'正文'});
  assert.equal(state.turns[0].transient,'');
  state=applyTimeline(state,{type:'tool_call',run_id:'r',tool_call_id:'tool',tool:'read_file',content:'内容'});
  assert.equal(state.turns[0].process[0].kind,'answer');
  assert.equal(state.turns[0].process[0].content,'正文');
  state=applyTimeline(state,{type:'run_finished',run_id:'r'});
  state=applyTimeline(state,{type:'status',run_id:'r',content:'过期的正在思考'});
  assert.equal(state.turns[0].transient,'');
});

test('context and permissions metadata do not create empty turns and usage survives new facts', () => {
  let state=applyTimeline(initialTimeline(),{type:'context_tokens',estimated:4000,threshold:128000});
  state=applyTimeline(state,{type:'permission_mode_changed',mode:'ask_for_approval'});
  assert.equal(state.turns.length,0);
  state=applyTimeline(state,{type:'user',run_id:'r',content:'任务'});
  assert.equal(state.usage.estimated,4000);
});

test('structured files and provider images render as Markdown references without dropping content', () => {
  const content=[{type:'text',text:'**结果**'}, {type:'local_file',path:'docs/计划.md'}, {type:'file',attachment:{attachmentId:'file-id',name:'report.txt'}}, {type:'image_url',image_url:{url:'https://example.test/image.png'}}];
  const state=timelineFromHistory([{type:'user',run_id:'r',content:'任务'},{type:'final',run_id:'r',content}]);
  assert.match(state.turns[0].final,/\*\*结果\*\*/);
  assert.match(state.turns[0].final,/docs\/%E8%AE%A1%E5%88%92.md/);
  assert.match(state.turns[0].final,/attachment:file-id/);
  assert.match(state.turns[0].final,/!\[图片\]\(https:\/\/example.test\/image.png\)/);
});

test('history reload keeps a live run that the snapshot has not committed yet', () => {
  let live=applyTimeline(initialTimeline(),{type:'user',run_id:'live-run',content:'主程序发的消息'});
  live=applyTimeline(live,{type:'run_started',run_id:'live-run'});
  const snapshot=timelineFromHistory([{type:'user',run_id:'old',content:'旧消息'},{type:'final',run_id:'old',content:'旧回答'}]);
  const merged=mergeLiveTurns(snapshot,live);
  assert.equal(merged.turns.length,2);
  assert.equal(merged.turns.at(-1).user,'主程序发的消息');
  assert.equal(merged.turns.at(-1).status,'running');
});

test('history reload fills a snapshot turn whose user fact had not arrived', () => {
  const live=applyTimeline(initialTimeline(),{type:'user',run_id:'r',content:'没进快照的消息'});
  const snapshot=applyTimeline(timelineFromHistory([]),{type:'run_started',run_id:'r'});
  assert.equal(snapshot.turns[0].user,'');
  const merged=mergeLiveTurns(snapshot,live);
  assert.equal(merged.turns.length,1);
  assert.equal(merged.turns[0].user,'没进快照的消息');
});

test('history reload still drops finished turns that the snapshot owns', () => {
  const previous=timelineFromHistory([{type:'user',run_id:'done',content:'已完成'}]);
  const next=timelineFromHistory([{type:'user',run_id:'done',content:'已完成'},{type:'final',run_id:'done',content:'结果'}]);
  const merged=mergeLiveTurns(next,previous);
  assert.equal(merged,next);
});
