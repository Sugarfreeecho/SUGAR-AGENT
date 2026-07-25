const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..', '..');
const source = fs.readFileSync(
  path.join(root, 'frontend', 'src', 'app', 'modules', 'layout-panels.js'),
  'utf8',
);
const start = source.indexOf('var chatOverlayScrollbarRaf');
const end = source.indexOf('function ensureChatOverlayScrollbarPortal', start);
assert(start >= 0 && end > start, 'overlay scrollbar metric source section is missing');

const context = vm.createContext({
  Map,
  Math,
  Number,
});
vm.runInContext(source.slice(start, end), context);

assert.strictEqual(
  context.computeChatOverlayScrollbarGeometry(600, 600, 0),
  null,
  'a non-overflowing container must not render an overlay scrollbar',
);

const normal = context.computeChatOverlayScrollbarGeometry(600, 2400, 900);
assert.strictEqual(normal.trackHeight, 600);
assert.strictEqual(normal.spacerHeight, 2400);
assert.strictEqual(normal.scrollTop, 900);

const long = context.computeChatOverlayScrollbarGeometry(600, 60000, 0);
assert.strictEqual(long.trackHeight, 600);
assert.strictEqual(long.spacerHeight, 60000);
assert.strictEqual(long.scrollTop, 0);

const clamped = context.computeChatOverlayScrollbarGeometry(600, 2400, 99999);
assert.strictEqual(clamped.scrollTop, 1800, 'native overlay scroll position must clamp to its range');

assert(context.CHAT_OVERLAY_SCROLL_TARGET_SELECTOR.includes('#chat-container'));
assert(context.CHAT_OVERLAY_SCROLL_TARGET_SELECTOR.includes('.process-aggregate-body'));
assert(context.CHAT_OVERLAY_SCROLL_TARGET_SELECTOR.includes('.feed-chunk-scroller'));
assert(context.CHAT_OVERLAY_SCROLL_TARGET_SELECTOR.includes('.chat-toc-list'));

process.stdout.write('overlay scrollbar runtime checks passed\n');
