import assert from 'node:assert/strict';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { createRequire } from 'node:module';
import { mkdtemp, rm, writeFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, sep, basename } from 'node:path';

const root = resolve(import.meta.dirname, '../..');
const require = createRequire(resolve(root, 'plugins/browser-use/node/package.json'));
const { chromium } = require('playwright');
const { wsServer: WebSocketServer } = require('playwright-core/lib/utilsBundle');
const work = await mkdtemp(resolve(tmpdir(), 'sugar-host-smoke-'));
const runtime = spawn(resolve(root, 'python/python.exe'), ['-u', resolve(import.meta.dirname, 'host-runtime-fixture.py'), resolve(work, 'outputs')], { cwd: root, windowsHide: true, env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
let diagnostics = '', sequence = 0, context;
runtime.stderr.on('data', data => { diagnostics = (diagnostics + data).slice(-4000); process.stderr.write(data); });
const pending = new Map();
let acceptReady, rejectReady;
const ready = new Promise((resolve, reject) => { acceptReady = resolve; rejectReady = reject; });
createInterface({ input: runtime.stdout }).on('line', line => {
  try {
    const data = JSON.parse(line);
    if (data.relay_url) acceptReady(data);
    else if (pending.has(data.id)) { pending.get(data.id)(data); pending.delete(data.id); }
  } catch { /* Nonprotocol diagnostics are excluded from evidence. */ }
});
runtime.once('exit', code => rejectReady(new Error(`Host fixture exited ${code}: ${diagnostics}`)));
const invoke = async (tool, args = {}) => {
  const id = ++sequence;
  const result = new Promise(resolve => pending.set(id, resolve));
  runtime.stdin.write(JSON.stringify({ id, tool, arguments: args }) + '\n');
  const response = await Promise.race([result, new Promise((_, reject) => setTimeout(() => reject(new Error('Host invocation timed out')), 75000).unref())]);
  assert.equal(response.kind, 'completed', response.message || response.error);
  assert.equal(response.metadata.browser_use.browser_id, 'fixture');
  return response.content;
};
const server = http.createServer(async (request, response) => {
  if (request.url === '/api/browser/v1/claim') { for await (const _ of request) {} response.setHeader('Content-Type', 'application/json'); response.end(JSON.stringify({ token: 'fixture-token', browser_id: 'fixture' })); return; }
  response.setHeader('Content-Type', 'text/html');
  response.end('<title>Production host fixture</title><h1>Production host fixture</h1><p>'+ (request.headers.cookie?.includes('host_login=present')?'Authenticated paired browser':'No paired browser login')+'</p><button onclick="this.textContent=\'Host clicked\'">Host action</button>');
});
const sockets = new WebSocketServer({ server });
try {
  const { relay_url } = await Promise.race([ready, new Promise((_, reject) => setTimeout(() => reject(new Error('Host fixture startup timed out: ' + diagnostics)), 45000).unref())]);
  console.log('Host runtime ready');
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const baseUrl = `http://127.0.0.1:${server.address().port}`;
  sockets.on('connection', socket => socket.on('message', raw => {
    const event = JSON.parse(raw);
    if (['hello', 'relay.request'].includes(event.type)) socket.send(JSON.stringify({ type: 'ready', relay_url }));
  }));
  context = await chromium.launchPersistentContext(resolve(work, 'profile'), {
    ...(process.env.SUGAR_TEST_BROWSER_PATH ? { executablePath: process.env.SUGAR_TEST_BROWSER_PATH } : { channel: 'msedge' }), headless: true,
    args: [`--disable-extensions-except=${resolve(root, 'browser-extension/dist')}`, `--load-extension=${resolve(root, 'browser-extension/dist')}`],
  });
  await context.addCookies([{name:'host_login',value:'present',url:baseUrl}]);
  const website = context.pages()[0] || await context.newPage(); await website.goto(baseUrl);
  const panel = await context.newPage(); await panel.goto('chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo/sidepanel.html');
  const paired = await panel.evaluate(baseUrl => chrome.runtime.sendMessage({ type: 'pair', baseUrl, code: 'fixture' }), baseUrl);
  assert.equal(paired.ok, true);
  console.log('Extension paired');
  await panel.waitForTimeout(500);
  await website.bringToFront();
  assert.match(await invoke('browser_get_context'), /Production host fixture/);
  const other=await context.newPage();await other.goto(baseUrl+'/other');await other.locator('h1').evaluate(node=>node.textContent='Different active page');await other.bringToFront();
  assert.match(await invoke('browser_tabs', { action: 'list' }), /Production host fixture/);
  const snapshot = await invoke('browser_snapshot');
  assert.doesNotMatch(snapshot,/Different active page/);
  const target = snapshot.match(/button "Host action"[^\n]*\[ref=([^\]]+)\]/)?.[1]; assert.ok(target);
  await panel.close();
  await invoke('browser_click', { target, element: 'Host action' });
  assert.equal(await website.locator('button').innerText(), 'Host clicked');
  await invoke('browser_tabs',{action:'new',url:baseUrl+'/new'});
  const created=context.pages().find(page=>page.url()===baseUrl+'/new');
  assert.ok(created,'Tool-created tab is absent from the paired browser');
  await invoke('browser_navigate',{url:baseUrl+'/destination'});
  await created.waitForURL(baseUrl+'/destination');
  assert.match(await invoke('browser_snapshot'),/Authenticated paired browser/);
  assert.equal(website.url(),baseUrl+'/');
  assert.equal(await website.locator('button').innerText(),'Host clicked');
  const report = { passed: true, browser: context.browser().version(), checks: ['python-host-invoker', 'execution-service-thread', 'managed-node-process', 'real-extension-relay', 'read-only-browser-context-through-host', 'upstream-snapshot-and-click', 'host-call-after-sidebar-close','tool-created-tab-and-navigation-stay-in-paired-browser','paired-browser-login-and-original-tab-are-preserved'], timestamp: new Date().toISOString() };
  await mkdir(resolve(root, 'browser-extension/artifacts/host'), { recursive: true });
  await writeFile(resolve(root, 'browser-extension/artifacts/host/integration.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally {
  await context?.close();
  for (const socket of sockets.clients) socket.terminate();
  await new Promise(resolve => sockets.close(resolve));
  server.closeAllConnections();
  if (server.listening) await new Promise(resolve => server.close(resolve));
  runtime.stdin.end();
  await Promise.race([new Promise(resolve => runtime.once('exit', resolve)), new Promise(resolve => setTimeout(resolve, 12000))]);
  if (runtime.exitCode === null) runtime.kill();
  const verified = resolve(work);
  if (!verified.startsWith(resolve(tmpdir()) + sep) || !basename(verified).startsWith('sugar-host-smoke-')) throw new Error('Unexpected fixture cleanup path');
  await rm(verified, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 });
}
