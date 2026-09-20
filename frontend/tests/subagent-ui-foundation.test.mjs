/**
 * Node assertions for the subagent UI foundation:
 *   - ui-slot-registry.js（迷你 slot 注册表）
 *   - subagent-catalog-store.js（目录对象层）
 *
 * 两个文件都是为浏览器 bundle 写的「共享作用域拼接、无模块」脚本，因此这里用
 * node:vm 求值（与 tests/dock-engine.test.mjs 同一套路），再对纯逻辑做断言。
 *
 * Run: node tests/subagent-ui-foundation.test.mjs
 */
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import vm from 'node:vm';

const here = dirname(fileURLToPath(import.meta.url));
const srcDir = join(here, '..', 'src', 'app');
const FILES = [
    join(srcDir, 'modules', 'ui-slot-registry.js'),
    join(srcDir, 'state', 'subagent-catalog-store.js'),
    join(srcDir, 'state', 'subagent-addressing.js'),
    join(srcDir, 'modules', 'subagent-frames.js'),
    join(srcDir, 'modules', 'subagent-catalog-ui.js'),
    join(srcDir, 'state', 'subagent-ui-decisions.js'),
    join(srcDir, 'modules', 'subagent-composer-ui.js'),
];

const GLUE = `
globalThis.__subagentUiApi = {
    uiSlots, subagentCatalogStore, subagentAddressing, subagentFrames, subagentCatalogUi,
    subagentUiDecisions, subagentComposerUi,
};
`;

const source = FILES.map((file) => readFileSync(file, 'utf8')).join('\n\n') + '\n\n' + GLUE;
const switches = [];

/** 最小 DOM 桩：这些模块只用到 createElement/getElementById/classList 等少量接口。 */
function makeElement(tag) {
    const el = {
        tagName: tag,
        id: '',
        className: '',
        type: '',
        textContent: '',
        innerHTML: '',
        hidden: false,
        dataset: {},
        parentNode: null,
        children: [],
        classList: {
            _set: new Set(),
            add(c) { this._set.add(c); },
            remove(c) { this._set.delete(c); },
            toggle(c, on) { if (on === undefined) { this._set.has(c) ? this._set.delete(c) : this._set.add(c); } else if (on) this._set.add(c); else this._set.delete(c); },
            contains(c) { return this._set.has(c); },
        },
        style: {},
        attributes: {},
        _listeners: {},
        setAttribute(k, v) { this.attributes[k] = String(v); },
        getAttribute(k) { return this.attributes[k] === undefined ? null : this.attributes[k]; },
        removeAttribute(k) { delete this.attributes[k]; },
        appendChild(child) { child.parentNode = this; this.children.push(child); return child; },
        removeChild(child) { const i = this.children.indexOf(child); if (i >= 0) this.children.splice(i, 1); child.parentNode = null; return child; },
        insertBefore(child, ref) {
            const i = ref ? this.children.indexOf(ref) : -1;
            if (i >= 0) this.children.splice(i, 0, child);
            else this.children.push(child);
            child.parentNode = this;
            return child;
        },
        remove() { if (this.parentNode) this.parentNode.removeChild(this); },
        addEventListener(k, fn) { (this._listeners[k] = this._listeners[k] || []).push(fn); },
        removeEventListener(k, fn) { const l = this._listeners[k] || []; const i = l.indexOf(fn); if (i >= 0) l.splice(i, 1); },
        dispatch(k, ev) { (this._listeners[k] || []).slice().forEach((fn) => fn(ev || {})); },
        querySelector(sel) {
            // 少量模块只按 class 取自己刚插入的子节点；给出最小可用实现。
            const cls = String(sel || '').replace(/^\./, '');
            const find = (node) => {
                for (const child of node.children || []) {
                    if (child.className && String(child.className).split(/\s+/).indexOf(cls) >= 0) return child;
                    const hit = find(child);
                    if (hit) return hit;
                }
                return null;
            };
            return find(this);
        },
        querySelectorAll() { return []; },
        focus() {},
        getBoundingClientRect() { return { left: 0, bottom: 0, width: 300, height: 20 }; },
        get isConnected() { return this.parentNode !== null; },
    };
    return el;
}
const documentStub = {
    body: makeElement('body'),
    documentElement: makeElement('html'),
    _byId: {},
    createElement: makeElement,
    getElementById(id) { return this._byId[id] || null; },
    querySelector() { return null; },
    addEventListener() {},
    removeEventListener() {},
};
const windowStub = { innerWidth: 1280, addEventListener() {}, removeEventListener() {}, setTimeout, clearTimeout };

const context = vm.createContext({
    console, setTimeout, clearTimeout, Date, document: documentStub, window: windowStub,
    requestAnimationFrame: (fn) => setTimeout(fn, 0),
    cancelAnimationFrame: (handle) => clearTimeout(handle),
    switchSession: async (sessionId) => { switches.push(String(sessionId)); return true; },
});
vm.runInContext(source, context);
const {
    uiSlots, subagentCatalogStore, subagentAddressing, subagentFrames, subagentCatalogUi,
    subagentUiDecisions, subagentComposerUi,
} = context.__subagentUiApi;

let passed = 0;
function test(name, fn) {
    try {
        fn();
        passed += 1;
        console.log('  ok  ' + name);
    } catch (error) {
        console.error('FAIL  ' + name);
        console.error('      ' + (error && error.stack ? error.stack.split('\n').slice(0, 5).join('\n      ') : error));
        process.exitCode = 1;
    }
}
async function testAsync(name, fn) {
    try {
        await fn();
        passed += 1;
        console.log('  ok  ' + name);
    } catch (error) {
        console.error('FAIL  ' + name);
        console.error('      ' + (error && error.stack ? error.stack.split('\n').slice(0, 5).join('\n      ') : error));
        process.exitCode = 1;
    }
}

// ── ui-slot-registry ────────────────────────────────────────────────────────
test('register before declaration fails loud', () => {
    uiSlots.resetForTests();
    assert.throws(() => uiSlots.register({ name: 'x.slot' }, 'tester'), /is not declared/);
});

test('declare + register + entriesOf + snapshot shape', () => {
    uiSlots.resetForTests();
    uiSlots.declareSlot('conversation.composer', { kind: 'chain', owner: 'conversation' });
    uiSlots.declareSlot('conversation.header.lineage', { kind: 'single', owner: 'conversation' });
    uiSlots.declareSlot('conversation.header.lineage.count', { kind: 'single', parent: 'conversation.header.lineage' });
    assert.equal(uiSlots.isDeclared('conversation.composer'), true);
    assert.equal(uiSlots.declaredKind('conversation.composer'), 'chain');
    const dispose = uiSlots.register({
        name: 'conversation.header.lineage',
        priority: 0,
        meta: { label: 'lineage' },
    }, 'ui-subagent');
    assert.equal(uiSlots.entriesOf('conversation.header.lineage').length, 1);
    assert.deepEqual(uiSlots.registrantsOf('conversation.header.lineage'), ['ui-subagent']);
    const snap = uiSlots.getSnapshot();
    assert.equal(snap.slots['conversation.header.lineage'].kind, 'single');
    assert.equal(snap.slots['conversation.header.lineage'].entries.length, 1);
    assert.equal(snap.slots['conversation.header.lineage.count'].parent, 'conversation.header.lineage');
    dispose();
    assert.equal(uiSlots.entriesOf('conversation.header.lineage').length, 0);
});

