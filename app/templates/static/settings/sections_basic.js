/* ═══════════════════════════════════════════════════════════════════════
   设置中心 · 分区（一）：常规 / 模型 / 技能
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  const A = window.MyAgentSettings;
  const { t, esc, api, W, icon, toast, reportError, askConfirm, openDialog, dialogValue, reload } = A;

  const LS = {
    theme: 'myagent-theme', font: 'myagent-font-level', list: 'myagent-session-list-mode',
    groupby: 'myagent-session-group-by',
    perm: 'myagent-new-session-permission-mode', model: 'myagent-new-session-model-profile',
  };
  const readLS = (key, fallback) => {
    try { const v = localStorage.getItem(key); return v === null ? fallback : v; } catch (e) { return fallback; }
  };
  const writeLS = (key, value) => { try { localStorage.setItem(key, value); } catch (e) { /* ignore */ } };

  const themeValue = () => {
    const raw = readLS(LS.theme, 'light');
    return raw === 'deep-dark' ? 'dark' : (raw === 'purple' || raw === 'dark') ? 'purple' : 'light';
  };
  const applyUiPrefs = () => {
    const root = document.documentElement;
    const theme = themeValue();
    root.classList.remove('theme-light', 'theme-dark', 'theme-purple');
    root.classList.add(theme === 'dark' ? 'theme-dark' : theme === 'purple' ? 'theme-purple' : 'theme-light');
    A.applyStFontSize(A.storedFontPx());
  };

  /* ── 字号：px 为准，同时维护旧的 0/1/2 档位键（老读者不受影响）────────── */
  const levelForPx = (px) => {
    const hit = A.FONT_LEVEL_PX.indexOf(px);
    if (hit >= 0) return hit;
    return px <= 15 ? 0 : (px <= 16 ? 1 : 2);
  };
  const updateStepperLimits = (px) => {
    const each = (sel, fn) => Array.prototype.forEach.call(document.querySelectorAll(sel), fn);
    each('[data-act="font-up"]', (b) => { b.disabled = px >= A.FONT_MAX; });
    each('[data-act="font-down"]', (b) => { b.disabled = px <= A.FONT_MIN; });
  };
  const setFontSize = (px) => {
    const next = A.clampFont(Math.round(px));
    A.setPrefs({ fontPx: String(next), font: String(levelForPx(next)) });
    A.applyStFontSize(next);
    const input = document.querySelector('[data-act="font-size-input"]');
    if (input && input.value !== String(next)) input.value = String(next);
    updateStepperLimits(next);
    return next;
  };

  /* ── 常规 ───────────────────────────────────────────────────────────── */
  A.registerSection({
    id: 'general', icon: 'general', zh: '常规', en: 'General', mode: 'instant',
    zhSub: '界面和两个常用默认值，改完立即生效。', enSub: 'Appearance and everyday defaults. Applied instantly.',
    async load() {
      const [modelResult, permissionResult] = await Promise.allSettled([api('/api/model_profiles'), api('/api/security/permissions')]);
      const profiles = modelResult.status === 'fulfilled' ? modelResult.value.profiles || [] : [];
      const defaultPermission = permissionResult.status === 'fulfilled' ? permissionResult.value.mode || 'ask_for_approval' : 'ask_for_approval';
      return {
        profiles,
        theme: themeValue(),
        fontPx: A.storedFontPx(),
        list: readLS(LS.list, 'detailed') === 'compact' ? 'compact' : 'detailed',
        groupby: readLS(LS.groupby, 'time') === 'workdir' ? 'workdir' : 'time',
        lang: A.lang,
        perm: readLS(LS.perm, '') || defaultPermission,
        model: readLS(LS.model, ''),
      };
    },
    render(d) {
      const themeOpts = [
        { v: 'light', t: t('浅色', 'Light') },
        { v: 'purple', t: t('紫色', 'Purple') },
        { v: 'dark', t: t('深色', 'Dark') },
      ];
      const permLabel = Object.fromEntries(A.permissionOptions().map((option) => [option.v, option.t]));
      const profileOptions = d.profiles.map((p) => '<option value="' + esc(p.id) + '"' + (d.model === p.id ? ' selected' : '') + '>' +
        esc(p.name || p.model) + '</option>').join('');
      return W.card(t('界面', 'Interface'), t('与聊天页共享', 'Shared with chat'),
        W.row(t('界面风格', 'Theme'), '', W.seg('theme', d.theme, themeOpts)) +
        W.row(t('字号', 'Font size'),
          t(A.FONT_MIN + '–' + A.FONT_MAX + ' px，可直接输入数字，或点右侧箭头逐级调',
            'Type a value (' + A.FONT_MIN + '–' + A.FONT_MAX + ' px) or use the arrows'),
          W.fontStepper(d.fontPx)) +
        W.row(t('会话列表', 'Session list'), '', W.seg('list', d.list, [{ v: 'compact', t: t('紧凑', 'Compact') }, { v: 'detailed', t: t('详细', 'Detailed') }])) +
        W.row(t('会话分组', 'Session grouping'), '', W.seg('groupby', d.groupby, [{ v: 'time', t: t('按时间', 'By time') }, { v: 'workdir', t: t('按工作目录', 'By workspace folder') }])) +
        W.row(t('语言', 'Language'), '', W.seg('lang', d.lang, [{ v: 'zh', t: '中文' }, { v: 'en', t: 'English' }]))) +
        W.card(t('新会话默认', 'New-session defaults'), t('只影响以后新建的会话', 'New sessions only'),
          W.row(t('权限模式', 'Permission mode'),
            d.perm ? permLabel[d.perm] || d.perm : t('跟随聊天页设置', 'Follows the chat page'),
            W.seg('perm', d.perm || 'ask_for_approval', A.permissionOptions()), 'lg') +
          W.row(t('模型档案', 'Model profile'), t('列表第一项为默认', 'First item is the default'),
            '<select class="st-input" data-act="select" data-key="model" style="width:192px">' +
            '<option value="">' + t('跟随列表第一项', 'Follow first item') + '</option>' + profileOptions + '</select>')) +
        W.note(t('权限模式的详细含义见「安全与权限」。', 'See Security for what each mode means.'));
    },
    onSeg(key, value) {
      if (key === 'lang') {
        const next = value === 'en' ? 'en' : 'zh';
        A.setPref('lang', next === 'en' ? 'en' : 'zh-CN');   /* 宿主聊天页同步切语言 */
        setTimeout(() => window.location.reload(), 50);      /* 先让偏好消息发出去，再重载本页以重刷文案 */
        return;
      }
      if (key === 'theme') {
        A.setPref('theme', value === 'dark' ? 'deep-dark' : value === 'purple' ? 'purple' : 'light');
        applyUiPrefs();
        toast(t('主题已切换', 'Theme switched'));
        reload();
        return;
      }
      if (key === 'list') { A.setPref('list', value === 'compact' ? 'compact' : 'detailed'); toast(t('会话列表已切换', 'Session list updated')); reload(); return; }
      if (key === 'groupby') { A.setPref('groupby', value === 'workdir' ? 'workdir' : 'time'); toast(t('会话分组已切换', 'Session grouping updated')); reload(); return; }
      if (key === 'perm') { writeLS(LS.perm, value); A.notifyHostPrefs(); toast(t('新会话默认权限已保存', 'Default permission saved')); reload(); return; }
    },
    /* 边输边生效：空串先不动，等离焦 / 回车时由 after() 里的 commit 规范化 */
    onFontInput(raw) {
      const n = parseInt(raw, 10);
      if (isNaN(n)) return;
      setFontSize(n);
    },
    onAction(act, el) {
      if (act === 'font-up') { toast(t('字号：', 'Font size: ') + setFontSize(A.storedFontPx() + 1) + ' px'); return; }
      if (act === 'font-down') { toast(t('字号：', 'Font size: ') + setFontSize(A.storedFontPx() - 1) + ' px'); return; }
      if (act !== 'select') return;
      if (el.dataset.key === 'model') {
        if (el.value) writeLS(LS.model, el.value); else { try { localStorage.removeItem(LS.model); } catch (e) { /* ignore */ } }
        toast(t('默认模型已保存', 'Default model saved'));
      }
    },
    after(root) {
      const input = root.querySelector('[data-act="font-size-input"]');
      if (!input) return;
      let last = A.storedFontPx();
      updateStepperLimits(last);
      const commit = () => {
        const raw = String(input.value || '').trim();
        if (raw === '') { input.value = String(last); return; }   /* 清空就退回上一个有效值 */
        const next = setFontSize(parseInt(raw, 10));
        if (next !== last) { last = next; toast(t('字号：', 'Font size: ') + next + ' px'); }
      };
      input.addEventListener('blur', commit);
      input.addEventListener('change', commit);
      input.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter') { ev.preventDefault(); commit(); input.blur(); }
      });
    },
  });

  /* ── 模型 ───────────────────────────────────────────────────────────── */
  const LLM_TYPES = ['auto', 'openai-compatible', 'openai-responses', 'anthropic'];
  const REASONING_EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max'];

  function modelField(label, hint, control, required) {
    const status = required ? 'required' : 'optional';
    return W.row(esc(label) + ' <span class="st-field-status ' + status + '" data-field-status="' + status + '">' +
      (required ? t('必填', 'Required') : t('选填', 'Optional')) + '</span>', hint, control);
  }

  function modelJson(field, label) {
    const text = dialogValue(field);
    let value;
    try { value = JSON.parse(text || '{}'); }
    catch (error) { throw new Error(label + t('必须是有效 JSON', ' must be valid JSON')); }
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      throw new Error(label + t('必须是 JSON 对象', ' must be a JSON object'));
    }
    return value;
  }

  function modelDialog(profile) {
    const p = profile || {};
    const isNew = !profile;
    const selectedEffort = REASONING_EFFORTS.includes(p.reasoning_effort) ? p.reasoning_effort : 'high';
    let capabilityAutomatic = p.capability_source !== 'manual';
    const capabilityText = A.lang === 'en' && p.capability_description_en
      ? p.capability_description_en : p.capability_description || '';
    openDialog({
      title: isNew ? t('添加模型', 'Add model') : t('编辑模型', 'Edit model') + ' · ' + (p.name || p.model),
      sub: isNew
        ? t('API 地址、密钥和模型名称必填；其他选填，可保持默认。', 'Endpoint, API key and model name are required; other fields are optional.')
        : t('API 地址和模型名称必填；已配置的密钥可留空保留。其他字段按标识填写。', 'Endpoint and model name are required; leave a configured key empty to keep it.'),
      okText: t('保存', 'Save'),
      body:
        modelField(t('API 地址', 'API base URL'), t('模型服务的接口地址', 'Model service endpoint'),
          '<input class="st-input" data-field="base_url" value="' + esc(p.base_url || '') + '" placeholder="https://api.openai.com/v1">', true) +
        modelField('API Key', p.api_key_set ? t('已配置，留空表示不修改', 'Configured — leave empty to keep') : t('密钥只写，保存后不再回显', 'Write-only'),
          '<input class="st-input" type="password" data-field="api_key" placeholder="' + (p.api_key_set ? '••••••' : 'sk-…') + '">', !p.api_key_set) +
        modelField(t('模型名称', 'Model name'), t('实际发送给接口的 model', 'Sent as the "model" field'),
          '<input class="st-input" data-field="model" value="' + esc(p.model || '') + '" placeholder="gpt-5-codex">' +
          W.btn(t('从接口获取', 'Fetch'), 'model-fetch'), true) +
        W.adv(t('高级设置', 'Advanced'),
          modelField(t('方案名称', 'Profile name'), t('留空使用模型名称', 'Defaults to model name'), '<input class="st-input" data-field="name" value="' + esc(p.name || '') + '">') +
          modelField(t('API 类型', 'API type'), '', '<select class="st-input" data-field="llm_type">' +
            LLM_TYPES.map((v) => '<option value="' + v + '"' + ((p.llm_type || 'auto') === v ? ' selected' : '') + '>' + v + '</option>').join('') +
            '</select>') +
          modelField(t('模型总窗口', 'Model window limit'), '', '<input class="st-input" data-field="model_context_window" value="' + esc(p.model_context_window || '') + '">' +
            W.btn(t('探测窗口', 'Probe limit'), 'model-probe')) +
          modelField(t('上下文长度（压缩阈值）', 'Context length (compaction threshold)'), t('达到此长度时压缩上下文；留空保留现有值或使用默认值', 'Compact at this length; keep existing value or default when empty'), '<input class="st-input" data-field="context_window" value="' + esc(p.context_window || '') + '" placeholder="400000">') +
          modelField(t('输出上限', 'Max output'), '', '<input class="st-input" data-field="max_output_tokens" value="' + esc(p.max_output_tokens || '') + '" placeholder="128000">') +
          modelField(t('温度', 'Temperature'), '', '<input class="st-input" data-field="temperature" value="' + esc(p.temperature == null ? '' : p.temperature) + '" placeholder="0.7">') +
          modelField(t('推理强度', 'Reasoning effort'), t('默认开启思考；强度取决于模型支持', 'Thinking is enabled by default; supported effort varies by model'),
            '<select class="st-input" data-field="reasoning_effort">' + REASONING_EFFORTS.map((value) => '<option value="' + value + '"' +
              (selectedEffort === value ? ' selected' : '') + '>' + value + '</option>').join('') + '</select>') +
          modelField('Responses ' + t('隐私', 'privacy'), t('禁止服务端存储，固定发送 store=false', 'Disable server storage (store=false)'),
            '<input type="checkbox" data-field="responses_store_disabled"' + (p.responses_store_disabled ? ' checked' : '') + '>') +
          modelField('System prompt', '', '<select class="st-input" data-field="system_prompt_mode">' +
            ['auto', 'merge', 'preserve'].map((v) => '<option value="' + v + '"' + ((p.system_prompt_mode || 'auto') === v ? ' selected' : '') + '>' + v + '</option>').join('') + '</select>') +
          modelField(t('多模态', 'Multimodal'), t('auto 按模型表识别；enabled 手动指定；disabled 关闭', 'Auto: model table; enabled: manual; disabled: off'),
            '<select class="st-input" data-field="multimodal_mode">' + ['auto', 'enabled', 'disabled'].map((v) => '<option value="' + v + '"' +
              ((p.multimodal_mode || 'auto') === v ? ' selected' : '') + '>' + v + '</option>').join('') + '</select>') +
          modelField(t('输入类型', 'Input modalities'), '', ['text', 'image', 'audio', 'video', 'file'].map((v) =>
            '<label><input type="checkbox" data-input-modality="' + v + '"' +
            ((p.configured_input_modalities || ['text']).indexOf(v) >= 0 ? ' checked' : '') + '> ' + v + '</label>').join(' ')) +
          modelField(t('能力说明', 'Capabilities'), t('自动生成内容已填入；可修改或恢复自动', 'Automatic description is shown; edit it or restore automatic mode'),
            '<div class="st-model-field-stack"><textarea class="st-input" data-field="capability_description" placeholder="' +
            t('模型表暂无能力信息，可自行填写', 'No model-table metadata; enter a description') + '">' + esc(capabilityText) + '</textarea>' +
            W.btn(t('恢复自动', 'Restore automatic'), 'model-capability-auto', 'sm text') + '</div>') +
          modelField(t('额外请求头 JSON', 'Extra headers JSON'), t('JSON 对象；留空或 {} 表示不添加请求头', 'JSON object; empty or {} adds no custom headers'),
            '<textarea class="st-input st-mono" data-field="headers_json" spellcheck="false">' + esc(JSON.stringify(p.headers || {}, null, 2)) + '</textarea>') +
          modelField(t('额外请求体 JSON', 'Extra body JSON'), t('JSON 对象；用于接口额外参数', 'JSON object for additional request parameters'),
            '<textarea class="st-input st-mono" data-field="extra_body_json" spellcheck="false">' + esc(p.extra_body_json || '{}') + '</textarea>')) +
        '<div data-model-probe-status role="status"></div>',
      onOk: async () => {
        const model = dialogValue('model');
        const baseUrl = dialogValue('base_url');
        if (!model) { toast(t('请填写模型名称', 'Model name is required'), true); return true; }
        if (!baseUrl) { toast(t('请填写 API 地址', 'API base URL is required'), true); return true; }
        const payload = { model, base_url: baseUrl, id: p.id, name: dialogValue('name') || model, llm_type: dialogValue('llm_type') || 'auto' };
        const key = dialogValue('api_key');
        if (!key && !p.api_key_set) { toast(t('请填写 API Key', 'API key is required'), true); return true; }
        if (key) payload.api_key = key;
        const cw = dialogValue('context_window'); if (cw) payload.context_window = Number(cw);
        const mo = dialogValue('max_output_tokens'); if (mo) payload.max_output_tokens = Number(mo);
        const windowLimit = dialogValue('model_context_window'); if (windowLimit) payload.model_context_window = Number(windowLimit);
        const temp = dialogValue('temperature'); payload.temperature = temp === '' ? '' : Number(temp);
        payload.thinking_mode = 'enabled';
        payload.reasoning_effort = dialogValue('reasoning_effort');
        payload.system_prompt_mode = dialogValue('system_prompt_mode');
        payload.multimodal_mode = dialogValue('multimodal_mode');
        payload.input_modalities = Array.from(document.querySelectorAll('#st-dlg-body [data-input-modality]:checked')).map((el) => el.dataset.inputModality);
        payload.capability_description = dialogValue('capability_description');
        if (capabilityAutomatic) payload.capability_description = '';
        payload.headers = modelJson('headers_json', t('额外请求头', 'Extra headers'));
        const extraBody = modelJson('extra_body_json', t('额外请求体', 'Extra body'));
        payload.extra_body_json = Object.keys(extraBody).length ? dialogValue('extra_body_json') : '';
        payload.responses_store_disabled = document.querySelector('#st-dlg-body [data-field="responses_store_disabled"]').checked;
        await api('/api/model_profiles', { method: 'POST', body: payload });
        toast(t('已保存并生效', 'Saved'));
        reload();
      },
      onSeg: () => false,
    });
    const body = document.getElementById('st-dlg-body');
    body.querySelectorAll('.st-row').forEach((row, index) => {
      const label = row.querySelector('.st-label');
      label.id = 'st-model-label-' + index;
      const required = !!row.querySelector('[data-field-status="required"]');
      row.querySelectorAll('[data-field]').forEach((field) => {
        field.setAttribute('aria-labelledby', label.id);
        field.required = required;
        field.setAttribute('aria-required', String(required));
      });
    });
    const capability = body.querySelector('[data-field="capability_description"]');
    let capabilityEpoch = 0, capabilityTimer = null;
    capability.addEventListener('input', () => { capabilityAutomatic = false; capabilityEpoch++; });
    const updateCapability = async () => {
      if (!capabilityAutomatic) return;
      const epoch = ++capabilityEpoch;
      try {
        const response = await api('/api/model_profiles/capabilities', { method: 'POST', body: {
          model: dialogValue('model'), name: dialogValue('name'), context_window: Number(dialogValue('context_window')) || 0,
        } });
        if (epoch !== capabilityEpoch || !capabilityAutomatic || !capability.isConnected) return;
        const data = response.capabilities || {};
        capability.value = (A.lang === 'en' ? data.capability_description_en : data.capability_description) || '';
      } catch (error) { if (epoch === capabilityEpoch && capability.isConnected) reportError(error); }
    };
    ['model', 'name', 'context_window'].forEach((field) => {
      body.querySelector('[data-field="' + field + '"]').addEventListener('input', () => {
        capabilityEpoch++;
        clearTimeout(capabilityTimer);
        capabilityTimer = setTimeout(updateCapability, 200);
      });
    });
    body.querySelector('[data-act="model-capability-auto"]').addEventListener('click', () => {
      capabilityAutomatic = true;
      clearTimeout(capabilityTimer);
      updateCapability();
    });
    const probeBtn = body && body.querySelector('[data-act="model-probe"]');
    if (probeBtn) probeBtn.addEventListener('click', async () => {
      const status = body.querySelector('[data-model-probe-status]');
      probeBtn.disabled = true;
      status.textContent = t('正在探测…', 'Probing…');
      try {
        const response = await api('/api/model_profiles/probe', { method: 'POST', body: {
          base_url: dialogValue('base_url'), api_key: dialogValue('api_key'), model: dialogValue('model'),
          llm_type: dialogValue('llm_type'), model_context_window: dialogValue('model_context_window'),
        } });
        const result = response.model || {};
        const limit = body.querySelector('[data-field="model_context_window"]');
        if (result.model_context_window || result.context_window) {
          limit.value = String(result.model_context_window || result.context_window);
          limit.dataset.autoValue = limit.value;
        }
        const detail = String(result.probe_error || '').trim();
        status.textContent = detail ? t('上下文探测失败，已使用列表/默认窗口：', 'Context probe failed; using listed/default window: ') + detail
          : result.probe_attempted === false ? t('已读取列表/默认窗口；填写密钥后可探测接口。', 'Using listed/default limits; provide a key to probe the endpoint.')
            : t('探测完成', 'Probe completed');
      } catch (error) { status.textContent = String(error.message || error); }
      finally { probeBtn.disabled = false; }
    });
    const fetchBtn = body && body.querySelector('[data-act="model-fetch"]');
    if (fetchBtn) {
      fetchBtn.addEventListener('click', async () => {
        const baseUrl = dialogValue('base_url');
        const keyInput = body.querySelector('[data-field="api_key"]');
        const key = keyInput ? keyInput.value.trim() : '';
        if (!baseUrl) { toast(t('请先填写 API 地址', 'Fill the API base URL first'), true); return; }
        fetchBtn.disabled = true;
        fetchBtn.textContent = t('获取中…', 'Fetching…');
        try {
          const res = await api('/api/model_profiles/discover', { method: 'POST', body: { base_url: baseUrl, api_key: key } });
          const models = res.models || [];
          if (!models.length) { toast(t('接口没有返回模型', 'No models returned'), true); return; }
          const listId = 'model-datalist';
          let list = document.getElementById(listId);
          if (!list) {
            list = document.createElement('datalist');
            list.id = listId;
            body.appendChild(list);
          }
          list.innerHTML = models.map((m) => '<option value="' + esc(m.id) + '">' + esc(m.id) +
            (m.context_window ? ' · ' + m.context_window + ' ctx' : '') + '</option>').join('');
          const input = body.querySelector('[data-field="model"]');
          if (input) { input.setAttribute('list', listId); input.focus(); }
          toast(t('已获取 ', 'Fetched ') + models.length + t(' 个模型，点模型名可自动补全', ' models — pick one from the list'));
        } catch (err) { reportError(err); } finally {
          fetchBtn.disabled = false;
          fetchBtn.textContent = t('从接口获取', 'Fetch');
        }
      });
    }
  }

  /* ── 模型档案排序：拖手柄 / ↑↓ 键（旧「高级设置」页的 drag-drop 平移过来）───── */
  const GRIP_SVG = '<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">' +
    '<circle cx="6" cy="4" r="1.25"/><circle cx="10" cy="4" r="1.25"/>' +
    '<circle cx="6" cy="8" r="1.25"/><circle cx="10" cy="8" r="1.25"/>' +
    '<circle cx="6" cy="12" r="1.25"/><circle cx="10" cy="12" r="1.25"/></svg>';
  let profileDrag = null;
  const profileAnimations = new WeakMap();

  function animateProfileRows(rows, before) {
    const after = new Map(rows.map((row) => [row, row.getBoundingClientRect()]));
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    rows.forEach((row) => {
      const prev = before.get(row);
      if (!prev) return;
      const dy = prev.top - after.get(row).top;
      if (!dy) return;
      profileAnimations.set(row, row.animate([
        { transform: 'translateY(' + dy + 'px)' }, { transform: 'none' },
      ], { duration: 160, easing: 'cubic-bezier(.2,.8,.2,1)' }));
    });
  }

  function wireProfileReorder(root, d) {
    const list = root.querySelector('[data-profile-list]');
    if (!list) return;
    const rows = () => Array.from(list.children);
    const domIds = () => rows().map((row) => row.dataset.profileId);
    let savedIds = domIds(), pendingIds = null, saving = false, saveTimer = null;
    let dragFrame = null, dragY = 0;
    const syncOrder = () => {
      const byId = new Map((d.profiles || []).map((profile) => [String(profile.id), profile]));
      d.profiles = domIds().map((id, index) => {
        const profile = byId.get(id);
        if (profile) profile.priority = index + 1;
        return profile;
      }).filter(Boolean);
      if (list.isConnected) window.__lastProfiles = d.profiles;
      rows().forEach((row, index) => { row.querySelector('[data-profile-default]').hidden = index !== 0; });
    };
    const restore = (ids = savedIds) => {
      const all = rows();
      const before = new Map(all.map((row) => [row, row.getBoundingClientRect()]));
      all.forEach((row) => { const animation = profileAnimations.get(row); if (animation) animation.cancel(); });
      const byId = new Map(all.map((row) => [row.dataset.profileId, row]));
      ids.forEach((id) => { if (byId.has(id)) list.appendChild(byId.get(id)); });
      animateProfileRows(all, before);
      syncOrder();
    };
    const savePending = async () => {
      if (saving || !pendingIds) return;
      const ids = pendingIds;
      pendingIds = null;
      if (JSON.stringify(ids) === JSON.stringify(savedIds)) return;
      saving = true;
      list.setAttribute('aria-busy', 'true');
      try {
        await api('/api/model_profiles/reorder', { method: 'POST', body: { ordered_ids: ids } });
        savedIds = ids;
        if (!pendingIds && list.isConnected) toast(t('顺序已保存', 'Order saved'));
      } catch (error) {
        pendingIds = null;
        restore();
        if (list.isConnected) reportError(error);
      } finally {
        saving = false;
        list.removeAttribute('aria-busy');
        if (pendingIds) savePending();
      }
    };
    const persist = (ids) => {
      pendingIds = ids;
      clearTimeout(saveTimer);
      saveTimer = setTimeout(savePending, 120);
    };
    const moveRow = (row, target, after) => {
      if (row === target || (after ? row.previousElementSibling === target : row.nextElementSibling === target)) return;
      const all = rows();
      const before = new Map(all.map((r) => [r, r.getBoundingClientRect()]));
      all.forEach((r) => { const animation = profileAnimations.get(r); if (animation) animation.cancel(); });
      if (after) list.insertBefore(row, target.nextSibling);
      else list.insertBefore(row, target);
      animateProfileRows(all, before);
      syncOrder();
    };
    const moveDraggedRow = () => {
      dragFrame = null;
      if (!profileDrag || profileDrag.row.parentNode !== list) return;
      const others = rows().filter((row) => row !== profileDrag.row);
      const top = list.getBoundingClientRect().top + list.clientTop;
      const target = others.find((row) => dragY < top + row.offsetTop + row.offsetHeight / 2);
      if (target) moveRow(profileDrag.row, target, false);
      else if (others.length) moveRow(profileDrag.row, others[others.length - 1], true);
    };

    rows().forEach((row) => {
      const handle = row.querySelector('.st-drag-handle');
      if (!handle) return;
      handle.draggable = true;
      handle.addEventListener('dragstart', (ev) => {
        profileDrag = { row, dropped: false, beforeIds: domIds() };
        row.classList.add('is-dragging');
        if (!ev.dataTransfer) return;
        ev.dataTransfer.effectAllowed = 'move';
        try { ev.dataTransfer.setData('text/plain', row.dataset.profileId || ''); } catch (e) { /* ignore */ }
        if (!ev.dataTransfer.setDragImage) return;
        const rect = row.getBoundingClientRect();
        const ox = Math.max(0, Math.min(rect.width, (ev.clientX || rect.left) - rect.left));
        const oy = Math.max(0, Math.min(rect.height, (ev.clientY || rect.top) - rect.top));
        try { ev.dataTransfer.setDragImage(row, ox, oy); } catch (e) { /* ignore */ }
      });
      handle.addEventListener('dragend', () => {
        const state = profileDrag;
        if (dragFrame !== null) cancelAnimationFrame(dragFrame);
        dragFrame = null;
        profileDrag = null;
        if (!state) return;
        state.row.classList.remove('is-dragging');
        if (!state.dropped) { restore(state.beforeIds); return; }
        const ids = domIds();
        if (JSON.stringify(ids) !== JSON.stringify(state.beforeIds)) persist(ids);
      });
      handle.addEventListener('keydown', (ev) => {
        const up = ev.key === 'ArrowUp';
        const down = ev.key === 'ArrowDown';
        if (!up && !down) return;
        ev.preventDefault();
        const all = rows();
        const index = all.indexOf(row);
        const target = up ? index - 1 : index + 1;
        if (index < 0 || target < 0 || target >= all.length) return;
        moveRow(row, all[target], !up);
        handle.focus({ preventScroll: true });
        const ids = domIds();
        persist(ids);
      });
    });

    list.addEventListener('dragover', (ev) => {
      if (!profileDrag || profileDrag.row.parentNode !== list) return;
      ev.preventDefault();
      if (ev.dataTransfer) ev.dataTransfer.dropEffect = 'move';
      dragY = ev.clientY;
      if (dragFrame === null) dragFrame = requestAnimationFrame(moveDraggedRow);
    });
    list.addEventListener('drop', (ev) => {
      if (!profileDrag || profileDrag.row.parentNode !== list) return;
      ev.preventDefault();
      if (dragFrame !== null) { cancelAnimationFrame(dragFrame); moveDraggedRow(); }
      profileDrag.dropped = true;
    });
  }

  A.registerSection({
    id: 'models', icon: 'model', zh: '模型', en: 'Models', mode: 'instant',
    zhSub: '点开关可临时停用；列表第一项是新会话默认。', enSub: 'Toggle to disable; the first row is the default.',
    async load() { return api('/api/model_profiles'); },
    render(d) {
      const profiles = d.profiles || [];
      const rows = profiles.map((p, i) =>
        '<div class="st-lrow st-profile-row" data-profile-id="' + esc(p.id) + '">' +
          '<button type="button" class="st-drag-handle" aria-label="' + esc(t('拖动排序', 'Drag to reorder')) +
            '" title="' + esc(t('拖动调整顺序，或选中后按 ↑ / ↓', 'Drag to reorder, or focus and press ↑ / ↓')) + '">' +
            GRIP_SVG + '</button>' +
          '<div class="st-li-main">' +
            '<div class="st-li-t">' + esc(p.name || p.model) + '<span data-profile-default' + (i === 0 ? '' : ' hidden') + '>' + W.chip(t('默认', 'Default')) + '</span>' +
              (p.enabled === false ? ' ' + W.chip(t('已停用', 'Off')) : '') + '</div>' +
            '<div class="st-li-s">model <span class="st-mono">' + esc(p.model) + '</span>' +
              (p.context_window ? ' · ctx ' + p.context_window : '') +
              (p.max_output_tokens ? ' · out ' + p.max_output_tokens : '') +
              (p.base_url ? ' · ' + esc(p.base_url) : '') + '</div>' +
          '</div>' +
          '<div class="st-li-act">' +
            W.sw('profile:' + p.id, p.enabled !== false) +
            '<button type="button" class="st-btn sm text" data-act="model-edit" data-id="' + esc(p.id) + '">' + t('编辑', 'Edit') + '</button>' +
            '<button type="button" class="st-btn sm text danger" data-act="model-del" data-id="' + esc(p.id) + '" data-name="' + esc(p.name || p.model) + '">' + t('删除', 'Delete') + '</button>' +
          '</div>' +
        '</div>').join('');
      return W.card(t('模型档案', 'Model profiles'), t('越靠上优先级越高，可拖动排序', 'Higher rows win — drag to reorder'),
        (rows ? '<div class="st-profile-list" data-profile-list>' + rows + '</div>' : '') ||
          W.empty(t('还没有模型，点「添加模型」开始。', 'No models yet — click Add model.')),
        W.btn(t('添加模型', 'Add model'), 'model-add', 'primary')) +
        W.note(t('模型档案保存在 <span class="st-mono">.sugaragent/model_profiles.json</span>；密钥只写不回显。' +
          '拖左侧手柄调整优先级，也可以选中手柄后按 <span class="st-mono">↑</span> / <span class="st-mono">↓</span>。',
          'Profiles live in <span class="st-mono">.sugaragent/model_profiles.json</span>; keys are write-only. ' +
          'Drag the handle — or focus it and press <span class="st-mono">↑</span> / <span class="st-mono">↓</span> — to change priority.'));
    },
    onToggle(key, on) {
      if (key.indexOf('profile:') !== 0) return;
      const id = key.slice('profile:'.length);
      api('/api/model_profiles/' + encodeURIComponent(id) + '/enabled', { method: 'POST', body: { enabled: on } })
        .then(() => toast(on ? t('已启用', 'Enabled') : t('已停用', 'Disabled')))
        .catch((err) => { reportError(err); reload(); });
    },
    onAction(act, el) {
      if (act === 'model-add') { modelDialog(null); return; }
      if (act === 'model-edit') {
        const profiles = window.__lastProfiles || [];
        const target = profiles.filter((p) => p.id === el.dataset.id)[0];
        modelDialog(target || { id: el.dataset.id });
        return;
      }
      if (act === 'model-del') {
        const name = el.dataset.name;
        askConfirm(t('删除模型档案「', 'Delete profile "') + name + t('」？', '"?' ), () => {
          api('/api/model_profiles/' + encodeURIComponent(el.dataset.id), { method: 'DELETE' })
            .then(() => { toast(t('已删除', 'Deleted')); reload(); })
            .catch(reportError);
        });
      }
    },
    after(root, d) {
      window.__lastProfiles = (d && d.profiles) || [];
      wireProfileReorder(root, d);
    },
  });

  /* ── 技能 ───────────────────────────────────────────────────────────── */
  function skillDialog() {
    let source = 'dir';
    const build = () => (
      W.row(t('安装来源', 'Source'), '', W.seg('skillSrc', source, [
        { v: 'dir', t: t('本地目录', 'Folder') },
        { v: 'zip', t: t('压缩包', 'Archive') },
        { v: 'git', t: t('Git 地址', 'Git URL') },
      ])) +
      W.row(source === 'git' ? t('仓库地址', 'Repository') : t('路径', 'Path'),
        t('技能文件夹里需要有 SKILL.md', 'The folder must contain SKILL.md'),
        '<div class="st-package-source" data-package-kind="skills"><input class="st-input" data-field="source"' +
          (source === 'git' ? '' : ' data-path-kind="' + (source === 'zip' ? 'file' : 'directory') + '"') + ' placeholder="' +
          (source === 'git' ? 'https://github.com/…/my-skill.git' : source === 'zip' ? 'D:\\downloads\\my-skill.zip' : 'D:\\skills\\my-skill') + '">' +
          '<span class="st-muted st-package-hint">' + t('也可将技能目录或压缩包拖到这里直接安装', 'Drop a skill folder or archive here to install') + '</span></div>') +
      '<div class="st-divider"><span>' + t('或', 'or') + '</span></div>' +
      W.row(t('新建技能', 'Create new'), t('会在技能目录生成 SKILL.md 骨架', 'Creates a SKILL.md skeleton'),
        '<input class="st-input" data-field="name" placeholder="pdf-report">') +
      W.row(t('一句话描述', 'One-line description'), t('决定 Agent 什么时候用它', 'When the agent should use it'),
        '<input class="st-input" data-field="description" placeholder="' + t('读取 PDF 并生成摘要报告', 'Read PDFs and summarize') + '">')
    );
    openDialog({
      title: t('添加技能', 'Add skill'),
      sub: t('安装一个现成的技能，或者新建一个空技能。', 'Install an existing skill, or create an empty one.'),
      okText: t('添加', 'Add'),
      body: build(),
      onSeg(key, value) {
        if (key !== 'skillSrc') return false;
        const currentValue = dialogValue('source');
        source = value;
        const body = document.getElementById('st-dlg-body');
        body.innerHTML = build();
        const input = body.querySelector('[data-field="source"]');
        if (input) input.value = currentValue;
        A.enhancePaths(body);
        return true;
      },
      onOk: async () => {
        const name = dialogValue('name');
        const description = dialogValue('description');
        const src = dialogValue('source');
        if (name) {
          await api('/api/skills/create', { method: 'POST', body: { name, description } });
          toast(t('已新建技能', 'Skill created'));
          reload();
          return;
        }
        if (!src) { toast(t('请填写路径或技能名称', 'Provide a path or a skill name'), true); return true; }
        await api('/api/skills/install', { method: 'POST', body: { source: src, kind: source } });
        toast(t('已安装技能', 'Skill installed'));
        reload();
      },
    });
  }

  A.registerSection({
    id: 'skills', icon: 'skills', zh: '技能', en: 'Skills', mode: 'instant',
    zhSub: '开着就能用，关掉后 Agent 不再使用该技能。', enSub: 'Enabled skills are available to the agent.',
    async load() { return api('/api/skills'); },
    render(d) {
      const skills = d.skills || [];
      /* 说明不进列表：名字上挂浮框，悬停/聚焦才显示完整 description */
      const rows = skills.map((s) => W.lrow(W.tip(esc(s.name), s.description || '', 'st-mono'), '',
        (s.enabled === false ? W.chip(t('已停用', 'Off')) : W.chip(t('已启用', 'On'))) +
        W.sw('skill:' + s.name, s.enabled !== false), s.name + ' ' + (s.description || ''))).join('');
      return W.search(t('搜索技能', 'Search skills'), A.search) +
        W.card(t('已安装技能', 'Installed skills'),
          t('技能是带 SKILL.md 的文件夹 · 悬停技能名看说明', 'A skill is a folder with SKILL.md — hover a name for its description'),
          rows || W.empty(t('没有匹配的技能', 'No matching skill')),
          W.btn(t('添加技能', 'Add skill'), 'skill-add', 'primary')) +
        '<div data-search-empty hidden>' + W.empty(t('没有匹配的技能', 'No matching skill')) + '</div>' +
        W.note(t('每个技能必须含 <span class="st-mono">SKILL.md</span>，且 frontmatter 里要有 name 和 description，否则会被忽略。',
          'Each skill needs <span class="st-mono">SKILL.md</span> with name and description in its frontmatter.'));
    },
    onSearch() { A.filterSearchRows(); },
    onToggle(key, on) {
      if (key.indexOf('skill:') !== 0) return;
      const name = key.slice('skill:'.length);
      api('/api/skills/' + encodeURIComponent(name) + '/enabled', { method: 'POST', body: { enabled: on } })
        .then(() => toast(on ? t('已启用', 'Enabled') : t('已停用', 'Disabled')))
        .catch((err) => { reportError(err); reload(); });
    },
    onAction(act) {
      if (act === 'skill-add') skillDialog();
    },
  });
})();
