const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../frontend/src/app/modules/ui-performance.js'), 'utf8');
const storage = new Map();
let writes = 0, now = 0;
function setup() {
  const events = {};
  const c = vm.createContext({
    window: { addEventListener() {} }, document: { hidden: false, addEventListener(k, fn) { events[k] = fn; } },
    localStorage: { getItem: k => storage.get(k), setItem(k, v) { writes++; storage.set(k, v); }, removeItem: k => storage.delete(k) },
    setTimeout: () => 1, clearTimeout() {}, performance: { now: () => now },
  });
  vm.runInContext(source + '\nglobalThis.metrics = uiPerformance;', c);
  return { c, events, api: c.window.__MYAGENT_UI_PERF__ };
}
const { c, api, events } = setup();
for (let i = 0; i < 1000; i++) { c.metrics.sample('s', 'stream.flush', 2); c.metrics.count('s', 'chars', 1); }
assert.equal(writes, 0, 'hot path must not write localStorage per frame');
let report = api.snapshot().reports[0];
assert.equal(report.sessions[0].timings['stream.flush'].count, 1000);
assert.equal(report.sessions[0].timings['stream.flush'].p95UpperMs, 2);
assert.equal(report.sessions[0].counters.chars, 1000);
c.document.hidden = true;
c.metrics.sample('s', 'stream.flush', 5000);
events.visibilitychange();
assert.equal(writes, 1);
c.document.hidden = false; now = 10000; events.visibilitychange();
now += 16;
c.metrics.sample('s', 'stream.frameGap', 8000);
assert(!api.snapshot().reports[0].sessions[0].timings['stream.frameGap']);
c.metrics.sample('s', 'stream.frameGap', 16);
for (let i = 0; i < 20; i++) c.metrics.count(`s-${i}`, 'opens');
api.flush();
assert.equal(api.snapshot().reports[0].sessions.length, 12);
const next = setup();
assert.equal(next.api.snapshot().reports.length, 2, 'reports survive reload');
next.api.reset();
assert.equal(next.api.snapshot().reports.length, 1);
assert.equal(storage.size, 0);
console.log('UI performance runtime checks passed');
