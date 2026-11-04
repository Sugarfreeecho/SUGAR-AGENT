import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {mainFollowModuleSource} from '../scripts/main-smooth-follow.mjs';
import {createTimelineReveal,settleTimelineReveal} from '../src/reveal-timeline.mjs';
import {applyTimeline,initialTimeline,timelineFromHistory} from '../src/timeline.mjs';

const source=(await mainFollowModuleSource()).replace(/export \{[^}]+\};\s*$/,'globalThis.api={computeSmoothRevealCount,takeSmoothTextPrefix};');
const context=vm.createContext({});vm.runInContext(source,context);
const make=()=>{const reveal=createTimelineReveal(context.api);reveal.sync(initialTimeline(),{boundary:'s'});return reveal;};
const apply=(state,event)=>applyTimeline(state,{run_id:'r',react_iter:1,...event});
const sync=(reveal,state,extra={})=>reveal.sync(state,{boundary:'s',...extra});

test('large live chunks reveal across frames with immediate first output and whole Unicode code points',()=>{
  const reveal=make(),text='逐字🙂🚀生成中文和 emoji。'.repeat(20);
  const state=apply(initialTimeline(),{type:'llm_response_delta',delta:text});
  const snapshot=JSON.stringify(state);let view=sync(reveal,state),length=view.turns[0].body.length,frames=0;
  assert.ok(length>0 && length<text.length);assert.equal(state.running,true);
  while(reveal.pending && frames++<150){
    reveal.advance(16.67);view=sync(reveal,state);
    const body=view.turns[0].body;
    assert.ok(body.length>=length && text.startsWith(body));
    assert.ok(!/[\uD800-\uDBFF]$/.test(body));length=body.length;
  }
  assert.ok(frames>5 && frames<150);assert.equal(view.turns[0].body,text);
  assert.equal(JSON.stringify(state),snapshot);
});

test('a first live event can mount a turn directly; restoring that turn instead shows its full snapshot',()=>{
  const state=apply(initialTimeline(),{type:'llm_response_delta',delta:'一次到达的较长文本'.repeat(30)});
  const reveal=createTimelineReveal(context.api);
  assert.ok(sync(reveal,state).turns[0].body.length<state.turns[0].body.length);
  const restored=settleTimelineReveal(state),fresh=createTimelineReveal(context.api);
  assert.equal(sync(fresh,restored).turns[0].body,state.turns[0].body);assert.equal(fresh.pending,false);
  assert.equal(settleTimelineReveal(restored),restored);
});

test('new chunks extend the reveal target without replaying or dropping previous text',()=>{
  const reveal=make();let state=apply(initialTimeline(),{type:'llm_response_delta',delta:'第一块文字'.repeat(30)});
  let view=sync(reveal,state);reveal.advance(16.67);view=sync(reveal,state);const head=view.turns[0].body;
  state=apply(state,{type:'llm_response_delta',delta:'随后继续🙂'.repeat(20)});
  assert.ok(sync(reveal,state).turns[0].body.startsWith(head));
  for(let i=0;i<200 && reveal.pending;i++){reveal.advance(16.67);view=sync(reveal,state);}
  assert.equal(view.turns[0].body,state.turns[0].body);
});

test('history and restored active snapshots appear fully and fresh extensions keep the displayed prefix',()=>{
  const reveal=make();let state=timelineFromHistory([{type:'run_started',run_id:'r'},{type:'llm_response_delta',run_id:'r',react_iter:1,delta:'已恢复的文本'.repeat(20)}]);
  assert.equal(sync(reveal,state).turns[0].body,state.turns[0].body);assert.equal(reveal.pending,false);
  const restored=state.turns[0].body;
  state=apply(state,{type:'llm_response_delta',delta:'新内容'.repeat(20)});
  const body=sync(reveal,state).turns[0].body;
  assert.ok(body.startsWith(restored) && body.length<state.turns[0].body.length);
  assert.equal(sync(reveal,state,{boundary:'reconnected'}).turns[0].body,state.turns[0].body);
  assert.equal(reveal.pending,false);
});

