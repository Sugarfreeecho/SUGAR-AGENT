'use strict'

/**
 * SugarAgent 桌面版主进程。
 *
 * 职责：
 *  1. 托管内置 Python 后端（app/main.py，监听 127.0.0.1:8192），把 stdout/stderr 落盘；
 *  2. 首次启动时把打包的技能模板铺到工作目录，未完成配置时直接打开应用自带的 /setup 欢迎页；
 *  3. 原生窗口 + 托盘常驻，关闭窗口即最小化到托盘，退出时按进程树清理后端；
 *  4. 后端异常退出时给出可操作的恢复对话框。
 */

const { app, BrowserWindow, Menu, Notification, Tray, clipboard, dialog, ipcMain, nativeImage, nativeTheme, session, shell } = require('electron')
const { spawn, spawnSync } = require('node:child_process')
const fs = require('node:fs')
const http = require('node:http')
const net = require('node:net')
const path = require('node:path')
const { createNotificationBridge } = require('./notifications')
const { removeLegacyElectronShortcuts } = require('./desktop-shortcuts')
const { openWorkspacePath } = require('./local-paths')
const { createLifecycleBridge } = require('./lifecycle-bridge')

const HOST = '127.0.0.1'
const BASE_PORT = Number(process.env.SUGARAGENT_PORT || 8192)
const PORT_SPAN = 8
let activePort = BASE_PORT
const baseUrl = () => `http://${HOST}:${activePort}`
function isApplicationUrl(value) {
  try { return new URL(value).origin === baseUrl() } catch { return false }
}
const browserGuests = require('./browser-guests').createBrowserGuests({ session, hostUrl: baseUrl })

const RUNTIME_DIR = path.join(process.resourcesPath, 'runtime')
const PYTHON_EXE = path.join(RUNTIME_DIR, 'python', process.platform === 'win32' ? 'python.exe' : 'python3')
const APP_ENTRY = path.join(RUNTIME_DIR, 'app', 'main.py')
const SKILL_TEMPLATE = path.join(RUNTIME_DIR, 'workspace-template', 'skills')
const TRAY_ICON = path.join(process.resourcesPath, 'tray.ico')
const USER_DIR = app.getPath('userData')
const LOG_DIR = path.join(USER_DIR, 'logs')
const OPEN_UI_PROTOCOL = 'sugaragent-desktop'

const IS_WINDOWS = process.platform === 'win32'
const IS_DEV = process.env.SUGARAGENT_DEV === '1'

let mainWindow = null
let tray = null
let backend = null
let backendLogStream = null
let backendLogFile = null
let quitting = false
let restartTimer = null
let backendRestarting = false
let backendPreparing = false
let lifecycleBridge = null
const expectedBackendExits = new WeakSet()
let uiReady = false
let pendingActivation = parseDesktopActivation(process.argv)
let notificationBridge = null
let desktopWindowReport = Promise.resolve()

// ---------------------------------------------------------------- logging ---

function ensureLogDir() {
  fs.mkdirSync(LOG_DIR, { recursive: true })
  return LOG_DIR
}

function log(line) {
  const stamp = new Date().toISOString()
  const text = `[${stamp}] ${line}\n`
  try {
    ensureLogDir()
    fs.appendFileSync(path.join(LOG_DIR, 'desktop.log'), text, 'utf8')
  } catch {
    /* 日志写失败不能影响主流程 */
  }
  if (IS_DEV) process.stdout.write(text)
}

/** 写出机器可读状态，便于自检脚本与故障排查（不含任何密钥）。 */
function writeStatus(extra = {}) {
  try {
    fs.mkdirSync(USER_DIR, { recursive: true })
    fs.writeFileSync(path.join(USER_DIR, 'desktop-status.json'), `${JSON.stringify({
      version: app.getVersion(),
      port: activePort,
      baseUrl: baseUrl(),
      backendPid: backend ? backend.pid : null,
      runtimeDir: RUNTIME_DIR,
      workDir: resolveLayout().workDir,
      logsDir: LOG_DIR,
      updatedAt: new Date().toISOString(),
      ...extra,
    }, null, 2)}\n`, 'utf8')
  } catch {
    /* 状态文件写失败不影响主流程 */
  }
}

// ------------------------------------------------------------ runtime env ---

/** 安装目录是否可写；不可写时把用户数据挪到 %APPDATA%。 */
function runtimeIsWritable() {
  const probe = path.join(RUNTIME_DIR, `.write-probe-${process.pid}`)
  try {
    fs.writeFileSync(probe, 'ok')
    fs.unlinkSync(probe)
    return true
  } catch {
    return false
  }
}

let layout = null

