#!/usr/bin/env node
'use strict'

/**
 * 载荷自检：用打包后的 Python 真实启动一次后端并等待健康检查通过。
 *
 *   node scripts/smoke-payload.mjs [--port 8192] [--timeout 180]
 *
 * 会使用独立的工作目录/日志目录（packaging/build/smoke），不会碰真实工作区；
 * 结束后按进程树结束子进程，退出码 0 表示自检通过。
 */

import fs from 'node:fs'
import path from 'node:path'
import http from 'node:http'
import { spawn, spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const PACKAGING = path.resolve(HERE, '..')
const PAYLOAD = path.join(PACKAGING, 'build', 'payload')
const PYTHON = path.join(PAYLOAD, 'python', 'python.exe')
const ENTRY = path.join(PAYLOAD, 'app', 'main.py')
const WORK = path.join(PACKAGING, 'build', 'smoke')

const argv = process.argv.slice(2)
function arg(name, fallback) {
  const index = argv.indexOf(`--${name}`)
  return index >= 0 && argv[index + 1] ? argv[index + 1] : fallback
}

const PORT = Number(arg('port', process.env.SUGARAGENT_SMOKE_PORT || 8192))
const TIMEOUT_MS = Number(arg('timeout', 180)) * 1000

function probe() {
  return new Promise(resolve => {
    const request = http.get({ host: '127.0.0.1', port: PORT, path: '/api/runtime-status', timeout: 2000 }, response => {
      let body = ''
      response.on('data', chunk => { body += chunk })
      response.on('end', () => resolve(response.statusCode >= 200 && response.statusCode < 500 ? (body.slice(0, 200) || 'ok') : false))
    })
    request.on('timeout', () => { request.destroy(); resolve(false) })
    request.on('error', () => resolve(false))
  })
}

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

async function main() {
  for (const dir of [WORK, path.join(WORK, 'workspace'), path.join(WORK, 'logs')]) {
    fs.mkdirSync(dir, { recursive: true })
  }
  const logPath = path.join(WORK, 'smoke-backend.log')
  const logStream = fs.createWriteStream(logPath, { flags: 'w' })

  console.log(`载荷自检：${ENTRY}（端口 ${PORT}）`)
  const SENSITIVE = /^(OPENAI_|ANTHROPIC_|DEEPSEEK_|DASHSCOPE|MOONSHOT|ZHIPU|QWEN|ARK_|VOLC|EXECUTOR_|MYAGENT_|LOCAL_LLM|LLM_|TAVILY_|BRAVE_|JINA_|SEARXNG_|FEISHU_|LARK_|SENTRY_|SSL_BYPASS|WEB_SEARCH|WEB_DOWNLOAD|GITHUB_TOKEN|GH_TOKEN|HF_TOKEN|HUGGING|AWS_|AZURE_|GOOGLE_|PYTHONPATH|PYTHONHOME|PYTHONSTARTUP|PYTHONUSERBASE)/i
  const baseEnv = Object.fromEntries(
    Object.entries(process.env).filter(([key, value]) => value !== undefined && !SENSITIVE.test(key)),
  )
  const child = spawn(PYTHON, [ENTRY], {
    cwd: PAYLOAD,
    env: {
      ...baseEnv,
      OPEN_BROWSER: '0',
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1',
      MYAGENT_SERVER_PORT: String(PORT),
      WORK_DIR: path.join(WORK, 'workspace'),
      LOG_DIR: path.join(WORK, 'logs'),
      SKILLS_DIR: path.join(WORK, 'workspace', 'skills'),
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  child.stdout.pipe(logStream, { end: false })
  child.stderr.pipe(logStream, { end: false })

  let exited = false
  child.on('exit', code => { exited = true; console.log(`后端提前退出：code=${code}`) })

  const deadline = Date.now() + TIMEOUT_MS
  let ready = false
  while (Date.now() < deadline) {
    if (exited) break
    const result = await probe()
    if (result) { ready = true; console.log(`✔ 健康检查通过：${result}`); break }
    await sleep(700)
  }

  try {
    if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true })
    else child.kill('SIGTERM')
  } catch { /* ignore */ }
  logStream.end()

  if (!ready) {
    console.error(`✘ 自检失败：${TIMEOUT_MS / 1000} 秒内未通过健康检查。日志：${logPath}`)
    const tail = fs.existsSync(logPath) ? fs.readFileSync(logPath, 'utf8').split(/\r?\n/).slice(-25).join('\n') : '(无日志)'
    console.error(tail)
    process.exitCode = 1
    return
  }
  console.log(`日志：${logPath}`)
}

main()
