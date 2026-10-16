const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const source = fs.readFileSync(path.resolve(__dirname, '../../frontend/src/app/modules/session-management.js'), 'utf8');
const start = source.indexOf('var sessionExportsInFlight = new Set();');
const end = source.indexOf('async function deleteSessionFromMenu', start);
const code = source.slice(start, end);

function setup(fetcher, confirmed = true) {
    const calls = { requests: [], downloads: [], alerts: [], urls: [], revoked: [], timers: [], menus: [] };
    const wrap = { _sessionMenuSession: { id: 'session-1' } };
    const context = vm.createContext({
        console: { error() {} },
        openUiModal: async () => confirmed,
        showUiAlert: alert => calls.alerts.push(alert),
        syncSessionMenuLabels: () => calls.menus.push(context.sessionExportsInFlight.has('session-1')),
        fetch: async (...args) => { calls.requests.push(args); return fetcher(...args); },
        URL: {
            createObjectURL: blob => { calls.urls.push(blob); return 'blob:session-zip'; },
            revokeObjectURL: url => calls.revoked.push(url),
        },
        setTimeout: (callback, delay) => calls.timers.push({ callback, delay }),
        document: {
            querySelectorAll: () => [wrap],
            body: { appendChild: link => { link.attached = true; } },
            createElement: () => ({
                click() { assert.equal(this.attached, true); calls.downloads.push({ href: this.href, name: this.download }); },
                remove() { this.attached = false; calls.removed = true; },
            }),
        },
    });
    vm.runInContext(code, context);
    return { context, calls, run: () => context.exportSessionFromMenu({ id: 'session-1', name: '示例' }) };
}

function zipResponse(overrides = {}) {
    return {
        ok: true,
        headers: new Headers({ 'Content-Type': 'application/zip', 'Content-Disposition': 'attachment; filename="session-session-1.zip"' }),
        blob: async () => new Blob(['ZIP bytes'], { type: 'application/zip' }),
        ...overrides,
    };
}

test('download is started only after reading a valid ZIP; object URL survives the click', async () => {
    const ui = setup(async () => zipResponse());
    await ui.run();
    assert.equal(ui.calls.requests[0][0], '/sessions/session-1/export');
    assert.equal(ui.calls.requests[0][1].credentials, 'same-origin');
    assert.deepEqual(ui.calls.downloads, [{ href: 'blob:session-zip', name: 'session-session-1.zip' }]);
    assert.equal(ui.calls.removed, true);
    assert.equal(ui.calls.alerts.length, 0);
    assert.equal(ui.calls.revoked.length, 0);
    assert(ui.calls.timers[0].delay >= 1000);
    ui.calls.timers[0].callback();
    assert.deepEqual(ui.calls.revoked, ['blob:session-zip']);
    assert.deepEqual(ui.calls.menus, [true, false]);
});

test('server error body is visible and never saved as a ZIP; retry remains available', async () => {
    let failed = true;
    const ui = setup(async () => failed
        ? { ok: false, status: 400, json: async () => ({ error: 'Attachment missing or corrupt' }) }
        : zipResponse());
    await ui.run();
    assert.equal(ui.calls.alerts[0].title, '导出失败');
    assert.equal(ui.calls.alerts[0].message, 'Attachment missing or corrupt');
    assert.equal(ui.calls.downloads.length, 0);
    assert.equal(ui.calls.urls.length, 0);
    failed = false;
    await ui.run();
    assert.equal(ui.calls.downloads.length, 1);
});

test('network and interrupted-body errors are visible without starting a download', async () => {
    for (const fetcher of [
        async () => { throw new Error('Network failed'); },
        async () => zipResponse({ blob: async () => { throw new Error('Connection interrupted'); } }),
    ]) {
        const ui = setup(fetcher);
        await ui.run();
        assert.equal(ui.calls.alerts.length, 1);
        assert.equal(ui.calls.downloads.length, 0);
        assert.equal(ui.context.sessionExportsInFlight.size, 0);
    }
});

test('HTML setup redirects and empty responses are rejected', async () => {
    for (const response of [
        zipResponse({ redirected: true }),
        zipResponse({ headers: new Headers({ 'Content-Type': 'text/html' }) }),
        zipResponse({ blob: async () => new Blob([]) }),
    ]) {
        const ui = setup(async () => response);
        await ui.run();
        assert.equal(ui.calls.alerts.length, 1);
        assert.equal(ui.calls.downloads.length, 0);
    }
});

test('cancellation makes no request; concurrent repeat clicks create one export', async () => {
    const cancelled = setup(async () => zipResponse(), false);
    await cancelled.run();
    assert.equal(cancelled.calls.requests.length, 0);
    let resolve;
    const ui = setup(() => new Promise(done => { resolve = done; }));
    const first = ui.run();
    await Promise.resolve();
    await ui.run();
    assert.equal(ui.calls.requests.length, 1);
    resolve(zipResponse());
    await first;
    assert.equal(ui.calls.downloads.length, 1);
});
