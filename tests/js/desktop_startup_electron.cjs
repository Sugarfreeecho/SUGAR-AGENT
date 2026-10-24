'use strict'

// Exercise the real startup page and navigation in a hidden offscreen renderer.
const { app, BrowserWindow, dialog, nativeTheme, shell } = require('electron')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const http = require('node:http')
const path = require('node:path')
const vm = require('node:vm')
const root = path.resolve(__dirname, '../..')
const source = fs.readFileSync(path.join(root, 'packaging/electron/main.js'), 'utf8')
const methods = ['createWindow', 'showStartup', 'loadApp'].map(name =>
  source.match(new RegExp(`^(?:async )?function ${name}\\([\\s\\S]*?^}`, 'm'))[0]).join('\n')
const progress = []
const cursors = []
let shown = false
let server
let win
const watchdog = setTimeout(() => { console.error('Startup smoke timed out'); app.exit(1) }, 20000)

app.whenReady().then(async () => {
  server = http.createServer((_request, response) => {
    response.setHeader('Content-Type', 'text/html; charset=utf-8')
    response.end('<!doctype html><title>SugarAgent</title><h1>Ready</h1>')
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const port = server.address().port
  const harness = vm.createContext({
    BrowserWindow: function (options) {
      win = new BrowserWindow({ ...options, webPreferences: { ...options.webPreferences, offscreen: true } })
      // Keep the smoke off the user's desktop while exercising the native renderer.
      win.show = () => { shown = true }
      const setProgressBar = win.setProgressBar.bind(win)
      win.setProgressBar = value => { progress.push(value); setProgressBar(value) }
      win.webContents.on('cursor-changed', (_event, cursor) => cursors.push(cursor))
      return win
    },
    mainWindow: null, quitting: false, nativeTheme, dialog, shell, path,
    require: name => require(path.resolve(root, 'packaging/electron', name)),
    TRAY_ICON: path.join(root, 'packaging/assets/tray.ico'),
    __dirname: path.join(root, 'packaging/electron'),
    baseUrl: () => `http://127.0.0.1:${port}`,
    browserGuests: require('../../packaging/electron/browser-guests').createBrowserGuests({ session: require('electron').session, hostUrl: () => `http://127.0.0.1:${port}` }),
    isConfigured: () => true, log() {}, writeStatus() {}, notifyStartupLauncher() {},
  })
  vm.runInContext(methods + '\nglobalThis.api = { showStartup, loadApp }', harness)
  await harness.api.showStartup()
  assert.equal(shown, true, 'startup becomes visible before the backend is available')
  assert.equal(win.webContents.getURL().startsWith('file:'), true)
  const status = await win.webContents.executeJavaScript(`({
    text: document.querySelector('[role="status"]').textContent,
    cursor: getComputedStyle(document.body).cursor,
    spinner: getComputedStyle(document.querySelector('.spinner')).animationName,
    reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
    logo: document.querySelector('.brand-logo').complete && document.querySelector('.brand-logo').naturalWidth,
  })`)
  assert.ok(status.text.includes('即将打开'))
  assert.equal(status.cursor, 'progress')
  assert.equal(status.logo, 256)
  assert.equal(status.spinner, status.reduced ? 'none' : 'spin')
  win.webContents.sendInputEvent({ type: 'mouseMove', x: 20, y: 20 })
  await new Promise(resolve => setTimeout(resolve, 150))
  assert.ok(cursors.includes('progress'), `native busy cursor expected, got ${cursors}`)
  const capture = process.argv.find(value => value.startsWith('--capture='))
  if (capture) fs.writeFileSync(capture.slice('--capture='.length), (await win.webContents.capturePage()).toPNG())
  await harness.api.loadApp('smoke-session')
  assert.equal(win.webContents.getURL(), `http://127.0.0.1:${port}/?session=smoke-session`)
  assert.equal(await win.webContents.executeJavaScript('getComputedStyle(document.body).cursor'), 'auto')
  assert.deepEqual(progress, [2, -1])
  win.destroy()
  server.close()
  clearTimeout(watchdog)
  console.log('Electron startup smoke: first paint, spinner, native busy cursor and UI transition passed')
  app.exit(0)
}).catch(error => {
  console.error(error.stack)
  if (win) win.destroy()
  if (server) server.close()
  app.exit(1)
})
