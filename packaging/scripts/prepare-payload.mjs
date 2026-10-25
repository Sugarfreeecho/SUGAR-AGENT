#!/usr/bin/env node
'use strict'

/**
 * 组装 SugarAgent 桌面版运行时载荷 → packaging/build/payload
 *
 * 载荷结构（安装后位于 resources/runtime）：
 *   app/                 应用代码（tools/skills 模板/前端 dist 都在其中）
 *   plugins/             内置插件
 *   python/              便携 Python 3.10 基座 + 干净安装的 site-packages
 *   workspace-template/  首次启动时铺设到工作目录的技能模板
 *   runtime-manifest.json 载荷清单（版本 / 依赖 / 体积）
 *
 * 用法：
 *   node scripts/prepare-payload.mjs                 # 拷贝 + 安装依赖（需要网络）
 *   node scripts/prepare-payload.mjs --skip-deps     # 复用已装好的 site-packages，快速重打包
 *   node scripts/prepare-payload.mjs --build-frontend # 先重新构建前端（vite build）
 *   node scripts/prepare-payload.mjs --list-skills   # 只打印白名单内/外的技能，不写载荷
 *   node scripts/prepare-payload.mjs --all-skills    # 忽略 skills.allowlist.txt，打包全部技能
 *   node scripts/prepare-payload.mjs --all-plugins   # 连独立功能插件一起打包（默认只打非独立功能）
 *
 * 技能模板只拷贝 skills.allowlist.txt 里列出的目录；该名单是打包侧的固定契约，
 * 与运行时界面的技能启停状态无关。
 * 插件只拷贝 app/plugins/tiers.json 里非 standalone 的目录（system / system-external / extension）。
 */

import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const { assertRuntimeArchives } = createRequire(import.meta.url)('./runtime-archives.cjs')
const { cleanupPyc } = createRequire(import.meta.url)('./payload-bytecode.cjs')

const HERE = path.dirname(fileURLToPath(import.meta.url))
const PACKAGING = path.resolve(HERE, '..')
const REPO = path.resolve(PACKAGING, '..')
const BUILD = path.join(PACKAGING, 'build')
const PAYLOAD = path.join(BUILD, 'payload')
const SITE_PACKAGES = path.join(PAYLOAD, 'python', 'Lib', 'site-packages')
const REPO_PYTHON = path.join(REPO, 'python', 'python.exe')
const PAYLOAD_PYTHON = path.join(PAYLOAD, 'python', 'python.exe')
const REQUIREMENTS = path.join(PACKAGING, 'requirements.desktop.txt')
const PACKAGE_JSON = JSON.parse(fs.readFileSync(path.join(PACKAGING, 'package.json'), 'utf8'))
// Build-only policy: installed applications may still create/reuse caches.
const PYTHON_BUILD_ENV = { ...process.env, PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1' }

const flags = new Set(process.argv.slice(2))
const SKIP_DEPS = flags.has('--skip-deps')
const BUILD_FRONTEND = flags.has('--build-frontend')
const SKIP_SKILLS = flags.has('--skip-skills')
const ALL_SKILLS = flags.has('--all-skills')
const LIST_SKILLS = flags.has('--list-skills')
const ALL_PLUGINS = flags.has('--all-plugins')
const LIST_PLUGINS = flags.has('--list-plugins')

const APP_EXCLUDE_NAMES = new Set(['__pycache__', '.pytest_cache', '.mypy_cache', 'logs'])
const APP_EXCLUDE_REL = new Set(['.env', '.env.local', '.env.production', '.requirements.installed'])
const PLUGIN_EXCLUDE_NAMES = new Set(['__pycache__', '.pytest_cache', 'node_modules', '.venv', 'venv'])
// Scripts/ 的内容都来自开发机历史安装（ct2-*、whisper 等 shim），只保留我们自己放的 rg.exe
const PYTHON_EXCLUDE_REL = new Set(['Lib/site-packages', 'Scripts', 'Lib/__pycache__'])

const EXCLUDED_PACKAGES = [
  'playwright（浏览器自动化，含浏览器内核 >300MB）',
  'matplotlib（图表绘制）',
  'pandas（数据分析）',
  'pymupdf（PDF 渲染；保留 pdfplumber）',
  'markitdown（文档转 Markdown）',
  'sentry-sdk / coverage / pytest / pytest-asyncio / python-magic（开发与监控）',
  'aiohttp 及其传递依赖（唯一使用者 sugar-bili-scroll，独立功能不随包分发）',
  'aiofiles / cachetools / chardet / jinja2 / loguru / tiktoken / regex / markupsafe / win32-setctime（代码无引用）',
  'pdfplumber / pdfminer.six / pypdfium2 / pypdf（pdf 技能已移出打包白名单）',
]

// ------------------------------------------------------------------ helpers ---

function log(message) {
  process.stdout.write(`${message}\n`)
}

function human(bytes) {
  if (bytes > 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`
  if (bytes > 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024).toFixed(0)} KB`
}

function rmrf(target) {
  fs.rmSync(target, { recursive: true, force: true })
}

function copyTree(src, dest, { excludeNames = new Set(), excludeRel = new Set(), label = '' } = {}) {
  if (!fs.existsSync(src)) throw new Error(`缺少源目录：${src}`)
  let files = 0
  let bytes = 0
  fs.cpSync(src, dest, {
    recursive: true,
    dereference: false,
    force: true,
    filter: source => {
      const rel = path.relative(src, source)
      if (!rel) return true
      const parts = rel.split(path.sep)
      if (parts.some(part => excludeNames.has(part))) return false
      const posix = parts.join('/')
      if (excludeRel.has(posix)) return false
      for (const excluded of excludeRel) {
        if (posix.startsWith(`${excluded}/`)) return false
      }
      return true
    },
  })
  const walk = dir => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) walk(full)
      else if (entry.isFile()) { files += 1; bytes += fs.statSync(full).size }
    }
  }
  walk(dest)
  if (label) log(`  · ${label}: ${files} 文件 / ${human(bytes)}`)
  return { files, bytes }
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: 'inherit', shell: false, ...options })
  if (result.error) throw result.error
  if (result.status !== 0) throw new Error(`命令失败（exit=${result.status}）：${command} ${args.join(' ')}`)
}

