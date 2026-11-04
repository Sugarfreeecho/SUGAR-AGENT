import test from 'node:test';
import assert from 'node:assert/strict';
import {skillDisplayMessage} from '../src/skill-selection.mjs';
import {applicationMethod} from '../src/application-api.mjs';

test('selected Skill display matches the main app and stays idempotent across live history',()=>{
  const message='检查项目',names=['repo-engineering','插件:中文 Skill'];
  const display=skillDisplayMessage(message,names);
  assert.equal(display,'检查项目\n\nActivated Skill: repo-engineering, 插件:中文 Skill');
  assert.equal(skillDisplayMessage(display,names),display);
  assert.equal(skillDisplayMessage(message,[]),message);
});
test('Skill catalog uses the exact read-only application endpoint',()=>{
  assert.equal(applicationMethod('/api/browser/v1/skills'),'GET');
  assert.throws(()=>applicationMethod('/api/browser/v1/skills',{}));
});
