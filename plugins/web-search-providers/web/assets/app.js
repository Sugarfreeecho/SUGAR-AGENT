'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const root = document.documentElement;
  const embedded = root.dataset.embedded === 'true';
  const t = (zh, en) => root.lang === 'en' ? en : zh;

  const PROVIDERS = {
    duckduckgo: {
      hint: [
        '默认选项，无需 API Key。依赖 ddgs 包，结果来自 DuckDuckGo。',
        'Default and keyless. Requires the ddgs package; results come from DuckDuckGo.'
      ]
    },
    tavily: {
      key: 'TAVILY_API_KEY',
      hint: [
        '面向 AI 应用的搜索 API，返回摘要与来源。需要 Tavily API Key。',
        'AI-oriented search API with snippets and sources. Requires a Tavily API key.'
      ]
    },
    brave: {
      key: 'BRAVE_API_KEY',
      hint: [
        'Brave Search API，免费额度有限。需要 Brave Search API Key。',
        'Brave Search API with a limited free tier. Requires a Brave Search API key.'
      ]
    },
    searxng: {
      url: true,
      hint: [
        '自建或公共 SearXNG 实例。需要可公网访问的地址，并开启 JSON 输出。',
        'A self-hosted or public SearXNG instance. Use a public URL with JSON output enabled.'
      ]
    },
    jina: {
      key: 'JINA_API_KEY',
      hint: [
        'Jina Reader 搜索接口，返回网页摘要。需要 Jina API Key。',
        'Jina Reader search endpoint with page summaries. Requires a Jina API key.'
      ]
    }
  };
  const KEY_LABELS = {
    TAVILY_API_KEY: ['Tavily API Key', 'Tavily API Key'],
    BRAVE_API_KEY: ['Brave Search API Key', 'Brave Search API Key'],
    JINA_API_KEY: ['Jina API Key', 'Jina API Key']
  };

  let snapshot = null;
  let saved = {provider: 'duckduckgo', max_results: 20};
  let selected = 'duckduckgo';
  let busy = '';
  let credentialFor = '';
  let testResult = null;
  let loadError = '';
  let disposed = false;

  function post(type, data = {}) {
    if (embedded && window.parent !== window) window.parent.postMessage({type, ...data}, location.origin);
  }
  function notice(text, kind = '') {
    const element = $('message');
    element.textContent = text;
    element.dataset.kind = kind;
    element.hidden = !text;
  }
  async function api(path, body) {
    const response = await fetch('/api/web-search-providers/' + path, {
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? {} : {'Content-Type': 'application/json'},
      ...(body === undefined ? {} : {body: JSON.stringify(body)}),
      cache: 'no-store', credentials: 'same-origin'
    });
    let data;
    try { data = await response.json(); }
    catch (_error) { throw new Error(t('服务响应无效，请刷新后重试。', 'Invalid server response. Refresh and retry.')); }
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(t('插件接口尚未加载，请重启 SugarAgent 或重新启用插件。',
          'The plugin API is not loaded yet. Restart SugarAgent or re-enable the plugin.'));
      }
      const detail = data.detail || data.error || data;
      throw new Error(typeof detail === 'string' ? detail : detail.message || t('请求失败', 'Request failed'));
    }
    return data;
  }
  function currentMax() {
    const raw = $('max-results').value.trim();
    return raw ? Number(raw) : NaN;
  }
  function settingsDirty() {
    return selected !== saved.provider || currentMax() !== saved.max_results;
  }
  function credentialDirty() {
    const info = PROVIDERS[selected] || {};
    if (info.key) return $('credential-value').value.trim().length > 0;
    if (info.url) return $('searxng-url').value.trim() !== ((snapshot && snapshot.searxng_base_url) || '');
    return false;
  }
  function credentialConfigured() {
    const info = PROVIDERS[selected] || {};
    if (info.key) return !!(snapshot && snapshot.keys && snapshot.keys[info.key] && snapshot.keys[info.key].configured);
    if (info.url) return !!(snapshot && snapshot.searxng_base_url);
    return true;
  }
  function readyReason() {
    if (!snapshot || selected !== snapshot.provider || snapshot.ready) return '';
    const info = PROVIDERS[selected] || {};
    if (selected === 'duckduckgo') return t('未安装 ddgs，DuckDuckGo 搜索不可用。', 'ddgs is not installed, so DuckDuckGo search is unavailable.');
    if (selected === 'searxng') return t('尚未填写 SearXNG 实例地址。', 'No SearXNG instance URL is configured.');
    if (info.key) {
      const label = (KEY_LABELS[info.key] || [info.key])[0].replace(' API Key', '');
      return t('尚未配置 ' + label + ' API Key。', 'Configure a ' + label + ' API key.');
    }
    return snapshot.ready_reason || '';
  }
  function renderStatus() {
    const chip = $('status-chip');
    if (!snapshot) {
      chip.dataset.kind = loadError ? 'error' : 'idle';
      chip.textContent = loadError ? t('读取失败', 'Load failed') : t('读取中', 'Loading');
      return;
    }
    if (settingsDirty()) {
      chip.dataset.kind = 'warning';
      chip.textContent = t('设置未保存', 'Unsaved changes');
    } else if (snapshot.ready) {
      chip.dataset.kind = 'ok';
      chip.textContent = t('已就绪', 'Ready');
    } else {
      chip.dataset.kind = 'warning';
      chip.textContent = t('需要配置', 'Needs setup');
    }
    const reason = readyReason();
    const element = $('status-reason');
    element.textContent = reason;
    element.hidden = !reason;
  }
  function renderProviderHint() {
    const info = PROVIDERS[selected];
    if (!info) return;
    $('provider-hint').textContent = t(info.hint[0], info.hint[1]);
  }
  function renderCredential() {
    const info = PROVIDERS[selected] || {};
    const kind = info.key || (info.url ? 'searxng' : 'duckduckgo');
    if (credentialFor !== kind) {
      credentialFor = kind;
      $('credential-value').value = '';
    }
    $('credential-none').hidden = kind !== 'duckduckgo';
    $('credential-key').hidden = !info.key;
    $('credential-searxng').hidden = !info.url;
    const chip = $('credential-chip');
    if (kind === 'duckduckgo') {
      chip.dataset.kind = 'ok';
      chip.textContent = t('无需凭据', 'No key needed');
      $('credential-none').textContent = t(
        'DuckDuckGo 无需 API Key，保存搜索引擎设置后即可使用。',
        'DuckDuckGo needs no API key. Save the engine setting to use it.');
      return;
    }
    if (info.key) {
      const row = snapshot && snapshot.keys ? snapshot.keys[info.key] : null;
      const label = KEY_LABELS[info.key] || [info.key, info.key];
      const configured = !!(row && row.configured);
      $('credential-label').textContent = t(label[0], label[1]);
      $('credential-value').placeholder = configured
        ? t('已保存；输入新密钥可替换', 'Saved; enter a new key to replace')
        : t('粘贴 API Key', 'Paste the API key');
      chip.dataset.kind = configured ? 'ok' : 'warning';
      chip.textContent = configured ? t('已配置 ', 'Configured ') + row.hint : t('未配置', 'Not configured');
      $('credential-hint').textContent = configured
        ? t('当前密钥：' + row.hint + '。留空不会改动已保存的密钥。',
            'Current key: ' + row.hint + '. Leaving the field empty keeps it.')
        : t('密钥只保存在本机 .env，不会发送到其他位置。',
            'The key is stored only in the local .env file.');
      $('remove-credential').hidden = !configured;
      return;
    }
    const configured = !!(snapshot && snapshot.searxng_base_url);
    chip.dataset.kind = configured ? 'ok' : 'warning';
    chip.textContent = configured ? t('已配置', 'Configured') : t('未配置', 'Not configured');
    $('remove-searxng').hidden = !configured;
  }
  function renderCredentialSummary() {
    const parts = Object.keys(KEY_LABELS).map(name => {
      const row = snapshot && snapshot.keys ? snapshot.keys[name] : null;
      const label = KEY_LABELS[name][0].replace(' API Key', '');
      return label + (row && row.configured ? ' ✓ ' + row.hint : ' —');
    });
    $('credential-summary').textContent = t('凭据状态：', 'Credentials: ') + parts.join(' · ');
  }
  function renderTest() {
    if (!testResult) {
      $('test-status').hidden = true;
      $('test-output').hidden = true;
      return;
    }
    $('test-status').hidden = false;
    $('test-status').dataset.kind = testResult.ok ? 'success' : 'error';
    $('test-status').textContent = (testResult.ok ? t('测试成功', 'Test passed') : t('测试失败', 'Test failed')) +
      ' · ' + testResult.latency_ms + ' ms';
    $('test-output').textContent = testResult.text || '';
    $('test-output').hidden = !testResult.text;
  }
  function updateButtons() {
    const ready = !!snapshot;
    const dirty = settingsDirty();
    const credDirty = credentialDirty();
    $('save-settings').disabled = !!busy || !ready || !dirty;
    $('reset-settings').disabled = !!busy;
    $('save-credential').disabled = !!busy || !ready || !$('credential-value').value.trim();
    $('remove-credential').disabled = !!busy || !ready || !credentialConfigured();
    $('save-searxng').disabled = !!busy || !ready || !$('searxng-url').value.trim();
    $('remove-searxng').disabled = !!busy || !ready || !credentialConfigured();
    $('run-test').disabled = !!busy || !ready || dirty || credDirty;
    $('run-test').textContent = busy === 'test' ? t('测试中…', 'Testing…') : t('开始测试', 'Test');
    $('save-settings').textContent = busy === 'settings' ? t('保存中…', 'Saving…') : t('保存设置', 'Save settings');
    $('save-credential').textContent = busy === 'credential' ? t('保存中…', 'Saving…') : t('保存密钥', 'Save key');
    $('save-searxng').textContent = busy === 'searxng' ? t('保存中…', 'Saving…') : t('保存地址', 'Save address');
    const testChip = $('test-chip');
    if (dirty || credDirty) {
      testChip.dataset.kind = 'warning';
      testChip.textContent = t('请先保存更改', 'Save changes first');
    } else {
      testChip.dataset.kind = 'idle';
      testChip.textContent = t('使用已保存设置', 'Uses saved settings');
    }
  }
  function renderAll() {
    renderProviderHint();
    renderCredential();
    renderCredentialSummary();
    renderStatus();
    updateButtons();
  }
  function applySnapshot(data, resetForm = true) {
    snapshot = data;
    loadError = '';
    saved = {provider: data.provider, max_results: data.max_results};
    if (resetForm) {
      selected = data.provider;
      $('provider').value = data.provider;
      $('max-results').value = String(data.max_results);
      $('searxng-url').value = data.searxng_base_url || '';
      credentialFor = '';
    } else {
      selected = $('provider').value;
    }
    $('max-results').max = String(data.max_results_limit || 100);
    $('config-file-hint').textContent = data.config_file ? t('配置文件：', 'Config file: ') + data.config_file : '';
    renderAll();
  }
  async function action(kind, fn) {
    if (busy) return;
    busy = kind;
    updateButtons();
    try { await fn(); }
    catch (error) { notice(error.message, 'error'); }
    finally {
      busy = '';
      updateButtons();
      renderStatus();
    }
  }
  async function load() {
    try {
      const data = await api('status');
      if (disposed) return;
      applySnapshot(data, true);
    } catch (error) {
      if (disposed) return;
      loadError = error.message;
      notice(error.message, 'error');
      const chip = $('status-chip');
      chip.dataset.kind = 'error';
      chip.textContent = t('读取失败', 'Load failed');
    }
  }

  function applyLanguage() {
    document.querySelectorAll('[data-en]').forEach(element => {
      if (element.dataset.zh === undefined) element.dataset.zh = element.textContent;
      element.textContent = t(element.dataset.zh, element.dataset.en);
    });
    document.querySelectorAll('[data-en-placeholder]').forEach(element => {
      if (element.dataset.zhPlaceholder === undefined) element.dataset.zhPlaceholder = element.placeholder;
      element.placeholder = t(element.dataset.zhPlaceholder, element.dataset.enPlaceholder);
    });
    renderAll();
    renderTest();
  }

  $('provider').addEventListener('change', () => {
    selected = $('provider').value;
    if (!PROVIDERS[selected]) selected = 'duckduckgo';
    testResult = null;
    notice('');
    renderTest();
    renderAll();
  });
  $('max-results').addEventListener('input', () => { notice(''); updateButtons(); renderStatus(); });
  $('credential-value').addEventListener('input', () => { notice(''); updateButtons(); });
  $('searxng-url').addEventListener('input', () => { notice(''); updateButtons(); });
  $('save-settings').addEventListener('click', () => action('settings', async () => {
    const max = currentMax();
    const limit = snapshot && snapshot.max_results_limit ? snapshot.max_results_limit : 100;
    if (!Number.isInteger(max)) throw new Error(t('结果上限必须是整数。', 'Results must be a whole number.'));
    if (max < 1 || max > limit) throw new Error(t('结果上限需在 1–' + limit + ' 之间。', 'Results must be between 1 and ' + limit + '.'));
    const data = await api('settings', {provider: selected, max_results: max});
    applySnapshot(data, true);
    notice(t('设置已保存并立即生效。', 'Settings saved and applied.'), 'success');
  }));
  $('reset-settings').addEventListener('click', () => {
    $('provider').value = 'duckduckgo';
    selected = 'duckduckgo';
    $('max-results').value = '20';
    testResult = null;
    renderTest();
    renderAll();
    notice(t('已填入默认值，点击“保存设置”后生效。', 'Defaults filled in; choose Save settings to apply.'), '');
  });
  $('save-credential').addEventListener('click', () => action('credential', async () => {
    const info = PROVIDERS[selected];
    if (!info || !info.key) return;
    const value = $('credential-value').value.trim();
    if (!value) throw new Error(t('请输入 API Key。', 'Enter an API key.'));
    const data = await api('credentials', {name: info.key, value});
    $('credential-value').value = '';
    applySnapshot(data, false);
    notice(t('密钥已保存并立即生效。', 'Key saved and applied.'), 'success');
  }));
  $('remove-credential').addEventListener('click', () => {
    const info = PROVIDERS[selected];
    if (!info || !info.key) return;
    if (!confirm(t('移除已保存的 API Key？', 'Remove the saved API key?'))) return;
    void action('credential', async () => {
      const data = await api('credentials', {name: info.key, remove: true});
      $('credential-value').value = '';
      applySnapshot(data, false);
      notice(t('密钥已移除。', 'Key removed.'), 'success');
    });
  });
  $('save-searxng').addEventListener('click', () => action('searxng', async () => {
    const value = $('searxng-url').value.trim();
    if (!value) throw new Error(t('请填写 SearXNG 实例地址。', 'Enter the SearXNG instance URL.'));
    const data = await api('searxng', {base_url: value});
    applySnapshot(data, false);
    $('searxng-url').value = data.searxng_base_url || '';
    notice(t('实例地址已保存。', 'Instance URL saved.'), 'success');
  }));
  $('remove-searxng').addEventListener('click', () => {
    if (!confirm(t('移除已保存的 SearXNG 实例地址？', 'Remove the saved SearXNG instance URL?'))) return;
    void action('searxng', async () => {
      const data = await api('searxng', {remove: true});
      applySnapshot(data, false);
      $('searxng-url').value = '';
      notice(t('实例地址已移除。', 'Instance URL removed.'), 'success');
    });
  });
  $('refresh').addEventListener('click', () => {
    if (settingsDirty() && !confirm(t('刷新会丢弃未保存的更改，继续？', 'Refresh will discard unsaved changes. Continue?'))) return;
    void action('refresh', async () => {
      const data = await api('status');
      applySnapshot(data, true);
      notice(t('状态已刷新。', 'Status refreshed.'), 'success');
    });
  });
  $('run-test').addEventListener('click', async () => {
    if (busy) return;
    const query = $('test-query').value.trim();
    if (!query) { notice(t('请输入测试搜索词。', 'Enter a query to test.'), 'error'); return; }
    busy = 'test';
    testResult = null;
    updateButtons();
    $('test-status').hidden = false;
    $('test-status').dataset.kind = '';
    $('test-status').textContent = t('正在测试…', 'Testing…');
    $('test-output').hidden = true;
    try {
      const result = await api('test', {query});
      testResult = result;
      renderTest();
      notice(result.ok ? t('测试成功。', 'Test passed.') : t('测试失败，请查看下方输出。', 'Test failed; see the output below.'),
        result.ok ? 'success' : 'error');
    } catch (error) {
      testResult = {ok: false, latency_ms: 0, text: error.message};
      renderTest();
      notice(error.message, 'error');
    } finally {
      busy = '';
      updateButtons();
    }
  });
  $('test-query').addEventListener('keydown', event => {
    if (event.key === 'Enter') { event.preventDefault(); $('run-test').click(); }
  });

  window.addEventListener('message', event => {
    if (!embedded || event.origin !== location.origin || event.source !== window.parent ||
      event.data?.type !== 'myagent:plugin-settings-context') return;
    const data = event.data;
    if (['theme-dark', 'theme-purple', 'theme-light'].includes(data.theme)) {
      root.classList.remove('theme-dark', 'theme-purple', 'theme-light');
      root.classList.add(data.theme);
    }
    root.lang = data.lang === 'en' ? 'en' : 'zh-CN';
    if (Number.isFinite(data.fontPx)) {
      const px = Math.max(12, Math.min(20, data.fontPx));
      root.style.setProperty('--st-fs', Math.max(11, px - 2) + 'px');
      root.style.setProperty('--st-fs-lg', px + 'px');
      root.style.setProperty('--st-fs-sm', Math.max(10, px - 3) + 'px');
      root.style.setProperty('--st-fs-xs', Math.max(9, px - 4) + 'px');
    }
    applyLanguage();
  });

  let lastHeight = 0;
  new ResizeObserver(() => {
    const height = Math.ceil(document.querySelector('main').getBoundingClientRect().height);
    if (height !== lastHeight) { lastHeight = height; post('myagent:plugin-settings-resize', {height}); }
  }).observe(document.querySelector('main'));
  window.addEventListener('pagehide', () => { disposed = true; });

  applyLanguage();
  post('myagent:plugin-settings-ready');
  load();
})();
