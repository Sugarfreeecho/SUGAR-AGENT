'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const { test } = require('node:test')

function cleanup(targets, packaged = true) {
  const removed = [], messages = []
  const code = fs.readFileSync(path.join(__dirname, '../../packaging/electron/desktop-shortcuts.js'), 'utf8')
  const context = vm.createContext({
    module: { exports: {} }, process: { platform: 'win32' },
    require: name => name === 'node:path' ? path : {
      existsSync: name => targets.has(name), unlinkSync: name => removed.push(name),
    },
  })
  vm.runInContext(code, context)
  context.module.exports.removeLegacyElectronShortcuts({
    app: { isPackaged: packaged, getPath: name => name === 'desktop' ? 'D:\\Desktop' : 'C:\\User\\AppData\\Roaming' },
    shell: { readShortcutLink: name => ({ target: targets.get(name) }) },
    execPath: 'D:\\SugarAgent\\SugarAgentRuntime.exe', log: message => messages.push(message),
  })
  return { removed, messages }
}

test('only legacy Electron links targeting this installed app are removed', () => {
  const desktop = 'D:\\Desktop\\Electron.lnk'
  const start = 'C:\\User\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Electron.lnk'
  const { removed } = cleanup(new Map([[desktop, 'D:\\SugarAgent\\SugarAgent.exe'],
    [start, 'd:\\sugaragent\\SugarAgentRuntime.exe']]))
  assert.deepEqual(removed, [desktop, start])
  assert.deepEqual(cleanup(new Map([[desktop, 'D:\\OtherApp\\electron.exe']])).removed, [])
})

test('source Electron launches and unreadable or relative links are preserved', () => {
  const desktop = 'D:\\Desktop\\Electron.lnk'
  assert.deepEqual(cleanup(new Map([[desktop, 'D:\\SugarAgent\\SugarAgentRuntime.exe']]), false).removed, [])
  assert.deepEqual(cleanup(new Map([[desktop, 'SugarAgentRuntime.exe']])).removed, [])
})