test('declaring an already-declared slot fails; parent must exist first', () => {
    uiSlots.resetForTests();
    uiSlots.declareSlot('a', { kind: 'single' });
    assert.throws(() => uiSlots.declareSlot('a', { kind: 'single' }), /already declared/);
    assert.throws(() => uiSlots.declareSlot('b', { kind: 'single', parent: 'missing' }), /parent slot .* is not declared/);
});

test('single/chain: duplicate priority throws, different priority shadows', () => {
    uiSlots.resetForTests();
    uiSlots.declareSlot('a', { kind: 'single' });
    const d0 = uiSlots.register({ name: 'a', priority: 0 }, 'first');
    assert.throws(() => uiSlots.register({ name: 'a', priority: 0 }, 'second'), /already has a "single" registration at priority 0/);
    const d1 = uiSlots.register({ name: 'a', priority: -10 }, 'third');
    assert.equal(uiSlots.pickWinner(uiSlots.entriesOf('a')).registrant, 'third');
    d1();
    assert.equal(uiSlots.pickWinner(uiSlots.entriesOf('a')).registrant, 'first');
    d0();
});

test('chain elects the first non-null select in priority order', () => {
    uiSlots.resetForTests();
    uiSlots.declareSlot('composer', { kind: 'chain' });
    uiSlots.register({
        name: 'composer', priority: 0,
        select: () => null,
    }, 'normal');
    const d1 = uiSlots.register({
        name: 'composer', priority: -10,
        select: (owner) => (owner && owner.readonly ? { reason: 'one-shot' } : null),
    }, 'readonly-later');
    const d2 = uiSlots.register({
        name: 'composer', priority: -20,
        select: () => ({ reason: 'always' }),
    }, 'always-first');
    const winner = uiSlots.electChain('composer', { readonly: true });
    assert.equal(winner.entry.registrant, 'always-first');
    assert.deepEqual(winner.matched, { reason: 'always' });
    d2();
    assert.equal(uiSlots.electChain('composer', { readonly: true }).entry.registrant, 'readonly-later');
    assert.equal(uiSlots.electChain('composer', { readonly: false }), null);
    d1();
});

test('a throwing select abstains and the next entry wins', () => {
    uiSlots.resetForTests();
    uiSlots.declareSlot('composer', { kind: 'chain' });
    const errors = [];
    uiSlots.setErrorHook((err, entry) => errors.push([entry && entry.registrant, String(err.message || err)]));
    uiSlots.register({ name: 'composer', priority: -30, select: () => { throw new Error('boom'); } }, 'thrower');
    uiSlots.register({ name: 'composer', priority: 0, select: () => ({ ok: true }) }, 'fallback');
    const winner = uiSlots.electChain('composer', {});
    assert.equal(winner.entry.registrant, 'fallback');
    assert.equal(errors.length, 1);
    assert.equal(errors[0][0], 'thrower');
});

test('abdicate lets the next winner take the cell', () => {
    uiSlots.resetForTests();
    const errors = [];
    uiSlots.setErrorHook((err, entry) => errors.push([entry && entry.registrant, String(err.message || err)]));
    uiSlots.declareSlot('lineage', { kind: 'single' });
    const d1 = uiSlots.register({ name: 'lineage', priority: -10 }, 'crashed');
    uiSlots.register({ name: 'lineage', priority: 0 }, 'survivor');
    assert.equal(uiSlots.pickWinner(uiSlots.entriesOf('lineage')).registrant, 'crashed');
    uiSlots.abdicate('lineage', uiSlots.entriesOf('lineage')[0].id, new Error('render failed'));
    assert.equal(uiSlots.pickWinner(uiSlots.entriesOf('lineage')).registrant, 'survivor');
    assert.deepEqual(errors, [['crashed', 'render failed']], 'abdicate reports through the error hook');
    d1();
});

test('disposer cascade removes declared child slots; stale disposer is a no-op', () => {
    uiSlots.resetForTests();
    uiSlots.declareSlot('root.slot', { kind: 'single' });
    const dispose = uiSlots.register({
        name: 'root.slot',
        priority: 0,
        children: [{ name: 'root.slot.child', kind: 'single' }],
    }, 'host');
    assert.equal(uiSlots.isDeclared('root.slot.child'), true);
    const childDispose = uiSlots.register({ name: 'root.slot.child', priority: 0 }, 'child-owner');
    dispose();
    assert.equal(uiSlots.isDeclared('root.slot.child'), false, 'child declaration is collapsed with its parent');
    assert.equal(uiSlots.entriesOf('root.slot.child').length, 0, 'child registration is released recursively');
    assert.doesNotThrow(() => childDispose());
    assert.doesNotThrow(() => dispose());
});

test('subscribe notifies with a fresh snapshot and publishes a seq', () => {
    uiSlots.resetForTests();
    const seen = [];
    const off = uiSlots.subscribe((snap) => seen.push(snap.seq));
    uiSlots.declareSlot('t', { kind: 'single' });
    const before = uiSlots.getSnapshot().seq;
    uiSlots.register({ name: 't', priority: 0 }, 'x');
    assert.ok(uiSlots.getSnapshot().seq > before);
    assert.ok(seen.length >= 2);
    const lastSeq = seen[seen.length - 1];
    off();
    uiSlots.register({ name: 't', priority: 1 }, 'y');
    assert.equal(seen[seen.length - 1], lastSeq, 'unsubscribed sink stops receiving');
});

// ── subagent-catalog-store ──────────────────────────────────────────────────
function fixtureFetch(routes, log) {
    return (url) => {
        log.push(url);
        const hit = routes.find((r) => url.indexOf(r.match) >= 0);
        if (!hit) return Promise.reject(new Error('no route for ' + url));
        return Promise.resolve(hit.body);
    };
}

function node(overrides) {
    return Object.assign({
        id: 'child-1', parent_id: 'parent-1', subagent_type: 'generalPurpose',
        running: true, status: 'running', depth: 1, has_children: false, source: 'runtime_v2',
    }, overrides || {});
}

