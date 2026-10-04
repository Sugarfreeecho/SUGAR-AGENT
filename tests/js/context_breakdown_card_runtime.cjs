/**
 * Context breakdown card (hover panel) runtime checks.
 *
 * Mirrors the DSH ContextMeter panel contract: the bar's overall length stays the
 * exact percent while the colored parts only proportion the heuristic breakdown,
 * a zero-width lane is dropped instead of drawn as a hairline, and a card without
 * breakdown data falls back to one neutral segment with the legend rows hidden.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..', '..');
const source = fs.readFileSync(
  path.join(root, 'frontend/src/app/modules/session-scroll-history.js'),
  'utf8',
);

function slice(pattern) {
  const match = source.match(pattern);
  assert.ok(match, `missing source for ${pattern}`);
  return match[0];
}

const context = vm.createContext({ console, Number, Array, Math });
vm.runInContext([
  slice(/^var CTX_BREAKDOWN_LANES = \[[^]*?^\];/m),
  slice(/^function contextBreakdownOrNull\(raw\) \{[^]*?^\}/m),
  slice(/^function formatTokenCompact\(n\) \{[^]*?^\}/m),
  slice(/^function renderContextBreakdownCard\(card, pctDisp, estimated, threshold, breakdown\) \{[^]*?^\}/m),
].join('\n\n'), context);

function fakeCard(laneKeys) {
  const rows = laneKeys.map(key => ({ key, textContent: '' }));
  const el = (initial) => Object.assign({ textContent: '' }, initial);
  const nodes = {
    '.ctx-card-pct': el(),
    '.ctx-card-figures': el(),
    '.ctx-card-bar': el({ innerHTML: '' }),
    '.ctx-card-rows': el({
      hidden: true,
      querySelectorAll: () => rows.map(row => ({
        getAttribute: name => (name === 'data-lane' ? row.key : null),
        set textContent(value) { row.textContent = value; },
        get textContent() { return row.textContent; },
      })),
    }),
  };
  return {
    nodes,
    rows,
    querySelector(selector) { return nodes[selector] || null; },
  };
}

function segments(innerHTML) {
  const found = [];
  const pattern = /class="ctx-card-seg(?: ctx-lane-(\w+))?" style="width:([\d.]+)%"/g;
  let match = pattern.exec(innerHTML);
  while (match) {
    found.push({ lane: match[1] || null, width: Number(match[2]) });
    match = pattern.exec(innerHTML);
  }
  return found;
}

// ── 1. Lane parts proportion the exact percent; rows and figures show ~ values ──
const card = fakeCard(['system_tokens', 'tools_tokens', 'message_tokens']);
context.renderContextBreakdownCard(
  card,
  50,
  10000,
  20000,
  { system_tokens: 1000, tools_tokens: 1000, message_tokens: 8000 },
);
assert.equal(card.nodes['.ctx-card-pct'].textContent, '50%');
assert.equal(card.nodes['.ctx-card-figures'].textContent, '~10k / 20k');
assert.equal(card.nodes['.ctx-card-rows'].hidden, false);
const parts = segments(card.nodes['.ctx-card-bar'].innerHTML);
assert.deepEqual(parts, [
  { lane: 'system', width: 5 },
  { lane: 'tools', width: 5 },
  { lane: 'messages', width: 40 },
]);
assert.deepEqual(card.rows.map(row => row.textContent), ['~1k', '~1k', '~8k']);
// The colored parts add up to the exact reading, never more: 5 + 5 + 40 = 50.
assert.equal(parts.reduce((sum, part) => sum + part.width, 0), 50);

// ── 2. A zero-width lane is dropped, not drawn as a hairline ──
context.renderContextBreakdownCard(
  card,
  25,
  5000,
  20000,
  { system_tokens: 0, tools_tokens: 1000, message_tokens: 9000 },
);
assert.deepEqual(segments(card.nodes['.ctx-card-bar'].innerHTML), [
  { lane: 'tools', width: 2.5 },
  { lane: 'messages', width: 22.5 },
]);
assert.deepEqual(card.rows.map(row => row.textContent), ['~0', '~1k', '~9k']);

// ── 3. Without breakdown data the bar is one neutral segment and rows stay hidden ──
context.renderContextBreakdownCard(card, 42, 4200, 10000, null);
assert.deepEqual(segments(card.nodes['.ctx-card-bar'].innerHTML), [{ lane: null, width: 42 }]);
assert.equal(card.nodes['.ctx-card-rows'].hidden, true);
assert.equal(card.nodes['.ctx-card-figures'].textContent, '~4.2k / 10k');

// ── 4. Over-threshold readings clamp the fallback segment to a full bar ──
context.renderContextBreakdownCard(card, 137.5, 5500, 4000, null);
assert.deepEqual(segments(card.nodes['.ctx-card-bar'].innerHTML), [{ lane: null, width: 100 }]);

// ── 5. Malformed lanes are rejected instead of drawing a wrong composition ──
assert.equal(context.contextBreakdownOrNull(null), null);
assert.equal(context.contextBreakdownOrNull({ system_tokens: 1, tools_tokens: 2 }), null);
assert.equal(
  context.contextBreakdownOrNull({ system_tokens: 1, tools_tokens: 2, message_tokens: -3 }),
  null,
);
const coerced = context.contextBreakdownOrNull({ system_tokens: 1, tools_tokens: '2', message_tokens: 3 });
// Field-by-field: the object comes from the VM realm, so a deep-equal against a
// host-realm literal would compare prototypes instead of values.
assert.equal(coerced.system_tokens, 1);
assert.equal(coerced.tools_tokens, 2);
assert.equal(coerced.message_tokens, 3);

// A rejected payload must render like "no breakdown" rather than trusting it.
context.renderContextBreakdownCard(
  card,
  10,
  1000,
  10000,
  context.contextBreakdownOrNull({ system_tokens: 1, tools_tokens: 2, message_tokens: -3 }),
);
assert.equal(card.nodes['.ctx-card-rows'].hidden, true);
assert.deepEqual(segments(card.nodes['.ctx-card-bar'].innerHTML), [{ lane: null, width: 10 }]);

console.log('context breakdown card runtime checks passed');
