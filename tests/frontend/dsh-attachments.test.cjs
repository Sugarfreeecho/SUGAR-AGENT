const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'frontend/src/app/modules/workspace-media.js'), 'utf8');
const styles = fs.readFileSync(path.join(root, 'frontend/src/styles/app.css'), 'utf8');
const queueSource = fs.readFileSync(path.join(root, 'frontend/src/app/modules/sse-handling.js'), 'utf8');
const queueFunction = queueSource.slice(queueSource.indexOf('function normalizeStoredFollowupItem('), queueSource.indexOf('function readStoredFollowupQueue('));
const ref = { attachmentId: 'sha256:' + 'a'.repeat(64), width: 80, height: 60, mediaType: 'image/jpeg', bytes: 700 };

function fixture() {
  const observers = [], revoked = [], requests = [];
  function element(tagName) {
    const node = {
      tagName: String(tagName || '').toUpperCase(),
      children: [],
      dataset: {},
      style: {},
      className: '',
      classList: {
        add(name) {
          const names = new Set(String(node.className || '').split(/\s+/).filter(Boolean));
          names.add(name);
          node.className = Array.from(names).join(' ');
        },
        contains(name) { return String(node.className || '').split(/\s+/).includes(name); },
      },
      setAttribute(name, value) { this[name] = String(value); },
      appendChild(child) { child.isConnected = true; this.children.push(child); },
      insertBefore(child, before) {
        child.isConnected = true;
        const index = before ? this.children.indexOf(before) : -1;
        if (index < 0) this.children.push(child);
        else this.children.splice(index, 0, child);
      },
      querySelector(selector) {
        const all = [];
        const visit = current => {
          (current.children || []).forEach(child => { all.push(child); visit(child); });
        };
        visit(this);
        if (selector.includes('.msg-user-attachment-strip')) {
          return all.find(child => child.classList && child.classList.contains('msg-user-attachment-strip'));
        }
        if (selector.includes('.msg-toolbar')) {
          return all.find(child => child.classList && child.classList.contains('msg-toolbar'));
        }
        const attachment = selector.match(/data-attachment-id="([^"]+)"/);
        if (attachment) return all.find(child => child.dataset && child.dataset.attachmentId === attachment[1]);
        return null;
      },
    };
    return node;
  }
  const container = {
    children: [],
    querySelector(selector) { return this.children.find(child => selector.includes(child.dataset.attachmentId)); },
    appendChild(child) { child.isConnected = true; this.children.push(child); },
  };
  const context = vm.createContext({
    AbortController,
    document: { body: {}, createElement: element },
    fetch: async url => { requests.push(url); return { ok: true, blob: async () => ({}) }; },
    URL: { createObjectURL: () => 'blob:test-image', revokeObjectURL: url => revoked.push(url) },
    MutationObserver: class { constructor(callback) { this.callback = callback; observers.push(this); } observe() {} disconnect() { this.disconnected = true; } },
    defaultSteerMode: () => 'append',
  });
  vm.runInContext(source + '\n' + queueFunction, context);
  return { context, container, element, observers, revoked, requests };
}

test('user message attachments render as an equal-height horizontal thumbnail strip', async () => {
  const f = fixture();
  const userMessage = f.element('div');
  userMessage.classList.add('msg-wrap--user');
  const secondRef = { ...ref, attachmentId: 'sha256:' + 'b'.repeat(64), width: 160, height: 90 };
  f.context.renderDurableAttachmentImages(userMessage, [ref, secondRef]);
  await new Promise(resolve => setImmediate(resolve));

  assert.equal(userMessage.children.length, 1);
  const strip = userMessage.children[0];
  assert.equal(strip.classList.contains('msg-user-attachment-strip'), true);
  assert.equal(strip.children.length, 2);
  assert.equal(strip.children.every(image => image.classList.contains('msg-attachment-thumbnail')), true);
  assert.equal(f.requests.length, 2);
  assert.match(styles, /\.msg-user-attachment-strip\s*\{[^}]*display:\s*flex;[^}]*flex-flow:\s*row wrap;/s);
  assert.match(styles, /\.msg-attachment-thumbnail\s*\{[^}]*height:\s*5rem;[^}]*object-fit:\s*contain;/s);
});

test('history and tool previews use a transient blob and release it when removed', async () => {
  const f = fixture();
  f.context.renderDurableAttachmentImages(f.container, [ref, ref]);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(f.requests.length, 1);
  assert.equal(f.container.children[0].src, 'blob:test-image');
  assert.equal(f.container.children[0].dataset.attachmentId, ref.attachmentId);
  f.container.children[0].isConnected = false;
  f.observers[0].callback();
  assert.deepEqual(f.revoked, ['blob:test-image']);
  assert.equal(f.observers[0].disconnected, true);
});

test('queue reload keeps the durable reference and no base64 or blob URL', () => {
  const f = fixture();
  const queued = { id: '1', text: 'inspect', attachments: [{ path: 'C:/workspace/image.jpg', name: 'image.jpg', attachment: ref }] };
  const restored = f.context.normalizeStoredFollowupItem(JSON.parse(JSON.stringify(queued)));
  assert.equal(restored.attachments[0].attachment.attachmentId, ref.attachmentId);
  assert.doesNotMatch(JSON.stringify(restored), /base64|blob:/);
});

test('an image detached during download never allocates a blob URL', async () => {
  const f = fixture();
  let created = 0;
  f.context.URL.createObjectURL = () => { created++; return 'blob:unexpected'; };
  f.context.renderDurableAttachmentImages(f.container, [ref]);
  f.container.children[0].isConnected = false;
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(created, 0);
});

test('two containers share one download and release only after the last user leaves', async () => {
  const f = fixture();
  const second = { ...f.container, children: [] };
  f.context.renderDurableAttachmentImages(f.container, [ref]);
  f.context.renderDurableAttachmentImages(second, [ref]);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(f.requests.length, 1);
  assert.equal(f.observers.length, 1);
  assert.equal(second.children[0].src, f.container.children[0].src);
  f.container.children[0].isConnected = false;
  f.observers[0].callback();
  assert.equal(f.revoked.length, 0);
  second.children[0].isConnected = false;
  f.observers[0].callback();
  assert.equal(f.revoked.length, 1);
});

test('detaching all consumers aborts an unfinished download', () => {
  const f = fixture();
  let signal;
  f.context.fetch = (_, options) => { signal = options.signal; return new Promise(() => {}); };
  f.context.renderDurableAttachmentImages(f.container, [ref]);
  f.container.children[0].isConnected = false;
  f.observers[0].callback();
  assert.equal(signal.aborted, true);
  assert.equal(f.context.durableImagePreviews.size, 0);
});

test('queue pins preserve server update order when an earlier request is delayed', async () => {
  const f = fixture();
  const storage = new Map();
  f.context.localStorage = { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) };
  const requests = [];
  let release;
  f.context.fetch = (_, options) => {
    requests.push(JSON.parse(options.body));
    return requests.length === 1 ? new Promise(resolve => { release = resolve; }) : Promise.resolve({ ok: true });
  };
  f.context.syncFollowupAttachmentPins('session', [{ attachments: [{ attachment: ref }] }]);
  f.context.syncFollowupAttachmentPins('session', []);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requests.length, 1);
  release({ ok: true });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requests.length, 2);
  assert.deepEqual(requests[0].attachmentIds, [ref.attachmentId]);
  assert.deepEqual(requests[1].attachmentIds, []);
  assert.equal(requests[0].scope, requests[1].scope);
});