test('thinking and tool parameter and output streams share playback while independent calls stay separate',()=>{
  const reveal=make();let state=apply(apply(initialTimeline(),{type:'run_started'}),{type:'llm_reasoning_delta',delta:'思考中'.repeat(60)});
  let view=sync(reveal,state);assert.ok(view.turns[0].process[0].content.length<state.turns[0].process[0].content.length);
  state=apply(state,{type:'tool_call_delta',tool_call_id:'a',name_delta:'run_shell',arguments_delta:'{"command":"'+'echo 内容'.repeat(40)});
  state=apply(state,{type:'tool_call_delta',tool_call_id:'b',name_delta:'read_file',arguments_delta:'{"path":"'+'path/'.repeat(40)});
  view=sync(reveal,state);
  for(const id of ['a','b'])assert.ok(view.turns[0].process.find(block=>block.id===id).argsText.length<state.turns[0].process.find(block=>block.id===id).argsText.length);
  state=apply(state,{type:'tool_command_delta',tool_call_id:'a',delta:'输出🙂\n'.repeat(50),stream:'stdout'});
  view=sync(reveal,state);assert.ok(view.turns[0].process.find(block=>block.id==='a').outputText.length<state.turns[0].process.find(block=>block.id==='a').outputText.length);
  for(let i=0;i<200 && reveal.pending;i++){reveal.advance(16.67);view=sync(reveal,state);}
  assert.equal(view.turns[0].process.find(block=>block.id==='a').outputText,state.turns[0].process.find(block=>block.id==='a').outputText);
});

test('committed snapshots, final replies and all terminal states drain playback immediately',()=>{
  for(const type of ['run_finished','run_interrupted','run_failed']){
    const reveal=make();let state=apply(initialTimeline(),{type:'llm_response_delta',delta:'尚未播放完'.repeat(50)});
    sync(reveal,state);assert.equal(reveal.pending,true);
    state=apply(state,{type});assert.equal(sync(reveal,state).turns[0].body,state.turns[0].body);assert.equal(reveal.pending,false);
  }
  const reveal=make();let state=apply(initialTimeline(),{type:'llm_reasoning_delta',delta:'思考草稿'.repeat(30)});
  sync(reveal,state);state=apply(state,{type:'llm_reasoning',content:'完整思考'});
  assert.equal(sync(reveal,state).turns[0].process[0].content,'完整思考');assert.equal(reveal.pending,false);
  state=apply(state,{type:'llm_response_delta',delta:'正文'.repeat(100)});sync(reveal,state);
  state=apply(state,{type:'final',content:'**最终答案**'});
  assert.equal(sync(reveal,state).turns[0].final,'**最终答案**');assert.equal(reveal.pending,false);
});

test('reduced motion, hidden views, replacements and session boundaries do not leave old text queued',()=>{
  const reveal=make();let state=apply(initialTimeline(),{type:'llm_response_delta',delta:'待显示'.repeat(100)});
  sync(reveal,state);assert.equal(reveal.pending,true);
  assert.equal(sync(reveal,state,{instant:true}).turns[0].body,state.turns[0].body);assert.equal(reveal.pending,false);
  state=apply(state,{type:'llm_response_delta',delta:'后续'.repeat(50)});sync(reveal,state);
  const corrected={...state,turns:[{...state.turns[0],body:'更正后的完整答案'}]};
  assert.equal(sync(reveal,corrected).turns[0].body,'更正后的完整答案');assert.equal(reveal.pending,false);
  sync(reveal,initialTimeline(),{boundary:'another-session'});reveal.advance(100);
  assert.equal(reveal.pending,false);assert.equal(sync(reveal,initialTimeline(),{boundary:'another-session'}).turns.length,0);
});