function inventory(root) {
  let files = 0
  let bytes = 0
  const stack = [root]
  while (stack.length) {
    const dir = stack.pop()
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) stack.push(full)
      else if (entry.isFile()) { files += 1; bytes += fs.statSync(full).size }
    }
  }
  return { files, bytes }
}

// 打包白名单：只把这里列出的技能拷进安装包，与运行时的技能启用状态无关。
const SKILL_ALLOWLIST = path.join(PACKAGING, 'skills.allowlist.txt')

function readSkillAllowlist() {
  if (!fs.existsSync(SKILL_ALLOWLIST)) {
    throw new Error(`缺少技能打包白名单：${SKILL_ALLOWLIST}（临时全量请用 --all-skills）`)
  }
  const names = []
  const text = fs.readFileSync(SKILL_ALLOWLIST, 'utf8').replace(/^\uFEFF/, '')
  for (const line of text.split(/\r?\n/)) {
    const value = line.split('#')[0].trim()
    if (!value) continue
    for (const item of value.split(/[,;]/)) {
      const name = item.trim()
      if (name && !names.some(existing => existing.toLowerCase() === name.toLowerCase())) names.push(name)
    }
  }
  if (!names.length) throw new Error(`技能打包白名单为空：${SKILL_ALLOWLIST}`)
  return { file: SKILL_ALLOWLIST, names }
}