function resolveLayout(refresh = false) {
  if (refresh) layout = null
  if (layout) return layout
  const writable = runtimeIsWritable()
  // 保持源码目录关系：workspace/ 与 app/、python/ 同级。
  // 只读安装目录沿用用户目录兜底，不依赖启动快捷方式的工作目录。
  const cwd = writable ? RUNTIME_DIR : USER_DIR
  layout = {
    writable,
    workDir: path.join(cwd, 'workspace'),
    logDir: path.join(USER_DIR, 'app-logs'),
    cwd,
  }
  // Use the backend's path resolver before seeding or exposing native actions.
  const probe = spawnSync(PYTHON_EXE, [path.join(RUNTIME_DIR, 'app', 'workspace_paths.py'),
    '--project-root', RUNTIME_DIR, '--work-dir', layout.workDir, '--log-dir', layout.logDir], {
    cwd,
    env: { ...process.env, WORK_DIR: process.env.WORK_DIR || layout.workDir, LOG_DIR: process.env.LOG_DIR || layout.logDir, MYAGENT_DOTENV_OVERRIDE: '1', PYTHONUTF8: '1' },
    encoding: 'utf8', windowsHide: true, timeout: 10000,
  })
  try {
    if (probe.status !== 0) throw new Error('path probe failed')
    const paths = JSON.parse(probe.stdout)
    if (!path.isAbsolute(paths.work_dir) || !path.isAbsolute(paths.skills_dir) || !path.isAbsolute(paths.log_dir)) throw new Error('invalid configured paths')
    Object.assign(layout, { workDir: paths.work_dir, skillsDir: paths.skills_dir, logDir: paths.log_dir })
  } catch (error) {
    log(`工作目录配置读取失败，使用默认路径：${error.message}`)
  }
  if (!writable) log('安装目录不可写：后端将使用用户目录作为工作根')
  return layout
}

function backendEnv() {
  const current = resolveLayout()
  // 只继承系统级变量：任何模型/搜索/云厂商密钥都不透传给子进程，
  // 否则打包机上的环境变量会把新装用户的“未配置”状态覆盖成已配置。
  const SENSITIVE = /^(OPENAI_|ANTHROPIC_|DEEPSEEK_|DASHSCOPE|MOONSHOT|ZHIPU|QWEN|ARK_|VOLC|EXECUTOR_|MYAGENT_|LOCAL_LLM|LLM_|TAVILY_|BRAVE_|JINA_|SEARXNG_|FEISHU_|LARK_|SENTRY_|SSL_BYPASS|WEB_SEARCH|WEB_DOWNLOAD|GITHUB_TOKEN|GH_TOKEN|HF_TOKEN|HUGGING|AWS_|AZURE_|GOOGLE_|PYTHONPATH|PYTHONHOME|PYTHONSTARTUP|PYTHONUSERBASE)/i
  const env = {}
  for (const [key, value] of Object.entries(process.env)) {
    if (value === undefined) continue
    if (SENSITIVE.test(key)) continue
    env[key] = value
  }
  Object.assign(env, {
    OPEN_BROWSER: '0',
    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1',
    SUGARAGENT_DESKTOP: '1',
    SUGARAGENT_DESKTOP_VERSION: app.getVersion(),
    SUGARAGENT_NOTIFY_PORT: notificationBridge ? String(notificationBridge.port) : '',
    SUGARAGENT_NOTIFY_TOKEN: notificationBridge ? notificationBridge.token : '',
    MYAGENT_SERVER_PORT: String(activePort),
    MYAGENT_SUPERVISOR_PID: String(process.pid || ''),
    WORK_DIR: current.workDir,
    SKILLS_DIR: current.skillsDir || path.join(current.workDir, 'skills'),
    LOG_DIR: current.logDir,
    ...(lifecycleBridge ? lifecycleBridge.environment() : {}),
  })
  return env
}

/** 第一次运行时把打包好的技能模板铺到工作目录（只在缺失时复制）。 */
function seedWorkspace() {
  const current = resolveLayout()
  const skillsDir = current.skillsDir || path.join(current.workDir, 'skills')
  try {
    fs.mkdirSync(current.workDir, { recursive: true })
    if (fs.existsSync(skillsDir) || !fs.existsSync(SKILL_TEMPLATE)) return
    fs.cpSync(SKILL_TEMPLATE, skillsDir, { recursive: true })
    log(`已铺设技能模板 → ${skillsDir}`)
  } catch (error) {
    log(`技能模板铺设失败：${error && error.message}`)
  }
}

// -------------------------------------------------------------- backend io ---

function openBackendLog() {
  ensureLogDir()
  const name = `backend-${new Date().toISOString().slice(0, 10)}.log`
  backendLogFile = path.join(LOG_DIR, name)
  backendLogStream = fs.createWriteStream(backendLogFile, { flags: 'a' })
  backendLogStream.on('error', error => log(`后端日志写入失败：${error.message}`))
  return backendLogStream
}

