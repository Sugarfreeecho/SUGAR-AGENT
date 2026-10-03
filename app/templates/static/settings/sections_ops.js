/* ═══════════════════════════════════════════════════════════════════════
   设置中心 · 分区（三）：安全与权限 / 环境变量 / 目录与路径
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  const A = window.MyAgentSettings;
  const { t, esc, api, W, toast, reportError, askConfirm, reload } = A;
  const sessionId = (A.bootSection && A.bootSection.sessionId) || '';

  const ACTIONS = [
    ['process.exec', 'Shell 命令', 'Shell'],
    ['fs.read', '读取', 'Read'],
    ['fs.write', '写入', 'Write'],
    ['fs.delete', '删除', 'Delete'],
    ['network.connect', '网络', 'Network'],
    ['web.search', '联网搜索', 'Web search'],
    ['mcp.call', 'MCP', 'MCP'],
    ['plugin.call', '插件', 'Plugin'],
  ];
  const BEHAVIORS = [['allow', '总是允许', 'Always allow'], ['ask', '每次问我', 'Ask me'], ['deny', '禁止', 'Deny']];
  const behaviorLabel = (b) => {
    const hit = BEHAVIORS.filter((x) => x[0] === b)[0];
    return hit ? (A.lang === 'zh' ? hit[1] : hit[2]) : b;
  };
  const actionLabel = (a) => {
    const hit = ACTIONS.filter((x) => x[0] === a)[0];
    return hit ? (A.lang === 'zh' ? hit[1] : hit[2]) : a;
  };

  /* ── 安全与权限 ─────────────────────────────────────────────────────── */
  A.registerSection({
    id: 'security', icon: 'security', zh: '安全与权限', en: 'Security', mode: 'instant',
    zhSub: '决定 Agent 的哪些操作需要先问你；默认设置对多数人是安全的。',
    enSub: 'Controls which actions need your approval.',
    async load() {
      const out = {};
      const grab = async (key, path) => { try { out[key] = await api(path); } catch (e) { out[key] = null; } };
      await Promise.all([
        grab('perm', sessionId ? '/sessions/' + encodeURIComponent(sessionId) + '/permissions' : '/api/security/permissions'),
        grab('rules', '/api/security/rules?session_id=' + encodeURIComponent(sessionId)),
        grab('settings', '/api/security/settings'),
        grab('domains', '/api/security/web-fetch-domains'),
        grab('extensions', '/api/security/extensions'),
      ]);
      return out;
    },
    render(d) {
      const mode = (!sessionId && localStorage.getItem('myagent-new-session-permission-mode')) || (d.perm && d.perm.mode) || 'ask_for_approval';
      const settings = d.settings || {};
      const rules = (d.rules && d.rules.rules) || [];
      const ruleRows = rules.map((r) => W.lrow(
        behaviorLabel(r.behavior) + (r.enabled === false ? ' ' + W.chip(t('已停用', 'Off')) : ''),
        esc(actionLabel(r.action)) + ' · <span class="st-mono">' + esc(r.pattern) + '</span>' +
          (r.source ? ' · ' + esc(r.source) : ''),
        '<button type="button" class="st-btn sm text danger" data-act="rule-del" data-id="' + esc(r.id) + '">' + t('删除', 'Delete') + '</button>'
      )).join('');
      const extensions = (d.extensions && d.extensions.extensions) || [];
      const extRows = extensions.map((x) => W.lrow(
        esc(x.name || x.extension_id),
        esc(x.kind) + ' · ' + esc(x.registration_status || '') + (x.content_digest ? ' · <span class="st-mono">' + esc(String(x.content_digest).slice(0, 8)) + '</span>' : ''),
        (x.trusted ? W.status('ok', t('已信任', 'Trusted')) : W.status('warn', t('待确认', 'Pending'))) +
        (x.trusted
          ? '<button type="button" class="st-btn sm text danger" data-act="trust-revoke" data-kind="' + esc(x.kind) + '" data-id="' + esc(x.extension_id) + '">' + t('撤销', 'Revoke') + '</button>'
          : '<button type="button" class="st-btn sm primary" data-act="trust-set" data-kind="' + esc(x.kind) + '" data-id="' + esc(x.extension_id) + '">' + t('信任', 'Trust') + '</button>')
      )).join('');
      const modeRow = W.row(t('权限模式', 'Permission mode'),
        sessionId ? t('与聊天输入框的权限选项同步', 'Synced with the chat permission selector') : t('与常规页共享新会话默认值', 'Shared new-session default with General'),
        W.seg('mode', mode, A.permissionOptions()), 'lg');
      return W.card(t('权限模式', 'Permission mode'),
        sessionId ? t('会写入当前会话并广播到所有客户端', 'Applies to the current session and broadcasts')
          : t('新会话默认权限', 'Default permission for new sessions'),
        modeRow) +
        W.note(t('请求批准：写文件自动执行，删除 / 联网 / 出项目先问你。替我审批：低风险自动放行。完全访问：只有高危系统命令才确认。',
          'Ask: writes run; deletes/network ask. Auto: low risk runs. Full: only high-risk commands ask.')) +
        W.card(t('规则', 'Rules'), t('点聊天页「总是允许」后会自动沉淀到这里', 'Saved when you click Always allow'),
          (ruleRows || W.empty(t('还没有规则', 'No rules yet'))) +
          '<div class="st-row block"><div class="st-ctl">' +
          '<select class="st-input" data-field="rule-action" style="width:132px">' +
          ACTIONS.map((a) => '<option value="' + a[0] + '">' + esc(A.lang === 'zh' ? a[1] : a[2]) + '</option>').join('') + '</select>' +
          '<select class="st-input" data-field="rule-behavior" style="width:132px">' +
          BEHAVIORS.map((b) => '<option value="' + b[0] + '">' + esc(A.lang === 'zh' ? b[1] : b[2]) + '</option>').join('') + '</select>' +
          '<input class="st-input" data-field="rule-pattern" style="flex:1;min-width:180px" placeholder="git push:*  或  D:\\proj\\**">' +
          W.btn(t('添加规则', 'Add rule'), 'rule-add', 'primary') + '</div></div>',
          sessionId ? W.btn(t('清除本会话规则', 'Clear session rules'), 'rule-clear', 'danger') : '') +
        W.card(t('其它安全项', 'Other security'), '',
          W.row(t('低风险自动审查', 'Auto-review low risk'), t('让审查 Agent 先核对意图，减少打断', 'An agent pre-checks intent'),
            W.chip(t('立即生效', 'Instant')) + W.sw('sec:auto_review', !!settings.auto_review_enabled)) +
          W.row(t('工作区外操作自动放行', 'Allow out-of-workspace ops'), t('写 / 删 / Shell 不再逐次确认（风险较高）', 'No per-action approval (higher risk)'),
            W.sw('sec:external', !!settings.allow_external_workspace_ops)) +
          W.adv(t('网页抓取白名单', 'web_fetch allow-list'),
            W.row(t('免审批域名', 'Pre-approved domains'), t('仅影响只读网页抓取，每行一个', 'Read-only web_fetch, one per line'),
              '<textarea class="st-input" data-field="domains" style="min-height:92px">' +
              esc(((d.domains && d.domains.domains) || []).join('\n')) + '</textarea>' +
              W.btn(t('保存', 'Save'), 'wf-save', 'primary')))) +
        W.card(t('扩展信任', 'Extension trust'), t('MCP 与可执行插件的注册审批', 'Registration approval for MCP and plugins'),
          extRows || W.empty(t('没有扩展需要确认', 'Nothing to confirm')));
    },
    onSeg(key, value) {
      if (key !== 'mode') return;
      if (!sessionId) {
        localStorage.setItem('myagent-new-session-permission-mode', value);
        A.notifyHostPrefs();
        toast(t('新会话默认权限已保存', 'Default permission saved'));
        return;
      }
      api('/sessions/' + encodeURIComponent(sessionId) + '/permissions', { method: 'POST', body: { mode: value } })
        .then(() => { toast(t('已切换权限模式', 'Permission mode updated')); reload(); })
        .catch((err) => { reportError(err); reload(); });
    },
    onToggle(key, on) {
      const map = { 'sec:auto_review': 'auto_review_enabled', 'sec:external': 'allow_external_workspace_ops' };
      const field = map[key];
      if (!field) return;
      const body = {};
      body[field] = on;
      api('/api/security/settings', { method: 'POST', body })
        .then(() => toast(t('已保存', 'Saved')))
        .catch((err) => { reportError(err); reload(); });
    },
    onAction(act, el) {
      if (act === 'rule-add') {
        const action = (document.querySelector('[data-field="rule-action"]') || {}).value;
        const behavior = (document.querySelector('[data-field="rule-behavior"]') || {}).value;
        const pattern = ((document.querySelector('[data-field="rule-pattern"]') || {}).value || '').trim();
        if (!pattern) { toast(t('请填写规则内容', 'Pattern is required'), true); return; }
        api('/api/security/rules', { method: 'POST', body: { action, behavior, pattern, session_id: sessionId || undefined, source: 'user' } })
          .then(() => { toast(t('已添加规则', 'Rule added')); reload(); })
          .catch(reportError);
        return;
      }
      if (act === 'rule-del') {
        api('/api/security/rules/' + encodeURIComponent(el.dataset.id), { method: 'DELETE' })
          .then(() => { toast(t('已删除', 'Deleted')); reload(); })
          .catch(reportError);
        return;
      }
      if (act === 'rule-clear') {
        askConfirm(t('清除本会话产生的规则？', 'Clear rules created by this session?'), () => {
          api('/api/security/rules?session_id=' + encodeURIComponent(sessionId), { method: 'DELETE' })
            .then(() => { toast(t('已清除', 'Cleared')); reload(); })
            .catch(reportError);
        });
        return;
      }
      if (act === 'wf-save') {
        const area = document.querySelector('[data-field="domains"]');
        const domains = (area ? area.value : '').split(/[\n,]/).map((s) => s.trim()).filter(Boolean);
        api('/api/security/web-fetch-domains', { method: 'POST', body: { domains } })
          .then(() => { toast(t('已保存', 'Saved')); reload(); })
          .catch(reportError);
        return;
      }
      if (act === 'trust-set' || act === 'trust-revoke') {
        const method = act === 'trust-set' ? 'POST' : 'DELETE';
        api('/api/security/extensions/' + encodeURIComponent(el.dataset.kind) + '/' + encodeURIComponent(el.dataset.id) + '/trust', { method })
          .then(() => { toast(t('已更新信任状态', 'Trust updated')); reload(); })
          .catch(reportError);
      }
    },
  });

  /* ── 环境变量 ───────────────────────────────────────────────────────── */
  A.registerSection({
    id: 'env', icon: 'env', zh: '环境变量', en: 'Environment', mode: 'explicit',
    dirtyMessage: ['有未保存的更改 · 离开前会拦截', 'Unsaved changes — leaving will be intercepted'],
    zhSub: '进阶选项都在这里；不确定就保持默认，改完点右下「保存」。',
    enSub: 'Advanced options — keep defaults if unsure.',
    async load() { return api('/api/env'); },
    render(d) {
      const flat = [];
      (d.groups || []).forEach((g) => (g.vars || []).forEach((v) => { v.__group = g.title; flat.push(v); }));
      const groups = [];
      flat.forEach((v) => {
        let bucket = groups.filter((g) => g.title === v.__group)[0];
        if (!bucket) { bucket = { title: v.__group, vars: [] }; groups.push(bucket); }
        bucket.vars.push(v);
      });
      const cards = groups.map((g) => W.card(esc(g.title), '',
        g.vars.map((v) => {
          const overridden = !!v.has_value && v.value !== '';
          const hint = v.hint ? esc(String(v.hint).split('\n')[0]) : '';
          const control = v.sensitive
            ? '<input class="st-input" type="password" data-env-key="' + esc(v.key) + '" value="" placeholder="' +
              (overridden ? t('已配置 ••••', 'Configured ••••') : t('未配置', 'Not set')) + '">'
            : '<input class="st-input" data-env-key="' + esc(v.key) + '" value="' + esc(v.value || '') + '"' +
              (v.path_kind ? ' data-path-kind="' + esc(v.path_kind) + '"' : '') + '>';
          return W.row('<span class="st-mono">' + esc(v.key) + '</span>',
            hint || (overridden ? t('已覆盖默认值', 'Overridden') : t('使用默认值', 'Default')),
            control + '<button type="button" class="st-btn sm text" data-act="env-reset" data-key="' + esc(v.key) + '">' + t('恢复默认', 'Reset') + '</button>',
            '', v.key + ' ' + (v.hint || ''));
        }).join(''))).join('');
      return W.search(t('搜索变量名', 'Search variable'), A.search) +
        (cards || W.empty(t('没有匹配的变量', 'No matching variable'))) +
        '<div data-search-empty hidden>' + W.empty(t('没有匹配的变量', 'No matching variable')) + '</div>' +
        W.note(t('「恢复默认」会从 .env 里删除该键；带「选择」按钮的路径类变量可以直接浏览目录。',
          'Reset removes the key from .env; path variables get a browse button.'));
    },
    onSearch() { A.filterSearchRows(); },
    onAction(act, el) {
      if (act !== 'env-reset') return;
      const key = el.dataset.key;
      api('/api/env', { method: 'POST', body: { remove: [key] } })
        .then(() => { toast(t('已恢复默认：', 'Reset: ') + key); A.setDirty(false); reload(); })
        .catch(reportError);
    },
    async save(d) {
      /* 只提交真正改过的键：否则「点一次保存」会把整屏默认项写进 .env（含空行） */
      const snapshot = {};
      ((d && d.groups) || []).forEach((g) => (g.vars || []).forEach((v) => { snapshot[v.key] = v; }));
      const values = {};
      const remove = [];
      Array.prototype.forEach.call(document.querySelectorAll('[data-env-key]'), (el) => {
        const key = el.dataset.envKey;
        const raw = el.value;
        if (el.type === 'password') {         /* 密钥只写：留空 = 不改 */
          if (raw !== '') values[key] = raw;
          return;
        }
        const before = String((snapshot[key] || {}).value || '');
        if (raw === before) return;           /* 没动过 */
        if (raw === '') {                     /* 清空 = 恢复默认（从 .env 删除该键） */
          if (before !== '') remove.push(key);
          return;
        }
        values[key] = raw;
      });
      if (!Object.keys(values).length && !remove.length) return;
      const body = {};
      if (Object.keys(values).length) body.values = values;
      if (remove.length) body.remove = remove;
      const res = await api('/api/env', { method: 'POST', body });
      if (res && res.restart_required) toast(t('已保存；工作区变更需重启 Agent 生效', 'Saved — restart required for WORK_DIR'), true);
      if (typeof MyAgentPathPicker !== 'undefined' && MyAgentPathPicker.scan) {
        try { MyAgentPathPicker.scan(); } catch (e) { /* ignore */ }
      }
    },
    after() {
      if (typeof MyAgentPathPicker !== 'undefined' && MyAgentPathPicker.scan) {
        try { MyAgentPathPicker.scan(); } catch (e) { /* ignore */ }
      }
    },
  });

  /* ── 目录与路径 ─────────────────────────────────────────────────────── */
  const PATH_GROUPS = [
    { key: 'WORK_DIR', zh: '工作区目录', en: 'Workspace folder', hint: ['会话数据、产物与技能都放在这里；修改后需重启 Agent', 'Sessions, artifacts and skills; restart required'], kind: 'directory', restart: true },
    { key: 'SKILLS_DIR', zh: '技能目录', en: 'Skills folder', hint: ['留空表示使用默认位置', 'Empty = default'], kind: 'directory' },
    { key: 'PLUGINS_DIR', zh: '插件目录', en: 'Plugins folder', hint: ['留空表示使用默认位置', 'Empty = default'], kind: 'directory' },
    { key: 'LOG_DIR', zh: '日志目录', en: 'Logs folder', hint: ['留空表示使用默认位置', 'Empty = default'], kind: 'directory' },
  ];
  const PATH_ADVANCED = [
    { key: 'HOOKS_PATH', zh: 'Hooks 配置', en: 'Hooks config', kind: 'file', hint: ['Hook 定义文件的位置', 'Where hook definitions live'] },
    { key: 'NODE_HOME', zh: 'Node.js 目录', en: 'Node.js home', kind: 'directory', hint: ['插件运行时用到的 Node', 'Node used by plugin runtime'] },
  ];

  A.registerSection({
    id: 'paths', icon: 'path', zh: '目录与路径', en: 'Paths', mode: 'explicit',
    dirtyMessage: ['有未保存的路径更改', 'Unsaved path changes'],
    zhSub: 'Agent 读写文件的位置；改工作区后需要重启。', enSub: 'Where the agent reads and writes.',
    async load() {
      const env = await api('/api/env');
      const map = {};
      (env.groups || []).forEach((g) => (g.vars || []).forEach((v) => { map[v.key] = v; }));
      return { map, path: env.path, effectivePaths: env.effective_paths || {} };
    },
    render(d) {
      const input = (item) => {
        const row = d.map[item.key] || {};
        const effective = d.effectivePaths[item.key] || [];
        const value = row.value || effective[0] || '';
        return '<input class="st-input" data-path-key="' + esc(item.key) + '" data-path-kind="' + esc(item.kind) +
          '" data-original="' + esc(value) + '" value="' + esc(value) + '" placeholder="' + esc(t('未检测到，可自行选择', 'Not detected — choose a path')) + '">';
      };
      const row = (item, extra) => {
        const hint = item.hint || ['', ''];
        const effective = d.effectivePaths[item.key] || [];
        const current = effective.length ? '<br>' + t('当前使用：', 'Currently used: ') + effective.map(esc).join('<br>') : '';
        return W.row(t(item.zh, item.en), t(hint[0], hint[1]) + current, (extra || '') + input(item));
      };
      return W.card(t('工作区', 'Workspace'), t('会话数据、产物与技能都放在这里', 'Sessions, artifacts and skills live here'),
        row(PATH_GROUPS[0], W.chip(t('需重启', 'Restart')))) +
        W.card(t('其它目录', 'Other folders'), t('留空表示使用默认位置', 'Empty = default'),
          PATH_GROUPS.slice(1).map((item) => row(item)).join('') +
          W.adv(t('更多路径', 'More paths'), PATH_ADVANCED.map((item) => row(item)).join(''))) +
        W.note(t('路径变量支持目录 / 文件两种选择器；改动会写入 <span class="st-mono">' + esc(d.path || '.env') + '</span>。',
          'Path variables support folder/file pickers; changes are written to <span class="st-mono">' + esc(d.path || '.env') + '</span>.'));
    },
    after() {
      if (typeof MyAgentPathPicker !== 'undefined' && MyAgentPathPicker.scan) {
        try { MyAgentPathPicker.scan(); } catch (e) { /* ignore */ }
      }
    },
    async save(d) {
      /* 同上：没填的路径键不要写成空行；把已有值清空 = 恢复默认（删键） */
      const snapshot = (d && d.map) || {};
      const values = {};
      const remove = [];
      Array.prototype.forEach.call(document.querySelectorAll('[data-path-key]'), (el) => {
        const key = el.dataset.pathKey;
        const now = el.value.trim();
        const before = String(el.dataset.original || '').trim();
        if (now === before) return;
        if (now === '') { if ((snapshot[key] || {}).value) remove.push(key); return; }
        values[key] = now;
      });
      if (!Object.keys(values).length && !remove.length) return;
      const body = {};
      if (Object.keys(values).length) body.values = values;
      if (remove.length) body.remove = remove;
      const res = await api('/api/env', { method: 'POST', body });
      if (res && res.restart_required) toast(t('已保存；工作区变更需重启 Agent 生效', 'Saved — restart required for WORK_DIR'), true);
    },
  });
})();
