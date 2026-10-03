const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const source = process.env.UI_REVIEW_REF
    ? execFileSync('git', ['show', `${process.env.UI_REVIEW_REF}:frontend/src/app/modules/model-profiles.js`], { encoding: 'utf8' })
    : fs.readFileSync(path.join(__dirname, '../../frontend/src/app/modules/model-profiles.js'), 'utf8');
const fn = name => source.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'))[0];
const tick = () => new Promise(resolve => setImmediate(resolve));
function fixture() {
    const calls = [], rendered = [];
    const context = vm.createContext({
        console, Promise, currentSessionId: 'A', modelProfilesCache: {},
        modelProfileIdBySession: {}, modelReasoningEffortBySession: {}, modelProfileSelectionEpoch: 0,
        activeModelProfileId: 'old', modelProfilesRefreshPromises: {},
        els: () => ({ control: {} }), loadModelProfilesForSwitcher: async () => {},
        renderModelProfileControl: () => rendered.push(context.activeModelProfileId),
        fetch: url => new Promise(resolve => calls.push({ url, resolve })),
        newSessionModelProfileId: () => '', h: s => s,
    });
    vm.runInContext(fn('refreshModelProfileSelector') + '\n' + fn('refreshModelProfileSelectorInBackground'), context);
    return { context, calls, rendered };
}
function refresh(f, sid = 'A', invalidate = false) {
    return f.context.refreshModelProfileSelectorInBackground(sid, { silent: true, invalidate });
}
function resolve(f, index, profile) {
    f.calls[index].resolve({ json: async () => ({ ok: true, profile_id: profile }) });
}
(async () => {
    let f = fixture();
    const first = refresh(f);
    await tick();
    assert.equal(refresh(f), first, 'ordinary refreshes coalesce');
    const bound = refresh(f, 'A', true);
    refresh(f, 'A', true);
    resolve(f, 0, 'old');
    await tick();
    assert.deepEqual(f.rendered, [], 'pre-bind response must not render');
    assert.equal(f.context.modelProfileIdBySession.A, undefined, 'stale response must not poison cache');
    assert.equal(f.calls.length, 2, 'authority changes require one trailing GET');
    resolve(f, 1, 'new-A');
    await Promise.all([first, bound]);
    assert.deepEqual(f.rendered, ['new-A']);
    assert.equal(f.context.modelProfileIdBySession.A, 'new-A');

    f = fixture();
    const active = refresh(f);
    await tick();
    await refresh(f, 'B', true);
    assert.equal(f.calls.length, 1, 'background session must not supersede active refresh');
    resolve(f, 0, 'new-A');
    await active;
    assert.deepEqual(f.rendered, ['new-A']);

    f = fixture();
    const oldRequest = refresh(f);
    await tick();
    const dirty = refresh(f, 'A', true);
    // A newer manual selection wins over both the old request and its queued recheck.
    f.context.modelProfileSelectionEpoch += 1;
    f.context.activeModelProfileId = 'manual';
    f.context.modelProfileIdBySession.A = 'manual';
    resolve(f, 0, 'old');
    await Promise.all([oldRequest, dirty]);
    assert.equal(f.calls.length, 1);
    assert.equal(f.context.activeModelProfileId, 'manual');
    assert.equal(f.context.modelProfileIdBySession.A, 'manual');
    assert.deepEqual(f.rendered, []);

    f = fixture();
    const leaving = refresh(f);
    await tick();
    refresh(f, 'A', true);
    f.context.currentSessionId = 'B';
    const entering = refresh(f, 'B');
    await tick();
    resolve(f, 1, 'new-B');
    await entering;
    resolve(f, 0, 'old-A');
    await leaving;
    assert.equal(f.calls.length, 2, 'leaving session must not queue a late recheck');
    assert.deepEqual(f.rendered, ['new-B']);
    console.log('model profile refresh race checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
