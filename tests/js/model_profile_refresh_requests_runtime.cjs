const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../frontend/src/app/modules/model-profiles.js'), 'utf8');
const fn = name => source.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'))[0];
const tick = () => new Promise(resolve => setImmediate(resolve));
const profiles = {ok:true, profiles:[{id:'p1'},{id:'p2'}],new_session_default_profile_id:'p1'};
function fixture() {
  let time = 100000;
  const calls=[], rendered=[];
  const context=vm.createContext({
    console, Promise, Date:{now:()=>time}, currentSessionId:'A',
    modelProfilesCache:profiles,modelProfilesLoadedAt:time,modelProfilesLoadPromise:null,
    MODEL_PROFILES_CACHE_TTL_MS:30000,modelProfileIdBySession:{A:'p1'},
    modelProfileSelectionEpoch:0,modelProfilesRefreshPromises:{},activeModelProfileId:'p1',
    els:()=>({control:{}}),newSessionModelProfileId:()=>'',h:s=>s,
    renderModelProfileControl:()=>rendered.push(context.activeModelProfileId),
    fetch:url=>new Promise(resolve=>calls.push({url,resolve})),
  });
  vm.runInContext(['loadModelProfilesForSwitcher','refreshModelProfileSelector',
    'refreshModelProfileSelectorInBackground','noteModelBindingChanged'].map(fn).join('\n'),context);
  return {context,calls,rendered,advance:n=>{time+=n;},reply:(i,data)=>calls[i].resolve({json:async()=>data})};
}
(async()=>{
  let f=fixture(),ctx={};
  let promise=f.context.noteModelBindingChanged('A',ctx,'closed');
  await tick();
  assert.equal(f.calls.length,1);assert.equal(f.calls[0].url,'/sessions/A/model_profile');
  f.reply(0,{ok:true,profile_id:'p1'});await promise;

  f=fixture();ctx={};
  await f.context.noteModelBindingChanged('A',ctx,'pending');
  assert.equal(f.calls.length,0,'pre-binding status must not fetch');
  promise=f.context.noteModelBindingChanged('A',ctx,'bound');await tick();
  const close=f.context.noteModelBindingChanged('A',ctx,'closed');
  assert.equal(f.calls.length,1,'bound and close share the in-flight GET');
  f.reply(0,{ok:true,profile_id:'p2'});await Promise.all([promise,close]);
  await f.context.noteModelBindingChanged('A',ctx,'closed');
  assert.equal(f.calls.length,1,'verified binding is not fetched again at close');
  assert.deepEqual(f.rendered,['p2']);

  f=fixture();ctx={};
  await f.context.noteModelBindingChanged('A',ctx,'pending');
  promise=f.context.noteModelBindingChanged('A',ctx,'closed');await tick();
  f.reply(0,{ok:true,profile_id:'p2'});await promise;
  assert.equal(f.calls.length,1,'close recovers when the authoritative notice is missing');

  f=fixture();ctx={};
  promise=f.context.noteModelBindingChanged('A',ctx,'bound');await tick();
  const retry=f.context.noteModelBindingChanged('A',ctx,'closed');
  f.reply(0,{ok:false,error:'temporary failure'});await tick();
  assert.equal(f.calls.length,2,'close retries one failed authoritative read');
  f.reply(1,{ok:true,profile_id:'p2'});await Promise.all([promise,retry]);
  assert.equal(f.context.activeModelProfileId,'p2');

  f=fixture();f.advance(30001);
  const list1=f.context.loadModelProfilesForSwitcher();
  const list2=f.context.loadModelProfilesForSwitcher();
  assert.equal(f.calls.length,1,'expired list reads coalesce');
  f.reply(0,profiles);await Promise.all([list1,list2]);
  await f.context.loadModelProfilesForSwitcher();
  assert.equal(f.calls.length,1,'fresh list is reused');
  const forced=f.context.loadModelProfilesForSwitcher(true);
  assert.equal(f.calls.length,2,'explicit configuration change bypasses TTL');
  f.reply(1,profiles);await forced;
  console.log('model profile refresh request checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
