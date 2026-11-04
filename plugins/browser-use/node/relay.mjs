import http from 'node:http';
import { randomBytes, timingSafeEqual } from 'node:crypto';
import { createRequire } from 'node:module';
import { ExtensionProtocolV2 } from './upstream/cdpRelayV2.ts';

const require = createRequire(import.meta.url);
const { wsServer: WebSocketServer } = require('playwright-core/lib/utilsBundle');

export class BrowserRelay {
  constructor({ token, allowedOrigin, onChange = () => {} }) {
    if (!token || !allowedOrigin) throw new Error('Relay authentication is required');
    this.token = token;
    this.allowedOrigin = allowedOrigin;
    this.onChange = onChange;
    this.extension = null;
    this.cdp = null;
    this.initialized = false;
    this.generation = 0;
    this.callbacks = new Map();
    this.nextId = 0;
    this.quietFocus = 0;
    this.cdpSecret = randomBytes(32).toString('hex');
    this.server = http.createServer((_req, res) => { res.writeHead(404); res.end(); });
    this.wss = new WebSocketServer({ noServer: true, maxPayload: 32 * 1024 * 1024 });
    this.server.on('upgrade', (req, socket, head) => {
      const url = new URL(req.url, 'http://127.0.0.1');
      const isExtension = url.pathname === '/extension';
      const valid = isExtension
        ? this.equal(url.searchParams.get('token') || '', this.token) && req.headers.origin === this.allowedOrigin
        : url.pathname === `/cdp/${this.cdpSecret}` && !req.headers.origin;
      if (!valid || (isExtension ? this.extension : this.cdp)) {
        socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');
        return;
      }
      this.wss.handleUpgrade(req, socket, head, ws => isExtension ? this.acceptExtension(ws) : this.acceptCDP(ws));
    });
  }
  equal(a, b) {
    const aa = Buffer.from(a), bb = Buffer.from(b);
    return aa.length === bb.length && timingSafeEqual(aa, bb);
  }
  async start() {
    await new Promise((resolve, reject) => {
      this.server.once('error', reject);
      this.server.listen(0, '127.0.0.1', resolve);
    });
    this.port = this.server.address().port;
    return this.status();
  }
  status() {
    return { port: this.port, connected: !!this.extension, initialized: this.initialized, generation: this.generation };
  }
  cdpEndpoint() { return `ws://127.0.0.1:${this.port}/cdp/${this.cdpSecret}`; }
  async withoutFocus(callback) {
    this.quietFocus++;
    try { return await callback(); } finally { this.quietFocus--; }
  }
  async browserContext(options = {}) {
    try { return await this.sendExtension('sugaragent.browserContext', [options]); }
    catch(error) { if(error.message.includes('sugaragent.browserContext'))throw new Error('Browser context requires SugarAgent extension 0.4.0; reload the extension');throw error; }
  }
  acceptExtension(ws) {
    this.extension = ws;
    this.initialized = false;
    this.generation++;
    this.handler = new ExtensionProtocolV2((method, params) => this.sendExtension(method, params));
    ws.on('message', raw => {
      try {
        const message = JSON.parse(raw.toString());
        if (message.id !== undefined) {
          const pending = this.callbacks.get(message.id);
          if (!pending) return;
          this.callbacks.delete(message.id);
          clearTimeout(pending.timer);
          message.error ? pending.reject(new Error(String(message.error))) : pending.resolve(message.result);
        } else if (message.method === 'sugaragent.ping') {
          ws.send(JSON.stringify({ method: 'sugaragent.pong' }));
        } else {
          this.handler.handleExtensionEvent(message.method, message.params);
          if (message.method === 'extension.initialized') {
            this.initialized = true;
            this.onChange(this.status());
          }
        }
      } catch { ws.close(1003, 'Invalid relay message'); }
    });
    ws.on('close', () => {
      if (this.extension !== ws) return;
      this.extension = null;
      this.initialized = false;
      this.handler.onExtensionDisconnect('connection closed');
      for (const pending of this.callbacks.values()) {
        clearTimeout(pending.timer);
        pending.reject(new Error('Browser disconnected; operation outcome may be unknown'));
      }
      this.callbacks.clear();
      this.cdp?.close(1000, 'Browser disconnected');
      this.onChange(this.status());
    });
    ws.on('error', () => {});
    this.onChange(this.status());
  }
  sendExtension(method, params) {
    if (!this.extension || this.extension.readyState !== 1) throw new Error('Browser is not connected');
    const id = ++this.nextId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.callbacks.delete(id);
        reject(new Error('Browser command timed out; observe the page before retrying'));
      }, 45000);
      this.callbacks.set(id, { resolve, reject, timer });
      this.extension.send(JSON.stringify({ id, method, params }));
    });
  }
  acceptCDP(ws) {
    if (!this.initialized) { ws.close(1000, 'Browser not initialized'); return; }
    this.cdp = ws;
    const handler = this.handler;
    const identityBrowsers = new Set(), identityPages = new Map();
    let identitySeq = 0;
    const emit = message => { if (ws.readyState === 1) ws.send(JSON.stringify(message)); };
    handler.connectOverCDP(message => { if (ws.readyState === 1) ws.send(JSON.stringify(message)); });
    ws.on('message', async raw => {
      let message;
      try {
        message = JSON.parse(raw.toString());
        const { method, params, sessionId } = message;
        let result;
        // Chromium's extension debugger cannot attach to the browser target.
        // These logical CDP sessions support public Playwright target-identity
        // lookup without another debugger attachment or any page operation.
        if (method === 'Page.bringToFront' && this.quietFocus) {
          result = {};
        } else if (method === 'Target.attachToBrowserTarget' && !sessionId) {
          const id = 'sugar-identity-browser-' + ++identitySeq;
          identityBrowsers.add(id); result = {sessionId:id};
        } else if (identityBrowsers.has(sessionId) && method === 'Target.attachToTarget') {
          const info = handler.getTargetInfoById(params.targetId);
          if (!info) throw new Error('Browser tab has closed');
          const id = 'sugar-identity-page-' + ++identitySeq;
          identityPages.set(id,{targetId:params.targetId,parent:sessionId});
          emit({sessionId,method:'Target.attachedToTarget',params:{sessionId:id,targetInfo:info,waitingForDebugger:false}});
          result = {sessionId:id};
        } else if (identityBrowsers.has(sessionId) && method === 'Target.detachFromTarget') {
          const page = identityPages.get(params.sessionId);
          if (page?.parent === sessionId) { identityPages.delete(params.sessionId); emit({sessionId,method:'Target.detachedFromTarget',params:{sessionId:params.sessionId}}); }
          result = {};
        } else if (identityPages.has(sessionId) && method === 'Target.getTargetInfo') {
          const info = handler.getTargetInfoById(identityPages.get(sessionId).targetId);
          if (!info) throw new Error('Browser tab has closed');
          result = {targetInfo:info};
        } else if (identityBrowsers.has(sessionId) || identityPages.has(sessionId)) {
          throw new Error('This CDP session supports target identity reads only');
        } else if (method === 'Browser.getVersion') {
          result = { protocolVersion: '1.3', product: 'Chrome/SugarAgent-Playwright', userAgent: 'SugarAgent' };
        } else if (method === 'Browser.setDownloadBehavior') {
          result = {};
        } else {
          const handled = await handler.handleCDPCommand(method, params, sessionId);
          result = handled ? handled.result : await handler.forwardToExtension(method, params, sessionId);
        }
        if (ws.readyState === 1) ws.send(JSON.stringify({ id: message.id, sessionId: message.sessionId, result }));
      } catch (error) {
        if (message?.id !== undefined && ws.readyState === 1)
          ws.send(JSON.stringify({ id: message.id, sessionId: message.sessionId, error: { message: error.message } }));
      }
    });
    ws.on('close', () => {
      if (this.cdp !== ws) return;
      this.cdp = null;
      this.extension?.close(1000, 'Playwright connection disconnected');
    });
    ws.on('error', () => {});
  }
  disconnect() { this.extension?.close(1000, 'Browser control paused'); this.cdp?.close(); }
  async close() {
    for (const client of this.wss.clients) client.terminate();
    await new Promise(resolve => this.wss.close(resolve));
    await new Promise(resolve => this.server.close(resolve));
  }
}
