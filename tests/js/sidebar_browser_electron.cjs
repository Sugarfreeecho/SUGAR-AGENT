'use strict'
// Real webviews in a hidden window exercise the production carrier and preload.
const { app, BrowserWindow, ipcMain, session, webContents } = require('electron')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const http = require('node:http')
const path = require('node:path')
const { createBrowserGuests } = require('../../packaging/electron/browser-guests')
const root = path.resolve(__dirname, '../..')
const servers = []
let win
let passed = false
const watchdog = setTimeout(() => { console.error('Sidebar browser smoke timed out'); app.exit(1) }, 40000)
const serve = async handler => {
  const server = http.createServer(handler); servers.push(server)
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  return `http://127.0.0.1:${server.address().port}`
}
async function wait(expression) {
  const until = Date.now() + 12000
  while (Date.now() < until) {
    if (await win.webContents.executeJavaScript(`(()=>{try{return (${expression})}catch{return false}})()`)) return
    await new Promise(resolve => setTimeout(resolve, 60))
  }
  throw new Error('Timed out: ' + expression)
}
app.whenReady().then(async () => {
  let secretRequests = 0
  const host = await serve((request, response) => {
    if (request.url === '/secret') secretRequests++
    response.setHeader('Content-Type', 'text/html; charset=utf-8')
    response.end('<!doctype html><html lang="en"><body></body></html>')
  })
  const target = await serve((request, response) => {
    response.setHeader('Content-Type', 'text/html; charset=utf-8')
    response.end(`<html><head><title>${request.url === '/two' ? 'Second page' : 'First page'}</title></head><body>Browser fixture</body></html>`)
  })
  const guests = createBrowserGuests({ session, hostUrl: () => host })
  win = new BrowserWindow({ show: false, webPreferences: { webviewTag: true, contextIsolation: true,
    nodeIntegration: false, preload: path.join(root, 'packaging/electron/preload.js') } })
  guests.bind(win)
  win.webContents.on('console-message', (_event, ...details) => console.log('Renderer:', ...details))
  ipcMain.handle('sugaragent:browser-acquire', (event, workspace) => {
    assert.equal(event.sender, win.webContents); assert.equal(event.senderFrame, event.sender.mainFrame)
    return guests.acquire(event.sender, workspace)
  })
  ipcMain.handle('sugaragent:browser-release', (event, lease) => guests.release(event.sender, lease))
  await win.loadURL(host)
  const source = fs.readFileSync(path.join(root, 'frontend/src/app/modules/dock/embedder/browser-page.js'), 'utf8')
  await win.webContents.executeJavaScript(`
    function dockPageText(zh,en){return en}
    ${source}
    dockRightOpenBrowser=function(url){window.requestedPopup=url};
    window.subject=new DockBrowserPage(${JSON.stringify(target + '/one')},'fixture-workspace',()=>{});
    document.body.appendChild(subject.element);
    void 0;
  `)
  await wait("subject.frame?.getURL().endsWith('/one') && subject.title==='First page'")
  assert.equal(await win.webContents.executeJavaScript("subject.frame.executeJavaScript('typeof require')"), 'undefined')
  await win.webContents.executeJavaScript(`subject.load(${JSON.stringify(target + '/two')})`)
  await wait("subject.title==='Second page' && subject.frame.canGoBack()")
  await win.webContents.executeJavaScript('subject.navigateHistory(-1)')
  await wait("subject.frame.getURL().endsWith('/one')")
  await win.webContents.executeJavaScript(`subject.frame.executeJavaScript(${JSON.stringify(`fetch('${host}/secret').catch(()=>{})`)})`)
  assert.equal(secretRequests, 0, 'guest requests cannot reach the application Host')
  await win.webContents.executeJavaScript(`subject.frame.executeJavaScript("void window.open('/popup')",true)`)
  await wait(`window.requestedPopup===${JSON.stringify(target + '/popup')}`)
  assert.equal(BrowserWindow.getAllWindows().length, 1, 'popups become sidebar requests, not native windows')
  await win.webContents.executeJavaScript('subject.dispose()')
  await wait("document.querySelectorAll('webview').length===0")
  assert.equal(webContents.getAllWebContents().some(contents => contents.getType() === 'webview'), false)
  passed = true
  console.log('sidebar browser Electron navigation, isolation, popup and cleanup checks passed')
}).catch(error => { console.error(error); process.exitCode = 1 }).finally(() => {
  fs.mkdirSync(path.join(root, '.analysis'), { recursive: true })
  fs.writeFileSync(path.join(root, '.analysis/sidebar-browser-electron.json'), JSON.stringify({ passed, timestamp: new Date().toISOString() }))
  clearTimeout(watchdog); win?.destroy(); servers.forEach(server => server.close()); app.exit(process.exitCode || 0)
})