/** 与源码版“运行日志”一致：在独立终端中实时追踪后端输出并按级别着色。 */
function openBackendLogs() {
  const viewer = path.join(RUNTIME_DIR, 'app', 'colored_log_viewer.ps1')
  if (!fs.existsSync(viewer)) {
    dialog.showErrorBox('无法打开后台日志', `缺少日志查看器：${viewer}`)
    return false
  }
  ensureLogDir()
  const logFile = backendLogFile || path.join(LOG_DIR, `backend-${new Date().toISOString().slice(0, 10)}.log`)
  fs.appendFileSync(logFile, '', 'utf8')
  // Start-Process 创建可见的独立控制台；辅助 PowerShell 自身保持隐藏。
  // 参数里的双引号保留空格路径，单引号按 PowerShell 字符串规则转义。
  const quote = value => `'${String(value).replace(/'/g, "''")}'`
  const args = ['-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', `"${viewer}"`, '-Path', `"${logFile}"`]
  const command = `Start-Process -FilePath 'powershell.exe' -ArgumentList @(${args.map(quote).join(', ')}) -WindowStyle Normal`
  const launcher = spawn('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', command], {
    stdio: 'ignore',
    windowsHide: true,
  })
  launcher.on('error', error => {
    log(`日志查看器启动失败：${error.message}`)
    dialog.showErrorBox('无法打开后台日志', error.message)
  })
  launcher.unref()
  return true
}

function startBackend(operation = null) {
  if (quitting) return null
  if (backend) return backend
  if (!fs.existsSync(PYTHON_EXE)) {
    fatal(`缺少内置 Python 运行时：${PYTHON_EXE}`)
    return
  }
  if (!fs.existsSync(APP_ENTRY)) {
    fatal(`缺少应用入口：${APP_ENTRY}`)
    return
  }
  if (!lifecycleBridge) {
    lifecycleBridge = createLifecycleBridge({ python: PYTHON_EXE,
      script: path.join(RUNTIME_DIR, 'app', 'lifecycle_supervisor.py'), baseUrl,
      onRestart: request => { if (!restartBackend(request)) lifecycleBridge.fail(request, '重启操作未能接管') },
      onPrepare: request => {
        if (!uiReady || !backend || request.target_instance_id !== backend.lifecycleInstanceId || quitting || backendRestarting) return false
        expectedBackendExits.add(backend)
        backendPreparing = true
        createTray()
        return true
      },
      onStatus: request => {
        if (request.phase === 'failed') {
          backendPreparing = false
          if (backend) expectedBackendExits.delete(backend)
          createTray()
        }
        if (mainWindow && mainWindow.webContents.send) mainWindow.webContents.send('sugaragent:lifecycle-status', request)
      }, log })
  }
  const instanceId = lifecycleBridge.newInstance(operation)
  lifecycleBridge.start(backendEnv())
  seedWorkspace()
  const stream = openBackendLog()
  stream.write(`\n===== 启动后端 ${new Date().toISOString()} =====\n`)
  let child
  try {
    child = spawn(PYTHON_EXE, [APP_ENTRY], {
      cwd: resolveLayout().cwd,
      env: backendEnv(),
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
      detached: !IS_WINDOWS,
    })
  } catch (error) {
    stream.end()
    if (backendLogStream === stream) backendLogStream = null
    throw error
  }
  backend = child
  child.lifecycleInstanceId = instanceId
  log(`后端已启动 pid=${child.pid}`)
  writeStatus({ backendState: 'started' })
  child.stdout.pipe(stream, { end: false })
  child.stderr.pipe(stream, { end: false })
  // close follows exit/error and the end of stdout/stderr. Keep the stream
  // alive until then so buffered output cannot write into a closed log.
  child.once('close', () => {
    stream.end()
    if (backendLogStream === stream) backendLogStream = null
  })
  let failureReported = false
  const reportFailure = (code, signal, error = null) => {
    const expected = expectedBackendExits.delete(child)
    const current = backend === child
    if (current) backend = null
    log(`后端退出 pid=${child.pid} code=${code} signal=${signal} quitting=${quitting} expected=${expected}${error ? ` error=${error.message}` : ''}`)
    stream.write(`===== 后端退出 code=${code} signal=${signal}${error ? ` error=${error.message}` : ''} =====\n`)
    if (quitting || expected || !current || failureReported) return
    failureReported = true
    writeStatus({ backendState: 'exited', backendExitCode: code, ...(error ? { backendError: error.message } : {}) })
    // Startup and restart own their failure UI; a running service owns its
    // crash dialog. Never report one failure again as a startup timeout.
    if (!uiReady || backendRestarting) return
    dialog.showMessageBox({
      type: 'error',
      title: 'SugarAgent 后端已停止',
      message: error ? `内置服务启动失败：${error.message}` : `内置服务意外退出（code=${code ?? 'null'}）。`,
      detail: `日志目录：${LOG_DIR}\n可点击“重启”重新拉起服务；本机 ${activePort} 端口被占用也会导致启动失败。`,
      buttons: ['重启', '打开日志目录', '退出'],
      defaultId: 0,
      cancelId: 2,
    }).then(result => {
      if (quitting || backend) return
      if (result.response === 0) restartBackend()
      else if (result.response === 1) shell.openPath(LOG_DIR)
      else app.quit()
    }).catch(error => log(`后端恢复对话框失败：${error.message}`))
  }
  child.on('error', error => reportFailure(null, null, error))
  child.on('exit', (code, signal) => reportFailure(code, signal))
  return child
}

