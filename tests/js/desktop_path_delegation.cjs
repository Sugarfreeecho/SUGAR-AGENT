'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const { test } = require('node:test')
const source = fs.readFileSync(path.resolve(__dirname, '../../frontend/src/app/config.js'), 'utf8')
  .replace(/^export\s+/gm, '')

test('desktop opens use IPC with session/draft context, without issuing the background opener request', async () => {
  const calls = []
  const context = vm.createContext({ URLSearchParams, currentSessionId: 'session-B',
    sugarAgentDesktop: { openLocalPath: async payload => { calls.push(payload); return { ok: true } } },
    fetch: () => { throw new Error('desktop must not invoke the background opener') },
    __WORK_DIR__: 'D:/workspace',
  })
  vm.runInContext(source, context)
  await context.openWorkspaceLocalPath('folder/文件.txt', true)
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0])), { session_id: 'session-B', rel: 'folder/文件.txt', directory: true })
  context.currentSessionId = ''
  await context.openWorkspaceLocalPath('same.txt')
  assert.equal(calls[1].work_dir, 'D:/workspace')
  await context.openWorkspaceLocalPath('D:/other/project', true, { context: {} })
  assert.equal(calls[2].session_id, undefined)
  assert.equal(calls[2].work_dir, undefined)
})

test('browser and older desktop clients retain session-aware HTTP opens and propagate failure', async () => {
  const calls = []
  const context = vm.createContext({ URLSearchParams, currentSessionId: 'session-C',
    sugarAgentDesktop: {},
    fetch: async (url, options) => {
      calls.push({ url, options })
      return { ok: false, json: async () => ({ ok: true, error: 'permission denied' }) }
    },
  })
  vm.runInContext(source, context)
  const signal = {}
  const result = await context.openWorkspaceLocalPath('dir/a.txt', true, { signal })
  assert.equal(result.ok, false)
  assert.equal(result.error, 'permission denied')
  assert.equal(calls[0].url, '/api/open-workspace-dir?session_id=session-C&rel=dir%2Fa.txt')
  assert.equal(calls[0].options.signal, signal)
  await context.openWorkspaceLocalPath('dir/a.txt', false)
  assert.match(calls[1].url, /^\/api\/open-workspace-file\?/)
})
