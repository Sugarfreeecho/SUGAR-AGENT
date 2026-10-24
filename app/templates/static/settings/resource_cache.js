/* Shared, memory-only catalog cache for chat and same-origin settings frames. */
(function (root) {
  'use strict';
  if (root.MyAgentResourceCache) return;
  try {
    if (root.parent !== root && root.parent.location.origin === root.location.origin
        && root.parent.MyAgentResourceCache?.supports('/api/plugins/catalog')) {
      root.MyAgentResourceCache = root.parent.MyAgentResourceCache;
      return;
    }
  } catch (_error) { /* A standalone settings window owns its cache. */ }

  const paths = new Set(['/api/model_profiles', '/api/skills', '/api/extensions', '/api/plugins/catalog', '/api/mcp/tools', '/api/tool_search/config']);
  const entries = new Map();
  const clone = value => JSON.parse(JSON.stringify(value));
  function invalidate(path, broadcast) {
    if (path) entries.delete(path);
    else entries.clear();
    root.dispatchEvent(new CustomEvent('myagent:catalog-invalidated', { detail: { path: path || '' } }));
    if (broadcast !== false) {
      try { root.localStorage.setItem('myagent-catalog-revision', Date.now() + ':' + Math.random()); } catch (_error) {}
    }
  }
  async function get(path, options) {
    options = options || {};
    if (!paths.has(path)) throw new Error('Unsupported catalog: ' + path);
    if (options.force) invalidate(path, false);
    let entry = entries.get(path);
    if (entry && entry.value && Date.now() < entry.expires) return clone(entry.value);
    if (!entry || !entry.promise) {
      entry = { promise: null, value: null, expires: 0 };
      entries.set(path, entry);
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 30000);
      entry.promise = (async () => {
        try {
          const response = await root.fetch(path, { credentials: 'same-origin', signal: controller.signal });
          const data = await response.json();
          if (!response.ok || !data || data.ok === false) throw new Error((data && (data.error || data.detail)) || 'HTTP ' + response.status);
          entry.value = data;
          // MCP discovery continues independently; poll only while it is warming.
          entry.expires = Date.now() + (data.initializing ? 1000 : 30000);
          return data;
        } finally {
          clearTimeout(timer);
          entry.promise = null;
          if (!entry.value && entries.get(path) === entry) entries.delete(path);
        }
      })();
    }
    const value = await entry.promise;
    // A save may have invalidated this request while its response was in flight.
    if (entries.get(path) !== entry) return get(path);
    return clone(value);
  }
  root.addEventListener('storage', event => {
    if (event.key === 'myagent-catalog-revision') invalidate(null, false);
  });
  root.MyAgentResourceCache = {
    get, invalidate, supports: path => paths.has(path),
    // Display metadata only: writes and cross-window changes discard it.
    peek: path => { const entry = entries.get(path); return entry?.value ? clone(entry.value) : null; },
  };
})(window);

/* Keep interaction feedback ahead of optional loading and rendering work. */
(function (root) {
  'use strict';
  if (root.MyAgentUiTasks) return;
  const pending = new Map();
  let warming = false;
  let yieldChannel = null;
  const yieldQueue = [];
  function yieldToMain() {
    if (typeof root.scheduler?.yield === 'function') return root.scheduler.yield();
    if (root.MessageChannel) {
      if (!yieldChannel) {
        yieldChannel = new root.MessageChannel();
        yieldChannel.port1.onmessage = () => { const resolve = yieldQueue.shift(); if (resolve) resolve(); };
      }
      return new Promise(resolve => { yieldQueue.push(resolve); yieldChannel.port2.postMessage(null); });
    }
    return new Promise(resolve => root.setTimeout(resolve, 0));
  }
  function afterPaint(work) {
    return new Promise((resolve, reject) => {
      const run = () => { try { resolve(work()); } catch (error) { reject(error); } };
      if (root.document.hidden || !root.requestAnimationFrame) root.setTimeout(run, 0);
      else root.requestAnimationFrame(() => root.setTimeout(run, 0));
    });
  }
  function cancel(key) {
    const job = pending.get(key);
    if (!job || job.running) return;
    root.clearTimeout(job.timer);
    if (job.idle && root.cancelIdleCallback) root.cancelIdleCallback(job.idle);
    pending.delete(key);
  }
  function warm(key, work) {
    if (root.document.hidden || pending.has(key)) return;
    const job = { timer: 0, idle: 0, running: false };
    pending.set(key, job);
    const run = deadline => {
      if (pending.get(key) !== job) return;
      if (root.document.hidden) { cancel(key); return; }
      if (warming || root.navigator?.scheduling?.isInputPending?.()
          || (deadline && deadline.timeRemaining() < 8)) {
        job.timer = root.setTimeout(schedule, 100);
        return;
      }
      warming = job.running = true;
      Promise.resolve().then(work).catch(() => {}).finally(() => {
        warming = false;
        if (pending.get(key) === job) pending.delete(key);
      });
    };
    const schedule = () => {
      if (root.requestIdleCallback) job.idle = root.requestIdleCallback(run);
      else job.timer = root.setTimeout(run, 100);
    };
    job.timer = root.setTimeout(schedule, 140);
  }
  function bindIntent(element, key, work) {
    if (!element) return;
    let activeKey = '';
    const enter = () => {
      activeKey = typeof key === 'function' ? key() : key;
      const captured = activeKey;
      warm(captured, () => work(captured));
    };
    const leave = () => {
      if (root.document.activeElement !== element) cancel(activeKey);
    };
    element.addEventListener('pointerenter', enter);
    element.addEventListener('focus', enter);
    element.addEventListener('pointerleave', leave);
    element.addEventListener('blur', leave);
  }
  root.MyAgentUiTasks = { afterPaint, yieldToMain, warm, cancel, bindIntent };
})(window);