function stopBackend() {
  const child = backend
  if (!child) return true
  if (!child.pid) return false
  const pid = child.pid
  // Register before sending the signal: the exit callback may run either
  // before or after a replacement process has started.
  expectedBackendExits.add(child)
  log(`停止后端 pid=${pid}`)
  try {
    if (IS_WINDOWS) {
      const result = spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true })
      if (result.error) throw result.error
      if (result.status !== 0) throw new Error(`taskkill 退出码 ${result.status}`)
    } else {
      process.kill(-pid, 'SIGTERM')
    }
  } catch (error) {
    expectedBackendExits.delete(child)
    log(`停止后端失败：${error && error.message}`)
    return false
  }
  if (backend === child) backend = null
  return true
}

function restartBackend(operation = null) {
  if (quitting || !uiReady || backendRestarting) return false
  backendRestarting = true
  backendPreparing = false
  createTray()
  if (mainWindow) mainWindow.setProgressBar(2)
  if (!stopBackend()) {
    if (operation) lifecycleBridge.fail(operation, '旧服务未能停止')
    backendRestarting = false
    if (mainWindow) mainWindow.setProgressBar(-1)
    createTray()
    dialog.showErrorBox('无法重启内置服务', `旧服务未能停止，请查看日志后重试。\n日志目录：${LOG_DIR}`)
    return false
  }
  layout = null
  writeStatus({ backendState: 'restarting' })
  restartTimer = setTimeout(async () => {
    restartTimer = null
    let reloaded = false
    try {
      if (quitting) return
      const child = startBackend(operation)
      const ready = await waitForBackend(180000, child)
      if (quitting) return
      if (!ready) {
        const message = child && backend === child
          ? '等待内置服务超过 180 秒仍未就绪。'
          : '内置服务启动失败或已退出。'
        dialog.showErrorBox('重启内置服务失败', `${message}\n日志目录：${LOG_DIR}`)
        if (operation) lifecycleBridge.fail(operation, message)
        return
      }
      const activation = pendingActivation
      pendingActivation = null
      await loadApp(activation ? activation.session : '')
      if (quitting) return
      if (backend !== child) throw new Error('内置服务在加载界面时退出。')
      reloaded = true
      if (mainWindow) void reportDesktopWindowVisibility(mainWindow.isVisible())
    } catch (error) {
      if (operation) lifecycleBridge.fail(operation, error.message)
      log(`后端重启失败：${error.message}`)
      if (!quitting) {
        if (!backend) writeStatus({ backendState: 'exited', backendError: error.message })
        dialog.showErrorBox('重启内置服务失败', `${error.message}\n日志目录：${LOG_DIR}`)
      }
    } finally {
      backendRestarting = false
      if (!quitting) {
        if (mainWindow) mainWindow.setProgressBar(-1)
        createTray()
        if (reloaded && pendingActivation) {
          const activation = pendingActivation
          pendingActivation = null
          void activateDesktop(activation).catch(error => log(`桌面通知激活失败：${error.message}`))
        }
      }
    }
  }, 800)
  return true
}

// ------------------------------------------------------------- healthcheck ---

function probeOnce(timeout = 1500, instanceId = '') {
  return new Promise(resolve => {
    const request = http.get({ host: HOST, port: activePort, path: '/api/ready', timeout }, response => {
      let body = ''
      response.setEncoding('utf8')
      response.on('data', chunk => { body += chunk; if (body.length > 16384) { request.destroy(); resolve(false) } })
      response.on('end', () => {
        try {
          const payload = JSON.parse(body)
          resolve(response.statusCode === 200 && payload.ok === true && payload.protocol === 'myagent-lifecycle-v1'
            && payload.instance_id === instanceId)
        } catch { resolve(false) }
      })
      response.on('error', () => resolve(false))
    })
    request.on('timeout', () => { request.destroy(); resolve(false) })
    request.on('error', () => resolve(false))
  })
}

/** 端口被别的 SugarAgent 实例占用时自动顺延，避免启动失败。 */
function isPortFree(port) {
  return new Promise(resolve => {
    const server = net.createServer()
    server.unref()
    server.once('error', () => resolve(false))
    server.once('listening', () => server.close(() => resolve(true)))
    server.listen(port, HOST)
  })
}

async function findFreePort(start, span) {
  for (let port = start; port < start + span; port += 1) {
    if (await isPortFree(port)) return port
  }
  return start
}

