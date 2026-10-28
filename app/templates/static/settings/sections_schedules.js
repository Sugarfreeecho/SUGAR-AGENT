/* Native scheduled tasks: the settings view uses the existing control backend. */
(function () {
  'use strict';
  const A = window.MyAgentSettings;
  const { t, esc, W, api, toast, reportError, openDialog, askConfirm } = A;
  const boot = A.bootSection || {};
  let data = { items: [], sessions: [], profiles: [], tools: [] };
  const key = () => window.crypto?.randomUUID?.() || (Date.now() + '-' + Math.random().toString(36).slice(2));
  const refKey = ref => [ref.kind, ref.owner, ref.name].join('\u0000');
  async function rpc(method, params = {}, idempotency = key()) {
    try {
      const response = await api('/api/settings/session-control', { method: 'POST',
        headers: { 'X-MyAgent-Settings': 'schedules' }, body: { method, params, idempotency_key: idempotency } });
      return response.data;
    } catch (err) {
      if (err.payload?.error?.message) err.message = err.payload.error.message;
      throw err;
    }
  }
  const labels = () => ({ daily: t('每天', 'Every day'), weekdays: t('工作日', 'Weekdays'), weekly: t('每周', 'Weekly'),
    monthly: t('每月', 'Monthly'), at: t('仅一次', 'Once'), after: t('延迟一次', 'After a delay'),
    interval: t('固定间隔', 'Fixed interval'), cron: 'Cron' });
  const states = () => ({ queued: t('排队中', 'Queued'), running: t('运行中', 'Running'), succeeded: t('已完成', 'Succeeded'),
    failed: t('失败', 'Failed'), stopped: t('已停止', 'Stopped'), interrupted: t('已中断', 'Interrupted'),
    unknown: t('结果不明', 'Unknown'), cancelled: t('已取消', 'Cancelled'), coalesced: t('已合并', 'Coalesced'), rejected: t('未接收', 'Rejected') });
  function date(value, zone) {
    if (!value) return '—';
    try { return new Intl.DateTimeFormat(A.lang === 'zh' ? 'zh-CN' : 'en-GB', {
      timeZone: zone || 'Asia/Shanghai', dateStyle: 'medium', timeStyle: 'short', hour12: false }).format(new Date(value * 1000)); }
    catch (_) { return new Date(value * 1000).toISOString(); }
  }
  function wallDate(value, zone) {
    const parts = new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(value));
    const p = Object.fromEntries(parts.map(x => [x.type, x.value]));
    return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
  }
  function decode(trigger = {}) {
    if (trigger.kind !== 'cron') return { ...trigger,
      local_at: trigger.at ? wallDate(trigger.at, trigger.time_zone || 'Asia/Shanghai') : '', minutes: (trigger.seconds || 3600) / 60 };
    const p = trigger.expression.trim().split(/\s+/);
    const d = { ...trigger, kind: 'cron', time: '09:00' };
    if (p.length === 5 && /^\d+$/.test(p[0]) && /^\d+$/.test(p[1]) && p[3] === '*') {
      d.time = p[1].padStart(2, '0') + ':' + p[0].padStart(2, '0');
      if (p[2] === '*') {
        if (p[4] === '*') d.kind = 'daily';
        else if (p[4] === '1-5') d.kind = 'weekdays';
        else if (/^[0-6](,[0-6])*$/.test(p[4])) { d.kind = 'weekly'; d.weekdays = p[4].split(',').map(x => Number(x) || 7); }
      } else if (/^\d+(,\d+)*$/.test(p[2]) && p[4] === '*') { d.kind = 'monthly'; d.days = p[2].split(',').map(Number); }
    }
    return d;
  }
  function repeatText(row) {
    const d = decode(row.trigger), name = labels()[d.kind] || d.kind;
    if (d.kind === 'at') return name;
    if (d.kind === 'interval') return t('每 ', 'Every ') + d.minutes + t(' 分钟', ' min');
    if (d.kind === 'cron') return 'Cron · ' + row.trigger.expression;
    return name + ' · ' + (d.time || '09:00');
  }
  const button = (label, action, id, variant = 'text sm') => W.btn(label, action, variant, 'data-id="' + esc(id) + '"');
  function list(d) {
    const rows = d.items.map(row => {
      const status = row.last_error ? W.status('warn', t('需要处理', 'Needs attention')) : row.completed ? W.chip(t('已结束', 'Finished')) :
        row.enabled ? W.status('ok', t('已启用', 'Enabled')) : W.chip(t('已暂停', 'Paused'));
      const session = d.sessions.find(s => s.id === row.target.session_id);
      const target = row.target.mode === 'new' ? t('每次开启新聊天', 'New chat each run') : (session?.name || row.target.session_id);
      return '<article class="st-schedule-item" data-search-text="' + esc(row.name + ' ' + row.action.text) + '">' +
        '<div class="st-schedule-item-head"><div><h3>' + esc(row.name) + '</h3><div class="st-hint">' + esc(repeatText(row)) +
        ' · ' + esc(row.trigger.time_zone || 'Asia/Shanghai') + '</div></div>' + status + '</div>' +
        '<p class="st-schedule-description">' + esc(row.action.text || '') + '</p>' +
        '<div class="st-schedule-meta"><span>' + t('下次运行：', 'Next: ') + esc(date(row.next_run_at, row.trigger.time_zone)) +
        '</span><span>' + esc(target) + '</span></div>' +
        (row.last_error ? '<p class="st-schedule-error">' + esc(row.last_error.message) + '</p>' : '') +
        '<div class="st-schedule-actions">' + button(t('编辑', 'Edit'), 'schedule-edit', row.id) +
        button(t('立即运行', 'Run now'), 'schedule-run', row.id) + (!row.completed ? button(row.enabled ? t('暂停', 'Pause') : t('启用', 'Enable'), 'schedule-toggle', row.id) : '') +
        button(t('执行记录', 'History'), 'schedule-history', row.id) + button(t('删除', 'Delete'), 'schedule-delete', row.id, 'text sm danger') + '</div></article>';
    }).join('');
    return '<div class="st-schedule-toolbar"><span class="st-hint">' + t('共 ', '') + d.items.length + t(' 个任务', ' tasks') +
      '</span><div class="st-acts">' + W.btn(t('刷新', 'Refresh'), 'schedule-refresh', 'sm') +
      W.btn(t('新建定时任务', 'New scheduled task'), 'schedule-new', 'primary sm') + '</div></div>' +
      (rows || '<div class="st-schedule-empty">' + A.icon('schedules', 30) + '<h3>' + t('把重复的事情交给 Agent', 'Let your agent handle recurring work') +
        '</h3><p>' + t('设置任务内容和时间，后端会在到期后自动执行。', 'Choose instructions and a time. The backend runs the task when due.') +
        '</p>' + W.btn(t('创建第一个任务', 'Create your first task'), 'schedule-new', 'primary') + '</div>') +
      W.note(t('任务在此电脑的后端运行。关闭聊天窗口不影响已接收的任务；电脑休眠或后端停机后，按补跑策略恢复。',
        'Tasks run on this computer’s backend. Closing chat does not cancel accepted work. Missed runs follow the selected recovery policy.'));
  }
  const field = (name, label, control, hint = '') => '<label class="st-schedule-field"><span>' + label + '</span>' + control +
    (hint ? '<small class="st-hint">' + hint + '</small>' : '') + '</label>';
  const input = (name, value, type = 'text', attrs = '') => '<input class="st-input" data-field="' + name + '" type="' + type + '" value="' + esc(value ?? '') + '" ' + attrs + '>';
  const select = (name, value, options) => '<select class="st-input" data-field="' + name + '">' +
    options.map(([v, label]) => '<option value="' + esc(v) + '"' + (String(v) === String(value) ? ' selected' : '') + '>' + esc(label) + '</option>').join('') + '</select>';
  function edit(row) {
    const original = row || {}, d = decode(original.trigger || { kind: 'daily', time: '09:00' });
    const override = original.runtime_override || {}, prompt = override.system_prompt || {}, tools = override.tools || {};
    const modelOptions = [['', t('继承会话 / 使用默认模型', 'Inherit chat / default model')], ...data.profiles.map(p => [p.id, p.name || p.model])];
    if (override.model_profile_id && !modelOptions.some(p => p[0] === override.model_profile_id)) {
      modelOptions.push([override.model_profile_id, override.model_profile_id + ' · ' + t('当前不可用', 'Unavailable')]);
    }
    const sid = original.target?.session_id || boot.sessionId || '', newChat = row ? row.target.mode === 'new' : !sid;
    const sessionOptions = [['', t('选择会话', 'Select a chat')], ...data.sessions.map(s => [s.id, s.name || s.id])];
    if (sid && !sessionOptions.some(x => x[0] === sid)) sessionOptions.push([sid, sid]);
    const selected = new Set((tools.allow || []).map(refKey));
    const refs = data.tools.map(x => x.tool_ref), unknown = (tools.allow || []).filter(ref => !refs.some(r => refKey(r) === refKey(ref)));
    const toolOptions = [...data.tools, ...unknown.map(ref => ({ tool_ref: ref, missing: true }))].map(x => {
      const ref = x.tool_ref;
      return '<label class="st-schedule-tool"><input type="checkbox" data-tool-ref="' + esc(JSON.stringify(ref)) + '"' +
        (selected.has(refKey(ref)) ? ' checked' : '') + '><span>' + esc(ref.name) +
        '<small>' + esc(ref.owner) + (x.missing ? ' · ' + t('当前不可用', 'Unavailable') : '') + '</small></span></label>';
    }).join('');
    const rowField = (label, control, hint = '') => W.row(label, hint, control);
    const toggle = (name, checked, label) => W.sw(name, checked, 'aria-label="' + label + '"');
    const form = '<form id="st-schedule-form" class="st-schedule-form">' +
      field('name', t('任务名称', 'Task name'), input('name', original.name, 'text', 'maxlength="160" placeholder="' + t('例如：每天整理项目进展', 'For example: Daily project summary') + '"')) +
      '<label class="st-schedule-field"><span class="st-sr-only">' + t('任务说明', 'Instructions') + '</span>' +
      '<textarea class="st-input st-schedule-prompt" data-field="instructions" required placeholder="' + t('说明… 希望 Agent 在运行时做什么？', 'Instructions… What should the agent do?') + '">' + esc(original.action?.text || '') + '</textarea></label>' +
      '<div class="st-card">' + rowField(t('重复', 'Repeat'), select('repeat', d.kind, Object.entries(labels()))) +
      '<div data-schedule-show="daily weekdays weekly monthly">' + rowField(t('时间', 'Time'), input('time', d.time || '09:00', 'time')) + '</div>' +
      '<div data-schedule-show="weekly">' + field('weekdays', t('每周', 'Days of week'), '<div class="st-schedule-weekdays">' +
        [1, 2, 3, 4, 5, 6, 7].map((n, i) => '<label><input type="checkbox" data-weekday="' + n + '"' + ((d.weekdays || [1]).includes(n) ? ' checked' : '') + '><span>' +
          [t('一', 'Mon'), t('二', 'Tue'), t('三', 'Wed'), t('四', 'Thu'), t('五', 'Fri'), t('六', 'Sat'), t('日', 'Sun')][i] + '</span></label>').join('') + '</div>') + '</div>' +
      '<div data-schedule-show="monthly">' + field('monthdays', t('每月日期', 'Days of month'), input('monthdays', (d.days || [1]).join(',')), t('用逗号分隔，如 1,15,28。不存在的日期跳过。', 'Comma-separated, e.g. 1,15,28. Missing dates are skipped.')) + '</div>' +
      '<div data-schedule-show="at">' + field('local_at', t('运行日期和时间', 'Date and time'), input('local_at', d.local_at || wallDate(Date.now() + 3600000, 'Asia/Shanghai'), 'datetime-local')) + '</div>' +
      '<div data-schedule-show="interval after">' + field('minutes', t('分钟', 'Minutes'), input('minutes', d.minutes || 60, 'number', 'min="1" step="1"')) + '</div>' +
      '<div data-schedule-show="cron">' + field('cron', t('五字段 Cron', 'Five-field Cron'), input('cron', d.expression || '0 9 * * *'), t('分钟 小时 日 月 星期，例如 0 9 * * 1-5', 'Minute hour day month weekday, e.g. 0 9 * * 1-5')) + '</div>' +
      rowField(t('时区', 'Timezone'), input('timezone', d.time_zone || 'Asia/Shanghai', 'text', 'list="st-schedule-zones" required')) +
      '<datalist id="st-schedule-zones"><option value="Asia/Shanghai"><option value="Asia/Tokyo"><option value="Europe/London"><option value="America/New_York"><option value="UTC"></datalist></div>' +
      W.adv(t('高级', 'Advanced'), '<div class="st-card">' +
        rowField(t('执行动作', 'Action'), select('action_kind', original.action?.kind || 'prompt', [['prompt', t('发送任务说明', 'Send instructions')], ['notice', t('仅写入通知', 'Add a notice')], ['continue', t('继续未完成会话', 'Continue an unfinished chat')], ['stop', t('停止会话', 'Stop a chat')]])) +
        rowField(t('在此电脑上运行', 'Run on this computer'), toggle('enabled', row ? row.enabled : true, t('在此电脑上运行', 'Run on this computer')), t('关闭后暂停未来触发。已接收的执行可在记录中取消。', 'Off pauses future triggers. Cancel accepted work in History.')) +
        rowField(t('通知', 'Notifications'), select('notification', original.notification || 'important', [['important', t('重要更新', 'Important updates')], ['always', t('每次结束', 'Every completion')], ['never', t('关闭', 'Off')]]),
          t('重要更新：失败、结果不明或需确认时，通过已启用的通知渠道提醒。', 'Important: failures, unknown outcomes, or confirmation requests via enabled notification channels.')) +
        rowField(t('每次运行时都开启新聊天', 'Open a new chat each run'), toggle('new_chat', newChat, t('每次运行时都开启新聊天', 'Open a new chat each run'))) +
        '<div data-schedule-existing>' + field('session', t('目标会话', 'Target chat'), select('session', sid, sessionOptions)) + '</div>' +
        '<div data-schedule-new>' + field('workspace', t('工作目录', 'Workspace'), input('workspace', original.workspace || boot.workspace || '', 'text', 'data-path-kind="directory"')) + '</div>' +
        rowField(t('模型', 'Model'), select('model', override.model_profile_id || '', modelOptions)) +
        rowField(t('推理强度', 'Reasoning effort'), select('effort', override.reasoning_effort || '', [['', t('继承', 'Inherit')], ...['low', 'medium', 'high', 'xhigh', 'max'].map(x => [x, x])])) + '</div>' +
        '<div class="st-card">' + rowField('System Prompt', select('prompt_mode', prompt.mode || 'inherit', [['inherit', t('继承会话', 'Inherit chat')], ['append', t('本次追加', 'Append for this run')], ['replace', t('本次替换', 'Replace for this run')]])) +
        '<div data-schedule-prompt-config>' + field('system_text', t('系统提示词', 'System prompt'), '<textarea class="st-input" rows="5" data-field="system_text">' + esc(prompt.text || '') + '</textarea>', t('仅作用于任务轮次，不改写目标会话的持久配置。', 'Applies only to task turns; the chat configuration stays independent.')) + '</div>' +
        rowField(t('工具', 'Tools'), select('tools_mode', tools.mode || 'inherit', [['inherit', t('继承可用工具', 'Inherit available tools')], ['custom', t('自定义列表', 'Custom list')]])) +
        '<div data-schedule-tools>' + (data.toolError ? '<p class="st-schedule-error">' + esc(data.toolError) + '</p>' : '') +
        '<p class="st-hint">' + t('未选择任何工具表示禁用全部工具。会话及宿主限制继续生效。', 'No selection disables all tools. Chat and host restrictions still apply.') + '</p><div class="st-schedule-tools">' + toolOptions + '</div></div>' +
        rowField(t('只读执行', 'Read-only execution'), toggle('read_only', !!override.read_only, t('只读执行', 'Read-only execution'))) +
        field('bindings', t('工具参数规则（JSON，可选）', 'Tool parameter bindings (JSON, optional)'), '<textarea class="st-input st-mono" rows="3" data-field="bindings" placeholder="[]">' + esc(JSON.stringify(tools.bindings || [], null, 2)) + '</textarea>', t('支持默认值、固定值及参数约束，保存时由后端校验。', 'Defaults, fixed values, and constraints are validated by the backend.')) + '</div>' +
        '<div class="st-card">' + rowField(t('最长运行时间（秒）', 'Run timeout (seconds)'), input('timeout', override.limits?.timeout_seconds, 'number', 'min="1"')) +
        rowField(t('最多工具调用次数', 'Maximum tool calls'), input('tool_calls', override.limits?.max_tool_calls, 'number', 'min="1" step="1"')) +
        rowField(t('漏跑策略', 'Missed runs'), select('misfire', original.misfire || 'latest', [['latest', t('补跑最新一次', 'Run the latest occurrence')], ['skip', t('跳过漏跑', 'Skip missed occurrences')]])) +
        rowField(t('最多计划运行次数', 'Maximum scheduled runs'), input('max_runs', original.max_runs, 'number', 'min="1" step="1"'), t('留空表示不限制；手动运行不计数。', 'Blank means unlimited; manual runs do not count.')) +
        rowField(t('截止时间（可选）', 'End time (optional)'), input('end_at', original.end_at ? wallDate(original.end_at * 1000, d.time_zone || 'Asia/Shanghai') : '', 'datetime-local')) + '</div>', true) +
      '<p class="st-schedule-error" id="st-schedule-error" role="alert" hidden></p></form>';
    let dirty = false, submitted = null, submissionKey = null;
    openDialog({ title: row ? t('编辑定时任务', 'Edit scheduled task') : t('设置定时任务', 'Set up a scheduled task'), body: form,
      okText: row ? t('保存', 'Save') : t('创建', 'Create'),
      beforeClose: () => !document.getElementById('st-dlg-ok').disabled && (!dirty || window.confirm(t('有未保存的任务设置，仍要关闭吗？', 'Discard unsaved task settings?'))),
      after(root) {
        const controller = new AbortController(), options = { signal: controller.signal };
        const refresh = () => {
          const value = n => root.querySelector('[data-field="' + n + '"]').value;
          root.querySelectorAll('[data-schedule-show]').forEach(el => { el.hidden = !el.dataset.scheduleShow.split(' ').includes(value('repeat')); });
          const newChat = root.querySelector('[data-key="new_chat"]').getAttribute('aria-checked') === 'true';
          root.querySelector('[data-schedule-existing]').hidden = newChat;
          root.querySelector('[data-schedule-new]').hidden = !newChat;
          root.querySelector('[data-schedule-tools]').hidden = value('tools_mode') !== 'custom';
          root.querySelector('[data-schedule-prompt-config]').hidden = value('prompt_mode') === 'inherit';
          root.querySelector('[data-field="instructions"]').required = ['prompt', 'notice'].includes(value('action_kind'));
          root.querySelectorAll('[data-schedule-show] input').forEach(el => { el.disabled = !!el.closest('[data-schedule-show]').hidden; });
        };
        root.addEventListener('input', () => { dirty = true; }, options);
        root._scheduleRefresh = refresh;
        root.addEventListener('change', () => { dirty = true; refresh(); }, options);
        root.addEventListener('click', ev => { if (ev.target.closest('[data-key]')) { dirty = true; refresh(); } }, options);
        root.querySelector('form').addEventListener('submit', ev => { ev.preventDefault(); document.getElementById('st-dlg-ok').click(); });
        refresh();
        return () => { controller.abort(); delete root._scheduleRefresh; };
      },
      async onOk() {
        const root = document.getElementById('st-schedule-form'), error = root.querySelector('#st-schedule-error');
        if (!root.reportValidity()) return true;
        const value = name => root.querySelector('[data-field="' + name + '"]').value.trim();
        const on = name => root.querySelector('[data-key="' + name + '"]').getAttribute('aria-checked') === 'true';
        const saveButton = document.getElementById('st-dlg-ok');
        if (saveButton.disabled) return true;
        saveButton.disabled = true;
        try {
          const kind = value('repeat'), zone = value('timezone');
          const actionKind = value('action_kind');
          if (on('new_chat') && ['continue', 'stop'].includes(actionKind)) throw new Error(t('继续或停止需要选择已有会话。', 'Continue and stop require an existing chat.'));
          let trigger = { kind, time_zone: zone };
          if (['daily', 'weekdays', 'weekly', 'monthly'].includes(kind)) trigger.time = value('time');
          if (kind === 'weekly') trigger.weekdays = [...root.querySelectorAll('[data-weekday]:checked')].map(x => Number(x.dataset.weekday));
          if (kind === 'monthly') trigger.days = value('monthdays').split(',').map(x => Number(x.trim()));
          if (kind === 'at') trigger.local_at = value('local_at');
          if (kind === 'interval' || kind === 'after') trigger.seconds = Number(value('minutes')) * 60;
          if (kind === 'cron') trigger.expression = value('cron');
          // Editing content preserves an existing anchor and next scheduled time.
          const initial = decode(original.trigger || {});
          if (row && kind === initial.kind && zone === (initial.time_zone || 'Asia/Shanghai') &&
              (kind !== 'interval' || Number(value('minutes')) === initial.minutes) &&
              (kind !== 'at' || value('local_at') === initial.local_at) &&
              (!['daily', 'weekdays', 'weekly', 'monthly'].includes(kind) || value('time') === initial.time) &&
              (kind !== 'weekly' || JSON.stringify(trigger.weekdays) === JSON.stringify(initial.weekdays)) &&
              (kind !== 'monthly' || JSON.stringify(trigger.days) === JSON.stringify(initial.days)) &&
              (kind !== 'cron' || value('cron') === initial.expression)) trigger = original.trigger;
          const runtime = { ...override };
          if (value('model')) runtime.model_profile_id = value('model'); else delete runtime.model_profile_id;
          if (value('effort')) runtime.reasoning_effort = value('effort'); else delete runtime.reasoning_effort;
          if (value('prompt_mode') === 'inherit') delete runtime.system_prompt;
          else runtime.system_prompt = { mode: value('prompt_mode'), text: value('system_text') };
          const bindings = JSON.parse(value('bindings') || '[]');
          if (!Array.isArray(bindings)) throw new Error(t('参数规则必须是 JSON 数组。', 'Bindings must be a JSON array.'));
          if (data.toolError && value('tools_mode') === 'custom') throw new Error(t('工具目录加载失败，请刷新后重试。', 'Reload the tool catalog before saving a custom list.'));
          runtime.tools = { ...tools, mode: value('tools_mode'), allow: value('tools_mode') === 'custom' ?
            [...root.querySelectorAll('[data-tool-ref]:checked')].map(x => JSON.parse(x.dataset.toolRef)) : [], bindings };
          runtime.read_only = on('read_only');
          runtime.limits = { ...(override.limits || {}) };
          for (const [field, name] of [['timeout', 'timeout_seconds'], ['tool_calls', 'max_tool_calls']]) {
            if (value(field)) runtime.limits[name] = Number(value(field)); else delete runtime.limits[name];
          }
          const policy = original.policy ? JSON.parse(JSON.stringify(original.policy)) : { scope: 'workspace', capabilities: ['read', 'session.create', 'session.send'] };
          policy.capabilities = [...new Set([...(policy.capabilities || []), {prompt: 'session.send', notice: 'session.notice', continue: 'session.continue', stop: 'session.interrupt'}[actionKind]])];
          const payload = { name: value('name') || value('instructions').split('\n')[0].slice(0, 60), enabled: on('enabled'), trigger,
            action: { kind: actionKind, text: value('instructions') }, policy, target: on('new_chat') ? { mode: 'new' } : { mode: 'existing', session_id: value('session') },
            workspace: on('new_chat') ? value('workspace') : (original.workspace || boot.workspace), runtime_override: runtime,
            notification: value('notification'), misfire: value('misfire'), max_runs: value('max_runs') ? Number(value('max_runs')) : null,
            end_local: value('end_at') ? { local_at: value('end_at'), time_zone: zone } : null,
            ...(row ? { id: row.id, expected_revision: row.revision } : {}) };
          if (!on('new_chat') && !value('session')) throw new Error(t('请选择目标会话。', 'Select a target chat.'));
          if (on('new_chat') && !value('workspace')) throw new Error(t('请填写工作目录。', 'Enter a workspace.'));
          const signature = JSON.stringify(payload);
          if (signature !== submitted) { submitted = signature; submissionKey = key(); }
          await rpc(row ? 'automation.update' : 'automation.create', payload, submissionKey);
          dirty = false;
          toast(t('定时任务已保存', 'Scheduled task saved'));
          await A.reload();
          return false;
        } catch (err) { error.textContent = err.message; error.hidden = false; return true; }
        finally { saveButton.disabled = false; }
      } });
  }
  async function history(id) {
    const result = await rpc('automation.history', { id, limit: 100 });
    const rows = result.executions.map(op => '<div class="st-schedule-run"><div class="st-schedule-item-head"><strong>' + esc(states()[op.status] || op.status) +
      '</strong><span class="st-hint">' + esc(date(op.created_at || op.created)) + '</span></div><p class="st-mono st-hint">' + esc(op.operation_id) + '</p>' +
      (op.error ? '<p class="st-schedule-error">' + esc(op.error.message) + '</p>' : '') +
      (op.content ? '<pre class="st-schedule-result">' + esc(op.content) + '</pre>' : '') +
      '<div class="st-acts">' + (op.session_id ? '<a class="st-btn sm text" href="/?session_id=' + encodeURIComponent(op.session_id) + '" target="_top">' + t('打开会话', 'Open chat') + '</a>' : '') +
      (['queued', 'running', 'cancelling'].includes(op.status) ? button(t('取消执行', 'Cancel execution'), 'schedule-cancel', op.operation_id) : '') + '</div></div>').join('');
    openDialog({ title: t('执行记录', 'Execution history'), body: '<div class="st-schedule-history">' +
      W.btn(t('刷新记录', 'Refresh history'), 'schedule-history', 'sm', 'data-id="' + esc(id) + '"') + (rows || W.empty(t('还没有执行记录', 'No executions yet'))) + '</div>',
      okText: t('关闭', 'Close') });
  }
  A.registerSection({ id: 'schedules', icon: 'schedules', zh: '定时任务', en: 'Scheduled tasks', mode: 'instant',
    zhSub: '按计划驱动 Agent，管理运行时间、会话与每次执行的配置。', enSub: 'Schedule agent work and manage timing, chats, and execution settings.',
    async load() {
      const [tasks, sessions, profiles, catalog] = await Promise.all([rpc('automation.list'), rpc('session.list'),
        api('/api/model_profiles').catch(() => ({ profiles: [] })), rpc('tool_catalog.list').catch(err => ({ tools: [], error: err.message }))]);
      data = { items: tasks.items, sessions: sessions.sessions.filter(s => !s.is_subagent && !s.archived),
        profiles: (profiles.profiles || []).filter(p => p.enabled !== false), tools: catalog.tools || [], toolError: catalog.error };
      return data;
    }, render: list, onSearch: A.filterSearchRows,
    onToggle() { document.getElementById('st-dlg-body')._scheduleRefresh?.(); },
    onAction(action, el) {
      if (!action.startsWith('schedule-')) return;
      const id = el.dataset.id, row = data.items.find(x => x.id === id);
      if (action === 'schedule-new') { edit(); return; }
      if (action === 'schedule-edit') { edit(row); return; }
      if (action === 'schedule-refresh') { A.reload().catch(reportError); return; }
      if (action === 'schedule-history') { history(id).catch(reportError); return; }
      const perform = async () => {
        el.disabled = true;
        try {
          if (action === 'schedule-cancel') { await rpc('operation.cancel', { id }); toast(t('已请求取消', 'Cancellation requested')); el.closest('.st-schedule-run')?.remove(); return; }
          await rpc('automation.' + (action === 'schedule-run' ? 'run' : action === 'schedule-delete' ? 'delete' : row.enabled ? 'pause' : 'resume'),
            { id, expected_revision: row.revision });
          toast(action === 'schedule-run' ? t('已接收，后端将排队执行', 'Accepted and queued by the backend') : t('已更新', 'Updated'));
          await A.reload();
        } finally { el.disabled = false; }
      };
      if (action === 'schedule-delete' || action === 'schedule-cancel') askConfirm(t('确认删除任务或取消这次执行？已经发生的外部操作不会撤回。', 'Delete this task or cancel this execution? Completed external actions remain.'), () => perform().catch(reportError));
      else perform().catch(reportError);
    } });
})();
