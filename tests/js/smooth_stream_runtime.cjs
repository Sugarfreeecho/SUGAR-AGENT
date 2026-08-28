const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..', '..');
const source = fs.readFileSync(
  path.join(root, 'frontend', 'src', 'app', 'modules', 'smooth-stream.js'),
  'utf8',
);

let now = 0;
let nextRaf = 1;
const frames = new Map();
const windowObject = {
  __MYAGENT_FEATURES__: { smoothStream: true },
  matchMedia: () => ({ matches: false }),
};
const context = vm.createContext({
  window: windowObject,
  performance: { now: () => now },
  requestAnimationFrame(callback) {
    const id = nextRaf++;
    frames.set(id, callback);
    return id;
  },
  cancelAnimationFrame(id) { frames.delete(id); },
  setTimeout() { return 1; },
  clearTimeout() {},
  Set,
  WeakMap,
  Math,
  Number,
  String,
  Object,
});

vm.runInContext(source + `
globalThis.__smoothStreamTest = {
  isSmoothStreamEnabled,
  isSmoothStreamActive,
  computeSmoothRevealCount,
  takeSmoothTextPrefix,
  computeSmoothFollowStep,
  smoothFollowController,
  animateSmoothTraceRowInsertion,
  mutateSmoothTraceRowHeight,
  config: SMOOTH_STREAM_CONFIG,
  followProfiles: SMOOTH_STREAM_FOLLOW_PROFILES,
};`, context);

const api = context.__smoothStreamTest;

assert.equal(api.isSmoothStreamEnabled(), true);
assert.equal(api.computeSmoothRevealCount(4, 16.67), 1);
assert.equal(api.computeSmoothRevealCount(80, 16.67), 10);
assert.equal(api.computeSmoothRevealCount(3, 1000), 3);

const unicode = api.takeSmoothTextPrefix('A😀中', 2);
assert.equal(unicode.segment, 'A😀');
assert.equal(unicode.rest, '中');
assert.equal(unicode.count, 2);

const follow = api.computeSmoothFollowStep(160, 16.67, 35, 'row');
assert(follow.advancePx > 0 && follow.advancePx < 160);
assert(
  follow.advancePx <= api.followProfiles.row.maxFollowSpeedPxPerSec * 16.67 / 1000 + 0.001,
  'follow advance must honor the configured px/s ceiling',
);

const tailFollow = api.computeSmoothFollowStep(4, 16.67, 35, 'row');
assert(
  tailFollow.advancePx >= api.followProfiles.row.minFollowSpeedPxPerSec * 16.67 / 1000 - 0.001,
  'the row channel must retain the prompt tail convergence',
);
const textTailFollow = api.computeSmoothFollowStep(4, 16.67, 35, 'text');
assert.equal(api.followProfiles.text.minFollowSpeedPxPerSec, 0);
assert(
  textTailFollow.advancePx < tailFollow.advancePx,
  'the text channel must retain the original easing tail without the row speed floor',
);

let lineLag = 18.94;
let lineFrames = 0;
while (lineLag > 0.25 && lineFrames < 120) {
  lineLag -= api.computeSmoothFollowStep(lineLag, 16.67, 35, 'row').advancePx;
  lineFrames += 1;
}
assert(
  lineFrames <= 20,
  `a one-line height change should settle promptly; took ${lineFrames} frames`,
);

function fakePort() {
  const listeners = Object.create(null);
  const attrs = new Map();
  return {
    isConnected: true,
    scrollHeight: 500,
    clientHeight: 100,
    scrollTop: 300,
    addEventListener(name, callback) { listeners[name] = callback; },
    setAttribute(name, value) { attrs.set(name, String(value)); },
    removeAttribute(name) { attrs.delete(name); },
    getAttribute(name) { return attrs.has(name) ? attrs.get(name) : null; },
    listeners,
  };
}

function runNextFrame(delta = 16.67) {
  const entry = frames.entries().next();
  assert.equal(entry.done, false, 'expected a queued animation frame');
  const [id, callback] = entry.value;
  frames.delete(id);
  now += delta;
  callback(now);
}