async function waitForBackend(timeoutMs = 180000, child = backend) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (quitting || !child || backend !== child) return false
    const ready = await probeOnce(1500, child.lifecycleInstanceId)
    if (quitting || backend !== child) return false
    if (ready) return true
    await new Promise(resolve => setTimeout(resolve, 400))
  }
  return false
}

// -------------------------------------------------------------- configured ---

const CONFIG_PROBE = [
  'import sys',
  'sys.path.insert(0, "app")',
  'from pathlib import Path',
  'try:',
  '    import model_profiles as mp',
  '    ok = any(mp.is_usable_profile(p) for p in mp.sorted_profiles(Path(".")))',
  'except Exception:',
  '    ok = False',
  'print("yes" if ok else "no")',
].join('\n')

/** 用应用自身的判定逻辑判断是否已完成模型配置。 */
function isConfigured() {
  const result = spawnSync(PYTHON_EXE, ['-c', CONFIG_PROBE], {
    cwd: resolveLayout().cwd,
    env: backendEnv(),
    encoding: 'utf8',
    timeout: 60000,
    windowsHide: true,
  })
  if (result.error) {
    log(`配置探测失败：${result.error.message}`)
    return true
  }
  const answer = String(result.stdout || '').trim().split(/\r?\n/).pop()
  return answer === 'yes'
}

// ------------------------------------------------------------------ window ---

function reportDesktopWindowVisibility(visible) {
  if (!notificationBridge || !uiReady || quitting) return Promise.resolve(false)
  const body = JSON.stringify({ visible })
  const authorization = `Bearer ${notificationBridge.token}`
  // Serialize fast close/reopen transitions so a late hide cannot override a
  // newer show at the backend and produce a notification over the open app.
  const send = () => new Promise(resolve => {
    const request = http.request({
      host: HOST, port: activePort, path: '/api/ui-desktop-window', method: 'POST', timeout: 1500,
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body), Authorization: authorization },
    }, response => {
      response.on('end', () => resolve(response.statusCode === 200))
      response.on('error', () => resolve(false))
      response.resume()
    })
    request.on('timeout', () => { request.destroy(); resolve(false) })
    request.on('error', () => resolve(false))
    request.end(body)
  })
  desktopWindowReport = desktopWindowReport.then(send, send).then(ok => {
    if (!ok && !quitting) log('桌面窗口显示状态同步失败')
    return ok
  })
  return desktopWindowReport
}

/** Native fallback for editing and embedded pages. Renderer menus prevent the
 * DOM contextmenu default, so only unhandled targets reach this event. */
function installNativeContextMenu(contents) {
  contents.on('context-menu', (event, params) => {
    const flags = params.editFlags || {}
    const items = []
    const label = (zh, en) => contents.sugarAgentLanguage === 'en' ? en : zh
    const edit = (role, zh, en, flag) => ({ role, label: label(zh, en), enabled: !!flags[flag] })
    if (params.isEditable) {
      items.push(edit('undo', '撤销', 'Undo', 'canUndo'), edit('redo', '重做', 'Redo', 'canRedo'),
        { type: 'separator' }, edit('cut', '剪切', 'Cut', 'canCut'), edit('copy', '复制', 'Copy', 'canCopy'),
        edit('paste', '粘贴', 'Paste', 'canPaste'), { type: 'separator' },
        edit('selectAll', '全选', 'Select all', 'canSelectAll'))
    } else if (params.selectionText) {
      items.push(edit('copy', '复制', 'Copy', 'canCopy'))
    }
    if (/^https?:\/\//i.test(params.linkURL || '')) {
      if (items.length) items.push({ type: 'separator' })
      const url = params.linkURL
      items.push({ label: label('在浏览器中打开链接', 'Open link in browser'), click: () => shell.openExternal(url).catch(() => {}) },
        { label: label('复制链接地址', 'Copy link address'), click: () => clipboard.writeText(url) })
    }
    if (params.mediaType === 'image' && params.hasImageContents) {
      if (items.length) items.push({ type: 'separator' })
      items.push({ label: label('复制图片', 'Copy image'), click: () => contents.copyImageAt(params.x, params.y) })
      if (/^(https?:|blob:|data:image\/)/i.test(params.srcURL || '')) {
        items.push({ label: label('保存图片', 'Save image'), click: () => contents.downloadURL(params.srcURL) })
      }
    }
    if (!items.length) return
    event.preventDefault()
    const window = BrowserWindow.fromWebContents(contents)
    Menu.buildFromTemplate(items).popup({ window, frame: params.frame || undefined })
  })
}

async function loadApp(session = '') {
  if (!mainWindow) return
  const configured = isConfigured()
  const target = configured ? (session ? `/?session=${encodeURIComponent(session)}` : '/') : '/setup'
  log(`加载界面 ${target}（configured=${configured}）`)
  await mainWindow.loadURL(`${baseUrl()}${target}`)
  mainWindow.setProgressBar(-1)
  writeStatus({ backendState: 'ready', windowTarget: target, configured })
}

