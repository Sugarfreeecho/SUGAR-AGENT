'use strict'

/** 渲染进程可用的最小桥接接口：只暴露必要的桌面能力。 */

const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('sugarAgentDesktop', {
  info: () => ipcRenderer.invoke('sugaragent:info'),
  restartBackend: () => ipcRenderer.invoke('sugaragent:restart-backend'),
  openLogs: () => ipcRenderer.invoke('sugaragent:open-logs'),
  openWorkDir: () => ipcRenderer.invoke('sugaragent:open-workdir'),
  openExternal: url => ipcRenderer.invoke('sugaragent:open-external', url),
})