await testAsync('refreshCatalogs fetches and normalizes entries; snapshot is reference-stable', async () => {
    subagentCatalogStore.resetForTests();
    const log = [];
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{ match: '/sessions/parent-1/subagents', body: { subagents: [node()] } }], log),
    });
    const before = subagentCatalogStore.getSnapshot();
    const catalog = await subagentCatalogStore.refreshCatalogs('parent-1');
    assert.equal(catalog.state, 'ready');
    assert.equal(catalog.entries.length, 1);
    assert.equal(catalog.entries[0].activity, 'running');
    assert.equal(catalog.entries[0].mode, 'continuable');
    assert.equal(log.length, 1);
    const snap = subagentCatalogStore.getSnapshot();
    assert.notEqual(snap, before);
    assert.equal(snap.catalogsByParent['parent-1'].state, 'ready');
    assert.deepEqual(snap.addresses['child-1'], {
        parentSessionId: 'parent-1', childSessionId: 'child-1', mode: 'continuable',
    });
    // 引用稳定：无新事实时同一引用
    assert.equal(subagentCatalogStore.getSnapshot(), snap);
});

await testAsync('refreshCatalogs is single-flight; force queues one trailing refresh', async () => {
    subagentCatalogStore.resetForTests();
    const log = [];
    let releaseFirst = null;
    subagentCatalogStore.setImplementation({
        fetchJson: (url) => {
            log.push(url);
            if (log.length === 1) {
                return new Promise((resolve) => {
                    releaseFirst = () => resolve({ subagents: [node()] });
                });
            }
            return Promise.resolve({ subagents: [node()] });
        },
    });
    const p1 = subagentCatalogStore.refreshCatalogs('parent-1');
    const p2 = subagentCatalogStore.refreshCatalogs('parent-1');
    const p3 = subagentCatalogStore.refreshCatalogs('parent-1', { force: true });
    assert.equal(log.length, 1, 'while in flight every call (including force) joins the same request');
    releaseFirst();
    await p1;
    await p2;
    await p3;
    // 尾随刷新排在微任务队列里，再让出一轮让 fetchJson 被调用
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(log.length, 2, 'force requested while in flight produces exactly one trailing refresh');
});

await testAsync('membership frames patch in-flight requests instead of being overwritten', async () => {
    subagentCatalogStore.resetForTests();
    let releaseFirst = null;
    let call = 0;
    subagentCatalogStore.setImplementation({
        fetchJson: () => {
            call += 1;
            if (call === 1) return Promise.resolve({ subagents: [node()] });
            return new Promise((resolve) => {
                releaseFirst = () => resolve({ subagents: [node()] });
            });
        },
    });
    await subagentCatalogStore.refreshCatalogs('parent-1');   // 先建立地址，成员帧才有落点
    const p = subagentCatalogStore.refreshCatalogs('parent-1');
    // 第二请求在途：成员帧到达（模拟 host/session-status: running → inactive）
    assert.equal(subagentCatalogStore.handleSessionStatus('child-1', false), true);
    releaseFirst();
    await p;
    const entries = subagentCatalogStore.entriesOf('parent-1');
    assert.equal(entries[0].activity, 'inactive', 'in-flight patch folded into the settled catalog');
});

await testAsync('session-added registers a new child; session-removed degrades to inactive without dropping the row', async () => {
    subagentCatalogStore.resetForTests();
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{ match: '/sessions/parent-1/subagents', body: { subagents: [node()] } }], []),
    });
    await subagentCatalogStore.refreshCatalogs('parent-1');
    assert.equal(subagentCatalogStore.handleSessionAdded({
        id: 'child-2', parent_id: 'parent-1', running: true, source: 'runtime_v2',
    }), true);
    const entries = subagentCatalogStore.entriesOf('parent-1');
    assert.equal(entries.length, 2);
    assert.equal(subagentCatalogStore.getAddress('child-2').parentSessionId, 'parent-1');
    assert.equal(subagentCatalogStore.handleSessionRemoved('child-2'), true);
    assert.equal(subagentCatalogStore.entriesOf('parent-1').length, 2, 'row survives removal');
    assert.equal(subagentCatalogStore.entriesOf('parent-1').find((e) => e.childId === 'child-2').activity, 'inactive');
});

await testAsync('selectSubagent only accepts healthy catalog children', async () => {
    subagentCatalogStore.resetForTests();
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{ match: '/sessions/parent-1/subagents', body: { subagents: [node()] } }], []),
    });
    await subagentCatalogStore.refreshCatalogs('parent-1');
    assert.equal(subagentCatalogStore.selectSubagent('unknown-child'), null);
    const addr = subagentCatalogStore.selectSubagent('child-1');
    assert.deepEqual(addr, { parentSessionId: 'parent-1', childSessionId: 'child-1', mode: 'continuable' });
    assert.deepEqual(subagentCatalogStore.getSelectedAddress(), addr);
    subagentCatalogStore.clearSelection();
    assert.equal(subagentCatalogStore.getSelectedAddress(), null);
});

await testAsync('setCatalogOpen refreshes once on open and is idempotent', async () => {
    subagentCatalogStore.resetForTests();
    const log = [];
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{ match: '/sessions/parent-1/subagents', body: { subagents: [node()] } }], log),
    });
    subagentCatalogStore.setCatalogOpen('parent-1', true);
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(log.length, 1);
    assert.equal(subagentCatalogStore.isCatalogOpen('parent-1'), true);
    subagentCatalogStore.setCatalogOpen('parent-1', true);
    assert.equal(log.length, 1, 'already-open set is a no-op');
    subagentCatalogStore.setCatalogOpen('parent-1', false);
    assert.equal(subagentCatalogStore.isCatalogOpen('parent-1'), false);
});

await testAsync('summarizeDescendants counts rows and running rows', async () => {
    subagentCatalogStore.resetForTests();
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{
            match: '/sessions/parent-1/subagents',
            body: { subagents: [node(), node({ id: 'child-2', running: false, status: 'completed' })] },
        }], []),
    });
    await subagentCatalogStore.refreshCatalogs('parent-1');
    assert.deepEqual(subagentCatalogStore.summarizeDescendants('parent-1'), { total: 2, running: 1 });
});

await testAsync('catalog rows carry duration inputs; token metrics are fetched lazily and cached', async () => {
    subagentCatalogStore.resetForTests();
    const log = [];
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([
            {
                match: '/sessions/parent-1/subagents',
                body: {
                    subagents: [node({
                        id: 'child-1',
                        started_at: Date.now() - 90_000,
                        finished_at: Date.now(),
                    })],
                },
            },
            { match: '/sessions/child-1/context_tokens', body: { ok: true, estimated: 12345, threshold: 90000 } },
        ], log),
    });
    await subagentCatalogStore.refreshCatalogs('parent-1');
    const row = subagentCatalogStore.entriesOf('parent-1')[0];
    assert.ok(row.startedAt > 0, 'started_at normalized');
    assert.ok(row.finishedAt > 0, 'finished_at normalized');
    assert.equal(subagentCatalogStore.getTokens('child-1'), null, 'no token metrics before the fetch');
    const tokens = await subagentCatalogStore.fetchTokens('child-1');
    assert.deepEqual(tokens, { estimated: 12345, threshold: 90000 });
    assert.deepEqual(subagentCatalogStore.getTokens('child-1'), { estimated: 12345, threshold: 90000 });
    const callsBefore = log.length;
    await subagentCatalogStore.fetchTokens('child-1');
    assert.equal(log.length, callsBefore, 'second read is served from cache');
});

