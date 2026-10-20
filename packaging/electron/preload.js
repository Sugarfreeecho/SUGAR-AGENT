'use strict'

/** 渲染进程可用的最小桥接接口：只暴露必要的桌面能力。 */

const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('sugarAgentDesktop', {
  info: () => ipcRenderer.invoke('sugaragent:info'),
  restartBackend: () => ipcRenderer.invoke('sugaragent:restart-backend'),
  openLogs: () => ipcRenderer.invoke('sugaragent:open-logs'),
  openWorkDir: () => ipcRenderer.invoke('sugaragent:open-workdir'),
  openLocalPath: request => ipcRenderer.invoke('sugaragent:open-local-path', request),
  openExternal: url => ipcRenderer.invoke('sugaragent:open-external', url),
})

// 在隔离的 preload 中观察顶层页面主题，兼容聊天页、设置页和首启向导。
// 不依赖某个前端构建版本，也不会把 Node/Electron 能力交给页面脚本。
if (process.isMainFrame) {
  window.addEventListener('DOMContentLoaded', () => {
    const root = document.documentElement
    let lastTheme = ''
    let lastLanguage = ''
    const syncTheme = () => {
      let language = root.lang
      if (!language) {
        try { language = localStorage.getItem('myagent-language') || '' } catch { /* Chinese default */ }
      }
      language = language === 'en' ? 'en' : 'zh-CN'
      if (language !== lastLanguage) {
        lastLanguage = language
        ipcRenderer.send('sugaragent:language', language)
      }
      let theme
      if (root.classList.contains('theme-light')) theme = 'light'
      else if (root.classList.contains('theme-dark')) theme = 'dark'
      else if (root.classList.contains('theme-purple')) theme = 'purple'
      else if (['light', 'dark', 'purple'].includes(root.dataset.theme)) theme = root.dataset.theme
      else {
        // 首启向导的深色样式只有 :root，没有显式 theme-dark 类。
        let stored = ''
        try { stored = localStorage.getItem('myagent-theme') || '' } catch { /* 默认浅色 */ }
        theme = stored === 'deep-dark' ? 'dark' : (stored === 'dark' || stored === 'purple' ? 'purple' : 'light')
      }
      if (theme === lastTheme) return
      lastTheme = theme
      ipcRenderer.send('sugaragent:theme', theme)
    }
    new MutationObserver(syncTheme).observe(root, { attributes: true, attributeFilter: ['class', 'data-theme', 'lang'] })
    syncTheme()
  }, { once: true })
}
