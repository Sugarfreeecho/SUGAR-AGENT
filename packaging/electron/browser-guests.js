'use strict'

const { randomUUID } = require('node:crypto')

/** Main-process ownership and isolation for the sidebar's browser guests. */
function createBrowserGuests({ session, hostUrl, maxPartitions = 64, closeTimeoutMs = 5000 }) {
  const partitions = new Map()
  const leases = new Map()
  function isHost(url) {
    const host = new URL(hostUrl())
    return url.port === host.port && (url.hostname === host.hostname || ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))
  }
  function allowed(value) {
    try {
      const url = new URL(value)
      return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password && !isHost(url)
    } catch { return false }
  }
  function configure(partition) {
    const storage = session.fromPartition(partition)
    storage.setPermissionRequestHandler((_contents, _permission, callback) => callback(false))
    storage.setPermissionCheckHandler(() => false)
    storage.setDevicePermissionHandler(() => false)
    storage.setDisplayMediaRequestHandler((_request, callback) => callback({}))
    storage.on('will-download', event => event.preventDefault())
    storage.webRequest.onBeforeRequest((details, callback) => {
      try {
        const url = new URL(details.url)
        const network = ['http:', 'https:', 'ws:', 'wss:'].includes(url.protocol)
        callback({ cancel: network ? !!url.username || !!url.password || isHost(url) : !['about:', 'data:', 'blob:'].includes(url.protocol) })
      } catch { callback({ cancel: true }) }
    })
  }
  async function release(owner, id) {
    const lease = leases.get(id)
    if (!lease) return
    if (lease.owner !== owner) throw new Error('Browser guest belongs to another window')
    leases.delete(id)
    if (lease.guest && !lease.guest.isDestroyed()) {
      let timer, onDestroyed
      try {
        await new Promise((resolve, reject) => {
          onDestroyed = resolve
          lease.guest.once('destroyed', onDestroyed)
          timer = setTimeout(() => reject(new Error('Browser page did not close within the cleanup budget')), closeTimeoutMs)
          lease.guest.close({ waitForBeforeUnload: false })
        })
      } finally {
        clearTimeout(timer)
        lease.guest.removeListener('destroyed', onDestroyed)
      }
    }
  }
  return {
    allowed,
    acquire(owner, workspace) {
      if (typeof workspace !== 'string' || !workspace || workspace.length > 4096) throw new Error('Invalid browser workspace')
      const key = process.platform === 'win32' ? workspace.replaceAll('\\', '/').toLowerCase() : workspace
      let partition = partitions.get(key)
      if (!partition) {
        if (partitions.size >= maxPartitions) throw new Error('浏览器已达到工作区数量上限，请重启桌面应用后再打开新工作区')
        partition = 'sugaragent-browser-' + randomUUID()
        configure(partition); partitions.set(key, partition)
      }
      const lease = randomUUID()
      leases.set(lease, { owner, partition, attached: false, guest: null })
      return { lease, partition }
    },
    release,
    bind(window) {
      const owner = window.webContents
      owner.on('will-attach-webview', (event, preferences, params) => {
        const id = typeof params.src === 'string' && params.src.startsWith('about:blank#') ? params.src.slice(12) : ''
        const lease = leases.get(id)
        if (!lease || lease.owner !== owner || lease.attached || lease.partition !== params.partition) { event.preventDefault(); return }
        lease.attached = true
        for (const key of Object.keys(preferences)) if (key !== 'disablePopups') delete preferences[key]
        Object.assign(preferences, { partition: lease.partition, nodeIntegration: false, nodeIntegrationInWorker: false,
          nodeIntegrationInSubFrames: false, contextIsolation: true, sandbox: true, webSecurity: true,
          allowRunningInsecureContent: false, webviewTag: false, plugins: false, navigateOnDragDrop: false,
          disableDialogs: true, devTools: false })
        params.httpreferrer = ''
      })
      owner.on('did-attach-webview', (_event, guest) => {
        let leaseId
        guest.once('dom-ready', () => {
          const url = guest.getURL()
          const id = url.startsWith('about:blank#') ? url.slice(12) : ''
          const lease = leases.get(id)
          if (!lease || lease.owner !== owner || lease.guest) { guest.close({ waitForBeforeUnload: false }); return }
          leaseId = id; lease.guest = guest
          guest.once('destroyed', () => leases.delete(id))
        })
        guest.setWindowOpenHandler(({ url, postBody }) => {
          if (leaseId && leases.get(leaseId)?.guest === guest && !owner.isDestroyed() && !postBody && allowed(url)) {
            owner.send('sugaragent:browser-open-requested', { lease: leaseId, url: new URL(url).href })
          }
          return { action: 'deny' }
        })
        guest.on('will-frame-navigate', event => { if (event.isMainFrame && !allowed(event.url)) event.preventDefault() })
        guest.on('will-redirect', (event, url, _inPlace, mainFrame) => { if (mainFrame && !allowed(url)) event.preventDefault() })
        guest.on('will-attach-webview', event => event.preventDefault())
        guest.on('login', (event, _details, _auth, callback) => { event.preventDefault(); callback() })
      })
      const releaseAll = () => {
        for (const [id, lease] of leases) if (lease.owner === owner) void release(owner, id).catch(error => console.warn('Browser cleanup failed', error))
      }
      owner.on('did-start-navigation', (_event, _url, inPlace, mainFrame) => { if (mainFrame && !inPlace) releaseAll() })
      owner.on('render-process-gone', releaseAll)
      owner.once('destroyed', releaseAll)
    },
  }
}

module.exports = { createBrowserGuests }
