const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'frontend/src/app/modules/session-management.js'), 'utf8');
const fn = name => source.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'))[0];
const tick = () => new Promise(resolve => setImmediate(resolve));
function deferred() { let resolve; const promise = new Promise(r => resolve = r); return { promise, resolve }; }

(async () => {
    const requests = [];
    const c = vm.createContext({
        console, Date, AbortController, HISTORY_DIALOGUES_PER_PAGE: 5, HISTORY_EVENT_BUDGET: 500,
        initialSessionHistoryPrefetch: null,
        fetchSessionHistoryJSON: (url, signal) => {
            const pending = deferred(); requests.push({ url, options: {signal}, ...pending }); return pending.promise;
        },
    });
    vm.runInContext(['initialSessionHistoryUrl', 'prefetchInitialSessionHistory', 'fetchInitialSessionHistorySnapshot'].map(fn).join('\n'), c);
    c.prefetchInitialSessionHistory('saved');
    assert.equal(requests.length, 1, 'saved history can start while sidebar is pending');
    const controller = new AbortController();
    const consumed = c.fetchInitialSessionHistorySnapshot('saved', c.initialSessionHistoryUrl('saved'), controller.signal);
    const response = { response: {ok: true}, data: {events: []} };
    requests[0].resolve(response);
    assert.strictEqual(await consumed, response);
    assert.equal(requests.length, 1, 'selected history consumes the prefetched response exactly once');

    c.prefetchInitialSessionHistory('old');
    const other = c.fetchInitialSessionHistorySnapshot('other', c.initialSessionHistoryUrl('other'), controller.signal);
    assert.equal(requests[1].options.signal.aborted, true, 'a different selected session cancels speculation');
    requests[2].resolve(response); await other;
    requests[1].resolve(null);
    c.prefetchInitialSessionHistory('active');
    const active = c.fetchInitialSessionHistorySnapshot('active', c.initialSessionHistoryUrl('active'), controller.signal);
    controller.abort();
    assert.equal(requests[3].options.signal.aborted, true, 'switch cancellation reaches the consumed prefetch');
    requests[3].resolve(response); await active;

    c.prefetchInitialSessionHistory('failed');
    const failure = new Error('timeout');
    requests[4].resolve({error: failure});
    await assert.rejects(c.fetchInitialSessionHistorySnapshot('failed', c.initialSessionHistoryUrl('failed'), new AbortController().signal), /timeout/);
    assert.equal(requests.length, 5, 'a failed startup read is consumed without a second full timeout');

    const metadata = deferred();
    let restores = 0, observers = 0, interactions = 0;
    const s = vm.createContext({
        console, performance: { now: Date.now }, currentSessionId: 'old', switchSessionEpoch: 0, messageLoadEpoch: 0,
        initialSessionHistoryPrefetch: null,
        sessionStore: { get: () => ({}), ui: {} }, sessionUnreadComplete: new Set(),
        localStorage: { setItem() {} }, document: { dispatchEvent() {} },
        CustomEvent: function () {},
        setCurrentSessionState: sid => { s.currentSessionId = sid; },
        isSessionRunning: () => false, isServerStreamActive: () => false,
        restoreStreamForRunningSession: () => false,
        restoreCachedSessionStream: () => { restores++; return true; },
        refreshSingleSessionRow: () => metadata.promise,
        refreshHumanInteractions: () => { interactions++; return new Promise(() => {}); },
        maybeStartStreamPollForSession: () => observers++,
    });
    for (const name of ['cancelSmoothStreamFollowForSessionSwitch', 'clearTocForSessionLoad', 'clearOptionalPanelsForSessionLoad',
        'hideRewriteUndoToast', 'clearSessionUnreadState', 'saveChatScrollForSession', 'stashInputDraft', 'prepareStashLeaving',
        'updateSessionTitle', 'restoreInputDraft', 'syncSessionListIndicatorClasses', 'setSendButtonState', 'hideLoading',
        'rebuildToc', 'scheduleContextTokensAfterPaint', 'restoreCachedSessionScrollPosition', 'scrollToBottom']) s[name] = () => {};
    vm.runInContext(fn('switchSession'), s);
    let timer;
    const completed = await Promise.race([
        s.switchSession('cached').then(() => true),
        new Promise(resolve => { timer = setTimeout(() => resolve(false), 100); }),
    ]);
    clearTimeout(timer);
    assert(completed, 'a cached restore must not wait for metadata or pending interactions');
    assert.equal(restores, 1); assert.equal(interactions, 1);
    assert.equal(observers, 1);
    s.currentSessionId = 'newer';
    metadata.resolve({ stream_active: true }); await tick();
    assert.equal(observers, 1, 'late runtime discovery cannot attach to a session that was left');

    const layout = fs.readFileSync(path.join(root, 'frontend/src/app/modules/layout-panels.js'), 'utf8');
    const initialize = layout.match(/^async function init\([^]*?^}/m)[0];
    const sidebar = deferred();
    const switches = [];
    const startup = vm.createContext({
        console, currentSessionId: null, NEW_SESSION_DRAFT_KEY: 'draft',
        localStorage: { getItem: () => 'saved' },
        loadUnreadFromStorage() {}, initSidebarSash() {}, showLoading() {},
        prefetchInitialSessionHistory() {}, loadSessions: () => sidebar.promise,
        sessionStore: { list: () => [{ id: 'saved' }] },
        switchSession: async sid => { switches.push(sid); startup.currentSessionId = sid; },
        createNewSession: async () => { throw new Error('unexpected draft'); },
        bindExistingLogs() {},
    });
    vm.runInContext(initialize, startup);
    const started = startup.init();
    await tick();
    assert.deepEqual(switches, ['saved'], 'ready history is displayed even while the sidebar request is blocked');
    sidebar.resolve(true);
    await started;
    assert.deepEqual(switches, ['saved'], 'sidebar completion must not load that history twice');
    const linkedSwitches = [], prefetches = [];
    const linked = vm.createContext({
        console, currentSessionId:null, pendingQuerySession:'linked', NEW_SESSION_DRAFT_KEY:'draft',
        localStorage:{getItem:()=> 'saved'},
        loadUnreadFromStorage(){}, initSidebarSash(){}, showLoading(){}, bindExistingLogs(){},
        prefetchInitialSessionHistory:sid=>prefetches.push(sid),
        loadSessions:async()=>true, sessionStore:{list:()=>[{id:'saved'},{id:'linked'}]},
        switchSession:async(sid,options)=>{linkedSwitches.push([sid,options.initialLoad]);linked.currentSessionId=sid;},
        createNewSession:async()=>{throw new Error('unexpected draft');},
    });
    vm.runInContext(initialize, linked);
    await linked.init();
    assert.deepEqual(prefetches,['linked'], 'deep links must not fetch saved history first');
    assert.deepEqual(linkedSwitches,[['linked',true]], 'the requested conversation uses the initial-load path once');
    assert.equal(linked.pendingQuerySession,'');
    console.log('session startup prefetch and immediate cached restore checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
