'use strict'

/**
 * electron-builder 配置：Windows x64 + NSIS 一键安装（按用户安装，无需管理员）。
 *
 * 载荷布局（安装后）：
 *   %LOCALAPPDATA%\Programs\SugarAgent\
 *     SugarAgent.exe                       ← Electron 外壳
 *     resources\app.asar                   ← 外壳代码（electron/**）
 *     resources\tray.ico                   ← 托盘图标
 *     resources\runtime\…                  ← 内置运行时（python + app + plugins + skills 模板）
 */

const { existsSync } = require('node:fs')
const path = require('node:path')

// 安装器形态：assisted（默认，带向导页面）/ oneclick（双击即装，仅进度条）
const INSTALLER_STYLE = process.env.SUGARAGENT_INSTALLER_STYLE === 'oneclick' ? 'oneclick' : 'assisted'
const ASSISTED = INSTALLER_STYLE === 'assisted'
const SETUP_NAME = ASSISTED ? 'SugarAgent-Setup-${version}-x64.${ext}' : 'SugarAgent-Setup-${version}-x64-oneclick.${ext}'

module.exports = {
  appId: 'com.sugaragent.desktop',
  productName: 'SugarAgent',
  copyright: `Copyright © ${new Date().getFullYear()} SugarAgent`,
  // 直接用 node_modules 里已下载好的 Electron 发行版，避免每次构建重复联网拉取
  electronDist: path.join(__dirname, 'node_modules', 'electron', 'dist'),
  directories: { output: 'build/dist', buildResources: 'assets' },
  files: ['electron/**/*', 'package.json'],
  asar: true,
  // 只保留中英两种 Chromium 语言包：默认 55 个语言包占 ~48MB
  electronLanguages: ['zh-CN', 'en-US'],
  extraResources: [
    { from: 'build/payload', to: 'runtime', filter: ['**/*'] },
    { from: 'assets/tray.ico', to: 'tray.ico' },
  ],
  win: {
    icon: 'assets/app.ico',
    target: [{ target: 'nsis', arch: ['x64'] }],
    executableName: 'SugarAgent',
    artifactName: SETUP_NAME,
  },
  nsis: {
    oneClick: !ASSISTED,
    // 先放开警告以便看清新页面的告警内容（定位后再决定是否恢复严格模式）
    warningsAsErrors: false,
    perMachine: false,
    allowElevation: false,
    // 定制安装器：本项目只做“仅当前用户”安装，跳过“为哪位用户安装”页
    include: path.join(__dirname, 'nsis', 'installer.nsh'),
    // 向导模式：允许用户自选安装位置，并提供“完成页”→ 可勾选立即运行
    allowToChangeInstallationDirectory: ASSISTED,
    createDesktopShortcut: true,
    createStartMenuShortcut: true,
    shortcutName: 'SugarAgent',
    uninstallDisplayName: 'SugarAgent 桌面版',
    deleteAppDataOnUninstall: false,
    runAfterFinish: true,
    installerLanguages: ['zh_CN', 'en_US'],
    artifactName: SETUP_NAME,
  },
  compression: process.env.SUGARAGENT_MAX_COMPRESSION === '1' ? 'maximum' : 'normal',
  afterPack: async context => {
    const payload = path.join(context.appOutDir, 'resources', 'runtime')
    const python = path.join(payload, 'python', 'python.exe')
    const entry = path.join(payload, 'app', 'main.py')
    if (!existsSync(python) || !existsSync(entry)) {
      throw new Error(`载荷不完整：缺少 ${python} 或 ${entry}；请先运行 npm run payload`)
    }
    context.packager.appInfo.buildNumber = undefined
  },
}
