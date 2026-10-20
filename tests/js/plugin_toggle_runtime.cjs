const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.resolve(__dirname, '../../frontend/src/app/modules/skill-picker.js'), 'utf8');
const defer = () => {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return {promise, resolve, reject};
};
const response = data => ({ok: true, json: async () => data});

function setup() {
    const requests = [], warnings = [], events = [], timers = new Map();
    let timerId = 0;
    const context = vm.createContext({
        console, currentSessionId: 'original',
        window: {}, document: {querySelector: () => null, getElementById: () => null, dispatchEvent: e => events.push(e)},
        CustomEvent: function (type, init) { this.type = type; this.detail = init.detail; },
        setTimeout: callback => { const id = ++timerId; timers.set(id, callback); return id; },
        clearTimeout: id => timers.delete(id),
        showGlobalWarningBanner: message => warnings.push(message),
        fetch: (url, options) => {
            const pending = defer(); requests.push({url, options, pending}); return pending.promise;
        },
    });
    vm.runInContext(source, context);
    vm.runInContext(`
        extensionsCache = {enabled: {plugins: true}, plugins: [{id: 'demo', name: 'Demo', enabled: true}]};
        renderSkillPicker = function () {};
    `, context);
    const button = {disabled: false, getAttribute: name => name === 'data-plugin-id' ? 'demo' : 'true'};
    return {context, button, requests, warnings, events, timers, html: () => context.renderSkillPickerPluginsHtml()};
}

async function flush() { for (let i = 0; i < 8; i++) await Promise.resolve(); }

(async () => {
    {
        const state = setup();
        const pending = state.context.toggleSkillPickerPlugin(state.button);
        assert.equal(state.button.disabled, true, 'the clicked control disables immediately');
        assert.match(state.html(), /正在禁用…/);
        assert.match(state.html(), /plugin-toggle-spinner/);
        assert.match(state.html(), /aria-busy="true"/);
        await state.context.toggleSkillPickerPlugin(state.button);
        assert.equal(state.requests.length, 1, 'repeated clicks cannot submit duplicate toggles');
        [...state.timers.values()][0]();
        assert.match(state.html(), /正在禁用，请稍候…/);
        state.context.currentSessionId = 'different';
        state.requests[0].pending.resolve(response({ok: true, state: {enabled: false}}));
        await flush();
        assert.match(state.html(), /正在刷新列表/);
        assert.equal(state.requests.length, 2);
        assert.equal(state.events[0].detail.sessionId, 'original', 'completion keeps the originating session');
        state.requests[1].pending.resolve(response({ok: true, enabled: {plugins: true}, plugins: [{id: 'demo', enabled: false}]}));
        await pending;
        assert.match(state.html(), /已禁用/);
        assert.doesNotMatch(state.html(), /plugin-toggle-spinner/);
        assert.equal(state.timers.size, 0);
        assert.equal(state.warnings.length, 0);
    }
    {
        const state = setup();
        const pending = state.context.toggleSkillPickerPlugin(state.button);
        state.requests[0].pending.resolve({ok: false, json: async () => ({ok: false, error: 'shutdown failed'})});
        await pending;
        assert.match(state.html(), /已启用/);
        assert.doesNotMatch(state.html(), /plugin-toggle-spinner/);
        assert.match(state.warnings[0], /shutdown failed/);
        assert.equal(state.timers.size, 0);
    }
    {
        const state = setup();
        const pending = state.context.toggleSkillPickerPlugin(state.button);
        state.requests[0].pending.resolve(response({ok: true}));
        await flush();
        state.requests[1].pending.reject(new Error('snapshot unavailable'));
        await pending;
        assert.match(state.html(), /已禁用/);
        assert.match(state.warnings[0], /插件已禁用，但列表刷新失败/);
        assert.doesNotMatch(state.html(), /plugin-toggle-spinner/);
    }
    {
        const state = setup();
        const first = state.context.loadSkillPickerExtensions();
        const second = state.context.loadSkillPickerExtensions();
        state.requests[1].pending.resolve(response({ok: true, enabled: {plugins: true}, plugins: [{id: 'demo', enabled: false}]}));
        await second;
        state.requests[0].pending.resolve(response({ok: true, enabled: {plugins: true}, plugins: [{id: 'demo', enabled: true}]}));
        await first;
        assert.match(state.html(), /已禁用/, 'a late old snapshot cannot overwrite the newest catalog');
    }
    console.log('Plugin toggle runtime checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
