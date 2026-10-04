import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

/* 最小 DOM 桩：只实现公共左侧栏模块实际用到的接口，
   让模块以 data:URL 模块形式加载并驱动（与页面里以脚本片段装载等价的调用面）。 */
function makeClassList() {
    const names = new Set();
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
        textContent: '',
        className: '',
        type: '',
        classList: makeClassList(),
        _attrs: {},
        _listeners: {},
        appendChild: function (child) {
            if (child.parentNode) child.parentNode.removeChild(child);
            child.parentNode = el;
            el.children.push(child);
            return child;
        },
        append: function (...children) { children.forEach(child => el.appendChild(child)); },
        insertBefore: function (child, reference) {
            if (child.parentNode) child.parentNode.removeChild(child);
            const index = reference ? el.children.indexOf(reference) : el.children.length;
            el.children.splice(index, 0, child);
            child.parentNode = el;
            return child;
        },
        get lastElementChild() { return el.children.at(-1) || null; },
        removeChild: function (child) {
            const index = el.children.indexOf(child);
            if (index >= 0) el.children.splice(index, 1);
            child.parentNode = null;
            return child;
        },
        replaceChildren: function () {
            Array.from(el.children).forEach(function (child) { child.parentNode = null; });
            el.children.length = 0;
            Array.from(arguments).forEach(function (child) { el.appendChild(child); });
        },
        setAttribute: function (name, value) { el._attrs[String(name)] = String(value); },
        getAttribute: function (name) {
            return Object.prototype.hasOwnProperty.call(el._attrs, String(name)) ? el._attrs[String(name)] : null;
        },
        addEventListener: function (type, handler) {
            const key = String(type);
            (el._listeners[key] = el._listeners[key] || []).push(handler);
        },
        removeEventListener: function () {},
        focus: function () {},
        closest: function (selector) {
            let node = el;
            while (node) {
                if (selector === '.pubar-pane' && node._attrs && node._attrs['data-pubar-pane']) return node;
                node = node.parentNode;
            }
            return null;
        },
        querySelector: function (selector) { return queryDescendant(el, selector); },
    };
    return el;
}

/* 只支持模块实际用到的两种选择器：类名与 [data-pubar-narrow-item="…"]。 */
function matchesStubSelector(el, selector) {
    const attributeMatch = /^\[data-pubar-narrow-item="([^"]+)"\]$/.exec(String(selector));
    if (attributeMatch) return el._attrs['data-pubar-narrow-item'] === attributeMatch[1];
    const text = String(selector);
    if (text.charCodeAt(0) === 46) {
        return String(el.className || '').split(/\s+/).includes(text.slice(1));
    }
    return false;
}

function queryDescendant(node, selector) {
    for (const child of node.children) {
        if (matchesStubSelector(child, selector)) return child;
        const nested = queryDescendant(child, selector);
        if (nested) return nested;
    }
    return null;
}

const root = makeElement('aside');
const tabs = makeElement('div');
const panes = makeElement('div');
const narrowStrip = makeElement('div');
root.appendChild(tabs);
root.appendChild(panes);
root.querySelector = function (selector) {
    if (selector === '.pubar-tabs') return tabs;
    if (selector === '.pubar-panes') return panes;
    return null;
};

const documentEvents = {};
globalThis.document = {
    readyState: 'complete',
    documentElement: { lang: 'zh' },
    getElementById: function (id) {
        return id === 'chat-todo-plan' ? root : id === 'pubar-narrow-strip' ? narrowStrip : null;
    },
    createElement: function (tag) { return makeElement(tag); },
    addEventListener: function (type, handler) {
        const key = String(type);
        (documentEvents[key] = documentEvents[key] || []).push(handler);
    },
    removeEventListener: function () {},
    dispatchEvent: function (event) {
        (documentEvents[String(event && event.type)] || []).forEach(function (handler) { handler(event); });
        return true;
    },
};

const storage = new Map();
try {
    globalThis.localStorage = {
        getItem: function (key) { return storage.has(String(key)) ? storage.get(String(key)) : null; },
        setItem: function (key, value) { storage.set(String(key), String(value)); },
    };
} catch (error) {
    // Node 可能锁定 localStorage；模块会退化为“不记忆”，不影响其余断言。
}