/** 先绘制本地启动页，再进行路径探测、技能复制和后端启动。 */
async function showStartup() {
  createWindow()
  const window = mainWindow
  const painted = new Promise(resolve => window.once('ready-to-show', resolve))
  window.setProgressBar(2)
  await window.loadFile(path.join(__dirname, 'startup.html'))
  await painted
}

/** 告知轻量启动入口：Electron 的第一帧已经可见，可以收起原生提示。 */
function notifyStartupLauncher() {
  const value = process.argv.find(arg => arg.startsWith('--sugaragent-startup-pipe='))
  const name = value && value.slice('--sugaragent-startup-pipe='.length)
  if (!IS_WINDOWS || !/^SugarAgent-startup-[a-f0-9]{32}$/.test(name || '')) return
  const socket = net.createConnection(`\\\\.\\pipe\\${name}`)
  socket.on('connect', () => socket.end('ready'))
  socket.on('error', error => log(`启动提示交接失败：${error.message}`))
  socket.setTimeout(2000, () => socket.destroy())
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    show: false,
    backgroundColor: nativeTheme.shouldUseDarkColors ? '#151517' : '#ffffff',
    title: 'SugarAgent',
    icon: TRAY_ICON,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webviewTag: true,
      spellcheck: false,
    },
  })

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    notifyStartupLauncher()
  })
  require('./speech-permissions').installSpeechPermissions(mainWindow.webContents, baseUrl)
  browserGuests.bind(mainWindow)
  mainWindow.on('close', event => {
    if (quitting) return
    event.preventDefault()
    mainWindow.hide()
  })
  mainWindow.on('hide', () => { void reportDesktopWindowVisibility(false) })
  mainWindow.on('show', () => { void reportDesktopWindowVisibility(true) })
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isApplicationUrl(url)) return { action: 'allow', overrideBrowserWindowOptions: { webPreferences: { webviewTag: false } } }
    shell.openExternal(url).catch(() => {})
    return { action: 'deny' }
  })
  const guardNavigation = (event, url) => {
    if (!isApplicationUrl(url)) {
      event.preventDefault()
      shell.openExternal(url).catch(() => {})
    }
  }
  mainWindow.webContents.on('will-navigate', guardNavigation)
  mainWindow.webContents.on('will-redirect', guardNavigation)
  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    log(`渲染进程异常：${JSON.stringify(details)}`)
    dialog.showMessageBox({
      type: 'error',
      title: 'SugarAgent 界面异常',
      message: '界面进程已崩溃。',
      buttons: ['重新加载', '退出'],
      defaultId: 0,
      cancelId: 1,
    }).then(result => {
      if (result.response === 0) mainWindow && mainWindow.reload()
      else app.quit()
    })
  })
  mainWindow.on('closed', () => { mainWindow = null })
}

function showWindow() {
  if (!mainWindow) createWindow()
  if (mainWindow.isMinimized()) mainWindow.restore()
  if (!mainWindow.isVisible()) mainWindow.show()
  mainWindow.focus()
  // focus() 没有成功返回值；记录真实状态，避免把任务栏闪烁误判为前置成功。
  if (!mainWindow.isFocused()) log('窗口激活未获得前台焦点')
}

// -------------------------------------------------------- desktop activation ---

function parseDesktopActivation(argv) {
  for (const value of argv) {
    try {
      const url = new URL(value)
      if (url.protocol !== `${OPEN_UI_PROTOCOL}:` || url.hostname !== 'open-ui'
          || (url.pathname && url.pathname !== '/')) continue
      const session = url.searchParams.get('session') || ''
      return { session: /^[A-Za-z0-9][A-Za-z0-9-]{0,63}$/.test(session) ? session : '' }
    } catch {
      /* 非协议命令行参数 */
    }
  }
  return null
}

function registerDesktopProtocol() {
  const launcher = path.join(path.dirname(process.execPath), 'SugarAgent.exe')
  const registered = app.isPackaged
    ? (IS_WINDOWS && path.basename(process.execPath) === 'SugarAgentRuntime.exe'
      ? app.setAsDefaultProtocolClient(OPEN_UI_PROTOCOL, launcher, [])
      : app.setAsDefaultProtocolClient(OPEN_UI_PROTOCOL))
    : app.setAsDefaultProtocolClient(OPEN_UI_PROTOCOL, process.execPath, [app.getAppPath()])
  if (!registered) log('桌面通知协议注册失败')
}

/** 复用前端现有的会话激活机制，正常情况下无需重载页面。 */
function requestSessionActivation(session) {
  return new Promise(resolve => {
    const body = JSON.stringify({ path: '/', session })
    const request = http.request({
      host: HOST, port: activePort, path: '/api/ui-activation', method: 'POST', timeout: 1500,
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
    }, response => {
      let data = ''
      response.setEncoding('utf8')
      response.on('data', chunk => { data += chunk })
      response.on('end', () => {
        try { resolve(response.statusCode === 200 && JSON.parse(data).reused === true) }
        catch { resolve(false) }
      })
      response.on('error', () => resolve(false))
    })
    request.on('timeout', () => { request.destroy(); resolve(false) })
    request.on('error', () => resolve(false))
    request.end(body)
  })
}