const port = fakePort();
let unpinned = 0;
api.smoothFollowController.request(port, {
  speedCps: 35,
  onUnpin() { unpinned += 1; },
});
runNextFrame();
assert(port.scrollTop > 300 && port.scrollTop < 400, 'a material follow gap must glide instead of snap');
assert.equal(port.getAttribute('data-smooth-follow-owned'), '1');

port.listeners.wheel({ deltaY: -8 });
assert.equal(unpinned, 1, 'an upward reader gesture must release follow');
assert.equal(api.smoothFollowController.isFollowing(port), false);
assert.equal(api.smoothFollowController.isReaderDetached(port), true);
assert.equal(port.getAttribute('data-smooth-follow-owned'), null);

const queuedAfterUnpin = frames.size;
api.smoothFollowController.request(port, { speedCps: 35 });
assert.equal(frames.size, queuedAfterUnpin, 'detached reader must not be reclaimed');
api.smoothFollowController.clearReaderDetached(port);
api.smoothFollowController.request(port, { speedCps: 35 });
assert.equal(api.smoothFollowController.isFollowing(port), true);
api.smoothFollowController.cancel(port);
assert.equal(api.smoothFollowController.isFollowing(port), false);
assert.equal(unpinned, 1, 'programmatic final-card cancellation is not a reader unpin');
port.scrollTop = 384;
assert.equal(api.smoothFollowController.snapToBottom(port), true);
assert.equal(port.scrollTop, 400, 'end-of-stream convergence must remove the easing tail');
while (frames.size) runNextFrame();

const splitChannelPort = fakePort();
splitChannelPort.scrollTop = 400;
splitChannelPort.scrollHeight = 504;
api.smoothFollowController.request(splitChannelPort, { speedCps: 35, channel: 'row' });
runNextFrame();
const rowChannelAdvance = splitChannelPort.scrollTop - 400;
assert(
  rowChannelAdvance >= 0.99,
  'a whole-row height delta must use the row tail-speed profile',
);
const beforeTextDelta = splitChannelPort.scrollTop;
splitChannelPort.scrollHeight = 508;
api.smoothFollowController.request(splitChannelPort, { speedCps: 35, channel: 'text' });
runNextFrame();
assert(
  splitChannelPort.scrollTop - beforeTextDelta < 0.99,
  'a later text-wrap height delta on the same viewport must switch to the text profile',
);
api.smoothFollowController.cancel(splitChannelPort);
while (frames.size) runNextFrame();

function fakeTraceHeightSource(initialHeight) {
  let height = initialHeight;
  let streaming = true;
  let layoutAnimating = false;
  const item = {
    parentElement: null,
    getBoundingClientRect() { return { height }; },
  };
  return {
    querySelectorAll(selector) { return selector === '.feed-item' ? [item] : []; },
    querySelector(selector) {
      if (selector === '[data-smooth-trace-layout-owned]') return layoutAnimating ? {} : null;
      return streaming || layoutAnimating ? {} : null;
    },
    setHeight(value) { height = value; },
    setStreaming(value) { streaming = !!value; },
    setLayoutAnimating(value) { layoutAnimating = !!value; },
  };
}

