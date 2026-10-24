/* Apply only appearance preferences before paint; no authentication state. */
(() => {
  const root = document.documentElement;
  root.dataset.embedded = String(new URLSearchParams(location.search).get('embedded') === '1');
  try {
    const theme = localStorage.getItem('myagent-theme');
    root.className = theme === 'deep-dark' ? 'theme-dark' : ['dark', 'purple'].includes(theme) ? 'theme-purple' : 'theme-light';
    root.lang = localStorage.getItem('myagent-language') === 'en' ? 'en' : 'zh-CN';
    const raw = parseInt(localStorage.getItem('myagent-font-size-px'), 10);
    const level = localStorage.getItem('myagent-font-level');
    const legacy = level === null ? 16 : [14, 16, 17][Number(level)];
    const px = Math.max(12, Math.min(20, Number.isFinite(raw) ? raw : legacy || 16));
    root.style.setProperty('--st-fs', Math.max(11, px - 2) + 'px');
    root.style.setProperty('--st-fs-lg', px + 'px');
    root.style.setProperty('--st-fs-sm', Math.max(10, px - 3) + 'px');
    root.style.setProperty('--st-fs-xs', Math.max(9, px - 4) + 'px');
  } catch (_error) { root.classList.add('theme-light'); }
})();