/** 白名单可以写目录名，也可以写 SKILL.md 里的 name；这里把两者都取到。 */
function skillFrontmatterName(directory) {
  try {
    const text = fs.readFileSync(path.join(directory, 'SKILL.md'), 'utf8')
    const frontmatter = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text)
    const name = frontmatter ? /^name:\s*(.+?)\s*$/m.exec(frontmatter[1]) : null
    const cleaned = name ? name[1].replace(/^["']|["']$/g, '').trim() : ''
    return cleaned || directory.name
  } catch {
    return directory.name
  }
}

function selectSkills(skillsRoot, allowlist, { all = false } = {}) {
  const allowed = all ? null : new Set(allowlist.map(name => name.toLowerCase()))
  const packaged = []
  const skipped = []
  const matched = new Set()
  for (const entry of fs.readdirSync(skillsRoot, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (!entry.isDirectory()) continue
    const directory = path.join(skillsRoot, entry.name)
    // 与 agent_tools.py 一致：只认第一层且必须有 SKILL.md。
    if (!fs.existsSync(path.join(directory, 'SKILL.md'))) {
      skipped.push({ name: entry.name, reason: '没有 SKILL.md（运行期同样不扫描）' })
      continue
    }
    const name = skillFrontmatterName(directory)
    if (allowed && !allowed.has(name.toLowerCase()) && !allowed.has(entry.name.toLowerCase())) {
      skipped.push({ name, reason: '不在 skills.allowlist.txt' })
      continue
    }
    matched.add(name.toLowerCase())
    matched.add(entry.name.toLowerCase())
    packaged.push({ name, directory })
  }
  const missing = allowed ? allowlist.filter(name => !matched.has(name.toLowerCase())) : []
  return { packaged, skipped, missing }
}

function resolveSkillsDir() {
  const pathsProbe = spawnSync(REPO_PYTHON, ['-B', path.join(REPO, 'app', 'workspace_paths.py'), '--project-root', REPO], {
    encoding: 'utf8', windowsHide: true, timeout: 10000, env: PYTHON_BUILD_ENV,
  })
  if (pathsProbe.status !== 0) throw new Error('无法读取技能模板目录配置：' + (pathsProbe.stderr || 'path probe failed'))
  return JSON.parse(pathsProbe.stdout).skills_dir
}

// 插件分级表：运行期用它决定默认状态与设置页可见性，打包用它决定收录范围。
const PLUGIN_TIERS = path.join(REPO, 'app', 'plugins', 'tiers.json')
const PACKAGED_PLUGIN_TIERS = new Set(['system', 'system-external', 'extension'])

function readPluginTiers() {
  let data
  try {
    data = JSON.parse(fs.readFileSync(PLUGIN_TIERS, 'utf8'))
  } catch (error) {
    throw new Error(`无法读取插件分级表：${PLUGIN_TIERS}（${error.message}）`)
  }
  const tiers = data && typeof data === 'object' ? data.tiers : null
  if (!tiers || typeof tiers !== 'object') throw new Error(`插件分级表缺少 tiers：${PLUGIN_TIERS}`)
  const mapping = new Map()
  for (const [tier, ids] of Object.entries(tiers)) {
    if (!Array.isArray(ids)) continue
    for (const id of ids) {
      const key = String(id || '').trim().toLowerCase()
      if (key && !mapping.has(key)) mapping.set(key, tier)
    }
  }
  return { file: PLUGIN_TIERS, mapping }
}

function selectPlugins(pluginsRoot, tiers, { all = false } = {}) {
  const packaged = []
  const skipped = []
  const seen = new Set()
  if (!fs.existsSync(pluginsRoot)) throw new Error(`缺少插件目录：${pluginsRoot}`)
  for (const entry of fs.readdirSync(pluginsRoot, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (!entry.isDirectory() || entry.name.startsWith('.')) continue
    const tier = tiers.mapping.get(entry.name.toLowerCase()) || 'standalone'
    seen.add(entry.name.toLowerCase())
    if (!all && !PACKAGED_PLUGIN_TIERS.has(tier)) {
      skipped.push({ name: entry.name, tier, reason: '独立功能不随安装包分发' })
      continue
    }
    packaged.push({ name: entry.name, tier })
  }
  const missing = all ? [] : [...tiers.mapping.entries()]
    .filter(([id, tier]) => PACKAGED_PLUGIN_TIERS.has(tier) && !seen.has(id))
    .map(([id]) => id)
  return { packaged, skipped, missing }
}

// ------------------------------------------------------------------- stages ---

function buildFrontend() {
  const frontend = path.join(REPO, 'frontend')
  const pkgPath = path.join(frontend, 'package.json')
  if (!fs.existsSync(pkgPath)) {
    log('· 跳过前端构建：未找到 frontend/package.json')
    return
  }
  const scripts = JSON.parse(fs.readFileSync(pkgPath, 'utf8')).scripts || {}
  if (!scripts.build) {
    log('· 跳过前端构建：frontend 未定义 build 脚本')
    return
  }
  if (!fs.existsSync(path.join(frontend, 'node_modules'))) {
    log('· 跳过前端构建：frontend/node_modules 缺失（先执行 npm install）')
    return
  }
  const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm'
  log('· 构建前端（vite build → app/templates/dist）…')
  run(npm, ['run', 'build'], { cwd: frontend, shell: process.platform === 'win32' })
}

function installDependencies() {
  if (SKIP_DEPS) {
    log('· 跳过依赖安装（--skip-deps），复用现有 site-packages')
    return
  }
  if (!fs.existsSync(REPO_PYTHON)) throw new Error(`缺少仓库内置解释器：${REPO_PYTHON}`)
  fs.mkdirSync(SITE_PACKAGES, { recursive: true })
  const args = [
    '-B', '-m', 'pip', 'install',
    '--no-compile',
    '--disable-pip-version-check',
    '--no-warn-script-location',
    '--no-input',
    '--target', SITE_PACKAGES,
    '-r', REQUIREMENTS,
  ]
  if (process.env.SUGARAGENT_PIP_INDEX) args.push('--index-url', process.env.SUGARAGENT_PIP_INDEX)
  log('· 安装精简依赖到载荷（首次约 2–5 分钟）…')
  run(REPO_PYTHON, args, { cwd: REPO, windowsHide: true, env: PYTHON_BUILD_ENV })
}

/** 让打包后的运行时自带 pip，用户可随时补装 pandas / playwright 等可选依赖。 */
function bootstrapPip() {
  if (SKIP_DEPS) return
  const args = [
    '-B', '-m', 'pip', 'install',
    '--no-compile',
    '--disable-pip-version-check',
    '--no-warn-script-location',
    '--no-input',
    '--upgrade',
    '--target', SITE_PACKAGES,
    'pip', 'setuptools', 'wheel',
  ]
  if (process.env.SUGARAGENT_PIP_INDEX) args.push('--index-url', process.env.SUGARAGENT_PIP_INDEX)
  log('· 为载荷内置 pip/setuptools/wheel（支持后续补装依赖）…')
  run(REPO_PYTHON, args, { cwd: REPO, windowsHide: true, env: PYTHON_BUILD_ENV })
}

function optimizeRuntimeArchives() {
  log('· 合并飞书 SDK / PPT 图标，保留离线资源并减少安装落盘文件…')
  run(PAYLOAD_PYTHON, ['-B', path.join(HERE, 'archive-runtime.py'), '--payload', PAYLOAD], {
    cwd: PAYLOAD, windowsHide: true,
    env: PYTHON_BUILD_ENV,
  })
  // Loose caches in a reused dependency tree are cleaned after all probes.
  return assertRuntimeArchives(PAYLOAD, { checkBytecode: false })
}

function verifyImports() {
  const probe = [
    'import importlib, importlib.util, sys',
    'mods = ["fastapi","uvicorn","httpx","openai","PIL","jsonschema","mcp",',
    '        "openpyxl","psutil","dotenv","yaml","orjson",',
    '        "tokenizers","sse_starlette","multipart"]',
    'missing = []',
    'for name in mods:',
    '    try: importlib.import_module(name)',
    '    except Exception as exc: missing.append(f"{name}: {exc}")',
    'if not missing:',
    '    from acp.schema import HttpMcpServer, McpServerStdio',
    '    if importlib.util.find_spec("lark_oapi") is not None:',
    '        import lark_oapi',
    '        if ".zip" not in lark_oapi.__file__: missing.append("lark_oapi was not loaded from its archive")',
    '        from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody',
    'print("IMPORT_CLEAN" if not missing else "IMPORT_FAIL " + "; ".join(missing))',
  ].join('\n')
  const result = spawnSync(PAYLOAD_PYTHON, ['-B', '-c', probe], {
    cwd: PAYLOAD, encoding: 'utf8', windowsHide: true, env: PYTHON_BUILD_ENV,
  })
  const output = `${result.stdout || ''}${result.stderr || ''}`.trim()
  log(`· 依赖自检：${output.split(/\r?\n/).pop()}`)
  if (!output.includes('IMPORT_CLEAN')) {
    throw new Error(`载荷依赖自检未通过：\n${output}`)
  }
}

function ensureRipgrep() {
  const scripts = path.join(PAYLOAD, 'python', 'Scripts')
  const existing = path.join(scripts, 'rg.exe')
  fs.mkdirSync(scripts, { recursive: true })
  // 只保留 rg.exe：清掉任何从旧环境带进来的 shim
  for (const entry of fs.readdirSync(scripts)) {
    if (entry.toLowerCase() === 'rg.exe') continue
    fs.rmSync(path.join(scripts, entry), { recursive: true, force: true })
  }
  if (fs.existsSync(existing)) return existing
  const found = []
  const stack = [SITE_PACKAGES]
  while (stack.length) {
    const dir = stack.pop()
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) stack.push(full)
      else if (entry.name === 'rg.exe') found.push(full)
    }
  }
  if (found.length) {
    fs.copyFileSync(found[0], existing)
    log(`· 已把 ripgrep 复制到 Scripts：${path.relative(PAYLOAD, found[0])}`)
    return existing
  }
  // pip 26 with --target does not materialize wheel `data/scripts` entries
  // (ripgrep's RECORD points at ../../bin/rg.exe, which never appears), so pull
  // the wheel once and extract the binary ourselves.
  const staging = path.join(BUILD, '.ripgrep-wheel')
  const spec = fs.readFileSync(REQUIREMENTS, 'utf8').split(/\r?\n/)
    .map(line => line.trim())
    .find(line => /^ripgrep(\s|[<>=!~]|$)/i.test(line)) || 'ripgrep'
  try {
    rmrf(staging)
    fs.mkdirSync(staging, { recursive: true })
    run(REPO_PYTHON, ['-B', '-m', 'pip', 'download', '--no-deps',
      '--disable-pip-version-check', '--dest', staging, spec],
      { cwd: PACKAGING, windowsHide: true, env: PYTHON_BUILD_ENV })
    const extract = [
      'import glob, pathlib, sys, zipfile',
      'wheels = glob.glob(sys.argv[1] + "/*.whl")',
      'if not wheels: sys.exit("no ripgrep wheel")',
      'target = pathlib.Path(sys.argv[2])',
      'with zipfile.ZipFile(wheels[0]) as archive:',
      '    names = [n for n in archive.namelist() if n.lower().endswith("rg.exe")]',
      '    if not names: sys.exit("no rg.exe in wheel")',
      '    target.write_bytes(archive.read(names[0]))',
    ].join('\n')
    run(REPO_PYTHON, ['-B', '-c', extract, staging, existing],
      { cwd: PACKAGING, windowsHide: true, env: PYTHON_BUILD_ENV })
    log('· 已从 ripgrep wheel 提取 rg.exe 到 Scripts')
    return existing
  } catch (error) {
    log(`· 注意：无法提取 ripgrep（${error.message}）；文件搜索会退回 Python 扫描`)
    return null
  } finally {
    rmrf(staging)
  }
}

function dependenciesList() {
  const result = spawnSync(PAYLOAD_PYTHON, ['-B', '-m', 'pip', 'list', '--format=freeze'], {
    cwd: PAYLOAD, encoding: 'utf8', windowsHide: true, env: PYTHON_BUILD_ENV,
  })
  const stdout = String(result.stdout || '')
  if (result.status === 0 && stdout.trim()) {
    return stdout
      .split(/\r?\n/)
      .map(line => line.trim())
      .filter(line => line && !line.startsWith('#'))
  }
  // 回退：pip 不可用时直接读 dist-info 目录名
  const distInfo = new Set()
  const stack = [SITE_PACKAGES]
  while (stack.length) {
    const dir = stack.pop()
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue
      if (entry.name.endsWith('.dist-info')) {
        const [name, version] = entry.name.replace(/\.dist-info$/, '').split('-')
        if (name && version) distInfo.add(`${name}==${version}`)
      } else {
        stack.push(path.join(dir, entry.name))
      }
    }
  }
  return [...distInfo].sort()
}

