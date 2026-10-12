#!/usr/bin/env node
'use strict'

/**
 * 给 electron-builder 的 NSIS 模板打中文 / 用户数据保留 / 安装器仓库补丁（幂等，可反复执行）。
 *
 * electron-builder 自带的 zh_CN 语言文件里，安装模式页仍有两处写死的英文/占位：
 *   · 全部用户单选项后面硬编码 "(must run as admin)"
 *   · 当前用户单选项是 "$9 ($0)"，$0 是 Windows 用户名，显示成 "仅为我安装 (pc)"
 * 这里把模板里的这两行替换成中文；升级依赖后重新执行即可（build.mjs 每次构建都会调用）。
 *
 * 另外两处与用户数据有关的补丁：
 *   · uninstaller.nsh：把 un.atomicRMDir 的跳过名单补成 workspace/.config/.sugaragent，
 *     并把最终 `RMDir /r $INSTDIR` 换成 un.SugarAgentRemoveFiles（定义见 nsis/installer.nsh）；
 *   · include/installer.nsh：只在带更新渠道（resources\app-update.yml）时才把安装器自身
 *     复制到 %LOCALAPPDATA%\sugaragent-updater\installer.exe，否则不生成这个 ~250MB 的仓库副本。
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const PACKAGING = path.resolve(HERE, '..')
const TEMPLATE_ROOT = path.join(PACKAGING, 'node_modules', 'app-builder-lib', 'templates', 'nsis')

const PATCHES = [
  {
    file: 'multiUserUi.nsh',
    from: 'SendMessage $MultiUser.InstallModePage.AllUsers ${WM_SETTEXT} 0 "STR:$8 (must run as admin)"',
    to: 'SendMessage $MultiUser.InstallModePage.AllUsers ${WM_SETTEXT} 0 "STR:$8（需管理员权限）"',
  },
  {
    file: 'multiUserUi.nsh',
    from: '${NSD_CreateRadioButton} 10u 50u 280u 20u "$9 ($0)"',
    to: '${NSD_CreateRadioButton} 10u 50u 280u 20u "$9（当前用户：$0）"',
  },
  {
    // 只替换首次匹配（un.atomicRMDir），保留升级失败时的 un.restoreFiles。
    file: 'uninstaller.nsh',
    from: 'IfFileExists "$INSTDIR$R0\\$R2\\*.*" isDir isNotDir',
    previous: 'StrCmp "$R0\\$R2" "\\resources\\runtime\\workspace" continue\n    IfFileExists "$INSTDIR$R0\\$R2\\*.*" isDir isNotDir',
    to: 'StrCmp "$R0\\$R2" "\\resources\\runtime\\workspace" continue\n    StrCmp "$R0\\$R2" "\\resources\\runtime\\.config" continue\n    StrCmp "$R0\\$R2" "\\resources\\runtime\\.sugaragent" continue\n    IfFileExists "$INSTDIR$R0\\$R2\\*.*" isDir isNotDir',
    required: true,
  },
  {
    file: 'uninstaller.nsh',
    from: 'RMDir /r $INSTDIR',
    to: 'Push ""\n    Call un.SugarAgentRemoveFiles',
    required: true,
  },
  {
    // 安装器仓库：electron-builder 默认无条件把安装器自身复制成
    // %LOCALAPPDATA%\sugaragent-updater\installer.exe（≈整包大小）。它只在“带更新渠道”的
    // 包里才有意义（更新器用 --package-file 复用本地包做差分/修复）；resources\app-update.yml
    // 由 PublishManager 在配置了 publish 时写入，正好当判据。
    file: 'include/installer.nsh',
    from: '      !insertmacro copyFile "$EXEPATH" "$LOCALAPPDATA\\${APP_INSTALLER_STORE_FILE}"',
    to: '      # SugarAgent：仅当带更新渠道（resources\\app-update.yml）时才留安装器副本\n      IfFileExists "$INSTDIR\\resources\\app-update.yml" 0 sugar_skip_installer_store\n        !insertmacro copyFile "$EXEPATH" "$LOCALAPPDATA\\${APP_INSTALLER_STORE_FILE}"\n      sugar_skip_installer_store:',
    required: true,
  },
]

let applied = 0
let already = 0
const missing = []

for (const patch of PATCHES) {
  const target = path.join(TEMPLATE_ROOT, patch.file)
  if (!fs.existsSync(target)) {
    if (patch.required) throw new Error(`缺少用户数据保留补丁的目标模板：${target}`)
    missing.push(patch.file)
    continue
  }
  const source = fs.readFileSync(target, 'utf8').replace(/\r\n/g, '\n')
  if (source.includes(patch.to)) {
    already += 1
    continue
  }
  const from = patch.previous && source.includes(patch.previous) ? patch.previous : patch.from
  if (!source.includes(from)) {
    if (patch.required) throw new Error(`NSIS 模板发生变化，无法应用用户数据保留补丁：${patch.file}`)
    missing.push(`${patch.file} :: ${patch.from.slice(0, 60)}…`)
    continue
  }
  fs.writeFileSync(target, source.replace(from, patch.to), 'utf8')
  applied += 1
}

console.log(`NSIS 模板补丁：新应用 ${applied} 处，已是最新 ${already} 处${missing.length ? `，未匹配 ${missing.length} 处` : ''}`)
if (missing.length) console.log(`  未匹配：${missing.join(' | ')}`)
