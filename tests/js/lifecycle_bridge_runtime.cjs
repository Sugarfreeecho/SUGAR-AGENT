const assert = require('node:assert/strict')
const { EventEmitter } = require('node:events')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const { test } = require('node:test')

test('supervisor bridge validates identity, deduplicates dispatch, and keeps status through backend replacement', () => {
  const launches = [], restarts = [], statuses = [], input = []
  const child = new EventEmitter()
  child.stdout = Object.assign(new EventEmitter(), { setEncoding() {} })
  child.stderr = new EventEmitter()
  child.stdin = Object.assign(new EventEmitter(), { writable: true, write: value => input.push(JSON.parse(value)) })
  child.kill = () => { child.killed = true }
  let nextId = 0
  const context = vm.createContext({ module: { exports: {} }, Buffer, URL, process: { pid: 123 },
    require: name => ({ 'node:crypto': { randomUUID: () => 'id-' + (++nextId), randomBytes: () => Buffer.from('secret') },
      'node:child_process': { spawn: (...args) => { launches.push(args); return child },
        spawnSync: () => ({ status:0, stdout:JSON.stringify({state_path:path.resolve(__dirname,'state.sqlite3')}) }) },
        'node:http': {}, 'node:path':path })[name] })
  vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../../packaging/electron/lifecycle-bridge.js'), 'utf8'), context)
  const bridge = context.module.exports.createLifecycleBridge({ python:'python', script:'watch.py', baseUrl:()=> 'http://127.0.0.1:1234',
    onRestart: value => restarts.push(value), onStatus: value => statuses.push(value), onPrepare:()=>true })
  const first = bridge.newInstance()
  bridge.start({ PATH:'runtime' })
  bridge.start({ PATH:'runtime' })
  assert.equal(launches.length, 1)
  const supervisor = bridge.environment().MYAGENT_LIFECYCLE_SUPERVISOR_ID
  const operation = { restart_id:'r', supervisor_id:supervisor, expected_new_instance_id:'replacement', phase:'starting' }
  child.stdout.emit('data', JSON.stringify({type:'prepare',operation})+'\n')
  assert.equal(input[0].ack_prepare,true)
  child.stdout.emit('data', JSON.stringify({ type:'restart', operation:{ ...operation, supervisor_id:'foreign' } }) + '\n')
  const event = JSON.stringify({ type:'restart', operation }) + '\n'
  child.stdout.emit('data', event.slice(0,20)); child.stdout.emit('data',event.slice(20))
  child.stdout.emit('data',event)
  assert.equal(restarts.length, 1)
  assert.equal(bridge.newInstance(operation), 'replacement')
  assert.equal(bridge.environment().MYAGENT_LIFECYCLE_STATE_PATH, path.resolve(__dirname,'state.sqlite3'))
  assert.notEqual(first, bridge.environment().MYAGENT_LIFECYCLE_INSTANCE_ID)
  child.stdout.emit('data',JSON.stringify({type:'status',operation:{...operation,phase:'completed'}})+'\n')
  assert.equal(statuses.at(-1).phase, 'completed')
  bridge.fail(operation, 'startup failed')
  assert.equal(input.at(-1).restart_id, 'r')
  bridge.close()
  assert.equal(child.killed, true)
})