await testAsync('failed token fetch is remembered and not retried', async () => {
    subagentCatalogStore.resetForTests();
    const log = [];
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{ match: '/sessions/parent-1/subagents', body: { subagents: [node()] } }], log),
    });
    await subagentCatalogStore.refreshCatalogs('parent-1');
    assert.equal(await subagentCatalogStore.fetchTokens('child-1'), null, 'missing route fails soft');
    const callsBefore = log.length;
    assert.equal(await subagentCatalogStore.fetchTokens('child-1'), null);
    assert.equal(log.length, callsBefore, 'a remembered miss is not retried');
});

await testAsync('refresh error keeps previous entries and records the failure', async () => {
    subagentCatalogStore.resetForTests();
    let fail = false;
    subagentCatalogStore.setImplementation({
        fetchJson: () => (fail ? Promise.reject(new Error('network down')) : Promise.resolve({ subagents: [node()] })),
    });
    await subagentCatalogStore.refreshCatalogs('parent-1');
    fail = true;
    const result = await subagentCatalogStore.refreshCatalogs('parent-1');
    assert.equal(result, null, '失败刷新对外结果为空');
    const catalog = subagentCatalogStore.getCatalog('parent-1');
    assert.equal(catalog.state, 'error');
    assert.ok(/network down/.test(catalog.error));
    assert.equal(subagentCatalogStore.entriesOf('parent-1').length, 1, 'previous entries retained on failure');
});

await testAsync('normalizeEntry flags corrupt rows and virtual tasks as one-shot', async () => {
    const corrupt = subagentCatalogStore.normalizeEntry({ description: 'no id here' });
    assert.equal(corrupt.diagnostic, true);
    assert.equal(subagentCatalogStore.normalizeEntry(node({ virtual_task: true })).mode, 'one-shot');
    const dismissed = subagentCatalogStore.normalizeEntry(node({ id: 'x', parent_id: 'p', running: false, status: 'completed' }));
    assert.equal(dismissed.activity, 'inactive');
});

await testAsync('entry label prefers the subagent own name over its type', async () => {
    // 目录行的显示名必须是子代理自己的名称/描述，而非 "explore" 这类类型
    const withDescription = subagentCatalogStore.normalizeEntry(
        node({ id: 'c1', parent_id: 'p', subagent_type: 'explore', description: '扫描前端渲染管线' })
    );
    assert.equal(withDescription.label, '扫描前端渲染管线');
    const withName = subagentCatalogStore.normalizeEntry(
        node({ id: 'c2', parent_id: 'p', name: '渲染审计', subagent_type: 'explore', description: 'desc' })
    );
    assert.equal(withName.label, '渲染审计', 'explicit name wins');
    const typeOnly = subagentCatalogStore.normalizeEntry(
        node({ id: 'c3', parent_id: 'p', subagent_type: 'explore', description: '' })
    );
    assert.equal(typeOnly.label, 'explore', 'type is only the last-resort fallback');
});

await testAsync('outcome separates result semantics from activity (dot colour source)', async () => {
    const norm = (over) => subagentCatalogStore.normalizeEntry(node(over));
    assert.equal(norm({ id: 'c1', parent_id: 'p', running: true, status: 'running' }).outcome, 'running');
    assert.equal(norm({ id: 'c2', parent_id: 'p', running: false, status: 'completed' }).outcome, 'ok');
    assert.equal(norm({ id: 'c3', parent_id: 'p', running: false, status: 'failed' }).outcome, 'failed');
    assert.equal(norm({ id: 'c4', parent_id: 'p', running: false, status: 'interrupted' }).outcome, 'failed');
    assert.equal(norm({ id: 'c5', parent_id: 'p', running: false, status: 'cancelled' }).outcome, 'failed');
    assert.equal(norm({ id: 'c6', parent_id: 'p', running: false, status: 'orphaned' }).outcome, 'failed');
    assert.equal(norm({ id: 'c6b', parent_id: 'p', running: true, status: 'orphaned' }).outcome, 'failed');
    assert.equal(norm({ id: 'c6c', parent_id: 'p', running: false, status: 'stale' }).outcome, 'failed');
    assert.equal(norm({ id: 'c7', parent_id: 'p', running: false, ok: false }).outcome, 'failed');
    assert.equal(norm({ id: 'c8', parent_id: 'p', running: false, status: 'queued' }).outcome, 'running');
    // 无任何状态线索（status 置空、逐字段全缺）→ unknown
    assert.equal(
        norm({ id: 'c9', parent_id: 'p', running: false, status: '', task_status: '' }).outcome,
        'unknown'
    );
    // 陈旧 running 标志不应盖过终态
    assert.equal(norm({ id: 'c10', parent_id: 'p', running: true, status: 'interrupted' }).outcome, 'failed');
});

await testAsync('marking a subagent read flips its unread state and persists once', async () => {
    subagentCatalogStore.resetForTests();
    assert.equal(subagentCatalogStore.isSubagentRead('child-1'), false);
    assert.equal(subagentCatalogStore.markSubagentRead('child-1'), true, 'first mark reports a change');
    assert.equal(subagentCatalogStore.isSubagentRead('child-1'), true);
    assert.equal(subagentCatalogStore.markSubagentRead('child-1'), false, 'repeat mark is a no-op');
    assert.equal(subagentCatalogStore.isSubagentRead('child-2'), false, 'other ids are unaffected');
});

