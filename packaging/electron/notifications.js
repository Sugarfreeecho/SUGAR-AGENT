'use strict'

const http = require('node:http')
const { randomBytes } = require('node:crypto')

const escapeXml = value => value.replace(/[&<>"']/g, ch => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;',
}[ch]))

const PLUGIN_ID = /^[a-z0-9][a-z0-9._-]{0,127}$/
const SETTINGS_SECTION = /^(?:general|models|skills|plugins|hooks|mcp|usage|security|schedules|env|paths|plugin:[a-z0-9][a-z0-9._-]{0,127}:[a-z0-9][a-z0-9._-]{0,127})$/

/** Keep an untrusted notification target within the two supported shapes. */
function normalizeTarget(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  if (value.kind === 'plugin' && PLUGIN_ID.test(value.plugin_id || '')) {
    const target = { kind: 'plugin', plugin_id: value.plugin_id }
    if (PLUGIN_ID.test(value.page_id || '')) target.page_id = value.page_id
    return target
  }
  if (value.kind === 'settings' && SETTINGS_SECTION.test(value.section || '')) {
    return { kind: 'settings', section: value.section }
  }
  return null
}

function activationUri({ session = '', target = null }) {
  const params = new URLSearchParams()
  if (session) params.set('session', session)
  if (target?.kind === 'plugin') {
    params.set('plugin', target.plugin_id)
    if (target.page_id) params.set('page', target.page_id)
  } else if (target?.kind === 'settings') {
    params.set('section', target.section)
  }
  const query = params.toString()
  return 'sugaragent-desktop://open-ui' + (query ? `?${query}` : '')
}

/** Backend-owned notifications must survive a hidden or destroyed renderer. */
async function createNotificationBridge({ Notification, icon, activate, log, platform = process.platform }) {
  const token = randomBytes(32).toString('hex')
  const notifications = new Set()

  function show({ title, message, session_id = '', target = null }) {
    return new Promise(resolve => {
      let notification, timer, settled = false
      const finish = ok => {
        if (settled) return
        settled = true
        clearTimeout(timer)
        resolve(ok)
      }
      try {
        if (!Notification.isSupported()) { finish(false); return }
        const session = /^[A-Za-z0-9][A-Za-z0-9-]{0,63}$/.test(session_id) ? session_id : ''
        const activationTarget = normalizeTarget(target)
        const options = { title, body: message, icon }
        if (platform === 'win32') {
          // Protocol activation keeps Action Center clicks working after the
          // notification object or the app has gone away.
          const uri = activationUri({ session, target: activationTarget })
          options.toastXml = `<toast activationType="protocol" launch="${escapeXml(uri)}"><visual>`
            + `<binding template="ToastGeneric"><text>${escapeXml(title)}</text>`
            + `<text>${escapeXml(message)}</text></binding></visual></toast>`
        }
        notification = new Notification(options)
        notifications.add(notification)
        notification.once('show', () => { log('桌面通知已发送'); finish(true) })
        notification.once('failed', (_event, error) => {
          log(`桌面通知发送失败：${error}`)
          notifications.delete(notification)
          finish(false)
        })
        notification.on('close', event => {
          if (event?.reason !== 'timedOut') notifications.delete(notification)
          finish(false)
        })
        if (platform !== 'win32') {
          notification.once('click', () => {
            notifications.delete(notification)
            const activation = { session }
            if (activationTarget) activation.target = activationTarget
            void activate(activation).catch(error => log(`桌面通知激活失败：${error.message}`))
          })
        }
        timer = setTimeout(() => {
          log('桌面通知发送超时')
          notifications.delete(notification)
          finish(false)
          try { notification.close() } catch (error) { log(`桌面通知关闭失败：${error.message}`) }
        }, 5000)
        notification.show()
      } catch (error) {
        if (notification) notifications.delete(notification)
        log(`桌面通知发送失败：${error.message}`)
        finish(false)
      }
    })
  }

  const server = http.createServer((request, response) => {
    const reply = status => {
      if (response.writableEnded || response.destroyed) return
      response.writeHead(status)
      response.end()
    }
    if (request.method !== 'POST' || request.url !== '/notify') { reply(404); request.resume(); return }
    if (request.headers.authorization !== `Bearer ${token}`) { reply(403); request.resume(); return }
    const chunks = []
    let size = 0
    request.on('data', chunk => {
      size += chunk.length
      if (size <= 16384) chunks.push(chunk)
    })
    request.on('error', () => { if (!response.writableEnded) reply(400) })
    request.on('end', async () => {
      if (response.writableEnded) return
      if (size > 16384) { reply(413); return }
      let payload
      try { payload = JSON.parse(Buffer.concat(chunks).toString('utf8')) }
      catch { reply(400); return }
      if (!payload || typeof payload.title !== 'string' || typeof payload.message !== 'string'
          || !payload.title.trim() || payload.title.length > 256 || payload.message.length > 4096
          || (payload.session_id !== undefined && typeof payload.session_id !== 'string')
          || (payload.target !== undefined && payload.target !== null
            && (typeof payload.target !== 'object' || Array.isArray(payload.target)))) {
        reply(400); return
      }
      reply(await show(payload) ? 200 : 503)
    })
  })
  server.requestTimeout = 10000
  server.headersTimeout = 10000
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', resolve)
  })
  server.on('error', error => log(`桌面通知通道异常：${error.message}`))
  return {
    port: server.address().port,
    token,
    close() {
      for (const notification of notifications) {
        try { notification.close() } catch (error) { log(`桌面通知关闭失败：${error.message}`) }
      }
      notifications.clear()
      server.close()
      server.closeAllConnections()
    },
  }
}

module.exports = { createNotificationBridge }
