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
    'import importlib, sys',
    'mods = ["fastapi","uvicorn","httpx","openai","PIL","jsonschema","mcp","lark_oapi",',
    '        "openpyxl","pdfplumber","psutil","dotenv","yaml","orjson","aiohttp","loguru",',
    '        "tokenizers","tiktoken","sse_starlette","multipart","jinja2","chardet","cachetools"]',
    'missing = []',
    'for name in mods:',
    '    try: importlib.import_module(name)',
    '    except Exception as exc: missing.append(f"{name}: {exc}")',
    'if not missing:',
    '    import lark_oapi',
    '    if ".zip" not in lark_oapi.__file__: missing.append("lark_oapi was not loaded from its archive")',
    '    from lark_oapi.api.im.v1 import ReplyMessageRequest, ReplyMessageRequestBody',
    '    from lark_oapi.ws import Client',
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
  log('· 注意：未在依赖中找到 rg.exe，文件搜索工具可能降级')
  return null
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

  log('· 拷贝 plugins/ ——')
  copyTree(path.join(REPO, 'plugins'), path.join(PAYLOAD, 'plugins'), {
    excludeNames: PLUGIN_EXCLUDE_NAMES,
    label: 'plugins',
  })

  log('· 拷贝 Python 基座 ——')
  copyTree(path.join(REPO, 'python'), path.join(PAYLOAD, 'python'), {
    excludeRel: PYTHON_EXCLUDE_REL,
    label: 'python 基座',
  })
  fs.mkdirSync(path.join(PAYLOAD, 'python', 'Scripts'), { recursive: true })

  if (!SKIP_SKILLS) {
    const pathsProbe = spawnSync(REPO_PYTHON, ['-B', path.join(REPO, 'app', 'workspace_paths.py'), '--project-root', REPO], {
      encoding: 'utf8', windowsHide: true, timeout: 10000, env: PYTHON_BUILD_ENV,
    })
    if (pathsProbe.status !== 0) throw new Error('无法读取技能模板目录配置：' + (pathsProbe.stderr || 'path probe failed'))
    const skills = JSON.parse(pathsProbe.stdout).skills_dir
    if (fs.existsSync(skills)) {
      log('· 拷贝技能模板 ——')
      copyTree(skills, path.join(PAYLOAD, 'workspace-template', 'skills'), {
        excludeNames: new Set(['__pycache__', '.pytest_cache']),
        label: 'skills 模板',
      })
    } else {
      log(`· 跳过技能模板：${skills} 不存在`)
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

main()