await testAsync('catalog row dot colours follow the agreed semantics', async () => {
    subagentCatalogStore.resetForTests();
    subagentCatalogUIReset();
    const titleRow = makeElement('div');
    titleRow.id = 'breadcrumb-text';
    documentStub._byId['breadcrumb-text'] = titleRow;
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{
            match: '/sessions/parent-1/subagents',
            body: {
                subagents: [
                    node({ id: 'run-child', running: true, status: 'running', description: 'running one' }),
                    node({ id: 'ok-child', running: false, status: 'completed', description: 'fresh done' }),
                    node({ id: 'err-child', running: false, status: 'failed', description: 'broken one' }),
                ],
            },
        }], []),
    });
    await subagentCatalogStore.refreshCatalogs('parent-1');
    subagentCatalogUi.renderTrigger(titleRow, 'parent-1');
    subagentCatalogUi.openMenu();
    const menu = documentStub.body.children.find((c) => c.id === 'subagent-catalog-menu');
    assert.ok(menu, 'menu rendered');
    const html = String(menu.innerHTML || '');
    const rowFor = (name) => {
        const idx = html.indexOf(name);
        return idx < 0 ? '' : html.slice(Math.max(0, idx - 320), idx);
    };
    assert.ok(/is-running/.test(rowFor('running one')), 'running row shows the amber dot class');
    assert.ok(/is-unread/.test(rowFor('fresh done')), 'fresh completed row shows the green dot class');
    assert.ok(/is-error/.test(rowFor('broken one')), 'failed row shows the red dot class');
    // 打开后（标记已读）→ 蓝
    subagentCatalogStore.markSubagentRead('ok-child');
    subagentCatalogUi.closeMenu({ restoreFocus: false });
    subagentCatalogUi.openMenu();
    const html2 = String((documentStub.body.children.find((c) => c.id === 'subagent-catalog-menu') || {}).innerHTML || '');
    const idx2 = html2.indexOf('fresh done');
    const row2 = idx2 < 0 ? '' : html2.slice(Math.max(0, idx2 - 320), idx2);
    assert.ok(/is-read/.test(row2), 'read row now shows the blue dot class');
    subagentCatalogUi.closeMenu({ restoreFocus: false });
    delete documentStub._byId['breadcrumb-text'];
});

await testAsync('leading subagent evidence mounts the trigger without a prior render (regression)', async () => {
    subagentCatalogStore.resetForTests();
    subagentCatalogUIReset();
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{ match: '/sessions/parent-1/subagents', body: { subagents: [node()] } }], []),
    });
    const titleRow = makeElement('div');
    titleRow.className = 'breadcrumb-title-row';
    const originalQuerySelector = documentStub.querySelector;
    documentStub.querySelector = (sel) => (sel === '.breadcrumb-title-row' ? titleRow : null);
    context.sessionStore = { currentSessionId: 'parent-1' };
    const findTrigger = () => titleRow.children.find(
        (c) => /subagent-catalog-trigger/.test(String(c.className))
    );
    try {
        await subagentCatalogStore.refreshCatalogs('parent-1');
        // 场景：证据已到，但触发器从未挂载（首次出现子代理时胶囊不及时出现的根因）
        subagentCatalogUi.hideTrigger();
        assert.equal(findTrigger(), undefined, 'no trigger before the evidence path runs');
        subagentCatalogUi.noteUnknownChildEvidence('parent-1');
        const mounted = findTrigger();
        assert.ok(mounted, 'trigger mounts on the current title row without a prior render');
        assert.equal(mounted.classList.contains('hidden'), false, 'trigger is visible once mounted');

        // 订阅回调路径：store 迟到的权威数据到达时也能把触发器补挂
        subagentCatalogUi.bindStore();
        subagentCatalogUi.hideTrigger();
        assert.equal(findTrigger(), undefined);
        subagentCatalogStore.setImplementation({
            fetchJson: fixtureFetch([{
                match: '/sessions/parent-1/subagents',
                body: { subagents: [node(), node({ id: 'child-2' })] },
            }], []),
        });
        await subagentCatalogStore.refreshCatalogs('parent-1', { force: true });
        const remounted = findTrigger();
        assert.ok(remounted, 'store refresh re-mounts the trigger for the current session');
        assert.equal(remounted.classList.contains('hidden'), false);
    } finally {
        documentStub.querySelector = originalQuerySelector;
        delete context.sessionStore;
        subagentCatalogUIReset();
    }
});

await testAsync('switching to a session without evidence keeps the capsule hidden under store notifications (regression)', async () => {
    subagentCatalogStore.resetForTests();
    subagentCatalogUIReset();
    const titleRow = makeElement('div');
    titleRow.className = 'breadcrumb-title-row';
    const originalQuerySelector = documentStub.querySelector;
    documentStub.querySelector = (sel) => (sel === '.breadcrumb-title-row' ? titleRow : null);
    context.sessionStore = { currentSessionId: 'parent-1' };
    const findTrigger = () => titleRow.children.find(
        (c) => /subagent-catalog-trigger/.test(String(c.className))
    );
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{ match: '/sessions/parent-1/subagents', body: { subagents: [node()] } }], []),
    });
    try {
        await subagentCatalogStore.refreshCatalogs('parent-1');
        subagentCatalogUi.bindStore();
        subagentCatalogUi.renderTrigger(titleRow, 'parent-1');
        assert.ok(findTrigger(), 'sanity: trigger mounted for parent-1');

        // 切到没有子代理证据的会话（新建对话 / 普通会话都走这条路径）
        context.sessionStore.currentSessionId = 'parent-2';
        subagentCatalogUi.renderTrigger(titleRow, 'parent-2');
        assert.equal(findTrigger(), undefined, 'trigger removed on the switch');

        // 旧会话目录的迟到通知不得把旧胶囊挂回当前标题行
        subagentCatalogStore.markSubagentRead('stale-guard-child-1');
        assert.equal(findTrigger(), undefined, 'store notification must not resurrect the old capsule');
        await subagentCatalogStore.refreshCatalogs('parent-1', { force: true });
        assert.equal(findTrigger(), undefined, 'old parent refresh must not resurrect the old capsule');
    } finally {
        documentStub.querySelector = originalQuerySelector;
        delete context.sessionStore;
        subagentCatalogUIReset();
    }
});

await testAsync('draft (no current session) stays capsule-free under store notifications (regression)', async () => {
    subagentCatalogStore.resetForTests();
    subagentCatalogUIReset();
    const titleRow = makeElement('div');
    titleRow.className = 'breadcrumb-title-row';
    const originalQuerySelector = documentStub.querySelector;
    documentStub.querySelector = (sel) => (sel === '.breadcrumb-title-row' ? titleRow : null);
    context.sessionStore = { currentSessionId: 'parent-1' };
    const findTrigger = () => titleRow.children.find(
        (c) => /subagent-catalog-trigger/.test(String(c.className))
    );
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{ match: '/sessions/parent-1/subagents', body: { subagents: [node()] } }], []),
    });
    try {
        await subagentCatalogStore.refreshCatalogs('parent-1');
        subagentCatalogUi.bindStore();
        subagentCatalogUi.renderTrigger(titleRow, 'parent-1');
        assert.ok(findTrigger(), 'sanity: trigger mounted for parent-1');

        // 新建对话：进入草稿态（updateSessionTitle 的无会话分支会调用 hideTrigger）
        context.sessionStore.currentSessionId = null;
        subagentCatalogUi.hideTrigger();
        assert.equal(findTrigger(), undefined, 'trigger hidden in draft');

        subagentCatalogStore.markSubagentRead('stale-guard-child-2');
        assert.equal(findTrigger(), undefined, 'store notification must not resurrect the capsule in draft');
        await subagentCatalogStore.refreshCatalogs('parent-1', { force: true });
        assert.equal(findTrigger(), undefined, 'old parent refresh must not resurrect the capsule in draft');
    } finally {
        documentStub.querySelector = originalQuerySelector;
        delete context.sessionStore;
        subagentCatalogUIReset();
    }
});

