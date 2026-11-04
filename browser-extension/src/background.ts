import { RelayConnection } from './upstream/relayConnection';
import { loopbackUrl, ordinaryTab } from './shared.mjs';
import { controlResult } from './control.mjs';
import { applicationMethod } from './application-api.mjs';
import { readBrowserContext } from './browser-context';
import {createPresenceBridge} from './presence.mjs';
import {verifyPairing} from './connection.mjs';
import {noteFrame,streamTrace} from './stream-diagnostics.mjs';

type Connection = { baseUrl: string; token?: string; browserId?: string };
let connection: Connection = { baseUrl: 'http://127.0.0.1:8192' };
let appSocket: WebSocket | null = null;
let relay: RelayConnection | null = null;
let relaySocket: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
let heartbeatTimer: ReturnType<typeof setInterval> | undefined;
let handshakeTimer: ReturnType<typeof setTimeout> | undefined;
let socketEpoch=0,lastMessageAt=0;
let retry = 1000;
let paused = false;
let status = 'disconnected';
let statusError='',connectionRevision=0;
const generation=crypto.randomUUID();
const ports = new Set<chrome.runtime.Port>();
const presence=createPresenceBridge({readWindow:(id:number)=>chrome.windows.get(id),send:(message:any)=>{if(appSocket?.readyState===WebSocket.OPEN)appSocket.send(JSON.stringify(message));}});
const subscriptions = new Set<string>();
const knownTabs = new Set<number>();
const ownedDebuggerTabs = new Set<number>();
function saveOwnedDebuggerTabs() {
  void chrome.storage.session.set({ 'sugar.debuggerTabs': [...ownedDebuggerTabs] });
}
let subscriptionWaiter: { sessionId: string; resolve: (value: unknown) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> } | null = null;

