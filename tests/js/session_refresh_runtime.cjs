const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync(path.resolve(__dirname, '../../frontend/src/app/modules/session-management.js'), 'utf8');
const start = source.indexOf('var SESSION_REFRESH_LIST_WAIT_MS');
const end = source.indexOf('var SESSION_IMPORT_ARCHIVE_EXT', start);

function deferred() {
    let resolve;
    const promise = new Promise(done => { resolve = done; });
    return { promise, resolve };
}

function setup(repair, load = async () => {}) {
    const calls = { requests: [], loads: [], reloads: 0, alerts: [], timers: new Map() };
    const button = {
        disabled: false, attributes: {}, classes: new Set(),
        setAttribute(key, value) { this.attributes[key] = value; },
        removeAttribute(key) { delete this.attributes[key]; },
    };
    button.classList = { add: value => button.classes.add(value), remove: value => button.classes.delete(value) };
    let timerId = 0;
    const context = vm.createContext({
        console: { error() {} },
        fetchWithTimeout: (...args) => { calls.requests.push(args); return repair(...args); },
        loadSessions: options => { calls.loads.push(options); return load(options); },
        showUiAlert: options => calls.alerts.push(options),
        window: {
            location: { reload: () => calls.reloads++ },
            setTimeout(callback, delay) { calls.timers.set(++timerId, { callback, delay }); return timerId; },
            clearTimeout(id) { calls.timers.delete(id); },
        },
    });
    vm.runInContext(source.slice(start, end), context);
    return { calls, button, context, run: () => context.refreshSessionListAndPage(button) };
}

const success = () => ({ ok: true, status: 200, json: async () => ({ ok: true, state_revision: 123 }) });
const flush = () => new Promise(resolve => setImmediate(resolve));

test('waits for index reconstruction before the list request or reload, including slow repairs', async () => {
    const repair = deferred(), list = deferred();
    const ui = setup(() => repair.promise, () => list.promise);
    const pending = ui.run();
    await flush();
    assert.equal(ui.button.disabled, true);
    assert.equal(ui.button.attributes['aria-busy'], 'true');
    assert(ui.button.classes.has('is-busy'));
    assert.equal(ui.calls.requests[0][0], '/sessions/index/repair');
    assert.equal(ui.calls.requests[0][1].method, 'POST');
    assert.equal(ui.calls.requests[0][1].credentials, 'same-origin');
    assert.equal(ui.calls.requests[0][2], 120000);
    assert.equal(ui.calls.timers.size, 0, 'the list deadline must not interrupt index reconstruction');
    assert.equal(ui.calls.loads.length, 0);
    assert.equal(ui.calls.reloads, 0);
    await ui.run();
    assert.equal(ui.calls.requests.length, 1, 'repeat clicks must not start concurrent rebuilds');
    repair.resolve(success());
    await flush();
    assert.equal(ui.calls.loads.length, 1);
    assert.equal(ui.calls.loads[0].force, true);
    assert.equal(ui.calls.reloads, 0);
    list.resolve();
    await pending;
    assert.equal(ui.calls.reloads, 1);
    assert.equal(ui.calls.timers.size, 0);
    assert.equal(ui.button.disabled, false);
    assert.equal(ui.context.sessionRefreshInFlight, false);
});

test('a hung list request cannot block page reload after a successful reconstruction', async () => {
    const ui = setup(async () => success(), () => new Promise(() => {}));
    const pending = ui.run();
    await flush();
    const deadline = [...ui.calls.timers.values()][0];
    assert.equal(deadline.delay, 1200);
    deadline.callback();
    await pending;
    assert.equal(ui.calls.reloads, 1);
    assert.equal(ui.calls.alerts.length, 0);
});

test('server and network failures keep the page open and release the button for a retry', async () => {
    const cases = [
        async () => ({ ok: false, status: 500, json: async () => ({ ok: false, error: 'Index is read-only' }) }),
        async () => ({ ok: true, status: 200, json: async () => ({ ok: false, error: 'Rebuild failed' }) }),
        async () => ({ ok: true, status: 200, json: async () => { throw new Error('Not JSON'); } }),
        async () => { const error = new Error('Timed out'); error.name = 'AbortError'; throw error; },
    ];
    for (const failure of cases) {
        let failed = true;
        const ui = setup((...args) => failed ? failure(...args) : Promise.resolve(success()));
        await ui.run();
        assert.equal(ui.calls.reloads, 0);
        assert.equal(ui.calls.loads.length, 0);
        assert.equal(ui.calls.alerts.length, 1);
        assert.equal(ui.calls.alerts[0].title, '刷新失败');
        assert.equal(ui.button.disabled, false);
        assert.equal(ui.button.classes.size, 0);
        assert.equal(ui.button.attributes['aria-busy'], undefined);
        failed = false;
        await ui.run();
        assert.equal(ui.calls.reloads, 1);
    }
});

test('list refresh failure still reloads after the successful backend repair', async () => {
    const ui = setup(async () => success(), () => { throw new Error('List request failed'); });
    await ui.run();
    assert.equal(ui.calls.reloads, 1);
    assert.equal(ui.calls.alerts.length, 0);
});
