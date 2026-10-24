/* Versioned bridge for plugin pages embedded in the details column. */
(function () {
  'use strict';
  if (window.parent === window || new URLSearchParams(location.search).get('surface') !== 'details') return;
  const lifetime = new AbortController();
  const intervals = new Set();
  let boundSession = null;
  const bridge = window.MyAgentPluginPage = {
    visible: false, context: null,
    request(action, data) {
      window.parent.postMessage({ ...data, type: 'myagent:plugin-page-request', version: 1, action }, location.origin);
    },
    close() { bridge.request('close'); },
    openUrl(url) { bridge.request('open-url', { url }); },
  };
  const setIntervalNative = window.setInterval.bind(window);
  const clearIntervalNative = window.clearInterval.bind(window);
  window.setInterval = function (callback, delay, ...args) {
    const id = setIntervalNative(function () {
      if (!bridge.visible || lifetime.signal.aborted) return;
      if (typeof callback === 'function') callback(...args);
    }, delay);
    intervals.add(id); return id;
  };
  window.clearInterval = function (id) { intervals.delete(id); clearIntervalNative(id); };
  const fetchNative = window.fetch.bind(window);
  window.fetch = function (input, options = {}) {
    const signals = [lifetime.signal, options.signal, input instanceof Request ? input.signal : null].filter(Boolean);
    return fetchNative(input, { ...options, signal: AbortSignal.any(signals) });
  };
  const style = document.createElement('link');
  style.rel = 'stylesheet'; style.href = '/static/plugin-page.css'; document.head.appendChild(style);
  document.documentElement.dataset.myagentPage = 'details';
  window.addEventListener('message', event => {
    if (event.origin !== location.origin || event.source !== window.parent || event.data?.version !== 1) return;
    const data = event.data;
    if (data.type === 'myagent:plugin-page-dispose') {
      document.dispatchEvent(new CustomEvent('myagent:plugin-page-dispose'));
      lifetime.abort(); intervals.forEach(clearIntervalNative); intervals.clear(); bridge.visible = false; return;
    }
    if (data.type !== 'myagent:plugin-page-context' || lifetime.signal.aborted) return;
    const previousVisible = bridge.visible;
    bridge.context = data; bridge.visible = data.visible === true;
    const root = document.documentElement;
    root.classList.remove('theme-light', 'theme-dark', 'theme-purple');
    if (['theme-light', 'theme-dark', 'theme-purple'].includes(data.theme)) root.classList.add(data.theme);
    root.lang = data.lang === 'en' ? 'en' : 'zh-CN';
    root.style.fontSize = Math.max(12, Math.min(20, Number(data.fontPx) || 16)) + 'px';
    const input = document.getElementById('session');
    if (input && data.sessionId && boundSession !== data.sessionId) {
      boundSession = data.sessionId; input.value = data.sessionId;
      document.getElementById('select')?.dispatchEvent(new Event('submit', { cancelable: true }));
    }
    document.dispatchEvent(new CustomEvent('myagent:plugin-page-context', { detail: data }));
    if (previousVisible !== bridge.visible) document.dispatchEvent(new CustomEvent('myagent:plugin-page-visibility', { detail: { visible: bridge.visible } }));
  });
  document.addEventListener('click', event => {
    const link = event.target.closest?.('a[href]');
    if (!link) return;
    const url = new URL(link.href, location.href);
    if (url.origin === location.origin && url.pathname === '/' && !url.search && !url.hash) {
      event.preventDefault(); bridge.close();
    } else if (url.origin !== location.origin && /^https?:$/.test(url.protocol)) {
      event.preventDefault(); bridge.openUrl(url.href);
    }
  });
  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('back')?.addEventListener('click', event => {
      event.preventDefault(); event.stopImmediatePropagation(); bridge.close();
    }, true);
    window.parent.postMessage({ type: 'myagent:plugin-page-ready', version: 1 }, location.origin);
  });
})();
