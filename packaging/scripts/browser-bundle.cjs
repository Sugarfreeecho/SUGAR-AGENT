'use strict'
const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')
const policy = require('../browser-runtime.lock.json')
const excluded = new Set(['node_modules', 'dist', 'artifacts', 'design-review', 'tests', '__pycache__', '.pytest_cache', '.git', '.config', '.sugaragent', '.cache', 'logs', 'outputs', 'test-results', 'playwright-report', 'coverage'])
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')

function filesUnder(root, { source = false } = {}) {
  const files = []
  function walk(directory) {
    for (const name of fs.readdirSync(directory).sort()) {
      const full = path.join(directory, name), stat = fs.lstatSync(full)
      if (source && (excluded.has(name) || name === '.env' || name.startsWith('.env.'))) continue
      if (stat.isSymbolicLink()) throw new Error(`浏览器发布资源不允许符号链接：${full}`)
      if (stat.isDirectory()) walk(full)
      else if (stat.isFile() && (!source || !name.endsWith('.pyc'))) files.push(full)
    }
  }
  walk(root)
  return files
}

function browserInputs(repo) {
  const hash = crypto.createHash('sha256')
  for (const relative of ['browser-extension', 'plugins/browser-use']) {
    for (const file of filesUnder(path.join(repo, relative), { source: true })) {
      hash.update(path.relative(repo, file).replaceAll('\\', '/') + '\0').update(fs.readFileSync(file))
    }
  }
  // The extension compiles the main UI follower into its own bundle.
  // Changes there must invalidate a previously prepared desktop payload too.
  const sharedFollow = 'frontend/src/app/modules/smooth-stream.js'
  hash.update(sharedFollow + '\0').update(fs.readFileSync(inside(repo, sharedFollow)))
  hash.update(JSON.stringify(policy))
  return hash.digest('hex')
}

function inside(root, relative) {
  if (typeof relative !== 'string' || path.isAbsolute(relative) || relative.split(/[\\/]/).includes('..')) throw new Error('无效的浏览器资源路径')
  const full = path.resolve(root, relative)
  if (!full.startsWith(path.resolve(root) + path.sep)) throw new Error('浏览器资源路径越界')
  let ancestor = path.resolve(root)
  for (const part of relative.split(/[\\/]/)) {
    ancestor = path.join(ancestor, part)
    if (fs.existsSync(ancestor) && fs.lstatSync(ancestor).isSymbolicLink()) throw new Error('浏览器资源路径不能经过符号链接')
  }
  return full
}

function assertBrowserBundle(payload, { repo } = {}) {
  const fail = message => { throw new Error(`${message}；请重新运行 npm run payload:fast 或 npm run payload`) }
  const report = path.join(payload, 'browser-bundle.json')
  if (!fs.existsSync(report)) fail('载荷缺少浏览器连接发布组件')
  const info = JSON.parse(fs.readFileSync(report, 'utf8'))
  if (info.schemaVersion !== 1 || !Array.isArray(info.files) || !info.files.length) fail('浏览器发布清单不完整')
  const expected = [
    'node/node.exe', 'node/LICENSE', 'plugins/browser-use/host.py', 'plugins/browser-use/runtime_paths.py',
    'plugins/browser-use/node/server.mjs', 'plugins/browser-use/node/engine.mjs',
    'plugins/browser-use/node/node_modules/@playwright/mcp/package.json',
    'plugins/browser-use/node/node_modules/playwright/package.json',
    'plugins/browser-use/node/node_modules/playwright-core/package.json',
    'browser-extension/dist/manifest.json', 'browser-extension/dist/sidepanel.html', 'browser-extension/dist/background.js', 'browser-extension/dist/sidepanel.js',
    'browser-extension/dist/THIRD_PARTY_NOTICES.md', `outputs/browser-extension/sugaragent-browser-${info.version}.zip`,
  ]
  const recorded = new Set(info.files.map(file => file.path))
  for (const relative of expected) if (!recorded.has(relative)) fail(`浏览器发布清单缺少 ${relative}`)
  for (const entry of info.files) {
    const file = inside(payload, entry.path)
    if (!fs.existsSync(file) || !fs.lstatSync(file).isFile() || fs.lstatSync(file).isSymbolicLink() || sha256(file) !== entry.sha256) fail(`浏览器资源缺失或已改变：${entry.path}`)
  }
  if (sha256(path.join(payload, 'node/node.exe')) !== policy.node.sha256 || sha256(path.join(payload, 'node/LICENSE')) !== policy.node.licenseSha256) fail('内置 Node 与固定版本不一致')
  const manifest = JSON.parse(fs.readFileSync(path.join(payload, 'browser-extension/dist/manifest.json'), 'utf8'))
  const plugin = JSON.parse(fs.readFileSync(path.join(payload, 'plugins/browser-use/.myagent-plugin/plugin.json'), 'utf8'))
  if (manifest.version !== info.version || plugin.version !== info.version) fail('浏览器扩展与后端插件版本不一致')
  const runtime = path.join(payload,'plugins/browser-use/node')
  const expectedMcp = JSON.parse(fs.readFileSync(path.join(runtime,'package.json'),'utf8')).dependencies?.['@playwright/mcp']
  const actualMcp = JSON.parse(fs.readFileSync(path.join(runtime,'node_modules/@playwright/mcp/package.json'),'utf8')).version
  if (expectedMcp !== actualMcp) fail('浏览器生产依赖与声明版本不一致')
  if (repo && info.inputDigest !== browserInputs(repo)) fail('浏览器源码或依赖已更新，复用载荷已过期')
  return info
}
module.exports = { sha256, filesUnder, browserInputs, inside, assertBrowserBundle }