const caughtUpPort = fakePort();
const traceHeightSource = fakeTraceHeightSource(100);
caughtUpPort.scrollTop = 400;
api.smoothFollowController.request(caughtUpPort, {
  speedCps: 35,
  traceHeightSource,
});
runNextFrame();
assert.equal(api.smoothFollowController.isFollowing(caughtUpPort), true);
assert.equal(
  caughtUpPort.getAttribute('data-smooth-follow-owned'),
  '1',
  'catching up between wrapped lines must retain stream ownership',
);
caughtUpPort.scrollHeight = 518;
traceHeightSource.setHeight(119);
// Simulate a browser-reported floor snap. The retained float extent, rather
// than this rounded engine value, must drive the next wrapped line.
caughtUpPort.scrollTop = 418;
runNextFrame();
assert(
  caughtUpPort.scrollTop > 400 && caughtUpPort.scrollTop < 418,
  'an async layout growth must resume from the retained float extent without another request',
);
for (let i = 0; i < 8; i += 1) runNextFrame();
assert(
  caughtUpPort.scrollTop < 418,
  'ordinary streaming height changes must retain the original glide',
);
traceHeightSource.setStreaming(false);
runNextFrame();
assert.equal(
  caughtUpPort.scrollTop,
  418,
  'finished streaming with stable trace-item height must end residual lag',
);
caughtUpPort.scrollHeight = 536;
traceHeightSource.setHeight(138);
traceHeightSource.setLayoutAnimating(true);
runNextFrame();
assert(
  caughtUpPort.scrollTop > 418 && caughtUpPort.scrollTop < 436,
  'new height growth after convergence must start a fresh glide instead of snapping',
);
traceHeightSource.setLayoutAnimating(false);
for (let i = 0; i < 4; i += 1) runNextFrame();
assert.equal(
  caughtUpPort.scrollTop,
  436,
  'a completed trace-row layout animation must settle once item height is stable',
);
api.smoothFollowController.cancel(caughtUpPort);

const layoutOwnedPort = fakePort();
const layoutOwnedSource = fakeTraceHeightSource(104);
layoutOwnedSource.setStreaming(false);
layoutOwnedSource.setLayoutAnimating(true);
layoutOwnedPort.scrollTop = 400;
layoutOwnedPort.scrollHeight = 504;
api.smoothFollowController.request(layoutOwnedPort, {
  speedCps: 35,
  channel: 'text',
  traceHeightSource: layoutOwnedSource,
});
runNextFrame();
assert(
  layoutOwnedPort.scrollTop - 400 >= 0.99,
  'a layout-owned row animation must take row-channel priority over a concurrent text request',
);
api.smoothFollowController.cancel(layoutOwnedPort);
while (frames.size) runNextFrame();

function fakeTraceRow(initialHeight) {
  let height = initialHeight;
  let animation = null;
  const attrs = new Map();
  const styleValues = new Map();
  return {
    isConnected: true,
    style: {
      set overflow(value) { styleValues.set('overflow', value); },
      get overflow() { return styleValues.get('overflow') || ''; },
      removeProperty(name) { styleValues.delete(name); },
    },
    setAttribute(name, value) { attrs.set(name, String(value)); },
    removeAttribute(name) { attrs.delete(name); },
    getAttribute(name) { return attrs.has(name) ? attrs.get(name) : null; },
    getBoundingClientRect() { return { height }; },
    setHeight(value) { height = value; },
    animate(keyframes, options) {
      animation = { keyframes, options, cancel() { if (this.oncancel) this.oncancel(); } };
      return animation;
    },
    getAnimation() { return animation; },
  };
}

const insertedRow = fakeTraceRow(44);
assert.equal(api.animateSmoothTraceRowInsertion(insertedRow), true);
assert.equal(insertedRow.getAnimation().keyframes[0].height, '0px');
assert.equal(insertedRow.getAnimation().keyframes[1].height, '44px');
assert.equal(insertedRow.getAnimation().options.duration, 190);
insertedRow.getAnimation().onfinish();
assert.equal(insertedRow.getAttribute('data-smooth-trace-layout-owned'), null);

const collapsingRow = fakeTraceRow(96);
api.mutateSmoothTraceRowHeight(collapsingRow, () => collapsingRow.setHeight(28));
assert.equal(collapsingRow.getAnimation().keyframes[0].height, '96px');
assert.equal(collapsingRow.getAnimation().keyframes[1].height, '28px');
assert.equal(collapsingRow.getAnimation().options.duration, 230);

windowObject.__MYAGENT_FEATURES__.smoothStream = false;
assert.equal(api.isSmoothStreamActive(), false);

console.log('smooth stream runtime checks passed');
