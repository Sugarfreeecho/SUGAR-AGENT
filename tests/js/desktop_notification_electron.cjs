'use strict'

// Opt-in native smoke: one real toast, without showing or focusing a window.
const assert = require('node:assert/strict')
const { app, BrowserWindow, Notification } = require('electron')
const { spawn } = require('node:child_process')
const path = require('node:path')
const { createNotificationBridge } = require('../../packaging/electron/notifications')
const root = path.resolve(__dirname, '../..')

app.whenReady().then(async () => {
  app.setAppUserModelId('com.sugaragent.desktop')
  const window = new BrowserWindow({ show: false })
  await window.loadURL('data:text/html,<title>Notification smoke</title>')
  assert.equal(window.isVisible(), false)
  assert.equal(await window.webContents.executeJavaScript('document.hasFocus()'), false)
  const bridge = await createNotificationBridge({
    Notification, platform: 'win32', icon: path.join(root, 'packaging/assets/tray.ico'),
    log: value => console.log(value), activate: async () => {},
  })
  const script = [
    'import sys',
    'sys.path.insert(0, sys.argv[1])',
    'from desktop_notify import _notify_electron',
    'sys.exit(0 if _notify_electron("SugarAgent", "通知验证：后台会话完成通知已送达") else 1)',
  ].join('\n')
  try {
    const child = spawn(path.join(root, 'python/python.exe'), ['-c', script, path.join(root, 'app')], {
      cwd: root, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONUTF8: '1', SUGARAGENT_NOTIFY_PORT: String(bridge.port), SUGARAGENT_NOTIFY_TOKEN: bridge.token },
    })
    child.stdout.pipe(process.stdout)
    child.stderr.pipe(process.stderr)
    const code = await new Promise((resolve, reject) => {
      child.on('error', reject)
      child.on('exit', resolve)
    })
    assert.equal(code, 0, 'Python must receive a successful native delivery acknowledgement')
    console.log('Native Electron notification delivered while the window was hidden')
  } finally {
    bridge.close()
    window.destroy()
  }
  app.exit(0)
}).catch(error => { console.error(error.stack); app.exit(1) })
