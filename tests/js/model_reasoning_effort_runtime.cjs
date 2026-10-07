const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../frontend/src/app/modules/model-profiles.js'), 'utf8');
const sessions = fs.readFileSync(path.join(__dirname, '../../frontend/src/app/modules/session-management.js'), 'utf8');
const fn = (text, name) => text.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'))[0];
const calls = [], storage = new Map(), pending = [];
const ctx = vm.createContext({
    console, currentSessionId: '', modelProfileSelectionEpoch: 0,
    MODEL_REASONING_EFFORTS: ['low', 'medium', 'high', 'xhigh', 'max'],
    LS_NEW_SESSION_REASONING_EFFORT: 'draft-effort', modelReasoningEffortBySession: {}, modelReasoningEffortBusy: {},
    localStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
    document: { getElementById: () => null }, renderModelProfileControl: () => {},
    newSessionModelProfileId: () => 'p1', selectedNewSessionPermissionMode: () => 'ask_for_approval',
    newSessionWorkDirTarget: () => '',
    fetch: (url, options) => new Promise(resolve => { calls.push({url, body: JSON.parse(options.body)}); pending.push(resolve); }),
});
vm.runInContext(['newSessionReasoningEffort', 'commitNewSessionReasoningEffort', 'currentSessionReasoningEffort', 'setCurrentSessionReasoningEffort'].map(name => fn(source, name)).join('\n') +
    '\n' + fn(sessions, 'collectNewSessionCreateOptions') + '\n' + fn(sessions, 'applyNewSessionOptionsToLegacyBackend'), ctx);
const plain = value => JSON.parse(JSON.stringify(value));
const resolve = index => pending[index]({ok: true, json: async () => ({ok: true})});
(async () => {
    await ctx.setCurrentSessionReasoningEffort('xhigh');
    assert.equal(calls.length, 0, 'draft changes must not mutate an existing session');
    assert.equal(ctx.currentSessionReasoningEffort(), 'xhigh');
    assert.equal(ctx.collectNewSessionCreateOptions().reasoning_effort, 'xhigh');
    ctx.commitNewSessionReasoningEffort('A');
    assert.equal(storage.size, 0);
    ctx.currentSessionId = 'A';
    assert.equal(ctx.currentSessionReasoningEffort(), 'xhigh');
    const saving = ctx.setCurrentSessionReasoningEffort('max');
    await ctx.setCurrentSessionReasoningEffort('low');
    assert.equal(calls.length, 1, 'only one change may be pending for the same session');
    assert.deepEqual(calls[0], { url: '/sessions/A/reasoning_effort', body: {reasoning_effort: 'max'} });
    resolve(0); await saving;
    assert.equal(ctx.modelReasoningEffortBySession.A, 'max');
    assert.equal(ctx.modelProfileSelectionEpoch, 1, 'a late model-binding GET must not overwrite the chosen effort');
    const restore = ctx.setCurrentSessionReasoningEffort('');
    resolve(1); await restore;
    assert.equal(ctx.currentSessionReasoningEffort(), '');
    const legacy = ctx.applyNewSessionOptionsToLegacyBackend('B', { reasoning_effort: 'medium' }, {});
    assert.deepEqual(calls[2], { url: '/sessions/B/reasoning_effort', body: {reasoning_effort: 'medium'} });
    resolve(2); await legacy;
    await ctx.applyNewSessionOptionsToLegacyBackend('B', {reasoning_effort: 'medium'}, {reasoning_effort: 'medium'});
    assert.equal(calls.length, 3, 'new servers must not receive duplicate writes');
    storage.set('draft-effort', 'obsolete-value');
    assert.equal(ctx.newSessionReasoningEffort(), '');
    console.log('reasoning effort draft, persistence and refresh checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
