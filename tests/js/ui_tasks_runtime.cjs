const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.resolve(__dirname, '../../app/templates/static/settings/resource_cache.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));
function fixture() {
    let id = 0, inputPending = false;
    const timers = new Map(), idle = new Map(), frames = [];
    const root = {document: {hidden: false}, addEventListener() {}, navigator: {scheduling: {isInputPending: () => inputPending}},
        setTimeout(fn) { timers.set(++id, fn); return id; }, clearTimeout(id) { timers.delete(id); },
        requestAnimationFrame(fn) { frames.push(fn); },
        requestIdleCallback(fn) { idle.set(++id, fn); return id; }, cancelIdleCallback(id) { idle.delete(id); }};
    vm.runInNewContext(source, {window: root, console, Promise});
    const timersOnce = () => { const copy = [...timers.values()]; timers.clear(); copy.forEach(fn => fn()); };
    const idleOnce = (budget = 30) => { const copy = [...idle.values()]; idle.clear(); copy.forEach(fn => fn({timeRemaining: () => budget})); };
    return {root, api: root.MyAgentUiTasks, frames, timers, idle, timersOnce, idleOnce,
        setInput(value) { inputPending = value; }};
}
(async () => {
    const f = fixture(); let ran = 0;
    const fallbackYield = f.api.yieldToMain();
    f.timersOnce(); await fallbackYield;
    let schedulerCalls = 0;
    f.root.scheduler = {yield() { schedulerCalls++; return Promise.resolve(); }};
    await f.api.yieldToMain(); assert.equal(schedulerCalls,1);
    delete f.root.scheduler;
    const messages=[];
    f.root.MessageChannel=class {constructor(){this.port1={};this.port2={postMessage:()=>messages.push(()=>this.port1.onmessage())};}};
    const yielded=[];
    const first=f.api.yieldToMain().then(()=>yielded.push(1)), second=f.api.yieldToMain().then(()=>yielded.push(2));
    assert.equal(f.timers.size,0,'MessageChannel fallback avoids nested timers');
    messages.shift()();await first;assert.deepEqual(yielded,[1]);messages.shift()();await second;assert.deepEqual(yielded,[1,2]);
    const paint = f.api.afterPaint(() => ++ran);
    assert.equal(ran, 0);
    f.frames.shift()(); assert.equal(ran, 0, 'RAF itself must remain free for feedback paint');
    f.timersOnce(); assert.equal(await paint, 1);

    f.api.warm('cancelled', () => ran++); f.api.cancel('cancelled');
    f.timersOnce(); f.idleOnce(); await tick(); assert.equal(ran, 1);
    f.api.warm('intent', () => ++ran); f.api.warm('intent', () => ran += 100);
    f.timersOnce(); f.idleOnce(1); await tick(); assert.equal(ran, 1, 'insufficient idle budget postpones warming');
    f.setInput(true); f.timersOnce(); f.idleOnce(); await tick(); assert.equal(ran, 1, 'pending input takes priority');
    f.setInput(false); f.timersOnce(); f.idleOnce(); await tick(); assert.equal(ran, 2, 'one warm per key');

    let release;
    f.api.warm('slow', () => new Promise(resolve => { release = resolve; }));
    f.api.warm('next', () => ++ran);
    f.timersOnce(); f.idleOnce(); await tick(); assert.equal(ran, 2, 'warm jobs do not fan out');
    release(); await tick(); f.timersOnce(); f.idleOnce(); await tick(); assert.equal(ran, 3);
    f.root.document.hidden = true;
    f.api.warm('hidden', () => ran++); assert.equal(f.timers.size, 0);
    f.root.document.hidden = false;
    const listeners = {};
    const element = {addEventListener(name, fn) { listeners[name] = fn; }};
    f.api.bindIntent(element, 'hover', () => ran++);
    listeners.pointerenter(); listeners.pointerleave(); f.timersOnce(); f.idleOnce(); await tick();
    assert.equal(ran, 3, 'passing over an entry never preloads it');
    console.log('UI feedback, intent cancellation, idle budget and bounded warming checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
