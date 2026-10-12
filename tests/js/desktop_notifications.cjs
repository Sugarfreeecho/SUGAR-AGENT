'use strict'

const assert = require('node:assert/strict')
const http = require('node:http')
const { EventEmitter } = require('node:events')
const { test } = require('node:test')
const { createNotificationBridge } = require('../../packaging/electron/notifications')

async function harness(t, { supported = true, outcome = 'show', platform = 'win32' } = {}) {
  const calls = { notifications: [], logs: [], activations: [] }
  class Notification extends EventEmitter {
    static isSupported() { return supported }
    constructor(options) { super(); this.options = options; calls.notifications.push(this) }
    show() {
      setImmediate(() => this.emit(outcome, {}, 'Native delivery failed'))
    }
    close() { this.emit('close', {}) }
  }
  const bridge = await createNotificationBridge({
    Notification, icon: 'tray.ico', platform,
    log: value => calls.logs.push(value),
    activate: async value => { calls.activations.push(value) },
  })
  t.after(() => bridge.close())
  async function post(payload, { token = bridge.token, path = '/notify' } = {}) {
    const data = typeof payload === 'string' ? payload : JSON.stringify(payload)
    return new Promise((resolve, reject) => {
      const request = http.request({
        host: '127.0.0.1', port: bridge.port, path, method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      }, response => { response.resume(); response.on('end', () => resolve(response.statusCode)) })
      request.on('error', reject)
      request.end(data)
    })
  }
  return { calls, post, bridge }
}

test('backend request delivers a native toast without a renderer and preserves session activation', async t => {
  const { calls, post } = await harness(t)
  assert.equal(await post({ title: 'SugarAgent', message: '状态：已完成\n会话：测试 <A> & "B"', session_id: 'session-1' }), 200)
  const options = calls.notifications[0].options
  assert.match(options.body, /状态：已完成/)
  assert.match(options.toastXml, /sugaragent-desktop:\/\/open-ui\?session=session-1/)
  assert.match(options.toastXml, /测试 &lt;A&gt; &amp; &quot;B&quot;/)
  assert.ok(calls.logs.includes('桌面通知已发送'))
})

test('unauthenticated, oversized, and malformed requests cannot emit native notifications', async t => {
  const { calls, post } = await harness(t)
  const payload = { title: 'SugarAgent', message: 'Completed' }
  assert.equal(await post(payload, { token: 'wrong-token' }), 403)
  assert.equal(await post(payload, { path: '/other' }), 404)
  assert.equal(await post('{'), 400)
  assert.equal(await post({ ...payload, title: null }), 400)
  assert.equal(await post({ ...payload, session_id: {} }), 400)
  assert.equal(await post({ ...payload, message: 'x'.repeat(17000) }), 413)
  assert.equal(calls.notifications.length, 0)
})

test('native failure and unsupported platforms are reported to the backend for fallback', async t => {
  for (const options of [{ outcome: 'failed' }, { supported: false }]) {
    const { calls, post } = await harness(t, options)
    assert.equal(await post({ title: 'SugarAgent', message: 'Completed' }), 503)
    if (options.outcome) assert.ok(calls.logs.some(value => value.includes('Native delivery failed')))
  }
})

test('notification timeout reports failure and dismisses the pending toast', async t => {
  const { calls, post } = await harness(t, { outcome: 'pending' })
  assert.equal(await post({ title: 'SugarAgent', message: 'Completed' }), 503)
  assert.ok(calls.logs.includes('桌面通知发送超时'))
})

test('invalid session ids cannot inject toast XML; non-Windows clicks activate the desktop', async t => {
  const windows = await harness(t)
  await windows.post({ title: 'SugarAgent', message: 'Completed', session_id: 'bad" />' })
  assert.match(windows.calls.notifications[0].options.toastXml, /launch="sugaragent-desktop:\/\/open-ui"/)
  const other = await harness(t, { platform: 'linux' })
  await other.post({ title: 'SugarAgent', message: 'Completed', session_id: 'session-2' })
  assert.equal(other.calls.notifications[0].options.toastXml, undefined)
  other.calls.notifications[0].emit('click', {})
  assert.deepEqual(other.calls.activations, [{ session: 'session-2' }])
})
