import test from 'node:test';
import assert from 'node:assert/strict';
import {humanEvent,mergeHumans,approvalChoices,questionAnswers,questionError} from '../src/human.mjs';
import {applyTimeline,initialTimeline} from '../src/timeline.mjs';

test('human events keep child session identity and never add empty message turns',()=>{
  const event={type:'interaction_requested',session_id:'child',interaction_id:'ask',questions:[]};
  assert.equal(humanEvent(event,'parent').session_id,'child');assert.equal(humanEvent(event,'parent').status,'pending');
  assert.equal(applyTimeline(initialTimeline(),event).turns.length,0);
});
test('late pending refresh and analysis never reopen a completed card',()=>{
  const row={session_id:'s',kind:'approval',approval_id:'a',request_version:1,status:'resolved',decision:'deny'};
  const rows=mergeHumans([row],[{...row,status:'pending',decision:undefined},{...row,status:'pending',analysis:{reason:'晚到分析'}}]);
  assert.equal(rows.length,1);assert.equal(rows[0].status,'resolved');assert.equal(rows[0].decision,'deny');assert.equal(rows[0].analysis.reason,'晚到分析');
});
test('question editing validates single choice, other text, multi choice and skipping',()=>{
  assert.equal(questionError({multi_select:false},{}),'请选择一个选项。');
  assert.equal(questionError({multi_select:true},{}),'请至少选择一个选项。');
  assert.equal(questionError({}, {selected:['o'],other:true,text:'  '}),'请输入其他答案。');
  assert.equal(questionError({}, {skipped:true}),'');
  const answers=questionAnswers({questions:[{question_id:'q1'},{question_id:'q2'}]}, {answers:{q1:{selected:['o1','o2'],other:true,text:' 写答案 ',notes:' 说明 '},q2:{skipped:true,selected:['old'],text:'old',other:true}}});
  assert.deepEqual(answers[0],{question_id:'q1',selected_option_ids:['o1','o2'],other_text:'写答案',notes:'说明',skipped:false});
  assert.deepEqual(answers[1],{question_id:'q2',selected_option_ids:[],other_text:null,notes:null,skipped:true});
});
test('approval buttons follow server flags, forced confirmation and workspace axes',()=>{
  assert.deepEqual(approvalChoices({force_approval:true,allow_always_available:true}).map(x=>x.decision),['allow_once']);
  assert.deepEqual(approvalChoices({allow_session_available:false}).map(x=>x.decision),['allow_once']);
  assert.deepEqual(approvalChoices({allow_always_available:true,rule_pattern:'git status'}).map(x=>x.decision),['allow_once','allow_always']);
  assert.deepEqual(approvalChoices({external_workspace_grantable:true}).map(x=>x.decision),['allow_external_workspace_once','allow_external_workspace']);
});