async function activateDesktop(activation) {
  // 启动期间复用已有的启动页，保留会话请求直到应用界面就绪。
  if (!uiReady || backendRestarting || backendPreparing) {
    pendingActivation = activation
    if (mainWindow) showWindow()
    return
  }
  showWindow()
  if (!activation.session) return
  const url = new URL(mainWindow.webContents.getURL())
  if (url.pathname === '/setup') return
  if (url.pathname === '/' && await requestSessionActivation(activation.session)) return
  await mainWindow.loadURL(`${baseUrl()}/?session=${encodeURIComponent(activation.session)}`)
}

function applyNativeTheme(event, theme) {
  // 仅允许本地应用的顶层窗口同步主题，嵌入的插件页面不能控制原生外观。
  if (!mainWindow || event.sender !== mainWindow.webContents
      || event.senderFrame !== mainWindow.webContents.mainFrame) return false
  let url
  try { url = new URL(event.senderFrame.url) } catch { return false }
  if (url.origin !== baseUrl() || !['light', 'dark', 'purple'].includes(theme)) return false
  nativeTheme.themeSource = theme === 'light' ? 'light' : 'dark'
  mainWindow.setBackgroundColor({ light: '#ffffff', dark: '#151517', purple: '#1e1e2e' }[theme])
  return true
}

// ------------------------------------------------------------------- tray ---

function trayImage() {
  const image = nativeImage.createFromPath(TRAY_ICON)
  return image.isEmpty() ? nativeImage.createEmpty() : image
}

async function requestBackendRestart() {
  try {
    if (!uiReady || !lifecycleBridge || quitting || backendRestarting || backendPreparing) return false
    const result = await lifecycleBridge.requestManual()
    showWindow()
    if (mainWindow && mainWindow.webContents.send) mainWindow.webContents.send('sugaragent:lifecycle-status', result.operation)
    return result
  } catch (error) {
    dialog.showErrorBox('无法提交重启请求', error.message)
    return false
  }
}

function createTray() {
  if (!tray) {
    tray = new Tray(trayImage())
    tray.setToolTip('SugarAgent')
    tray.on('double-click', () => showWindow())
  }
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: '打开主界面', click: () => showWindow() },
    { label: '在浏览器中打开', enabled: uiReady && !backendRestarting && !backendPreparing, click: () => shell.openExternal(`${baseUrl()}/`) },
    { type: 'separator' },
    { label: '重启内置服务', enabled: uiReady && !backendRestarting && !backendPreparing, click: () => requestBackendRestart() },
    { label: '打开后台日志', click: () => openBackendLogs() },
    { label: '打开工作目录', click: () => shell.openPath(resolveLayout().workDir) },
    { type: 'separator' },
    { label: '退出 SugarAgent', click: () => { quitting = true; app.quit() } },
  ]))
}

// ------------------------------------------------------------------- boot ---

function fatal(message) {
  if (mainWindow) mainWindow.setProgressBar(-1)
  dialog.showErrorBox('SugarAgent 无法启动', `${message}\n\n请重新安装，或把本目录下的日志反馈给开发者。`)
  app.quit()
}

