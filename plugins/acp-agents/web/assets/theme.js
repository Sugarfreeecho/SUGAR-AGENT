(() => {
  const root = document.documentElement;
  root.dataset.embedded = String(new URLSearchParams(location.search).get('embedded') === '1');
  try {
    const theme = localStorage.getItem('myagent-theme');
    root.className = theme === 'deep-dark' ? 'theme-dark' : ['dark', 'purple'].includes(theme) ? 'theme-purple' : 'theme-light';
    root.lang = localStorage.getItem('myagent-language') === 'en' ? 'en' : 'zh-CN';
    const px = Math.max(12, Math.min(20, parseInt(localStorage.getItem('myagent-font-size-px'), 10) || 16));
    root.style.setProperty('--st-fs', Math.max(11, px - 2) + 'px');
    root.style.setProperty('--st-fs-lg', px + 'px');
  } catch (_) { root.className = 'theme-light'; }
})();
