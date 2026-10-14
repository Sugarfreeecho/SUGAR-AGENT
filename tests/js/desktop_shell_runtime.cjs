'use strict'

const assert = require('node:assert/strict')
const { EventEmitter } = require('node:events')
const fs = require('node:fs')
const path = require('node:path')
const { test } = require('node:test')
const vm = require('node:vm')

const ROOT = path.resolve(__dirname, '../..')

function shellHarness({ argv = [], configured = true, reused = true, packaged = true, writable = true, paths = null, autoPaint = true, execPath = 'D:\\SugarAgent\\SugarAgent.exe', manualTimers = false, killResult = { status: 0 }, spawnError = null, deferHealth = false } = {}) {
  const calls = { loads: [], files: [], pipes: [], progress: [], launches: [], requests: [], protocols: [], writes: [], popups: [], children: [], logStreams: [], dialogs: [], errorBoxes: [], taskkills: [], ipc: new Map(), timers: new Map(), health: [] }
  let nextTimer = 1
  const app = Object.assign(new EventEmitter(), {
    isPackaged: packaged,
    getPath: name => `D:\\User's Data\\${name}`,
    getAppPath: () => 'D:\\Desktop Source',
    getVersion: () => 'test',
    requestSingleInstanceLock: () => true,
    whenReady: () => ({ then: callback => ({ catch: handler => {
      calls.boot = () => Promise.resolve().then(callback).catch(handler)
    } }) }),
    setAppUserModelId() {},
    setAsDefaultProtocolClient: (...args) => { calls.protocols.push(args); return true },
    quit: () => { calls.quit = true; app.emit('before-quit'); app.emit('will-quit') },
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
    hide() { calls.hidden = true; this.emit('hide') }
    isVisible() { return !!calls.shown && !calls.hidden }
    focus() { calls.focused = true }
    setBackgroundColor(color) { calls.background = color }
    setProgressBar(value) { calls.progress.push(value) }
    async loadURL(url) { calls.loads.push(url); this.webContents.mainFrame.url = url }
    async loadFile(file) {
      calls.files.push(file)
      this.webContents.mainFrame.url = 'file:///startup.html'
      if (autoPaint) queueMicrotask(() => this.emit('ready-to-show'))
    }
  }
  const ipcMain = Object.assign(new EventEmitter(), { handle: (name, callback) => calls.ipc.set(name, callback) })
  const electron = {
    app, BrowserWindow, ipcMain, nativeTheme,
    Menu: { setApplicationMenu() {}, buildFromTemplate: items => {
      Object.defineProperty(items, 'popup', { value: options => calls.popups.push({ items, options }) })
      return items
    } },
    clipboard: { writeText: text => { calls.clipboard = text } },
    Tray: class extends EventEmitter {
      setToolTip() {}
      setContextMenu(items) { calls.menu = items }
    },
    nativeImage: { createFromPath: () => ({ isEmpty: () => false }) },
    dialog: {
      showErrorBox: (...args) => { calls.error = args; calls.errorBoxes.push(args) },
      showMessageBox: options => {
        let resolve
        const promise = new Promise(done => { resolve = done })
        calls.dialogs.push({ options, resolve })
        return promise
      },
    },
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
    createWriteStream: file => {
      calls.logFile = file
      const stream = Object.assign(new EventEmitter(), {
        ended: false, chunks: [],
        write(chunk) { assert.equal(this.ended, false, 'output must not write to a closed log'); this.chunks.push(chunk) },
        end() { assert.equal(this.ended, false, 'close each log once'); this.ended = true },
      })
      calls.logStreams.push(stream)
      return stream
    },
  }
  const childProcess = {
    spawnSync: (exe, args, options) => {
      if (exe === 'taskkill') { calls.taskkills.push({ args, options }); return killResult }
      if (args[0].endsWith('workspace_paths.py') && paths) {
        calls.pathProbe = { exe, args, options }
        return { status: 0, stdout: JSON.stringify(paths) }
      }
      return { stdout: configured ? 'yes\n' : 'no\n' }
    },
    spawn: (...args) => {
      calls.launches.push(args)
      if (spawnError && args[0].endsWith('python.exe')) throw spawnError
      const child = new EventEmitter()
      child.unref = () => {}
      if (args[0].endsWith('python.exe')) {
        child.pid = 10000 + calls.children.length
        child.stdout = { pipe: stream => { child.outputLog = stream } }
        child.stderr = { pipe: stream => { child.errorLog = stream } }
        calls.children.push(child)
      }
      return child
    },
  }
  const http = {
    get: (options, callback) => {
      const request = Object.assign(new EventEmitter(), { destroy() {} })
      const respond = () => callback({ statusCode: 200, resume() {} })
      calls.health.push({ request, respond, options })
      if (!deferHealth) queueMicrotask(respond)
      return request
    },
    request: (options, callback) => {
      const request = new EventEmitter()
      request.end = body => {
        calls.requests.push({ options, body: JSON.parse(body) })
        const response = Object.assign(new EventEmitter(), { statusCode: 200, setEncoding() {}, resume() {} })
        callback(response)
        response.emit('data', JSON.stringify({ reused }))
        response.emit('end')
      }
      return request
    },
  }
  const context = vm.createContext({
    require: name => ({ electron, 'node:fs': fakeFs, 'node:path': path.win32,
      'node:child_process': childProcess, 'node:http': http, 'node:net': {
        createConnection: name => {
          const socket = Object.assign(new EventEmitter(), {
            end: message => { calls.pipeMessage = message }, setTimeout() {}, destroy() {},
          })
          calls.pipes.push(name)
          queueMicrotask(() => socket.emit('connect'))
          return socket
        },
      },
      './notifications': { createNotificationBridge: async () => ({ port: 12345, token: 'test', close() {} }) },
      './desktop-shortcuts': { removeLegacyElectronShortcuts() {} } })[name],
    process: { argv, env: {}, resourcesPath: 'D:\\SugarAgent Runtime', platform: 'win32', execPath },
    __dirname: path.join(ROOT, 'packaging/electron'), URL, Buffer,
    setTimeout: manualTimers ? (callback, delay) => {
      const id = nextTimer++
      calls.timers.set(id, { callback, delay })
      return id
    } : setTimeout,
    clearTimeout: manualTimers ? id => calls.timers.delete(id) : clearTimeout,
  })
  vm.runInContext(fs.readFileSync(path.join(ROOT, 'packaging/electron/main.js'), 'utf8') + `
    globalThis.api = { createWindow, createTray, loadApp, openBackendLog, openBackendLogs, startBackend, stopBackend, restartBackend, waitForBackend, registerIpc,
      parseDesktopActivation, registerDesktopProtocol, activateDesktop, applyNativeTheme, installNativeContextMenu, resolveLayout, backendEnv, notifyStartupLauncher,
      ready: () => { uiReady = true }, pending: () => pendingActivation,
      port: value => { activePort = value },
      backend: () => backend, logStream: () => backendLogStream,
      bootBackend: (start, wait) => { findFreePort = async () => BASE_PORT; startBackend = start; waitForBackend = wait },
      notifications: value => { notificationBridge = value } };
  `, context)
  return { api: context.api, app, calls, nativeTheme }
}

function runRestartTimer(calls) {
  const entry = [...calls.timers.entries()].find(([, timer]) => timer.delay === 800)
  assert.ok(entry, 'restart should schedule a single delayed start')
  const [id, timer] = entry
  calls.timers.delete(id)
  return timer.callback()
}

function lastStatus(calls) {
  const status = calls.writes.filter(([file]) => file.endsWith('desktop-status.json')).at(-1)
  return JSON.parse(status[1])
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

test('closing to tray reports hidden state to the owning backend without unloading the renderer', async () => {
  const { api, calls } = shellHarness()
  api.port(8195)
  api.notifications({ port: 12345, token: 'per-launch-secret' })
  api.createWindow()
  api.ready()
  let prevented = false
  calls.window.emit('close', { preventDefault() { prevented = true } })
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(prevented && calls.hidden, true)
  const report = calls.requests.find(row => row.options.path === '/api/ui-desktop-window')
  assert.ok(report, 'hide must reach the backend even though pagehide is never fired')
  assert.equal(report.options.port, 8195)
  assert.equal(report.options.headers.Authorization, 'Bearer per-launch-secret')
  assert.deepEqual(report.body, { visible: false })
  calls.window.emit('show')
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(calls.requests.at(-1).body, { visible: true })
})

test('cold start paints a busy window before backend work and keeps it until the app is loaded', async () => {
  const { api, calls } = shellHarness({ autoPaint: false })
  let finishBackend
  const ready = new Promise(resolve => { finishBackend = resolve })
  let starts = 0
  api.bootBackend(() => {
    starts += 1
    assert.equal(calls.shown, true, 'startup page must be painted before backend preparation')
    assert.ok(calls.menu, 'startup window can be reopened from the tray')
    assert.equal(calls.menu.find(item => item.label === '重启内置服务').enabled, false)
  }, () => ready)
  const boot = calls.boot()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(starts, 0, 'backend preparation must wait for the first paint')
  assert.equal(calls.files.length, 1)
  assert.ok(calls.files[0].endsWith('startup.html'))
  assert.deepEqual(calls.progress, [2])
  assert.equal(calls.loads.length, 0)
  const window = calls.window
  window.emit('ready-to-show')
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(starts, 1)
  assert.equal(calls.loads.length, 0, 'startup page remains visible while backend is not ready')
  finishBackend(true)
  await boot
  assert.equal(calls.window, window, 'main UI must reuse the startup window')
  assert.deepEqual(calls.loads, ['http://127.0.0.1:8192/'])
  assert.deepEqual(calls.progress, [2, -1])
  assert.equal(calls.menu.find(item => item.label === '重启内置服务').enabled, true)
})

test('repeated shortcut launches restore the startup window and retain notification navigation', async () => {
  const { api, app, calls } = shellHarness()
  let finishBackend
  const ready = new Promise(resolve => { finishBackend = resolve })
  let starts = 0
  api.bootBackend(() => { starts += 1 }, () => ready)
  const boot = calls.boot()
  await new Promise(resolve => setImmediate(resolve))
  const window = calls.window
  app.emit('second-instance', {}, [])
  assert.equal(calls.restored && calls.shown && calls.focused, true)
  assert.equal(calls.window, window)
  app.emit('second-instance', {}, ['sugaragent-desktop://open-ui?session=during-start'])
  finishBackend(true)
  await boot
  assert.equal(starts, 1)
  assert.deepEqual(calls.loads, ['http://127.0.0.1:8192/?session=during-start'])
})

test('startup timeout or backend exception clears busy progress and reports the failure', async () => {
  for (const fail of [() => false, () => { throw new Error('backend failed') }]) {
    const { api, calls } = shellHarness()
    api.bootBackend(() => {}, fail)
    await calls.boot()
    assert.deepEqual(calls.progress, [2, -1])
    assert.equal(calls.loads.length, 0)
    assert.equal(calls.error[0], 'SugarAgent 无法启动')
    assert.equal(calls.quit, true)
  }
})

test('quitting during startup does not start the backend after the first paint', async () => {
  const { api, app, calls } = shellHarness({ autoPaint: false })
  let started = false
  api.bootBackend(() => { started = true }, () => true)
  const boot = calls.boot()
  await new Promise(resolve => setImmediate(resolve))
  app.emit('before-quit')
  calls.window.emit('ready-to-show')
  await boot
  assert.equal(started, false)
  assert.equal(calls.menu, undefined)
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

test('tray restart treats the old exit as expected and reloads after the replacement is ready', async () => {
  const paths = { work_dir: 'E:\\Projects', skills_dir: 'E:\\Library\\skills', log_dir: 'E:\\Logs' }
  const { api, calls } = shellHarness({ manualTimers: true, paths })
  api.createWindow()
  api.ready()
  api.createTray()
  api.startBackend()
  const old = calls.children[0]
  const oldLog = calls.logStreams[0]
  paths.work_dir = 'F:\\New Projects'
  assert.equal(calls.menu.find(item => item.label === '重启内置服务').click(), true)
  assert.equal(calls.menu.find(item => item.label === '重启内置服务').enabled, false)
  assert.equal(calls.taskkills[0].args.join(' '), '/PID 10000 /T /F')
  assert.equal(calls.taskkills[0].options.windowsHide, true)
  assert.equal(lastStatus(calls).backendState, 'restarting')
  old.emit('exit', 1, null)
  assert.equal(calls.dialogs.length, 0)
  assert.equal(lastStatus(calls).backendState, 'restarting')
  assert.equal(oldLog.ended, false, 'drain stdout/stderr before closing the log')
  old.outputLog.write('last buffered output\n')
  old.emit('close', 1, null)
  assert.equal(oldLog.ended, true)
  await runRestartTimer(calls)
  assert.equal(calls.children.length, 2)
  assert.equal(calls.launches[1][2].env.WORK_DIR, paths.work_dir)
  assert.equal(calls.launches[1][2].env.MYAGENT_SERVER_PORT, '8192')
  assert.deepEqual(calls.loads, ['http://127.0.0.1:8192/'])
  assert.equal(lastStatus(calls).backendState, 'ready')
  assert.equal(lastStatus(calls).backendPid, calls.children[1].pid)
  assert.equal(calls.menu.find(item => item.label === '重启内置服务').enabled, true)
  assert.equal(calls.errorBoxes.length, 0)
})

test('late exit and close from the old child preserve the new child, status, and log', async () => {
  const { api, app, calls } = shellHarness({ manualTimers: true })
  api.createWindow()
  api.ready()
  api.startBackend()
  const old = calls.children[0]
  api.restartBackend()
  await runRestartTimer(calls)
  const fresh = calls.children[1]
  const currentStatus = lastStatus(calls)
  const freshLog = calls.logStreams[1]
  const freshChunks = freshLog.chunks.length
  old.emit('exit', 1, null)
  old.emit('close', 1, null)
  assert.equal(api.backend(), fresh)
  assert.equal(api.logStream(), freshLog)
  assert.equal(freshLog.ended, false)
  assert.equal(freshLog.chunks.length, freshChunks, 'old exit must write only to its own log')
  assert.deepEqual(lastStatus(calls), currentStatus)
  assert.equal(await api.waitForBackend(1000), true)
  assert.equal(calls.dialogs.length, 0)
  app.quit()
  assert.equal(calls.taskkills.at(-1).args[1], String(fresh.pid), 'quit must still track and stop the replacement')
  fresh.emit('exit', 1, null)
  fresh.emit('close', 1, null)
  assert.equal(freshLog.ended, true)
  assert.equal(calls.dialogs.length, 0)
})

test('tray, IPC, and recovery restarts share one operation while waiting for readiness', async () => {
  const { api, calls } = shellHarness({ manualTimers: true, deferHealth: true })
  api.createWindow()
  api.registerIpc()
  const restart = calls.ipc.get('sugaragent:restart-backend')
  assert.equal(restart(), false, 'startup cannot be interrupted by a restart')
  api.ready()
  api.startBackend()
  assert.equal(restart(), true)
  assert.equal(restart(), false)
  assert.equal(calls.menu.find(item => item.label === '重启内置服务').click(), false)
  assert.equal(calls.timers.size, 1)
  const operation = runRestartTimer(calls)
  assert.equal(calls.children.length, 2)
  assert.equal(restart(), false, 'keep the guard after the timer fires')
  assert.equal(calls.menu.find(item => item.label === '重启内置服务').enabled, false)
  assert.equal(calls.taskkills.length, 1)
  calls.health[0].respond()
  await operation
  assert.equal(calls.errorBoxes.length, 0)
  assert.equal(calls.loads.length, 1)
  assert.equal(calls.menu.find(item => item.label === '重启内置服务').enabled, true)
})

test('quit cancels the pending restart and guards a callback already queued for dispatch', async () => {
  const { api, app, calls } = shellHarness({ manualTimers: true })
  api.ready()
  api.startBackend()
  api.restartBackend()
  const callback = [...calls.timers.values()][0].callback
  app.quit()
  assert.equal(calls.timers.size, 0)
  await callback()
  assert.equal(api.startBackend(), null)
  assert.equal(api.restartBackend(), false)
  assert.equal(calls.children.length, 1)
  assert.equal(calls.errorBoxes.length, 0)
})

test('quit during a pending health probe neither reloads nor reports startup failure', async () => {
  const { api, app, calls } = shellHarness({ manualTimers: true, deferHealth: true })
  api.createWindow()
  api.ready()
  api.startBackend()
  api.restartBackend()
  const operation = runRestartTimer(calls)
  app.quit()
  calls.health[0].respond()
  await operation
  assert.equal(calls.children.length, 2)
  assert.equal(calls.taskkills.length, 2)
  assert.equal(calls.loads.length, 0)
  assert.equal(calls.errorBoxes.length, 0)
})

test('a genuine running-service crash shows recovery once and can restart', async () => {
  const { api, calls } = shellHarness({ manualTimers: true })
  api.createWindow()
  api.ready()
  api.port(8196)
  api.startBackend()
  const child = calls.children[0]
  child.emit('exit', 7, null)
  child.emit('close', 7, null)
  assert.equal(calls.dialogs.length, 1)
  assert.match(calls.dialogs[0].options.message, /code=7/)
  assert.ok(calls.dialogs[0].options.detail.includes('8196'))
  assert.equal(lastStatus(calls).backendState, 'exited')
  assert.equal(lastStatus(calls).backendPid, null)
  assert.equal(calls.logStreams[0].ended, true)
  calls.dialogs[0].resolve({ response: 0 })
  await new Promise(resolve => setImmediate(resolve))
  await runRestartTimer(calls)
  assert.equal(calls.taskkills.length, 0, 'the crashed child is already stopped')
  assert.equal(calls.dialogs.length, 1)
  assert.equal(lastStatus(calls).backendState, 'ready')
  assert.deepEqual(calls.loads, ['http://127.0.0.1:8196/'])
})

test('stale recovery dialogs cannot interrupt a service that has since restarted', async () => {
  for (const response of [0, 2]) {
    const { api, calls } = shellHarness({ manualTimers: true })
    api.createWindow()
    api.ready()
    api.startBackend()
    calls.children[0].emit('exit', 1, null)
    api.restartBackend()
    await runRestartTimer(calls)
    const fresh = calls.children[1]
    calls.dialogs[0].resolve({ response })
    await new Promise(resolve => setImmediate(resolve))
    assert.equal(api.backend(), fresh)
    assert.equal(calls.timers.size, 0)
    assert.equal(calls.taskkills.length, 0)
    assert.equal(calls.quit, undefined)
  }
})

test('restart child exit or spawn error produces one real failure instead of a false timeout', async () => {
  for (const fail of [child => child.emit('exit', 1, null), child => child.emit('error', new Error('spawn EACCES'))]) {
    const { api, calls } = shellHarness({ manualTimers: true, deferHealth: true })
    api.createWindow()
    api.ready()
    api.startBackend()
    api.restartBackend()
    const operation = runRestartTimer(calls)
    const child = calls.children[1]
    fail(child)
    child.emit('close', 1, null)
    calls.health[0].respond()
    await operation
    assert.equal(api.backend(), null)
    assert.equal(calls.dialogs.length, 0)
    assert.equal(calls.errorBoxes.length, 1)
    assert.equal(calls.errorBoxes[0][0], '重启内置服务失败')
    assert.match(calls.errorBoxes[0][1], /启动失败或已退出/)
    assert.ok(!calls.errorBoxes[0][1].includes('180 秒'))
    assert.equal(calls.loads.length, 0, 'a health response cannot revive an exited child')
    assert.equal(calls.logStreams[1].ended, true)
    assert.equal(calls.menu.find(item => item.label === '重启内置服务').enabled, true)
    assert.equal(lastStatus(calls).backendState, 'exited')
  }
})

test('a synchronous spawn exception closes the log and releases the restart guard', async () => {
  const { api, calls } = shellHarness({ manualTimers: true, spawnError: new Error('spawn failed') })
  api.createWindow()
  api.ready()
  assert.equal(api.restartBackend(), true)
  await runRestartTimer(calls)
  assert.equal(calls.logStreams[0].ended, true)
  assert.equal(api.logStream(), null)
  assert.equal(calls.errorBoxes.length, 1)
  assert.match(calls.errorBoxes[0][1], /spawn failed/)
  assert.equal(lastStatus(calls).backendState, 'exited')
  assert.equal(calls.menu.find(item => item.label === '重启内置服务').enabled, true)
})

test('a true readiness timeout is reported while retaining the live child for cleanup', async () => {
  const { api, app, calls } = shellHarness({ manualTimers: true })
  api.createWindow()
  api.ready()
  api.bootBackend(api.startBackend, () => false)
  api.restartBackend()
  await runRestartTimer(calls)
  assert.equal(calls.errorBoxes.length, 1)
  assert.match(calls.errorBoxes[0][1], /180 秒/)
  assert.equal(calls.loads.length, 0)
  assert.equal(api.backend(), calls.children[0])
  app.quit()
  assert.equal(calls.taskkills.length, 1)
})

test('a failed taskkill preserves the running child and its later crash is still reported', () => {
  for (const killResult of [{ status: 1 }, { error: new Error('taskkill not found'), status: null }]) {
    const { api, calls } = shellHarness({ manualTimers: true, killResult })
    api.createWindow()
    api.ready()
    api.startBackend()
    const child = calls.children[0]
    assert.equal(api.restartBackend(), false)
    assert.equal(api.backend(), child)
    assert.equal(calls.timers.size, 0)
    assert.equal(calls.logStreams[0].ended, false)
    assert.equal(calls.errorBoxes.length, 1)
    assert.equal(calls.menu.find(item => item.label === '重启内置服务').enabled, true)
    child.emit('exit', 2, null)
    assert.equal(calls.dialogs.length, 1, 'a rejected stop must not mark future exits as expected')
  }
})

test('notification navigation is queued while restarting and loaded on the new service', async () => {
  const { api, calls } = shellHarness({ manualTimers: true })
  api.createWindow()
  api.ready()
  api.startBackend()
  api.restartBackend()
  await api.activateDesktop({ session: 'during-restart' })
  assert.equal(calls.requests.length, 0)
  assert.equal(calls.loads.length, 0)
  await runRestartTimer(calls)
  assert.deepEqual(calls.loads, ['http://127.0.0.1:8192/?session=during-restart'])
  assert.equal(api.pending(), null)
})

test('a child exiting during page load is reported and pending notification navigation survives failure', async () => {
  const { api, calls } = shellHarness({ manualTimers: true })
  api.createWindow()
  api.ready()
  api.startBackend()
  let finishLoad
  calls.window.loadURL = () => new Promise(resolve => { finishLoad = resolve })
  api.restartBackend()
  const operation = runRestartTimer(calls)
  await new Promise(resolve => setImmediate(resolve))
  await api.activateDesktop({ session: 'retry-after-failure' })
  calls.children[1].emit('exit', 3, null)
  finishLoad()
  await operation
  assert.equal(calls.errorBoxes.length, 1)
  assert.match(calls.errorBoxes[0][1], /加载界面时退出/)
  assert.equal(calls.dialogs.length, 0)
  assert.equal(lastStatus(calls).backendState, 'exited')
  assert.equal(api.pending().session, 'retry-after-failure')
  assert.equal(calls.requests.length, 0)
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

test('installed runtime registers protocol activations through the native launcher', () => {
  const { api, calls } = shellHarness({ execPath: 'D:\\SugarAgent\\SugarAgentRuntime.exe' })
  api.registerDesktopProtocol()
  assert.equal(calls.protocols[0][1], 'D:\\SugarAgent\\SugarAgent.exe')
})

test('native splash handoff only occurs after first paint and accepts generated pipe names', async () => {
  const name = 'SugarAgent-startup-' + 'a'.repeat(32)
  const { api, calls } = shellHarness({ argv: ['--sugaragent-startup-pipe=' + name] })
  api.createWindow()
  assert.equal(calls.pipes.length, 0)
  calls.window.emit('ready-to-show')
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(calls.pipes[0], '\\\\.\\pipe\\' + name)
  assert.equal(calls.pipeMessage, 'ready')
  const invalid = shellHarness({ argv: ['--sugaragent-startup-pipe=other-pipe'] })
  invalid.api.notifyStartupLauncher()
  assert.equal(invalid.calls.pipes.length, 0)
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
