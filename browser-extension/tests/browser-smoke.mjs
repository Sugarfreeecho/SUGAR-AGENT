import assert from 'node:assert/strict';
import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { createRequire } from 'node:module';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, sep, basename } from 'node:path';
import { BrowserRelay } from '../../plugins/browser-use/node/relay.mjs';
import { BrowserEngine } from '../../plugins/browser-use/node/engine.mjs';

const require = createRequire(new URL('../../plugins/browser-use/node/package.json', import.meta.url));
const { chromium } = require('playwright');
const { wsServer: WebSocketServer } = require('playwright-core/lib/utilsBundle');
const extensionId = 'mdiicfkdpohkiccgjiomnlmokamaafbo';
const extensionPath = resolve(import.meta.dirname, '../dist');
const work = await mkdtemp(resolve(tmpdir(), 'sugar-browser-smoke-'));
const artifactDir = resolve(import.meta.dirname, '../artifacts', process.env.SUGAR_TEST_BROWSER_PATH ? 'chrome' : 'edge');
await mkdir(artifactDir, { recursive: true });
const checks = [];
const layout = {};
const uiSession = 'fixture-session';
const uiHistory = [
  { type: 'user', run_id: 'history-run', content: '帮我查看这个网页，并整理主要内容。' },
  { type: 'llm_response', run_id: 'history-run', reasoning: '先确认页面来源，再读取与任务有关的内容。', content: '我先查看页面。' },
  { type: 'tool_call', run_id: 'history-run', tool: 'browser_snapshot', tool_call_id: 'history-tool', result: '已读取页面结构和正文。', status: { ok: true, truncated: false, timed_out: false, source: 'tool', duration_ms: 12 } },
  { type: 'final', run_id: 'history-run', content: '已读取页面。\n\n页面包含 **项目说明**、使用方式和参考链接。你可以继续提问，或把下一步操作交给我。\n\n| 内容 | 状态 |\n| --- | --- |\n| 当前网页 | 已读取 |\n| 登录状态 | 已保留 |' },
];
uiHistory[3].content += '\n\n公式：$x^2 + 1$。\n\n```python\nprint("hello")\n```\n\n```mermaid\ngraph LR\n  A[网页] --> B[Agent]\n```';
let context, engine, finishStream, lastSendPayload;
let uiModel = 'fixture-model', uiEffort = '', uiWorkDir = work;
const token = randomUUID();
const relay = new BrowserRelay({ token, allowedOrigin: `chrome-extension://${extensionId}` });
await relay.start();
const backend = http.createServer(async (request, response) => {
  if (request.url?.startsWith('/api/browser/v1/media')) {
    assert.equal(request.headers.authorization, 'Bearer fixture-token');
    response.writeHead(200, { 'Content-Type': 'image/png' });
    response.end(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aBWQAAAAASUVORK5CYII=', 'base64')); return;
  }
  if (request.url === '/api/browser/v1/human/list') { response.setHeader('Content-Type','application/json');response.end(JSON.stringify({records:[]}));return; }
  if (request.url === '/api/browser/v1/steers') { response.setHeader('Content-Type','application/json');response.end(JSON.stringify({items:[]}));return; }
  if (request.url === '/api/browser/v1/connection') { response.setHeader('Content-Type','application/json');response.end(JSON.stringify({paired:true,browser_id:'fixture-browser'}));return; }
  if (request.url === '/api/browser/v1/session-state') { response.setHeader('Content-Type','application/json');response.end(JSON.stringify({permissions:{mode:'ask_for_approval',can_change:true,security_enabled:true,available_modes:{ask_for_approval:true,approve_for_me:true,full_access:true}},context_tokens:{estimated:4096,threshold:128000}}));return; }
  if (request.url === '/api/browser/v1/models') {
    response.setHeader('Content-Type', 'application/json'); response.end(JSON.stringify({ profiles: [{ id: 'fixture-model', name: '测试模型 · 具有很长名称的浏览器协作配置' }] })); return;
  }
  if (request.url === '/api/browser/v1/workspaces') {
    response.setHeader('Content-Type', 'application/json'); response.end(JSON.stringify({ default_work_dir: work, workspaces: [{path: work, name: basename(work)}] })); return;
  }
  if (request.url === '/api/browser/v1/plugins') {
    response.setHeader('Content-Type', 'application/json'); response.end(JSON.stringify({plugins:[{id:'browser-use',name:'浏览器连接',description:'使用当前浏览器',enabled:true,loaded:true,settings_section:'plugin:browser-use:browser'}]}));return;
  }
  if (request.url === '/api/browser/v1/workspaces/validate') {
    let body='';for await(const chunk of request)body+=chunk;
    response.setHeader('Content-Type', 'application/json');response.end(JSON.stringify({path:JSON.parse(body).path}));return;
  }
  if (request.url === '/api/control/v1/rpc' || request.url === '/api/browser/v1/messages') {
    let body = ''; for await (const chunk of request) body += chunk;
    const payload = JSON.parse(body);
    const { method, params } = request.url === '/api/browser/v1/messages' ? {method:'session.send',params:payload} : payload;
    if(method==='session.update') { if('model_profile_id' in params)uiModel=params.model_profile_id;if('reasoning_effort' in params)uiEffort=params.reasoning_effort;if('work_dir' in params)uiWorkDir=params.work_dir; }
    const result = method === 'session.list' ? { sessions: [{ id: uiSession, name: '网页研究', updated_at: new Date().toISOString() }] }
      : method === 'session.history' ? { events: uiHistory, range_start: 0, has_older: false }
      : method === 'session.get' ? { session: { id: uiSession, name: '网页研究', stream_active: false, model_profile_id:uiModel, reasoning_effort:uiEffort, work_dir:uiWorkDir } }
      : method === 'approval.list' ? { approvals: [] }
      : { accepted: true, session_id: uiSession, operation_id: 'fixture-operation' };
    response.setHeader('Content-Type', 'application/json'); response.end(JSON.stringify({ ok: true, data: result }));
    if (method === 'session.send') {
      lastSendPayload=params;
      const stream = [
        { type: 'user', content: params.ui_message, run_id: 'live-run' },
        { type: 'run_started', run_id: 'live-run' },
        { type: 'llm_reasoning_delta', delta: '根据附加网页整理要点。', run_id: 'live-run', ephemeral: true },
        { type: 'tool_call', name: 'browser_snapshot', content: '页面内容已读取', tool_call_id: 'live-tool', run_id: 'live-run' },
        { type: 'llm_response_delta', delta: '正在形成回答…', run_id: 'live-run', ephemeral: true },
        { type: 'final', content: '任务完成：已整理网页要点。', run_id: 'live-run' },
        { type: 'run_finished', result_status: 'succeeded', run_id: 'live-run' },
      ];
      const dispatch = (event, index) => {
        for (const socket of apps.clients) if (socket.readyState === 1) socket.send(JSON.stringify({ type: 'session.event', session_id: uiSession, event: { ...event, event_bus_seq: index + 100, event_bus_epoch: 'fixture' } }));
      };
      stream.slice(0, 5).forEach((event, index) => setTimeout(() => dispatch(event, index), 120 * (index + 1)));
      // Hold the terminal facts until the UI has observed the live reasoning.
      // Machine speed must not decide whether a 360 ms intermediate state is tested.
      finishStream = () => stream.slice(5).forEach((event, index) => setTimeout(() => dispatch(event, index + 5), 120 * (index + 1)));
    }
    return;
  }
  if (request.url === '/api/browser/v1/claim') {
    for await (const _ of request) { /* consume body */ }
    response.setHeader('Content-Type', 'application/json');
    response.end(JSON.stringify({ token: 'fixture-token', browser_id: 'fixture-browser' }));
    return;
  }
  const name = request.url === '/second' ? 'Second fixture' : request.url === '/new' ? 'New fixture' : 'First fixture';
  if (request.url === '/frame') {
    response.setHeader('Content-Type', 'text/html'); response.end('<button onclick="this.textContent=\'Frame clicked\'">Cross origin action</button>'); return;
  }
  if (request.url === '/framed') {
    response.setHeader('Content-Type', 'text/html'); response.end(`<h1>Frame fixture</h1><iframe src="http://localhost:${backend.address().port}/frame"></iframe>`); return;
  }
  if (request.url === '/download') {
    response.writeHead(200, { 'Content-Type': 'text/plain', 'Content-Disposition': 'attachment; filename="fixture-download.txt"' });
    response.end('Downloaded by the browser task.'); return;
  }
  const loggedIn = request.headers.cookie?.includes('fixture_login=present');
  response.setHeader('Content-Type', 'text/html; charset=utf-8');
  response.end(`<!doctype html><html><head><title>${name}</title></head><body><main><h1>${name}</h1><p>${loggedIn ? 'Authenticated existing session' : 'No session'}</p><button id="increment">Increment</button><output id="count">0</output><label>Note<input id="note"></label><label>Upload fixture<input id="upload" type="file"></label><a href="/download" download>Download fixture</a><script>increment.onclick=()=>count.textContent=String(Number(count.textContent)+1)</script></main></body></html>`);
});
await new Promise(resolve => backend.listen(0, '127.0.0.1', resolve));
const baseUrl = `http://127.0.0.1:${backend.address().port}`;
const apps = new WebSocketServer({ server: backend });
apps.on('connection', socket => {
  socket.on('message', raw => {
    const data = JSON.parse(raw.toString());
    if (data.type === 'hello' || data.type === 'relay.request') socket.send(JSON.stringify({ type: 'ready', relay_url: `ws://127.0.0.1:${relay.port}/extension?token=${token}` }));
    if (data.type === 'subscribe') socket.send(JSON.stringify({ type: 'subscribed', session_id: data.session_id }));
    if (data.type === 'ping') socket.send(JSON.stringify({type:'pong'}));
  });
});
const textOf = result => (result.content || []).filter(block => block.type === 'text').map(block => block.text).join('\n');
async function waitFor(condition, message, timeout = 20000) {
  const until = Date.now() + timeout;
  while (Date.now() < until) {
    if (await condition()) return;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(message);
}
try {
  context = await chromium.launchPersistentContext(resolve(work, 'profile'), {
    ...(process.env.SUGAR_TEST_BROWSER_PATH ? { executablePath: process.env.SUGAR_TEST_BROWSER_PATH } : { channel: 'msedge' }),
    headless: process.env.SUGAR_TEST_HEADED !== '1',
    locale: 'zh-CN',
    downloadsPath: resolve(work, 'downloads'),
    args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
  });
  let workers = context.serviceWorkers();
  if (!workers.length) workers = [await context.waitForEvent('serviceworker', { timeout: 12000 })];
  assert.ok(workers.some(worker => worker.url().startsWith(`chrome-extension://${extensionId}/`)), 'SugarAgent extension service worker was not loaded');
  checks.push('real-extension-service-worker');
  await context.addCookies([{ name: 'fixture_login', value: 'present', url: baseUrl }]);
  const first = context.pages()[0] || await context.newPage();
  await first.goto(`${baseUrl}/first`);
  const second = await context.newPage();
  await second.goto(`${baseUrl}/second`);
  const panel = await context.newPage();
  await panel.goto(`chrome-extension://${extensionId}/sidepanel.html`);
  const paired = await panel.evaluate(async baseUrl => chrome.runtime.sendMessage({ type: 'pair', baseUrl, code: 'fixture' }), baseUrl);
  assert.equal(paired.ok, true, JSON.stringify(paired));
  await waitFor(() => relay.initialized, 'Extension did not initialize the real Playwright relay');
  checks.push('authenticated-extension-relay');
  await panel.locator('textarea[aria-label="消息"]').waitFor();
  assert.equal(await panel.locator('.session-bar,.session-state,.composer-footer,.brand').count(), 0);
  assert.equal(await panel.locator('.topbar .session-title').innerText().then(text => text.replace('⌄', '').trim()), '网页研究');
  const headerBounds = await panel.locator('.topbar').boundingBox();
  const composerBounds = await panel.locator('.composer-seat').boundingBox();
  assert.ok(headerBounds.height <= 46, 'Header consumes a second row');
  assert.ok(composerBounds.height <= 145, `Idle composer is too tall: ${composerBounds.height}`);
  await panel.getByTitle('附加资料', { exact: true }).click();
  await panel.getByRole('menuitem', { name: '附加文件' }).waitFor();
  await panel.keyboard.press('Escape');
  assert.equal(await panel.getByRole('menu').count(), 0);
  await panel.getByTitle('附加资料', { exact: true }).click();
  await panel.keyboard.press('End'); await panel.keyboard.press('Enter');
  const chooseTab = panel.getByRole('dialog', { name: '选择网页', exact: true });
  await chooseTab.getByText('First fixture', { exact: true }).click();
  await panel.locator('.context-chip').getByText('↗ First fixture', { exact: true }).waitFor();
  await panel.getByLabel('移除网页', { exact: true }).click();
  checks.push('compact-single-row-header-and-chatgpt-style-composer');
  await panel.getByText('已读取页面。', { exact: false }).first().waitFor();
  await panel.locator('.process-heading').first().click();
  await panel.locator('.process-block.tool summary').getByText('已完成', { exact: true }).waitFor();
  assert.equal(await panel.locator('.assistant-label,.assistant-mark').count(), 0);
  assert.equal(await panel.locator('.answer').first().evaluate(node => getComputedStyle(node).fontSize), '12px');
  assert.ok((await panel.locator('.model-picker').boundingBox()).width <= 142);
  await panel.locator('.process-heading').first().click();
  checks.push('production-history-process-opens-and-compact-body-has-no-repeated-brand');
  await panel.locator('.katex').first().waitFor();
  await panel.locator('.hljs-keyword,.hljs-built_in').first().waitFor();
  await panel.locator('.mermaid-preview svg').first().waitFor({ timeout: 20000 });
  checks.push('local-math-code-and-diagram-rendering');
  await panel.setViewportSize({width:400,height:800});
  await panel.screenshot({path:resolve(artifactDir,'selected-m-dark-chat-400.png')});
  await panel.locator('.model-picker>.popover-trigger').click();
  await panel.locator('.model-picker .popover-panel').waitFor();
  await panel.screenshot({path:resolve(artifactDir,'selected-m-model-400.png')});
  await panel.keyboard.press('Escape');
  // A main-app attachment must be fetched with the browser identity.
  uiHistory.unshift({ type: 'user', run_id: 'image-run', content: [{ type: 'image', attachment: { attachmentId: 'fixture-image' } }] });
  await panel.reload();
  await waitFor(() => panel.locator('.attachment-image').evaluateAll(images => images.length === 1 && images[0].naturalWidth > 0), 'Shared history image did not render');
  checks.push('authenticated-shared-history-image');
  await panel.setViewportSize({ width: 400, height: 800 });
  await panel.screenshot({ path: resolve(artifactDir, 'sidebar-light-400.png') });
  await panel.setViewportSize({ width: 320, height: 720 });
  assert.equal(await panel.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'Narrow sidebar overflows horizontally');
  assert.ok((await panel.locator('.composer-seat').boundingBox()).height <= 145, 'Narrow idle composer grew too tall');
  layout.header = (await panel.locator('.topbar').boundingBox()).height;
  layout.idleComposer = (await panel.locator('.composer-seat').boundingBox()).height;
  layout.reading = (await panel.locator('.reading').boundingBox()).height;
  layout.viewport = { width: 320, height: 720 };
  await panel.screenshot({ path: resolve(artifactDir, 'sidebar-light-320.png') });
  await panel.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
  await panel.screenshot({ path: resolve(artifactDir, 'sidebar-dark-320.png') });
  checks.push('sidebar-history-and-responsive-layout');
  const savedHistory = [...uiHistory]; uiHistory.length = 0;
  await panel.reload(); await panel.getByText('继续最近的会话', { exact: true }).waitFor();
  await panel.setViewportSize({ width: 400, height: 800 });
  await panel.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' });
  await panel.screenshot({ path: resolve(artifactDir, 'sidebar-welcome-light-400.png') });
  await panel.setViewportSize({ width: 320, height: 720 });
  assert.equal(await panel.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await panel.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
  await panel.screenshot({ path: resolve(artifactDir, 'sidebar-welcome-dark-320.png') });
  uiHistory.push(...savedHistory); await panel.reload(); await panel.locator('.answer').first().waitFor();
  await panel.locator('.header-more>.popover-trigger').click(); await panel.locator('.header-more .menu-item').filter({hasText:/^(设置|Settings)$/}).click();
  // Compare the three palettes with the actual main settings source tokens.
  const mainThemes = await readFile(resolve(import.meta.dirname, '../../app/templates/static/settings/settings.css'), 'utf8');
  for (const theme of ['light', 'purple', 'dark']) {
    const block = theme === 'light' ? mainThemes.match(/:root\s*\{([^}]+)\}/)?.[1] : mainThemes.match(new RegExp(':root\\.theme-' + theme + '\\s*\\{([^}]+)\\}'))?.[1];
    const expectedBg = block?.match(/--st-page:\s*([^;]+);/)?.[1];
    const expectedText = block?.match(/--st-text:\s*([^;]+);/)?.[1];
    assert.ok(expectedBg && expectedText, 'Main theme tokens were not found');
    await panel.locator('[data-pref-theme]').selectOption(theme);
    await waitFor(async () => await panel.evaluate(theme => document.documentElement.dataset.theme === theme, theme), 'Theme choice did not apply');
    const colors = await panel.evaluate(() => { const style = getComputedStyle(document.documentElement); return { bg: style.getPropertyValue('--bg').trim(), text: style.getPropertyValue('--text').trim() }; });
    assert.deepEqual(colors, { bg: expectedBg, text: expectedText });
    await panel.getByText('返回', { exact: true }).click();
    await panel.locator('.mermaid-preview svg').first().waitFor({ timeout: 20000 });
    const footerGeometry=await panel.locator('.composer-seat').evaluate(node=>{const rect=node.getBoundingClientRect();return{top:rect.top,bottom:rect.bottom,viewport:innerHeight,scrollY};});
    assert.ok(footerGeometry.top>=0&&footerGeometry.bottom<=footerGeometry.viewport+1&&footerGeometry.scrollY===0,'Theme/diagram render displaced the composer: '+JSON.stringify(footerGeometry));
    await panel.screenshot({ path: resolve(artifactDir, `sidebar-theme-${theme}-320.png`) });
    await panel.locator('.header-more>.popover-trigger').click(); await panel.locator('.header-more .menu-item').filter({hasText:/^(设置|Settings)$/}).click();
  }
  await panel.locator('[data-pref-theme]').selectOption('system');
  checks.push('main-agent-light-purple-and-dark-palettes');
  await panel.locator('[data-pref-language]').selectOption('en');
  await panel.getByRole('heading', { name: 'Settings', exact: true }).waitFor();
  await panel.getByText('Back', { exact: true }).click();
  assert.ok(await panel.locator('.answer').allTextContents().then(values => values.some(value => value.includes('页面包含'))));
  await panel.evaluate(()=>Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,value:async()=>{}}));
  await panel.locator('.answer-actions .copy-button').first().click();
  await panel.getByRole('button',{name:'Copied',exact:true}).waitFor();
  checks.push('english-copy-feedback-is-translated-without-translating-content');
  await panel.locator('.header-more>.popover-trigger').click(); await panel.locator('.header-more .menu-item').filter({hasText:/^(设置|Settings)$/}).click();
  await panel.locator('[data-pref-language]').selectOption('zh-CN');
  await panel.getByText('返回', { exact: true }).click();
  checks.push('language-switch-preserves-conversation');
  await panel.locator('textarea[aria-label="消息"]').fill('尚未发送的草稿');
  await panel.evaluate(async () => {
    await chrome.storage.session.set({ 'sugar.composer.fixture-session': { contexts: [{ title: '保留的网页', url: 'https://example.com/', text: 'Draft context', capturedAt: new Date().toISOString() }], uploads: [{ id: 'pending-file', name: 'pending.txt', size: 5 }] } });
  });
  await panel.waitForTimeout(400);
  await panel.reload();
  await panel.getByText('保留的网页', { exact: false }).waitFor();
  await panel.getByText('▤ pending.txt', { exact: true }).waitFor();
  assert.equal(await panel.locator('textarea[aria-label="消息"]').inputValue(), '尚未发送的草稿');
  checks.push('composer-survives-sidebar-reopen');
  await panel.getByLabel('移除网页', { exact: true }).click();
  await panel.getByLabel('移除文件', { exact: true }).click();
  await panel.locator('textarea[aria-label="消息"]').fill('请总结这个网页');
  await first.evaluate(()=>{const range=document.createRange();range.selectNodeContents(document.querySelector('h1'));const selection=getSelection();selection.removeAllRanges();selection.addRange(range);});
  await first.bringToFront();
  await panel.getByTitle('发送', { exact: true }).evaluate(button=>button.click());
  await panel.getByText('正在形成回答…', { exact: true }).waitFor();
  assert.equal(await panel.locator('.process-block.reason').last().getAttribute('open'), null, 'Completed reasoning stayed open during the answer');
  assert.equal(typeof finishStream, 'function'); finishStream();
  await panel.getByText('任务完成：已整理网页要点。', { exact: true }).waitFor();
  await waitFor(async () => (await panel.locator('.process-heading').last().getAttribute('aria-expanded')) === 'false', 'Successful live process did not fold');
  assert.equal(lastSendPayload.automatic,true);
  assert.equal(lastSendPayload.browser_context.page.url,`${baseUrl}/first`);
  assert.equal(lastSendPayload.browser_context.page.selection.text,'First fixture');
  assert.equal('text' in lastSendPayload.browser_context.page,false,'Full page body was attached automatically');
  checks.push('sidebar-message-automatically-associates-active-page-and-selection-without-full-body');
  await panel.screenshot({ path: resolve(artifactDir, 'sidebar-completed-320.png') });
  checks.push('sidebar-send-live-events-and-successful-fold');
  engine = new BrowserEngine(relay, { outputDir: resolve(work, 'output') });
  const catalog = await engine.catalog();
  assert.ok(catalog.some(tool => tool.name === 'browser_snapshot'));
  const probeContext = await engine.context();
  const probeSession = await probeContext.newCDPSession(probeContext.pages()[0]);
  const probeTarget = await probeSession.send('Target.getTargetInfo');
  const nativeTargets = await panel.evaluate(() => chrome.debugger.getTargets());
  assert.ok(nativeTargets.some(target => target.id === probeTarget.targetInfo.targetId), 'Public Playwright CDP session cannot resolve a stable native tab target');
  await probeSession.detach();
  checks.push('stable-native-target-maps-to-public-playwright-page');
  const contextCall=(session_id,run_id,browser_context)=>engine.call({session_id,run_id,tool:'browser_get_context',arguments:{},...(browser_context?{browser_context}:{})});
  await second.bringToFront();
  const bound=await contextCall('auto-context','auto-A',{automatic:true,page:lastSendPayload.browser_context.page});
  assert.equal(bound.structuredContent.active_page.url,`${baseUrl}/second`);
  assert.equal(bound.structuredContent.task_page.url,`${baseUrl}/first`);
  assert.match(textOf(await engine.call({session_id:'auto-context',run_id:'auto-A',tool:'browser_snapshot'})),/First fixture/);
  assert.equal(await panel.evaluate(async()=>(await chrome.tabs.query({active:true,lastFocusedWindow:true}))[0].url),`${baseUrl}/second`,'Observing the task page stole the user\'s active tab');
  const secondReference=(await panel.evaluate(()=>chrome.runtime.sendMessage({type:'page-context'}))).result.page;
  await first.bringToFront();
  await contextCall('auto-context','auto-B',{automatic:true,page:secondReference});
  assert.match(textOf(await engine.call({session_id:'auto-context',run_id:'auto-B',tool:'browser_snapshot'})),/Second fixture/);
  assert.equal(await panel.evaluate(async()=>(await chrome.tabs.query({active:true,lastFocusedWindow:true}))[0].url),`${baseUrl}/first`);
  assert.match(textOf(await engine.call({session_id:'auto-context',run_id:'auto-A',tool:'browser_snapshot'})),/First fixture/);
  engine.release('auto-A');engine.release('auto-B');
  checks.push('run-page-stays-bound-across-user-tab-switches-without-focus-stealing');
  const duplicate=await context.newPage();await duplicate.goto(`${baseUrl}/first`);await duplicate.locator('h1').evaluate(node=>node.textContent='Duplicate URL fixture');await duplicate.bringToFront();
  const duplicateReference=(await panel.evaluate(()=>chrome.runtime.sendMessage({type:'page-context'}))).result.page;
  await first.bringToFront();await contextCall('duplicate-context','duplicate-run',{automatic:true,page:duplicateReference});
  assert.match(textOf(await engine.call({session_id:'duplicate-context',run_id:'duplicate-run',tool:'browser_snapshot'})),/Duplicate URL fixture/);
  await duplicate.close();
  assert.equal((await contextCall('duplicate-context','duplicate-run')).structuredContent.task_page.available,false);
  await assert.rejects(engine.call({session_id:'duplicate-context',run_id:'duplicate-run',tool:'browser_snapshot'}),/bound_tab_closed/);
  const explicitIndex=(await engine.context()).pages().findIndex(page=>page.url()===`${baseUrl}/first`);
  await engine.call({session_id:'duplicate-context',run_id:'duplicate-run',tool:'browser_tabs',arguments:{action:'select',index:explicitIndex}});
  assert.equal((await contextCall('duplicate-context','duplicate-run')).structuredContent.task_page.available,true);
  engine.release('duplicate-run');await first.bringToFront();
  checks.push('stable-context-distinguishes-duplicate-urls-and-closed-page-requires-explicit-retargeting');
  await panel.bringToFront();const beforeNoPage=(await engine.context()).pages().length;
  const unavailable=await contextCall('no-page-context','no-page-run');
  assert.equal(unavailable.structuredContent.active_page,null);assert.equal(unavailable.structuredContent.task_page,null);
  assert.equal((await engine.context()).pages().length,beforeNoPage,'Reading context created an unrequested blank tab');
  engine.release('no-page-run');await first.bringToFront();checks.push('unsupported-active-page-does-not-select-another-page-or-create-a-tab');
  const call = (tool, args = {}, session_id = 'session-a', run_id = 'run-a') => engine.call({ session_id, run_id, tool, arguments: args, workspace: work });
  const tabs = textOf(await call('browser_tabs', { action: 'list' }));
  assert.match(tabs, /First fixture/);
  assert.match(tabs, /Second fixture/);
  assert.doesNotMatch(tabs, /chrome-extension:/);
  checks.push('all-existing-ordinary-tabs');
  await writeFile(resolve(artifactDir, 'tabs.txt'), tabs);
  const firstIndex = Number(tabs.match(/(\d+):[^\n]*First fixture/)?.[1]);
  assert.ok(Number.isInteger(firstIndex));
  await call('browser_tabs', { action: 'select', index: firstIndex });
  const snapshot = textOf(await call('browser_snapshot'));
  await writeFile(resolve(artifactDir, 'snapshot.txt'), snapshot);
  assert.match(snapshot, /Authenticated existing session/);
  checks.push('existing-login-state');
  const incrementRef = snapshot.match(/button "Increment"[^\n]*\[ref=([^\]]+)\]/)?.[1];
  assert.ok(incrementRef, 'No actionable Playwright reference found');
  const clickResult = await call('browser_click', { target: incrementRef, element: 'Increment' });
  assert.ok(!clickResult.isError, textOf(clickResult));
  assert.equal(await first.locator('#count').innerText(), '1');
  checks.push('upstream-click-tool');
  const uploadPath = resolve(work, 'fixture-upload.txt');
  await writeFile(uploadPath, 'User supplied upload fixture.');
  const uploadSnapshot = textOf(await call('browser_snapshot'));
  const uploadRef = uploadSnapshot.match(/button "Upload fixture"[^\n]*\[ref=([^\]]+)\]/)?.[1];
  assert.ok(uploadRef, 'File chooser reference missing from upstream snapshot');
  await call('browser_click', { target: uploadRef, element: 'Upload fixture' });
  const uploadResult = await call('browser_file_upload', { paths: [uploadPath] });
  assert.ok(!uploadResult.isError, textOf(uploadResult));
  assert.equal(await first.locator('#upload').evaluate(input => input.files[0]?.name), 'fixture-upload.txt');
  checks.push('upstream-file-upload-tool');
  const downloadSnapshot = textOf(await call('browser_snapshot'));
  const downloadRef = downloadSnapshot.match(/link "Download fixture"[^\n]*\[ref=([^\]]+)\]/)?.[1];
  assert.ok(downloadRef, 'Download link missing from upstream snapshot');
  const downloadPromise = first.waitForEvent('download');
  const downloadResult = await call('browser_click', { target: downloadRef, element: 'Download fixture' });
  assert.ok(!downloadResult.isError, textOf(downloadResult));
  const download = await downloadPromise;
  assert.equal(await download.failure(), null);
  assert.match(await readFile(await download.path(), 'utf8'), /Downloaded by the browser task/);
  checks.push('browser-download-through-upstream-click');
  await panel.close();
  const secondSnapshot = textOf(await call('browser_snapshot'));
  const nextRef = secondSnapshot.match(/button "Increment"[^\n]*\[ref=([^\]]+)\]/)?.[1];
  await call('browser_click', { target: nextRef, element: 'Increment' });
  assert.equal(await first.locator('#count').innerText(), '2');
  checks.push('continues-after-sidepanel-closes');
  await call('browser_tabs', { action: 'select', index: firstIndex }, 'session-b', 'run-b');
  await assert.rejects(call('browser_click', { target: nextRef, element: 'Increment' }, 'session-b', 'run-b'), /tab_busy/);
  checks.push('same-tab-write-lease');
  const secondIndex = Number(tabs.match(/(\d+):[^\n]*Second fixture/)?.[1]);
  await call('browser_tabs', { action: 'select', index: secondIndex }, 'session-b', 'run-b');
  assert.match(textOf(await call('browser_snapshot', {}, 'session-b', 'run-b')), /Second fixture/);
  assert.match(textOf(await call('browser_snapshot')), /First fixture/);
  checks.push('per-session-current-tab-isolation');
  await call('browser_tabs', { action: 'select', index: firstIndex }, 'session-b', 'run-b');
  engine.release('run-a');
  const bSnapshot = textOf(await call('browser_snapshot', {}, 'session-b', 'run-b'));
  const bRef = bSnapshot.match(/button "Increment"[^\n]*\[ref=([^\]]+)\]/)?.[1];
  await call('browser_click', { target: bRef, element: 'Increment' }, 'session-b', 'run-b');
  assert.equal(await first.locator('#count').innerText(), '3');
  checks.push('lease-release-between-sessions');
  const screenshot = await call('browser_take_screenshot', { type: 'png' }, 'session-b', 'run-b');
  assert.ok(!screenshot.isError, textOf(screenshot));
  checks.push('upstream-screenshot-tool');
  const newResult = await call('browser_tabs', { action: 'new', url: `${baseUrl}/new` }, 'session-b', 'run-b');
  await writeFile(resolve(artifactDir, 'new-tab.txt'), textOf(newResult));
  assert.ok(!newResult.isError, textOf(newResult));
  assert.match(textOf(await call('browser_snapshot', {}, 'session-b', 'run-b')), /New fixture/);
  checks.push('new-task-tab');
  await call('browser_navigate', { url: `${baseUrl}/framed` }, 'session-b', 'run-b');
  const framed = textOf(await call('browser_snapshot', {}, 'session-b', 'run-b'));
  const frameRef = framed.match(/button "Cross origin action"[^\n]*\[ref=([^\]]+)\]/)?.[1];
  assert.ok(frameRef, 'Cross origin iframe was missing from the upstream snapshot');
  assert.ok(!(await call('browser_click', { target: frameRef, element: 'Cross origin action' }, 'session-b', 'run-b')).isError);
  assert.match(textOf(await call('browser_snapshot', {}, 'session-b', 'run-b')), /Frame clicked/);
  checks.push('cross-origin-iframe-snapshot-and-click');
  const nativeFramed=context.pages().find(page=>page.url()===`${baseUrl}/framed`);
  await nativeFramed.frame({url:`http://localhost:${backend.address().port}/frame`}).locator('button').evaluate(node=>{const range=document.createRange();range.selectNodeContents(node);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);});
  const contextPanel=await context.newPage();await contextPanel.goto(`chrome-extension://${extensionId}/sidepanel.html`);await nativeFramed.bringToFront();
  const frameContext=(await contextPanel.evaluate(()=>chrome.runtime.sendMessage({type:'page-context'}))).result;
  assert.equal(frameContext.page.selection.text,'Frame clicked');assert.ok(frameContext.page.selection.frame_id>0);assert.match(frameContext.page.selection.frame_url,/localhost/);
  await contextPanel.close();checks.push('active-page-context-includes-selected-text-and-provenance-from-cross-origin-frame');
  const generation = relay.generation;
  for (const socket of apps.clients) socket.terminate();
  await waitFor(() => relay.initialized && relay.generation > generation, 'App and browser relay did not recover after disconnect', 35000);
  assert.match(textOf(await call('browser_tabs', { action: 'list' }, 'session-recovered', 'run-recovered')), /First fixture/);
  checks.push('backend-disconnect-reconnect');
  const beforeEviction = relay.generation;
  const browserCDP = await context.browser().newBrowserCDPSession();
  const targets = await browserCDP.send('Target.getTargets');
  const workerTarget = targets.targetInfos.find(target => target.type === 'service_worker' && target.url.startsWith(`chrome-extension://${extensionId}/`));
  assert.ok(workerTarget, 'No extension worker target to evict');
  assert.equal((await browserCDP.send('Target.closeTarget', { targetId: workerTarget.targetId })).success, true);
  await waitFor(() => relay.initialized && relay.generation > beforeEviction, 'Persistent alarm did not recover the evicted extension worker', 45000);
  assert.match(textOf(await call('browser_tabs', { action: 'list' }, 'session-after-worker', 'run-after-worker')), /First fixture/);
  await browserCDP.detach();
  checks.push('evicted-service-worker-recovers-without-sidebar');
  engine.cancel('cancelled-run');
  await assert.rejects(call('browser_snapshot', {}, 'cancelled-session', 'cancelled-run'), /run_cancelled/);
  checks.push('cancel-blocks-unsent-browser-actions');
  engine.pause(true);
  await assert.rejects(call('browser_snapshot'), /browser_paused/);
  checks.push('pause-blocks-further-calls');
  // A message sent from the main app normally arrives as a live `user` fact.
  // When that one delivery is lost, the running turn must recover the bubble
  // from history instead of rendering generation without the question.
  const recoveryPanel = await context.newPage();
  await recoveryPanel.goto(`chrome-extension://${extensionId}/sidepanel.html`);
  await recoveryPanel.locator('textarea[aria-label="消息"]').waitFor();
  await waitFor(() => recoveryPanel.locator('.turn').count(), 'Recovery sidebar did not load the conversation');
  uiHistory.push({ type: 'user', run_id: 'orphan-run', content: '主程序发送的消息' });
  for (const socket of apps.clients) if (socket.readyState === 1) socket.send(JSON.stringify({ type: 'session.event', session_id: uiSession, event: { type: 'run_started', run_id: 'orphan-run', event_bus_seq: 900, event_bus_epoch: 'fixture' } }));
  await waitFor(() => recoveryPanel.locator('.user-message').getByText('主程序发送的消息', { exact: true }).count(), 'Sidebar did not recover a missing live user fact from history');
  checks.push('missing-live-user-fact-recovers-from-history');
  for (const socket of apps.clients) if (socket.readyState === 1) socket.send(JSON.stringify({ type: 'session.event', session_id: uiSession, event: { type: 'run_finished', result_status: 'succeeded', run_id: 'orphan-run', event_bus_seq: 901, event_bus_epoch: 'fixture' } }));
  await recoveryPanel.close();
  const report = { passed: true, browser: await context.browser()?.version(), checks, layout, timestamp: new Date().toISOString() };
  await writeFile(resolve(artifactDir, 'browser-smoke.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} catch (error) {
  await writeFile(resolve(artifactDir, 'browser-smoke.json'), JSON.stringify({ passed: false, checks, error: error.stack }, null, 2));
  throw error;
} finally {
  await context?.close().catch(() => {});
  for (const socket of apps.clients) socket.terminate();
  await new Promise(resolve => apps.close(resolve));
  backend.closeAllConnections();
  await new Promise(resolve => backend.close(resolve));
  await engine?.close().catch(() => {});
  await relay.close();
  const verified = resolve(work);
  if (!verified.startsWith(resolve(tmpdir()) + sep) || !basename(verified).startsWith('sugar-browser-smoke-')) throw new Error('Refusing unexpected temporary cleanup target');
  await rm(verified, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 });
}
