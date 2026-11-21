/* Native scheduled tasks: the settings view uses the existing control backend. */
(function () {
  'use strict';
  const A = window.MyAgentSettings;
  const { t, esc, W, api, toast, reportError, openDialog, askConfirm } = A;
  const boot = A.bootSection || {};
  let data = { items: [], sessions: [], profiles: [] };
  let statusFilter = 'all';
  const key = () => window.crypto?.randomUUID?.() || (Date.now() + '-' + Math.random().toString(36).slice(2));

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
  const labels = () => ({ at: t('仅一次', 'Once'), interval: t('固定间隔', 'Fixed interval'),
    daily: t('每天', 'Every day'), weekdays: t('工作日', 'Weekdays'), weekly: t('每周', 'Weekly'),
    monthly: t('每月', 'Monthly'), cron: t('自定义 Cron', 'Custom Cron'), after: t('延迟一次', 'After a delay') });
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
  function taskState(row) {
    if (row.last_error) return 'error';
    if (row.completed) return 'ended';
    return row.enabled ? 'active' : 'paused';
  }
  function stateChip(row) {
    return row.last_error ? W.status('warn', t('需要处理', 'Needs attention')) : row.completed ? W.chip(t('已结束', 'Finished')) :
      row.enabled ? W.status('ok', t('已启用', 'Enabled')) : W.chip(t('已暂停', 'Paused'));
  }
  function applyStatusFilter() {
    const body = document.getElementById('st-body');
    if (!body) return;
    const q = String(A.search || '').toLowerCase();
    body.querySelectorAll('[data-act="schedule-filter"]').forEach(el => el.classList.toggle('is-on', el.dataset.val === statusFilter));
    body.querySelectorAll('.st-schedule-row').forEach(row => {
      const searched = !!q && !String(row.dataset.searchText || '').toLowerCase().includes(q);
      row.hidden = searched || (statusFilter !== 'all' && row.dataset.status !== statusFilter);
    });
    const rows = [...body.querySelectorAll('.st-schedule-row')];
    const none = body.querySelector('[data-schedule-none]');
    if (none) none.hidden = rows.some(row => !row.hidden);
  }
  function list(d) {
    const rows = d.items.map(row => {
      const session = d.sessions.find(s => s.id === row.target.session_id);
      const target = row.target.mode === 'new' ? t('每次新建会话', 'New chat each run')
        : row.target.mode === 'new_once' ? t('新建并复用会话', 'Create once and reuse')
          : (session?.name || row.target.session_id);
      return '<article class="st-schedule-item st-schedule-row" data-status="' + taskState(row) +
        '" data-search-text="' + esc(row.name + ' ' + row.action.text + ' ' + (row.target.session_id || '')) + '">' +
        '<div class="st-schedule-row-main"><div class="st-schedule-row-title"><h3>' + esc(row.name) + '</h3>' + stateChip(row) + '</div>' +
        '<div class="st-schedule-row-sub"><span>' + esc(repeatText(row)) + '</span><span>' + esc(row.trigger.time_zone || 'Asia/Shanghai') +
        '</span><span>' + t('下次 ', 'Next ') + esc(date(row.next_run_at, row.trigger.time_zone)) + '</span><span>' + esc(target) + '</span></div>' +
        (row.last_error ? '<p class="st-schedule-error">' + esc(row.last_error.message) + '</p>' : '') + '</div>' +
        '<div class="st-schedule-row-actions">' + button(t('编辑', 'Edit'), 'schedule-edit', row.id) +
        button(t('运行', 'Run'), 'schedule-run', row.id) + (!row.completed ? button(row.enabled ? t('暂停', 'Pause') : t('启用', 'Enable'), 'schedule-toggle', row.id) : '') +
        button(t('记录', 'History'), 'schedule-history', row.id) + button(t('删除', 'Delete'), 'schedule-delete', row.id, 'text sm danger') + '</div></article>';
    }).join('');
    const filters = [['active', t('已启用', 'Active')], ['paused', t('已暂停', 'Paused')], ['ended', t('已结束', 'Ended')], ['all', t('全部', 'All')]]
      .map(([value, label]) => W.btn(label, 'schedule-filter', 'sm' + (statusFilter === value ? ' is-on' : ''), 'data-val="' + value + '"')).join('');
    return '<div class="st-schedule-toolbar"><div class="st-schedule-filters">' + filters + '</div><div class="st-acts">' +
      W.btn(t('刷新', 'Refresh'), 'schedule-refresh', 'sm') + W.btn(t('新建任务', 'New task'), 'schedule-new', 'primary sm') + '</div></div>' +
      (rows || '<div class="st-schedule-empty">' + A.icon('schedules', 30) + '<h3>' + t('把重复的事情交给 Agent', 'Let your agent handle recurring work') +
        '</h3><p>' + t('设置任务内容和时间，后端会在到期后自动执行。', 'Choose instructions and a time. The backend runs the task when due.') +
        '</p>' + W.btn(t('创建第一个任务', 'Create your first task'), 'schedule-new', 'primary') + '</div>') +
      (d.items.length ? '<div class="st-schedule-empty" data-schedule-none hidden><h3>' + t('没有符合筛选的任务', 'No tasks match this filter') +
        '</h3><p>' + t('切换筛选条件，或新建一个任务。', 'Change the filter, or create a task.') + '</p></div>' : '');
  }
  const input = (name, value, type = 'text', attrs = '') => '<input class="st-input" data-field="' + name + '" type="' + type + '" value="' + esc(value ?? '') + '" ' + attrs + '>';
  const select = (name, value, options) => {
    const shown = options.find(([option]) => String(option) === String(value));
    return '<span class="st-schedule-select" data-select-wrap="' + name + '"><select class="st-schedule-native" data-field="' + name + '" tabindex="-1" aria-hidden="true">' +
      options.map(([v, label]) => '<option value="' + esc(v) + '"' + (String(v) === String(value) ? ' selected' : '') + '>' + esc(label) + '</option>').join('') +
      '</select><button type="button" class="st-schedule-select-trigger" data-select-trigger="' + name + '" aria-haspopup="listbox" aria-expanded="false">' +
      '<span data-select-label="' + name + '">' + esc(shown ? shown[1] : value) + '</span>' + CHEVRON + '</button>' +
      '<div class="st-schedule-select-pop" data-select-pop="' + name + '" hidden><div class="st-schedule-select-list" role="listbox" data-select-list="' + name + '"></div></div></span>';
  };
  const SYSTEM_ZONE = (() => {
    try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'; } catch (_) { return 'UTC'; }
  })();
  const TZ_KEY = 'myagent-schedule-timezones';
  const TZ_CACHE = new Map();
  // 国家标准时区：一个时区对应一个国家/地区标准时间，内部映射到 IANA 标识，
  // 界面上绝不展示城市名（如 Asia/Shanghai → 中国标准时间，而不是“上海”）。
  const NATIONAL_ZONES = [
    { region: 'UTC', label: '协调世界时', zone: 'UTC' },
    { region: '亚洲', label: '中国标准时间', zone: 'Asia/Shanghai' },
    { region: '亚洲', label: '香港标准时间', zone: 'Asia/Hong_Kong' },
    { region: '亚洲', label: '澳门标准时间', zone: 'Asia/Macau' },
    { region: '亚洲', label: '台湾标准时间', zone: 'Asia/Taipei' },
    { region: '亚洲', label: '日本标准时间', zone: 'Asia/Tokyo' },
    { region: '亚洲', label: '韩国标准时间', zone: 'Asia/Seoul' },
    { region: '亚洲', label: '新加坡标准时间', zone: 'Asia/Singapore' },
    { region: '亚洲', label: '马来西亚标准时间', zone: 'Asia/Kuala_Lumpur' },
    { region: '亚洲', label: '菲律宾标准时间', zone: 'Asia/Manila' },
    { region: '亚洲', label: '泰国标准时间', zone: 'Asia/Bangkok' },
    { region: '亚洲', label: '越南标准时间', zone: 'Asia/Ho_Chi_Minh' },
    { region: '亚洲', label: '老挝标准时间', zone: 'Asia/Vientiane' },
    { region: '亚洲', label: '柬埔寨标准时间', zone: 'Asia/Phnom_Penh' },
    { region: '亚洲', label: '缅甸标准时间', zone: 'Asia/Yangon' },
    { region: '亚洲', label: '印度尼西亚西部时间', zone: 'Asia/Jakarta' },
    { region: '亚洲', label: '印度尼西亚中部时间', zone: 'Asia/Makassar' },
    { region: '亚洲', label: '印度尼西亚东部时间', zone: 'Asia/Jayapura' },
    { region: '亚洲', label: '文莱标准时间', zone: 'Asia/Brunei' },
    { region: '亚洲', label: '东帝汶标准时间', zone: 'Asia/Dili' },
    { region: '亚洲', label: '斯里兰卡标准时间', zone: 'Asia/Colombo' },
    { region: '亚洲', label: '印度标准时间', zone: 'Asia/Kolkata' },
    { region: '亚洲', label: '尼泊尔标准时间', zone: 'Asia/Kathmandu' },
    { region: '亚洲', label: '不丹标准时间', zone: 'Asia/Thimphu' },
    { region: '亚洲', label: '孟加拉国标准时间', zone: 'Asia/Dhaka' },
    { region: '亚洲', label: '巴基斯坦标准时间', zone: 'Asia/Karachi' },
    { region: '亚洲', label: '阿富汗标准时间', zone: 'Asia/Kabul' },
    { region: '亚洲', label: '乌兹别克斯坦标准时间', zone: 'Asia/Tashkent' },
    { region: '亚洲', label: '土库曼斯坦标准时间', zone: 'Asia/Ashgabat' },
    { region: '亚洲', label: '哈萨克斯坦东部时间', zone: 'Asia/Almaty' },
    { region: '亚洲', label: '哈萨克斯坦西部时间', zone: 'Asia/Aqtobe' },
    { region: '亚洲', label: '塔吉克斯坦标准时间', zone: 'Asia/Dushanbe' },
    { region: '亚洲', label: '吉尔吉斯斯坦标准时间', zone: 'Asia/Bishkek' },
    { region: '亚洲', label: '蒙古乌兰巴托时间', zone: 'Asia/Ulaanbaatar' },
    { region: '亚洲', label: '蒙古科布多时间', zone: 'Asia/Hovd' },
    { region: '亚洲', label: '伊朗标准时间', zone: 'Asia/Tehran' },
    { region: '亚洲', label: '以色列标准时间', zone: 'Asia/Jerusalem' },
    { region: '亚洲', label: '黎巴嫩标准时间', zone: 'Asia/Beirut' },
    { region: '亚洲', label: '叙利亚标准时间', zone: 'Asia/Damascus' },
    { region: '亚洲', label: '约旦标准时间', zone: 'Asia/Amman' },
    { region: '亚洲', label: '伊拉克标准时间', zone: 'Asia/Baghdad' },
    { region: '亚洲', label: '沙特阿拉伯标准时间', zone: 'Asia/Riyadh' },
    { region: '亚洲', label: '也门标准时间', zone: 'Asia/Aden' },
    { region: '亚洲', label: '阿曼标准时间', zone: 'Asia/Muscat' },
    { region: '亚洲', label: '阿联酋标准时间', zone: 'Asia/Dubai' },
    { region: '亚洲', label: '卡塔尔标准时间', zone: 'Asia/Qatar' },
    { region: '亚洲', label: '科威特标准时间', zone: 'Asia/Kuwait' },
    { region: '亚洲', label: '巴林标准时间', zone: 'Asia/Bahrain' },
    { region: '亚洲', label: '格鲁吉亚标准时间', zone: 'Asia/Tbilisi' },
    { region: '亚洲', label: '亚美尼亚标准时间', zone: 'Asia/Yerevan' },
    { region: '亚洲', label: '阿塞拜疆标准时间', zone: 'Asia/Baku' },
    { region: '亚洲', label: '马尔代夫标准时间', zone: 'Indian/Maldives' },
    { region: '亚洲', label: '塞浦路斯标准时间', zone: 'Asia/Nicosia' },
    { region: '欧洲', label: '英国时间', zone: 'Europe/London' },
    { region: '欧洲', label: '爱尔兰时间', zone: 'Europe/Dublin' },
    { region: '欧洲', label: '葡萄牙时间', zone: 'Europe/Lisbon' },
    { region: '欧洲', label: '冰岛时间', zone: 'Atlantic/Reykjavik' },
    { region: '欧洲', label: '欧洲中部时间', zone: 'Europe/Berlin' },
    { region: '欧洲', label: '欧洲东部时间', zone: 'Europe/Bucharest' },
    { region: '欧洲', label: '希腊标准时间', zone: 'Europe/Athens' },
    { region: '欧洲', label: '芬兰标准时间', zone: 'Europe/Helsinki' },
    { region: '欧洲', label: '乌克兰标准时间', zone: 'Europe/Kyiv' },
    { region: '欧洲', label: '白俄罗斯标准时间', zone: 'Europe/Minsk' },
    { region: '欧洲', label: '摩尔多瓦标准时间', zone: 'Europe/Chisinau' },
    { region: '欧洲', label: '俄罗斯加里宁格勒时间', zone: 'Europe/Kaliningrad' },
    { region: '欧洲', label: '俄罗斯莫斯科时间', zone: 'Europe/Moscow' },
    { region: '欧洲', label: '俄罗斯萨马拉时间', zone: 'Europe/Samara' },
    { region: '欧洲', label: '俄罗斯叶卡捷琳堡时间', zone: 'Asia/Yekaterinburg' },
    { region: '欧洲', label: '俄罗斯鄂木斯克时间', zone: 'Asia/Omsk' },
    { region: '欧洲', label: '俄罗斯新西伯利亚时间', zone: 'Asia/Novosibirsk' },
    { region: '欧洲', label: '俄罗斯克拉斯诺亚尔斯克时间', zone: 'Asia/Krasnoyarsk' },
    { region: '欧洲', label: '俄罗斯伊尔库茨克时间', zone: 'Asia/Irkutsk' },
    { region: '欧洲', label: '俄罗斯雅库茨克时间', zone: 'Asia/Yakutsk' },
    { region: '欧洲', label: '俄罗斯符拉迪沃斯托克时间', zone: 'Asia/Vladivostok' },
    { region: '欧洲', label: '俄罗斯马加丹时间', zone: 'Asia/Magadan' },
    { region: '欧洲', label: '俄罗斯堪察加时间', zone: 'Asia/Kamchatka' },
    { region: '欧洲', label: '挪威标准时间', zone: 'Europe/Oslo' },
    { region: '欧洲', label: '瑞典标准时间', zone: 'Europe/Stockholm' },
    { region: '欧洲', label: '丹麦标准时间', zone: 'Europe/Copenhagen' },
    { region: '欧洲', label: '荷兰标准时间', zone: 'Europe/Amsterdam' },
    { region: '欧洲', label: '比利时标准时间', zone: 'Europe/Brussels' },
    { region: '欧洲', label: '卢森堡标准时间', zone: 'Europe/Luxembourg' },
    { region: '欧洲', label: '瑞士标准时间', zone: 'Europe/Zurich' },
    { region: '欧洲', label: '奥地利标准时间', zone: 'Europe/Vienna' },
    { region: '欧洲', label: '意大利标准时间', zone: 'Europe/Rome' },
    { region: '欧洲', label: '西班牙标准时间', zone: 'Europe/Madrid' },
    { region: '欧洲', label: '波兰标准时间', zone: 'Europe/Warsaw' },
    { region: '欧洲', label: '捷克标准时间', zone: 'Europe/Prague' },
    { region: '欧洲', label: '斯洛伐克标准时间', zone: 'Europe/Bratislava' },
    { region: '欧洲', label: '匈牙利标准时间', zone: 'Europe/Budapest' },
    { region: '欧洲', label: '保加利亚标准时间', zone: 'Europe/Sofia' },
    { region: '欧洲', label: '塞尔维亚标准时间', zone: 'Europe/Belgrade' },
    { region: '欧洲', label: '克罗地亚标准时间', zone: 'Europe/Zagreb' },
    { region: '欧洲', label: '斯洛文尼亚标准时间', zone: 'Europe/Ljubljana' },
    { region: '欧洲', label: '波斯尼亚和黑塞哥维那时间', zone: 'Europe/Sarajevo' },
    { region: '欧洲', label: '黑山标准时间', zone: 'Europe/Podgorica' },
    { region: '欧洲', label: '北马其顿标准时间', zone: 'Europe/Skopje' },
    { region: '欧洲', label: '阿尔巴尼亚标准时间', zone: 'Europe/Tirane' },
    { region: '欧洲', label: '爱沙尼亚标准时间', zone: 'Europe/Tallinn' },
    { region: '欧洲', label: '拉脱维亚标准时间', zone: 'Europe/Riga' },
    { region: '欧洲', label: '立陶宛标准时间', zone: 'Europe/Vilnius' },
    { region: '欧洲', label: '土耳其标准时间', zone: 'Europe/Istanbul' },
    { region: '美洲', label: '美国东部时间', zone: 'America/New_York' },
    { region: '美洲', label: '美国中部时间', zone: 'America/Chicago' },
    { region: '美洲', label: '美国山地时间', zone: 'America/Denver' },
    { region: '美洲', label: '美国太平洋时间', zone: 'America/Los_Angeles' },
    { region: '美洲', label: '美国阿拉斯加时间', zone: 'America/Anchorage' },
    { region: '美洲', label: '美国夏威夷时间', zone: 'Pacific/Honolulu' },
    { region: '美洲', label: '加拿大东部时间', zone: 'America/Toronto' },
    { region: '美洲', label: '加拿大中部时间', zone: 'America/Winnipeg' },
    { region: '美洲', label: '加拿大山地时间', zone: 'America/Edmonton' },
    { region: '美洲', label: '加拿大太平洋时间', zone: 'America/Vancouver' },
    { region: '美洲', label: '加拿大纽芬兰时间', zone: 'America/St_Johns' },
    { region: '美洲', label: '墨西哥太平洋时间', zone: 'America/Tijuana' },
    { region: '美洲', label: '墨西哥中部时间', zone: 'America/Mexico_City' },
    { region: '美洲', label: '墨西哥东北时间', zone: 'America/Monterrey' },
    { region: '美洲', label: '危地马拉标准时间', zone: 'America/Guatemala' },
    { region: '美洲', label: '萨尔瓦多标准时间', zone: 'America/El_Salvador' },
    { region: '美洲', label: '洪都拉斯标准时间', zone: 'America/Tegucigalpa' },
    { region: '美洲', label: '尼加拉瓜标准时间', zone: 'America/Managua' },
    { region: '美洲', label: '哥斯达黎加标准时间', zone: 'America/Costa_Rica' },
    { region: '美洲', label: '巴拿马标准时间', zone: 'America/Panama' },
    { region: '美洲', label: '古巴标准时间', zone: 'America/Havana' },
    { region: '美洲', label: '牙买加标准时间', zone: 'America/Jamaica' },
    { region: '美洲', label: '巴哈马标准时间', zone: 'America/Nassau' },
    { region: '美洲', label: '波多黎各大西洋时间', zone: 'America/Puerto_Rico' },
    { region: '美洲', label: '多米尼加标准时间', zone: 'America/Santo_Domingo' },
    { region: '美洲', label: '特立尼达和多巴哥时间', zone: 'America/Port_of_Spain' },
    { region: '美洲', label: '委内瑞拉标准时间', zone: 'America/Caracas' },
    { region: '美洲', label: '哥伦比亚标准时间', zone: 'America/Bogota' },
    { region: '美洲', label: '厄瓜多尔标准时间', zone: 'America/Guayaquil' },
    { region: '美洲', label: '秘鲁标准时间', zone: 'America/Lima' },
    { region: '美洲', label: '玻利维亚标准时间', zone: 'America/La_Paz' },
    { region: '美洲', label: '智利圣地亚哥时间', zone: 'America/Santiago' },
    { region: '美洲', label: '巴拉圭标准时间', zone: 'America/Asuncion' },
    { region: '美洲', label: '阿根廷布宜诺斯艾利斯时间', zone: 'America/Argentina/Buenos_Aires' },
    { region: '美洲', label: '乌拉圭标准时间', zone: 'America/Montevideo' },
    { region: '美洲', label: '巴西巴西利亚时间', zone: 'America/Sao_Paulo' },
    { region: '美洲', label: '巴西马瑙斯时间', zone: 'America/Manaus' },
    { region: '美洲', label: '巴西里约布兰科时间', zone: 'America/Rio_Branco' },
    { region: '美洲', label: '格陵兰西部时间', zone: 'America/Nuuk' },
    { region: '非洲', label: '摩洛哥标准时间', zone: 'Africa/Casablanca' },
    { region: '非洲', label: '阿尔及利亚标准时间', zone: 'Africa/Algiers' },
    { region: '非洲', label: '突尼斯标准时间', zone: 'Africa/Tunis' },
    { region: '非洲', label: '利比亚标准时间', zone: 'Africa/Tripoli' },
    { region: '非洲', label: '埃及标准时间', zone: 'Africa/Cairo' },
    { region: '非洲', label: '苏丹标准时间', zone: 'Africa/Khartoum' },
    { region: '非洲', label: '埃塞俄比亚标准时间', zone: 'Africa/Addis_Ababa' },
    { region: '非洲', label: '肯尼亚标准时间', zone: 'Africa/Nairobi' },
    { region: '非洲', label: '坦桑尼亚标准时间', zone: 'Africa/Dar_es_Salaam' },
    { region: '非洲', label: '乌干达标准时间', zone: 'Africa/Kampala' },
    { region: '非洲', label: '卢旺达标准时间', zone: 'Africa/Kigali' },
    { region: '非洲', label: '刚果金沙萨时间', zone: 'Africa/Kinshasa' },
    { region: '非洲', label: '尼日利亚标准时间', zone: 'Africa/Lagos' },
    { region: '非洲', label: '加纳标准时间', zone: 'Africa/Accra' },
    { region: '非洲', label: '塞内加尔标准时间', zone: 'Africa/Dakar' },
    { region: '非洲', label: '科特迪瓦标准时间', zone: 'Africa/Abidjan' },
    { region: '非洲', label: '安哥拉标准时间', zone: 'Africa/Luanda' },
    { region: '非洲', label: '赞比亚标准时间', zone: 'Africa/Lusaka' },
    { region: '非洲', label: '津巴布韦标准时间', zone: 'Africa/Harare' },
    { region: '非洲', label: '莫桑比克标准时间', zone: 'Africa/Maputo' },
    { region: '非洲', label: '博茨瓦纳标准时间', zone: 'Africa/Gaborone' },
    { region: '非洲', label: '纳米比亚标准时间', zone: 'Africa/Windhoek' },
    { region: '非洲', label: '南非标准时间', zone: 'Africa/Johannesburg' },
    { region: '非洲', label: '毛里求斯标准时间', zone: 'Indian/Mauritius' },
    { region: '非洲', label: '塞舌尔标准时间', zone: 'Indian/Mahe' },
    { region: '非洲', label: '马达加斯加标准时间', zone: 'Indian/Antananarivo' },
    { region: '大洋洲', label: '澳大利亚西部标准时间', zone: 'Australia/Perth' },
    { region: '大洋洲', label: '澳大利亚中部标准时间', zone: 'Australia/Adelaide' },
    { region: '大洋洲', label: '澳大利亚东部标准时间', zone: 'Australia/Sydney' },
    { region: '大洋洲', label: '澳大利亚布里斯班时间', zone: 'Australia/Brisbane' },
    { region: '大洋洲', label: '新西兰标准时间', zone: 'Pacific/Auckland' },
    { region: '大洋洲', label: '斐济标准时间', zone: 'Pacific/Fiji' },
    { region: '大洋洲', label: '巴布亚新几内亚时间', zone: 'Pacific/Port_Moresby' },
    { region: '大洋洲', label: '所罗门群岛时间', zone: 'Pacific/Guadalcanal' },
    { region: '大洋洲', label: '瓦努阿图时间', zone: 'Pacific/Efate' },
    { region: '大洋洲', label: '新喀里多尼亚时间', zone: 'Pacific/Noumea' },
    { region: '大洋洲', label: '汤加标准时间', zone: 'Pacific/Tongatapu' },
    { region: '大洋洲', label: '萨摩亚标准时间', zone: 'Pacific/Apia' },
    { region: '大洋洲', label: '关岛标准时间', zone: 'Pacific/Guam' },
    { region: '大洋洲', label: '瑙鲁时间', zone: 'Pacific/Nauru' },
    { region: '大洋洲', label: '图瓦卢时间', zone: 'Pacific/Funafuti' },
    { region: '大洋洲', label: '基里巴斯塔拉瓦时间', zone: 'Pacific/Tarawa' },
    { region: '大洋洲', label: '马绍尔群岛时间', zone: 'Pacific/Majuro' },
    { region: '大洋洲', label: '帕劳时间', zone: 'Pacific/Palau' },
    { region: '大洋洲', label: '密克罗尼西亚时间', zone: 'Pacific/Chuuk' },
    { region: '大洋洲', label: '美属萨摩亚时间', zone: 'Pacific/Pago_Pago' },
  ];
  const CHEVRON = '<svg class="st-schedule-chevron" width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6l4 4 4-4"/></svg>';
  const CALENDAR_ICON = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2.5" y="3.5" width="11" height="10" rx="2"/><path d="M5 1.5v4M11 1.5v4M2.5 6.5h11"/></svg>';
  const CLOCK_ICON = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6"/><path d="M8 4.5V8l2.5 1.5"/></svg>';
  function tzInfo(zone) {
    const key = (A.lang || 'zh') + '|' + zone;
    if (TZ_CACHE.has(key)) return TZ_CACHE.get(key);
    const now = new Date();
    let name = zone, offset = 'UTC+00:00', minutes = 0;
    try {
      const parts = new Intl.DateTimeFormat(A.lang === 'zh' ? 'zh-CN' : 'en-US',
        { timeZone: zone, timeZoneName: 'long' }).formatToParts(now);
      name = parts.find(part => part.type === 'timeZoneName')?.value || zone;
    } catch (_) { /* an unknown stored zone still gets an offset */ }
    try {
      const parts = new Intl.DateTimeFormat('en-US',
        { timeZone: zone, timeZoneName: 'shortOffset' }).formatToParts(now);
      const raw = parts.find(part => part.type === 'timeZoneName')?.value || 'GMT';
      const match = raw.match(/GMT([+-])(\d{1,2})(?::?(\d{2}))?/);
      if (match) {
        const sign = match[1] === '-' ? -1 : 1;
        minutes = sign * (Number(match[2]) * 60 + Number(match[3] || 0));
        offset = 'UTC' + match[1] + String(match[2]).padStart(2, '0') + ':' + (match[3] || '00');
      } else if (/GMT|UTC/i.test(raw)) {
        offset = 'UTC+00:00';
      }
    } catch (_) { /* keep UTC+00:00 */ }
    const value = { zone, name, offset, minutes, system: zone === SYSTEM_ZONE };
    TZ_CACHE.set(key, value);
    return value;
  }
  function tzLabel(zone) {
    const info = tzInfo(zone);
    const entry = NATIONAL_ZONES.find(item => item.zone === zone);
    const name = entry ? entry.label : info.name;
    return info.offset + ' · ' + name + (info.system ? t('（系统）', ' (system)') : '');
  }
  function timezoneChoices(selected) {
    const seen = new Set();
    const rows = [];
    for (const entry of NATIONAL_ZONES) {
      const info = tzInfo(entry.zone);
      const key = entry.label + '|' + info.offset;
      if (seen.has(key)) continue;
      seen.add(key);
      rows.push({ zone: entry.zone, name: entry.label, offset: info.offset, minutes: info.minutes,
        system: info.system, region: entry.region });
    }
    if (!rows.some(row => row.zone === selected)) {
      const info = tzInfo(selected);
      const entry = NATIONAL_ZONES.find(item => item.zone === selected);
      rows.unshift({ zone: selected, name: entry ? entry.label : info.name, offset: info.offset,
        minutes: info.minutes, system: info.system, region: t('其他', 'Other') });
    }
    return rows.sort((left, right) => (right.system - left.system) || 0);
  }
  function recentTimezones() {
    try {
      const list = JSON.parse(localStorage.getItem(TZ_KEY) || '[]');
      return Array.isArray(list) ? list.filter(zone => typeof zone === 'string') : [];
    } catch (_) { return []; }
  }
  function rememberTimezone(zone) {
    try { localStorage.setItem(TZ_KEY, JSON.stringify([zone, ...recentTimezones().filter(item => item !== zone)].slice(0, 6))); }
    catch (_) { /* private mode */ }
  }
  function timezonePicker(zone) {
    return '<div class="st-schedule-tz">' +
      '<button type="button" class="st-schedule-choice st-schedule-tz-trigger" data-tz-trigger aria-haspopup="listbox" aria-expanded="false">' +
      '<span data-tz-label>' + esc(tzLabel(zone)) + '</span>' + CHEVRON + '</button>' +
      '<div class="st-schedule-tz-pop" data-tz-pop hidden><input class="st-input" data-tz-search autocomplete="off" ' +
      'placeholder="' + esc(t('搜索时区名称或 UTC 偏移', 'Search time zone name or UTC offset')) + '" aria-label="' + esc(t('搜索时区', 'Search time zones')) + '">' +
      '<div class="st-schedule-tz-list" data-tz-list role="listbox"></div></div>' +
      '<input type="hidden" data-field="timezone" value="' + esc(zone) + '"></div>';
  }
  function wireTimezone(root) {
    const trigger = root.querySelector('[data-tz-trigger]');
    const pop = root.querySelector('[data-tz-pop]');
    const search = root.querySelector('[data-tz-search]');
    const list = root.querySelector('[data-tz-list]');
    const label = root.querySelector('[data-tz-label]');
    const hidden = root.querySelector('[data-field="timezone"]');
    if (!trigger || !pop || !search || !list || !label || !hidden) return () => {};
    let selected = hidden.value || SYSTEM_ZONE;
    const close = () => { pop.hidden = true; trigger.setAttribute('aria-expanded', 'false'); };
    const option = item => '<button type="button" role="option" aria-selected="' + (item.zone === selected) +
      '" class="st-schedule-tz-option' + (item.zone === selected ? ' is-on' : '') + '" data-tz-zone="' + esc(item.zone) + '">' +
      '<span><b>' + esc(item.name) + '</b><small>' + esc(item.region) + (item.system ? ' · ' + t('系统', 'System') : '') + '</small>' +
      '</span><span>' + esc(item.offset) + '</span></button>';
    const render = () => {
      const query = search.value.trim().toLowerCase();
      const all = timezoneChoices(selected);
      const recent = query ? [] : recentTimezones().map(zone => all.find(item => item.zone === zone)).filter(Boolean);
      const matches = all.filter(item => !query ||
        [item.zone, item.name, item.offset, item.region].join(' ').toLowerCase().includes(query));
      const rows = [];
      if (recent.length) rows.push('<div class="st-schedule-tz-head">' + t('最近使用', 'Recent') + '</div>', ...recent.map(option));
      rows.push('<div class="st-schedule-tz-head">' + t('全部时区', 'All time zones') + '</div>');
      rows.push(...(matches.length ? matches.slice(0, 120).map(option) : ['<div class="st-schedule-tz-empty">' + t('没有匹配的时区', 'No matching time zone') + '</div>']));
      list.innerHTML = rows.join('');
    };
    const choose = zone => {
      selected = zone;
      hidden.value = zone;
      label.textContent = tzLabel(zone);
      rememberTimezone(zone);
      render();
      close();
      trigger.focus();
      hidden.dispatchEvent(new Event('change', { bubbles: true }));
    };
    const onTrigger = () => {
      if (pop.hidden) {
        search.value = '';
        render();
        pop.hidden = false;
        trigger.setAttribute('aria-expanded', 'true');
        search.focus();
      } else close();
    };
    const onList = event => {
      const button = event.target.closest('[data-tz-zone]');
      if (button) choose(button.dataset.tzZone);
    };
    const onKey = event => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); trigger.focus(); return; }
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
      const options = [...list.querySelectorAll('[data-tz-zone]')];
      if (!options.length) return;
      const index = options.indexOf(document.activeElement);
      const next = event.key === 'ArrowDown' ? Math.min(options.length - 1, index + 1) : Math.max(0, index < 0 ? 0 : index - 1);
      options[next].focus();
      event.preventDefault();
    };
    const outside = event => {
      if (!pop.hidden && !pop.contains(event.target) && !trigger.contains(event.target)) close();
    };
    trigger.addEventListener('click', onTrigger);
    search.addEventListener('input', render);
    list.addEventListener('click', onList);
    pop.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', outside, true);
    render();
    return () => document.removeEventListener('pointerdown', outside, true);
  }

  function wireSelects(root) {
    const closeAll = except => {
      root.querySelectorAll('[data-select-pop]').forEach(pop => {
        if (pop !== except) pop.hidden = true;
      });
      root.querySelectorAll('[data-select-trigger]').forEach(trigger => {
        trigger.setAttribute('aria-expanded', String(trigger.nextElementSibling?.hidden === false));
      });
    };
    const cleanups = [];
    root.querySelectorAll('[data-select-trigger]').forEach(trigger => {
      const name = trigger.dataset.selectTrigger;
      const wrap = trigger.closest('.st-schedule-select');
      const select = wrap?.querySelector('select[data-field="' + name + '"]');
      const pop = wrap?.querySelector('[data-select-pop="' + name + '"]');
      const list = wrap?.querySelector('[data-select-list="' + name + '"]');
      const label = wrap?.querySelector('[data-select-label="' + name + '"]');
      if (!select || !pop || !list || !label) return;
      const close = () => { pop.hidden = true; trigger.setAttribute('aria-expanded', 'false'); };
      const render = () => {
        list.innerHTML = [...select.options].map(option =>
          '<button type="button" role="option" aria-selected="' + (option.selected ? 'true' : 'false') +
          '" class="st-schedule-select-option' + (option.selected ? ' is-on' : '') + '" data-select-value="' + esc(option.value) + '">' +
          esc(option.text) + '</button>').join('');
      };
      const open = () => {
        closeAll(pop);
        render();
        pop.hidden = false;
        trigger.setAttribute('aria-expanded', 'true');
        const rect = trigger.getBoundingClientRect();
        pop.classList.toggle('is-up', window.innerHeight - rect.bottom < 220 && rect.top > 220);
        requestAnimationFrame(() => {
          const active = list.querySelector('[aria-selected="true"]') || list.querySelector('button');
          active?.focus();
        });
      };
      const choose = value => {
        select.value = value;
        select.dispatchEvent(new Event('change', { bubbles: true }));
        label.textContent = select.options[select.selectedIndex]?.text || '';
        close();
        trigger.focus();
      };
      const onTrigger = event => {
        if (event.type === 'keydown' && !['Enter', ' ', 'ArrowDown'].includes(event.key)) return;
        event.preventDefault();
        if (pop.hidden) open(); else close();
      };
      const onList = event => {
        const option = event.target.closest('[data-select-value]');
        if (option) choose(option.dataset.selectValue);
      };
      const onKey = event => {
        if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); trigger.focus(); return; }
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          event.target.closest('[data-select-value]')?.click();
          return;
        }
        if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
        const options = [...list.querySelectorAll('[data-select-value]')];
        if (!options.length) return;
        const index = options.indexOf(document.activeElement);
        const next = event.key === 'ArrowDown' ? Math.min(options.length - 1, index + 1) : Math.max(0, index < 0 ? 0 : index - 1);
        options[next].focus();
        event.preventDefault();
      };
      const outside = event => {
        if (!pop.hidden && !pop.contains(event.target) && !trigger.contains(event.target)) close();
      };
      const onNative = () => {
        label.textContent = select.options[select.selectedIndex]?.text || '';
        if (!pop.hidden) render();
      };
      trigger.addEventListener('click', onTrigger);
      trigger.addEventListener('keydown', onTrigger);
      list.addEventListener('click', onList);
      pop.addEventListener('keydown', onKey);
      select.addEventListener('change', onNative);
      document.addEventListener('pointerdown', outside, true);
      cleanups.push(() => {
        trigger.removeEventListener('click', onTrigger);
        trigger.removeEventListener('keydown', onTrigger);
        list.removeEventListener('click', onList);
        pop.removeEventListener('keydown', onKey);
        select.removeEventListener('change', onNative);
        document.removeEventListener('pointerdown', outside, true);
      });
    });
    return () => cleanups.forEach(cleanup => cleanup());
  }

  function edit(row) {
    const original = row || {}, d = decode(original.trigger || {
      kind: 'at', at: new Date(Date.now() + 3600000).toISOString(), time_zone: SYSTEM_ZONE });
    const override = original.runtime_override || {};
    const prompt = override.system_prompt || {};
    const actionKind = original.action?.kind || 'prompt';
    const modelOptions = [['', t('继承会话 / 使用默认模型', 'Inherit chat / default model')], ...data.profiles.map(p => [p.id, p.name || p.model])];
    if (override.model_profile_id && !modelOptions.some(p => p[0] === override.model_profile_id)) {
      modelOptions.push([override.model_profile_id, override.model_profile_id + ' · ' + t('当前不可用', 'Unavailable')]);
    }
    const sid = original.target?.session_id || boot.sessionId || '';
    const targetMode = row ? (row.target.mode || 'existing') : 'new_once';
    const sessionOptions = [['', t('选择会话', 'Select a chat')], ...data.sessions.map(s => [s.id, s.name || s.id])];
    if (sid && !sessionOptions.some(x => x[0] === sid)) sessionOptions.push([sid, sid]);
    const localRaw = d.local_at || wallDate(Date.now() + 3600000, d.time_zone || SYSTEM_ZONE);
    const localParts = localRaw.split('T');
    const localDate = localParts[0] || '';
    const localClock = (localParts[1] || '09:00').length === 5 ? (localParts[1] || '09:00') + ':00' : (localParts[1] || '09:00');
    const workspace = original.workspace || boot.workspace || '';
    const rowField = (label, control, hint = '', cls = '') => W.row(label, hint, control, cls);
    const toggle = (name, checked, label) => W.sw(name, checked, 'aria-label="' + label + '"');
    const form = '<form id="st-schedule-form" class="st-schedule-form">' +
      '<div class="st-schedule-section"><label class="st-schedule-section-title" for="st-schedule-name">' + t('自动化任务名称', 'Automation name') + '</label>' +
      input('name', original.name, 'text', 'id="st-schedule-name" maxlength="160" placeholder="' + t('例如：每日阅读摘要', 'For example: Daily reading digest') + '"') + '</div>' +
      '<div class="st-schedule-section"><label class="st-schedule-section-title" for="st-schedule-prompt">' + t('自动化任务内容', 'Automation content') + '</label>' +
      '<textarea id="st-schedule-prompt" class="st-input st-schedule-prompt" data-field="instructions" required placeholder="' +
      t('说明任务内容和预期结果\n例如：汇总阅读清单中的新文章，并附原文链接', 'Describe the task and expected result.\nFor example: Summarize new items in the reading list with source links.') + '">' +
      esc(original.action?.text || '') + '</textarea></div>' +
      '<div class="st-card st-schedule-group">' +
      rowField(t('执行位置', 'Execution'), select('target_mode', targetMode,
        [['existing', t('指定会话（当前会话）', 'Specific chat (current)')],
         ['new_once', t('新建并复用会话', 'Create once and reuse')],
         ['new', t('每次新建会话', 'New chat each run')]])) +
      rowField(t('关联工作区', 'Workspace'), input('workspace', workspace, 'text', 'data-path-kind="directory"')) +
      '<div data-schedule-existing>' + rowField(t('目标会话', 'Target chat'), select('session', sid, sessionOptions)) + '</div></div>' +
      '<div class="st-schedule-section-title">' + t('运行时间', 'Run time') + '</div>' +
      '<div class="st-card st-schedule-group">' +
      rowField(t('重复', 'Repeat'), select('repeat', d.kind, Object.entries(labels()))) +
      '<div data-schedule-show="at">' +
      rowField(t('日期', 'Date'), '<span class="st-schedule-value"><input class="st-schedule-inline" type="date" data-field="date_value" value="' + esc(localDate) + '">' +
        '<button type="button" class="st-schedule-icon" data-pick="date_value" aria-label="' + esc(t('选择日期', 'Choose date')) + '">' + CALENDAR_ICON + '</button></span>') +
      rowField(t('时间', 'Time'), '<span class="st-schedule-value"><input class="st-schedule-inline" type="time" step="1" data-field="clock_value" value="' + esc(localClock) + '">' +
        '<button type="button" class="st-schedule-icon" data-pick="clock_value" aria-label="' + esc(t('选择时间', 'Choose time')) + '">' + CLOCK_ICON + '</button></span>') +
      '<input type="hidden" data-field="local_at" value="' + esc(localRaw) + '"></div>' +
      '<div data-schedule-show="daily weekdays weekly monthly">' + rowField(t('时间', 'Time'), input('time', d.time || '09:00', 'time')) + '</div>' +
      '<div data-schedule-show="weekly">' + rowField(t('星期', 'Days of week'), '<div class="st-schedule-weekdays">' +
      [1, 2, 3, 4, 5, 6, 7].map((n, i) => '<label><input type="checkbox" data-weekday="' + n + '"' + ((d.weekdays || [1]).includes(n) ? ' checked' : '') + '><span>' +
        [t('一', 'Mon'), t('二', 'Tue'), t('三', 'Wed'), t('四', 'Thu'), t('五', 'Fri'), t('六', 'Sat'), t('日', 'Sun')][i] + '</span></label>').join('') + '</div>') + '</div>' +
      '<div data-schedule-show="monthly">' + rowField(t('每月日期', 'Days of month'), input('monthdays', (d.days || [1]).join(',')), t('用逗号分隔，如 1,15,28。', 'Comma-separated, e.g. 1,15,28.')) + '</div>' +
      '<div data-schedule-show="interval after">' + rowField(t('间隔（分钟）', 'Minutes'), input('minutes', d.minutes || 60, 'number', 'min="1" step="1"')) + '</div>' +
      '<div data-schedule-show="cron">' + rowField('Cron', input('cron', d.expression || '0 9 * * *'), t('分钟 小时 日 月 星期，例如 0 9 * * 1-5', 'Minute hour day month weekday, e.g. 0 9 * * 1-5')) + '</div>' +
      rowField(t('时区', 'Timezone'), timezonePicker(d.time_zone || SYSTEM_ZONE)) + '</div>' +
      W.adv(t('高级设置', 'Advanced'), '<div class="st-card">' +
        rowField(t('启用', 'Enabled'), toggle('enabled', row ? row.enabled : true, t('启用', 'Enabled')), t('关闭后暂停未来触发。', 'Off pauses future triggers.')) +
        rowField(t('执行动作', 'Action'), select('action_kind', actionKind, [['prompt', t('发送任务说明', 'Send instructions')], ['notice', t('仅写入通知', 'Add a notice')], ['continue', t('继续未完成会话', 'Continue an unfinished chat')], ['stop', t('停止会话', 'Stop a chat')]])) +
        rowField(t('通知', 'Notifications'), select('notification', original.notification || 'important', [['important', t('重要更新', 'Important updates')], ['always', t('每次结束', 'Every completion')], ['never', t('关闭', 'Off')]])) +
        rowField(t('漏跑策略', 'Missed runs'), select('misfire', original.misfire || 'latest', [['latest', t('补跑最新一次', 'Run the latest occurrence')], ['skip', t('跳过漏跑', 'Skip missed occurrences')]])) +
        rowField(t('最多计划运行次数', 'Maximum scheduled runs'), input('max_runs', original.max_runs, 'number', 'min="1" step="1"'), t('留空表示不限制；手动运行不计数。', 'Blank means unlimited; manual runs do not count.')) +
        rowField(t('截止时间', 'End time'), input('end_at', original.end_at ? wallDate(original.end_at * 1000, d.time_zone || SYSTEM_ZONE) : '', 'datetime-local')) +
        rowField(t('模型', 'Model'), select('model', override.model_profile_id || '', modelOptions)) +
        rowField(t('推理强度', 'Reasoning effort'), select('effort', override.reasoning_effort || '', [['', t('继承', 'Inherit')], ...['low', 'medium', 'high', 'xhigh', 'max'].map(x => [x, x])])) +
        rowField('System Prompt', select('prompt_mode', prompt.mode || 'inherit',
          [['inherit', t('继承会话', 'Inherit chat')], ['append', t('本次追加', 'Append for this run')], ['replace', t('本次替换', 'Replace for this run')]]),
          t('仅作用于任务轮次，不改写目标会话的持久配置。', 'Applies only to task turns; the chat configuration stays independent.')) +
        '<div class="st-schedule-prompt-config" data-schedule-prompt-config>' +
        '<textarea class="st-input" rows="4" data-field="system_text" placeholder="' + t('输入本次任务轮次使用的 System Prompt', 'System prompt for this task turn') + '">' + esc(prompt.text || '') + '</textarea></div>' +
        '<p class="st-hint st-schedule-preserved">' + t('工具白名单、只读与预算设置会保留；需要修改时请使用 CLI 或 API。',
          'Tool allowlist, read-only and budget settings are preserved; use the CLI or API to change them.') + '</p></div>') +
      '<p class="st-schedule-error" id="st-schedule-error" role="alert" hidden></p></form>';
    let dirty = false, submitted = null, submissionKey = null;
    openDialog({ title: row ? t('编辑定时任务', 'Edit scheduled task') : t('手动创建', 'Create manually'),
      sub: row ? repeatText(row) + ' · ' + t('下次 ', 'Next ') + date(row.next_run_at, row.trigger.time_zone)
        : '',
      cancelText: t('放弃', 'Discard'), body: form,
      okText: row ? t('保存', 'Save') : t('创建', 'Create'),
      beforeClose: () => !document.getElementById('st-dlg-ok').disabled && (!dirty || window.confirm(t('有未保存的任务设置，仍要关闭吗？', 'Discard unsaved task settings?'))),
      after(root) {
        const controller = new AbortController(), options = { signal: controller.signal };
        const syncLocal = () => {
          const date = root.querySelector('[data-field="date_value"]');
          const clock = root.querySelector('[data-field="clock_value"]');
          const hidden = root.querySelector('[data-field="local_at"]');
          if (date && clock && hidden && date.value && clock.value) hidden.value = date.value + 'T' + clock.value;
        };
        const syncSelectLabels = () => {
          root.querySelectorAll('select[data-field]').forEach(select => {
            const label = root.querySelector('[data-select-label="' + select.dataset.field + '"]');
            if (label) label.textContent = select.options[select.selectedIndex]?.text || '';
          });
        };
        const refresh = () => {
          const value = n => root.querySelector('[data-field="' + n + '"]').value;
          root.querySelectorAll('[data-schedule-show]').forEach(el => { el.hidden = !el.dataset.scheduleShow.split(' ').includes(value('repeat')); });
          const mode = value('target_mode');
          root.querySelector('[data-schedule-existing]').hidden = mode !== 'existing';
          const workspace = root.querySelector('[data-field="workspace"]');
          if (workspace) workspace.disabled = mode === 'existing';
          root.querySelector('[data-field="instructions"]').required = ['prompt', 'notice'].includes(value('action_kind'));
          const promptMode = value('prompt_mode');
          const promptBox = root.querySelector('[data-schedule-prompt-config]');
          if (promptBox) {
            promptBox.hidden = promptMode === 'inherit';
            const text = promptBox.querySelector('textarea');
            if (text) text.disabled = promptMode === 'inherit';
          }
          root.querySelectorAll('[data-schedule-show] input').forEach(el => { el.disabled = !!el.closest('[data-schedule-show]').hidden; });
        };
        const unwireTimezone = wireTimezone(root);
        const unwireSelects = wireSelects(root);
        root.addEventListener('input', () => { dirty = true; syncLocal(); }, options);
        root._scheduleRefresh = refresh;
        root.addEventListener('change', () => { dirty = true; syncLocal(); syncSelectLabels(); refresh(); }, options);
        root.addEventListener('click', ev => {
          const pick = ev.target.closest('[data-pick]');
          if (pick) {
            const input = root.querySelector('[data-field="' + pick.dataset.pick + '"]');
            if (input?.showPicker) { try { input.showPicker(); } catch (_) { input.focus(); } }
            else input?.focus();
            return;
          }
          if (ev.target.closest('[data-key]')) { dirty = true; refresh(); }
        }, options);
        root.querySelector('form').addEventListener('submit', ev => { ev.preventDefault(); document.getElementById('st-dlg-ok').click(); });
        syncSelectLabels();
        refresh();
        return () => { controller.abort(); unwireTimezone(); unwireSelects(); delete root._scheduleRefresh; };
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
          const kind = value('repeat'), zone = value('timezone'), targetMode = value('target_mode');
          const actionKind = value('action_kind');
          if (!zone) throw new Error(t('请选择时区。', 'Select a timezone.'));
          if (value('prompt_mode') !== 'inherit' && !value('system_text')) {
            const advanced = root.querySelector('.st-adv');
            if (advanced) advanced.open = true;
            throw new Error(t('请输入 System Prompt，或选择继承会话。', 'Enter a System Prompt, or inherit the chat.'));
          }
          if (targetMode !== 'existing' && ['continue', 'stop'].includes(actionKind)) throw new Error(t('继续或停止需要选择已有会话。', 'Continue and stop require an existing chat.'));
          let trigger = { kind, time_zone: zone };
          if (['daily', 'weekdays', 'weekly', 'monthly'].includes(kind)) trigger.time = value('time');
          if (kind === 'weekly') trigger.weekdays = [...root.querySelectorAll('[data-weekday]:checked')].map(x => Number(x.dataset.weekday));
          if (kind === 'monthly') trigger.days = value('monthdays').split(',').map(x => Number(x.trim()));
          if (kind === 'at') {
            if (!value('local_at')) throw new Error(t('请选择运行日期和时间。', 'Choose a date and time.'));
            trigger.local_at = value('local_at');
          }
          if (kind === 'interval' || kind === 'after') trigger.seconds = Number(value('minutes')) * 60;
          if (kind === 'cron') trigger.expression = value('cron');
          // Editing content preserves an existing anchor and next scheduled time.
          const initial = decode(original.trigger || {});
          if (row && kind === initial.kind && zone === (initial.time_zone || SYSTEM_ZONE) &&
              (kind !== 'interval' || Number(value('minutes')) === initial.minutes) &&
              (kind !== 'at' || value('local_at') === initial.local_at) &&
              (!['daily', 'weekdays', 'weekly', 'monthly'].includes(kind) || value('time') === initial.time) &&
              (kind !== 'weekly' || JSON.stringify(trigger.weekdays) === JSON.stringify(initial.weekdays)) &&
              (kind !== 'monthly' || JSON.stringify(trigger.days) === JSON.stringify(initial.days)) &&
              (kind !== 'cron' || value('cron') === initial.expression)) trigger = original.trigger;
          // Hidden execution controls keep their stored values: only model and
          // effort are edited here; tools, System Prompt and limits stay intact.
          const runtime = { ...override };
          if (value('model')) runtime.model_profile_id = value('model'); else delete runtime.model_profile_id;
          if (value('effort')) runtime.reasoning_effort = value('effort'); else delete runtime.reasoning_effort;
          const promptMode = value('prompt_mode');
          if (promptMode === 'inherit') delete runtime.system_prompt;
          else runtime.system_prompt = { mode: promptMode, text: value('system_text') };
          const policy = original.policy ? JSON.parse(JSON.stringify(original.policy)) : { scope: 'workspace', capabilities: ['read', 'session.create', 'session.send'] };
          policy.capabilities = [...new Set([...(policy.capabilities || []), { prompt: 'session.send', notice: 'session.notice', continue: 'session.continue', stop: 'session.interrupt' }[actionKind]])];
          const payload = { name: value('name') || value('instructions').split('\n')[0].slice(0, 60) || t('未命名任务', 'Untitled task'),
            enabled: on('enabled'), trigger, action: { kind: actionKind, text: value('instructions') }, policy,
            target: targetMode === 'existing' ? { mode: 'existing', session_id: value('session') } : { mode: targetMode },
            workspace: targetMode === 'existing' ? (original.workspace || boot.workspace) : value('workspace'), runtime_override: runtime,
            notification: value('notification'), misfire: value('misfire'), max_runs: value('max_runs') ? Number(value('max_runs')) : null,
            end_local: value('end_at') ? { local_at: value('end_at'), time_zone: zone } : null,
            ...(row ? { id: row.id, expected_revision: row.revision } : {}) };
          if (targetMode === 'existing' && !value('session')) throw new Error(t('请选择目标会话。', 'Select a target chat.'));
          if (targetMode !== 'existing' && !value('workspace')) throw new Error(t('请填写工作目录。', 'Enter a workspace.'));
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
    zhSub: '按计划驱动 Agent，专注任务内容、时间和执行位置。', enSub: 'Schedule agent work with a focused title, prompt, time and destination.',
    async load() {
      const [tasks, sessions, profiles] = await Promise.all([rpc('automation.list'), rpc('session.list'),
        api('/api/model_profiles').catch(() => ({ profiles: [] }))]);
      data = { items: tasks.items, sessions: sessions.sessions.filter(s => !s.is_subagent && !s.archived),
        profiles: (profiles.profiles || []).filter(p => p.enabled !== false) };
      return data;
    }, render: list, onSearch: () => { A.filterSearchRows(); applyStatusFilter(); },
    after(_body, loaded) {
      applyStatusFilter();
      // Only the visible tab watches for changes. Query the shared task list;
      // do not start a browser scheduler or reload an active task editor.
      let disposed = false, pending = false;
      const signature = JSON.stringify(loaded.items);
      async function changed() {
        if (disposed || pending || document.hidden || !document.getElementById('st-dialog').hidden) return;
        pending = true;
        try {
          const current = await rpc('automation.list');
          if (!disposed && document.getElementById('st-dialog').hidden && JSON.stringify(current.items) !== signature) await A.reload();
        } catch (_) { /* The refresh button reports connection errors on demand. */ }
        finally { pending = false; }
      }
      const timer = window.setInterval(changed, 15000);
      window.addEventListener('focus', changed);
      return () => { disposed = true; window.clearInterval(timer); window.removeEventListener('focus', changed); };
    },
    onToggle() { document.getElementById('st-dlg-body')._scheduleRefresh?.(); },
    onAction(action, el) {
      if (!action.startsWith('schedule-')) return;
      if (action === 'schedule-filter') { statusFilter = el.dataset.val || 'all'; applyStatusFilter(); return; }
      const id = el.dataset.id, row = data.items.find(x => x.id === id);
      if (action === 'schedule-new') { edit(); return; }
      if (action === 'schedule-edit') { edit(row); return; }
      if (action === 'schedule-refresh') { A.reload().catch(reportError); return; }
      if (action === 'schedule-history') { history(id).catch(reportError); return; }
      // Keep the row visible after a pause/resume instead of leaving the
      // current status filter pointing at the state it just left.
      if (action === 'schedule-toggle') statusFilter = row.enabled ? 'paused' : 'active';
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
