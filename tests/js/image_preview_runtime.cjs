const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'frontend/src/app/modules/workspace-media.js'), 'utf8');

function harness(text = source, asyncDecode = false) {
  const frames = new Map();
  const timers = new Map();
  const styleKeys = [];
  const resizeCallbacks = [];
  const decodes = [];
  const metrics = { layoutReads: 0, styleWrites: 0, frameRequests: 0, scrollWrites: 0 };
  let frameId = 0;
  let timerId = 0;
  const viewport = { width: 1000, height: 600 };
  class Element {
    constructor(tag) {
      this.tagName = tag;
      this.children = [];
      this.listeners = {};
      this.className = '';
      this.open = false;
      this.complete = true;
      this.naturalWidth = 1200;
      this.naturalHeight = 400;
      this.srcWrites = 0;
      this.style = new Proxy({}, { set: (target, key, value) => {
        metrics.styleWrites++;
        styleKeys.push(key);
        target[key] = value;
        return true;
      } });
      this.classList = { add() {}, remove() {}, toggle() {} };
      if (tag === 'img' && asyncDecode) this.decode = () => new Promise((resolve, reject) => decodes.push({ resolve, reject }));
    }
    get clientWidth() { metrics.layoutReads++; return viewport.width + (this.className.endsWith('stage') ? 20 : 0); }
    get clientHeight() { metrics.layoutReads++; return viewport.height + (this.className.endsWith('stage') ? 20 : 0); }
    set scrollLeft(value) { metrics.scrollWrites++; this._scrollLeft = value; }
    set scrollTop(value) { metrics.scrollWrites++; this._scrollTop = value; }
    getBoundingClientRect() {
      metrics.layoutReads++;
      if (this.className.endsWith('canvas')) return { left: 10, top: 10, width: viewport.width, height: viewport.height };
      const ratio = Math.min(1, viewport.width / this.naturalWidth, viewport.height / this.naturalHeight);
      return { left: 10, top: 10, width: this.naturalWidth * ratio, height: this.naturalHeight * ratio };
    }
    set src(value) { this._src = value; this.srcWrites++; }
    get src() { return this._src || ''; }
    appendChild(child) { this.children.push(child); return child; }
    setAttribute(key, value) { this[key] = value; }
    addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
    setPointerCapture(id) { this.pointerCapture = id; }
    hasPointerCapture(id) { return this.pointerCapture === id; }
    releasePointerCapture() { this.pointerCapture = null; }
    emit(name, event = {}) { (this.listeners[name] || []).forEach(callback => callback(event)); }
    showModal() { this.open = true; }
    close() { this.open = false; this.emit('close'); }
  }
  const window = {
    addEventListener() {},
    requestAnimationFrame(callback) { metrics.frameRequests++; frames.set(++frameId, callback); return frameId; },
    cancelAnimationFrame(id) { frames.delete(id); },
    setTimeout(callback) { timers.set(++timerId, callback); return timerId; },
    clearTimeout(id) { timers.delete(id); },
    getComputedStyle() { metrics.layoutReads++; return { paddingLeft: '10px', paddingRight: '10px', paddingTop: '10px', paddingBottom: '10px' }; },
    ResizeObserver: class {
      constructor(callback) { resizeCallbacks.push(callback); }
      observe() {}
    },
  };
  const context = vm.createContext({ window, document: { body: new Element('body'), createElement: tag => new Element(tag) } });
  const start = text.indexOf('var durableAttachmentPreviewDialog = null;');
  const end = text.indexOf("if (typeof document !== 'undefined'", start);
  assert.ok(start >= 0 && end > start);
  vm.runInContext(text.slice(start, end), context);
  const thumbnail = { src: 'blob:preview', alt: '图片' };
  context.openChatImagePreview(thumbnail);
  const dialog = context.durableAttachmentPreviewDialog;
  const flush = () => {
    const callbacks = Array.from(frames.values());
    frames.clear();
    callbacks.forEach(callback => callback());
  };
  const clearMetrics = () => {
    Object.keys(metrics).forEach(key => { metrics[key] = 0; });
    styleKeys.length = 0;
  };
  const settle = () => {
    const callbacks = Array.from(timers.values());
    timers.clear();
    callbacks.forEach(callback => callback());
    flush();
  };
  const wheel = (deltaY, deltaMode = 0, position = {}) => {
    let prevented = false;
    dialog._previewStage.emit('wheel', { deltaY, deltaMode, ...position, preventDefault() { prevented = true; } });
    return prevented;
  };
  return { context, dialog, thumbnail, viewport, decodes, resizeCallbacks, frames, timers, styleKeys, metrics, flush, settle, clearMetrics, wheel };
}