function publish(message: unknown) {
  for (const port of ports) { try { port.postMessage(message); } catch { ports.delete(port); } }
}
function setStatus(value: string, error = '') {
  status = value;statusError=error;++connectionRevision;
  void chrome.storage.session.set({ 'sugar.status': { status, error, paused } });
  publish({ type: 'connection', status, error, paused, paired:!!connection.token,revision:connectionRevision,generation });
  void chrome.action.setBadgeText({ text: paused ? 'Ⅱ' : error ? '!' : '' });
}
function closeRelay() {
  const previous = relay;
  relay = null;
  relaySocket = null;
  knownTabs.clear();
  previous?.close('Connection changed');
}
function connectRelay(raw: string) {
  if (paused) return;
  const url = loopbackUrl(raw, ['ws:']);
  if (url.pathname !== '/extension') throw new Error('Invalid Playwright relay address');
  closeRelay();
  const socket = new WebSocket(url.href);
  relaySocket = socket;
  socket.onopen = async () => {
    if (relaySocket !== socket) { socket.close(); return; }
    relay = new RelayConnection(socket, readBrowserContext);
    relay.ontabattached = tabId => { ownedDebuggerTabs.add(tabId); saveOwnedDebuggerTabs(); };
    relay.ontabdetached = tabId => { ownedDebuggerTabs.delete(tabId); saveOwnedDebuggerTabs(); };
    relay.onclose = () => {
      if (relaySocket !== socket) return;
      relay = null;
      relaySocket = null;
      knownTabs.clear();
      publish({ type: 'browser', connected: false, paused });
      if (appSocket?.readyState === WebSocket.OPEN && !paused)
        appSocket.send(JSON.stringify({ type: 'relay.request' }));
    };
    const tabs = await chrome.tabs.query({});
    for (const tab of tabs.filter(ordinaryTab)) {
      if (tab.id !== undefined) { knownTabs.add(tab.id); relay.attachTab(tab); }
    }
    relay.didInitialize();
    publish({ type: 'browser', connected: true, paused: false });
  };
  socket.onerror = () => publish({ type: 'browser', connected: false, error: '浏览器桥接连接失败' });
}
function scheduleReconnect() {
  clearTimeout(reconnectTimer);
  if (!connection.token) return;
  reconnectTimer = setTimeout(() => void connectApp(), retry);
  retry = Math.min(retry * 2, 30000);
  void chrome.alarms.create('sugar-reconnect', { periodInMinutes: 0.5 });
}
async function connectApp() {
  clearTimeout(reconnectTimer);
  if (appSocket?.readyState === WebSocket.OPEN || appSocket?.readyState === WebSocket.CONNECTING) return;
  if (!connection.token) { setStatus('unpaired'); return; }
  const url = loopbackUrl(connection.baseUrl);
  url.protocol = 'ws:';
  url.pathname = '/api/browser/v1/ws';
  setStatus('connecting');
  const socket = new WebSocket(url.href);
  const paired=connection,epoch=++socketEpoch;
  appSocket = socket;
  lastMessageAt=Date.now();
  clearTimeout(handshakeTimer);
  handshakeTimer=setTimeout(()=>{if(appSocket===socket && status!=='connected')socket.close(4000,'Handshake timeout');},10000);
  socket.onopen = () => {if(appSocket===socket && connection===paired)socket.send(JSON.stringify({ type: 'hello', token: paired.token, browser_id: paired.browserId }));};
  socket.onmessage = event => {
    if(appSocket!==socket || connection!==paired)return;
    lastMessageAt=Date.now();
    try {
      const message = JSON.parse(event.data);
      if(message.type==='session.event')noteFrame('background_received',message.session_id,message.event);
      if (message.type === 'ready') {
        clearTimeout(handshakeTimer);
        retry = 1000;
        setStatus('connected');
        presence.ready();
        if (message.relay_url) connectRelay(message.relay_url);
        for (const sessionId of subscriptions) socket.send(JSON.stringify({ type: 'subscribe', session_id: sessionId }));
      } else if (message.type === 'relay') {
        if (!paused && message.url) connectRelay(message.url);
      } else if (message.type === 'subscribed') {
        const waiter = subscriptionWaiter;
        if (waiter && waiter.sessionId === message.session_id) {
          clearTimeout(waiter.timer); waiter.resolve({ subscribed: true }); subscriptionWaiter = null;
        }
      } else if (message.type === 'error') {
        setStatus('error', message.message || '浏览器运行时暂时不可用');
      } else if (message.type === 'session.error') {
        if (subscriptionWaiter && (!message.session_id || subscriptionWaiter.sessionId === message.session_id)) {
          clearTimeout(subscriptionWaiter.timer); subscriptionWaiter.reject(new Error(message.message || '无法打开此会话')); subscriptionWaiter = null;
        }
        publish(message);
      } else publish(message);
    } catch { setStatus('error', '连接消息格式不正确'); }
  };
  socket.onclose = async event => {
    if (appSocket !== socket) return;
    appSocket = null;
    clearTimeout(handshakeTimer);
    if (subscriptionWaiter) {
      clearTimeout(subscriptionWaiter.timer); subscriptionWaiter.reject(new Error('连接已断开，请等待重连')); subscriptionWaiter = null;
    }
    closeRelay();
    if(!connection.token){setStatus('unpaired');return;}
    setStatus('disconnected','连接暂时中断，配对已保留，正在自动重连');
    if(event.code===4401){
      const verified=await verifyPairing(paired);
      if(epoch!==socketEpoch || connection!==paired || appSocket)return;
      if(verified==='invalid'){
        setStatus('auth-required','配对授权已被撤销或已到期，请重新配对');
        void chrome.alarms.clear('sugar-reconnect');return;
      }
    }else if(event.code===4403)setStatus('disconnected','浏览器连接插件暂不可用，恢复后将自动重连');
    scheduleReconnect();
  };
  socket.onerror = () => {if(appSocket===socket)setStatus('disconnected', '无法连接本机 SugarAgent，配对已保留');};
}
async function backend(path: string, body?: unknown, target=connection) {
  const url = loopbackUrl(target.baseUrl);
  url.pathname = path;
  const response = await fetch(url.href, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', ...(target.token ? { Authorization: `Bearer ${target.token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (response.status === 404 && path === '/api/browser/v1/messages') throw new Error('请重启 SugarAgent 后端以启用自动页面关联，然后重试。');
  if (!response.ok) throw new Error(typeof data.error === 'string' ? data.error : data.error?.message || data.detail || `HTTP ${response.status}`);
  return controlResult(data);
}
async function capture(tabId?: number, selectionOnly = false) {
  const tab = tabId === undefined ? (await chrome.tabs.query({ active: true, lastFocusedWindow: true }))[0] : await chrome.tabs.get(tabId);
  if (!tab?.id || !ordinaryTab(tab)) throw new Error('这个页面不能附加');
  const result = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: () => ({
    title: document.title, url: location.href, selection: getSelection()?.toString() || '',
    text: ((document.querySelector('main,article,[role=main]') || document.body) as HTMLElement)?.innerText || '',
  }) });
  const value = result[0]?.result;
  if (!value) throw new Error('无法读取页面');
  return { title: value.title, url: value.url, text: (selectionOnly ? value.selection : value.text).slice(0, 32000), tabId: tab.id, capturedAt: new Date().toISOString() };
}
async function message(request: any) {
  await initializing;
  switch (request.type) {
    case 'state': return { status, error:statusError, paused, paired:!!connection.token, baseUrl: connection.baseUrl, browserId: connection.browserId, extensionId: chrome.runtime.id,revision:connectionRevision,generation };
    case 'stream-diagnostics': return {version:chrome.runtime.getManifest().version,status,generation,subscriptions:[...subscriptions],port_count:ports.size,last_socket_message_at:lastMessageAt,frames:streamTrace(request.sessionId)};
    case 'pair': {
      const base = loopbackUrl(request.baseUrl || connection.baseUrl);
      const result = await backend('/api/browser/v1/claim', { code: request.code, name: request.name || 'SugarAgent 浏览器', extension_id: chrome.runtime.id }, {baseUrl:base.origin});
      connection = { baseUrl: base.origin, token: result.token, browserId: result.browser_id };
      await chrome.storage.local.set({ 'sugar.connection': connection });
      await chrome.alarms.create('sugar-reconnect', { periodInMinutes: 0.5 });
      const previous=appSocket;appSocket=null;previous?.close();
      closeRelay();
      await connectApp();
      return { paired: true };
    }
    case 'rpc': return backend('/api/control/v1/rpc', { method: request.method, params: request.params || {}, idempotency_key: request.key || crypto.randomUUID() });
    case 'api': {
      applicationMethod(request.path, request.body);
      return backend(request.path, request.body);
    }
    case 'subscribe': {
      subscriptions.clear();
      if (request.sessionId) subscriptions.add(request.sessionId);
      if (appSocket?.readyState !== WebSocket.OPEN) throw new Error('会话连接尚未就绪');
      if (subscriptionWaiter) { clearTimeout(subscriptionWaiter.timer); subscriptionWaiter.reject(new Error('会话订阅已切换')); }
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => { subscriptionWaiter = null; reject(new Error('会话订阅确认超时')); }, 10000);
        subscriptionWaiter = { sessionId: request.sessionId || '', resolve, reject, timer };
        appSocket!.send(JSON.stringify({ type: 'subscribe', session_id: request.sessionId || '' }));
      });
    }
    case 'tabs': return (await chrome.tabs.query({})).filter(ordinaryTab).map(tab => ({ id: tab.id, title: tab.title, url: tab.url }));
    case 'capture': return capture(request.tabId, request.selectionOnly);
    case 'page-context': return readBrowserContext(request.options || {});
    case 'pause': {
      paused = !!request.paused;
      await chrome.storage.session.set({ 'sugar.paused': paused });
      if (paused) closeRelay();
      if (appSocket?.readyState === WebSocket.OPEN) appSocket.send(JSON.stringify({ type: 'pause', paused }));
      setStatus(status); return { paused };
    }
    case 'reconnect': await connectApp(); return { connecting: true };
    case 'disconnect': {
      connection = {baseUrl:connection.baseUrl};++socketEpoch;
      await chrome.storage.local.remove('sugar.connection');
      await chrome.alarms.clear('sugar-reconnect');
      closeRelay(); appSocket?.close(); appSocket = null;
      clearTimeout(reconnectTimer); setStatus('unpaired'); return { disconnected: true };
    }
    default: throw new Error('Unknown extension request');
  }
}
chrome.runtime.onMessage.addListener((request, sender, respond) => {
  if (sender.id !== chrome.runtime.id || !sender.url?.startsWith(chrome.runtime.getURL(''))) return false;
  void message(request).then(result => respond({ ok: true, result }), error => respond({ ok: false, error: error.message }));
  return true;
});
chrome.runtime.onConnect.addListener(port => {
  if (port.sender?.id !== chrome.runtime.id || !port.sender?.url?.startsWith(chrome.runtime.getURL(''))) { port.disconnect(); return; }
  ports.add(port);
  const sidepanel=port.name==='sugaragent-sidepanel' && new URL(port.sender.url!).pathname==='/sidepanel.html';
  if(sidepanel){presence.attach(port);port.onMessage.addListener(message=>{void presence.report(port,message);});}
  void initializing.then(()=>port.postMessage({ type: 'connection', status,error:statusError, paused, paired:!!connection.token,revision:connectionRevision,generation })).catch(()=>{});
  port.onDisconnect.addListener(() => {ports.delete(port);if(sidepanel)presence.detach(port);});
});
chrome.windows.onFocusChanged.addListener(id=>presence.focusChanged(id));
chrome.tabs.onCreated.addListener(tab => {
  if (!relay || !ordinaryTab(tab) || tab.id === undefined) return;
  knownTabs.add(tab.id);
  if (!tab.openerTabId || !relay.attachedTabs.has(tab.openerTabId)) relay.attachTab(tab);
});
chrome.tabs.onUpdated.addListener((tabId, _change, tab) => {
  if (relay && ordinaryTab(tab) && !knownTabs.has(tabId)) { knownTabs.add(tabId); relay.attachTab(tab); }
});
chrome.tabs.onRemoved.addListener(tabId => knownTabs.delete(tabId));
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === 'sugar-reconnect') void initializing.then(connectApp); });
chrome.runtime.onInstalled.addListener(() => {
  void chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: 'sugar-page', title: '将网页附加到 SugarAgent', contexts: ['page'] });
    chrome.contextMenus.create({ id: 'sugar-selection', title: '将选区附加到 SugarAgent', contexts: ['selection'] });
  });
});
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!tab?.windowId || !tab.id) return;
  void chrome.sidePanel.open({ windowId: tab.windowId });
  void capture(tab.id, info.menuItemId === 'sugar-selection').then(value => {
    void chrome.storage.session.set({ 'sugar.pendingContext': value });
    publish({ type: 'context', value });
  });
});
chrome.commands.onCommand.addListener(() => {
  void chrome.windows.getLastFocused().then(async window => { if (window.id !== undefined) await chrome.sidePanel.open({ windowId: window.id }); });
});
async function initialize() {
  await chrome.storage.local.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' });
  const local = await chrome.storage.local.get('sugar.connection');
  if (local['sugar.connection']) connection = local['sugar.connection'];
  // Chrome can retain this extension's debugger sessions after forcibly
  // evicting its worker. Reclaim only tabs recorded by our own relay before
  // establishing a fresh protocol generation; another debugger is untouched.
  const previous = (await chrome.storage.session.get('sugar.debuggerTabs'))['sugar.debuggerTabs'];
  if (Array.isArray(previous)) await Promise.allSettled(previous.filter(Number.isInteger).map(tabId => chrome.debugger.detach({ tabId })));
  await chrome.storage.session.remove('sugar.debuggerTabs');
  if (connection.token) await chrome.alarms.create('sugar-reconnect', { periodInMinutes: 0.5 });
  paused = !!(await chrome.storage.session.get('sugar.paused'))['sugar.paused'];
  await connectApp();
  heartbeatTimer = setInterval(() => {
    if(appSocket?.readyState===WebSocket.OPEN && Date.now()-lastMessageAt>65000){appSocket.close(4000,'Heartbeat timeout');return;}
    if (appSocket?.readyState === WebSocket.OPEN) appSocket.send(JSON.stringify({ type: 'ping' }));
    if (relaySocket?.readyState === WebSocket.OPEN) relaySocket.send(JSON.stringify({ method: 'sugaragent.ping' }));
  }, 20000);
}
const initializing=initialize().catch(error => setStatus('error', error.message));
