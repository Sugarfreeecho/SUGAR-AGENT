'use strict'

const fs = require('node:fs')
const path = require('node:path')
const { assertNoLooseBytecode } = require('./payload-bytecode.cjs')

/** Reject a reused payload whose loose files would undo the install optimization. */
function assertRuntimeArchives(payload, { checkBytecode = true } = {}) {
  const report = path.join(payload, 'runtime-archives.json')
  const fail = message => { throw new Error(`${message}；请先重新准备载荷（npm run payload:fast 或 npm run payload）`) }
  if (!fs.existsSync(report)) fail('载荷尚未进行 SDK / PPT 图标归档优化')
  const info = JSON.parse(fs.readFileSync(report, 'utf8'))
  if (info.schemaVersion !== 1) fail('运行时归档清单不完整')
  const sdk = path.join(payload, 'python', 'Lib', 'site-packages')
  const zip = path.join(sdk, 'lark_oapi.zip')
  const pth = path.join(sdk, 'sugaragent-runtime-archives.pth')
  if (info.sdk) {
    if (!fs.existsSync(zip) || !fs.existsSync(pth) ||
        !fs.readFileSync(pth, 'utf8').split(/\r?\n/).includes('lark_oapi.zip') ||
        fs.existsSync(path.join(sdk, 'lark_oapi'))) fail('飞书 SDK 归档或加载路径不正确')
  } else if (fs.existsSync(zip) || fs.existsSync(pth) || fs.existsSync(path.join(sdk, 'lark_oapi'))) {
    fail('载荷不含飞书 SDK，但仍残留归档或加载路径')
  }
  const skill = path.join(payload, 'workspace-template', 'skills', 'ppt-master')
  if (fs.existsSync(skill)) {
    const icons = path.join(skill, 'templates', 'icons')
    if (!info.pptIcons || !fs.existsSync(path.join(icons, 'icons.zip')) ||
        !fs.existsSync(path.join(icons, 'icon-archive.json')) ||
        !fs.existsSync(path.join(skill, 'scripts', 'sugaragent_icon_archive.py'))) fail('PPT 图标归档或读取适配缺失')
    const stack = [icons]
    while (stack.length) {
      const directory = stack.pop()
      for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
        const full = path.join(directory, entry.name)
        if (entry.isDirectory()) stack.push(full)
        else if (entry.name.toLowerCase().endsWith('.svg')) fail('载荷混入了已展开的 PPT 图标')
      }
    }
  }
  if (checkBytecode) assertNoLooseBytecode(payload)
  return info
}

module.exports = { assertRuntimeArchives }
