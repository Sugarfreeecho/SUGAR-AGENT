'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const root = document.documentElement;
  const embedded = root.dataset.embedded === 'true';
  const t = (zh, en) => root.lang === 'en' ? en : zh;
  let snapshot = null, saved = null, saving = false, loadingTargets = false;
  let polling = false, disposed = false, timer = null;
  let outboundSnapshot = null, remoteBusy = false, selectedTask = '', intentCache = null;
  const requests = new Set();
  const dirty = () => saved !== null && $('targets').value !== saved;
  const unsaved = () => dirty() || !!$('task-prompt').value.trim();
  function post(type, data = {}) {
    if (embedded && window.parent !== window) window.parent.postMessage({type, ...data}, location.origin);
  }
  function message(id, text) { $(id).textContent = text; $(id).hidden = !text; }
  async function api(path, method = 'GET', body) {
    const controller = new AbortController(); requests.add(controller);
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch('/api/acp/' + path, {method, credentials: 'same-origin', cache: 'no-store',
        signal: controller.signal, ...(body === undefined ? {} : {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})});
      const data = await response.json();
      if (!response.ok) throw new Error(response.status === 404
        ? t('ACP 接口尚未加载，请重新启用 ACP Agents 插件。', 'ACP API is not loaded. Re-enable the ACP Agents plugin.')
        : typeof data.detail === 'string' ? data.detail : t('请求失败', 'Request failed') + ' (' + response.status + ')');
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error(t('请求超时，请检查后端。', 'Request timed out. Check the backend.'));
      throw error;
    } finally { clearTimeout(timeout); requests.delete(controller); }
  }
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function time(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString(root.lang === 'en' ? 'en-US' : 'zh-CN', {hour12: false});
  }
  const activity = key => ({connected: t('建立连接', 'Connected'), attached: t('关联会话', 'Session attached'),
    detached: t('关闭会话', 'Session closed'), prompt: t('执行任务', 'Prompt started'), configured: t('更新配置', 'Configuration updated'),
    completed: t('任务结束', 'Prompt finished'), disconnected: t('断开连接', 'Disconnected')})[key] || key;
  function renderConnections() {
    if (!snapshot) return;
    $('summary').textContent = t('在线客户端 ', 'Online clients: ') + snapshot.online_count + t(' · 关联会话 ', ' · Attached sessions: ') + snapshot.session_count;
    const list = $('connections'); list.replaceChildren();
    if (!snapshot.connections.length) list.append(element('div', t('暂无接入客户端。下方提供启动配置，连接成功后会显示在这里。', 'No clients connected. Use the launch configuration below; connections will appear here.'), 'empty'));
    for (const row of snapshot.connections) {
      const card = element('article', undefined, 'connection');
      const line = element('div', undefined, 'client-line');
      line.append(element('strong', (row.client.title || row.client.name || t('未提供客户端名称', 'Unnamed client')) + (row.client.version ? ' · ' + row.client.version : '')));
      const badge = element('span', row.status === 'online' ? (row.busy ? t('运行中', 'Running') : t('已连接', 'Connected')) : row.status === 'stale' ? t('心跳超时', 'Heartbeat timed out') : t('已断开', 'Disconnected'), 'badge');
      badge.dataset.status = row.status; line.append(badge); card.append(line);
      const facts = element('dl');
      const fields = [[t('连接 ID', 'Connection ID'), row.id], [t('传输 / 协议', 'Transport / protocol'), 'stdio / ACP v' + row.protocol_version],
        [t('连接时间', 'Connected at'), time(row.connected_at)], [t('最后心跳', 'Last heartbeat'), time(row.last_seen)],
        [t('最近活动', 'Last activity'), activity(row.activity) + ' · ' + time(row.last_activity)]];
      for (const [label, value] of fields) facts.append(element('dt', label), element('dd', value));
      card.append(facts);
      if (!row.sessions.length) card.append(element('p', t('尚未关联会话', 'No attached sessions yet'), 'hint'));
      for (const session of row.sessions) {
        const section = element('div', undefined, 'session');
        const attached = row.status === 'online' && session.attached;
        const label = session.busy ? t('运行中', 'Running') : attached ? t('已关联', 'Attached') : row.status === 'stale' && session.attached ? t('连接待确认', 'Connection unconfirmed') : t('已关闭', 'Closed');
        section.append(element('strong', (session.title || t('会话', 'Session')) + ' · ' + label));
        const id = element('p'); id.append(element('code', session.session_id)); section.append(id);
        section.append(element('p', session.cwd, 'hint'));
        const link = element('a', t('查看会话 ↗', 'View session ↗')); link.href = '/?session=' + encodeURIComponent(session.session_id);
        link.target = '_blank'; link.rel = 'noopener'; section.append(link); card.append(section);
      }
      list.append(card);
    }
    $('launch').value = JSON.stringify({sugaragent: snapshot.launch}, null, 2);
    $('copy-launch').disabled = false;
  }
  function updateDraft() {
    $('save').disabled = saved === null || !dirty() || saving || loadingTargets;
    $('reload-targets').disabled = saving || loadingTargets;
    $('draft-status').textContent = saving ? t('正在保存…', 'Saving…') : dirty() ? t('有未保存的更改', 'Unsaved changes') : saved === null ? '' : t('已保存', 'Saved');
    post('myagent:plugin-settings-dirty', {dirty: unsaved()});
  }
  function language() {
    document.querySelectorAll('[data-en]').forEach(node => {
      if (!node.dataset.zh) node.dataset.zh = node.textContent;
      node.textContent = root.lang === 'en' ? node.dataset.en : node.dataset.zh;
    });
    renderConnections(); updateDraft(); renderOutbound();
  }
  async function poll() {
    if (polling || disposed || document.hidden) return;
    polling = true; $('refresh').disabled = true;
    try {
      const data = await api('connections');
      if (disposed) return;
      snapshot = data; renderConnections(); message('connection-error', '');
    } catch (error) {
      if (!disposed) message('connection-error', error.message + (snapshot ? t(' 下方保留上次结果，状态可能已过期。', ' Previous results are shown below and may be out of date.') : ''));
    } finally {
      await pollOutbound();
      polling = false; $('refresh').disabled = false;
      clearTimeout(timer); if (!disposed && !document.hidden) timer = setTimeout(poll, 5000);
    }
  }
  function options(select, rows, placeholder) {
    const wanted = select.value;
    select.replaceChildren();
    if (placeholder) { const item = element('option', placeholder); item.value = ''; select.append(item); }
    for (const row of rows) { const item = element('option', row.label); item.value = row.value; select.append(item); }
    if ([...select.options].some(option => option.value === wanted)) select.value = wanted;
  }
  function taskStatus(row) {
    return ({queued: t('排队中', 'Queued'), running: t('执行中', 'Running'), succeeded: t('成功', 'Succeeded'),
      incomplete: t('未完成', 'Incomplete'), failed: t('失败', 'Failed'), cancelled: t('已取消', 'Cancelled'), interrupted: t('已中断', 'Interrupted')})[row.status] || row.status;
  }
  function updateRemoteButtons() {
    const ready = !!$('source-session').value && !!$('target-agent').value && !remoteBusy;
    for (const id of ['remote-list', 'remote-new']) $(id).disabled = !ready;
    $('remote-more').disabled = !ready || !outboundSnapshot?.next_cursors?.[$('target-agent').value];
    $('remote-close').disabled = !ready || !$('remote-session').value;
    $('task-submit').disabled = !ready || !$('task-prompt').value.trim();
    $('task-notify').disabled = !$('task-background').checked;
  }
  function renderOutbound() {
    if (!outboundSnapshot) { updateRemoteButtons(); return; }
    options($('source-session'), outboundSnapshot.parents.map(row => ({value: row.id, label: row.name})), t('请选择来源会话', 'Choose a source conversation'));
    options($('target-agent'), outboundSnapshot.targets.map(id => ({value: id, label: id})), outboundSnapshot.targets.length ? null : t('尚未配置目标', 'No targets configured'));
    const agent = $('target-agent').value;
    options($('remote-session'), outboundSnapshot.sessions.filter(row => row.agent === agent && row.available).map(row => ({
      value: row.session_id, label: (row.title ? row.title + ' · ' : '') + row.session_id + (row.connected ? t(' · 已连接', ' · Connected') : '')
    })), t('新建会话（默认）', 'New session (default)'));
    const container = $('outbound-tasks'); container.replaceChildren();
    if (!outboundSnapshot.tasks.length) container.append(element('p', t('此来源会话尚无 ACP 任务。', 'No ACP tasks for this source conversation.'), 'hint'));
    for (const row of outboundSnapshot.tasks) {
      const item = element('div', undefined, 'task-row');
      item.append(element('strong', row.agent + ' · ' + taskStatus(row) + ' · ' + (row.session_action === 'new' ? t('新建', 'New') : t('续接', 'Continue'))));
      item.append(element('p', row.session_id || t('等待创建会话', 'Waiting for session'), 'hint'));
      const actions = element('div', undefined, 'actions');
      const show = element('button', t('查看进度与结果', 'View progress and result'), 'st-btn');
      show.addEventListener('click', () => { selectedTask = row.task_id; void loadTask(); }); actions.append(show);
      if (['queued', 'running'].includes(row.status)) {
        const cancel = element('button', t('取消任务', 'Cancel task'), 'st-btn');
        cancel.addEventListener('click', async () => {
          cancel.disabled = true;
          try { await api('outbound/tasks/' + encodeURIComponent(row.task_id) + '/cancel', 'POST', {origin: $('source-session').value}); await pollOutbound(); }
          catch (error) { message('outbound-error', error.message); }
          finally { cancel.disabled = false; }
        }); actions.append(cancel);
      }
      item.append(actions); container.append(item);
    }
    updateRemoteButtons();
  }
  async function loadTask() {
    if (!selectedTask || !$('source-session').value || disposed) return;
    const tid = selectedTask, origin = $('source-session').value;
    try {
      const row = await api('outbound/tasks/' + encodeURIComponent(tid) + '?origin=' + encodeURIComponent(origin));
      if (disposed || selectedTask !== tid || $('source-session').value !== origin) return;
      $('task-detail').hidden = false;
      $('task-progress').textContent = row.events.filter(event => event.type === 'message').map(event => event.text).join('') || t('暂无文本进度', 'No progress text yet');
      $('task-result').textContent = row.output || '';
      $('task-delivery').textContent = taskStatus(row) + ' · ' + t('回送状态：', 'Reporting: ') + (row.delivery.status || 'none')
        + (row.delivery.operation_id ? ' · ' + row.delivery.operation_id : '') + (row.error ? ' · ' + row.error : '')
        + (row.truncated ? t(' · 文本已截断', ' · Text truncated') : '');
    } catch (error) { if (!disposed) message('outbound-error', error.message); }
  }
  async function pollOutbound() {
    if (disposed || document.hidden) return;
    const origin = $('source-session').value;
    try {
      const data = await api('outbound' + (origin ? '?origin=' + encodeURIComponent(origin) : ''));
      if (disposed || $('source-session').value !== origin) return;
      outboundSnapshot = data; renderOutbound(); message('outbound-error', ''); await loadTask();
    } catch (error) { if (!disposed) message('outbound-error', error.message + t(' 已显示的任务记录可能已过期。', ' Displayed task records may be out of date.')); }
  }
  async function requestRemote(action, more = false) {
    if (remoteBusy) return;
    const args = {agent: $('target-agent').value};
    if (more) args.cursor = outboundSnapshot.next_cursors[args.agent];
    if (action === 'task') Object.assign(args, {prompt: $('task-prompt').value, background: $('task-background').checked, notify: $('task-notify').value});
    if (['task', 'close'].includes(action) && $('remote-session').value) args.session_id = $('remote-session').value;
    const payload = {origin: $('source-session').value, action, arguments: args};
    const signature = JSON.stringify(payload);
    if (!intentCache || intentCache.signature !== signature) intentCache = {signature, id: crypto.randomUUID()};
    payload.request_id = intentCache.id;
    remoteBusy = true; updateRemoteButtons();
    try {
      const receipt = await api('outbound/requests', 'POST', payload);
      message('outbound-notice', t('请求已交给来源会话，等待 Agent 执行。操作 ID：', 'Request queued in the source conversation. Operation ID: ') + receipt.operation_id);
      if (action === 'task') { $('task-prompt').value = ''; updateDraft(); }
      await pollOutbound();
    } catch (error) { message('outbound-error', error.message); }
    finally { remoteBusy = false; updateRemoteButtons(); }
  }
  $('source-session').addEventListener('change', () => { selectedTask = ''; $('remote-session').value = ''; $('task-detail').hidden = true; void pollOutbound(); });
  $('target-agent').addEventListener('change', () => { $('remote-session').value = ''; renderOutbound(); });
  $('remote-session').addEventListener('change', updateRemoteButtons);
  $('task-background').addEventListener('change', updateRemoteButtons);
  $('task-prompt').addEventListener('input', () => { updateRemoteButtons(); updateDraft(); });
  $('remote-list').addEventListener('click', () => requestRemote('list'));
  $('remote-more').addEventListener('click', () => requestRemote('list', true));
  $('remote-new').addEventListener('click', () => requestRemote('new'));
  $('remote-close').addEventListener('click', () => requestRemote('close'));
  $('task-submit').addEventListener('click', () => requestRemote('task'));
  async function loadTargets() {
    if (saving || loadingTargets) return;
    if (dirty() && !confirm(t('重新读取会丢弃未保存的配置，继续？', 'Reload and discard unsaved changes?'))) return;
    loadingTargets = true; updateDraft();
    try {
      const data = await api('targets');
      if (disposed) return;
      saved = data.agents_json; $('targets').value = saved; $('targets').disabled = false;
      $('targets').removeAttribute('aria-invalid'); message('settings-error', '');
    } catch (error) { if (!disposed) message('settings-error', error.message); }
    finally { loadingTargets = false; updateDraft(); }
  }
  $('targets').addEventListener('input', () => { $('targets').removeAttribute('aria-invalid'); updateDraft(); });
  $('refresh').addEventListener('click', () => { clearTimeout(timer); void poll(); });
  $('reload-targets').addEventListener('click', loadTargets);
  $('save').addEventListener('click', async () => {
    if (saving || !dirty()) return;
    const draft = $('targets').value;
    try { JSON.parse(draft); }
    catch (error) { $('targets').setAttribute('aria-invalid', 'true'); message('settings-error', t('JSON 格式错误：', 'Invalid JSON: ') + error.message); return; }
    saving = true; updateDraft();
    try {
      const data = await api('targets', 'PUT', {agents_json: draft});
      saved = data.agents_json; message('settings-error', ''); $('targets').removeAttribute('aria-invalid');
      message('message', t('配置已保存并生效。目标数量：', 'Configuration saved. Targets: ') + data.target_ids.length);
    } catch (error) { if (!disposed) message('settings-error', error.message); }
    finally { saving = false; updateDraft(); }
  });
  $('copy-launch').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText($('launch').value); message('message', t('启动配置已复制。', 'Launch configuration copied.')); }
    catch (_) { $('launch').focus(); $('launch').select(); message('message', t('请复制已选中的启动配置。', 'Copy the selected launch configuration.')); }
  });
  window.addEventListener('message', event => {
    if (!embedded || event.origin !== location.origin || event.source !== window.parent || event.data?.type !== 'myagent:plugin-settings-context') return;
    const data = event.data;
    if (['theme-dark', 'theme-purple', 'theme-light'].includes(data.theme)) root.className = data.theme;
    root.lang = data.lang === 'en' ? 'en' : 'zh-CN';
    if (Number.isFinite(data.fontPx)) {
      const px = Math.max(12, Math.min(20, data.fontPx)); root.style.setProperty('--st-fs', Math.max(11, px - 2) + 'px'); root.style.setProperty('--st-fs-lg', px + 'px');
    }
    language();
  });
  window.addEventListener('beforeunload', event => { if (unsaved()) { event.preventDefault(); event.returnValue = ''; } });
  document.addEventListener('visibilitychange', () => { clearTimeout(timer); if (!document.hidden) void poll(); });
  window.addEventListener('pagehide', () => { disposed = true; clearTimeout(timer); for (const request of requests) request.abort(); });
  let lastHeight = 0;
  new ResizeObserver(() => {
    const height = Math.ceil(document.querySelector('main').getBoundingClientRect().height) + 12;
    if (lastHeight !== height) { lastHeight = height; post('myagent:plugin-settings-resize', {height}); }
  }).observe(document.querySelector('main'));
  language(); post('myagent:plugin-settings-ready'); void poll(); void loadTargets();
})();
