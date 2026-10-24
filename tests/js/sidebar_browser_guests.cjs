'use strict'
const assert = require('node:assert/strict')
const { EventEmitter } = require('node:events')
const { test } = require('node:test')
const { createBrowserGuests } = require('../../packaging/electron/browser-guests')

function harness(options = {}) {
  const sessions = new Map()
  const session = { fromPartition(key) {
    if (!sessions.has(key)) sessions.set(key, Object.assign(new EventEmitter(), {
      setPermissionRequestHandler(fn) { this.permission = fn }, setPermissionCheckHandler(fn) { this.check = fn },
      setDevicePermissionHandler(fn) { this.device = fn }, setDisplayMediaRequestHandler(fn) { this.display = fn },
      webRequest: { onBeforeRequest(fn) { this.request = fn } },
    }))
    return sessions.get(key)
  } }
  const guests = createBrowserGuests({ session, hostUrl: () => 'http://127.0.0.1:8192', ...options })
  const owner = Object.assign(new EventEmitter(), { isDestroyed: () => false, send: (...args) => { owner.sent = args } })
  guests.bind({ webContents: owner })
  return { guests, owner, sessions }
}

test('workspace partitions are shared deliberately and guest network policy blocks application aliases', () => {
  const { guests, owner, sessions } = harness()
  const a = guests.acquire(owner, 'workspace-a'), b = guests.acquire(owner, 'workspace-a')
  assert.equal(a.partition, b.partition)
  assert.notEqual(a.partition, guests.acquire(owner, 'workspace-b').partition)
  const storage = sessions.get(a.partition)
  assert.equal(storage.check(), false)
  for (const url of ['http://localhost:8192/api/env', 'http://127.0.0.1:8192/', 'ws://[::1]:8192/', 'file:///C:/secret']) {
    let result
    storage.webRequest.request({ url }, value => { result = value })
    assert.equal(result.cancel, true, url)
  }
  assert.equal(guests.allowed('http://127.0.0.1:5173/'), true)
  assert.equal(guests.allowed('https://user:secret@example.com'), false)
  assert.equal(guests.allowed('javascript:alert(1)'), false)
})

test('only the reserved owner can attach one isolated guest and release it', async () => {
  const { guests, owner } = harness()
  const reservation = guests.acquire(owner, 'workspace')
  const params = { src: 'about:blank#' + reservation.lease, partition: reservation.partition }
  const preferences = { preload: 'evil.js', nodeIntegration: true, webSecurity: false }
  let rejected = false
  const event = { preventDefault() { rejected = true } }
  owner.emit('will-attach-webview', event, preferences, params)
  assert.equal(rejected, false)
  assert.equal(preferences.preload, undefined)
  assert.equal(preferences.nodeIntegration, false)
  assert.equal(preferences.sandbox, true)
  assert.equal(preferences.contextIsolation, true)
  assert.equal(preferences.webSecurity, true)
  owner.emit('will-attach-webview', event, {}, params)
  assert.equal(rejected, true, 'a lease cannot be attached twice')
  const guest = Object.assign(new EventEmitter(), { getURL: () => params.src, isDestroyed: () => false,
    setWindowOpenHandler(fn) { this.popup = fn }, close() { this.closed = true; this.emit('destroyed') } })
  owner.emit('did-attach-webview', {}, guest); guest.emit('dom-ready')
  assert.deepEqual(guest.popup({ url: 'https://example.com/page' }), { action: 'deny' })
  assert.equal(owner.sent[0], 'sugaragent:browser-open-requested')
  assert.equal(owner.sent[1].lease, reservation.lease)
  await assert.rejects(guests.release({}, reservation.lease), /another window/)
  await guests.release(owner, reservation.lease)
  assert.equal(guest.closed, true)
})

test('releasing a reservation before attachment closes its late guest', async () => {
  const { guests, owner } = harness()
  const reservation = guests.acquire(owner, 'workspace')
  await guests.release(owner, reservation.lease)
  const guest = Object.assign(new EventEmitter(), { getURL: () => 'about:blank#' + reservation.lease,
    setWindowOpenHandler() {}, close() { this.closed = true } })
  owner.emit('did-attach-webview', {}, guest); guest.emit('dom-ready')
  assert.equal(guest.closed, true)
})

test('workspace partition capacity preserves existing workspace state', () => {
  const { guests, owner } = harness({ maxPartitions: 2 })
  const first = guests.acquire(owner, 'first')
  guests.acquire(owner, 'second')
  assert.throws(() => guests.acquire(owner, 'third'), /工作区数量上限/)
  assert.equal(guests.acquire(owner, 'first').partition, first.partition)
})

test('an unresponsive guest cannot leave release IPC waiting indefinitely', async () => {
  const { guests, owner } = harness({ closeTimeoutMs: 15 })
  const reservation = guests.acquire(owner, 'workspace')
  owner.emit('will-attach-webview', { preventDefault() {} }, {}, {
    src: 'about:blank#' + reservation.lease, partition: reservation.partition })
  const guest = Object.assign(new EventEmitter(), { getURL: () => 'about:blank#' + reservation.lease,
    isDestroyed: () => false, setWindowOpenHandler() {}, close() {} })
  owner.emit('did-attach-webview', {}, guest); guest.emit('dom-ready')
  await assert.rejects(guests.release(owner, reservation.lease), /cleanup budget/)
  assert.equal(guest.listenerCount('destroyed'), 1, 'only the ownership cleanup listener remains')
  await guests.release(owner, reservation.lease)
})