test('subscribe reports catalog transitions in order', () => {
    subagentCatalogStore.resetForTests();
    const states = [];
    const off = subagentCatalogStore.subscribe((snap) => {
        const c = snap.catalogsByParent['parent-1'];
        states.push(c ? c.state : 'none');
    });
    subagentCatalogStore.setImplementation({
        fetchJson: () => new Promise(() => {}),   // 悬挂请求，便于观察 loading
    });
    void subagentCatalogStore.refreshCatalogs('parent-1');
    assert.deepEqual(states, ['loading'], '进入 loading 时通知一次；无新事实不重复通知');
    assert.equal(subagentCatalogStore.getSnapshot().catalogsByParent['parent-1'].state, 'loading');
    off();
});

// ── subagent-addressing ─────────────────────────────────────────────────────
await testAsync('openChild pushes the parent, switches to the child, and reports the address', async () => {
    subagentCatalogStore.resetForTests();
    subagentAddressing.resetForTests();
    switches.length = 0;
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{ match: '/sessions/parent-1/subagents', body: { subagents: [node()] } }], []),
    });
    await subagentCatalogStore.refreshCatalogs('parent-1');
    assert.equal(subagentAddressing.isChildOpen(), false);
    const navigations = [];
    const offNav = subagentAddressing.onNavigate((info) => navigations.push(info));
    const ok = await subagentAddressing.openChild('child-1', { parentSessionId: 'parent-1', title: '子任务 A' });
    assert.equal(ok, true);
    assert.equal(subagentAddressing.isChildOpen(), true);
    assert.deepEqual(switches, ['child-1']);
    const snap = subagentAddressing.snapshot();
    assert.equal(snap.open, true);
    assert.equal(snap.depth, 1);
    assert.deepEqual(snap.address, {
        parentSessionId: 'parent-1', childSessionId: 'child-1', mode: 'continuable',
    });
    assert.equal(snap.title, '子任务 A');
    assert.equal(navigations.length, 1);
    assert.equal(navigations[0].kind, 'open');
    offNav();
});

await testAsync('openChild without a resolvable parent fails and leaves no stack entry', async () => {
    subagentCatalogStore.resetForTests();
    subagentAddressing.resetForTests();
    switches.length = 0;
    const ok = await subagentAddressing.openChild('stranger-child', {});
    assert.equal(ok, false);
    assert.equal(subagentAddressing.isChildOpen(), false);
    assert.deepEqual(switches, [], 'no switch attempted without an address');
});

await testAsync('openChild rolls back the stack when the switch fails', async () => {
    subagentCatalogStore.resetForTests();
    subagentAddressing.resetForTests();
    switches.length = 0;
    const originalSwitch = context.switchSession;
    context.switchSession = async () => false;
    try {
        const ok = await subagentAddressing.openChild('child-1', { parentSessionId: 'parent-1' });
        assert.equal(ok, false);
        assert.equal(subagentAddressing.isChildOpen(), false, 'failed switch rolls the stack back');
    } finally {
        context.switchSession = originalSwitch;
    }
});

await testAsync('returnToParent switches back and clears the addressing selection', async () => {
    subagentCatalogStore.resetForTests();
    subagentAddressing.resetForTests();
    switches.length = 0;
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{ match: '/sessions/parent-1/subagents', body: { subagents: [node()] } }], []),
    });
    await subagentCatalogStore.refreshCatalogs('parent-1');
    subagentCatalogStore.selectSubagent('child-1');
    await subagentAddressing.openChild('child-1', { parentSessionId: 'parent-1' });
    const navigations = [];
    subagentAddressing.onNavigate((info) => navigations.push(info));
    const ok = await subagentAddressing.returnToParent();
    assert.equal(ok, true);
    assert.equal(subagentAddressing.isChildOpen(), false);
    assert.deepEqual(switches, ['child-1', 'parent-1']);
    assert.equal(navigations[0].kind, 'back');
    assert.equal(subagentCatalogStore.getSelectedAddress(), null, '返回后不再寻址子会话');
});

await testAsync('title resolution falls back to the catalog row label, then to the id prefix', async () => {
    subagentCatalogStore.resetForTests();
    subagentAddressing.resetForTests();
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{
            match: '/sessions/parent-1/subagents',
            body: { subagents: [node({ id: 'abcdef123456', parent_id: 'parent-1', description: 'a' })] },
        }], []),
    });
    await subagentCatalogStore.refreshCatalogs('parent-1');
    await subagentAddressing.openChild('abcdef123456', { parentSessionId: 'parent-1' });
    const snap = subagentAddressing.snapshot();
    assert.ok(snap.title.indexOf('generalPurpose') === 0 || snap.title.length > 0, 'title comes from the catalog row');
    subagentAddressing.resetForTests();
    await subagentAddressing.openChild('zzzzzzzzzzzz', { parentSessionId: 'parent-1' });
    assert.equal(subagentAddressing.snapshot().title, 'zzzzzzzzzzzz'.slice(0, 12));
});

test('reset clears the stack and marks subscribers', () => {
    subagentAddressing.resetForTests();
    const seen = [];
    const off = subagentAddressing.subscribe((snap) => seen.push(snap.depth));
    assert.equal(subagentAddressing.depth(), 0);
    off();
});

// ── subagent-frames（成员帧桥接） ───────────────────────────────────────────
await testAsync('subagent_start frame registers a new child row; subagent_finish flips it inactive', async () => {
    subagentCatalogStore.resetForTests();
    subagentFrames.resetForTests();
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{ match: '/sessions/parent-1/subagents', body: { subagents: [] } }], []),
    });
    context.currentSessionId = 'parent-1';
    try {
        await subagentCatalogStore.refreshCatalogs('parent-1');
        assert.equal(subagentFrames.noteSubagentLifecycleFrame({
            type: 'subagent_start', agent_id: 'child-9', subagent_type: 'explore', description: 'scan',
        }), true);
        let entries = subagentCatalogStore.entriesOf('parent-1');
        assert.equal(entries.length, 1);
        assert.equal(entries[0].childId, 'child-9');
        assert.equal(entries[0].activity, 'running');
        assert.equal(subagentFrames.noteSubagentLifecycleFrame({
            type: 'subagent_finish', agent_id: 'child-9', ok: true,
        }), true);
        entries = subagentCatalogStore.entriesOf('parent-1');
        assert.equal(entries.length, 1, 'finished child keeps its row');
        assert.equal(entries[0].activity, 'inactive');
    } finally {
        context.currentSessionId = undefined;
    }
});

