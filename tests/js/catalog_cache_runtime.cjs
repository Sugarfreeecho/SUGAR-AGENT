const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'app/templates/static/settings/resource_cache.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));
function fixture() {
    let now = 100000;
    const requests = [], events = {}, stored = [];
    const context = vm.createContext({
        console, AbortController, setTimeout, clearTimeout, Date: { now: () => now }, Math,
        CustomEvent: function (type, init) { this.type = type; this.detail = init.detail; },
        location: { origin: 'http://fixture.test' },
        addEventListener(type, fn) { events[type] = fn; }, dispatchEvent() {},
        localStorage: { setItem: (...args) => stored.push(args) },
        fetch: (url, options) => new Promise((resolve, reject) => {
            requests.push({ url, resolve: data => resolve({ ok: true, json: async () => data }), reject });
            options.signal.addEventListener('abort', () => reject(new Error('timeout')));
        }),
    });
    context.window = context; context.parent = context;
    vm.runInContext(source, context);
    return { context, cache: context.MyAgentResourceCache, requests, events, stored, advance: ms => now += ms };
}

(async () => {
    const f = fixture();
    const first = f.cache.get('/api/skills'), second = f.cache.get('/api/skills');
    assert.equal(f.requests.length, 1, 'concurrent consumers share one request');
    f.requests[0].resolve({ ok: true, skills: [{ name: 'alpha', enabled: true }] });
    const [a, b] = await Promise.all([first, second]);
    a.skills[0].enabled = false;
    assert.equal(b.skills[0].enabled, true, 'forms cannot mutate another consumer’s cache');
    assert.equal((await f.cache.get('/api/skills')).skills[0].enabled, true);
    assert.equal(f.requests.length, 1, 'fresh catalog does not refetch');
    f.advance(30001);
    const expired = f.cache.get('/api/skills');
    assert.equal(f.requests.length, 2);
    f.requests[1].resolve({ ok: true, skills: [] }); await expired;

    const old = f.cache.get('/api/extensions');
    f.cache.invalidate('/api/extensions');
    const newer = f.cache.get('/api/extensions');
    f.requests[3].resolve({ ok: true, revision: 'new' }); await newer;
    f.requests[2].resolve({ ok: true, revision: 'old' });
    assert.equal((await old).revision, 'new', 'a save invalidates even an in-flight response');
    assert.equal((await f.cache.get('/api/extensions')).revision, 'new');

    const failed = f.cache.get('/api/model_profiles');
    f.requests[4].reject(new Error('offline')); await assert.rejects(failed, /offline/);
    const retry = f.cache.get('/api/model_profiles');
    f.requests[5].resolve({ ok: true, profiles: [] }); await retry;
    assert.equal(f.requests.length, 6, 'failures remain retryable');
    await assert.rejects(f.cache.get('/api/env'), /Unsupported catalog/);
    assert(f.stored.every(([key]) => key === 'myagent-catalog-revision'), 'storage contains invalidation signals only');

    const child = vm.createContext({ window: null, parent: f.context, location: f.context.location });
    child.window = child; vm.runInContext(source, child);
    assert.strictEqual(child.MyAgentResourceCache, f.cache, 'settings iframe reuses the chat cache');

    // Run the real picker with a minimal event surface and real cache.
    const picker = fs.readFileSync(path.join(root, 'frontend/src/app/modules/skill-picker.js'), 'utf8');
    f.context.document = { querySelector: () => null, getElementById: () => null, addEventListener() {} };
    f.context.currentSessionId = '';
    vm.runInContext(picker, f.context);
    vm.runInContext('renderSkillPicker = function () {};', f.context);
    let pending = f.context.refreshSkillPickerTab(); await pending;
    assert.equal(f.requests.length, 6, 'opening Skill reuses cache and does not fetch MCP or plugins');
    vm.runInContext("skillPickerActiveTab = 'hooks';", f.context);
    await f.context.refreshSkillPickerTab();
    vm.runInContext("skillPickerActiveTab = 'plugins';", f.context);
    await f.context.refreshSkillPickerTab();
    assert.equal(f.requests.length, 6, 'Hooks and Plugins share the same catalog');
    vm.runInContext("skillPickerActiveTab = 'mcp';", f.context);
    pending = f.context.refreshSkillPickerTab();
    assert.equal(f.requests.length, 7);
    f.requests[6].resolve({ ok: true, tools: [], servers: [] }); await pending;
    await tick();
    const catalog = f.cache.get('/api/plugins/catalog');
    f.requests[7].resolve({ ok: true, plugins: [{id: 'demo'}] }); await catalog;
    f.advance(30001);
    const retained = f.cache.peek('/api/plugins/catalog');
    retained.plugins.length = 0;
    assert.equal(f.cache.peek('/api/plugins/catalog').plugins.length, 1, 'retained display values are isolated');
    assert.equal(f.requests.length, 8, 'peeking expired display metadata never starts work');
    f.cache.invalidate('/api/plugins/catalog');
    assert.equal(f.cache.peek('/api/plugins/catalog'), null, 'mutations discard retained plugin tabs');
    const legacyParent = { ...f.context, MyAgentResourceCache: { supports: () => false } };
    const legacyChild = vm.createContext({ ...f.context, MyAgentResourceCache: undefined, parent: legacyParent });
    legacyChild.window = legacyChild;
    vm.runInContext(source, legacyChild);
    assert.notStrictEqual(legacyChild.MyAgentResourceCache, legacyParent.MyAgentResourceCache, 'old open chat pages cannot lend an incompatible cache');
    console.log('catalog cache and lazy picker runtime checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
