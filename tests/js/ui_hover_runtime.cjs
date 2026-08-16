const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..', '..');
const fullSource = fs.readFileSync(
  path.join(root, 'frontend/src/app/modules/toc-todo.js'),
  'utf8',
);
const source = fullSource.slice(0, fullSource.indexOf('/**'));
const documentListeners = Object.create(null);
const windowListeners = Object.create(null);
const animationFrames = [];
let hitTarget = null;

function classList(initial) {
  const values = new Set(initial || []);
  return {
    add(value) { values.add(value); },
    remove(value) { values.delete(value); },
    contains(value) { return values.has(value); },
  };
}

const document = {
  _uiHoverTipGlobalCleanupBound: false,
  visibilityState: 'visible',
  addEventListener(type, handler) { documentListeners[type] = handler; },
  elementFromPoint() { return hitTarget; },
  getElementById() { return null; },
};
const window = {
  innerWidth: 1200,
  innerHeight: 800,
  addEventListener(type, handler) { windowListeners[type] = handler; },
};
const context = vm.createContext({
  console,
  document,
  window,
  Number,
  requestAnimationFrame(callback) { animationFrames.push(callback); },
});
vm.runInContext(`
var uiHoverTooltipEl = null;
var hoverTooltipMoveScheduled = false;
var uiHoverTipScrollReconcileScheduled = false;
var uiHoverTipTimer = null;
var uiHoverTipActiveEl = null;
var uiHoverTipLastEv = null;
${source}
`, context);

const tooltip = {
  classList: classList(['is-visible']),
  style: {},
  offsetWidth: 180,
  offsetHeight: 80,
};
const child = {};
const trigger = {
  isConnected: true,
  contains(node) { return node === child; },
  matches(selector) { return selector === ':hover'; },
};
const pointer = { clientX: 240, clientY: 160 };
context.uiHoverTooltipEl = tooltip;
context.uiHoverTipActiveEl = trigger;
context.uiHoverTipLastEv = pointer;
hitTarget = child;
context.bindUiHoverTipGlobalCleanup();

assert.equal(typeof documentListeners.scroll, 'function');
documentListeners.scroll({ target: { id: 'streaming-chat' } });
documentListeners.scroll({ target: { id: 'streaming-chat' } });
assert.equal(animationFrames.length, 1, 'burst scroll events should share one layout reconciliation');
animationFrames.shift()();
assert.equal(
  tooltip.classList.contains('is-visible'),
  true,
  'an unrelated live-generation scroll must preserve the hovered tooltip',
);
assert.equal(tooltip.style.left, '254px');
assert.equal(tooltip.style.top, '174px');

hitTarget = { id: 'content-under-pointer-after-scroll' };
documentListeners.scroll({ target: { id: 'picker-list' } });
animationFrames.shift()();
assert.equal(
  tooltip.classList.contains('is-visible'),
  false,
  'a scroll that moves the trigger away from the pointer must dismiss the tooltip',
);

console.log('ui hover runtime checks passed');