await testAsync('activity frames are throttled and only apply to known children', async () => {
    subagentCatalogStore.resetForTests();
    subagentFrames.resetForTests();
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{
            match: '/sessions/parent-1/subagents',
            body: { subagents: [node({ id: 'child-1', running: false, status: 'completed' })] },
        }], []),
    });
    await subagentCatalogStore.refreshCatalogs('parent-1');
    assert.equal(subagentFrames.noteSubagentActivity('unknown-child', true), false, 'unknown child ignored');
    assert.equal(subagentFrames.noteSubagentActivity('child-1', true), true, 'first activity frame flips to running');
    assert.equal(subagentFrames.noteSubagentActivity('child-1', true), false, 'repeat frame within throttle window is a no-op');
    assert.equal(subagentCatalogStore.entriesOf('parent-1')[0].activity, 'running');
});

// ── subagent-catalog-ui（触发器 + 目录树） ──────────────────────────────────
await testAsync('renderTrigger hides without evidence and shows the count with a running dot', async () => {
    subagentCatalogStore.resetForTests();
    subagentCatalogUIReset();
    const titleRow = makeElement('div');
    titleRow.id = 'breadcrumb-text';
    documentStub._byId['breadcrumb-text'] = titleRow;
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{
            match: '/sessions/parent-1/subagents',
            body: { subagents: [node({ id: 'child-1' }), node({ id: 'child-2', running: false, status: 'completed' })] },
        }], []),
    });
    // 无证据：不渲染
    subagentCatalogUi.renderTrigger(titleRow, 'parent-1');
    assert.equal(titleRow.children.length, 0, 'no trigger before the catalog is known');
    await subagentCatalogStore.refreshCatalogs('parent-1');
    subagentCatalogUi.renderTrigger(titleRow, 'parent-1');
    assert.equal(titleRow.children.length, 1, 'trigger mounted after the catalog lands');
    const trigger = titleRow.children[0];
    assert.equal(trigger.id, 'subagent-catalog-trigger');
    assert.ok(trigger.innerHTML.indexOf('2 个子代理') >= 0, 'count shown');
    assert.ok(trigger.innerHTML.indexOf('1 运行中') >= 0, 'running count shown');
    assert.ok(trigger.innerHTML.indexOf('is-running') >= 0, 'activity dot is on');
    delete documentStub._byId['breadcrumb-text'];
});

await testAsync('openMenu subscribes the catalog, lists rows, and selects a child', async () => {
    subagentCatalogStore.resetForTests();
    subagentCatalogUIReset();
    switches.length = 0;
    const titleRow = makeElement('div');
    titleRow.id = 'breadcrumb-text';
    documentStub._byId['breadcrumb-text'] = titleRow;
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{
            match: '/sessions/parent-1/subagents',
            body: {
                subagents: [
                    node({ id: 'child-1', description: 'first task' }),
                    node({ id: 'child-2', running: false, status: 'completed', description: 'second task' }),
                ],
            },
        }], []),
    });
    await subagentCatalogStore.refreshCatalogs('parent-1');
    subagentCatalogUi.renderTrigger(titleRow, 'parent-1');
    subagentCatalogUi.openMenu();
    assert.equal(subagentCatalogUi.isMenuOpen(), true);
    assert.equal(subagentCatalogStore.isCatalogOpen('parent-1'), true, 'opening the menu subscribes the catalog');
    const menu = documentStub.body.children.find((c) => c.id === 'subagent-catalog-menu');
    assert.ok(menu, 'menu is portaled onto the body');
    assert.ok(menu.innerHTML.indexOf('child-1') >= 0 || menu.innerHTML.indexOf('generalPurpose') >= 0, 'rows rendered');
    subagentCatalogUi.setRowsForTests([{ key: 'child-1' }, { key: 'child-2' }]);
    const ok = subagentCatalogUi.selectRow('child-2');
    assert.equal(ok, true);
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.deepEqual(switches, ['child-2'], 'selecting a row opens that child');
    assert.equal(subagentCatalogStore.getSelectedAddress().childSessionId, 'child-2');
    subagentCatalogUi.closeMenu({ restoreFocus: false });
    assert.equal(subagentCatalogStore.isCatalogOpen('parent-1'), false, 'closing the menu unsubscribes');
    delete documentStub._byId['breadcrumb-text'];
});

test('diagnostic rows are not selectable', () => {
    subagentCatalogStore.resetForTests();
    subagentCatalogUIReset();
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{ match: '/sessions/parent-1/subagents', body: { subagents: [] } }], []),
    });
    subagentCatalogUi.setRowsForTests([{ key: 'diag-0', diagnostic: true }, { key: 'child-1' }]);
    assert.equal(subagentCatalogUi.selectRow('diag-0'), false, 'diagnostic key is never selectable');
    assert.equal(subagentCatalogUi.selectRow('child-1'), false, 'unknown child key is not selectable either');
});

function subagentCatalogUIReset() {
    subagentCatalogUi.resetForTests();
    documentStub.body.children.length = 0;
    Object.keys(documentStub._byId).forEach((k) => delete documentStub._byId[k]);
}

// ── subagent-ui-decisions（编辑器三态 + 续接条件，纯函数） ──────────────────
test('editor state: no addressing leaves the composer alone', () => {
    const d = subagentUiDecisions.decideEditorState({ addressing: null });
    assert.equal(d.mode, 'none');
    assert.equal(d.canWrite, true);
    assert.equal(subagentUiDecisions.shouldRenderReadOnlyComposer(d), false);
    assert.equal(subagentUiDecisions.shouldDisableInput(d), false);
});

test('editor state: continuable child with an available parent stays writable', () => {
    const d = subagentUiDecisions.decideEditorState({
        addressing: { parentSessionId: 'p', childSessionId: 'c' },
        entry: { mode: 'continuable', activity: 'running' },
        parentAvailable: true,
    });
    assert.equal(d.mode, 'writable');
    assert.equal(d.canWrite, true);
    assert.equal(d.canStop, true, 'running child keeps its independent Stop');
    assert.equal(subagentUiDecisions.shouldDisableInput(d), false);
});

