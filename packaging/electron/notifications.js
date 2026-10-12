'use strict'

const http = require('node:http')
const { randomBytes } = require('node:crypto')

const escapeXml = value => value.replace(/[&<>"']/g, ch => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;',
}[ch]))

/** Backend-owned notifications must survive a hidden or destroyed renderer. */
async function createNotificationBridge({ Notification, icon, activate, log, platform = process.platform }) {
  const token = randomBytes(32).toString('hex')
  const notifications = new Set()

  function show({ title, message, session_id = '' }) {
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
        const options = { title, body: message, icon }
        if (platform === 'win32') {
          // Protocol activation keeps Action Center clicks working after the
          // notification object or the app has gone away.
          const uri = 'sugaragent-desktop://open-ui' + (session ? `?session=${session}` : '')
          options.toastXml = `<toast activationType="protocol" launch="${uri}"><visual>`
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
            void activate({ session }).catch(error => log(`桌面通知激活失败：${error.message}`))
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
          || (payload.session_id !== undefined && typeof payload.session_id !== 'string')) {
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
