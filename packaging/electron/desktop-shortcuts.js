'use strict'

const fs = require('node:fs')
const path = require('node:path').win32

/** Remove only legacy Electron shortcuts owned by this packaged installation. */
function removeLegacyElectronShortcuts({ app, shell, execPath, log }) {
  if (process.platform !== 'win32' || !app.isPackaged) return
  const root = path.dirname(execPath)
  const owned = new Set([execPath, path.join(root, 'SugarAgent.exe'), path.join(root, 'SugarAgentRuntime.exe')]
    .map(value => path.normalize(value).toLowerCase()))
  for (const directory of [app.getPath('desktop'), path.join(app.getPath('appData'), 'Microsoft', 'Windows', 'Start Menu', 'Programs')]) {
    const shortcut = path.join(directory, 'Electron.lnk')
    if (!fs.existsSync(shortcut)) continue
    try {
      const { target } = shell.readShortcutLink(shortcut)
      if (!path.isAbsolute(target) || !owned.has(path.normalize(target).toLowerCase())) continue
      fs.unlinkSync(shortcut)
      log(`已移除本应用的旧 Electron 快捷方式：${shortcut}`)
    } catch (error) {
      log(`旧 Electron 快捷方式检查失败：${error.message}`)
    }
  }
}

module.exports = { removeLegacyElectronShortcuts }
