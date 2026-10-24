/* ═══════════════════════════════════════════════════════════════════════
   设置中心 · 用量统计的会话明细视图
   由原 Execution Dashboard 插件并入：每个会话的 LLM 请求曲线、阶段耗时、
   工具统计、网络流量、Run 对账与轮次明细。数据走单会话快照，秒开。
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  const A = window.MyAgentSettings;
  const { t, esc } = A;
  const detailOpenStates = new WeakMap();

  const CHART_POINT_LIMIT = 300;
  const SERIES_COLORS = ['#89b4fa', '#f9e2af', '#a6e3a1', '#cba6f7', '#f38ba8', '#94e2d5', '#fab387', '#74c7ec'];
  const PHASE_DEFS = [
    ['pre_api', 'API 发送前准备', 'Pre-API'],
    ['api_send', 'API 发送', 'API send'],
    ['first_token', '首 token', 'First token'],
    ['llm_output', 'LLM 输出', 'LLM output'],
    ['tool_execution', '工具执行', 'Tool execution'],
    ['round_postprocess', '轮内后处理', 'Round post'],
    ['final_pipeline', 'Run 收尾', 'Run finalize'],
  ];

  const num = (value) => (Number.isFinite(Number(value)) ? Number(value) : 0);

  function ms(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '—';
    // 一个会话可能横跨好几天，Run 墙钟累加后是几百万秒，用天/小时才看得懂。
    if (n >= 86400000) return (n / 86400000).toFixed(1) + t(' 天', ' d');
    if (n >= 3600000) return (n / 3600000).toFixed(1) + t(' 小时', ' h');
    if (n >= 1000) return (n / 1000).toFixed(n >= 10000 ? 1 : 2) + ' s';
    return Math.max(0, Math.round(n)) + ' ms';
  }

  function bytes(value) {
    const n = num(value);
    if (n >= 1048576) return (n / 1048576).toFixed(2) + ' MB';
    if (n >= 1024) return (n / 1024).toFixed(1) + ' KB';
    return Math.round(n) + ' B';
  }

  function format(value, unit) {
    if (unit === 'ms') return ms(value);
    if (unit === 'B') return bytes(value);
    return Math.round(num(value)).toLocaleString();
  }

  // 坐标轴要窄：398,777,282 这种刻度会把绘图区顶出去。
  function axisLabel(value, unit) {
    if (unit === 'ms') return ms(value);
    if (unit === 'B') return bytes(value);
    const n = num(value);
    if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e4) return Math.round(n / 1e3) + 'K';
    return Math.round(n).toLocaleString();
  }

  function phaseData(req, key) {
    const phases = req.phases || {};
    if (key === 'pre_api') {
      const base = phases.pre_api || {};
      const tail = Math.max(0, num(req.pre_api_tail_ms));
      const events = Object.assign({}, base.events || {});
      if (tail > 0) events.pre_api_tail = tail;
      return { total_ms: num(base.total_ms) + tail, events: events };
    }
    if (phases[key]) return phases[key];
    const stream = ((phases.llm_stream || {}).events) || [];
    const at = (name) => num((stream.find((item) => item.step === name) || {}).ms_since_api_start);
    if (key === 'api_send') {
      const v = Math.max(0, at('stream_created') - at('request_start'));
      return { total_ms: v, events: { request_start_to_stream_created: v } };
    }
    if (key === 'first_token') {
      const v = Math.max(0, at('first_delta') - at('stream_created'));
      return { total_ms: v, events: { stream_created_to_first_delta: v } };
    }
    if (key === 'llm_output') {
      const v = Math.max(0, (at('stream_exhausted') || at('turn_ready')) - at('first_delta'));
      return { total_ms: v, events: { first_delta_to_stream_end: v } };
    }
    if (key === 'tool_execution') {
      const recorded = phases.tool_execution;
      if (recorded && num(recorded.total_ms) > 0) return recorded;
      const values = (req.tools || []).map((tool) => num(tool.duration_ms));
      const wall = values.length ? Math.max.apply(null, values) : 0;
      return { total_ms: wall, events: { estimated_parallel_wall_time: wall } };
    }
    if (key === 'round_postprocess') {
      const a = num((phases.tool_result_post || {}).total_ms);
      const b = num((phases.tool_to_next_api || {}).total_ms);
      return { total_ms: a + b, events: { tool_result_post: a, tool_to_next_api: b } };
    }
    return { total_ms: 0, events: {} };
  }

  function phaseLabel(key) {
    const hit = PHASE_DEFS.filter((item) => item[0] === key)[0];
    return hit ? t(hit[1], hit[2]) : key;
  }

  function toolWallMs(req) {
    const recorded = (req.phases || {}).tool_execution;
    if (recorded && num(recorded.total_ms) > 0) return num(recorded.total_ms);
    return (req.tools || []).reduce((max, tool) => Math.max(max, num(tool.duration_ms)), 0);
  }

  function runWallMs(run) {
    const wall = num(run.wall_ms);
    if (wall > 0) return wall;
    const start = Date.parse(run.started_at || '');
    const end = Date.parse(run.finished_at || '');
    if (!Number.isFinite(start)) return 0;
    return Math.max(0, (Number.isFinite(end) ? end : Date.now()) - start);
  }

  function flatten(payload, sessionId) {
    const rows = [];
    (payload.sessions || []).forEach((session) => {
      if (sessionId && session.session_id !== sessionId) return;
      (session.runs || []).forEach((run) => (run.requests || []).forEach((req) => rows.push({ session, run, req })));
    });
    rows.sort((a, b) => String(a.req.started_at || a.run.started_at || '')
      .localeCompare(String(b.req.started_at || b.run.started_at || '')));
    return rows;
  }

  function sample(rows) {
    if (rows.length <= CHART_POINT_LIMIT) return rows;
    const out = [];
    for (let i = 0; i < CHART_POINT_LIMIT; i += 1) {
      out.push(rows[Math.round((i * (rows.length - 1)) / (CHART_POINT_LIMIT - 1))]);
    }
    return out;
  }

  function runMergedRows(rows) {
    const runs = new Map();
    rows.forEach((row) => {
      const key = row.run.run_id || row.req.started_at;
      if (!runs.has(key)) runs.set(key, { session: row.session, run: row.run, reqs: [] });
      runs.get(key).reqs.push(row.req);
    });
    return Array.from(runs.values()).map((group) => {
      const last = group.reqs[group.reqs.length - 1] || {};
      return Object.assign({}, group, {
        req: {
          react_iter: group.reqs.length ? 1 : 0,
          started_at: (group.reqs[0] || {}).started_at || group.run.started_at,
          model: last.model || '',
          status: group.run.status || '',
        },
      });
    });
  }

  function reconcileRunStats(run, reqs) {
    const wall = runWallMs(run);
    let startup = reqs.reduce((n, r) => n + num(r.startup_ms), 0);
    if (!startup && reqs.length) {
      const first = Date.parse(reqs[0].started_at || '');
      const begin = Date.parse(run.started_at || '');
      if (Number.isFinite(first) && Number.isFinite(begin)) startup = Math.max(0, first - begin);
    }
    const reqWall = reqs.reduce((n, r) => n + (num(r.wall_ms) > 0
      ? num(r.wall_ms)
      : num(r.duration_ms) + num((r.phases || {}).pre_api && (r.phases || {}).pre_api.total_ms)
        + toolWallMs(r) + num(((r.phases || {}).round_postprocess || {}).total_ms)), 0);
    const roundGap = reqs.reduce((n, r) => n + num(r.round_gap_ms), 0);
    const finalPipe = reqs.reduce((n, r) => n + num(((r.phases || {}).final_pipeline || {}).total_ms), 0);
    const api = reqs.reduce((n, r) => n + num(r.duration_ms), 0);
    const toolWall = reqs.reduce((n, r) => n + toolWallMs(r), 0);
    const known = startup + reqWall + roundGap + finalPipe;
    return { wall, startup, reqWall, roundGap, finalPipe, api, toolWall, residual: Math.max(0, wall - known) };
  }

  function runWallTotal(rows) {
    const seen = new Set();
    let total = 0;
    rows.forEach((row) => {
      const key = String(row.run.run_id || '') + '|' + String(row.req.started_at || '');
      if (seen.has(key)) return;
      seen.add(key);
      total += runWallMs(row.run);
    });
    return total;
  }

  /* ── 折线图 ─────────────────────────────────────────────────────────── */
  function drawLineChart(host, rows, series, unit, state, redraw) {
    host.innerHTML = '';
    if (!rows.length || !series.length) {
      host.innerHTML = '<div class="st-ud-empty">' + t('暂无数据', 'No data') + '</div>';
      return;
    }
    const selected = state.legend.get(host.id) || '';
    const list = series.map((item, index) => Object.assign(
      { axis: 'left', unit: unit || '', color: SERIES_COLORS[index % SERIES_COLORS.length] }, item));
    const visible = selected ? list.filter((item) => item.name === selected) : list;
    const left = visible.filter((item) => item.axis !== 'right');
    const right = visible.filter((item) => item.axis === 'right');
    const peak = (items) => Math.max(1, ...rows.flatMap((row) => items.map((item) => num(item.value(row)))));
    const maxLeft = peak(left);
    const maxRight = peak(right);
    const hasRight = list.some((item) => item.axis === 'right');
    const H = 250;
    const pad = { t: 18, b: 44 };
    const axisWidth = hasRight ? 118 : 60;
    // 设置页里横向滚动很难用，直接铺满容器宽度，点再密也看得清趋势。
    // clientWidth 含左右 padding（24px），不减掉会让 svg 顶出内容区、右边被裁。
    const width = Math.max(300, host.clientWidth - axisWidth - 32);
    const x = (index) => 10 + (rows.length === 1 ? 0.5 : index / (rows.length - 1)) * (width - 20);
    const y = (value, max) => H - pad.b - (num(value) / max) * (H - pad.t - pad.b);

    let svg = '<svg viewBox="0 0 ' + width + ' ' + H + '" width="' + width + '" height="' + H + '" role="img">';
    for (let i = 0; i <= 4; i += 1) {
      const yy = y(i / 4, 1);
      svg += '<line x1="0" y1="' + yy + '" x2="' + width + '" y2="' + yy + '" class="st-ud-grid"/>';
    }
    list.forEach((item) => {
      const max = item.axis === 'right' ? maxRight : maxLeft;
      const dim = selected && item.name !== selected;
      const points = rows.map((row, index) => x(index) + ',' + y(item.value(row), max)).join(' ');
      svg += '<polyline points="' + points + '" fill="none" stroke="' + item.color +
        '" stroke-width="' + (dim ? 1 : 2) + '" opacity="' + (dim ? 0.15 : 1) + '"/>';
      rows.forEach((row, index) => {
        const tip = {
          metric: item.name,
          display: format(item.value(row), item.unit),
          time: row.req.started_at || row.run.started_at || '',
          iter: row.reqs ? 'Run · ' + row.reqs.length + ' 轮' : 'LLM #' + row.req.react_iter,
          model: row.req.model || '',
        };
        svg += '<circle class="st-ud-point" data-tip="' + esc(JSON.stringify(tip)) + '" cx="' + x(index) +
          '" cy="' + y(item.value(row), max) + '" r="3.5" fill="' + item.color + '" opacity="' + (dim ? 0.12 : 1) + '"/>';
      });
    });
    // 一个会话里 Run 会重新计数，x 轴标注 Run 序号比 react_iter 更好认。
    const runIndex = new Map();
    rows.forEach((row) => {
      const key = row.run.run_id || row.req.started_at;
      if (!runIndex.has(key)) runIndex.set(key, runIndex.size + 1);
    });
    const firstAt = Date.parse((rows[0].req || {}).started_at || '');
    const lastAt = Date.parse((rows[rows.length - 1].req || {}).started_at || '');
    const multiDay = Number.isFinite(firstAt) && Number.isFinite(lastAt) && Math.abs(lastAt - firstAt) > 86400000;
    rows.forEach((row, index) => {
      const step = Math.ceil(rows.length / 8);
      if (rows.length > 12 && index % step !== 0 && index !== rows.length - 1) return;
      const when = new Date(row.req.started_at || row.run.started_at || '');
      const stamp = multiDay
        ? (when.getMonth() + 1) + '-' + String(when.getDate()).padStart(2, '0')
        : when.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const anchor = index === 0 ? 'start' : index === rows.length - 1 ? 'end' : 'middle';
      svg += '<text x="' + x(index) + '" y="' + (H - 24) + '" text-anchor="' + anchor + '">' + esc(stamp) + '</text>';
      svg += '<text x="' + x(index) + '" y="' + (H - 8) + '" text-anchor="' + anchor + '">' +
        esc('Run ' + (runIndex.get(row.run.run_id || row.req.started_at) || 1)) + '</text>';
    });
    svg += '</svg>';

    const axis = (side, max, item, enabled) => '<div class="st-ud-axis st-ud-axis--' + side + '">' + (enabled
      ? [0, 1, 2, 3, 4].map((i) => '<span style="top:' + y((max * i) / 4, max) + 'px">' +
        esc(axisLabel((max * i) / 4, item.unit)) + '</span>').join('')
      : '') + '</div>';
    const legend = '<div class="st-ud-legend">' + list.map((item) =>
      '<button type="button" data-series="' + esc(item.name) + '" class="' +
      (selected === item.name ? 'is-on' : selected ? 'is-dim' : '') + '"><i style="background:' + item.color + '"></i>' +
      esc(item.name) + '</button>').join('') + '</div>';

    host.innerHTML = '<div class="st-ud-stage">' +
      axis('left', maxLeft, (left[0] || visible[0] || list[0]), left.length > 0) +
      '<div class="st-ud-scroll">' + svg + '</div>' +
      (hasRight ? axis('right', maxRight, (right[0] || list.find((i) => i.axis === 'right')), right.length > 0) : '') +
      '</div>' + legend;
    host.querySelectorAll('.st-ud-legend button').forEach((button) => {
      button.onclick = () => {
        state.legend.set(host.id, selected === button.dataset.series ? '' : button.dataset.series);
        redraw();
      };
    });
  }

  /* ── 事件/阶段/工具 ─────────────────────────────────────────────────── */
  function eventsHtml(events) {
    if (Array.isArray(events)) {
      return events.map((item) => '<div class="st-ud-row"><span>' + esc(item.step || 'event') + '</span><b>' +
        esc(ms(item.ms_since_api_start)) + '</b><small>' +
        esc(Object.keys(item).filter((key) => !['step', 'ms_since_api_start', 'model'].includes(key))
          .map((key) => key + '=' + item[key]).join(' · ')) + '</small></div>').join('') ||
        '<div class="st-ud-empty-inline">' + t('暂无子事件', 'No events') + '</div>';
    }
    const keys = Object.keys(events || {});
    return keys.length ? keys.map((key) => '<div class="st-ud-row"><span>' + esc(key) + '</span><b>' +
      esc(ms(events[key])) + '</b></div>').join('')
      : '<div class="st-ud-empty-inline">' + t('暂无子事件', 'No events') + '</div>';
  }

  function detailsHtml(openState, key, summary, inner, opened) {
    if (openState.has(key)) opened = openState.get(key);
    return '<details class="st-ud-fold" data-open-key="' + esc(key) + '"' + (opened ? ' open' : '') +
      '><summary>' + summary + '</summary><div>' + inner + '</div></details>';
  }

  function toolRows(req) {
    return (req.tools || []).map((tool) => '<div class="st-ud-row"><span>' + esc(tool.tool || 'tool') +
      '</span><b>' + esc(ms(tool.duration_ms)) + '</b><small>' +
      esc(tool.failed ? t('失败', 'failed') : t('成功', 'ok')) + '</small></div>').join('');
  }

  /* ── 顶部数字 ───────────────────────────────────────────────────────── */
  function topCards(rows) {
    const input = rows.reduce((n, r) => n + num((r.req.usage || {}).prompt_tokens || (r.req.context || {}).estimated_tokens), 0);
    const output = rows.reduce((n, r) => n + num((r.req.usage || {}).completion_tokens), 0);
    const api = rows.reduce((n, r) => n + num(r.req.duration_ms), 0);
    const tools = rows.reduce((n, r) => n + (r.req.tools || []).length, 0);
    const ttft = rows.filter((r) => Number.isFinite(Number(r.req.first_token_ms)) && num(r.req.first_token_ms) > 0);
    const traffic = rows.reduce((n, r) => {
      const net = r.req.network || {};
      return n + num(net.request_bytes) + num(net.response_payload_bytes_estimated || net.response_content_length);
    }, 0);
    const cards = [
      [t('LLM 请求', 'Requests'), rows.length.toLocaleString()],
      [t('Run 墙钟', 'Run wall'), ms(runWallTotal(rows))],
      [t('API 流累计', 'API stream'), ms(api)],
      [t('平均首 token', 'Avg first token'), ttft.length ? ms(ttft.reduce((n, r) => n + num(r.req.first_token_ms), 0) / ttft.length) : '—'],
      [t('累计输入', 'Input tokens'), input.toLocaleString()],
      [t('累计输出', 'Output tokens'), output.toLocaleString()],
      [t('工具调用', 'Tool calls'), tools.toLocaleString()],
      [t('网络流量', 'Traffic'), bytes(traffic)],
    ];
    return '<div class="st-usage-sum st-ud-cards">' + cards.map(([label, value]) =>
      '<div class="cell"><div class="v">' + esc(String(value)) + '</div><div class="l">' + esc(label) + '</div></div>').join('') + '</div>';
  }

  /* ── 主渲染 ─────────────────────────────────────────────────────────── */
  function render(host, payload, options) {
    const opts = options || {};
    const rows = flatten(payload || {}, opts.sessionId);
    const observed = ((payload || {}).sessions || [])[0] || {};
    const observedRuns = (observed.observability || {}).runs || [];
    const previous = detailOpenStates.get(host);
    const state = { legend: new Map(), phaseMode: 'round', toolMode: 'count',
      open: previous && previous.sessionId === opts.sessionId ? previous.open : new Map() };
    detailOpenStates.set(host, { sessionId: opts.sessionId, open: state.open });
    let selected = '__all__';

    if (!rows.length) {
      host.innerHTML = '<div class="st-ud-empty">' + t('这个会话还没有执行统计。', 'No execution metrics for this session yet.') + '</div>';
      return function () {};
    }

    const runIds = new Set(rows.map((row) => row.run.run_id || row.req.started_at));
    const fileCount = observedRuns.reduce((n, run) => n + (run.file_changes || []).length, 0);
    host.innerHTML =
      '<div class="st-ud-meta">' + rows.length.toLocaleString() + t(' 次请求 · ', ' requests · ') +
        runIds.size + t(' 个 Run · ', ' runs · ') +
        t('文件变更 ', 'file changes ') + fileCount.toLocaleString() + '</div>' +
      topCards(rows) +
      '<div class="st-ud-grid">' +
        '<article class="st-card"><div class="st-card-head"><span class="st-t">' + t('Token 曲线', 'Tokens') +
          '</span><span class="st-h">' + t('累计输入 / 输出与上下文长度', 'Cumulative input, output and context') +
          '</span></div><div class="st-ud-chart" id="st-ud-api"></div></article>' +
        '<article class="st-card"><div class="st-card-head"><span class="st-t">' + t('阶段耗时', 'Phase timing') +
          '</span><div class="st-acts"><select data-ud="phase-mode" class="st-input sm">' +
          '<option value="round">' + t('按轮次', 'Per round') + '</option>' +
          '<option value="run">' + t('按 Run 合并', 'Per run') + '</option></select></div></div>' +
          '<div class="st-ud-chart" id="st-ud-phase"></div></article>' +
        '<article class="st-card"><div class="st-card-head"><span class="st-t">' + t('工具统计', 'Tools') +
          '</span><div class="st-acts"><select data-ud="tool-mode" class="st-input sm">' +
          '<option value="count">' + t('调用次数', 'Calls') + '</option>' +
          '<option value="duration">' + t('累计耗时', 'Duration') + '</option></select></div></div>' +
          '<div class="st-ud-chart" id="st-ud-tool"></div></article>' +
        '<article class="st-card"><div class="st-card-head"><span class="st-t">' + t('网络', 'Network') +
          '</span><span class="st-h">' + t('左轴耗时 · 右轴流量', 'Left: time · right: bytes') +
          '</span></div><div class="st-ud-chart" id="st-ud-net"></div></article>' +
      '</div>' +
      '<div class="st-ud-toolbar"><div><h3>' + t('轮次明细', 'Rounds') +
        '</h3><span>' + t('点开看阶段与工具', 'Expand for phases and tools') + '</span></div>' +
        '<label>' + t('范围', 'Scope') + '<select data-ud="scope" class="st-input sm">' +
        '<option value="__all__">' + t('累计总值', 'All rounds') + '</option>' +
        rows.slice().reverse().map((row) => '<option value="' +
          esc([row.run.run_id || '', row.req.react_iter].join('|')) + '">' +
          esc('LLM #' + row.req.react_iter + ' · ' + new Date(row.req.started_at || row.run.started_at || '').toLocaleString()) +
          '</option>').join('') + '</select></label></div>' +
      '<div data-ud="detail"></div>' +
      '<div class="st-ud-tip" hidden></div>';

    const apiEl = host.querySelector('#st-ud-api');
    const phaseEl = host.querySelector('#st-ud-phase');
    const toolEl = host.querySelector('#st-ud-tool');
    const netEl = host.querySelector('#st-ud-net');
    const detailEl = host.querySelector('[data-ud="detail"]');

    function renderCharts() {
      let cumulativeIn = 0;
      let cumulativeOut = 0;
      const cumulativeRows = sample(rows.map((row) => {
        cumulativeIn += num((row.req.usage || {}).prompt_tokens || (row.req.context || {}).estimated_tokens);
        cumulativeOut += num((row.req.usage || {}).completion_tokens);
        return Object.assign({}, row, { cumulativeInput: cumulativeIn, cumulativeOutput: cumulativeOut });
      }));
      drawLineChart(apiEl, cumulativeRows, [
        { name: t('累计输入 token', 'Input tokens'), value: (r) => r.cumulativeInput },
        { name: t('累计输出 token', 'Output tokens'), value: (r) => r.cumulativeOutput },
        { name: t('上下文长度', 'Context'), value: (r) => num((r.req.context || {}).estimated_tokens) },
      ], '', state, renderCharts);

      const phaseRows = sample(state.phaseMode === 'run' ? runMergedRows(rows) : rows);
      drawLineChart(phaseEl, phaseRows, PHASE_DEFS.map(([key]) => ({
        name: phaseLabel(key),
        value: (row) => (row.reqs
          ? row.reqs.reduce((n, req) => n + num(phaseData(req, key).total_ms), 0)
          : num(phaseData(row.req, key).total_ms)),
      })), 'ms', state, renderCharts);

      const names = [];
      rows.forEach((row) => (row.req.tools || []).forEach((tool) => {
        const name = String(tool.tool || 'tool');
        if (!names.includes(name)) names.push(name);
      }));
      const totals = {};
      const toolRowsData = sample(rows.map((row) => {
        (row.req.tools || []).forEach((tool) => {
          const name = String(tool.tool || 'tool');
          totals[name] = (totals[name] || 0) + (state.toolMode === 'duration' ? num(tool.duration_ms) : 1);
        });
        return Object.assign({}, row, { toolTotals: Object.assign({}, totals) });
      }));
      drawLineChart(toolEl, toolRowsData, names.map((name) => ({
        name, value: (row) => num(row.toolTotals[name]),
      })), state.toolMode === 'duration' ? 'ms' : '', state, renderCharts);

      drawLineChart(netEl, sample(rows), [
        { name: t('请求至首 token', 'Request → first token'), axis: 'left', unit: 'ms',
          value: (r) => num((r.req.network || {}).request_to_first_token_ms || r.req.first_token_ms) },
        { name: t('Transport 总耗时', 'Transport'), axis: 'left', unit: 'ms',
          value: (r) => num((r.req.network || {}).transport_elapsed_ms) },
        { name: t('请求流量', 'Request bytes'), axis: 'right', unit: 'B',
          value: (r) => num((r.req.network || {}).request_bytes) },
        { name: t('响应流量', 'Response bytes'), axis: 'right', unit: 'B',
          value: (r) => num((r.req.network || {}).response_payload_bytes_estimated || (r.req.network || {}).response_content_length) },
      ], 'ms', state, renderCharts);
    }

    function reconcileTable(groups) {
      // 一百来个 Run 逐个展开是噪音，压成一张表，只留最近 30 个。
      const limit = 30;
      const shown = groups.slice(-limit);
      const head = ['Run', t('轮数', 'Rounds'), t('墙钟', 'Wall'), t('API 流', 'API'),
        t('工具', 'Tools'), t('残差', 'Residual')];
      const body = shown.map((group, index) => {
        const stats = reconcileRunStats(group.run, group.reqs);
        const ordinal = groups.length - shown.length + index + 1;
        return '<tr><td title="' + esc(group.run.run_id || '') + '">Run ' + ordinal + ' · ' +
          esc(String(group.run.run_id || '').slice(0, 8)) + '</td>' +
          '<td>' + group.reqs.length + '</td>' +
          '<td>' + esc(ms(stats.wall)) + '</td>' +
          '<td>' + esc(ms(stats.api)) + '</td>' +
          '<td>' + esc(ms(stats.toolWall)) + '</td>' +
          '<td>' + esc(ms(stats.residual)) + '</td></tr>';
      }).join('');
      return (groups.length > limit
        ? '<div class="st-ud-meta">' + t('共 ' + groups.length + ' 个 Run，显示最近 ' + limit + ' 个',
            'Showing the last ' + limit + ' of ' + groups.length + ' runs') + '</div>'
        : '') +
        '<table class="st-usage-table"><thead><tr>' +
        head.map((cell) => '<th>' + esc(cell) + '</th>').join('') +
        '</tr></thead><tbody>' + body + '</tbody></table>';
    }

    function cumulativeDetail() {
      const phaseTotals = {};
      const phaseEvents = {};
      rows.forEach((row) => PHASE_DEFS.forEach(([name]) => {
        const phase = phaseData(row.req, name);
        phaseTotals[name] = (phaseTotals[name] || 0) + num(phase.total_ms);
        phaseEvents[name] = phaseEvents[name] || {};
        Object.entries(phase.events || {}).forEach(([event, value]) => {
          phaseEvents[name][event] = (phaseEvents[name][event] || 0) + num(value);
        });
      }));
      const all = Object.values(phaseTotals).reduce((n, v) => n + num(v), 0);
      const groups = new Map();
      rows.forEach((row) => {
        const key = row.run.run_id || row.req.started_at;
        if (!groups.has(key)) groups.set(key, { run: row.run, reqs: [] });
        groups.get(key).reqs.push(row.req);
      });
      const reconcile = reconcileTable(Array.from(groups.values()));
      const phases = PHASE_DEFS.map(([name]) => {
        const total = num(phaseTotals[name]);
        const events = Object.entries(phaseEvents[name] || {}).map(([event, value]) =>
          '<div class="st-ud-row st-ud-row--agg"><span>' + esc(event) + '</span><b>' +
          esc(t('平均 ', 'avg ') + ms(value / rows.length)) + '</b><small>' +
          esc(t('累计 ', 'total ') + ms(value)) + ' · ' +
          (total ? ((value / total) * 100).toFixed(1) : '0.0') + '%</small></div>').join('') ||
          '<div class="st-ud-empty-inline">' + t('暂无子事件', 'No events') + '</div>';
        return detailsHtml(state.open, 'total|' + name, '<span>' + esc(phaseLabel(name)) + '</span><b>' +
          esc(t('平均 ', 'avg ') + ms(total / rows.length)) + ' · ' + (all ? ((total / all) * 100).toFixed(1) : '0.0') + '%</b>',
          events, false);
      }).join('');
      return '<div class="st-ud-section-title">' + t('Run 对账', 'Run reconciliation') +
        '<span>' + t('残差 = 墙钟里没被任何阶段计入的部分', 'Residual = wall time no phase accounted for') + '</span></div>' +
        reconcile +
        '<div class="st-ud-section-title">' + t('阶段累计', 'Phase totals') +
        '<span>' + rows.length + t(' 次请求', ' requests') + '</span></div>' + phases;
    }

    function singleDetail(row) {
      const { run, req } = row;
      const phases = PHASE_DEFS.map(([name]) => detailsHtml(state.open,
        [run.run_id, req.react_iter, name].join('|'),
        '<span>' + esc(phaseLabel(name)) + '</span><b>' + esc(ms(phaseData(req, name).total_ms)) + '</b>',
        eventsHtml(phaseData(req, name).events), name === 'llm_stream')).join('');
      const tools = (req.tools || []).length
        ? detailsHtml(state.open, [run.run_id, req.react_iter, 'tools'].join('|'),
          '<span>tools</span><b>' + req.tools.length + '</b>', toolRows(req), false)
        : '';
      const usage = req.usage || {};
      const ctx = req.context || {};
      return '<div class="st-ud-cards">' +
        [['LLM #' + req.react_iter, req.model || ''], [t('状态', 'Status'), req.status || '—'],
          [t('输入 token', 'Input'), num(usage.prompt_tokens || ctx.estimated_tokens).toLocaleString()],
          [t('输出 token', 'Output'), num(usage.completion_tokens).toLocaleString()],
          [t('上下文', 'Context'), num(ctx.estimated_tokens).toLocaleString() + ' / ' + num(ctx.context_window).toLocaleString()],
          [t('首 token', 'First token'), ms(req.first_token_ms)],
          [t('API 流耗时', 'API stream'), ms(req.duration_ms)],
          [t('工具调用', 'Tools'), (req.tools || []).length]]
          .map(([label, value]) => '<div><span>' + esc(String(label)) + '</span><b>' + esc(String(value)) + '</b></div>').join('') +
        '</div>' + phases + tools;
    }

    function renderDetail() {
      detailEl.innerHTML = selected === '__all__' ? cumulativeDetail() : (function () {
        const row = rows.filter((item) => [item.run.run_id || '', item.req.react_iter].join('|') === selected)[0];
        return row ? singleDetail(row) : cumulativeDetail();
      })();
      detailEl.querySelectorAll('details[data-open-key]').forEach((node) => {
        node.querySelector('summary').addEventListener('click', (event) => {
          event.preventDefault();
          const next = !node.open;
          state.open.set(node.dataset.openKey, next);
          node.open = next;
        });
      });
    }

    host.querySelector('[data-ud="phase-mode"]').onchange = (event) => {
      state.phaseMode = event.target.value;
      renderCharts();
    };
    host.querySelector('[data-ud="tool-mode"]').onchange = (event) => {
      state.toolMode = event.target.value;
      renderCharts();
    };
    host.querySelector('[data-ud="scope"]').onchange = (event) => {
      selected = event.target.value;
      renderDetail();
    };

    const tip = host.querySelector('.st-ud-tip');
    host.addEventListener('pointerover', (event) => {
      const point = event.target.closest && event.target.closest('.st-ud-point');
      if (!point) return;
      try {
        const data = JSON.parse(point.dataset.tip || '{}');
        tip.innerHTML = '<strong>' + esc(data.metric) + '</strong><b>' + esc(data.display) + '</b>' +
          '<dl><dt>' + t('时间', 'Time') + '</dt><dd>' + esc(data.time ? new Date(data.time).toLocaleString() : '—') +
          '</dd><dt>' + t('轮次', 'Round') + '</dt><dd>' + esc(data.iter) + '</dd><dt>' + t('模型', 'Model') +
          '</dt><dd>' + esc(data.model || '—') + '</dd></dl>';
        tip.hidden = false;
        const box = host.getBoundingClientRect();
        tip.style.left = Math.max(8, Math.min(box.width - 240, event.clientX - box.left + 12)) + 'px';
        tip.style.top = Math.max(8, event.clientY - box.top + 12) + 'px';
      } catch (error) { /* 忽略坏数据 */ }
    });
    host.addEventListener('pointerout', (event) => {
      if (event.target.closest && event.target.closest('.st-ud-point')) tip.hidden = true;
    });

    renderCharts();
    renderDetail();
    return function () { host.innerHTML = ''; };
  }

  window.MyAgentUsageDetail = { render: render };
})();
