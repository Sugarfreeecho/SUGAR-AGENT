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
  smoothFollowEaseOutCubic,
  smoothFollowController,
  animateSmoothTraceRowInsertion,
  mutateSmoothTraceRowHeight,
  config: SMOOTH_STREAM_CONFIG,
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

assert.equal(api.config.followDurationMs, 160);
assert.equal(api.config.maxFollowStepPx, 20);
assert.equal(api.smoothFollowEaseOutCubic(0), 0);
assert.equal(api.smoothFollowEaseOutCubic(1), 1);

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
api.smoothFollowController.request(port);
assert.equal(frames.size, queuedAfterUnpin, 'detached reader must not be reclaimed');
api.smoothFollowController.clearReaderDetached(port);
api.smoothFollowController.request(port);
assert.equal(api.smoothFollowController.isFollowing(port), true);
api.smoothFollowController.cancel(port);
assert.equal(api.smoothFollowController.isFollowing(port), false);
assert.equal(unpinned, 1, 'programmatic final-card cancellation is not a reader unpin');
port.scrollTop = 384;
assert.equal(api.smoothFollowController.snapToBottom(port), true);
assert.equal(port.scrollTop, 400, 'end-of-stream convergence must remove the easing tail');
while (frames.size) runNextFrame();

function followedPort(options) {
  const p = fakePort();
  p.scrollTop = 400;
  api.smoothFollowController.request(p, options);
  runNextFrame();
  assert.equal(p.scrollTop, 400);
  return p;
}

function recordedFrame(p, delta = 16.67) {
  const before = p.scrollTop;
  runNextFrame(delta);
  const moved = p.scrollTop - before;
  assert(moved <= api.config.maxFollowStepPx + 0.0001,
    `follow wrote ${moved}px in one frame`);
  return moved;
}

const textPort = fakePort();
const rowPort = fakePort();
for (const p of [textPort, rowPort]) p.scrollTop = 400;
api.smoothFollowController.request(textPort, { channel: 'text' });
api.smoothFollowController.request(rowPort, { channel: 'row' });
assert.equal(frames.size, 1, 'both viewports share one follow rAF');
runNextFrame();
textPort.scrollHeight += 19;
rowPort.scrollHeight += 19;
runNextFrame();
assert.equal(textPort.scrollTop, rowPort.scrollTop,
  'text wrapping and whole-row growth must use identical motion');
api.smoothFollowController.cancel(textPort);
api.smoothFollowController.cancel(rowPort);

const oneLine = followedPort();
oneLine.scrollHeight += 19;
let lineFrames = 0;
let lineMaxStep = 0;
while (oneLine.scrollTop < 419 && lineFrames < 30) {
  lineMaxStep = Math.max(lineMaxStep, recordedFrame(oneLine));
  lineFrames++;
}
assert(lineFrames > 2 && lineFrames * 16.67 <= 250,
  `19px wrapping should glide then stop; took ${lineFrames} frames`);
assert(lineMaxStep < 20);
for (let i = 0; i < 20; i++) {
  assert.equal(recordedFrame(oneLine), 0, 'a pause must have no lingering tail');
}
api.smoothFollowController.cancel(oneLine);

const slowOutput = followedPort();
const slowMovingFrames = [];
for (let burst = 0; burst < 2; burst++) {
  slowOutput.scrollHeight += 19;
  let movingFrames = 0;
  while (slowOutput.scrollTop < slowOutput.scrollHeight - slowOutput.clientHeight) {
    recordedFrame(slowOutput);
    assert(++movingFrames * 16.67 <= 250);
  }
  slowMovingFrames.push(movingFrames);
  for (let i = 0; i < 45; i++) assert.equal(recordedFrame(slowOutput), 0);
}
api.smoothFollowController.cancel(slowOutput);

const fastOutput = followedPort();
let fastPeakLag = 0;
let fastPeakStep = 0;
for (let i = 0; i < 120; i++) {
  if (i % 2 === 0) fastOutput.scrollHeight += 19; // one wrapped line each ~33ms
  fastPeakStep = Math.max(fastPeakStep, recordedFrame(fastOutput));
  fastPeakLag = Math.max(fastPeakLag,
    fastOutput.scrollHeight - fastOutput.clientHeight - fastOutput.scrollTop);
}
assert(fastPeakLag <= 19 * 1.5,
  `frequent wrapping lagged ${fastPeakLag}px, above 1.5 lines`);
assert(fastPeakStep > 0 && fastPeakStep < 20);
api.smoothFollowController.cancel(fastOutput);

