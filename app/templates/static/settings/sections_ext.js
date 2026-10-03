/* ═══════════════════════════════════════════════════════════════════════
   设置中心 · 分区（二）：插件 / Hooks / MCP
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  const A = window.MyAgentSettings;
  const { t, esc, api, W, toast, reportError, askConfirm, openDialog, dialogValue, reload } = A;

  const pluginId = (p) => p.id || p.plugin_id || p.namespace || p.name || '';
  const pluginName = (p) => p.name || pluginId(p);
  /* 说明类文字一律走悬停浮框（列表里只留名字/短标识），没有说明就原样输出 */
  const tipIf = (label, text, cls) => (text ? W.tip(label, text, cls) : label);
  const componentsSummary = (p) => {
    const c = p.components || {};
    const parts = [];
    if (c.skills && c.skills.length) parts.push('skill×' + c.skills.length);
    if (c.hooks && c.hooks.length) parts.push('hook×' + c.hooks.length);
    if (c.mcp_sources && c.mcp_sources.length) parts.push('mcp×' + c.mcp_sources.length);
    if (c.agents && c.agents.length) parts.push('agent×' + c.agents.length);
    if (c.commands && c.commands.length) parts.push('cmd×' + c.commands.length);
    return parts.join(' · ');
  };

  /* ── 插件 ───────────────────────────────────────────────────────────── */
  function pluginSettingsDialog(id) {
    api('/api/plugins/' + encodeURIComponent(id) + '/settings').then((res) => {
      const settings = res.settings || {};
      const fields = settings.fields || [];
      if (!fields.length) { toast(t('该插件没有可配置项', 'This plugin has no settings'), true); return; }
      const rows = A.pluginSettingsMarkup(settings);
      const missing = settings.missing_required || [];
      openDialog({
        title: t('插件设置', 'Plugin settings') + ' · ' + esc(settings.title || id),
        sub: missing.length ? t('还缺少必填项：', 'Missing required: ') + missing.join(', ')
          : t('改动会立即写入该插件的配置文件。', 'Changes are written to the plugin config immediately.'),
        okText: t('保存', 'Save'),
        body: rows,
        onOk: async () => {
          const body = document.getElementById('st-dlg-body');
          const values = A.pluginSettingsValues(body, settings);
          await api('/api/plugins/' + encodeURIComponent(id) + '/settings', { method: 'PATCH', body: { values } });
          toast(t('已保存', 'Saved'));
        },
      });
    }).catch((err) => {
      reportError(new Error(t('该插件没有设置表单：', 'This plugin has no settings schema: ') + (err.message || '')));
    });
  }

  A.registerSection({
    id: 'plugins', icon: 'plugins', zh: '插件', en: 'Plugins', mode: 'instant',
    zhSub: '插件可带工具、技能和 Hooks，启停后即时生效。', enSub: 'Plugins may bundle tools, skills and hooks.',
    async load() {
      const snapshot = await api('/api/extensions');
      return snapshot;
    },
    render(d) {
      const plugins = (d.plugins || []).filter((p) => !p.system_builtin);
      const rows = plugins.map((p) => {
        const compat = p.compatibility || {};
        const bad = compat.status === 'incompatible' || compat.compatible === false;
        const loaded = p.loaded !== false && p.enabled !== false;
        return W.lrow(
          tipIf(esc(pluginName(p)) + (p.version ? ' <span class="st-muted">v' + esc(p.version) + '</span>' : ''),
            p.description || ''),
          esc(componentsSummary(p) || p.namespace || ''),
          (bad ? W.status('warn', t('不兼容', 'Incompatible'))
            : loaded ? W.status('ok', t('正常', 'OK')) : W.status('warn', t('已停用', 'Disabled'))) +
          W.sw('plugin:' + pluginId(p), p.enabled !== false) +
          '<button type="button" class="st-btn sm text" data-act="plugin-settings" data-id="' + esc(pluginId(p)) + '">' + t('设置', 'Settings') + '</button>' +
          '<button type="button" class="st-btn sm text danger" data-act="plugin-del" data-id="' + esc(pluginId(p)) + '" data-name="' + esc(pluginName(p)) + '">' + t('移除', 'Remove') + '</button>'
        );
      }).join('');
      const errors = d.plugin_errors || [];
      const warnings = d.plugin_warnings || [];
      /* 插件贡献的设置入口（原聊天页「界面设置」弹窗里的槽位，已迁到本页） */
      const contributed = (d.ui_contributions || []).filter((c) => ['settings.section', 'navigation'].includes(String(c.slot || '')));
      const contributedCard = contributed.length ? W.card(
        t('插件页面与设置', 'Plugin pages and settings'), t('由插件贡献，随插件启用状态出现', 'Contributed by plugins'),
        contributed.map((c) => W.lrow(
          tipIf(esc(c.title || c.label || c.id || ''), c.description || ''),
          esc(c.plugin_id || ''),
          c.href ? '<a class="st-btn sm" href="' + esc(c.href) + '" target="_blank" rel="noopener">' + t('打开', 'Open') + '</a>'
            : '<button class="st-btn sm" type="button" data-act="plugin-settings" data-id="' + esc(c.plugin_id) + '">' + t('设置', 'Settings') + '</button>'
        )).join('')) : '';
      return W.card(t('安装插件', 'Install plugin'), t('支持本地目录、压缩包或 Git 地址', 'Local folder, archive or Git URL'),
        '<div class="st-row block"><div class="st-ctl"><div class="st-package-source" data-package-kind="plugins">' +
        '<input class="st-input" data-field="plugin-source" style="max-width:420px" placeholder="D:\\plugins\\my-plugin 或 https://github.com/…/plugin.git">' +
        '<div class="st-package-buttons"><button class="st-btn" type="button" data-browse-kind="directory" data-browse-field="plugin-source">' + t('选择目录', 'Choose folder') + '</button>' +
        '<button class="st-btn" type="button" data-browse-kind="file" data-browse-field="plugin-source">' + t('选择压缩包', 'Choose archive') + '</button>' +
        W.btn(t('安装 / 更新', 'Install / update'), 'plugin-install', 'primary') + '</div>' +
        '<span class="st-muted st-package-hint">' + t('拖入插件目录或压缩包可直接安装', 'Drop a plugin folder or archive to install') + '</span></div></div></div>') +
        W.card(t('已安装插件', 'Installed plugins'), t('悬停插件名看简介', 'Hover a name for its description'),
          rows || W.empty(t('还没有插件', 'No plugins installed')),
          W.btn(t('重新发现 / 热重载', 'Rediscover'), 'plugin-reload')) +
        contributedCard +
        (errors.length ? W.note('<b>' + t('插件错误', 'Plugin errors') + '：</b>' + errors.map(esc).join('<br>')) : '') +
        (warnings.length ? W.note('<b>' + t('插件警告', 'Plugin warnings') + '：</b>' + warnings.map(esc).join('<br>')) : '');
    },
    onToggle(key, on) {
      if (key.indexOf('plugin:') !== 0) return;
      const id = key.slice('plugin:'.length);
      api('/api/plugins/' + encodeURIComponent(id) + '/enabled', { method: 'POST', body: { enabled: on } })
        .then(() => { toast(on ? t('已启用', 'Enabled') : t('已停用', 'Disabled')); reload(); })
        .catch((err) => { reportError(err); reload(); });
    },
    onAction(act, el) {
      if (act === 'plugin-install') {
        const input = document.querySelector('[data-field="plugin-source"]');
        const source = input ? input.value.trim() : '';
        if (!source) { toast(t('请填写来源', 'Provide a source first'), true); return; }
        toast(t('安装中…', 'Installing…'));
        api('/api/plugins/install', { method: 'POST', body: { source } })
          .then((res) => { toast(t('已', 'Plugin ') + (res.action === 'updated' ? t('更新', 'updated') : t('安装', 'installed'))); reload(); })
          .catch(reportError);
        return;
      }
      if (act === 'plugin-del') {
        askConfirm(t('移除插件「', 'Remove plugin "') + el.dataset.name + t('」？会移入回收站，可恢复。', '"? It goes to trash and is recoverable.'), () => {
          api('/api/plugins/' + encodeURIComponent(el.dataset.id), { method: 'DELETE' })
            .then(() => { toast(t('已移除', 'Removed')); reload(); })
            .catch(reportError);
        });
        return;
      }
      if (act === 'plugin-settings') { pluginSettingsDialog(el.dataset.id); return; }
      if (act === 'plugin-reload') {
        api('/api/extensions/reload', { method: 'POST', body: {} })
          .then((res) => {
            const c = (res && res.changes) || {};
            toast(t('已重载：新增 ', 'Reloaded: +') + (c.added || []).length + t('，移除 ', ', -') + (c.removed || []).length);
            reload();
          })
          .catch(reportError);
      }
    },
    after(root, snapshot) { if (A.syncPluginSections) A.syncPluginSections(snapshot); },
  });

  /* ── Hooks ──────────────────────────────────────────────────────────── */
  A.registerSection({
    id: 'hooks', icon: 'hooks', zh: 'Hooks', en: 'Hooks', mode: 'instant',
    zhSub: '在工具执行前后插入自定义动作；不懂就保持默认。', enSub: 'Run custom actions around tool calls.',
    async load() {
      const snapshot = await api('/api/extensions');
      let env = { groups: [] };
      try { env = await api('/api/env'); } catch (e) { /* 未配置时可能不可用 */ }
      const flat = {};
      (env.groups || []).forEach((g) => (g.vars || []).forEach((v) => { flat[v.key] = v; }));
      return { snapshot, env: flat };
    },
    render(d) {
      const enabled = d.snapshot.enabled || {};
      const paths = d.snapshot.paths || {};
      const hooksPath = (d.env.HOOKS_PATH && d.env.HOOKS_PATH.value) || paths.hooks || '';
      const hooks = d.snapshot.hooks || [];
      const rows = hooks.map((h) => W.lrow(
        esc(h.id || h.hook_id || '—'),
        t('事件', 'Event') + ' ' + esc(h.event || '—') +
          (h.matcher ? ' · ' + t('匹配', 'matcher') + ' <span class="st-mono">' + esc(h.matcher) + '</span>' : '') +
          (h.source || h.source_id || h.plugin_id ? ' · ' + t('来源', 'from') + ' ' + esc(h.source || h.source_id || h.plugin_id) : ''),
        W.chip(esc(h.failure_policy || h.policy || (h.requires_approval ? 'ask' : 'default')))
      )).join('');
      return W.card(t('总开关', 'Master switch'), t('由 HOOKS_ENABLED 控制', 'Gated by HOOKS_ENABLED'),
        W.row(t('启用 Hooks', 'Enable hooks'), t('关闭后所有 Hook 都不执行', 'Turns all hooks off'),
          W.chip(t('立即生效', 'Instant')) + W.sw('env:HOOKS_ENABLED', enabled.hooks !== false)) +
        W.row(t('配置文件', 'Config file'), t('留空则用工作区默认位置', 'Empty = workspace default'),
          '<input class="st-input" data-field="HOOKS_PATH" style="width:192px" value="' + esc(hooksPath) + '" data-path-kind="file">' +
          W.btn(t('保存', 'Save'), 'hook-save-path'))) +
        W.card(t('已注册 Hook', 'Registered hooks'), t('来自配置文件与插件', 'From config and plugins'),
          rows || W.empty(t('还没有 Hook', 'No hooks configured')),
          W.btn(t('热重载', 'Reload'), 'hooks-reload')) +
        (d.snapshot.hook_errors && d.snapshot.hook_errors.length
          ? W.note('<b>' + t('Hook 错误', 'Hook errors') + '：</b>' + d.snapshot.hook_errors.map(esc).join('<br>')) : '') +
        W.note(t('不需要 Hook 就直接关掉总开关，不影响其它功能。', 'If you do not need hooks, switch them off.'));
    },
    onToggle(key, on) {
      if (key !== 'env:HOOKS_ENABLED') return;
      api('/api/env', { method: 'POST', body: { values: { HOOKS_ENABLED: on ? '1' : '0' } } })
        .then(() => toast(on ? t('已启用 Hooks', 'Hooks enabled') : t('已关闭 Hooks', 'Hooks disabled')))
        .catch((err) => { reportError(err); reload(); });
    },
    onAction(act) {
      if (act === 'hook-save-path') {
        const input = document.querySelector('[data-field="HOOKS_PATH"]');
        const value = input ? input.value.trim() : '';
        api('/api/env', { method: 'POST', body: { values: { HOOKS_PATH: value } } })
          .then(() => { toast(t('已保存', 'Saved')); reload(); })
          .catch(reportError);
        return;
      }
      if (act === 'hooks-reload') {
        api('/api/extensions/reload', { method: 'POST', body: {} })
          .then(() => { toast(t('已重载', 'Reloaded')); reload(); })
          .catch(reportError);
      }
    },
  });

  /* ── MCP ────────────────────────────────────────────────────────────── */
  function parseConfig(text) {
    try { return JSON.parse(text || '{}'); } catch (e) { return null; }
  }

  /* Split argv without treating Windows path separators as shell escapes. */
  function splitMcpCommand(text) {
    const parts = [];
    let token = '', quote = '', started = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (ch === '\\' && quote !== "'") {
        let end = i;
        while (text[end] === '\\') end++;
        const count = end - i;
        if (text[end] === '"') {
          token += '\\'.repeat(Math.floor(count / 2));
          if (count % 2) token += '"';
          else quote = quote ? '' : '"';
          i = end;
        } else {
          token += '\\'.repeat(count); i = end - 1;
        }
        started = true;
      } else if (quote) {
        if (ch === quote) quote = '';
        else token += ch;
      } else if (ch === '"' || ch === "'") {
        quote = ch; started = true;
      } else if (/\s/.test(ch)) {
        if (started) { parts.push(token); token = ''; started = false; }
      } else {
        token += ch; started = true;
      }
    }
    if (quote) throw new Error(t('命令中的引号未闭合', 'Unclosed quote in command'));
    if (started) parts.push(token);
    if (!parts[0]) throw new Error(t('请填写有效命令', 'Enter a valid command'));
    return { command: parts[0], args: parts.slice(1) };
  }

  A.registerSection({
    id: 'mcp', icon: 'mcp', zh: 'MCP', en: 'MCP', mode: 'instant',
    zhSub: 'MCP 服务器为 Agent 提供额外工具（浏览器、文档库等）。', enSub: 'MCP servers give the agent extra tools.',
    async load() {
      const tools = await api('/api/mcp/tools');
      let config = { text: '', path: '' };
      try { config = await api('/api/mcp_config'); } catch (e) { /* ignore */ }
      return { tools: tools.tools || [], servers: tools.servers || [], config };
    },
    render(d) {
      const byServer = Object.create(null);
      (d.tools || []).forEach((tool) => { (byServer[tool.server] = byServer[tool.server] || []).push(tool); });
      const servers = (d.servers || []).slice();
      Object.keys(byServer).forEach((server) => {
        if (!servers.some((item) => item.server === server)) servers.push({ server });
      });
      const serverRows = servers.map((s) => {
        const tools = byServer[s.server] || [];
        const head = W.lrow(
          esc(s.server),
          t('传输', 'transport') + ' ' + esc(s.transport || '—') + ' · ' + tools.length + t(' 个工具', ' tools') +
            (s.error ? ' · <span class="st-muted">' + esc(s.error) + '</span>' : ''),
          (s.connected ? W.status('ok', t('已连接', 'Connected')) : W.status('warn', t('未连接', 'Not connected'))) +
          (s.discovered === false || !tools.length
            ? '<button type="button" class="st-btn sm primary" data-act="mcp-register" data-id="' + esc(s.server) + '">' + t('注册', 'Register') + '</button>'
            : '')
        );
        const toolRows = tools.map((tool) => W.lrow(
          tipIf('<span class="st-mono">' + esc(tool.function_name) + '</span>',
            tool.description || tool.tool_name || ''),
          '',
          W.sw('mcp:' + tool.function_name, tool.enabled !== false)
        )).join('');
        return '<section class="st-mcp-group" data-mcp-server="' + esc(s.server) + '">' + head +
          '<div class="st-mcp-tools">' + (toolRows || W.empty(t('该服务器尚未注册工具', 'No tools registered for this server'))) + '</div></section>';
      }).join('');
      const config = parseConfig(d.config.text);
      const advanced = '<textarea class="st-input" data-field="mcp-json" spellcheck="false">' +
        esc(JSON.stringify(config || {}, null, 2)) + '</textarea>' +
        '<div style="display:flex;justify-content:flex-end;gap:8px;padding-top:10px">' +
        W.btn(t('重新加载', 'Reload'), 'mcp-reload') + W.btn(t('保存并重载', 'Save & reload'), 'mcp-save-json', 'primary') + '</div>';
      return W.card(t('添加服务器', 'Add server'), t('两种方式任选其一', 'Either way works'),
          W.row(t('命令方式', 'Command'), t('本地进程，例如 npx 启动的 MCP', 'Local process'),
            '<input class="st-input" data-field="mcp-cmd" style="width:192px" placeholder="npx.cmd -y …">' +
            '<button class="st-btn sm" type="button" data-browse-kind="file" data-browse-field="mcp-cmd" data-browse-command="1">' + t('选择程序', 'Choose program') + '</button>' +
            W.btn(t('添加', 'Add'), 'mcp-add-cmd', 'primary')) +
          W.row(t('地址方式', 'URL'), t('SSE / streamable-http 远程服务', 'SSE / streamable-http'),
            '<input class="st-input" data-field="mcp-url" style="width:192px" placeholder="http://127.0.0.1:3005/sse">' +
            W.btn(t('添加', 'Add'), 'mcp-add-url', 'primary')) +
          W.adv(t('高级：直接编辑 mcp_servers.json', 'Advanced: edit mcp_servers.json'), advanced)) +
        W.card(t('已添加服务器', 'Added servers'), t('按服务器分组 · 悬停工具名看说明', 'Grouped by server — hover tools for descriptions'),
          serverRows || W.empty(t('还没有 MCP 服务器', 'No MCP servers yet'))) +
        W.note(t('配置文件：<span class="st-mono">' + esc(d.config.path || 'mcp_servers.json') + '</span>。保存后会自动重载连接。',
          'Config file: <span class="st-mono">' + esc(d.config.path || 'mcp_servers.json') + '</span>. Connections reload on save.'));
    },
    onToggle(key, on) {
      if (key.indexOf('mcp:') !== 0) return;
      const fn = key.slice('mcp:'.length);
      api('/api/mcp/tools/' + encodeURIComponent(fn) + '/enabled', { method: 'POST', body: { enabled: on } })
        .then(() => toast(on ? t('已启用', 'Enabled') : t('已停用', 'Disabled')))
        .catch((err) => { reportError(err); reload(); });
    },
    onAction(act, el) {
      if (act === 'mcp-register') {
        api('/api/mcp/servers/' + encodeURIComponent(el.dataset.id) + '/register', { method: 'POST', body: {} })
          .then(() => { toast(t('已注册', 'Registered')); reload(); })
          .catch(reportError);
        return;
      }
      if (act === 'mcp-save-json') {
        const area = document.querySelector('[data-field="mcp-json"]');
        const text = area ? area.value : '';
        try { JSON.parse(text || '{}'); } catch (e) { toast(t('JSON 格式不正确', 'Invalid JSON'), true); return; }
        api('/api/mcp_config', { method: 'POST', body: { text } })
          .then(() => { toast(t('已保存并重载', 'Saved & reloaded')); reload(); })
          .catch(reportError);
        return;
      }
      if (act === 'mcp-reload') { reload(); return; }
      if (act === 'mcp-add-cmd' || act === 'mcp-add-url') {
        const isUrl = act === 'mcp-add-url';
        const input = document.querySelector('[data-field="' + (isUrl ? 'mcp-url' : 'mcp-cmd') + '"]');
        const raw = input ? input.value.trim() : '';
        if (!raw) { toast(t('请填写', 'Fill the field first'), true); return; }
        const current = A.__mcpText || '';
        const config = current.trim() ? parseConfig(current) : { enabled: true, servers: {} };
        if (!config || typeof config !== 'object' || Array.isArray(config)) {
          toast(t('现有 MCP 配置格式不正确，请先修复', 'Fix the invalid MCP config first'), true); return;
        }
        const key = config.servers != null ? 'servers' : (config.mcpServers != null ? 'mcpServers' : 'servers');
        const servers = config[key] == null ? {} : config[key];
        if (typeof servers !== 'object' || Array.isArray(servers)) {
          toast(t('服务器配置必须是对象', 'Server config must be an object'), true); return;
        }
        let server;
        try { server = isUrl ? { url: raw } : splitMcpCommand(raw); }
        catch (error) { reportError(error); return; }
        let index = 1;
        while (Object.prototype.hasOwnProperty.call(servers, 'server-' + index)) index++;
        servers['server-' + index] = server;
        config[key] = servers;
        api('/api/mcp_config', { method: 'POST', body: { text: JSON.stringify(config, null, 2) } })
          .then(() => { toast(t('已添加并重载', 'Added & reloaded')); reload(); })
          .catch(reportError);
      }
    },
    after(root, d) { A.__mcpText = (d && d.config && d.config.text) || ''; },
  });
})();
