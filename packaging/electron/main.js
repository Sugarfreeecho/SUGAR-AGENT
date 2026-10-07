'use strict'

/**
 * SugarAgent 桌面版主进程。
 *
 * 职责：
 *  1. 托管内置 Python 后端（app/main.py，监听 127.0.0.1:8192），把 stdout/stderr 落盘；
 *  2. 首次启动时把打包的技能模板铺到工作目录，未完成配置时直接打开应用自带的 /setup 向导；
 *  3. 原生窗口 + 托盘常驻，关闭窗口即最小化到托盘，退出时按进程树清理后端；
 *  4. 后端异常退出时给出可操作的恢复对话框。
 */

const { app, BrowserWindow, Menu, Tray, dialog, ipcMain, nativeImage, shell } = require('electron')
const { spawn, spawnSync } = require('node:child_process')
const fs = require('node:fs')
const http = require('node:http')
const net = require('node:net')
const path = require('node:path')

const HOST = '127.0.0.1'
const BASE_PORT = Number(process.env.SUGARAGENT_PORT || 8192)
const PORT_SPAN = 8
let activePort = BASE_PORT
const baseUrl = () => `http://${HOST}:${activePort}`

const RUNTIME_DIR = path.join(process.resourcesPath, 'runtime')
const PYTHON_EXE = path.join(RUNTIME_DIR, 'python', process.platform === 'win32' ? 'python.exe' : 'python3')
const APP_ENTRY = path.join(RUNTIME_DIR, 'app', 'main.py')
const SKILL_TEMPLATE = path.join(RUNTIME_DIR, 'workspace-template', 'skills')
const TRAY_ICON = path.join(process.resourcesPath, 'tray.ico')
const USER_DIR = app.getPath('userData')
const LOG_DIR = path.join(USER_DIR, 'logs')

const IS_WINDOWS = process.platform === 'win32'
const IS_DEV = process.env.SUGARAGENT_DEV === '1'

let mainWindow = null
let tray = null
let backend = null
let backendLogStream = null
let quitting = false
let restartTimer = null

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

function resolveLayout() {
  if (layout) return layout
  const writable = runtimeIsWritable()
  // 工作目录放在“文档”下，卸载/重装都不会带走用户的会话与技能
  const workDir = path.join(app.getPath('documents'), 'SugarAgent', 'workspace')
  layout = {
    writable,
    workDir,
    logDir: path.join(USER_DIR, 'app-logs'),
    cwd: writable ? RUNTIME_DIR : USER_DIR,
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
    MYAGENT_SERVER_PORT: String(activePort),
    WORK_DIR: current.workDir,
    LOG_DIR: current.logDir,
  })
  return env
}

/** 第一次运行时把打包好的技能模板铺到工作目录（只在缺失时复制）。 */
function seedWorkspace() {
  const current = resolveLayout()
  const skillsDir = path.join(current.workDir, 'skills')
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
  backendLogStream = fs.createWriteStream(path.join(LOG_DIR, name), { flags: 'a' })
  return backendLogStream
}

function startBackend() {
  if (backend) return
  if (!fs.existsSync(PYTHON_EXE)) {
    fatal(`缺少内置 Python 运行时：${PYTHON_EXE}`)
    return
  }
  if (!fs.existsSync(APP_ENTRY)) {
    fatal(`缺少应用入口：${APP_ENTRY}`)
    return
  }
  seedWorkspace()
  const stream = openBackendLog()
  stream.write(`\n===== 启动后端 ${new Date().toISOString()} =====\n`)
  backend = spawn(PYTHON_EXE, [APP_ENTRY], {
    cwd: resolveLayout().cwd,
    env: backendEnv(),
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  log(`后端已启动 pid=${backend.pid}`)
  writeStatus({ backendState: 'started' })
  backend.stdout.pipe(stream, { end: false })
  backend.stderr.pipe(stream, { end: false })
  backend.on('error', error => log(`后端启动失败：${error.message}`))
  backend.on('exit', (code, signal) => {
    const pid = backend && backend.pid
    backend = null
    log(`后端退出 pid=${pid} code=${code} signal=${signal} quitting=${quitting}`)
    writeStatus({ backendState: 'exited', backendExitCode: code })
    if (backendLogStream) {
      backendLogStream.write(`===== 后端退出 code=${code} signal=${signal} =====\n`)
    }
    if (quitting) return
    dialog.showMessageBox({
      type: 'error',
      title: 'SugarAgent 后端已停止',
      message: `内置服务意外退出（code=${code ?? 'null'}）。`,
      detail: `日志目录：${LOG_DIR}\n可点击“重启”重新拉起服务；本机 8192 端口被占用也会导致启动失败。`,
      buttons: ['重启', '打开日志目录', '退出'],
      defaultId: 0,
      cancelId: 2,
    }).then(result => {
      if (result.response === 0) restartBackend()
      else if (result.response === 1) shell.openPath(LOG_DIR)
      else app.quit()
    })
  })
}

function stopBackend() {
  if (!backend || !backend.pid) return
  const pid = backend.pid
  log(`停止后端 pid=${pid}`)
  try {
    if (IS_WINDOWS) {
      spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true })
    } else {
      process.kill(-pid, 'SIGTERM')
    }
  } catch (error) {
    log(`停止后端失败：${error && error.message}`)
  }
  backend = null
}