function registerIpc() {
  function assertAppSender(event) {
    if (!mainWindow || event.sender !== mainWindow.webContents || event.senderFrame !== event.sender.mainFrame) throw new Error('Invalid browser sender')
    const url = new URL(event.senderFrame.url)
    if (url.origin !== baseUrl() || !['/', '/setup', '/settings'].includes(url.pathname)
        && !url.pathname.startsWith('/setup/')) throw new Error('Desktop IPC requires the application document')
    return url
  }
  function assertBrowserSender(event) {
    const url = assertAppSender(event)
    if (url.origin !== baseUrl() || url.pathname !== '/') throw new Error('Browser IPC requires the application document')
  }
  ipcMain.handle('sugaragent:browser-acquire', (event, workspace) => {
    assertBrowserSender(event)
    return browserGuests.acquire(event.sender, workspace)
  })
  ipcMain.handle('sugaragent:browser-release', (event, lease) => {
    assertBrowserSender(event)
    if (typeof lease !== 'string') throw new Error('Invalid browser lease')
    return browserGuests.release(event.sender, lease)
  })
  ipcMain.handle('sugaragent:info', event => {
    assertAppSender(event)
    return {
    version: app.getVersion(),
    port: activePort,
    baseUrl: baseUrl(),
    runtimeDir: RUNTIME_DIR,
    userDir: USER_DIR,
    logsDir: LOG_DIR,
    workDir: resolveLayout().workDir,
    }
  })
  ipcMain.handle('sugaragent:restart-backend', event => {
    assertBrowserSender(event)
    return requestBackendRestart()
  })
  ipcMain.handle('sugaragent:lifecycle-status', event => {
    assertBrowserSender(event)
    return lifecycleBridge ? lifecycleBridge.status() : null
  })
  ipcMain.handle('sugaragent:open-logs', event => {
    assertAppSender(event)
    return openBackendLogs()
  })
  ipcMain.on('sugaragent:theme', applyNativeTheme)
  ipcMain.on('sugaragent:language', (event, language) => {
    if (!mainWindow || event.sender !== mainWindow.webContents || event.senderFrame !== event.sender.mainFrame) return
    try { if (new URL(event.senderFrame.url).origin !== baseUrl()) return } catch { return }
    event.sender.sugarAgentLanguage = language === 'en' ? 'en' : 'zh-CN'
  })
  ipcMain.handle('sugaragent:open-workdir', event => {
    assertAppSender(event)
    return shell.openPath(resolveLayout().workDir)
  })
  ipcMain.handle('sugaragent:open-local-path', (event, payload) => {
    if (!mainWindow || event.sender !== mainWindow.webContents
        || event.senderFrame !== event.sender.mainFrame) return { ok: false, error: '无效的页面来源' }
    try {
      if (new URL(event.senderFrame.url).origin !== baseUrl()) return { ok: false, error: '无效的页面来源' }
    } catch { return { ok: false, error: '无效的页面来源' } }
    return openWorkspacePath({ baseUrl: baseUrl(), shell, log }, payload)
  })
  ipcMain.handle('sugaragent:open-external', (event, url) => {
    assertAppSender(event)
    if (typeof url === 'string' && /^https?:\/\//i.test(url)) return shell.openExternal(url)
    return false
  })
}

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  // Also covers settings/setup child windows and context menus in their frames.
  app.on('web-contents-created', (_event, contents) => installNativeContextMenu(contents))
  app.on('second-instance', (_event, argv) => {
    void activateDesktop(parseDesktopActivation(argv) || { session: '' })
      .catch(error => log(`桌面通知激活失败：${error.message}`))
  })

  app.whenReady().then(async () => {
    app.setAppUserModelId('com.sugaragent.desktop')
    removeLegacyElectronShortcuts({ app, shell, execPath: process.execPath, log })
    // 前端默认浅色；载入后 preload 会按实际页面主题同步原生边框和菜单。
    nativeTheme.themeSource = 'light'
    ensureLogDir()
    registerDesktopProtocol()
    log(`启动 SugarAgent ${app.getVersion()}（runtime=${RUNTIME_DIR}）`)
    registerIpc()
    if (IS_DEV) {
      const { default: installExtension, REACT_DEVELOPER_TOOLS } = (() => {
        try { return require('electron-devtools-installer') } catch { return { default: null } }
      })()
      if (installExtension) installExtension(REACT_DEVELOPER_TOOLS).catch(() => {})
    } else {
      Menu.setApplicationMenu(null)
    }
    await showStartup()
    if (quitting) return
    createTray()
    app.on('activate', () => showWindow())
    activePort = await findFreePort(BASE_PORT, PORT_SPAN)
    if (quitting) return
    if (activePort !== BASE_PORT) log(`端口 ${BASE_PORT} 已被占用，改用 ${activePort}`)
    try {
      notificationBridge = await createNotificationBridge({
        Notification, icon: TRAY_ICON, activate: activateDesktop, log,
      })
    } catch (error) {
      log(`桌面通知通道启动失败：${error.message}`)
    }
    if (quitting) return
    startBackend()
    const ready = await waitForBackend(180000)
    if (quitting) return
    if (!ready) {
      const message = backend ? '内置服务在 180 秒内未就绪。' : '内置服务启动失败或已退出。'
      fatal(`${message}\n日志：${path.join(LOG_DIR, `backend-${new Date().toISOString().slice(0, 10)}.log`)}`)
      return
    }
    const initialActivation = pendingActivation
    pendingActivation = null
    await loadApp(initialActivation ? initialActivation.session : '')
    uiReady = true
    void reportDesktopWindowVisibility(mainWindow.isVisible())
    createTray()
    if (pendingActivation) {
      const activation = pendingActivation
      pendingActivation = null
      await activateDesktop(activation)
    }
  }).catch(error => {
    if (quitting) return
    log(`桌面启动失败：${error.message}`)
    fatal(error.message)
  })

  app.on('window-all-closed', () => {
    // 常驻托盘：不在这里退出。
  })

  app.on('before-quit', () => {
    quitting = true
    if (restartTimer !== null) clearTimeout(restartTimer)
    restartTimer = null
  })

  app.on('will-quit', () => {
    if (lifecycleBridge) lifecycleBridge.close()
    if (notificationBridge) notificationBridge.close()
    stopBackend()
  })
}
