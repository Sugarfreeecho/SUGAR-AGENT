'use strict'

const assert = require('node:assert/strict')
const { EventEmitter } = require('node:events')
const fs = require('node:fs')
const path = require('node:path')
const { test } = require('node:test')
const vm = require('node:vm')

const ROOT = path.resolve(__dirname, '../..')

function shellHarness({ argv = [], configured = true, reused = true, packaged = true, writable = true, paths = null } = {}) {
  const calls = { loads: [], launches: [], requests: [], protocols: [], writes: [], popups: [] }
  const app = Object.assign(new EventEmitter(), {
    isPackaged: packaged,
    getPath: name => `D:\\User's Data\\${name}`,
    getAppPath: () => 'D:\\Desktop Source',
    getVersion: () => 'test',
    requestSingleInstanceLock: () => true,
    whenReady: () => ({ then: callback => { calls.boot = callback } }),
    setAsDefaultProtocolClient: (...args) => { calls.protocols.push(args); return true },
    quit: () => {},
  })
  const nativeTheme = { shouldUseDarkColors: false, themeSource: 'system' }
  class BrowserWindow extends EventEmitter {
    constructor(options) {
      super()
      this.options = options
      this.webContents = Object.assign(new EventEmitter(), {
        mainFrame: { url: 'http://127.0.0.1:8192/' },
        setWindowOpenHandler: () => {},
        getURL: () => this.webContents.mainFrame.url,
      })
      calls.window = this
      this.minimized = true
    }
    isMinimized() { return this.minimized }
    restore() { calls.restored = true; this.minimized = false }
    show() { calls.shown = true }
    focus() { calls.focused = true }
    setBackgroundColor(color) { calls.background = color }
    async loadURL(url) { calls.loads.push(url); this.webContents.mainFrame.url = url }
  }
  const ipcMain = Object.assign(new EventEmitter(), { handle: () => {} })
  const electron = {
    app, BrowserWindow, ipcMain, nativeTheme,
    Menu: { buildFromTemplate: items => {
      Object.defineProperty(items, 'popup', { value: options => calls.popups.push({ items, options }) })
      return items
    } },
    clipboard: { writeText: text => { calls.clipboard = text } },
    Tray: class extends EventEmitter {
      setToolTip() {}
      setContextMenu(items) { calls.menu = items }
    },
    nativeImage: { createFromPath: () => ({ isEmpty: () => false }) },
    dialog: { showErrorBox: (...args) => { calls.error = args } },
    shell: { openExternal: url => { calls.external = url }, openPath: () => {} },
  }
  BrowserWindow.fromWebContents = () => calls.window
  const fakeFs = {
    mkdirSync() {}, unlinkSync() {}, existsSync: () => true,
    writeFileSync: (...args) => {
      if (!writable && args[0].includes('.write-probe-')) throw new Error('Read-only runtime')
      calls.writes.push(args)
    },
    appendFileSync: (...args) => calls.writes.push(args),
    createWriteStream: file => { calls.logFile = file; return {} },
  }
  const childProcess = {
    spawnSync: (exe, args, options) => {
      if (args[0].endsWith('workspace_paths.py') && paths) {
        calls.pathProbe = { exe, args, options }
        return { status: 0, stdout: JSON.stringify(paths) }
      }
      return { stdout: configured ? 'yes\n' : 'no\n' }
    },
    spawn: (...args) => {
      calls.launches.push(args)
      const child = new EventEmitter()
      child.unref = () => {}
      return child
    },
  }
  const http = {
    request: (options, callback) => {
      const request = new EventEmitter()
      request.end = body => {
        calls.requests.push({ options, body: JSON.parse(body) })
        const response = Object.assign(new EventEmitter(), { statusCode: 200, setEncoding() {} })
        callback(response)
        response.emit('data', JSON.stringify({ reused }))
        response.emit('end')
      }
      return request
    },
  }
  const context = vm.createContext({
    require: name => ({ electron, 'node:fs': fakeFs, 'node:path': path.win32,
      'node:child_process': childProcess, 'node:http': http, 'node:net': {},
      './notifications': require('../../packaging/electron/notifications') })[name],
    process: { argv, env: {}, resourcesPath: 'D:\\SugarAgent Runtime', platform: 'win32', execPath: 'D:\\SugarAgent\\SugarAgent.exe' },
    __dirname: path.join(ROOT, 'packaging/electron'), URL, Buffer, setTimeout, clearTimeout,
  })
  vm.runInContext(fs.readFileSync(path.join(ROOT, 'packaging/electron/main.js'), 'utf8') + `
    globalThis.api = { createWindow, createTray, loadApp, openBackendLog, openBackendLogs,
      parseDesktopActivation, registerDesktopProtocol, activateDesktop, applyNativeTheme, installNativeContextMenu, resolveLayout, backendEnv,
      ready: () => { uiReady = true }, pending: () => pendingActivation,
      port: value => { activePort = value },
      notifications: value => { notificationBridge = value } };
  `, context)
  return { api: context.api, app, calls, nativeTheme }
}