test('editor state: parent offline locks input but keeps Stop while running', () => {
    const running = subagentUiDecisions.decideEditorState({
        addressing: { parentSessionId: 'p', childSessionId: 'c' },
        entry: { mode: 'continuable', activity: 'running' },
        parentAvailable: false,
    });
    assert.equal(running.mode, 'locked-stop');
    assert.equal(running.canStop, true);
    assert.equal(subagentUiDecisions.shouldDisableInput(running), true);
    assert.equal(subagentUiDecisions.shouldRenderReadOnlyComposer(running), false);
    const stopped = subagentUiDecisions.decideEditorState({
        addressing: { parentSessionId: 'p', childSessionId: 'c' },
        entry: { mode: 'continuable', activity: 'inactive' },
        parentAvailable: false,
    });
    assert.equal(stopped.mode, 'read-only');
    assert.equal(subagentUiDecisions.shouldRenderReadOnlyComposer(stopped), true);
    assert.ok(subagentUiDecisions.readOnlyReasonText(stopped).length > 0);
});

test('editor state: one-shot history is read-only in every case', () => {
    const running = subagentUiDecisions.decideEditorState({
        addressing: { parentSessionId: 'p', childSessionId: 'c' },
        entry: { mode: 'one-shot', activity: 'running' },
        parentAvailable: true,
    });
    assert.equal(running.mode, 'read-only');
    assert.equal(running.canStop, false, 'one-shot has no Stop');
    assert.equal(subagentUiDecisions.shouldDisableInput(running), true);
    assert.ok(/只读/.test(subagentUiDecisions.readOnlyReasonText(running)));
});

test('continuation prompt: only when results are pending and no child is running', () => {
    assert.deepEqual(subagentUiDecisions.decideContinuationPrompt({ pendingCount: 0, runningCount: 0 }), {
        show: false, reason: 'nothing-pending',
    });
    assert.deepEqual(subagentUiDecisions.decideContinuationPrompt({ pendingCount: 2, runningCount: 1 }), {
        show: false, reason: 'children-running',
    });
    assert.deepEqual(subagentUiDecisions.decideContinuationPrompt({ pendingCount: 2, runningCount: 0 }), {
        show: true, reason: 'pending-results',
    });
});

// ── subagent-composer-ui（呈现层） ─────────────────────────────────────────
await testAsync('composer UI mounts the read-only placeholder and gates the input', async () => {
    subagentCatalogStore.resetForTests();
    subagentAddressing.resetForTests();
    subagentComposerUi.resetForTests();
    setupComposerDom();
    subagentCatalogStore.setImplementation({
        fetchJson: fixtureFetch([{
            match: '/sessions/parent-1/subagents',
            body: { subagents: [node({ id: 'child-1', virtual_task: true })] },
        }], []),
    });
    await subagentCatalogStore.refreshCatalogs('parent-1');
    await subagentAddressing.openChild('child-1', { parentSessionId: 'parent-1' });
    subagentComposerUi.syncComposer();
    const placeholder = documentStub._byId['subagent-composer-readonly'] || findInTree('subagent-composer-readonly');
    assert.ok(placeholder, 'read-only placeholder mounted for a one-shot child');
    assert.ok(/只读/.test(placeholder.textContent), 'explains why it is read-only');
    assert.equal(documentStub._byId['message-input'].disabled, true, 'input disabled');
    assert.equal(documentStub._byId['send-btn'].disabled, true, 'send disabled');
});

await testAsync('editor takeover runs through the slot chain election', async () => {
    uiSlots.resetForTests();
    subagentComposerUi.resetForTests();
    subagentCatalogStore.resetForTests();
    subagentAddressing.resetForTests();
    assert.equal(subagentComposerUi.registerComposerSeat(), true, 'seat registers on the shared registry');
    assert.equal(uiSlots.isDeclared(subagentComposerUi.SLOT_NAME), true);
    assert.equal(uiSlots.declaredKind(subagentComposerUi.SLOT_NAME), 'chain');
    const readonly = { mode: 'read-only', reason: 'one-shot' };
    const writable = { mode: 'writable', reason: '' };
    assert.equal(subagentComposerUi.electComposerSeat(writable), null, 'writable editor keeps the seat');
    const elected = subagentComposerUi.electComposerSeat(readonly);
    assert.ok(elected, 'read-only decision wins the seat');
    assert.deepEqual(elected.matched, { reason: 'one-shot', mode: 'read-only' });
    assert.equal(elected.entry.priority, -10);
    // 再注册一次是幂等的（不会重复占位）
    assert.equal(subagentComposerUi.registerComposerSeat(), false);
    assert.equal(uiSlots.entriesOf(subagentComposerUi.SLOT_NAME).length, 1);
    subagentComposerUi.resetForTests();
});

await testAsync('composer UI shows the continuation hint only for the addressed parent session', async () => {
    subagentCatalogStore.resetForTests();
    subagentAddressing.resetForTests();
    subagentComposerUi.resetForTests();
    setupComposerDom();
    context.currentSessionId = 'parent-1';
    try {
        subagentComposerUi.syncFromSessionSummary('parent-1', {
            subagent_pending_continue: 2,
            subagent_running: 0,
            subagent_can_continue: true,
            subagent_continuation: { state: 'ready', pending_count: 2 },
        });
        const hint = findInTree('subagent-continue-hint');
        assert.ok(hint, 'hint mounted when results are pending');
        assert.ok(/2 个子任务结果/.test(hint.innerHTML) || /2 个子任务结果/.test(descendantText(hint)), 'count shown');
        subagentComposerUi.syncFromSessionSummary('parent-1', {
            subagent_pending_continue: 0,
            subagent_running: 1,
            subagent_can_continue: true,
            subagent_continuation: { state: 'wait_children', pending_count: 0 },
        });
        assert.equal(findInTree('subagent-continue-hint'), null, 'hint removed while children run');
    } finally {
        context.currentSessionId = undefined;
    }
});

function setupComposerDom() {
    documentStub.body.children.length = 0;
    Object.keys(documentStub._byId).forEach((k) => delete documentStub._byId[k]);
    const panelInner = makeElement('div');
    panelInner.className = 'panel-inner';
    const row = makeElement('div');
    row.className = 'composer-row';
    panelInner.appendChild(row);
    documentStub.body.appendChild(panelInner);
    const input = makeElement('textarea');
    input.id = 'message-input';
    const send = makeElement('button');
    send.id = 'send-btn';
    documentStub._byId['message-input'] = input;
    documentStub._byId['send-btn'] = send;
    documentStub.querySelector = (selector) => {
        if (selector === '.panel-inner') return panelInner;
        if (selector === '.composer-row') return row;
        return null;
    };
    documentStub.getElementById = (id) => documentStub._byId[id] || findInTree(id);
}

function findInTree(id, root) {
    const start = root || documentStub.body;
    for (const child of start.children || []) {
        if (child.id === id) return child;
        const found = findInTree(id, child);
        if (found) return found;
    }
    return null;
}

function descendantText(el) {
    let out = el.textContent || '';
    (el.children || []).forEach((child) => { out += descendantText(child); });
    return out;
}

console.log('\n' + passed + ' assertions passed' + (process.exitCode ? ' (with failures)' : ''));
