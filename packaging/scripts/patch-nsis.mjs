#!/usr/bin/env node
'use strict'

/**
 * 给 electron-builder 的 NSIS 模板打中文补丁（幂等，可反复执行）。
 *
 * electron-builder 自带的 zh_CN 语言文件里，安装模式页仍有两处写死的英文/占位：
 *   · 全部用户单选项后面硬编码 "(must run as admin)"
 *   · 当前用户单选项是 "$9 ($0)"，$0 是 Windows 用户名，显示成 "仅为我安装 (pc)"
 * 这里把模板里的这两行替换成中文；升级依赖后重新执行即可（build.mjs 每次构建都会调用）。
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
]

let applied = 0
let already = 0
const missing = []

for (const patch of PATCHES) {
  const target = path.join(TEMPLATE_ROOT, patch.file)
  if (!fs.existsSync(target)) {
    missing.push(patch.file)
    continue
  }
  const source = fs.readFileSync(target, 'utf8')
  if (source.includes(patch.to)) {
    already += 1
    continue
  }
  if (!source.includes(patch.from)) {
    missing.push(`${patch.file} :: ${patch.from.slice(0, 60)}…`)
    continue
  }
  fs.writeFileSync(target, source.replace(patch.from, patch.to), 'utf8')
  applied += 1
}

console.log(`NSIS 中文补丁：新应用 ${applied} 处，已是最新 ${already} 处${missing.length ? `，未匹配 ${missing.length} 处` : ''}`)
if (missing.length) console.log(`  未匹配：${missing.join(' | ')}`)
