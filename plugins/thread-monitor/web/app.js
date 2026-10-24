/* 线程监控面板：只读轮询 /api/thread-monitor 并渲染两组指标。 */
(function () {
  'use strict';

  var API = '/api/thread-monitor';
  var HISTORY = 120;
  var INTERVAL_KEY = 'thread-monitor-interval';

  var state = {
    intervalMs: 2000,
    timer: null,
    paused: false,
    busy: false,
    data: null,
    filter: '',
  };

  var ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (ch) { return ESCAPES[ch]; });
  }

  function num(value) {
    var n = Number(value);
    return Number.isFinite(n) ? n : 0;
  }

  function fmt(value, digits) {
    var n = Number(value);
    if (!Number.isFinite(n)) return '—';
    return n.toLocaleString('en-US', {
      minimumFractionDigits: digits || 0,
      maximumFractionDigits: digits || 0,
    });
  }

  function clock(seconds) {
    var s = Math.max(0, Math.round(Number(seconds) || 0));
    if (s < 60) return s + ' 秒';
    var m = Math.floor(s / 60);
    if (m < 60) return m + ' 分 ' + (s % 60) + ' 秒';
    var h = Math.floor(m / 60);
    if (h < 24) return h + ' 小时 ' + (m % 60) + ' 分';
    return Math.floor(h / 24) + ' 天 ' + (h % 24) + ' 小时';
  }

  function timeLabel(ts) {
    var d = new Date(Number(ts) * 1000);
    if (isNaN(d.getTime())) return '';
    return d.toTimeString().slice(0, 8);
  }

  function $(id) {
    return document.getElementById(id);
  }

  /* ── 渲染 ───────────────────────────────────────────────────────── */

  function renderKpis(data) {
    var runs = data.concurrency || {};
    var ratio = data.threads_per_run;
    var cards = [
      {
        label: '进程 OS 线程',
        value: fmt(data.thread_total),
        hint: '增量 ' + (num(data.delta_threads) > 0 ? '+' : '') + fmt(data.delta_threads)
          + ' · 峰值 ' + fmt(data.peak_threads) + ' · 基线 ' + fmt(data.baseline_threads),
        tone: num(data.delta_threads) > 0 ? 'up' : '',
      },
      {
        label: '业务并发',
        value: fmt(runs.total),
        hint: '会话 ' + fmt(runs.root_runs) + ' · 子代理 ' + fmt(runs.subagent_runs)
          + ' · 后台任务 ' + fmt(runs.background_jobs) + ' · 终端 ' + fmt(runs.terminals)
          + ' · 团队 ' + fmt(runs.active_team_sessions),
        tone: '',
      },
      {
        label: '线程 / 并发',
        value: ratio == null ? '—' : fmt(ratio, 2),
        hint: ratio == null ? '当前没有活动运行' : '每个活动运行平均占用线程数',
        tone: '',
      },
      {
        label: '待处理交互',
        value: fmt(runs.pending_interactions),
        hint: '提问 + 审批（不计入并发总数）',
        tone: num(runs.pending_interactions) > 0 ? 'warn' : '',
      },
    ];
    $('kpis').innerHTML = cards.map(function (card) {
      return '<div class="tm-kpi ' + (card.tone ? 'tm-kpi--' + card.tone : '') + '">'
        + '<span class="tm-kpi-label">' + esc(card.label) + '</span>'
        + '<b class="tm-kpi-value">' + esc(card.value) + '</b>'
        + '<span class="tm-kpi-hint">' + esc(card.hint) + '</span>'
        + '</div>';
    }).join('');
  }

  function renderTrend(data) {
    var rows = Array.isArray(data.history) ? data.history : [];
    var box = $('trend');
    if (rows.length < 2) {
      box.innerHTML = '<p class="tm-empty">采样不足，等待下一帧…</p>';
      $('trend-note').textContent = rows.length + ' 个采样点';
      return;
    }
    var w = 640;
    var h = 190;
    var padL = 36;
    var padR = 10;
    var padT = 12;
    var padB = 20;
    var threads = rows.map(function (row) { return num(row.thread_total); });
    var runs = rows.map(function (row) { return num(row.concurrency_total); });
    var max = Math.max(1, Math.max.apply(null, threads), Math.max.apply(null, runs));
    var stepX = (w - padL - padR) / (rows.length - 1);
    function y(value) {
      return padT + (h - padT - padB) * (1 - value / max);
    }
    function path(values) {
      return values.map(function (value, index) {
        return (index ? 'L' : 'M') + (padL + stepX * index).toFixed(1) + ',' + y(value).toFixed(1);
      }).join(' ');
    }
    var grid = [0, 0.5, 1].map(function (ratio) {
      var gy = padT + (h - padT - padB) * ratio;
      return '<line class="tm-gridline" x1="' + padL + '" y1="' + gy.toFixed(1) + '" x2="' + (w - padR)
        + '" y2="' + gy.toFixed(1) + '"></line>'
        + '<text class="tm-axis" x="' + (padL - 6) + '" y="' + (gy + 3.5).toFixed(1) + '" text-anchor="end">'
        + Math.round(max * (1 - ratio)) + '</text>';
    }).join('');
    var lastThreads = threads[threads.length - 1];
    var lastRuns = runs[runs.length - 1];
    var marker = '<circle class="tm-point" cx="' + (w - padR) + '" cy="' + y(lastThreads).toFixed(1)
      + '" r="3.4"></circle>';
    var axis = '<text class="tm-axis" x="' + padL + '" y="' + (h - 4) + '">' + esc(timeLabel(rows[0].timestamp)) + '</text>'
      + '<text class="tm-axis" x="' + (w - padR) + '" y="' + (h - 4) + '" text-anchor="end">'
      + esc(timeLabel(rows[rows.length - 1].timestamp)) + '</text>';
    box.innerHTML = '<svg viewBox="0 0 ' + w + ' ' + h + '" role="img" '
      + 'aria-label="线程总数与业务并发趋势">'
      + grid + axis
      + '<path class="tm-line tm-line--runs" d="' + path(runs) + '"></path>'
      + '<path class="tm-line tm-line--threads" d="' + path(threads) + '"></path>'
      + marker
      + '</svg>';
    $('trend-note').textContent = rows.length + ' 个采样点 · 现在 ' + lastThreads + ' 线程 / '
      + lastRuns + ' 并发';
  }

  function renderGroups(data) {
    var rows = Array.isArray(data.thread_groups) ? data.thread_groups : [];
    var box = $('groups');
    if (!rows.length) {
      box.innerHTML = '<p class="tm-empty">暂无分组</p>';
      return;
    }
    var max = Math.max.apply(null, rows.map(function (row) { return num(row.count); }));
    box.innerHTML = rows.map(function (row) {
      var width = max > 0 ? Math.max(2, (num(row.count) / max) * 100) : 0;
      return '<div class="tm-bar">'
        + '<div class="tm-bar-head"><code>' + esc(row.group) + '</code><b>' + fmt(row.count) + '</b></div>'
        + '<div class="tm-bar-track"><span style="width:' + width.toFixed(1) + '%"></span></div>'
        + '<div class="tm-bar-foot">累计 CPU ' + fmt(row.cpu_seconds, 1) + ' 秒</div>'
        + '</div>';
    }).join('');
  }

  function renderThreads(data) {
    var rows = Array.isArray(data.threads) ? data.threads : [];
    var needle = state.filter.trim().toLowerCase();
    if (needle) {
      rows = rows.filter(function (row) {
        return (String(row.name) + ' ' + String(row.group)).toLowerCase().indexOf(needle) >= 0;
      });
    }
    var body = $('threads');
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="5" class="tm-empty-cell">没有匹配的线程</td></tr>';
      return;
    }
    body.innerHTML = rows.map(function (row) {
      return '<tr>'
        + '<td class="tm-mono">' + fmt(row.thread_id) + '</td>'
        + '<td class="tm-mono">' + esc(row.name) + '</td>'
        + '<td><span class="tm-chip">' + esc(row.group) + '</span></td>'
        + '<td>' + (row.daemon ? '是' : '否') + '</td>'
        + '<td class="tm-num tm-mono">' + fmt(row.cpu_seconds, 2) + '</td>'
        + '</tr>';
    }).join('');
  }

  function renderLeaks(data) {
    var rows = Array.isArray(data.suspected_leaks) ? data.suspected_leaks : [];
    $('leak-note').textContent = '存活超过 ' + clock(data.leak_suspect_seconds) + ' 的线程';
    var box = $('leaks');
    if (!rows.length) {
      box.innerHTML = '<p class="tm-empty">没有超过阈值的线程</p>';
      return;
    }
    box.innerHTML = rows.map(function (row) {
      return '<div class="tm-leak">'
        + '<div><code>' + esc(row.name) + '</code><span class="tm-chip">' + esc(row.group) + '</span></div>'
        + '<b>' + clock(row.alive_seconds) + '</b>'
        + '</div>';
    }).join('');
  }

  function renderProcess(data) {
    var process = data.process || {};
    var facts = [
      ['PID', fmt(process.pid)],
      ['进程线程数（psutil）', fmt(process.num_threads)],
      ['进程运行时长', process.uptime_seconds == null ? '—' : clock(process.uptime_seconds)],
      ['常驻内存', process.rss_mb == null ? '—' : fmt(process.rss_mb, 1) + ' MB'],
      ['采样器运行时长', process.monitor_uptime_seconds == null ? '—' : clock(process.monitor_uptime_seconds)],
      ['采样间隔', fmt(data.interval_seconds, 2) + ' 秒'],
      ['最后采样', timeLabel(data.timestamp)],
    ];
    $('process').innerHTML = facts.map(function (row) {
      return '<div><dt>' + esc(row[0]) + '</dt><dd>' + esc(row[1]) + '</dd></div>';
    }).join('');
  }

  function renderNotice(data) {
    var box = $('notice');
    var errors = Array.isArray(data && data.errors) ? data.errors : [];
    if (!errors.length) {
      box.hidden = true;
      box.textContent = '';
      return;
    }
    box.hidden = false;
    box.textContent = '部分数据源不可用：' + errors.slice(0, 3).join('；');
  }

  function render(data) {
    state.data = data;
    renderKpis(data);
    renderTrend(data);
    renderGroups(data);
    renderThreads(data);
    renderLeaks(data);
    renderProcess(data);
    renderNotice(data);
    document.title = fmt(data.thread_total) + ' 线程 · 线程监控';
  }

  function renderFailure(message) {
    var box = $('notice');
    box.hidden = false;
    box.textContent = message;
  }

  /* ── 轮询 ───────────────────────────────────────────────────────── */

  function applyInterval(value) {
    var ms = Math.max(500, Math.min(30000, Number(value) || 2000));
    state.intervalMs = ms;
    try {
      localStorage.setItem(INTERVAL_KEY, String(ms));
    } catch (error) { /* 隐私模式下写不进去，忽略 */ }
    restart();
  }

  function restart() {
    if (state.timer) clearInterval(state.timer);
    state.timer = null;
    if (state.paused || document.hidden || window.MyAgentPluginPage?.visible === false) return;
    state.timer = setInterval(refresh, state.intervalMs);
  }

  async function refresh() {
    if (state.busy) return;
    state.busy = true;
    try {
      var response = await fetch(API + '?history=' + HISTORY, { cache: 'no-store' });
      var payload = await response.json();
      if (!response.ok || !payload || payload.ok !== true) {
        var reason = payload && (payload.message || payload.error);
        throw new Error(reason || ('HTTP ' + response.status));
      }
      render(payload.data || {});
    } catch (error) {
      renderFailure('读取线程数据失败：' + (error && error.message ? error.message : String(error)));
    } finally {
      state.busy = false;
    }
  }

  async function resetBaseline() {
    var button = $('reset');
    button.disabled = true;
    try {
      var response = await fetch(API + '/reset', { method: 'POST', cache: 'no-store' });
      var payload = await response.json();
      if (!response.ok || !payload || payload.ok !== true) {
        throw new Error((payload && (payload.message || payload.error)) || ('HTTP ' + response.status));
      }
      render(payload.data || {});
    } catch (error) {
      renderFailure('重置失败：' + (error && error.message ? error.message : String(error)));
    } finally {
      button.disabled = false;
    }
  }

  function togglePause() {
    state.paused = !state.paused;
    $('pause').textContent = state.paused ? '继续' : '暂停';
    $('pause').classList.toggle('is-paused', state.paused);
    restart();
    if (!state.paused) refresh();
  }

  function bind() {
    var saved = 0;
    try {
      saved = Number(localStorage.getItem(INTERVAL_KEY)) || 0;
    } catch (error) {
      saved = 0;
    }
    var select = $('interval');
    if (saved && [1000, 2000, 5000, 10000].indexOf(saved) >= 0) select.value = String(saved);
    state.intervalMs = Number(select.value) || 2000;

    select.addEventListener('change', function () { applyInterval(select.value); });
    $('refresh').addEventListener('click', refresh);
    $('reset').addEventListener('click', resetBaseline);
    $('pause').addEventListener('click', togglePause);
    $('back').addEventListener('click', function () { window.location.href = '/'; });
    $('filter').addEventListener('input', function (event) {
      state.filter = String(event.target.value || '');
      if (state.data) renderThreads(state.data);
    });
    document.addEventListener('visibilitychange', function () {
      restart();
      if (!document.hidden && !state.paused) refresh();
    });
    document.addEventListener('myagent:plugin-page-visibility', function (event) {
      restart();
      if (event.detail.visible && !state.paused) refresh();
    });
  }

  bind();
  refresh();
  restart();
})();
