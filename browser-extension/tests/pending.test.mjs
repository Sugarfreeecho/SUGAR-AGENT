import test from 'node:test';
import assert from 'node:assert/strict';
import {mergePendingMessages,reconcilePendingTurns,pendingRecovery,steerDelivery} from '../src/pending-messages.mjs';
import {initialTimeline,applyTimeline,mergeSteerSnapshot,stageSteerMessage} from '../src/timeline.mjs';

test('queue snapshots keep only unsent optimistic and recoverable rows, never duplicate acknowledgements',()=>{
  const previous=[{clientId:'a',status:'sending'},{operationId:'b',status:'queued'},{operationId:'c',recovery:true}];
  const received=[{clientId:'a',operationId:'server-a',status:'queued'}];
  assert.deepEqual(mergePendingMessages(previous,received),[received[0],previous[2]]);
});
test('queued turn UI facts only fill an existing run with no user; they never manufacture turns or overwrite history',()=>{
  const state=applyTimeline(initialTimeline(),{type:'run_started',run_id:'run'});
  const facts=[{runId:'run',content:'queued text',images:['image']},{runId:'absent',content:'not started'}];
  const filled=reconcilePendingTurns(state,facts);
  assert.equal(filled.turns.length,1);assert.equal(filled.turns[0].user,'queued text');assert.deepEqual(filled.turns[0].images,['image']);
  assert.equal(reconcilePendingTurns(filled,[{...facts[0],content:'stale'}]),filled);
  assert.equal(reconcilePendingTurns(state,[{...facts[0],recovery:true}]),state);
});
test('interrupt mode and images survive a consumption snapshot that arrives before a receipt',()=>{
  let state=applyTimeline(initialTimeline(),{type:'user',run_id:'run',content:'start'});
  state=stageSteerMessage(state,'local','steer','interrupt');
  state=mergeSteerSnapshot(state,[{id:'steer',client_id:'op',ui_content:'steer',mode:'interrupt',state:'consumed',consumed_by:'run',ui_attachments:[{attachmentId:'image'}]}]);
  const block=state.turns[0].process[0];assert.equal(block.mode,'interrupt');assert.deepEqual(block.images,['image']);assert.equal(state.pendingSteers.length,0);
  assert.match(steerDelivery({mode:'interrupt',status:'deferred'},true),/等待/);
});
test('conversion recovery keeps the exact draft and mode across reload and is scoped to the paired browser and session',async()=>{
  const data={'sugar.connection':{browserId:'browser-a'}};
  globalThis.chrome={storage:{local:{async get(key){return {[key]:structuredClone(data[key])};},async set(value){Object.assign(data,structuredClone(value));}}}};
  const item={operationId:'original',draft:{text:'saved',uploads:[{id:'image'}]},recoveryMode:'interrupt'};
  await pendingRecovery('session',item);assert.equal((await pendingRecovery('session'))[0].recoveryMode,'interrupt');
  await pendingRecovery('session',item);assert.equal((await pendingRecovery('session')).length,1);
  assert.deepEqual(await pendingRecovery('other-session'),[]);
  data['sugar.connection']={browserId:'browser-b'};assert.deepEqual(await pendingRecovery('session'),[]);
  data['sugar.connection']={browserId:'browser-a'};await pendingRecovery('session',item,true);assert.deepEqual(await pendingRecovery('session'),[]);
  delete globalThis.chrome;
});
