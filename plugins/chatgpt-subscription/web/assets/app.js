'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const root = document.documentElement;
  const embedded = root.dataset.embedded === 'true';
  const t = (zh, en) => root.lang === 'en' ? en : zh;
  let accounts = [], profiles = [], catalog = [], busy = '', loadingModels = false;
  let currentAccount = '', modelAccount = '', initialized = false, waiting = false;
  let polling = null, modelGeneration = 0, statusGeneration = 0, modelAbort, statusAbort, disposed = false;
  let remembered = {};
  try { remembered = JSON.parse(sessionStorage.getItem('chatgpt-subscription:view') || '{}'); } catch (_error) {}
  const selected = () => accounts.find(row => row.id === $('account').value);
  const expired = row => row?.connected && !row.renewable && row.expires_at * 1000 <= Date.now();
  const canUse = () => selected()?.plan_enabled && !expired(selected());
  const savedModel = () => profiles.find(row => row.account_id === currentAccount && row.model === $('model').value);
  const defaultName = () => 'ChatGPT · ' + $('model').value + ' · ' + currentAccount.slice(0, 6);

  function post(type, data = {}) {
    if (embedded && window.parent !== window) window.parent.postMessage({type, ...data}, location.origin);
  }
  function remember() {
    try {
      sessionStorage.setItem('chatgpt-subscription:view', JSON.stringify({
        account: currentAccount, model: $('model').value, name: $('profile-name').value
      }));
    } catch (_error) {}
  }
  function notice(id, text, kind = '') {
    const element = $(id);
    element.textContent = text;
    element.dataset.kind = kind;
    element.hidden = !text;
    if (id === 'model-status') $('model-error-usage').hidden = true;
  }
  async function api(path, body, signal) {
    const response = await fetch('/api/chatgpt-subscription/' + path, {
      method: body === undefined ? 'GET' : 'POST', signal,
      headers: body === undefined ? {} : {'Content-Type': 'application/json'},
      ...(body === undefined ? {} : {body: JSON.stringify(body)}),
      cache: 'no-store', credentials: 'same-origin'
    });
    let data;
    try { data = await response.json(); } catch (_error) { throw new Error(t('服务响应无效，请刷新后重试。', 'Invalid server response. Refresh and try again.')); }
    if (!response.ok) {
      const detail = data.detail || data.error || data;
      const error = new Error(typeof detail === 'string' ? detail : detail.message || t('请求失败', 'Request failed'));
      error.code = detail.code || '';
      throw error;
    }
    return data;
  }
  function controls() {
    const valid = !!canUse() && !!$('model').value && modelAccount === currentAccount && !loadingModels;
    const saved = savedModel();
    const unchanged = saved?.enabled && saved.name === ($('profile-name').value.trim() || defaultName());
    $('account').disabled = !!busy;
    $('login').disabled = !!busy || waiting;
    $('login').hidden = !!selected()?.plan_enabled && !expired(selected());
    $('new-account').hidden = !selected();
    $('new-account').disabled = !!busy || waiting;
    $('logout').hidden = !selected()?.connected;
    $('logout').disabled = !!busy;
    $('cancel').hidden = !waiting;
    $('cancel').disabled = !!busy;
    $('refresh').disabled = !!busy;
    $('models').disabled = !!busy || !canUse() || loadingModels;
    $('models').textContent = loadingModels ? t('读取中…', 'Loading…') : t('刷新模型', 'Refresh models');
    $('model').disabled = !!busy || !valid;
    $('profile-name').disabled = !!busy || !valid;
    $('add-profile').disabled = !!busy || !valid || unchanged;
    $('add-profile').textContent = busy === 'save' ? t('保存中…', 'Saving…') : unchanged ? t('已添加', 'Added') :
      saved ? t('更新配置', 'Update configuration') : t('添加模型', 'Add model');
    $('test-model').disabled = !!busy || !valid;
    $('test-model').textContent = busy === 'test' ? t('测试中…', 'Testing…') : t('测试调用', 'Test request');
  }
  function renderProfiles() {
    const list = $('profile-list');
    list.replaceChildren();
    const rows = profiles.filter(row => row.account_id === currentAccount);
    if (!rows.length) {
      const empty = document.createElement('p');
      empty.className = 'empty-state';
      empty.textContent = currentAccount ? t('此账号还没有添加模型配置。', 'No models added for this account yet.') :
        t('选择一个账号，查看其模型配置。', 'Choose an account to view its configurations.');
      list.append(empty);
    }
    for (const row of rows) {
      const item = document.createElement('div'); item.className = 'profile-row';
      const main = document.createElement('div');
      const name = document.createElement('div'); name.className = 'profile-name'; name.textContent = row.name;
      const meta = document.createElement('div'); meta.className = 'profile-meta'; meta.textContent = row.model;
      const status = document.createElement('span'); status.className = 'profile-pill';
      status.textContent = !selected()?.connected ? t('需登录', 'Sign-in needed') : row.enabled ? t('已启用', 'Enabled') : t('已停用', 'Disabled');
      main.append(name, meta); item.append(main, status); list.append(item);
    }
  }
  function renderAccount() {
    const row = selected(), chip = $('connection-status');
    chip.dataset.kind = row?.plan_enabled && !expired(row) ? 'ok' : row?.connected ? 'warning' : 'idle';
    chip.textContent = row?.plan_enabled && !expired(row) ? t('已授权订阅', 'Plan connected') : expired(row) ? t('需要重新登录', 'Sign-in expired') :
      row?.connected ? t('未授权订阅', 'Plan not authorized') : t('未连接', 'Not connected');
    $('account-description').textContent = !row ? t('登录时选择账号和工作区，并允许此应用使用套餐。', 'Choose an account and workspace, then allow this app to use your plan.') :
      !row.connected || expired(row) ? t('此连接需要重新登录。已有模型配置会保留。', 'Sign in again to use this connection. Your configurations are retained.') :
      !row.plan_enabled ? t('账号已登录；请重新授权，允许使用 ChatGPT 套餐。', 'Signed in without plan access. Continue with ChatGPT to authorize plan usage.') :
      t('此连接已就绪，授权会自动续期。', 'This connection is ready and renews automatically.');
    renderProfiles(); controls();
  }
  function setModelName() {
    if (!$('model').value) { $('profile-name').value = ''; return; }
    const saved = savedModel();
    $('profile-name').value = saved?.name || defaultName();
    if (remembered.account === currentAccount && remembered.model === $('model').value && remembered.name) {
      $('profile-name').value = remembered.name;
      remembered = {};
    }
  }
  function renderModels() {
    const previous = $('model').value || (remembered.account === currentAccount ? remembered.model : '');
    const filter = $('model-filter').value.trim().toLowerCase();
    const rows = catalog.filter(row => (row.name + ' ' + row.id).toLowerCase().includes(filter));
    $('model').replaceChildren(...rows.map(row => new Option(row.name, row.id)));
    if (rows.some(row => row.id === previous)) $('model').value = previous;
    if (!rows.length) $('model').add(new Option(t('没有匹配的模型', 'No matching models'), ''));
    if ($('model').value !== previous || !$('profile-name').value) setModelName();
    const saved = savedModel();
    $('model-hint').textContent = !$('model').value ? t('请调整关键词，选择可用模型。', 'Adjust your search to select an available model.') : saved ? t('这个模型已添加，可编辑名称后更新配置。', 'This model is already added. Edit its name to update the configuration.') :
      t('添加后，在聊天页模型菜单中选择该配置。', 'After adding, choose this configuration in the chat model menu.');
    controls();
  }
  function resetModels() {
    modelGeneration++; modelAbort?.abort(); catalog = []; modelAccount = ''; loadingModels = false;
    $('model').replaceChildren(); $('profile-name').value = ''; $('model-filter').value = '';
    $('model-fields').hidden = true; $('model-empty').hidden = false;
    $('model-empty').textContent = t('连接账号后，自动读取该账号的可用模型。', 'Connect an account to load its models automatically.');
    notice('model-status', ''); controls();
  }
  async function loadModels() {
    if (!canUse()) return;
    modelAbort?.abort(); modelAbort = new AbortController();
    const epoch = ++modelGeneration, account = currentAccount;
    loadingModels = true; controls();
    $('model-empty').hidden = !!catalog.length;
    if (!catalog.length) $('model-empty').textContent = t('正在读取可用模型…', 'Loading available models…');
    notice('model-status', '');
    try {
      const result = await api('models?account_id=' + encodeURIComponent(account), undefined, modelAbort.signal);
      if (disposed || epoch !== modelGeneration || account !== currentAccount) return;
      catalog = result.models || []; modelAccount = account;
      $('model-fields').hidden = !catalog.length; $('model-empty').hidden = !!catalog.length;
      if (!catalog.length) $('model-empty').textContent = t('此账号暂未返回可用模型。可刷新重试或检查授权。', 'No models were returned. Refresh or check the account authorization.');
      renderModels();
    } catch (error) {
      if (error.name !== 'AbortError' && epoch === modelGeneration) {
        $('model-empty').textContent = t('模型读取失败。点击“刷新模型”重试。', 'Models could not be loaded. Choose Refresh models to retry.');
        notice('model-status', error.message, 'error');
      }
    } finally { if (epoch === modelGeneration) { loadingModels = false; controls(); } }
  }
  function schedulePoll() {
    clearTimeout(polling);
    if (waiting && !disposed && !document.hidden) polling = setTimeout(() => refresh().catch(error => {
      if (error.name !== 'AbortError') notice('message', error.message, 'error');
    }), 1500);
  }
  async function refresh() {
    statusAbort?.abort(); statusAbort = new AbortController();
    const epoch = ++statusGeneration;
    const data = await api('status', undefined, statusAbort.signal);
    if (disposed || epoch !== statusGeneration) return;
    const previous = currentAccount;
    accounts = data.accounts || []; profiles = data.profiles || [];
    const completion = waiting && data.login.state === 'connected' ? data.login.account_id : '';
    const preferred = completion || (initialized ? previous : remembered.account || accounts.find(row => row.connected)?.id || '');
    $('account').replaceChildren(new Option(t('添加新账号或工作区', 'Add account or workspace'), ''));
    for (const row of accounts) $('account').add(new Option(row.label + ' · ' + row.id.slice(0, 6), row.id));
    $('account').value = accounts.some(row => row.id === preferred) ? preferred : '';
    currentAccount = $('account').value; initialized = true;
    if (currentAccount !== previous || !canUse()) resetModels();
    waiting = data.login.state === 'waiting';
    $('login-progress').hidden = !waiting && !['error', 'expired'].includes(data.login.state);
    $('login-progress').dataset.kind = ['error', 'expired'].includes(data.login.state) ? 'error' : '';
    $('login-state').textContent = data.login.message || '';
    if (!waiting) { $('authorize').hidden = true; $('authorize').removeAttribute('href'); }
    renderAccount();
    if (catalog.length) renderModels();
    schedulePoll();
    if (canUse() && !catalog.length && !loadingModels) void loadModels();
    if (data.show_plan_notice && !$('plan-notice').open) $('plan-notice').showModal();
  }
  async function action(kind, fn) {
    if (busy) return;
    busy = kind; controls();
    try { await fn(); }
    catch (error) {
      if (error.name !== 'AbortError') {
        notice(kind === 'test' || kind === 'save' ? 'model-status' : 'message', error.message, 'error');
        if (['subscription_sharing_usage_limit_exceeded', 'subscription_sharing_usage_unavailable'].includes(error.code)) $('model-error-usage').hidden = false;
      }
    }
    finally { busy = ''; controls(); }
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
    renderAccount();
    if (catalog.length) renderModels();
  }
  window.addEventListener('message', event => {
    if (!embedded || event.origin !== location.origin || event.source !== window.parent || event.data?.type !== 'myagent:plugin-settings-context') return;
    const data = event.data;
    if (['theme-dark', 'theme-purple', 'theme-light'].includes(data.theme)) {
      root.classList.remove('theme-dark', 'theme-purple', 'theme-light'); root.classList.add(data.theme);
    }
    root.lang = data.lang === 'en' ? 'en' : 'zh-CN';
    if (Number.isFinite(data.fontPx)) {
      const px = Math.max(12, Math.min(20, data.fontPx));
      root.style.setProperty('--st-fs', Math.max(11, px - 2) + 'px'); root.style.setProperty('--st-fs-lg', px + 'px');
      root.style.setProperty('--st-fs-sm', Math.max(10, px - 3) + 'px'); root.style.setProperty('--st-fs-xs', Math.max(9, px - 4) + 'px');
    }
    applyLanguage();
  });
  $('account').addEventListener('change', () => {
    currentAccount = $('account').value; resetModels(); renderAccount(); remember(); void loadModels();
  });
  $('new-account').addEventListener('click', () => { $('account').value = ''; $('account').dispatchEvent(new Event('change')); $('login').focus(); });
  $('model-filter').addEventListener('input', () => { renderModels(); remember(); });
  $('model').addEventListener('change', () => { setModelName(); renderModels(); notice('model-status', ''); remember(); });
  $('profile-name').addEventListener('input', () => { controls(); remember(); });
  $('refresh').addEventListener('click', () => action('refresh', async () => { notice('message', ''); await refresh(); }));
  $('models').addEventListener('click', () => void loadModels());
  $('login').addEventListener('click', () => action('login', async () => {
    notice('message', '');
    const result = await api('login', {account_id: currentAccount});
    const url = new URL(result.authorization_url);
    if (url.origin !== 'https://auth.openai.com' || url.pathname !== '/api/accounts/authorize') throw new Error(t('无效的授权地址', 'Invalid authorization URL'));
    $('authorize').href = url.href; $('authorize').hidden = false;
    waiting = true;
    await refresh();
  }));
  $('cancel').addEventListener('click', () => action('cancel', async () => { await api('cancel', {}); await refresh(); }));
  $('logout').addEventListener('click', () => action('logout', async () => {
    const result = await api('logout', {account_id: currentAccount});
    resetModels(); await refresh(); notice('message', result.message, result.revoked ? 'success' : '');
  }));
  $('add-profile').addEventListener('click', () => action('save', async () => {
    const data = await api('profiles', {account_id: currentAccount, model: $('model').value, name: $('profile-name').value.trim()});
    await refresh();
    notice('model-status', t('已保存“', 'Saved “') + data.profile.name + t('”。可在聊天页模型菜单中选择。', '”. Choose it in the chat model menu.'), 'success');
    remember();
  }));
  $('test-model').addEventListener('click', () => action('test', async () => {
    notice('model-status', t('正在发送测试请求…', 'Sending a test request…'));
    const result = await api('test', {account_id: currentAccount, model: $('model').value});
    notice('model-status', t('调用成功 · ', 'Request succeeded · ') + (result.latency_ms / 1000).toFixed(2) + t(' 秒', ' s'), 'success');
  }));
  $('manage-models').addEventListener('click', event => {
    if (embedded) { event.preventDefault(); remember(); post('myagent:plugin-settings-navigate', {section: 'models'}); }
  });
  async function dismissNotice() {
    $('notice-dismiss').disabled = true;
    try { await api('notice', {}); $('plan-notice').close(); }
    catch (error) { $('notice-error').textContent = error.message; }
    finally { $('notice-dismiss').disabled = false; }
  }
  $('notice-dismiss').addEventListener('click', dismissNotice);
  $('plan-notice').addEventListener('cancel', event => { event.preventDefault(); void dismissNotice(); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !$('plan-notice').open && embedded) { event.preventDefault(); post('myagent:plugin-settings-close'); }
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) clearTimeout(polling);
    else void refresh().catch(error => { if (error.name !== 'AbortError') notice('message', error.message, 'error'); });
  });
  window.addEventListener('pagehide', () => { disposed = true; clearTimeout(polling); modelAbort?.abort(); statusAbort?.abort(); });
  let lastHeight = 0;
  new ResizeObserver(() => {
    const height = Math.ceil(document.querySelector('main').getBoundingClientRect().height);
    if (height !== lastHeight) { lastHeight = height; post('myagent:plugin-settings-resize', {height}); }
  }).observe(document.querySelector('main'));
  applyLanguage(); post('myagent:plugin-settings-ready');
  refresh().catch(error => { if (error.name !== 'AbortError') notice('message', error.message, 'error'); });
})();