globalThis.requestAnimationFrame = function (callback) { callback(); return 1; };

let contentNotifications = 0;
globalThis.notifyPanelContentChanged = function () { contentNotifications += 1; };

const sourceUrl = new URL('../../frontend/src/app/modules/public-sidebar.js', import.meta.url);
const source = await readFile(sourceUrl, 'utf8');
const moduleUrl = `data:text/javascript;base64,${Buffer.from(
    source
    + '\nexport { initPublicSidebar, pubarSync, pubarActivate, pubarHasContent, pubarPaneHostFor,'
    + ' pubarRegisterPane, pubarRemovePane, pubarResetForSession, pubarGetActiveId, pubarNotifyActivity };\n'
).toString('base64')}`;
const mod = await import(moduleUrl);

assert.equal(mod.initPublicSidebar(), true);
assert.equal(globalThis.MyAgentPubar.ready, true);
assert.equal(typeof globalThis.MyAgentPubar.paneHostFor, 'function');
assert.equal(mod.pubarHasContent(), false);
assert.equal(tabs.hidden, true);

const planHost = mod.pubarPaneHostFor('plan', { label: '计划', order: 10 });
assert.ok(planHost);
assert.equal(planHost.getAttribute('data-pubar-pane'), 'plan');
planHost.appendChild(makeElement('section'));
mod.pubarSync();
assert.equal(mod.pubarHasContent(), true);
assert.equal(tabs.hidden, true, '仅 1 类内容时不显示页签条');
assert.equal(planHost.hidden, false);
assert.equal(mod.pubarGetActiveId(), 'plan');

const initialNarrowItem = narrowStrip.children[0];
mod.pubarSync();
assert.equal(narrowStrip.children[0], initialNarrowItem, '未变化的条目保留 DOM、焦点与悬停状态');
let narrowActionValue = 0;
globalThis.MyAgentPubar.configureNarrow('plan', {
    label: '计划', actions: [{ label: '执行', onClick() { narrowActionValue = 1; } }],
});
const actionItem = narrowStrip.children[0];
globalThis.MyAgentPubar.configureNarrow('plan', {
    label: '计划', actions: [{ label: '执行', onClick() { narrowActionValue = 2; } }],
});
assert.equal(narrowStrip.children[0], actionItem, '仅更换动作回调时不重建按钮');
actionItem.children[1].children[0]._listeners.click[0]({ preventDefault() {}, stopPropagation() {} });
assert.equal(narrowActionValue, 2, '复用的按钮调用最新回调');

/* 秒级状态胶囊（Goal 计时）只应改文字：重建会丢悬停/过渡态并让 backdrop-filter 重新合成出残影。 */
globalThis.MyAgentPubar.configureNarrow('plan', {
    label: '计划', chip: { text: '1 / 3 已完成', tone: 'accent' },
    actions: [{ label: '执行', onClick() { narrowActionValue = 2; } }],
});
mod.pubarSync();
const chipItem = narrowStrip.children[0];
const chipOf = (item) => item.children[0].children.find(
    child => String(child.className || '').split(/\s+/).includes('pni-chip'));
assert.equal(chipOf(chipItem).textContent, '1 / 3 已完成');
assert.equal(globalThis.MyAgentPubar.updateNarrowChip('plan', '2 / 3 已完成'), true);
assert.equal(chipOf(chipItem).textContent, '2 / 3 已完成', '文字已更新到活体 DOM');
assert.equal(narrowStrip.children[0], chipItem, '仅更新胶囊文字时不重建条目');
mod.pubarSync();
assert.equal(narrowStrip.children[0], chipItem, '更新后的面板同步也不重建条目');
globalThis.MyAgentPubar.configureNarrow('plan', {
    label: '计划', chip: { text: '2 / 3 已完成', tone: 'accent' }, summary: '新的摘要',
    actions: [{ label: '执行', onClick() { narrowActionValue = 2; } }],
});
assert.notEqual(narrowStrip.children[0], chipItem, '摘要等结构内容变化时仍重建条目');

