/**
 * Context breakdown card (hover panel) runtime checks.
 *
 * Two contracts live here:
 *  1. Composition rendering — mirrors the DSH ContextMeter panel: the bar's overall
 *     length stays the exact percent while the colored parts only proportion the
 *     heuristic breakdown, a zero-width lane is dropped instead of drawn as a
 *     hairline, and missing lanes are never invented.
 *  2. The card is one state, not two — a value without lanes still opens the card
 *     (legend hidden, "priced with the next request" note) and schedules exactly one
 *     lane refetch, so hovering cannot alternate between the plain tooltip and the
 *     card. These checks drive the real refresh function: the guard that limits the
 *     refetch to one per session is consumed inside it, and an earlier version that
 *     consumed it at scheduling time silently lost the only attempt whenever a
 *     request happened to be in flight.
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

const timers = [];
const frames = [];
const documentListeners = Object.create(null);
const recordCalls = [];
let cardEl = null;
let fetchCount = 0;
let nextResponse = null;
const tokenCache = Object.create(null);
let fetchGate = null;

const context = vm.createContext({
  console,
  Number,
  Array,
  Math,
  Object,
  Date,
  currentSessionId: 'demo',
  contextTokenInFlightBySession: Object.create(null),
  applyContextTokenLabelForCurrentSession() {},
  selectContextTokens(sid) { return tokenCache[sid] || null; },
  setContextTokensForSession(sid, estimated, threshold, breakdown) {
    tokenCache[sid] = { estimated, threshold, breakdown, updatedAt: Date.now() };
  },
  // Mirrors the real chain: applying a value is what asks for missing lanes.
  setContextTokenLabel(estimated, threshold, breakdown) {
    context.ctxCardReady = true;
    context.ensureContextBreakdownForCurrentSession(breakdown);
  },
  recordContextTokens(sid, estimated, threshold, breakdown) {
    recordCalls.push({ sid, breakdown, inFlightWhenRecorded: !!context.contextTokenInFlightBySession[sid] });
    context.setContextTokensForSession(sid, estimated, threshold, breakdown);
    if (sid === context.currentSessionId) context.setContextTokenLabel(estimated, threshold, breakdown);
  },
  async fetch() {
    fetchCount += 1;
    if (fetchGate) await fetchGate;
    return { ok: true, json: async () => nextResponse };
  },
  document: {
    getElementById(id) { return id === 'ctx-breakdown' ? cardEl : null; },
    addEventListener(type, handler) { documentListeners[type] = handler; },
  },
  requestAnimationFrame(callback) { frames.push(callback); },
  setTimeout(callback) { timers.push(callback); return timers.length; },
  clearTimeout() { timers.length = 0; },
});

vm.runInContext([
  slice(/^var CTX_BREAKDOWN_LANES = \[[^]*?^\];/m),
  slice(/^var CTX_CARD_HOVER_DELAY_MS = \d+;/m),
  slice(/^var CTX_CARD_NOTE_WITH_LANES = .*;$/m),
  slice(/^var CTX_CARD_NOTE_WITHOUT_LANES = .*;$/m),
  slice(/^var ctxCardOpenTimer = null;/m),
  slice(/^var ctxCardReady = false;/m),
  slice(/^var contextBreakdownRefetchTried = Object\.create\(null\);/m),
  slice(/^function contextBreakdownOrNull\(raw\) \{[^]*?^\}/m),
  slice(/^function closeContextBreakdownCard\(\) \{[^]*?^\}/m),
  slice(/^function openContextBreakdownCard\(\) \{[^]*?^\}/m),
  slice(/^function ensureContextBreakdownForCurrentSession\(breakdown\) \{[^]*?^\}/m),
  slice(/^function formatTokenCompact\(n\) \{[^]*?^\}/m),
  slice(/^function renderContextBreakdownCard\(card, pctDisp, estimated, threshold, breakdown\) \{[^]*?^\}/m),
  slice(/^function bindContextBreakdownHover\(el\) \{[^]*?^\}/m),
  slice(/^const CONTEXT_TOKEN_CACHE_TTL_MS = \d+;/m),
  slice(/^let contextTokenRequestSeq = \d+;/m),
  slice(/^async function refreshContextTokensFromServer\(sid, seq, force\) \{[^]*?^\}/m),
].join('\n\n'), context);

function fakeCard(laneKeys) {
  const rows = laneKeys.map(key => ({ key, textContent: '' }));
  const el = (initial) => Object.assign({ textContent: '' }, initial);
  const nodes = {
    '.ctx-card-pct': el(),
    '.ctx-card-figures': el(),
    '.ctx-card-bar': el({ innerHTML: '' }),
    '.ctx-card-note': el(),
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
    hidden: true,
    attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
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

function flushFrames() {
  while (frames.length) frames.shift()();
}

function flushTimers() {
  while (timers.length) timers.shift()();
}

// ── 1. Lane parts proportion the exact percent; rows and figures show ~ values ──
const card = fakeCard(['system_tokens', 'tools_tokens', 'message_tokens']);
cardEl = card;
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
assert.ok(card.nodes['.ctx-card-note'].textContent.indexOf('构成按本地估算') >= 0);

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
assert.equal(card.nodes['.ctx-card-note'].textContent, context.CTX_CARD_NOTE_WITHOUT_LANES);

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

// Deferred schemas are outside this request: show savings without adding them
// to the composition lanes or changing the meter's total.
const deferred = context.contextBreakdownOrNull({system_tokens: 1000, tools_tokens: 1000,
  message_tokens: 8000, deferred_tools_count: 99, deferred_tools_tokens: 25000, saved_tools_tokens: 24000});
assert.equal(deferred.deferred_tools_count, 99);
context.renderContextBreakdownCard(card, 50, 10000, 20000, deferred);
assert.ok(card.nodes['.ctx-card-note'].textContent.includes('已延迟 99 个工具'));
assert.ok(card.nodes['.ctx-card-note'].textContent.includes('24k tokens'));
assert.equal(segments(card.nodes['.ctx-card-bar'].innerHTML).reduce((sum, part) => sum + part.width, 0), 50);

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

// ── 6. Hover opens the card for any value, lanes or not (one popup, not two) ──
const trigger = { handlers: Object.create(null), addEventListener(type, handler) { this.handlers[type] = handler; } };
context.bindContextBreakdownHover(trigger);
context.bindContextBreakdownHover(trigger); // idempotent

context.ctxCardReady = false;
trigger.handlers.mouseenter();
flushTimers();
assert.equal(card.hidden, true, 'no value: hovering must not open an empty card');

context.ctxCardReady = true;
trigger.handlers.mouseenter();
assert.equal(timers.length, 1, 'hover must arm exactly one open timer');
flushTimers();
assert.equal(card.hidden, false, 'a value without lanes must still open the card');
assert.equal(card.attributes['aria-hidden'], 'false');
trigger.handlers.mouseleave();
assert.equal(card.hidden, true, 'leaving the trigger closes the card');
context.openContextBreakdownCard();
assert.equal(card.hidden, false);
documentListeners.keydown({ key: 'Escape' });
assert.equal(card.hidden, true, 'Escape closes the card');

// ── 7. Lane refetch policy, driven through the real refresh function ──
(async () => {
  const tick = () => new Promise(resolve => setTimeout(resolve, 0));
  const reset = (response, sid = 'demo') => {
    nextResponse = response;
    fetchCount = 0;
    recordCalls.length = 0;
    context.currentSessionId = sid;
    context.ctxCardReady = true;
    delete context.contextBreakdownRefetchTried[sid];
    delete context.contextTokenInFlightBySession[sid];
    delete tokenCache[sid];
    fetchGate = null;
  };
  const laneLess = { ok: true, estimated: 41230, threshold: 512000 };
  const withLanes = {
    ok: true,
    estimated: 41230,
    threshold: 512000,
    breakdown: { system_tokens: 4144, tools_tokens: 9070, message_tokens: 28016 },
  };

  // 7a. One deferred, forced refetch; a repeat does not re-ask.
  reset(laneLess);
  context.ensureContextBreakdownForCurrentSession(null);
  assert.equal(fetchCount, 0, 'never block the current paint with the refetch');
  flushFrames();
  await tick();
  assert.equal(fetchCount, 1);
  assert.equal(
    context.contextBreakdownRefetchTried.demo,
    true,
    'the guard is consumed by the request that actually starts',
  );
  context.ensureContextBreakdownForCurrentSession(null);
  flushFrames();
  await tick();
  assert.equal(fetchCount, 1, 'a second hover must not re-ask for the same session');

  // 7b. An in-flight request must not consume the guard: its lane-less answer retries.
  reset(laneLess);
  context.contextTokenInFlightBySession.demo = true;
  context.ensureContextBreakdownForCurrentSession(null);
  flushFrames();
  await tick();
  assert.equal(fetchCount, 0, 'an in-flight fetch already covers the session');
  assert.equal(
    context.contextBreakdownRefetchTried.demo,
    undefined,
    'a skipped attempt must not consume the only chance',
  );
  delete context.contextTokenInFlightBySession.demo;
  context.ensureContextBreakdownForCurrentSession(null);
  flushFrames();
  await tick();
  assert.equal(fetchCount, 1, 'the retry still happens once the in-flight mark clears');

  // 7c. Lanes clear the guard, so a composition that regresses is refilled once more.
  reset(withLanes);
  await context.refreshContextTokensFromServer('demo', null, false);
  assert.equal(context.contextBreakdownRefetchTried.demo, undefined, 'lanes clear the guard');
  flushFrames();
  await tick();
  assert.equal(fetchCount, 1, 'lanes present: no extra request');
  nextResponse = laneLess;
  delete tokenCache.demo;
  fetchCount = 0;
  context.ensureContextBreakdownForCurrentSession(null);
  flushFrames();
  await tick();
  assert.equal(fetchCount, 1, 'a regression is refilled exactly once');

  // 7d. The in-flight mark clears before the value is recorded, or the refetch
  // scheduled by that very value would look redundant and never happen.
  reset(laneLess);
  await context.refreshContextTokensFromServer('demo', null, false);
  assert.equal(recordCalls.length, 1);
  assert.equal(
    recordCalls[0].inFlightWhenRecorded,
    false,
    'the lane refetch must not arrive while the same session is still marked in flight',
  );
  flushFrames();
  await tick();
  assert.equal(fetchCount, 2, 'the lane-less response starts exactly one follow-up request');

  // 7e. Switching away during a forced refetch keeps the response in that
  // session's cache without painting it over the newly selected session.
  reset(withLanes, 'away');
  context.setContextTokensForSession('away', 41230, 512000, null);
  let release;
  fetchGate = new Promise(resolve => { release = resolve; });
  const pending = context.refreshContextTokensFromServer('away', null, true);
  context.currentSessionId = 'other';
  release();
  await pending;
  assert.equal(recordCalls.length, 0, 'a background session never changes the current label');
  assert.deepEqual(tokenCache.away.breakdown, withLanes.breakdown);
  assert.equal(context.contextBreakdownRefetchTried.away, undefined);
  context.currentSessionId = 'away';
  await context.refreshContextTokensFromServer('away', null, false);
  flushFrames();
  await tick();
  assert.equal(fetchCount, 1, 'returning within the cache TTL uses the completed refetch');

  // 7f. An obsolete paint sequence still retains the successful session data.
  reset(withLanes, 'superseded');
  await context.refreshContextTokensFromServer('superseded', -1, true);
  assert.equal(recordCalls.length, 0);
  assert.deepEqual(tokenCache.superseded.breakdown, withLanes.breakdown);

  console.log('context breakdown card runtime checks passed');
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