test('default workspace keeps the source layout and follows the read-only fallback', () => {
  for (const writable of [true, false]) {
    const { api } = shellHarness({ writable })
    const layout = api.resolveLayout()
    const root = writable ? 'D:\\SugarAgent Runtime\\runtime' : "D:\\User's Data\\userData"
    assert.equal(layout.cwd, root)
    assert.equal(layout.workDir, path.win32.join(root, 'workspace'))
    assert.equal(api.backendEnv().WORK_DIR, layout.workDir)
  }
})

test('desktop actions and backend environment share configured paths and refresh after restart', () => {
  const paths = { work_dir: 'E:\\Projects', skills_dir: 'E:\\Library\\skills', log_dir: 'E:\\Logs' }
  const { api, calls } = shellHarness({ paths })
  assert.equal(api.resolveLayout().workDir, paths.work_dir)
  assert.equal(api.backendEnv().WORK_DIR, paths.work_dir)
  assert.equal(api.backendEnv().SKILLS_DIR, paths.skills_dir)
  assert.equal(api.backendEnv().LOG_DIR, paths.log_dir)
  assert.equal(calls.pathProbe.options.windowsHide, true)
  paths.work_dir = 'F:\\New Projects'
  assert.equal(api.resolveLayout(true).workDir, paths.work_dir)
})

test('tray omits setup and opens a live colored log viewer for the active file', () => {
  const { api, calls } = shellHarness()
  api.createTray()
  assert.equal(calls.menu.some(item => /配置向导/.test(item.label || '')), false)
  api.openBackendLog()
  calls.menu.find(item => item.label === '打开后台日志').click()
  const [exe, args, options] = calls.launches[0]
  assert.equal(exe, 'powershell.exe')
  assert.equal(options.windowsHide, true)
  assert.match(args.at(-1), /Start-Process.*-WindowStyle Normal/)
  assert.ok(args.at(-1).includes('"D:\\SugarAgent Runtime\\runtime\\app\\colored_log_viewer.ps1"'))
  assert.ok(args.at(-1).includes(`"${calls.logFile.replace(/'/g, "''")}"`))
})

test('desktop protocol registration covers installed and source Electron launches', () => {
  for (const packaged of [true, false]) {
    const { api, calls } = shellHarness({ packaged })
    api.registerDesktopProtocol()
    const registration = calls.protocols[0]
    assert.equal(registration[0], 'sugaragent-desktop')
    assert.equal(registration.length, packaged ? 1 : 3)
    if (!packaged) assert.equal(registration[2][0], 'D:\\Desktop Source')
  }
})

test('native notification bridge reaches the backend across restarts and closes on quit', () => {
  const { api, app } = shellHarness()
  let closed = false
  api.notifications({ port: 12345, token: 'per-launch-secret', close: () => { closed = true } })
  for (const refresh of [false, true]) {
    api.resolveLayout(refresh)
    assert.equal(api.backendEnv().SUGARAGENT_NOTIFY_PORT, '12345')
    assert.equal(api.backendEnv().SUGARAGENT_NOTIFY_TOKEN, 'per-launch-secret')
  }
  app.emit('will-quit')
  assert.equal(closed, true)
})

test('protocol accepts only desktop UI links and validates session ids', () => {
  const { api } = shellHarness()
  assert.equal(api.parseDesktopActivation(['sugaragent://open-ui?session=abc']), null)
  assert.equal(api.parseDesktopActivation(['sugaragent-desktop://other']), null)
  assert.equal(api.parseDesktopActivation(['sugaragent-desktop://open-ui/settings']), null)
  assert.equal(api.parseDesktopActivation(['sugaragent-desktop://open-ui?session=%22bad']).session, '')
  assert.equal(api.parseDesktopActivation(['--flag', 'sugaragent-desktop://open-ui?session=abc-123']).session, 'abc-123')
})

test('notification restores desktop window and uses its active backend port without reloading', async () => {
  const { api, app, calls } = shellHarness()
  api.port(8195)
  api.createWindow()
  api.ready()
  app.emit('second-instance', {}, ['sugaragent-desktop://open-ui?session=abc-123'])
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(calls.restored && calls.shown && calls.focused, true)
  assert.equal(calls.requests[0].options.port, 8195)
  assert.equal(calls.requests[0].body.session, 'abc-123')
  assert.equal(calls.loads.length, 0)
  assert.equal(calls.external, undefined)
})

test('missing page heartbeat falls back to a session URL inside the desktop window', async () => {
  const { api, calls } = shellHarness({ reused: false })
  api.port(8196)
  api.createWindow()
  api.ready()
  await api.activateDesktop({ session: 'abc' })
  assert.equal(calls.loads[0], 'http://127.0.0.1:8196/?session=abc')
  assert.equal(calls.external, undefined)
})

