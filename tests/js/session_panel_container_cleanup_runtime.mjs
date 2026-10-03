import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

/* 最小 DOM 桩：只实现 plugin-ui-slots.js 渲染会话面板用到的接口。
   覆盖「面板从 payload 消失后，旧卡片必须从原容器移除」这一回归。 */
function makeClassList(initial) {
    const names = new Set(initial || []);
    return {
        add: function (name) { names.add(String(name)); },
        remove: function (name) { names.delete(String(name)); },
        toggle: function (name, force) {
            const on = force === undefined ? !names.has(String(name)) : force === true;
            if (on) names.add(String(name)); else names.delete(String(name));
            return on;
        },
        contains: function (name) { return names.has(String(name)); },
    };
}

function makeElement(tag) {
    const el = {
        tagName: String(tag || 'div').toUpperCase(),
        children: [],
        parentNode: null,
        hidden: false,
        isFragment: false,
        textContent: '',
        className: '',
        classList: makeClassList(),
        dataset: {},
        style: {},
        appendChild: function (child) {
            if (child && child.isFragment) {
                Array.from(child.children).forEach(function (grandChild) {
                    el.appendChild(grandChild);
                });
                child.replaceChildren();
                return child;
            }
            if (child.parentNode) child.parentNode.removeChild(child);
            child.parentNode = el;
            el.children.push(child);
            return child;
        },
        append: function () {
            Array.from(arguments).forEach(function (child) { el.appendChild(child); });
        },
        insertBefore: function (child, before) {
            const index = el.children.indexOf(before);
            el.appendChild(child);
            if (index >= 0) {
                el.children.splice(el.children.indexOf(child), 1);
                el.children.splice(index, 0, child);
            }
            return child;
        },
        removeChild: function (child) {
            const index = el.children.indexOf(child);
            if (index >= 0) el.children.splice(index, 1);
            child.parentNode = null;
            return child;
        },
        remove: function () {
            if (el.parentNode) el.parentNode.removeChild(el);
        },
        contains: function (child) {
            let node = child;
            while (node) {
                if (node === el) return true;
                node = node.parentNode;
            }
            return false;
        },
        replaceChildren: function () {
            Array.from(el.children).forEach(function (child) { child.parentNode = null; });
            el.children.length = 0;
            Array.from(arguments).forEach(function (child) { el.appendChild(child); });
        },
        setAttribute: function (name, value) { el[name] = String(value); },
        getAttribute: function (name) { return el[name] === undefined ? null : el[name]; },
        addEventListener: function () {},
        removeEventListener: function () {},
        querySelector: function () { return null; },
        querySelectorAll: function () { return []; },
    };
    return el;
}

function makeFragment() {
    const fragment = makeElement('#fragment');
    fragment.isFragment = true;
    return fragment;
}

function makeRow(sessionId, active) {
    const row = makeElement('div');
    row.dataset.sessionId = sessionId;
    if (active) row.classList.add('active');
    return row;
}

const sessionsList = makeElement('div');
const rows = [makeRow('s1', true), makeRow('s2', false)];
const host = makeElement('div');              // 回退宿主 #plugin-session-panels
const paneHosts = Object.create(null);        // pubar 页签 host（按 group 分）
const documentEvents = {};

globalThis.CustomEvent = class CustomEvent {
    constructor(type, init) {
        this.type = String(type);
        this.detail = (init && init.detail) || null;
    }
};

globalThis.document = {
    getElementById: function (id) {
        if (id === 'plugin-session-panels') return host;
        if (id === 'sessions-list') return sessionsList;
        return null;
    },
    createElement: function (tag) { return makeElement(tag); },
    createDocumentFragment: function () { return makeFragment(); },
    querySelector: function () { return null; },
    querySelectorAll: function (selector) {
        return String(selector).indexOf('.session-item') >= 0 ? rows : [];
    },
    addEventListener: function (type, handler) {
        const key = String(type);
        (documentEvents[key] = documentEvents[key] || []).push(handler);
    },
    removeEventListener: function () {},
    dispatchEvent: function (event) {
        (documentEvents[String(event && event.type)] || []).forEach(function (handler) {
            handler(event);
        });
        return true;
    },
};

