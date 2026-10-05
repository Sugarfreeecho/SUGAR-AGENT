/* ═══════════════════════════════════════════════════════════════════════
   设置中心 · 外壳（注册表 / 导航 / i18n / 主题 / API / 组件 / 弹窗）
   MyAgent · /settings
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  const BOOT = window.__MYAGENT_SETTINGS__ || {};
  /* 内嵌模式：由聊天页浮层用 iframe 打开（齿轮入口），点「返回聊天」= 关浮层。
     后端会下发 embedded，但页面自己也认 iframe —— 不依赖后端是否已重启。 */
  function isFramed() {
    try { return window.self !== window.top; } catch (e) { return true; }
  }
  const EMBEDDED = !!BOOT.embedded || isFramed();
  const SECTIONS = [];
  const LS_LANG = 'myagent-language';
  const LS_THEME = 'myagent-theme';
  const LS_FONT = 'myagent-font-level';
  const LS_FONT_PX = 'myagent-font-size-px';
  /* 字号轴：学 DSH 的整数 px 步进（那边 12–17），这里按 MyAgent 现状把上限放到 20 */
  const FONT_MIN = 12;
  const FONT_MAX = 20;
  const FONT_DEFAULT = 16;
  const FONT_LEVEL_PX = [14, 16, 17];   /* 旧三档 0/1/2 的像素值，用于迁移 */

  const clampFont = (px) => Math.max(FONT_MIN, Math.min(FONT_MAX, px));
  const storedFontPx = () => {
    const raw = parseInt(localStorage.getItem(LS_FONT_PX), 10);
    if (!isNaN(raw)) return clampFont(raw);
    const level = parseInt(localStorage.getItem(LS_FONT), 10);
    return FONT_LEVEL_PX[isNaN(level) || level < 0 || level > 2 ? 1 : level] || FONT_DEFAULT;
  };

  const state = {
    lang: localStorage.getItem(LS_LANG) === 'en' ? 'en' : 'zh',
    section: BOOT.section || 'general',
    dirty: false,
    dirtyMessage: '',
    data: {},        /* 分区数据缓存：sectionId -> payload */
    dialog: null,    /* 当前弹窗 */
    confirm: null,
  };

  const t = (zh, en) => (state.lang === 'zh' ? zh : en);
  const permissionOptions = () => [
    { v: 'ask_for_approval', t: t('请求批准', 'Ask for approval') },
    { v: 'approve_for_me', t: t('替我审批', 'Approve for me') },
    { v: 'full_access', t: t('完全访问权限', 'Full access') },
  ];
  function enhancePaths(root) {
    if (window.MyAgentPathPicker) window.MyAgentPathPicker.scan(root);
    if (window.MyAgentPackageImport) window.MyAgentPackageImport.bind(root);
  }
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.prototype.slice.call((root || document).querySelectorAll(sel));

  /* ── 图标：DSH packages/client/ui-primitives/src/icons/index.tsx（16px 网格、1.3px 描边） ── */
  const ICONS = {
    general: { vb: '0 0 16 16', body: '<path d="M8 9.75012C8.9665 9.75012 9.75 8.96662 9.75 8.00012C9.75 7.03362 8.9665 6.25012 8 6.25012C7.0335 6.25012 6.25 7.03362 6.25 8.00012C6.25 8.96662 7.0335 9.75012 8 9.75012Z" stroke="currentColor"/><path d="M13.0107 7.79377C12.9505 7.89401 12.9205 7.94413 12.9205 7.99951C12.9205 8.0549 12.9505 8.10502 13.0106 8.20528L13.9849 9.83006C14.045 9.93029 14.0751 9.9804 14.0751 10.0358C14.0751 10.0911 14.045 10.1413 13.9849 10.2415L13.0037 11.8777C12.9468 11.9726 12.9184 12.0201 12.8725 12.0461C12.8267 12.072 12.7713 12.072 12.6607 12.072H10.6704C10.5598 12.072 10.5045 12.072 10.4586 12.098C10.4128 12.1239 10.3843 12.1714 10.3274 12.2662L9.33825 13.9142C9.28133 14.009 9.25287 14.0564 9.20703 14.0823C9.16118 14.1083 9.10588 14.1083 8.99529 14.1083H7.00486C6.89426 14.1083 6.83896 14.1083 6.79312 14.0823C6.74727 14.0564 6.71881 14.009 6.6619 13.9142L5.67273 12.2662C5.61581 12.1714 5.58735 12.1239 5.54151 12.098C5.49566 12.072 5.44036 12.072 5.32977 12.072H3.33945C3.2288 12.072 3.17347 12.072 3.12761 12.0461C3.08176 12.0201 3.0533 11.9726 2.9964 11.8777L2.0152 10.2415C1.9551 10.1413 1.92505 10.0911 1.92505 10.0358C1.92505 9.9804 1.9551 9.93029 2.0152 9.83006L2.98951 8.20528C3.04963 8.10502 3.07969 8.0549 3.07969 7.99951C3.07968 7.94413 3.04961 7.89401 2.98946 7.79377L2.01529 6.17011C1.95514 6.06987 1.92507 6.01975 1.92507 5.96437C1.92506 5.90899 1.95512 5.85886 2.01524 5.7586L2.9964 4.1224C3.0533 4.0275 3.08176 3.98005 3.12761 3.95408C3.17347 3.92811 3.2288 3.92811 3.33945 3.92811H5.32977C5.44036 3.92811 5.49566 3.92811 5.54151 3.90216C5.58735 3.87621 5.61581 3.82879 5.67273 3.73397L6.6619 2.08599C6.71881 1.99116 6.74727 1.94375 6.79312 1.9178C6.83896 1.89185 6.89426 1.89185 7.00486 1.89185H8.99529C9.10588 1.89185 9.16118 1.89185 9.20703 1.9178C9.25287 1.94375 9.28133 1.99116 9.33825 2.08599L10.3274 3.73397C10.3843 3.82879 10.4128 3.87621 10.4586 3.90216C10.5045 3.92811 10.5598 3.92811 10.6704 3.92811H12.6607C12.7713 3.92811 12.8267 3.92811 12.8725 3.95408C12.9184 3.98005 12.9468 4.0275 13.0037 4.1224L13.9849 5.7586C14.045 5.85886 14.0751 5.90899 14.0751 5.96437C14.0751 6.01975 14.045 6.06987 13.9849 6.17011L13.0107 7.79377Z" stroke="currentColor" stroke-miterlimit="10"/>' },
    model: { vb: '0 0 16 16', body: '<path d="M7.8667 0.349609C8.96906 0.349634 10.0601 0.481272 11.0317 0.735352C11.9973 0.987845 12.8453 1.362 13.4644 1.84766C14.0744 2.32629 14.507 2.95539 14.5161 3.69336H14.5171V8.53516C14.0843 8.32076 13.6108 8.17679 13.1108 8.11816C13.1831 7.96848 13.2162 7.82856 13.2163 7.70312V5.76758C12.6269 6.16618 11.8739 6.47995 11.0317 6.7002C10.0602 6.95423 8.96896 7.08494 7.8667 7.08496C6.76461 7.08493 5.67411 6.95415 4.70264 6.7002C3.85994 6.48006 3.10694 6.1662 2.51709 5.76758V7.70312L2.521 7.78418C2.56374 8.19554 2.93361 8.74414 3.91357 9.23145C4.9281 9.73585 6.35004 10.0371 7.8667 10.0371C8.26373 10.0371 8.6543 10.0141 9.03271 9.97461C8.75596 10.3799 8.54664 10.8349 8.42041 11.3232C8.23666 11.3313 8.0518 11.3369 7.8667 11.3369C6.20108 11.3369 4.57025 11.01 3.33447 10.3955C3.04163 10.2499 2.76658 10.0836 2.51709 9.90039V11.6738C2.51728 12.1379 2.88589 12.7556 3.92236 13.292C4.93457 13.8157 6.35342 14.1289 7.8667 14.1289C8.12318 14.1289 8.37694 14.1161 8.62646 14.0986C8.82021 14.5535 9.08999 14.9682 9.41943 15.3271C8.91285 15.3934 8.39149 15.4287 7.8667 15.4287C6.19761 15.4287 4.56379 15.0869 3.32568 14.4463C2.11244 13.8185 1.21649 12.8562 1.21631 11.6738V3.76367C1.21595 3.74853 1.21438 3.733 1.21436 3.71777C1.21436 2.96917 1.65103 2.33053 2.26807 1.84668C2.88747 1.36112 3.73675 0.987685 4.70264 0.735352C5.67413 0.481376 6.76457 0.349636 7.8667 0.349609ZM7.8667 1.65039C6.86269 1.65042 5.88326 1.77028 5.03076 1.99316C4.17183 2.2176 3.50421 2.52956 3.06982 2.87012C2.65043 3.19909 2.52622 3.48898 2.51709 3.69336V3.74414C2.52719 3.94845 2.65185 4.23772 3.06982 4.56543C3.50425 4.90601 4.17172 5.21795 5.03076 5.44238C5.88326 5.66527 6.8627 5.78513 7.8667 5.78516C8.8707 5.78513 9.85015 5.66525 10.7026 5.44238C11.5611 5.21787 12.2286 4.9049 12.6626 4.56445C13.0982 4.22252 13.2163 3.9231 13.2163 3.71777L13.2104 3.63574C13.1818 3.43623 13.044 3.16941 12.6626 2.87012C12.2286 2.52957 11.5614 2.21773 10.7026 1.99316C9.85009 1.77025 8.8708 1.65041 7.8667 1.65039Z" fill="currentColor" stroke="none"/><path d="M12.8936 10.0361L13.2061 10.5566C13.2296 10.5959 13.2651 10.6562 13.3027 10.707C13.3469 10.7666 13.4148 10.8431 13.5195 10.9023C13.6244 10.9617 13.725 10.9801 13.7988 10.9873C13.8619 10.9934 13.9318 10.9932 13.9775 10.9932H14.6162L14.8896 11.4502L14.5947 11.9443C14.5698 11.9859 14.5312 12.0483 14.5029 12.1084C14.4781 12.1611 14.4514 12.2312 14.4395 12.3164L14.4326 12.4072L14.4395 12.4971C14.4514 12.5825 14.4781 12.6532 14.5029 12.7061C14.5312 12.7661 14.5689 12.8287 14.5938 12.8701L14.8896 13.3633L14.6162 13.8213H13.9775C13.9318 13.8213 13.8619 13.821 13.7988 13.8271C13.7433 13.8326 13.6728 13.8442 13.5967 13.875L13.5195 13.9121C13.4148 13.9714 13.3469 14.0478 13.3027 14.1074C13.265 14.1583 13.2296 14.2186 13.2061 14.2578L12.8936 14.7783H12.3115L11.999 14.2578C11.9755 14.2186 11.9401 14.1583 11.9023 14.1074C11.8693 14.0628 11.823 14.0083 11.7578 13.959L11.6855 13.9121L11.6074 13.875C11.5316 13.8445 11.4615 13.8325 11.4062 13.8271C11.3432 13.821 11.2733 13.8213 11.2275 13.8213H10.5889L10.3135 13.3633L10.6104 12.8701C10.6352 12.8287 10.6739 12.7661 10.7021 12.7061C10.7352 12.6357 10.7724 12.534 10.7725 12.4072C10.7724 12.2804 10.7352 12.1788 10.7021 12.1084C10.6739 12.0483 10.6353 11.9859 10.6104 11.9443L10.3135 11.4502L10.5889 10.9932H11.2275C11.2733 10.9932 11.3432 10.9934 11.4062 10.9873C11.4801 10.9801 11.5808 10.9616 11.6855 10.9023C11.7903 10.843 11.8582 10.7666 11.9023 10.707C11.94 10.6562 11.9755 10.5959 11.999 10.5566L12.3115 10.0361H12.8936Z" stroke="currentColor" stroke-miterlimit="10"/>' },
    skills: { vb: '0 0 17 17', body: '<path d="M4.57788 5.77124H10.7029" stroke="currentColor"/><path d="M4.57788 8.89819H7.91879" stroke="currentColor"/><path d="M12.1404 1.19446C12.9442 1.19446 13.6404 1.81999 13.6404 2.64465V8.89856H12.6404V2.64465C12.6404 2.42015 12.4411 2.19446 12.1404 2.19446H3.14038C2.83968 2.19446 2.64038 2.42015 2.64038 2.64465V13.0929C2.64082 13.3172 2.84001 13.5421 3.14038 13.5421H8.88159V14.5421H3.14038C2.33675 14.5421 1.6408 13.9172 1.64038 13.0929V2.64465C1.64038 1.81999 2.33651 1.19446 3.14038 1.19446H12.1404Z" fill="currentColor" stroke="none"/><path d="M12.0051 15.1056C12.0051 13.6395 10.8166 12.451 9.35059 12.451C10.8166 12.451 12.0051 11.2626 12.0051 9.79651C12.0051 11.2626 13.1936 12.451 14.6597 12.451C13.1936 12.451 12.0051 13.6395 12.0051 15.1056Z" stroke="currentColor"/>' },
    plugins: { vb: '0 0 24 24', sw: 1.6, body: '<path d="M9 4v4M15 4v4"/><path d="M6 8h12v5a6 6 0 0 1-12 0z"/><path d="M12 19v2"/>' },
    hooks: { vb: '0 0 16 16', body: '<path d="M6.59961 9.40051C6.82779 9.6334 7.10015 9.81842 7.40074 9.94472C7.70132 10.071 8.02409 10.1361 8.35013 10.1361C8.67618 10.1361 8.99894 10.071 9.29953 9.94472C9.60011 9.81842 9.87247 9.6334 10.1007 9.40051L12.9015 6.59967C13.3658 6.13541 13.6266 5.50572 13.6266 4.84915C13.6266 4.19258 13.3658 3.56289 12.9015 3.09863C12.4372 2.63436 11.8075 2.37354 11.151 2.37354C10.4944 2.37354 9.86472 2.63436 9.40045 3.09863L9.05034 3.44873" stroke="currentColor"/><path d="M9.40051 6.59959C9.17233 6.3667 8.89997 6.18169 8.59939 6.05538C8.2988 5.92907 7.97603 5.86401 7.64999 5.86401C7.32395 5.86401 7.00118 5.92907 6.70059 6.05538C6.40001 6.18169 6.12765 6.3667 5.89946 6.59959L3.09863 9.40043C2.63436 9.8647 2.37354 10.4944 2.37354 11.151C2.37354 11.8075 2.63436 12.4372 3.09863 12.9015C3.56289 13.3657 4.19258 13.6266 4.84915 13.6266C5.50572 13.6266 6.13541 13.3657 6.59967 12.9015L6.94978 12.5514" stroke="currentColor"/>' },
    mcp: { vb: '0 0 24 24', sw: 1.6, body: '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01"/>' },
    security: { vb: '0 0 24 24', sw: 1.6, body: '<path d="M12 3l7 3v5.5c0 4.4-3 8.1-7 9.5-4-1.4-7-5.1-7-9.5V6z"/><path d="M9.4 12l1.9 1.9 3.6-3.8"/>' },
    env: { vb: '0 0 16 16', body: '<path d="M6.27612 1.5L4.52612 14.5" stroke="currentColor"/><path d="M11.4739 1.5L9.72388 14.5" stroke="currentColor"/><path d="M2.39868 5.5H14.0681" stroke="currentColor"/><path d="M1.93188 10.5H13.6013" stroke="currentColor"/>' },
    path: { vb: '0 0 16 16', body: '<path d="M12.3994 13.5986H2.04956C1.49728 13.5986 1.04956 13.1509 1.04956 12.5986V3.40137C1.04956 2.84908 1.49728 2.40137 2.04956 2.40137H4.76632C5.01016 2.40137 5.24561 2.49046 5.42836 2.6519L6.94088 3.98799C7.12364 4.14943 7.35908 4.23852 7.60293 4.23852H12.3994C12.9517 4.23852 13.3994 4.68624 13.3994 5.23852V7.16991" stroke="currentColor"/><path d="M2.55911 7.93683C2.67584 7.49906 3.07229 7.19446 3.52536 7.19446H13.6491C14.3061 7.19446 14.7846 7.81725 14.6153 8.45209L13.4411 12.856C13.3244 13.2938 12.9279 13.5984 12.4748 13.5984H2.35113C1.69411 13.5984 1.21562 12.9756 1.38489 12.3407L2.55911 7.93683Z" stroke="currentColor"/>' },
    chevron: { vb: '0 0 16 16', body: '<path d="M6 4l4 4-4 4" stroke="currentColor"/>' },
    search: { vb: '0 0 16 16', body: '<circle cx="7" cy="7" r="4.5" stroke="currentColor"/><path d="M10.4 10.4L14 14" stroke="currentColor"/>' },
  };
  const icon = (key, size) => {
    const d = ICONS[key] || ICONS.general;
    const px = size || 16;
    return '<svg width="' + px + '" height="' + px + '" viewBox="' + d.vb + '" fill="none" stroke="currentColor" stroke-width="' + (d.sw || 1.3) + '" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + d.body + '</svg>';
  };

  /* ── API ─────────────────────────────────────────────────────────────── */
  async function api(path, options) {
    const opts = Object.assign({ credentials: 'same-origin', headers: {} }, options || {});
    if (opts.body !== undefined && typeof opts.body !== 'string') {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(path, opts);
    let data = null;
    try { data = await res.json(); } catch (e) { data = null; }
    if (!res.ok) {
      const msg = (data && (data.error || data.detail)) || ('HTTP ' + res.status);
      throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
    if (data && data.ok === false) throw new Error(data.error || t('请求失败', 'Request failed'));
    return data || {};
  }

  /* ── 组件 ────────────────────────────────────────────────────────────── */
  const W = {
    card: (title, hint, inner, actions) => '<div class="st-card">' +
      (title ? '<div class="st-card-head"><span class="st-t">' + title + '</span>' +
        (hint ? '<span class="st-h">' + hint + '</span>' : '') +
        '<span class="st-acts">' + (actions || '') + '</span></div>' : '') + inner + '</div>',
    row: (label, hint, ctl, cls, searchText) => '<div class="st-row ' + (cls || '') + '"' +
      (searchText == null ? '' : ' data-search-text="' + esc(searchText) + '"') + '>' +
      '<div><div class="st-label">' + label + '</div>' + (hint ? '<div class="st-hint">' + hint + '</div>' : '') + '</div>' +
      '<div class="st-ctl">' + ctl + '</div></div>',
    lrow: (title, sub, acts, searchText) => '<div class="st-lrow"' +
      (searchText == null ? '' : ' data-search-text="' + esc(searchText) + '"') + '><div class="st-li-main">' +
      '<div class="st-li-t">' + title + '</div>' + (sub ? '<div class="st-li-s">' + sub + '</div>' : '') +
      '</div><div class="st-li-act">' + (acts || '') + '</div></div>',
    seg: (key, value, options) => '<div class="st-seg">' + options.map((o) =>
      '<button type="button" data-act="seg" data-key="' + key + '" data-val="' + esc(o.v) + '" class="' +
      (String(value) === String(o.v) ? 'is-on' : '') + '">' + o.t + '</button>').join('') + '</div>',
    sw: (key, on, attrs) => '<button type="button" class="st-sw' + (on ? ' is-on' : '') + '" data-act="toggle" data-key="' +
      esc(key) + '" role="switch" aria-checked="' + (on ? 'true' : 'false') + '" ' + (attrs || '') + '></button>',
    btn: (label, act, kind, attrs) => '<button type="button" class="st-btn ' + (kind || '') + '" data-act="' +
      (act || 'noop') + '" ' + (attrs || '') + '>' + label + '</button>',
    chip: (text) => '<span class="st-chip">' + text + '</span>',
    status: (kind, text) => '<span class="st-status ' + kind + '"><i></i>' + text + '</span>',
    /* 悬停/聚焦浮框：详情类的字段（如技能说明）不该在列表里铺开，挂在这里按需看 */
    tip: (label, text, cls) => '<span class="st-tip-target' + (cls ? ' ' + cls : '') + '" tabindex="0" data-tip="' +
      esc(text || '') + '">' + label + '</span>',
    /* 字号步进器（学 DSH FontSizeRow）：药丸里是可输入的数值，右侧悬浮上下箭头，尾巴跟 px 单位 */
    fontStepper: (px) => '<span class="st-stepper">' +
      '<input class="st-stepper-input" data-act="font-size-input" type="text" inputmode="numeric" autocomplete="off" spellcheck="false" ' +
        'aria-label="' + esc(t('字号（px）', 'Font size (px)')) + '" value="' + esc(String(px)) + '">' +
      '<span class="st-stepper-arrows">' +
        '<button type="button" class="st-stepper-arrow" data-act="font-up" aria-label="' + esc(t('增大字号', 'Increase font size')) + '">' +
          '<svg width="9" height="9" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 10l4-4 4 4"/></svg>' +
        '</button>' +
        '<button type="button" class="st-stepper-arrow" data-act="font-down" aria-label="' + esc(t('减小字号', 'Decrease font size')) + '">' +
          '<svg width="9" height="9" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6l4 4 4-4"/></svg>' +
        '</button>' +
      '</span></span><span class="st-unit">px</span>',
    input: (key, value, ph, type) => '<input class="st-input" type="' + (type || 'text') + '" data-field="' + esc(key) +
      '" value="' + esc(value == null ? '' : value) + '" placeholder="' + esc(ph || '') + '">',
    note: (html) => '<div class="st-note">' + html + '</div>',
    empty: (text) => '<div class="st-empty">' + text + '</div>',
    adv: (title, inner, open) => '<details class="st-adv"' + (open ? ' open' : '') + '><summary>' +
      '<svg class="st-caret" width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
      ICONS.chevron.body + '</svg>' + title + '</summary><div class="st-inner">' + inner + '</div></details>',
    search: (placeholder, value) => '<div class="st-search">' + icon('search', 14) +
      '<input data-act="search" placeholder="' + esc(placeholder) + '" value="' + esc(value || '') + '"></div>',
  };

  /* ── 提示 / 确认 / 弹窗 ──────────────────────────────────────────────── */
  let toastTimer = null;
  /* 悬停浮框：一个单例气泡，跟随 [data-tip] 的目标定位（超出视口会翻到上方） */
  let tipEl = null;
  function ensureTip() {
    if (!tipEl) {
      tipEl = document.createElement('div');
      tipEl.className = 'st-tip';
      tipEl.hidden = true;
      document.body.appendChild(tipEl);
    }
    return tipEl;
  }
  function showTip(target) {
    const text = target && target.getAttribute ? target.getAttribute('data-tip') : '';
    const el = ensureTip();
    if (!text) { el.hidden = true; return; }
    el.textContent = text;
    el.hidden = false;
    const rect = target.getBoundingClientRect();
    const box = el.getBoundingClientRect();
    const left = Math.max(8, Math.min(rect.left, window.innerWidth - box.width - 8));
    let top = rect.bottom + 8;
    if (top + box.height > window.innerHeight - 8) top = Math.max(8, rect.top - box.height - 8);
    el.style.left = left + 'px';
    el.style.top = top + 'px';
  }
  function hideTip() { if (tipEl) tipEl.hidden = true; }
  function toast(message, isError) {
    const el = $('#st-toast');
    el.textContent = message;
    el.classList.toggle('err', !!isError);
    el.classList.add('is-on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('is-on'), isError ? 3200 : 1800);
  }
  function reportError(err) {
    console.error(err);
    toast(t('操作失败：', 'Failed: ') + (err && err.message ? err.message : err), true);
  }

  function askConfirm(message, onOk) {
    state.confirm = onOk;
    $('#st-cf-body').textContent = message;
    $('#st-confirm').hidden = false;
  }

  function openDialog(cfg) {
    state.dialog = cfg;
    $('#st-dlg-title').textContent = cfg.title || '';
    $('#st-dlg-sub').textContent = cfg.sub || '';
    $('#st-dlg-sub').hidden = !cfg.sub;
    $('#st-dlg-body').innerHTML = cfg.body || '';
    $('#st-dlg-ok').textContent = cfg.okText || t('保存', 'Save');
    $('#st-dialog').hidden = false;
    if (cfg.after) cfg.after($('#st-dlg-body'));
    enhancePaths($('#st-dlg-body'));
  }
  function closeDialog() { state.dialog = null; $('#st-dialog').hidden = true; }
  function dialogValue(field) {
    const el = $('[data-field="' + field + '"]', $('#st-dlg-body'));
    return el ? el.value.trim() : '';
  }

  /* ── 脏值 / 保存条 ───────────────────────────────────────────────────── */
  function setDirty(dirty, message) {
    state.dirty = !!dirty;
    state.dirtyMessage = message || '';
    updateFooter();
  }
  function updateFooter() {
    const section = current();
    const explicit = !!(section && section.mode === 'explicit');
    $('#st-footer').hidden = !explicit;
    if (!explicit) return;
    /* 显式保存的分区：保存条常驻，脏值优先提示 */
    $('#st-dirty-msg').textContent = state.dirty
      ? (state.dirtyMessage || t('有未保存的更改', 'Unsaved changes'))
      : t('改完点「保存」才会写入', 'Click Save to apply changes');
  }

  /* ── 主题 / 字体（与聊天页共用同一批 localStorage 键） ───────────────── */
  function applyThemeFromStorage() {
    const raw = localStorage.getItem(LS_THEME);
    const root = document.documentElement;
    root.classList.remove('theme-light', 'theme-dark', 'theme-purple');
    if (raw === 'deep-dark') root.classList.add('theme-dark');
    else if (raw === 'purple') root.classList.add('theme-purple');
    else if (raw === 'dark') root.classList.add('theme-purple');
    else root.classList.add('theme-light');
    applyFontFromStorage();
  }
  function applyFontFromStorage() {
    applyStFontSize(storedFontPx());
  }
  /* 设置中心自己的文字尺度跟着字号轴走：比正文低 2px 为基准，其余档位保持原先的相对关系 */
  function applyStFontSize(px) {
    const base = Math.max(11, clampFont(px) - 2);
    const root = document.documentElement;
    root.setAttribute('data-font-size', String(clampFont(px)));
    root.style.setProperty('--st-fs', base + 'px');
    root.style.setProperty('--st-fs-lg', (base + 2) + 'px');
    root.style.setProperty('--st-fs-sm', (base - 0.5) + 'px');
    root.style.setProperty('--st-fs-xs', (base - 1.5) + 'px');
  }

  /* ── 导航 / 分区渲染 ────────────────────────────────────────────────── */
  function current() { return SECTIONS.filter((s) => s.id === state.section)[0] || SECTIONS[0]; }

  function renderNav() {
    $('#st-nav-list').innerHTML = SECTIONS.map((s) => '<button type="button" class="st-cell' +
      (s.id === state.section ? ' is-on' : '') + '" data-act="nav" data-id="' + esc(s.id) + '">' +
      icon(s.icon) + '<span class="st-lbl">' + esc(t(s.zh, s.en)) + '</span></button>').join('');
  }

  let searchTimer = null;
  let sectionLoadEpoch = 0;

  function filterSearchRows() {
    const body = $('#st-body');
    const q = String(state.search || '').toLowerCase();
    const rows = Array.from(body.querySelectorAll('[data-search-text]'));
    rows.forEach((row) => { row.hidden = !!q && row.dataset.searchText.toLowerCase().indexOf(q) < 0; });
    body.querySelectorAll('.st-card').forEach((card) => {
      const items = Array.from(card.querySelectorAll('[data-search-text]'));
      card.hidden = items.length > 0 && items.every((row) => row.hidden);
    });
    const empty = body.querySelector('[data-search-empty]');
    if (empty) empty.hidden = !rows.length || rows.some((row) => !row.hidden);
  }

  function canLeaveSettings() {
    return !state.dirty || !current() || current().mode !== 'explicit' ||
      window.confirm(t('有未保存的更改，仍要离开吗？', 'Unsaved changes. Leave anyway?'));
  }

  async function showSection(id, options) {
    const section = SECTIONS.filter((s) => s.id === id)[0];
    if (!section) return;
    if (!options || !options.force) {
      if (!canLeaveSettings()) return;
    }
    const previousSection = state.section;
    const loadEpoch = ++sectionLoadEpoch;
    clearTimeout(searchTimer);
    hideTip();
    state.section = id;
    state.dirty = false;
    /* 只有真正换分区才清搜索词：分区内的 reload()（搜索补全、增删改后刷新）必须留着它，
       否则「技能 / 环境变量」的搜索框一敲字就被自己清空，看着像搜索坏了。 */
    if (previousSection !== id) state.search = '';
    if (location.hash !== '#' + id) {
      try { history.replaceState(null, '', '#' + id); } catch (e) { location.hash = id; }
    }
    renderNav();
    $('#st-title').textContent = t(section.zh, section.en);
    $('#st-sub').textContent = t(section.zhSub || '', section.enSub || '');
    updateFooter();
    const body = $('#st-body');
    body.innerHTML = '<div class="st-empty">' + t('加载中…', 'Loading…') + '</div>';
    try {
      if (section.load) state.data[id] = await section.load();
    } catch (err) {
      state.data[id] = { __error: err };
    }
    if (loadEpoch !== sectionLoadEpoch || state.section !== id) return;
    const data = state.data[id];
    if (data && data.__error) {
      body.innerHTML = W.note('<b>' + t('加载失败', 'Failed to load') + '：</b>' + esc(data.__error.message || data.__error) +
        '<br>' + t('若这是首次使用，请先完成配置向导。', 'If this is a fresh install, finish the setup wizard first.'));
      return;
    }
    try {
      body.innerHTML = section.render(data);
    } catch (err) {
      console.error(err);
      body.innerHTML = W.note('<b>' + t('这个分区渲染失败了', 'This section failed to render') + '：</b>' +
        esc(err && err.message ? err.message : err));
      return;
    }
    body.scrollTop = 0;
    if (section.after) section.after(body, data);
    enhancePaths(body);
    if (section.onSearch) section.onSearch(state.search || '');
  }

  function reload() { return showSection(state.section, { force: true }); }

  /* ── 全局事件 ───────────────────────────────────────────────────────── */
  function bindShell() {
    document.addEventListener('click', (event) => {
      const el = event.target.closest('[data-act]');
      if (!el) {
        if (!$('#st-confirm').hidden && event.target.id === 'st-confirm') askConfirmHide();
        else if (!$('#st-dialog').hidden && event.target.id === 'st-dialog') closeDialog();
        return;
      }
      const act = el.dataset.act;
      if (act === 'nav') { showSection(el.dataset.id); return; }
      if (act === 'cf-cancel') { askConfirmHide(); return; }
      if (act === 'cf-ok') { const fn = state.confirm; askConfirmHide(); if (fn) fn(); return; }
      if (act === 'dlg-cancel') { closeDialog(); return; }
      if (act === 'dlg-ok') {
        const cfg = state.dialog;
        if (!cfg) return;
        Promise.resolve()
          .then(() => cfg.onOk && cfg.onOk())
          .then((keep) => { if (keep !== true) closeDialog(); })
          .catch(reportError);
        return;
      }
      if (act === 'seg') {
        if (state.dialog && state.dialog.onSeg && state.dialog.onSeg(el.dataset.key, el.dataset.val)) return;
        const handler = current() && current().onSeg;
        if (handler && handler(el.dataset.key, el.dataset.val, el)) return;
        return;
      }
      if (act === 'toggle') {
        const on = !el.classList.contains('is-on');
        el.classList.toggle('is-on', on);
        el.setAttribute('aria-checked', String(on));
        const handler = current() && current().onToggle;
        if (handler) handler(el.dataset.key, on, el);
        return;
      }
      const section = current();
      if (section && section.onAction) section.onAction(act, el);
    });

    document.addEventListener('input', (event) => {
      const el = event.target;
      if (el.matches('[data-act="search"]')) {
        state.search = el.value;
        const section = current();
        if (section && section.onSearch) {
          clearTimeout(searchTimer);
          searchTimer = setTimeout(() => {
            if (current() === section) section.onSearch(state.search);
          }, 150);
        }
        return;
      }
      if (el.matches('[data-act="font-size-input"]')) {
        /* 只留数字，边输边生效（离焦/回车时由分区把值规范化） */
        const cleaned = String(el.value || '').replace(/[^0-9]/g, '').slice(0, 2);
        if (cleaned !== el.value) el.value = cleaned;
        const section = current();
        if (section && section.onFontInput) section.onFontInput(cleaned);
        return;
      }
      if (el.closest('#st-body')) {
        const section = current();
        if (section && section.mode === 'explicit') setDirty(true, section.dirtyMessage && t(section.dirtyMessage[0], section.dirtyMessage[1]));
      }
    });

    $('#st-back').addEventListener('click', () => { leaveSettings(); });

    /* 悬停 / 聚焦浮框（事件委托，动态渲染的内容也生效） */
    document.addEventListener('mouseover', (event) => {
      const el = event.target && event.target.closest ? event.target.closest('[data-tip]') : null;
      if (el) showTip(el); else hideTip();
    });
    document.addEventListener('mouseout', (event) => {
      const el = event.target && event.target.closest ? event.target.closest('[data-tip]') : null;
      if (el) hideTip();
    });
    document.addEventListener('focusin', (event) => {
      const el = event.target && event.target.closest ? event.target.closest('[data-tip]') : null;
      if (el) showTip(el);
    });
    document.addEventListener('focusout', () => { hideTip(); });
    document.addEventListener('scroll', () => { hideTip(); }, true);

    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape' || event.defaultPrevented) return;
      if (!$('#st-confirm').hidden) { event.preventDefault(); askConfirmHide(); }
      else if (!$('#st-dialog').hidden) { event.preventDefault(); closeDialog(); }
      else if (EMBEDDED) { event.preventDefault(); leaveSettings(); }
    });
    if (EMBEDDED) {
      document.documentElement.classList.add('st-embedded');
      const stage = document.querySelector('.st-stage');
      if (stage) {
        stage.addEventListener('click', (event) => { if (event.target === stage) leaveSettings(); });
      }
    }
    $('#st-lang').addEventListener('click', () => {
      if (!canLeaveSettings()) return;
      state.lang = state.lang === 'zh' ? 'en' : 'zh';
      localStorage.setItem(LS_LANG, state.lang === 'en' ? 'en' : 'zh-CN');
      document.documentElement.lang = state.lang === 'en' ? 'en' : 'zh-CN';
      renderNav();
      showSection(state.section, { force: true });
    });
    $('#st-footer').addEventListener('click', (event) => {
      const el = event.target.closest('[data-act]');
      if (!el) return;
      if (el.dataset.act === 'discard') { setDirty(false); showSection(state.section, { force: true }); }
      if (el.dataset.act === 'save') {
        const section = current();
        if (section && section.save) {
          Promise.resolve(section.save(state.data[section.id]))
            .then(() => { setDirty(false); toast(t('已保存并生效', 'Saved')); return showSection(section.id, { force: true }); })
            .catch(reportError);
        }
      }
    });
    window.addEventListener('hashchange', () => {
      const id = location.hash.replace('#', '').split('?')[0];
      if (id && id !== state.section) showSection(id);
    });
  }
  function askConfirmHide() { state.confirm = null; $('#st-confirm').hidden = true; }

  function leaveSettings() {
    if (!canLeaveSettings()) return;
    setDirty(false);
    if (EMBEDDED) {
      try { window.parent.postMessage({ type: 'myagent:settings-close' }, window.location.origin); } catch (e) { /* ignore */ }
      return;
    }
    window.location.href = '/';
  }

  /* 偏好（主题 / 字号 / 会话列表 / 语言）实时回推给宿主聊天页，边改边变 */
  function notifyHostPrefs() {
    if (!EMBEDDED) return;
    const read = (key) => { try { return localStorage.getItem(key); } catch (e) { return null; } };
    const prefs = {
      theme: read('myagent-theme'),
      font: read('myagent-font-level'),
      fontPx: read('myagent-font-size-px'),
      list: read('myagent-session-list-mode'),
      lang: read('myagent-language'),
      permissionMode: read('myagent-new-session-permission-mode') || '',
    };
    try { window.parent.postMessage({ type: 'myagent:settings-prefs', prefs }, window.location.origin); } catch (e) { /* ignore */ }
  }

  /* 与聊天页共用的偏好键：写 localStorage 的同时立刻回推宿主 —— 浮层开着也能看到背景实时变化 */
  const PREF_KEYS = {
    theme: 'myagent-theme',
    font: 'myagent-font-level',
    fontPx: 'myagent-font-size-px',
    list: 'myagent-session-list-mode',
    lang: 'myagent-language',
  };
  function setPref(name, value) {
    const patch = {};
    patch[name] = value;
    setPrefs(patch);
  }
  /* 一次写多个偏好只回推一次（字号同时要落 px 与新档位映射） */
  function setPrefs(patch) {
    Object.keys(patch || {}).forEach((name) => {
      const key = PREF_KEYS[name] || name;
      const value = patch[name];
      try {
        if (value === null || value === undefined || value === '') localStorage.removeItem(key);
        else localStorage.setItem(key, value);
      } catch (e) { /* ignore */ }
    });
    notifyHostPrefs();
  }

  /* ── 对外接口 ───────────────────────────────────────────────────────── */
  window.MyAgentSettings = {
    registerSection(def) { SECTIONS.push(def); },
    replacePluginSections(definitions) {
      for (let index = SECTIONS.length - 1; index >= 0; index--) {
        if (SECTIONS[index].pluginOwned) SECTIONS.splice(index, 1);
      }
      SECTIONS.push(...definitions);
      renderNav();
      if (state.section.startsWith('plugin:') && !SECTIONS.some((section) => section.id === state.section)) showSection('plugins', { force: true });
    },
    t, esc, api, W, icon, toast, reportError, askConfirm, openDialog, closeDialog, dialogValue, enhancePaths, permissionOptions,
    setDirty, setDirtyMessage(zh, en) { state.dirtyMessage = t(zh, en); updateFooter(); },
    reload, showSection, notifyHostPrefs, setPref, setPrefs, filterSearchRows,
    requestClose: leaveSettings,
    storedFontPx, applyStFontSize, clampFont, FONT_MIN, FONT_MAX, FONT_DEFAULT, FONT_LEVEL_PX,
    get lang() { return state.lang; },
    get search() { return state.search || ''; },
    boot() {
      applyThemeFromStorage();
      document.documentElement.lang = state.lang === 'en' ? 'en' : 'zh-CN';
      $('#st-back').textContent = t('返回聊天', 'Back to chat');
      $('#st-lang').textContent = '中/EN';
      $('#st-dirty-msg').textContent = t('有未保存的更改', 'Unsaved changes');
      $('#st-cf-title').textContent = t('确认操作', 'Confirm');
      $('#st-dlg-title').textContent = '';
      bindShell();
      const hash = location.hash.replace('#', '').split('?')[0];
      const initial = SECTIONS.some((s) => s.id === hash) ? hash : hash.startsWith('plugin:') ? 'plugins' : state.section;
      showSection(SECTIONS.some((s) => s.id === initial) ? initial : SECTIONS[0].id, { force: true });
      if (this.loadPluginSections) {
        const epoch = sectionLoadEpoch;
        this.loadPluginSections().then(() => {
          if (epoch === sectionLoadEpoch && hash.startsWith('plugin:') && SECTIONS.some((s) => s.id === hash)) showSection(hash, { force: true });
        }).catch((error) => console.warn('Plugin settings unavailable', error));
      }
    },
    bootSection: BOOT,
  };
})();