function restartBackend() {
  stopBackend()
  if (restartTimer) clearTimeout(restartTimer)
  restartTimer = setTimeout(async () => {
    startBackend()
    const ready = await waitForBackend(180000)
    if (ready) await loadApp()
    else dialog.showErrorBox('启动超时', `等待内置服务超过 180 秒仍未就绪。\n日志目录：${LOG_DIR}`)
  }, 800)
}

// ------------------------------------------------------------- healthcheck ---

function probeOnce(timeout = 1500) {
  return new Promise(resolve => {
    const request = http.get({ host: HOST, port: activePort, path: '/api/runtime-status', timeout }, response => {
      response.resume()
      resolve(response.statusCode >= 200 && response.statusCode < 500)
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

async function waitForBackend(timeoutMs = 180000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (!backend) return false
    if (await probeOnce()) return true
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

async function loadApp() {
  if (!mainWindow) return
  const configured = isConfigured()
  const target = configured ? '/' : '/setup'
  log(`加载界面 ${target}（configured=${configured}）`)
  await mainWindow.loadURL(`${baseUrl()}${target}`)
  writeStatus({ backendState: 'ready', windowTarget: target, configured })
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1024,
    minHeight: 700,
    show: false,
    backgroundColor: '#0f1115',
    title: 'SugarAgent',
    icon: TRAY_ICON,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      spellcheck: false,
    },
  })

  mainWindow.once('ready-to-show', () => mainWindow.show())
  mainWindow.on('close', event => {
    if (quitting) return
    event.preventDefault()
    mainWindow.hide()
  })
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith(baseUrl())) return { action: 'allow' }
    shell.openExternal(url).catch(() => {})
    return { action: 'deny' }
  })
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith(baseUrl())) {
      event.preventDefault()
      shell.openExternal(url).catch(() => {})
    }
  })
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
  mainWindow.show()
  mainWindow.focus()
}

// ------------------------------------------------------------------- tray ---

function trayImage() {
  const image = nativeImage.createFromPath(TRAY_ICON)
  return image.isEmpty() ? nativeImage.createEmpty() : image
}

function createTray() {
  tray = new Tray(trayImage())
  tray.setToolTip('SugarAgent')
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: '打开主界面', click: () => showWindow() },
    { label: '打开配置向导', click: () => { showWindow(); mainWindow.loadURL(`${baseUrl()}/setup`) } },
    { label: '在浏览器中打开', click: () => shell.openExternal(`${baseUrl()}/`) },
    { type: 'separator' },
    { label: '重启内置服务', click: () => restartBackend() },
    { label: '打开日志目录', click: () => shell.openPath(LOG_DIR) },
    { label: '打开工作目录', click: () => shell.openPath(resolveLayout().workDir) },
    { type: 'separator' },
    { label: '退出 SugarAgent', click: () => { quitting = true; app.quit() } },
  ]))
  tray.on('double-click', () => showWindow())
}

// ------------------------------------------------------------------- boot ---

function fatal(message) {
  dialog.showErrorBox('SugarAgent 无法启动', `${message}\n\n请重新安装，或把本目录下的日志反馈给开发者。`)
  app.quit()
}

function registerIpc() {
  ipcMain.handle('sugaragent:info', () => ({
    version: app.getVersion(),
    port: activePort,
    baseUrl: baseUrl(),
    runtimeDir: RUNTIME_DIR,
    userDir: USER_DIR,
    logsDir: LOG_DIR,
    workDir: resolveLayout().workDir,
  }))
  ipcMain.handle('sugaragent:restart-backend', () => { restartBackend(); return true })
  ipcMain.handle('sugaragent:open-logs', () => shell.openPath(LOG_DIR))
  ipcMain.handle('sugaragent:open-workdir', () => shell.openPath(resolveLayout().workDir))
  ipcMain.handle('sugaragent:open-external', (_event, url) => {
    if (typeof url === 'string' && /^https?:\/\//i.test(url)) return shell.openExternal(url)
    return false
  })
}

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', () => showWindow())

  app.whenReady().then(async () => {
    app.setAppUserModelId('com.sugaragent.desktop')
    ensureLogDir()
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
    activePort = await findFreePort(BASE_PORT, PORT_SPAN)
    if (activePort !== BASE_PORT) log(`端口 ${BASE_PORT} 已被占用，改用 ${activePort}`)
    startBackend()
    const ready = await waitForBackend(180000)
    if (!ready) {
      fatal(`内置服务在 180 秒内未就绪。\n日志：${path.join(LOG_DIR, `backend-${new Date().toISOString().slice(0, 10)}.log`)}`)
      return
    }
    createWindow()
    await loadApp()
    createTray()
    app.on('activate', () => showWindow())
  })

  app.on('window-all-closed', () => {
    // 常驻托盘：不在这里退出。
  })

  app.on('before-quit', () => {
    quitting = true
  })

  app.on('will-quit', () => {
    stopBackend()
  })
}
