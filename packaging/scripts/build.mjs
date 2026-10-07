#!/usr/bin/env node
'use strict'

/**
 * 一键构建：图标 → 运行时载荷 → electron-builder（可选只出目录版）
 *
 *   node scripts/build.mjs                  # 出 NSIS 安装包
 *   node scripts/build.mjs --dir            # 只出未打包目录（调试用）
 *   node scripts/build.mjs --skip-payload   # 复用现有载荷
 *   node scripts/build.mjs --build-frontend # 附带重新构建前端
 */

import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const PACKAGING = path.resolve(HERE, '..')
const REPO = path.resolve(PACKAGING, '..')
const REPO_PYTHON = path.join(REPO, 'python', 'python.exe')

const flags = new Set(process.argv.slice(2))
const DIR_ONLY = flags.has('--dir')
const SKIP_PAYLOAD = flags.has('--skip-payload')
const SKIP_ICONS = flags.has('--skip-icons')
const BUILD_FRONTEND = flags.has('--build-frontend')

function run(command, args, options = {}) {
  process.stdout.write(`\n$ ${command} ${args.join(' ')}\n`)
  const result = spawnSync(command, args, { stdio: 'inherit', ...options })
  if (result.error) throw result.error
  if (result.status !== 0) throw new Error(`命令失败（exit=${result.status}）`)
}

function human(bytes) {
  if (bytes > 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`
}

function main() {
  if (!SKIP_ICONS) {
    run(REPO_PYTHON, [path.join(HERE, 'make-icons.py')], { cwd: PACKAGING })
  }

  if (!SKIP_PAYLOAD) {
    const args = [path.join(HERE, 'prepare-payload.mjs')]
    if (BUILD_FRONTEND) args.push('--build-frontend')
    run(process.execPath, args, { cwd: PACKAGING })
  }

  // electron-builder 模板的中文补丁（幂等；npm install 覆盖模板后会自动重打）
  run(process.execPath, [path.join(HERE, 'patch-nsis.mjs')], { cwd: PACKAGING })

  // Node 20+ 不允许直接 spawn .cmd 垫片，统一用 node 执行 CLI 入口
  const builder = path.join(PACKAGING, 'node_modules', 'electron-builder', 'cli.js')
  if (!fs.existsSync(builder)) throw new Error('缺少 electron-builder，请先执行 npm install')

  const args = ['--config', 'electron-builder.config.cjs', '--win', '--x64', '--publish', 'never']
  if (DIR_ONLY) args.push('--dir')
  run(process.execPath, [builder, ...args], {
    cwd: PACKAGING,
    env: { ...process.env, CSC_IDENTITY_AUTO_DISCOVERY: 'false' },
  })

  const dist = path.join(PACKAGING, 'build', 'dist')
  const unpacked = path.join(dist, 'win-unpacked')
  console.log('\n构建产物：')
  if (fs.existsSync(unpacked)) {
    let files = 0
    let bytes = 0
    const stack = [unpacked]
    while (stack.length) {
      const dir = stack.pop()
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) stack.push(full)
        else if (entry.isFile()) { files += 1; bytes += fs.statSync(full).size }
      }
    }
    console.log(`  目录版：${unpacked}（${files} 文件 / ${human(bytes)}）`)
  }
  if (fs.existsSync(dist)) {
    for (const entry of fs.readdirSync(dist, { withFileTypes: true })) {
      if (entry.isFile() && entry.name.endsWith('.exe')) {
        const size = fs.statSync(path.join(dist, entry.name)).size
        console.log(`  安装包：${path.join(dist, entry.name)}（${human(size)}）`)
      }
    }
  }
}

main()
