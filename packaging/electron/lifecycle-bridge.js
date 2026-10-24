'use strict'

const { randomUUID, randomBytes } = require('node:crypto')
const { spawn, spawnSync } = require('node:child_process')
const http = require('node:http')
const path = require('node:path')

function jsonRequest(baseUrl, path, data, headers = {}) {
  return new Promise((resolve, reject) => {
    const target = new URL(path, baseUrl)
    const request = http.request(target, { method: data ? 'POST' : 'GET', timeout: 5000,
      headers: { 'Content-Type': 'application/json', ...headers } }, response => {
      let body = ''
      response.setEncoding('utf8')
      response.on('data', chunk => { body += chunk; if (body.length > 262144) request.destroy(new Error('Lifecycle response too large')) })
      response.on('end', () => {
        try {
          const value = JSON.parse(body)
          if (response.statusCode < 200 || response.statusCode >= 300 || !value.ok) throw new Error(value.error || 'Lifecycle request failed')
          resolve(value)
        } catch (error) { reject(error) }
      })
    })
    request.on('error', reject)
    request.on('timeout', () => request.destroy(new Error('Lifecycle request timed out')))
    request.end(data ? JSON.stringify(data) : undefined)
  })
}

function createLifecycleBridge({ python, script, baseUrl, onRestart, onStatus, onPrepare, log = () => {} }) {
  const supervisorId = randomUUID()
  const token = randomBytes(32).toString('hex')
  let identity = {}
  let watcher = null
  let latest = null
  let mailboxPath = ''
  const dispatched = new Set()
  return {
    newInstance(operation) {
      identity = { MYAGENT_LIFECYCLE_SUPERVISOR_ID: supervisorId, MYAGENT_LIFECYCLE_TOKEN: token,
        MYAGENT_LIFECYCLE_INSTANCE_ID: operation ? operation.expected_new_instance_id : randomUUID(),
        MYAGENT_LIFECYCLE_RESTART_ID: operation ? operation.restart_id : '',
        ...(mailboxPath ? { MYAGENT_LIFECYCLE_STATE_PATH: mailboxPath } : {}) }
      return identity.MYAGENT_LIFECYCLE_INSTANCE_ID
    },
    environment() { return { ...identity } },
    status() { return latest },
    start(environment) {
      if (watcher) return
      const probe = spawnSync(python, [script, 'state-path'], { env: environment, windowsHide: true,
        encoding: 'utf8', timeout: 10000 })
      if (probe.error || probe.status !== 0) throw new Error('Cannot locate protected lifecycle state')
      mailboxPath = JSON.parse(probe.stdout).state_path
      if (typeof mailboxPath !== 'string' || !path.isAbsolute(mailboxPath)) throw new Error('Invalid lifecycle state path')
      identity.MYAGENT_LIFECYCLE_STATE_PATH = mailboxPath
      const child = spawn(python, [script, 'watch', '--parent-pid', String(process.pid), '--base-url', baseUrl()], {
        env: { ...environment, ...identity }, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'],
      })
      watcher = child
      child.stdin.on('error', error => log(`Lifecycle handoff failed: ${error.message}`))
      let buffer = ''
      child.stdout.setEncoding('utf8')
      child.stdout.on('data', chunk => {
        buffer += chunk
        if (buffer.length > 1048576) { child.kill(); return }
        let end
        while ((end = buffer.indexOf('\n')) !== -1) {
          const line = buffer.slice(0, end)
          buffer = buffer.slice(end + 1)
          try {
            const event = JSON.parse(line)
            if (!event.operation || event.operation.supervisor_id !== supervisorId) continue
            latest = event.operation
            if (event.type === 'prepare') {
              const accepted = onPrepare && onPrepare(event.operation) === true
              child.stdin.write(JSON.stringify({ restart_id: event.operation.restart_id,
                ...(accepted ? { ack_prepare:true } : { error:'目标后端实例无法接管' }) }) + '\n')
              onStatus(event.operation)
            } else if (event.type === 'restart' && !dispatched.has(event.operation.restart_id)) {
              dispatched.add(event.operation.restart_id)
              onRestart(event.operation)
            }
            else if (event.type === 'status') onStatus(event.operation)
          } catch (error) { log(`Lifecycle bridge event failed: ${error.message}`) }
        }
      })
      child.stderr.on('data', chunk => log(`Lifecycle bridge: ${String(chunk).trim()}`))
      child.on('error', error => log(`Lifecycle bridge unavailable: ${error.message}`))
      child.on('close', () => { if (watcher === child) watcher = null })
    },
    fail(operation, message) {
      if (operation && watcher && watcher.stdin.writable) {
        watcher.stdin.write(JSON.stringify({ restart_id: operation.restart_id, error: message }) + '\n')
      }
    },
    async requestManual() {
      const status = await jsonRequest(baseUrl(), '/api/lifecycle/status')
      return jsonRequest(baseUrl(), '/api/lifecycle/restarts', { reason: '用户从桌面菜单请求重启服务' },
        { 'X-MyAgent-Lifecycle-UI': status.ui_token })
    },
    close() { if (watcher) watcher.kill(); watcher = null },
  }
}

module.exports = { createLifecycleBridge, jsonRequest }