const growingRow = followedPort();
let rowPeakLag = 0;
let rowPeakStep = 0;
for (let i = 0; i < 12; i++) {
  growingRow.scrollHeight += 10; // WAAPI height growth on each frame
  const moved = recordedFrame(growingRow);
  assert(moved > 0,
    'continuous retargeting must still move on every frame');
  rowPeakStep = Math.max(rowPeakStep, moved);
  rowPeakLag = Math.max(rowPeakLag,
    growingRow.scrollHeight - growingRow.clientHeight - growingRow.scrollTop);
}
assert(rowPeakLag <= 19 * 1.5);
let rowSettleFrames = 0;
while (growingRow.scrollTop < 520 && rowSettleFrames < 20) {
  recordedFrame(growingRow);
  rowSettleFrames++;
}
assert(rowSettleFrames * 16.67 <= 250);
api.smoothFollowController.cancel(growingRow);

const mediumRow = followedPort();
mediumRow.scrollHeight += 200;
let mediumFrames = 0;
let mediumPeakStep = 0;
while (mediumRow.scrollTop < 600 && mediumFrames < 30) {
  mediumPeakStep = Math.max(mediumPeakStep, recordedFrame(mediumRow));
  mediumFrames++;
}
assert(mediumFrames * 16.67 <= 250);
api.smoothFollowController.cancel(mediumRow);

const largeRow = followedPort();
largeRow.scrollHeight += 400;
for (let i = 0; i < 15; i++) recordedFrame(largeRow);
assert(largeRow.scrollTop < 800,
  'a large backlog must not break the frame cap to meet the duration');
while (largeRow.scrollTop < 800) recordedFrame(largeRow);
api.smoothFollowController.cancel(largeRow);

const collapsingRowPort = followedPort();
collapsingRowPort.scrollHeight += 60;
while (collapsingRowPort.scrollTop < 460) recordedFrame(collapsingRowPort);
collapsingRowPort.scrollHeight -= 40;
collapsingRowPort.scrollTop = 420; // browser clamps when the floor shrinks
runNextFrame();
assert.equal(collapsingRowPort.scrollTop, 420,
  'a shrinking scroll range must not rebound toward the old floor');
api.smoothFollowController.cancel(collapsingRowPort);

const slowFrame = followedPort();
slowFrame.scrollHeight += 200;
assert(recordedFrame(slowFrame, 50) <= 20,
  'a long frame must retain the absolute 20px displacement cap');
api.smoothFollowController.cancel(slowFrame);

const caughtUpPort = followedPort({ traceHeightSource: {
  querySelectorAll() { throw new Error('following must not scan feed rows'); },
  querySelector() { throw new Error('following must not inspect streaming flags'); },
} });
assert.equal(caughtUpPort.getAttribute('data-smooth-follow-owned'), '1');
caughtUpPort.scrollHeight += 18;
// An engine-reported floor snap must not replace the retained float position.
caughtUpPort.scrollTop = 418;
runNextFrame();
assert(caughtUpPort.scrollTop > 400 && caughtUpPort.scrollTop < 418);
for (let i = 0; i < 15; i++) recordedFrame(caughtUpPort);
assert.equal(caughtUpPort.scrollTop, 418,
  'a still-streaming row must settle without waiting for its streaming flag');
caughtUpPort.scrollHeight += 18;
assert(recordedFrame(caughtUpPort) > 0,
  'later async layout growth must start a fresh glide without a request');
api.smoothFollowController.cancel(caughtUpPort);

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
const disabledPort = fakePort();
api.smoothFollowController.request(disabledPort);
assert.equal(disabledPort.scrollTop, disabledPort.scrollHeight,
  'disabled smooth streaming must retain the legacy immediate scroll');
assert.equal(api.smoothFollowController.isFollowing(disabledPort), false);

if (process.argv.includes('--report')) {
  console.log(JSON.stringify({
    frameMs: 16.67,
    single19: { settleMs: +(lineFrames * 16.67).toFixed(1), maxStepPx: +lineMaxStep.toFixed(2) },
    slow19: { settleMs: slowMovingFrames.map(n => +(n * 16.67).toFixed(1)),
      stoppedFramesPerBurst: 45 },
    fast19Every33ms: { maxLagPx: +fastPeakLag.toFixed(2),
      maxLagLines: +(fastPeakLag / 19).toFixed(2), maxStepPx: +fastPeakStep.toFixed(2) },
    growingRow10pxPerFrame: { maxLagPx: +rowPeakLag.toFixed(2),
      settleAfterGrowthMs: +(rowSettleFrames * 16.67).toFixed(1),
      maxStepPx: +rowPeakStep.toFixed(2) },
    single200: { settleMs: +(mediumFrames * 16.67).toFixed(1),
      maxStepPx: +mediumPeakStep.toFixed(2) },
  }, null, 2));
} else console.log('smooth stream runtime checks passed');