// ---------------------------------------------------------------------- main ---

function main() {
  if (LIST_PLUGINS) {
    const selection = selectPlugins(path.join(REPO, 'plugins'), readPluginTiers(), { all: ALL_PLUGINS })
    log(`插件分级表：${path.relative(REPO, PLUGIN_TIERS)}`)
    log(`打包（${selection.packaged.length}）：${selection.packaged.map(item => `${item.name}(${item.tier})`).join(', ') || '无'}`)
    log(`跳过（${selection.skipped.length}）：${selection.skipped.map(item => `${item.name}[${item.reason}]`).join(', ') || '无'}`)
    if (selection.missing.length) log(`分级表里没找到（构建会失败）：${selection.missing.join(', ')}`)
    return
  }

  if (LIST_SKILLS) {
    const skillsRoot = resolveSkillsDir()
    const allowlist = readSkillAllowlist()
    const { packaged, skipped, missing } = selectSkills(skillsRoot, allowlist.names, { all: ALL_SKILLS })
    log(`技能模板目录：${skillsRoot}`)
    log(`打包白名单：${path.relative(REPO, allowlist.file)}（${ALL_SKILLS ? '本次忽略，全量打包' : `${allowlist.names.length} 项`}）`)
    log(`打包（${packaged.length}）：${packaged.map(skill => skill.name).join(', ') || '无'}`)
    log(`跳过（${skipped.length}）：${skipped.map(item => `${item.name}[${item.reason}]`).join(', ') || '无'}`)
    if (missing.length) log(`白名单里没找到（构建会失败）：${missing.join(', ')}`)
    return
  }

  log(`SugarAgent 桌面版载荷准备 v${PACKAGE_JSON.version}`)
  log(`  仓库：${REPO}`)
  log(`  输出：${PAYLOAD}`)

  if (BUILD_FRONTEND) buildFrontend()

  if (process.platform === 'win32') {
    log('· 校验并更新 Windows egress helper…')
    run('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
      path.join(REPO, 'scripts', 'build_egress_helper_windows.ps1'), '-IfNeeded'],
    { cwd: REPO, windowsHide: true })
  }

  let skillSummary = { mode: SKIP_SKILLS ? 'skipped' : ALL_SKILLS ? 'all' : 'active', packaged: [], skipped: [] }

  const distIndex = path.join(REPO, 'app', 'templates', 'dist', 'index.html')
  if (!fs.existsSync(distIndex)) {
    log('· 警告：app/templates/dist/index.html 不存在，界面会显示后端兜底页；请先构建前端')
  }

  const reuseEnvironment = SKIP_DEPS && fs.existsSync(SITE_PACKAGES)
  if (reuseEnvironment) {
    log('· 复用已有 site-packages（--skip-deps）：只刷新 app/plugins/技能模板')
    for (const stale of ['app', 'plugins', 'workspace-template']) rmrf(path.join(PAYLOAD, stale))
  } else {
    rmrf(PAYLOAD)
  }
  fs.mkdirSync(PAYLOAD, { recursive: true })

  log('· 拷贝 app/ ——')
  copyTree(path.join(REPO, 'app'), path.join(PAYLOAD, 'app'), {
    excludeNames: APP_EXCLUDE_NAMES,
    excludeRel: APP_EXCLUDE_REL,
    label: 'app',
  })

  const pluginSelection = selectPlugins(path.join(REPO, 'plugins'), readPluginTiers(), { all: ALL_PLUGINS })
  if (pluginSelection.missing.length) {
    throw new Error(`分级表里的插件目录不存在：${pluginSelection.missing.join(', ')}（检查 app/plugins/tiers.json）`)
  }
  fs.mkdirSync(path.join(PAYLOAD, 'plugins'), { recursive: true })
  log(`· 拷贝 plugins/（${ALL_PLUGINS ? '全部分级' : '排除独立功能'}）——`)
  let pluginFiles = 0
  let pluginBytes = 0
  for (const plugin of pluginSelection.packaged) {
    const stats = copyTree(path.join(REPO, 'plugins', plugin.name), path.join(PAYLOAD, 'plugins', plugin.name), {
      excludeNames: PLUGIN_EXCLUDE_NAMES,
    })
    pluginFiles += stats.files
    pluginBytes += stats.bytes
  }
  log(`  · 打包 ${pluginSelection.packaged.length} 个插件：${pluginSelection.packaged.map(item => `${item.name}(${item.tier})`).join(', ')}`)
  log(`  · 合计 ${pluginFiles} 文件 / ${human(pluginBytes)}`)
  if (pluginSelection.skipped.length) {
    log(`  · 跳过 ${pluginSelection.skipped.length} 个：${pluginSelection.skipped.map(item => item.name).join(', ')}`)
  }
  const pluginSummary = {
    mode: ALL_PLUGINS ? 'all' : 'tiers',
    tiersFile: path.relative(REPO, PLUGIN_TIERS).replace(/\\/g, '/'),
    packaged: pluginSelection.packaged.map(item => ({ id: item.name, tier: item.tier })),
    skipped: pluginSelection.skipped,
  }

  log('· 拷贝 Python 基座 ——')
  copyTree(path.join(REPO, 'python'), path.join(PAYLOAD, 'python'), {
    excludeRel: PYTHON_EXCLUDE_REL,
    label: 'python 基座',
  })
  fs.mkdirSync(path.join(PAYLOAD, 'python', 'Scripts'), { recursive: true })

  if (!SKIP_SKILLS) {
    const skills = resolveSkillsDir()
    if (fs.existsSync(skills)) {
      // 只带白名单里的技能：名单是打包侧的固定契约，不随界面上的启停变化。
      const allowlist = ALL_SKILLS ? null : readSkillAllowlist()
      const selection = selectSkills(skills, allowlist ? allowlist.names : [], { all: ALL_SKILLS })
      const destination = path.join(PAYLOAD, 'workspace-template', 'skills')
      let files = 0
      let bytes = 0
      log(`· 拷贝技能模板（${ALL_SKILLS ? '全部技能（忽略白名单）' : '仅白名单技能'}）——`)
      log(`  打包白名单：${allowlist ? path.relative(REPO, allowlist.file) : '（本次忽略）'}`)
      for (const skill of selection.packaged) {
        const stats = copyTree(skill.directory, path.join(destination, path.basename(skill.directory)), {
          excludeNames: new Set(['__pycache__', '.pytest_cache']),
        })
        files += stats.files
        bytes += stats.bytes
      }
      if (selection.missing.length) {
        throw new Error(
          `白名单里的技能未找到：${selection.missing.join(', ')}；请修正 ${path.relative(REPO, SKILL_ALLOWLIST)}`)
      }
      log(`  · 打包 ${selection.packaged.length} 个技能：${selection.packaged.map(skill => skill.name).join(', ') || '无'}`)
      log(`  · 合计 ${files} 文件 / ${human(bytes)}`)
      if (selection.skipped.length) {
        log(`  · 跳过 ${selection.skipped.length} 项：${selection.skipped.map(item => `${item.name}（${item.reason}）`).join('、')}`)
      }
      skillSummary = {
        mode: ALL_SKILLS ? 'all' : 'allowlist',
        allowlistFile: allowlist ? path.relative(REPO, allowlist.file).replace(/\\/g, '/') : null,
        packaged: selection.packaged.map(skill => skill.name),
        skipped: selection.skipped,
        missing: selection.missing,
      }
    } else {
      log(`· 跳过技能模板：${skills} 不存在`)
      skillSummary = { ...skillSummary, packaged: [], skipped: [{ name: skills, reason: '技能目录不存在' }] }
    }
  }

  installDependencies()
  bootstrapPip()
  const rg = ensureRipgrep()
  const runtimeArchives = optimizeRuntimeArchives()
  verifyImports()

  const pythonProbe = spawnSync(PAYLOAD_PYTHON, ['-B', '-c', 'import platform;print(platform.python_version())'], {
    encoding: 'utf8', windowsHide: true, env: PYTHON_BUILD_ENV,
  })
  const pythonVersion = String(pythonProbe.stdout || '').trim() || 'unknown'
  const dependencies = dependenciesList()
  const bytecodeCleanup = cleanupPyc(PAYLOAD)
  assertRuntimeArchives(PAYLOAD)
  log(`· 清理松散字节码：${bytecodeCleanup.files} 文件 / ${human(bytecodeCleanup.bytes)}`)
  const stats = inventory(PAYLOAD)
  const manifest = {
    schemaVersion: 1,
    product: PACKAGE_JSON.productName || 'SugarAgent',
    version: PACKAGE_JSON.version,
    builtAt: new Date().toISOString(),
    python: pythonVersion,
    dependencies,
    excludedDependencies: EXCLUDED_PACKAGES,
    skills: skillSummary,
    plugins: pluginSummary,
    ripgrep: rg ? path.relative(PAYLOAD, rg).replace(/\\/g, '/') : null,
    runtimeArchives,
    bytecodeCleanup,
    stats,
  }
  fs.writeFileSync(path.join(PAYLOAD, 'runtime-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')

  log('')
  log(`✔ 载荷完成：${stats.files} 文件 / ${human(stats.bytes)} / Python ${manifest.python}`)
  log(`  依赖 ${manifest.dependencies.length} 项（已排除：${EXCLUDED_PACKAGES.length} 类重依赖）`)
}

const invokedDirectly = Boolean(process.argv[1]) && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (invokedDirectly) main()

export { copyTree, readPluginTiers, readSkillAllowlist, selectPlugins, selectSkills, skillFrontmatterName }