globalThis.MyAgentPubar = {
    paneHostFor: function (groupId) {
        const id = String(groupId || 'plugins');
        if (!paneHosts[id]) paneHosts[id] = makeElement('div');
        return paneHosts[id];
    },
};

const planPanel = {
    plugin_id: 'session-todo',
    id: 'current-plan',
    title: 'Current plan',
    variant: 'info',
    group: { id: 'plan', label: '计划', order: 10 },
    actions: [],
    fields: [
        { label: 'Completed', value: 1, format: 'number' },
        { label: 'Total', value: 2, format: 'number' },
        {
            label: 'Items', format: 'list',
            columns: [{ label: 'Status', format: 'text' }, { label: 'Task', format: 'text' }],
            rows: [{ values: ['in_progress', '任务 A'] }],
        },
    ],
};

let payload = {
    ok: true,
    sessions: { s1: { badges: [], panels: [planPanel] } },
};
globalThis.fetch = async function () {
    return { ok: true, json: async () => payload };
};

/* 收集警告：刷新失败会打 console.warn，测试末尾据此判定链路未被破坏。 */
const warnings = [];
const originalWarn = console.warn;
console.warn = function () {
    warnings.push(Array.from(arguments).map(String).join(' ').slice(0, 200));
};

const source = await readFile(
    new URL('../../frontend/src/app/plugin-ui-slots.js', import.meta.url), 'utf8');
const mod = await import(`data:text/javascript;base64,${
    Buffer.from(source).toString('base64')}`);

/* 1) 面板存在：渲染进 pubar 的「plan」页签 host，回退宿主保持隐藏。 */
await mod.refreshPluginSessionUi(['s1']);
assert.equal(paneHosts.plan.children.length, 1, 'pubar 页签 host 渲染出 1 张卡片');
assert.equal(paneHosts.plan.children[0].dataset.contributionId, 'current-plan');
assert.equal(host.children.length, 0, 'pubar 接管时不写回退宿主');
assert.equal(host.hidden, true);

/* 2) 同一容器重复刷新：只替换、不叠加。 */
await mod.refreshPluginSessionUi(['s1']);
assert.equal(paneHosts.plan.children.length, 1, '重复刷新不应叠加卡片');

/* 3) 面板从 payload 消失（计划清空）：旧卡片必须被移除。 */
payload = { ok: true, sessions: { s1: { badges: [], panels: [] } } };
await mod.refreshPluginSessionUi(['s1']);
assert.equal(paneHosts.plan.children.length, 0,
    'payload 里没有面板时，原容器必须被清空（否则旧卡片永久残留）');

/* 4) 无 pubar 时回退宿主 #plugin-session-panels 走同一条清理路径。 */
delete globalThis.MyAgentPubar;
payload = { ok: true, sessions: { s1: { badges: [], panels: [planPanel] } } };
await mod.refreshPluginSessionUi(['s1']);
assert.equal(host.children.length, 1, '回退宿主渲染出 1 张卡片');
assert.equal(host.hidden, false);
payload = { ok: true, sessions: { s1: { badges: [], panels: [] } } };
await mod.refreshPluginSessionUi(['s1']);
assert.equal(host.children.length, 0, '回退宿主同样必须移除旧卡片');
assert.equal(host.hidden, true, '没有可见面板时宿主保持隐藏');

/* 5) 另一张卡片重新出现：容器恢复渲染。 */
payload = { ok: true, sessions: { s1: { badges: [], panels: [planPanel] } } };
await mod.refreshPluginSessionUi(['s1']);
assert.equal(host.children.length, 1, '面板重新出现时容器恢复渲染');

console.warn = originalWarn;
assert.deepEqual(warnings, [], '刷新链路不应产生警告');

console.log('session panel container cleanup runtime checks passed');
