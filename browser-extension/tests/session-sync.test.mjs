import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeSessionMetadata,latestPermission} from '../src/session-sync.mjs';

test('metadata renames active sessions, preserves other fields, and rejects mismatched identity',()=>{
  const rows=[{id:'s',name:'新会话',pinned:true},{id:'other',name:'其他'}];
  const renamed=mergeSessionMetadata(rows,{session_id:'s',session:{id:'s',name:'生成后的标题'}});
  assert.equal(renamed[0].name,'生成后的标题');assert.equal(renamed[0].pinned,true);assert.equal(renamed[1],rows[1]);
  assert.equal(mergeSessionMetadata(rows,{session_id:'s',session:{id:'wrong',name:'错误'}}),rows);
  assert.equal(mergeSessionMetadata(rows,{session_id:'s',deleted:true}).length,1);
});
test('newer live permission mode wins over delayed snapshot while retaining connection capabilities',()=>{
  const fresh={mode:'full_access',updated_at:20};
  const result=latestPermission({mode:'ask_for_approval',updated_at:10,can_change:true},fresh);
  assert.equal(result.mode,'full_access');assert.equal(result.can_change,true);
  assert.equal(latestPermission({mode:'approve_for_me',updated_at:30},fresh).mode,'approve_for_me');
  assert.equal(latestPermission({mode:'ask_for_approval'},{mode:'approve_for_me'}).mode,'approve_for_me');
});

test('selected child metadata updates never insert nested children into the root session list',()=>{
  const root={id:'parent',name:'主会话'},rows=[root];
  assert.deepEqual(mergeSessionMetadata(rows,{session_id:'child',session:{id:'child',name:'子任务',is_subagent:true,parent_session_id:'parent'}}),rows);
  const corrected=mergeSessionMetadata([...rows,{id:'child',name:'旧子任务'}],{session_id:'child',session:{id:'child',name:'子任务',is_subagent:true}});
  assert.deepEqual(corrected,rows);
});