function burst(text) {
  const app = harness(text);
  app.flush();
  app.clearMetrics();
  for (let i = 0; i < 1000; i++) app.wheel(-1);
  const pendingFrames = app.frames.size;
  app.flush();
  return { ...app.metrics, pendingFrames };
}

async function main() {
  const app = harness();
  app.flush();
  assert.equal(app.dialog._previewImage.style.visibility, '');
  const fittedWidth = app.dialog._previewImage.style.width;
  const fittedHeight = app.dialog._previewImage.style.height;
  app.clearMetrics();
  for (let i = 0; i < 1000; i++) assert.ok(app.wheel(-1));
  assert.equal(app.frames.size, 1, 'a wheel burst must queue only one render');
  assert.equal(app.metrics.styleWrites, 0, 'wheel handlers must not mutate layout or style');
  assert.equal(app.metrics.layoutReads, 0, 'wheel handlers must not read layout');
  app.flush();
  assert.deepEqual(app.metrics, { layoutReads: 0, styleWrites: 2, frameRequests: 1, scrollWrites: 0 });
  assert.equal(app.dialog._previewImage.style.width, fittedWidth);
  assert.equal(app.dialog._previewImage.style.height, fittedHeight);
  assert.match(app.dialog._previewImage.style.transform, /^translate3d\(.+\) scale\(/);
  assert.equal(app.timers.size, 1, 'a wheel burst needs only one final detail refresh');
  assert.ok(Math.abs(app.dialog._previewScale - Math.exp(1.6)) < 1e-10, 'coalescing must preserve the accumulated zoom');
  app.settle();
  assert.equal(app.dialog._previewZoomLabel.textContent, '413%');
  assert.ok(Math.abs(parseFloat(app.dialog._previewImage.style.width) - 1000 * Math.exp(1.6)) < 1e-7);
  assert.equal(app.dialog._previewImage.style.transform, 'none');
  assert.equal(app.dialog._previewImage.style.willChange, '', 'the final image must not keep a stale compositor raster');
  app.clearMetrics();
  for (let frame = 0; frame < 10; frame++) {
    app.wheel(1);
    app.flush();
  }
  assert.equal(app.metrics.layoutReads, 0);
  assert.ok(app.styleKeys.every(key => key === 'transform' || key === 'willChange'), 'continuous input must not resize or reposition layout');
  assert.equal(app.timers.size, 1);

  app.wheel(-100000);
  app.flush();
  assert.equal(app.dialog._previewScale, 8);
  app.wheel(100000);
  app.flush();
  assert.equal(app.dialog._previewScale, 0.2);
  app.context.resetDurableAttachmentPreviewZoom(app.dialog);
  app.flush();
  app.wheel(-1, 1);
  app.flush();
  assert.ok(Math.abs(app.dialog._previewScale - Math.exp(16 * 0.0016)) < 1e-10);

  const scale = app.dialog._previewScale;
  app.viewport.width = 600;
  app.viewport.height = 400;
  app.resizeCallbacks[0]();
  app.flush();
  assert.equal(parseFloat(app.dialog._previewImage.style.width), 600 * scale);
  assert.equal(app.dialog._previewScale, scale, 'resizing must preserve the chosen zoom');
  app.wheel(-20);
  app.flush();
  assert.equal(app.timers.size, 1);
  app.wheel(-20);
  assert.equal(app.frames.size, 1);
  app.dialog.close();
  assert.equal(app.frames.size, 0, 'closing must cancel queued work');
  assert.equal(app.timers.size, 0, 'closing must cancel delayed detail work');
  app.context.openChatImagePreview(app.thumbnail);
  app.flush();
  assert.equal(app.dialog._previewScale, 1);
  assert.equal(app.dialog._previewImage.srcWrites, 1, 'reopening the same image must reuse its source');

  app.dialog._previewImage.naturalWidth = 12000;
  app.dialog._previewImage.naturalHeight = 4000;
  app.context.resetDurableAttachmentPreviewZoom(app.dialog);
  app.flush();
  app.dialog._previewControls[2].emit('click');
  app.flush();
  assert.equal(app.dialog._previewImage.style.width, '12000px', '100% must reach the original even when it needs more than 8x the fitted size');
  assert.equal(app.dialog._previewZoomLabel.textContent, '100%');
  app.dialog._previewControls[3].emit('click');
  app.flush();
  app.wheel(-800, 0, { clientX: 460, clientY: 210 });
  app.flush();
  const anchoredX = app.dialog._previewOffsetX;
  assert.ok(anchoredX < 0, 'zooming on the right side keeps that detail under the pointer');
  app.dialog._previewStage.emit('pointerdown', { button: 0, pointerId: 1, clientX: 460, clientY: 210, preventDefault() {} });
  app.dialog._previewStage.emit('pointermove', { pointerId: 1, clientX: 510, clientY: 210 });
  app.flush();
  assert.equal(app.dialog._previewOffsetX, anchoredX + 50);
  app.dialog._previewStage.emit('pointermove', { pointerId: 1, clientX: 50000, clientY: 50000 });
  app.flush();
  assert.ok(app.dialog._previewOffsetX <= (app.dialog._previewFitSize.width * app.dialog._previewScale - app.viewport.width) / 2);
  app.dialog._previewStage.emit('pointercancel');
  assert.equal(app.dialog._previewDrag, null);
  assert.equal(app.dialog._previewStage.pointerCapture, null);
  app.dialog._previewControls[3].emit('click');
  app.flush();
  assert.equal(app.dialog._previewOffsetX, 0);
  assert.equal(app.dialog._previewOffsetY, 0);

  app.context.openChatImagePreview({ src: 'blob:original', currentSrc: 'blob:thumbnail', alt: 'original' });
  app.flush();
  assert.equal(app.dialog._previewImage.src, 'blob:original');

  const loading = harness(source, true);
  assert.equal(loading.dialog._previewImage.style.visibility, 'hidden');
  assert.equal(loading.frames.size, 0, 'wait for decode before fitting a large image');
  loading.dialog.close();
  loading.clearMetrics();
  loading.decodes[0].resolve();
  await Promise.resolve();
  assert.equal(loading.frames.size, 0, 'a stale decode must not reopen or render the viewer');
  assert.equal(loading.metrics.styleWrites, 0);
  loading.context.openChatImagePreview(loading.thumbnail);
  loading.decodes[1].resolve();
  await Promise.resolve();
  loading.flush();
  assert.equal(loading.dialog._previewImage.style.visibility, '');
  loading.context.resetDurableAttachmentPreviewZoom(loading.dialog);
  loading.decodes[2].reject(new Error('decode unavailable'));
  await Promise.resolve();
  loading.flush();
  assert.equal(loading.dialog._previewImage.style.visibility, '', 'decoded-image fallback must remain usable');

  console.log('image preview runtime checks passed');
  console.log(JSON.stringify({ wheelEvents: 1000, after: burst(source) }));
  const baseline = process.argv[2];
  if (baseline) console.log(JSON.stringify({ before: burst(fs.readFileSync(baseline, 'utf8')) }));
}

main().catch(error => { console.error(error); process.exitCode = 1; });
