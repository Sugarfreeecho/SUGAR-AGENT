/* ═══════════════════════════════════════════════════════════════════════
   设置中心 · 分区：用量统计
   数据来自各会话的 execution_metrics.json，经 /api/usage-stats 汇总；
   全量扫描较慢，后端后台重建，这里轮询到 ready 再画。
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  const A = window.MyAgentSettings;
  const { t, esc, api, W, reportError } = A;

  let current = null;        // 最近一次 ready 的载荷
  let mode = 'total';        // total | output
  let heatMode = 'daily';    // daily | weekly | cumulative
  let heatDay = '';          // 热力图里选中的日期
  let sessionAll = false;    // 会话表是否展开全部
  let sessionQuery = '';     // 会话表检索词
  let sortKey = '';          // 会话表排序列：requests | input | output | lastAt
  let sortDir = 'desc';
  let modelMode = 'model';   // model | profile（按模型名 / 按模型配置）
  let pollTimer = null;
  let pollCount = 0;
  let view = { type: 'summary' };   // summary | detail（某个会话的执行明细）
  let detailCleanup = null;

  const num = (value) => Number(value || 0).toLocaleString('en-US');
  const isoDay = (date) => date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' +
    String(date.getDate()).padStart(2, '0');

  // 卡片只有一百来像素宽：上了四位数就不留小数，免得「4075.5 万」折成两行。
  const trim = (value, digits) => (value >= 1000 ? String(Math.round(value)) : value.toFixed(digits));

  function compact(value) {
    const n = Number(value || 0);
    if (A.lang === 'zh') {
      if (n >= 1e8) return trim(n / 1e8, 2) + ' 亿';
      if (n >= 1e4) return trim(n / 1e4, 1) + ' 万';
      return String(n);
    }
    if (n >= 1e9) return trim(n / 1e9, 2) + 'B';
    if (n >= 1e6) return trim(n / 1e6, 1) + 'M';
    if (n >= 1e3) return trim(n / 1e3, 1) + 'K';
    return String(n);
  }

  function onUsageSection() {
    return (location.hash || '') === '#usage';
  }

  function scheduleRefresh() {
    if (pollTimer || pollCount >= 90) return;
    pollTimer = setTimeout(async () => {
      pollTimer = null;
      pollCount += 1;
      if (!onUsageSection()) return;
      try {
        const payload = await api('/api/usage-stats');
        if (payload && payload.data && payload.data.ready) {
          pollCount = 0;
          A.showSection('usage', { force: true });
          return;
        }
      } catch (error) { /* 继续等下一轮 */ }
      scheduleRefresh();
    }, 1000);
  }

  function digest(data) {
    const totals = data.totals || {};
    const hit = Number(totals.cacheHit || 0);
    const miss = Number(totals.cacheMiss || 0);
    const rate = hit + miss > 0 ? Math.round((hit / (hit + miss)) * 100) : null;
    const cells = [
      [compact(totals.tokens), t('累计 Token', 'Total tokens'), num(totals.tokens)],
      [compact(totals.output), t('输出 Token', 'Output tokens'), num(totals.output)],
      [num(totals.requests), t('请求数', 'Requests'), ''],
      [num(totals.sessions), t('会话数', 'Sessions'), ''],
      [rate === null ? '—' : rate + '%', t('上下文命中', 'Cache hit'), num(hit) + ' / ' + num(hit + miss)],
    ];
    return '<div class="st-usage-sum">' + cells.map(([value, label, title]) =>
      '<div class="cell"' + (title ? ' title="' + esc(title) + '"' : '') + '>' +
        '<div class="v">' + esc(String(value)) + '</div><div class="l">' + esc(label) + '</div></div>').join('') +
      '</div>';
  }

  // 「总量 / 输出」现在直接决定格里画的是哪个量，不再需要单独的柱状图。
  function heatValue(row) {
    if (!row) return 0;
    return mode === 'output'
      ? Number(row.output || 0)
      : Number(row.input || 0) + Number(row.output || 0);
  }

  function table(head, rows) {
    if (!rows.length) return W.empty(t('暂无数据。', 'No data.'));
    return '<table class="st-usage-table"><thead><tr>' +
      head.map((cell) => '<th>' + esc(cell) + '</th>').join('') +
      '</tr></thead><tbody>' + rows.join('') + '</tbody></table>';
  }

  /* ── Token 活动热力图（自 zen-gate 用量页搬来） ───────────────────────── */
  function heatCells(days) {
    const byDay = new Map();
    (days || []).forEach((row) => byDay.set(row.day, row));
    const keyOf = isoDay;
    const totalOf = (key) => heatValue(byDay.get(key));
    const requestsOf = (key) => Number(((byDay.get(key) || {}).requests) || 0);
    const metricLabel = () => (mode === 'output' ? t('输出', 'output') : t('总量', 'total'));

    const end = new Date();
    end.setHours(0, 0, 0, 0);
    const start = new Date(end);
    start.setDate(start.getDate() - start.getDay() - 51 * 7);

    const cells = [];
    let peak = 0;
    if (heatMode === 'weekly') {
      for (let week = 0; week < 52; week += 1) {
        let sum = 0;
        let reqs = 0;
        let firstKey = '';
        let lastKey = '';
        for (let day = 0; day < 7; day += 1) {
          const date = new Date(start);
          date.setDate(start.getDate() + week * 7 + day);
          const key = keyOf(date);
          sum += totalOf(key);
          reqs += requestsOf(key);
          if (day === 0) firstKey = key;
          lastKey = key;
        }
        cells.push({ key: lastKey, value: sum, col: week,
          from: firstKey, to: lastKey, requests: reqs,
          tip: firstKey.slice(5) + ' ~ ' + lastKey.slice(5) + ' · ' + metricLabel() + ' ' + compact(sum) +
            ' · ' + num(reqs) + t(' 次请求', ' reqs') });
        if (sum > peak) peak = sum;
      }
    } else {
      const days48 = Math.round((end - start) / 86400000) + 1;
      let running = 0;
      for (let index = 0; index < days48; index += 1) {
        const date = new Date(start);
        date.setDate(start.getDate() + index);
        const key = keyOf(date);
        const value = totalOf(key);
        running += value;
        const shown = heatMode === 'cumulative' ? running : value;
        const row = byDay.get(key);
        cells.push({ key, value: shown, col: Math.floor(index / 7),
          tip: key + (heatMode === 'cumulative' ? t(' · 累计 ', ' · cumulative ') : ' · ') + compact(shown) +
            (row
              ? ' · ' + t('输入 ', 'in ') + compact(row.input) + ' · ' + t('输出 ', 'out ') + compact(row.output) +
                ' · ' + num(requestsOf(key)) + t(' 次请求', ' reqs')
              : t(' · 当天没有用量', ' · no usage')) });
        if (shown > peak) peak = shown;
      }
    }
    return { cells, peak };
  }

  function heatGrid(days) {
    const { cells, peak } = heatCells(days);
    if (!cells.length) return W.empty(t('还没有按天的记录。', 'No daily records yet.'));
    const level = (value) => (value <= 0 ? 0 : Math.min(4, Math.max(1, Math.ceil((value / peak) * 4))));
    const squares = cells.map((cell) =>
      '<i class="st-heat-cell l' + level(cell.value) + (cell.key === heatDay ? ' is-on' : '') +
      '" data-act="usage-heat-day" data-day="' + esc(cell.key) + '" title="' + esc(cell.tip) + '"></i>').join('');

    // 月份标签按「周列」计：一列可能横跨两个月，按当天分组会出现同列两个标签。
    const labels = [];
    for (let col = 0; col < 52; col += 1) {
      const first = heatMode === 'weekly' ? cells[col] : cells[col * 7];
      if (!first) continue;
      const month = new Date(first.key + 'T00:00:00').getMonth();
      const last = labels[labels.length - 1];
      if (last && last.month === month) last.span += 1;
      else labels.push({ month, span: 1 });
    }
    // 一列只有 10px，两个字的「10月」塞不进 2 列，窄的只写数字。
    const months = labels.map((label) =>
      '<span style="grid-column:span ' + label.span + '">' +
      ((label.span >= 3 ? (label.month + 1) + t('月', '') : String(label.month + 1))) + '</span>').join('');

    // 柱状图不需要色阶图例，但这一行的高度要占住，否则切模式时整张卡片会跳 29px。
    const legend = heatMode === 'weekly'
      ? '<div class="st-heat-legend">' + t('柱高 = 当周合计', 'bar height = weekly total') + '</div>'
      : '<div class="st-heat-legend">' + t('较少', 'less') +
        [0, 1, 2, 3, 4].map((lv) => '<i class="l' + lv + '"></i>').join('') + t('较多', 'more') + '</div>';
    const picked = heatDay
      ? (function () {
        if (heatMode === 'weekly') {
          const week = weekSummary(days, heatDay);
          return '<div class="st-heat-day">' +
            esc(week.from.slice(5) + ' ~ ' + week.to.slice(5)) + ' · ' +
            t('输入 ', 'in ') + num(week.input) + ' · ' + t('输出 ', 'out ') + num(week.output) + ' · ' +
            num(week.requests) + t(' 次请求', ' reqs') +
            closePick() + '</div>';
        }
        const row = (days || []).find((item) => item.day === heatDay);
        return '<div class="st-heat-day">' + esc(heatDay) + ' · ' +
          (row ? t('输入 ', 'in ') + num(row.input) + ' · ' + t('输出 ', 'out ') + num(row.output) +
            ' · ' + num(row.requests) + t(' 次请求', ' reqs') : t('当天没有用量', 'no usage')) +
          closePick() + '</div>';
      })()
      : '<div class="st-heat-day">' + (heatMode === 'weekly'
        ? t('点柱子看当周明细', 'Click a bar for the week')
        : t('点格子看当天明细', 'Click a cell for the day')) + '</div>';

    // 每周只有 52 个点，颜色深浅表达不了量级，改用柱高更直观。
    const chart = heatMode === 'weekly'
      ? '<div class="st-heat-scroll"><div class="st-week-bars">' + cells.map((cell) =>
        '<i class="' + (cell.key === heatDay ? 'is-on' : '') + '" data-act="usage-heat-day" data-day="' + esc(cell.key) +
        '" style="height:' + Math.max(2, Math.round((cell.value / peak) * 100)) + '%" title="' +
        esc(cell.tip) + '"></i>').join('') + '</div><div class="st-heat-months">' + months + '</div></div>'
      : '<div class="st-heat-scroll"><div class="st-heat">' + squares +
        '</div><div class="st-heat-months">' + months + '</div></div>';
    return chart + legend + picked;
  }

  function closePick() {
    return ' <button type="button" class="st-btn sm text" data-act="usage-heat-day" data-day="">' +
      t('收起', 'Close') + '</button>';
  }

  // 周明细：把选中那一列（7 天）加起来。
  function weekSummary(days, endKey) {
    const byDay = new Map((days || []).map((row) => [row.day, row]));
    const end = new Date(endKey + 'T00:00:00');
    let from = endKey;
    let input = 0;
    let output = 0;
    let requests = 0;
    for (let index = 6; index >= 0; index -= 1) {
      const date = new Date(end);
      date.setDate(end.getDate() - index);
      const key = isoDay(date);
      if (index === 6) from = key;
      const row = byDay.get(key);
      if (!row) continue;
      input += Number(row.input || 0);
      output += Number(row.output || 0);
      requests += Number(row.requests || 0);
    }
    return { from, to: endKey, input, output, requests };
  }

  function heatModes() {
    return '<div class="st-heat-modes">' +
      [['daily', t('每日', 'Daily')], ['weekly', t('每周', 'Weekly')], ['cumulative', t('累计', 'Cumulative')]]
        .map(([key, label]) => '<button type="button" data-act="usage-heat-mode" data-mode="' + key + '"' +
          (heatMode === key ? ' class="on"' : '') + '>' + esc(label) + '</button>').join('') + '</div>';
  }

  // 原「每日 Token」卡片的功能收进这里：量纲（总量/输出）直接作用在格子上。
  function heatControls() {
    const metric = '<div class="st-usage-seg sm">' +
      [['total', t('总量', 'Total')], ['output', t('输出', 'Output')]].map(([key, label]) =>
        '<button type="button" data-act="usage-mode" data-mode="' + key + '"' +
        (mode === key ? ' class="on"' : '') + '>' + esc(label) + '</button>').join('') + '</div>';
    return '<div class="st-heat-controls">' + metric + heatModes() + '</div>';
  }

  function speedLine(totals) {
    if (!totals) return '';
    const parts = [];
    if (totals.ttftMs) parts.push(t('平均首字 ', 'first token ') + (totals.ttftMs / 1000).toFixed(1) + 's');
    if (totals.tokensPerSec) parts.push(t('输出 ', 'output ') + totals.tokensPerSec + ' tok/s');
    if (!parts.length) return '';
    const samples = Math.max(Number(totals.ttftSamples || 0), Number(totals.speedSamples || 0));
    return '<div class="st-usage-speed">' + parts.join(' · ') +
      (samples ? ' · ' + t('采样 ' + num(samples) + ' 次', 'over ' + num(samples) + ' requests') : '') + '</div>';
  }

  function modelTable(models, firstLabel) {
    const ttft = (value) => {
      if (!value) return '—';
      return value >= 1000 ? (value / 1000).toFixed(1) + 's' : Math.round(value) + 'ms';
    };
    return table(
      [firstLabel || t('模型', 'Model'), t('请求', 'Reqs'), t('输入', 'Input'), t('输出', 'Output'),
        t('平均首字', 'First token')],
      (models || []).map((row) =>
        '<tr><td title="' + esc(row.model) + '">' + esc(row.other ? t('其他', 'Other') : row.model) + '</td>' +
        '<td>' + num(row.requests) + '</td>' +
        '<td>' + compact(row.input) + '</td>' +
        '<td>' + compact(row.output) + '</td>' +
        '<td>' + esc(ttft(row.ttftMs)) + '</td></tr>')
    );
  }

  function sessionTable(sessions) {
    const rows = sessions || [];
    if (!rows.length) return W.empty(t('暂无数据。', 'No data.'));
    const visible = sessionAll ? Infinity : 30;
    const head = [
      ['name', t('会话', 'Session')],
      ['requests', t('请求', 'Reqs')],
      ['input', t('输入', 'Input')],
      ['output', t('输出', 'Output')],
      ['lastAt', t('最近', 'Last')],
    ].map(([key, label]) => (key === 'name'
      ? '<th>' + esc(label) + '</th>'
      : '<th class="st-usage-sort' + (sortKey === key ? ' is-on' : '') + '" data-act="usage-sort" data-key="' + key +
        '" title="' + esc(t('点击排序', 'Click to sort')) + '">' + esc(label) +
        (sortKey === key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '') + '</th>')).join('');
    const body = rows.map((row, index) =>
      // 全部行都在 DOM 里：过滤、排序、30 条截断都在前端做，不重新请求。
      '<tr class="st-ud-link" data-act="usage-session" data-id="' + esc(row.id) + '" data-name="' + esc(row.name) +
      '" data-search="' + esc((row.name + ' ' + row.id).toLowerCase()) + '"' +
      ' data-requests="' + Number(row.requests || 0) + '" data-input="' + Number(row.input || 0) +
      '" data-output="' + Number(row.output || 0) + '" data-last="' + esc(String(row.lastAt || '')) + '"' +
      (index >= visible ? ' hidden' : '') +
      ' title="' + esc(t('查看执行明细', 'Open execution detail')) + '">' +
      '<td title="' + esc(row.id) + '">' + esc(row.name) + '</td>' +
      '<td>' + num(row.requests) + '</td>' +
      '<td>' + compact(row.input) + '</td>' +
      '<td>' + compact(row.output) + '</td>' +
      '<td>' + esc(String(row.lastAt || '').slice(0, 10)) + '</td></tr>').join('');
    return '<table class="st-usage-table" data-usage-sessions><thead><tr>' + head +
      '</tr></thead><tbody>' + body + '</tbody></table>';
  }

  /* 会话表：全部行都在 DOM 里，按输入过滤、按 30 条截断，开关与检索都不再请求后端。 */
  function applySessionFilter(host) {
    const input = host.querySelector('[data-usage-session-search]');
    if (input && input.value !== sessionQuery) input.value = sessionQuery;
    const query = sessionQuery.trim().toLowerCase();
    const tbody = host.querySelector('[data-usage-sessions] tbody');
    const rows = Array.from(host.querySelectorAll('tr[data-search]'));
    if (!rows.length) return;

    // 排序：换个列就按新列降序，同一列再点切升序，第三次回到默认（后端的总量序，DOM 原序不动）。
    if (sortKey) {
      const value = (row) => (sortKey === 'lastAt'
        ? row.dataset.last || ''
        : Number(row.dataset[sortKey] || 0));
      rows.sort((a, b) => {
        const left = value(a);
        const right = value(b);
        if (left === right) return 0;
        return (sortDir === 'asc') === (left < right) ? -1 : 1;
      });
      if (tbody) rows.forEach((row) => tbody.appendChild(row));
    }

    let matched = 0;
    let shown = 0;
    rows.forEach((row) => {
      if (query && row.dataset.search.indexOf(query) < 0) {
        row.hidden = true;
        return;
      }
      matched += 1;
      const keep = sessionAll || shown < 30;
      row.hidden = !keep;
      if (keep) shown += 1;
    });
    const label = host.querySelector('[data-usage-session-count]');
    if (label) label.textContent = query ? matched + ' / ' + rows.length : String(matched);
  }

  function bindSessionSearch(host) {
    const input = host.querySelector('[data-usage-session-search]');
    if (!input) return;
    input.value = sessionQuery;
    input.addEventListener('input', () => {
      sessionQuery = input.value;
      applySessionFilter(host);
    });
  }

  function repaint() {
    const host = document.getElementById('st-body');
    if (!host || !current) return;
    host.innerHTML = body(current);
    bindSessionSearch(host);
    applySessionFilter(host);
    scrollHeatToEnd(host);
  }

  // 最近的数据在最右边，默认滚到头。
  function scrollHeatToEnd(host) {
    const box = host.querySelector('.st-heat-scroll');
    if (box) box.scrollLeft = box.scrollWidth;
  }

  function detailShell() {
    return '<div class="st-ud-head">' +
      '<button type="button" class="st-btn sm" data-act="usage-back">← ' + t('返回汇总', 'Back') + '</button>' +
      '<div><b>' + esc(view.name || view.id) + '</b>' +
      '<code class="st-mono">' + esc(view.id) + '</code></div></div>' +
      '<div data-ud-slot><div class="st-hint">' + t('加载明细…', 'Loading…') + '</div></div>';
  }

  async function loadDetail(sessionId, slot) {
    try {
      const payload = await api('/api/execution-metrics?session_id=' + encodeURIComponent(sessionId));
      if (view.type !== 'detail' || view.id !== sessionId) return;
      const data = (payload && payload.data) || {};
      if (detailCleanup) { detailCleanup(); detailCleanup = null; }
      if (!window.MyAgentUsageDetail) throw new Error(t('明细模块未加载', 'detail module missing'));
      detailCleanup = window.MyAgentUsageDetail.render(slot, data, { sessionId: sessionId });
    } catch (error) {
      slot.innerHTML = '<div class="st-hint">' +
        esc(t('明细加载失败：', 'Failed to load detail: ') + String((error && error.message) || error)) + '</div>';
    }
  }

  function body(data) {
    const models = data.models || [];
    const modelRows = modelMode === 'profile' ? (data.profiles || []) : models;
    const modelTotal = modelMode === 'profile' ? Number(data.profilesTotal || 0) : Number(data.modelsTotal || 0);
    const modelSeg = '<div class="st-usage-seg sm">' +
      [['model', t('按模型名', 'By model')], ['profile', t('按配置', 'By profile')]].map(([key, label]) =>
        '<button type="button" data-act="usage-model-mode" data-mode="' + key + '"' +
        (modelMode === key ? ' class="on"' : '') + '>' + esc(label) + '</button>').join('') + '</div>';
    const sessions = data.sessions || [];
    const subagents = Number((data.totals || {}).subagents || 0);
    const subNote = subagents > 0
      ? t('，另有 ' + subagents + ' 个子代理已计入总量', '; ' + subagents + ' subagents counted in the totals')
      : '';
    const countNote = (shown, total, zh, en) => (shown >= total
      ? t('共 ' + total + ' ' + zh, 'All ' + total + ' ' + en)
      : t('共 ' + total + ' ' + zh + '，显示前 ' + shown + ' 个', 'Top ' + shown + ' of ' + total + ' ' + en));
    const sessionBar = '<div class="st-usage-sess-bar">' +
      '<input type="search" class="st-input sm" data-usage-session-search placeholder="' +
      esc(t('搜索会话名或 ID', 'Search name or ID')) + '" aria-label="' + esc(t('搜索会话', 'Search sessions')) + '">' +
      '<span class="st-muted" data-usage-session-count>' + num(sessions.length) + '</span>' +
      (sessions.length > 30
        ? '<button type="button" class="st-btn sm text" data-act="usage-sessions-all">' +
          (sessionAll ? t('只看前 30', 'Top 30') : t('全部 ' + num(sessions.length) + ' 个', 'All ' + num(sessions.length))) +
          '</button>'
        : '') + '</div>';
    return digest(data) +
      W.card(t('Token 活动', 'Token activity'),
        t('近 52 周，点开看明细', 'Last 52 weeks; click for details'),
        heatGrid(data.days) + speedLine(data.totals), heatControls()) +
      '<div class="st-usage-two">' +
        W.card(t('按模型', 'By model'),
          countNote(modelRows.length, modelTotal, modelMode === 'profile' ? '个配置' : '个模型',
            modelMode === 'profile' ? 'profiles' : 'models'),
          '<div class="st-usage-model-scroll">' +
          modelTable(modelRows, modelMode === 'profile' ? t('模型配置', 'Profile') : t('模型', 'Model')) +
          '</div>', modelSeg) +
        W.card(t('按会话', 'By session'),
          (sessionAll
            ? t('共 ' + num(data.sessionsTotal) + ' 个会话，已全部展开', 'All ' + num(data.sessionsTotal) + ' sessions')
            : countNote(30, data.sessionsTotal, '个会话', 'sessions')) + subNote,
          sessionBar + sessionTable(sessions)) +
      '</div>' +
      W.note(t(
        '数据来自本机各会话的 <span class="st-mono">execution_metrics.json</span>，只统计有 usage 回包的成功请求；' +
        '子代理会话（<span class="st-mono">subagents/</span>）的用量已计入总量，但不单独列在会话表里；' +
        '「按配置」按当前模型配置归类，不在配置里的记作「(未标注)」；' +
        '不同模型的自报口径可能不同，跨模型相加只作趋势参考。',
        'Aggregated from local <span class="st-mono">execution_metrics.json</span>; only requests that returned usage are counted. ' +
        'Subagent sessions under <span class="st-mono">subagents/</span> are included in the totals but not listed as sessions. ' +
        '"By profile" groups models by the current profile config; models outside any profile count as "(unlabeled)". ' +
        'Providers report tokens differently, so cross-model sums are a trend indicator only.') +
        ' · ' + t('统计于 ', 'Built ') + esc(String(data.generatedAt || '').replace('T', ' ').replace('Z', '')) +
        ' <button type="button" class="st-btn sm text" data-act="usage-refresh">' + t('重新统计', 'Rebuild') + '</button>');
  }

  A.registerSection({
    id: 'usage', icon: 'usage', zh: '用量统计', en: 'Usage', mode: 'instant',
    zhSub: '本机所有会话的 token 用量，只读；数据不出本机。',
    enSub: 'Token usage across every local session. Read-only, never uploaded.',
    async load() {
      try {
        return await api('/api/usage-stats');
      } catch (error) {
        return { __error: error };
      }
    },
    render(payload) {
      if (view.type === 'detail') return detailShell();
      const data = (payload && payload.data) || {};
      if (!data.ready) {
        current = null;
        scheduleRefresh();
        const message = data.error
          ? t('统计失败：', 'Build failed: ') + esc(String(data.error))
          : t('正在统计本机用量…第一次要扫一遍所有会话，通常几秒到十几秒。',
              'Building usage from local sessions — the first pass scans them all, usually a few seconds.');
        return W.card(t('用量统计', 'Usage'), '', '<div class="st-hint">' + message + '</div>');
      }
      current = data;
      pollCount = 0;
      return body(data);
    },
    onAction(act, el) {
      if (act === 'usage-session') {
        view = { type: 'detail', id: el.dataset.id || '', name: el.dataset.name || '' };
        A.showSection('usage', { force: true });
        return;
      }
      if (act === 'usage-back') {
        view = { type: 'summary' };
        A.showSection('usage', { force: true });
        return;
      }
      if (act === 'usage-mode') {
        mode = el.dataset.mode === 'output' ? 'output' : 'total';
        repaint();
        return;
      }
      if (act === 'usage-model-mode') {
        modelMode = el.dataset.mode === 'profile' ? 'profile' : 'model';
        repaint();
        return;
      }
      if (act === 'usage-heat-mode') {
        heatMode = el.dataset.mode || 'daily';
        heatDay = '';
        repaint();
        return;
      }
      if (act === 'usage-heat-day') {
        const day = el.dataset.day || '';
        heatDay = heatDay === day ? '' : day;
        repaint();
        return;
      }
      if (act === 'usage-sessions-all') {
        sessionAll = !sessionAll;
        repaint();
        return;
      }
      if (act === 'usage-sort') {
        const key = el.dataset.key || '';
        if (!key) return;
        if (sortKey !== key) { sortKey = key; sortDir = 'desc'; }
        else if (sortDir === 'desc') { sortDir = 'asc'; }
        else { sortKey = ''; sortDir = 'desc'; }
        repaint();
        return;
      }
      if (act === 'usage-refresh') {
        el.disabled = true;
        current = null;
        api('/api/usage-stats?refresh=1')
          .then(() => { pollCount = 0; A.showSection('usage', { force: true }); })
          .catch((error) => { el.disabled = false; reportError(error); });
      }
    },
    after(body) {
      if (view.type === 'detail') {
        const slot = body.querySelector('[data-ud-slot]');
        if (slot) loadDetail(view.id, slot);
      }
      bindSessionSearch(body);
      applySessionFilter(body);
      scrollHeatToEnd(body);
      // 离开分区时停掉轮询与明细视图；回来时会重新 load。
      return () => {
        clearTimeout(pollTimer);
        pollTimer = null;
        if (detailCleanup) { detailCleanup(); detailCleanup = null; }
      };
    },
  });
})();
