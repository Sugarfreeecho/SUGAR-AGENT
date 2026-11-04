import assert from 'node:assert/strict';
import http from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createRequire } from 'node:module';
const root = resolve(import.meta.dirname, '../..');
const require = createRequire(resolve(root, 'plugins/browser-use/node/package.json'));
const { chromium } = require('playwright');
const out = resolve(root, 'browser-extension/artifacts/settings'); await mkdir(out, { recursive: true });
const checks = [], actions = [];
let installed = false, enabled = false, devices = [], available = false, defaultId = '', browser, bundled = false;
const server = http.createServer(async (request, response) => {
  const send = data => { response.setHeader('Content-Type', 'application/json'); response.end(JSON.stringify(data)); };
  if (request.url === '/frame-fixture') {
    response.setHeader('Content-Type', 'text/html');
    response.end('<body style="margin:0;background:#1b1b1c"><iframe src="/" style="width:100%;height:900px;border:0"></iframe><script>window.addEventListener("message",e=>{if(e.data?.type==="myagent:plugin-settings-ready")e.source.postMessage({type:"myagent:plugin-settings-context",theme:"theme-dark",fontPx:12},location.origin)})</script>'); return;
  }
  if (request.url === '/api/plugins/catalog') return send({ plugins: [{ id: 'browser-use', enabled }], enabled: { plugins: true } });
  if (request.url === '/api/plugins/browser-use/enabled') { enabled = true; actions.push('enable'); return send({ ok: true }); }
  if (!enabled && ['/api/browser/v1/setup', '/api/browser/v1/status'].includes(request.url)) { response.writeHead(404); response.end('{}'); return; }
  if (request.url === '/api/browser/v1/setup') return send({ protocol: 1, plugin_enabled: true, node_available: true, runtime_installed: installed, runtime_bundled: bundled, installation: { status: 'idle' }, extension_ready: true, extension_directory: 'D:\\SugarAgent\\browser-extension\\dist', download_ready: true, version: '0.2.0' });
  if (request.url === '/api/browser/v1/status') return send({ devices, default_browser: defaultId });
  if (request.url === '/api/browser/v1/setup/install') { installed = true; actions.push('install'); return send({ status: 'running' }); }
  if (request.url === '/api/browser/v1/setup/reveal') { actions.push('reveal'); return send({ opened: true }); }
  if (request.url === '/api/browser/v1/setup/download') { response.writeHead(200, { 'Content-Type': 'application/zip', 'Content-Disposition': 'attachment; filename="sugaragent-browser.zip"' }); response.end('PK-fixture'); return; }
  if (request.url === '/api/browser/v1/pairings') { let body = ''; for await (const chunk of request) body += chunk; actions.push(JSON.parse(body)); return send({ code: 'ABCD-EFGH' }); }
  if (request.url === '/api/browser/v1/default') { let body = ''; for await (const chunk of request) body += chunk; defaultId = JSON.parse(body).browser_id; actions.push('default'); return send({ default_browser: defaultId }); }
  if (request.url?.endsWith('/revoke')) { actions.push('revoke'); devices = []; return send({ revoked: true }); }
  if (request.url === '/api/lifecycle/status') return send({ restart_available: available, ui_token: 'fixture-ui-token' });
  if (request.url === '/api/lifecycle/restarts') return send({ operation: { restart_id: 'fixture-restart', request_digest: 'fixture-digest', impact: { running_tasks: 2, background_jobs: 1, terminals: 0 } } });
  if (request.url?.endsWith('/decision')) { let body = ''; for await (const chunk of request) body += chunk; const data = JSON.parse(body); assert.equal(request.headers['x-myagent-lifecycle-ui'], 'fixture-ui-token'); actions.push(data.decision); return send({ operation: {} }); }
  const name = request.url === '/' ? 'index.html' : new URL(request.url,'http://localhost').pathname.split('/').at(-1);
  if (!['index.html', 'style.css', 'app.js','view.js','standalone.js'].includes(name)) { response.writeHead(404); response.end(); return; }
  response.setHeader('Content-Type', name.endsWith('.js') ? 'text/javascript' : name.endsWith('.css') ? 'text/css' : 'text/html');
  response.end(await readFile(resolve(root, 'plugins/browser-use/web', name)));
});
try {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 860, height: 1100 } });
  await context.addInitScript(()=>{let text='';Object.defineProperty(navigator,'clipboard',{value:{writeText:async value=>{text=value;},readText:async()=>text}});});
  const page = await context.newPage();
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto(origin);
  for (const [theme, expected] of [['light', '#fafafa'], ['purple', '#181825'], ['dark', '#1b1b1c']]) {
    await page.evaluate(theme => window.postMessage({ type: 'myagent:plugin-settings-context', theme: 'theme-' + theme }, location.origin), theme);
    await page.waitForFunction(theme => document.documentElement.dataset.theme === theme, theme);
    assert.equal(await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()), expected);
  }
  await page.evaluate(() => delete document.documentElement.dataset.theme);
  checks.push('inherits-all-three-parent-agent-themes');
  for (const size of [12, 16, 20]) {
    await page.evaluate(fontPx => window.postMessage({ type: 'myagent:plugin-settings-context', theme: 'theme-light', fontPx }, location.origin), size);
    await page.waitForFunction(size => getComputedStyle(document.documentElement).getPropertyValue('--setup-title').trim() === size + 'px', size);
    assert.equal(await page.locator('h1').evaluate(node => getComputedStyle(node).fontSize), size + 'px');
    assert.equal(await page.locator('.step-heading strong').first().evaluate(node => getComputedStyle(node).fontSize), Math.max(11, size - 2) + 'px');
  }
  await page.evaluate(() => { for (const name of ['--setup-font', '--setup-title', '--setup-small', '--setup-tiny']) document.documentElement.style.removeProperty(name); delete document.documentElement.dataset.theme; });
  assert.ok(await page.locator('h1').evaluate(node => parseFloat(getComputedStyle(node).fontSize) <= 16));
  assert.ok((await page.locator('#step-extension .step-heading').boundingBox()).height <= 70);
  checks.push('compact-settings-layout-follows-main-font-size-axis');
  await page.getByRole('button', { name: '启用插件', exact: true }).click();
  await page.getByText('扩展包 v0.2.0',{exact:true}).waitFor();checks.push('extension-package-version-comes-from-setup-manifest');
  assert.ok(actions.includes('enable')); checks.push('enable-disabled-plugin-inside-the-first-step');
  await page.getByRole('button', { name: '安装运行组件', exact: true }).click();
  await page.getByText('Playwright 运行组件已安装', { exact: true }).waitFor();
  assert.ok(actions.includes('install')); checks.push('guided-runtime-install-and-detection');
  await page.getByRole('button', { name: '继续加载扩展 →' }).click();
  await page.getByRole('button', { name: 'Edge', exact: true }).click();
  assert.equal(await page.locator('#browser-url').innerText(), 'edge://extensions');
  await page.locator('[data-copy="browser-url"]').click();
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), 'edge://extensions');
  await page.getByRole('button', { name: '打开扩展文件夹' }).click(); assert.ok(actions.includes('reveal'));
  const downloadPromise = page.waitForEvent('download'); await page.getByRole('link', { name: '下载扩展 ZIP' }).click(); assert.equal((await downloadPromise).suggestedFilename(), 'sugaragent-browser.zip');
  await page.screenshot({ path: resolve(out, 'setup-load-light.png'), fullPage: true });
  checks.push('browser-specific-loading-folder-download-and-copy');
  await page.getByRole('button', { name: '已加载扩展，继续配对 →' }).click();
  await page.locator('#name').fill('工作浏览器'); await page.getByRole('button', { name: '生成配对码', exact: true }).click();
  await page.getByText('ABCD-EFGH', { exact: true }).waitFor(); assert.equal(actions.find(item => item.name)?.name, '工作浏览器');
  assert.equal(await page.locator('#server-url').innerText(), origin);
  await page.screenshot({ path: resolve(out, 'setup-pair-light.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
  await page.screenshot({ path: resolve(out, 'setup-pair-dark-390.png'), fullPage: true });
  checks.push('pairing-code-server-address-and-responsive-layout');
  devices = [{ id: 'fixture-device', name: '工作浏览器 <script>', runtime: { initialized: true } }];
  await page.getByText('浏览器与 Agent 已连通', { exact: true }).waitFor();
  assert.equal(await page.locator('#code-panel').isVisible(), false);
  await page.getByRole('button', { name: '设为默认', exact: true }).click(); assert.equal(defaultId, 'fixture-device');
  checks.push('automatic-pairing-completion-and-default-device');
  await page.locator('#step-service .step-heading').click();
  await page.getByRole('button', { name: '重启开发后端', exact: true }).click();
  await page.getByRole('alert').filter({ hasText: '当前启动方式不支持' }).waitFor();
  available = true;
  await page.getByRole('button', { name: '重启开发后端', exact: true }).click();
  await page.getByText('重启会影响 2 个运行任务', { exact: false }).waitFor();
  await page.locator('#restart-dialog').getByRole('button', { name: '取消', exact: true }).click();
  await page.waitForTimeout(100); assert.ok(actions.includes('deny')); assert.ok(!actions.includes('allow_once'));
  await page.getByRole('button', { name: '重启开发后端', exact: true }).click();
  await page.getByRole('button', { name: '确认重启', exact: true }).click();
  assert.ok(actions.includes('allow_once')); checks.push('restart-availability-impact-and-explicit-decision');
  await page.getByRole('button', { name: '撤销配对', exact: true }).click();
  assert.ok(!actions.includes('revoke'));
  await page.locator('#revoke-dialog').getByRole('button', { name: '撤销配对', exact: true }).click();
  assert.ok(actions.includes('revoke')); checks.push('confirmed-device-revocation');
  await page.setViewportSize({ width: 720, height: 820 });
  await page.goto(origin + '/frame-fixture');
  const embedded = page.frameLocator('iframe');
  await embedded.locator('html.embedded[data-theme=dark]').waitFor();
  assert.equal(await embedded.locator('h1').isVisible(), false, 'Embedded settings repeats the main panel title');
  assert.equal(await embedded.locator('.step-heading strong').first().evaluate(node => getComputedStyle(node).fontSize), '11px');
  assert.equal(await embedded.locator('.setup').evaluate(node => getComputedStyle(node).paddingLeft), '0px');
  await page.screenshot({ path: resolve(out, 'setup-embedded-compact.png'), fullPage: true });
  checks.push('embedded-settings-inherits-parent-fonts-without-double-padding');
  bundled=true;installed=true;await page.goto(origin);await page.locator('#step-service .step-heading').click();
  await page.getByText('运行组件已随 SugarAgent 提供，无需另行安装',{exact:true}).waitFor();
  assert.equal(await page.locator('#install').isHidden(),true);assert.equal(await page.locator('#manual-runtime').isHidden(),true);
  installed=false;await page.locator('#refresh').click();await page.getByText('运行组件不完整，请修复或重新安装 SugarAgent',{exact:true}).waitFor();
  assert.equal(await page.locator('#install').isHidden(),true);assert.equal(await page.locator('#next-service').isDisabled(),true);
  checks.push('packaged-runtime-needs-no-node-install-and-broken-bundle-asks-for-app-repair');
  assert.deepEqual(errors, []);
  const report = { passed: true, checks, timestamp: new Date().toISOString() }; await writeFile(resolve(out, 'settings-smoke.json'), JSON.stringify(report, null, 2)); console.log(JSON.stringify(report, null, 2));
} finally { await browser?.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