const changes = mod.pubarRegisterPane({ id: 'changes', label: '改动', order: 90 });
assert.ok(changes && changes.host);
changes.setVisible(true);
changes.setCount(3);
assert.equal(tabs.hidden, false);
assert.deepEqual(
    tabs.children.map(function (tab) { return tab.getAttribute('data-pubar-tab'); }),
    ['plan', 'changes']
);
const changesTab = tabs.children[1];
assert.equal(changesTab.children[1].hidden, false);
assert.equal(changesTab.children[1].textContent, '3');
assert.deepEqual(narrowStrip.children.map(item => item.getAttribute('data-pubar-narrow-item')), ['plan', 'changes']);
await new Promise(function (resolve) { setTimeout(resolve, 220); });
assert.equal(mod.pubarGetActiveId(), 'changes', '新页签出现后自动切换');
assert.equal(changes.host.hidden, false);

const pluginsHost = mod.pubarPaneHostFor('plugins', null);
const pluginsChild = makeElement('section');
pluginsHost.appendChild(pluginsChild);
mod.pubarSync();
assert.deepEqual(
    tabs.children.map(function (tab) { return tab.getAttribute('data-pubar-tab'); }),
    ['plan', 'plugins', 'changes']
);
const pluginsTab = tabs.children[1];
assert.equal(pluginsTab.children[1].hidden, true, '插件页签仅在 >1 时显示数字');
assert.equal(pluginsTab.classList.contains('is-pulse'), false, '自动跟切不叠加脉冲');
await new Promise(function (resolve) { setTimeout(resolve, 220); });
assert.equal(mod.pubarGetActiveId(), 'plugins', '新面板出现后自动切换');

const keydown = tabs._listeners.keydown[0];
keydown({ key: 'ArrowRight', preventDefault: function () {} });
assert.equal(mod.pubarGetActiveId(), 'changes');
keydown({ key: 'ArrowLeft', preventDefault: function () {} });
assert.equal(mod.pubarGetActiveId(), 'plugins');
keydown({ key: 'End', preventDefault: function () {} });
assert.equal(mod.pubarGetActiveId(), 'changes');
assert.equal(changes.host.hidden, false);
assert.equal(planHost.hidden, true);
assert.equal(storage.get('pubar-active-tab'), 'changes', '活动页签被记忆');

mod.pubarNotifyActivity(pluginsChild);
await new Promise(function (resolve) { setTimeout(resolve, 220); });
assert.equal(mod.pubarGetActiveId(), 'plugins', '显式活动通知自动切换');

const detachedPanel = makeElement('section');
mod.pubarNotifyActivity(detachedPanel);
assert.equal(mod.pubarGetActiveId(), 'plugins', '未挂载上报暂不切换');
planHost.appendChild(detachedPanel);
await new Promise(function (resolve) { setTimeout(resolve, 400); });
assert.equal(mod.pubarGetActiveId(), 'plan', '未挂载上报在内容提交后补切');

mod.pubarResetForSession();
assert.equal(planHost.children.length, 0);
assert.equal(pluginsHost.children.length, 0);
assert.equal(mod.pubarHasContent(), true, '外部页签（改动）不受会话重置影响');
assert.equal(mod.pubarGetActiveId(), 'changes', '会话重置后保持记忆/回落');

pluginsHost.appendChild(makeElement('section'));
mod.pubarSync();
assert.equal(mod.pubarGetActiveId(), 'changes', '会话切换抑制期内不自动切换');
assert.equal(tabs.children[1].classList.contains('is-pulse'), true, '抑制期内回退为脉冲提示');
pluginsHost.replaceChildren();
mod.pubarSync();

changes.setVisible(false);
assert.equal(mod.pubarHasContent(), false);
assert.equal(tabs.hidden, true);
assert.equal(mod.pubarGetActiveId(), null);

changes.remove();
assert.equal(tabs.children.length, 2);
assert.equal(panes.children.length, 2);

planHost.appendChild(makeElement('section'));
document.dispatchEvent(new CustomEvent('myagent:plugin-session-ui-rendered', { detail: {} }));
assert.equal(mod.pubarHasContent(), true);
assert.equal(mod.pubarGetActiveId(), 'plan', '记忆页签不可用时回落到第一个有内容页签');

assert.ok(contentNotifications > 0);

console.log('public sidebar runtime checks passed');
