'use strict'

const assert = require('node:assert/strict')
const http = require('node:http')
const os = require('node:os')
const path = require('node:path')
const { test } = require('node:test')
const { openWorkspacePath } = require('../../packaging/electron/local-paths')

async function harness(t, { status = 200, body, openError = '', closeResponse = false } = {}) {
  const target = path.join(os.tmpdir(), '中文 workspace', 'report & notes.txt')
  const calls = { requests: [], open: [], reveal: [], logs: [] }
  const server = http.createServer((request, response) => {
    calls.requests.push(new URL(request.url, 'http://localhost'))
    if (closeResponse) { response.destroy(); return }
    response.writeHead(status, { 'Content-Type': 'application/json' })
    response.end(typeof body === 'string' ? body : JSON.stringify(body || { ok: true, path: target, is_dir: false }))
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  t.after(() => new Promise(resolve => { server.close(resolve); server.closeAllConnections() }))
  const options = {
    baseUrl: `http://127.0.0.1:${server.address().port}`,
    shell: {
      openPath: async value => { calls.open.push(value); return openError },
      showItemInFolder: value => { calls.reveal.push(value) },
    },
    log: value => calls.logs.push(value),
  }
  return { target, calls, open: payload => openWorkspacePath(options, payload) }
}

test('desktop reveal validates against its active backend and opens the exact Unicode file once', async t => {
  const { calls, target, open } = await harness(t)
  const result = await open({ rel: '中文/report & notes.txt', directory: true, session_id: 'custom-session' })
  assert.equal(result.ok, true)
  assert.deepEqual(calls.reveal, [target])
  assert.equal(calls.open.length, 0)
  assert.equal(calls.requests[0].pathname, '/api/open-workspace-dir')
  assert.equal(calls.requests[0].searchParams.get('probe'), '1')
  assert.equal(calls.requests[0].searchParams.get('session_id'), 'custom-session')
  assert.equal(calls.requests[0].searchParams.get('rel'), '中文/report & notes.txt')
})

test('directories and default-app opens wait for the native result and retain draft workspace context', async t => {
  const folder = path.join(os.tmpdir(), 'project space')
  const directory = await harness(t, { body: { ok: true, path: folder, is_dir: true } })
  assert.equal((await directory.open({ rel: '.', directory: true, work_dir: folder })).ok, true)
  assert.deepEqual(directory.calls.open, [folder])
  assert.equal(directory.calls.requests[0].searchParams.get('work_dir'), folder)
  const file = await harness(t)
  assert.equal((await file.open({ rel: 'report.txt', directory: false })).ok, true)
  assert.deepEqual(file.calls.open, [file.target])
  assert.equal(file.calls.reveal.length, 0)
  const failure = await harness(t, { openError: 'Access denied by native shell' })
  assert.deepEqual(await failure.open({ rel: 'report.txt', directory: false }),
    { ok: false, error: 'Access denied by native shell' })
})

test('denied, malformed, interrupted, or non-absolute backend responses never launch system apps', async t => {
  for (const options of [
    { status: 403, body: { ok: false, error: 'outside allowed roots' } },
    { body: '{bad json' },
    { body: { ok: true, path: 'relative.txt', is_dir: false } },
    { body: { ok: true, path: os.tmpdir() } },
    { closeResponse: true },
  ]) {
    const { calls, open } = await harness(t, options)
    assert.equal((await open({ rel: 'report.txt', directory: true })).ok, false)
    assert.equal(calls.open.length + calls.reveal.length, 0)
  }
})

test('invalid IPC payloads cannot change the endpoint or reach the system shell', async t => {
  const { calls, open } = await harness(t)
  for (const payload of [null, {}, { rel: 'x', directory: 'true' },
    { rel: 'x', directory: true, session_id: {} }, { rel: 'x'.repeat(32769), directory: true }]) {
    assert.equal((await open(payload)).ok, false)
  }
  assert.equal(calls.requests.length, 0)
})
