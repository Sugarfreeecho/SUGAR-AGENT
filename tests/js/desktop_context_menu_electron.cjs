'use strict'

// Run with Electron, using an offscreen window and a popup recorder.
const { app, BrowserWindow, Menu, clipboard, shell } = require('electron')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const root = path.resolve(__dirname, '../..')
const source = fs.readFileSync(path.join(root, 'packaging/electron/main.js'), 'utf8')
const nativeSource = source.match(/^function installNativeContextMenu\([\s\S]*?^}/m)[0]
const popups = []
const harness = vm.createContext({ BrowserWindow, clipboard, shell,
  Menu: { buildFromTemplate: items => ({ popup: options => popups.push({ items, options }) }) } })
vm.runInContext(nativeSource + '\nglobalThis.install = installNativeContextMenu', harness)
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))

app.whenReady().then(async () => {
  const win = new BrowserWindow({ show: false, webPreferences: { offscreen: true, contextIsolation: true } })
  const contents = win.webContents
  harness.install(contents)
  await win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(`
    <style>body{margin:0}button,textarea{display:block;width:200px;height:60px}</style>
    <button id="custom">Custom menu</button><textarea id="editable">Draft</textarea>
    <iframe style="height:120px" srcdoc="<textarea style='height:80px'>Settings</textarea>"></iframe>`))
  const menuSource = fs.readFileSync(path.join(root, 'frontend/src/app/modules/context-menus.js'), 'utf8')
  await contents.executeJavaScript(menuSource + `
    MyAgentContextMenu.bind(document.querySelector('#custom'),()=>[{label:'Custom action',action(){}}]);
    void 0;
  `)
  const rightClick = async (x, y) => {
    contents.sendInputEvent({ type: 'mouseDown', button: 'right', clickCount: 1, x, y })
    contents.sendInputEvent({ type: 'mouseUp', button: 'right', clickCount: 1, x, y })
    await delay(100)
  }
  await rightClick(30, 30)
  assert.equal(await contents.executeJavaScript("!!document.querySelector('.ui-context-menu')"), true)
  assert.equal(popups.length, 0, 'custom DOM menu must suppress the native fallback')
  await contents.executeJavaScript('MyAgentContextMenu.close(false)')
  await rightClick(30, 90)
  assert.equal(popups.length, 1, 'editable target must reach the native fallback')
  assert.ok(popups[0].items.some(item => item.role === 'paste'))
  assert.equal(popups[0].options.frame, contents.mainFrame)
  await rightClick(40, 150)
  assert.equal(popups.length, 2, 'settings frame must receive an editing menu')
  assert.notEqual(popups[1].options.frame, contents.mainFrame)
  win.destroy()
  console.log('Electron context menu smoke: custom suppression, native editing and iframe targeting passed')
  app.exit(0)
}).catch(error => { console.error(error.stack); app.exit(1) })