test('startup activation queues the session until the window can be loaded', async () => {
  const { api, calls } = shellHarness({ argv: ['sugaragent-desktop://open-ui?session=cold-start'] })
  assert.equal(api.pending().session, 'cold-start')
  await api.activateDesktop({ session: 'during-start' })
  assert.equal(calls.window, undefined)
  api.createWindow()
  await api.loadApp(api.pending().session)
  assert.equal(calls.loads[0], 'http://127.0.0.1:8192/?session=during-start')
})

test('notification preserves first-run setup when a model is not configured', async () => {
  const { api, calls } = shellHarness({ configured: false })
  api.createWindow()
  await api.loadApp('abc')
  api.ready()
  await api.activateDesktop({ session: 'abc' })
  assert.deepEqual(calls.loads, ['http://127.0.0.1:8192/setup'])
})

test('trusted page theme updates native appearance; embedded or external pages cannot', () => {
  const { api, calls, nativeTheme } = shellHarness()
  api.createWindow()
  const event = { sender: calls.window.webContents, senderFrame: calls.window.webContents.mainFrame }
  for (const [theme, source, color] of [['dark', 'dark', '#151517'], ['light', 'light', '#ffffff'], ['purple', 'dark', '#1e1e2e']]) {
    assert.equal(api.applyNativeTheme(event, theme), true)
    assert.equal(nativeTheme.themeSource, source)
    assert.equal(calls.background, color)
  }
  assert.equal(api.applyNativeTheme({ ...event, senderFrame: { url: event.senderFrame.url } }, 'light'), false)
  event.senderFrame.url = 'https://example.com/'
  assert.equal(api.applyNativeTheme(event, 'light'), false)
  assert.equal(nativeTheme.themeSource, 'dark')
})

test('preload syncs initial theme and subsequent root changes, including legacy themes', () => {
  let loaded, changed
  const sent = []
  const classes = new Set(['theme-light'])
  const root = { classList: { contains: value => classes.has(value) }, dataset: {} }
  let stored = ''
  vm.runInNewContext(fs.readFileSync(path.join(ROOT, 'packaging/electron/preload.js'), 'utf8'), {
    require: () => ({ contextBridge: { exposeInMainWorld() {} }, ipcRenderer: { send: (...args) => sent.push(args) } }),
    process: { isMainFrame: true },
    document: { documentElement: root },
    localStorage: { getItem: () => stored },
    window: { addEventListener: (_name, callback) => { loaded = callback } },
    MutationObserver: class {
      constructor(callback) { changed = callback }
      observe(target, options) { assert.equal(target, root); assert.equal(options.attributes, true) }
    },
  })
  loaded()
  classes.clear(); classes.add('theme-dark'); changed(); changed()
  classes.clear(); classes.add('theme-purple'); changed()
  classes.clear(); stored = 'deep-dark'; changed()
  stored = 'dark'; changed()
  assert.deepEqual(sent.filter(row => row[0] === 'sugaragent:theme').map(row => row[1]), ['light', 'dark', 'purple', 'dark', 'purple'])
  assert.deepEqual(sent.filter(row => row[0] === 'sugaragent:language').map(row => row[1]), ['zh-CN'])
})

test('native context menu targets the clicked settings frame and respects edit flags', () => {
  const { api, calls } = shellHarness()
  api.createWindow()
  const contents = calls.window.webContents
  api.installNativeContextMenu(contents)
  const frame = { url: 'http://127.0.0.1:8192/settings' }
  contents.emit('context-menu', { preventDefault() {} }, {
    frame, isEditable: true, editFlags: { canUndo: true, canRedo: false, canCopy: true, canCut: false, canPaste: true, canSelectAll: true },
  })
  const popup = calls.popups[0]
  assert.equal(popup.options.frame, frame)
  assert.equal(popup.options.window, calls.window)
  assert.equal(popup.items.find(item => item.role === 'paste').enabled, true)
  assert.equal(popup.items.find(item => item.role === 'cut').enabled, false)
  assert.equal(popup.items.find(item => item.role === 'redo').enabled, false)
})

test('native fallback copies images and safe link addresses without opening unsafe protocols', () => {
  const { api, calls } = shellHarness()
  api.createWindow()
  const contents = calls.window.webContents
  contents.copyImageAt = (x, y) => { calls.image = [x, y] }
  api.installNativeContextMenu(contents)
  contents.emit('context-menu', { preventDefault() {} }, {
    frame: contents.mainFrame, linkURL: 'javascript:alert(1)', mediaType: 'none',
  })
  assert.equal(calls.popups.length, 0)
  contents.emit('context-menu', { preventDefault() {} }, {
    frame: contents.mainFrame, linkURL: 'https://example.com/', mediaType: 'image', hasImageContents: true, x: 12, y: 34,
  })
  calls.popups[0].items.find(item => item.label === '复制链接地址').click()
  assert.equal(calls.clipboard, 'https://example.com/')
  calls.popups[0].items.find(item => item.label === '复制图片').click()
  assert.deepEqual(calls.image, [12, 34])
})
