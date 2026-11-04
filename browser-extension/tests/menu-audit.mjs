import assert from 'node:assert/strict';
import http from 'node:http';
import { createRequire } from 'node:module';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, sep, basename } from 'node:path';
import {skillDisplayMessage} from '../src/skill-selection.mjs';

const require = createRequire(new URL('../../plugins/browser-use/node/package.json', import.meta.url));
const { chromium } = require('playwright');
const { wsServer: WebSocketServer } = require('playwright-core/lib/utilsBundle');
const work = await mkdtemp(resolve(tmpdir(), 'sugar-menu-audit-'));
const artifacts = resolve(import.meta.dirname, '../artifacts/menus');
await mkdir(artifacts, { recursive: true });
const sessions = Array.from({ length: 12 }, (_, i) => ({ id: 'session-' + i, name: i ? `会话 ${i} · 检查较长标题的布局与操作` : '浏览器侧栏交互检查', updated_at: new Date().toISOString() }));
const models = Array.from({ length: 16 }, (_, i) => ({ id: 'model-' + i, name: i ? `模型 ${i} · 自定义配置` : 'DeepSeek V4.1 Flash · 用于浏览器任务的自定义长名称' }));
let model = 'model-0', effort = '', workspace = 'D:\\Projects\\SugarAgent', failModel = false, failRename = false, failDelete = false, delaySend = false, pendingSend;
const events = [{ type: 'user', run_id: 'history', content: '检查一下这个扩展的菜单。' }, { type: 'final', run_id: 'history', content: '我会检查会话、工作区、插件和模型选择。' }];
let executionRecords=[],streamActive=false;
let olderAvailable=false,olderEvents=[];
let releaseEntryImage;
let context, panel, permissionMode='ask_for_approval', failPermission=false;
let failUpload=false,holdUpload=false,releaseUpload,sendCount=0;const uploadedFiles=new Map();
let failSkills=false,skillsCatalog=[{name:'repo-engineering',description:'工程规程与代码检查',enabled:true},{name:'research',description:'网页研究与信息整理',enabled:true},{name:'disabled-skill',description:'已停用的 Skill',enabled:false}];
const permissionStatus=()=>({mode:permissionMode,mode_scope:'global',security_enabled:true,can_change:true,available_modes:{ask_for_approval:true,approve_for_me:true,full_access:true}});
const errors = [], checks = [], requests = [];
const server = http.createServer(async (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  if (req.url === '/api/browser/v1/claim') return res.end(JSON.stringify({ token: 'menu-token', browser_id: 'menu-browser' }));
  if (req.url === '/api/browser/v1/human/list') { res.setHeader('Content-Type','application/json');res.end(JSON.stringify({records:[]}));return; }
  if (req.url === '/api/browser/v1/steers') { res.setHeader('Content-Type','application/json');res.end(JSON.stringify({items:[]}));return; }
  if(req.url==='/api/browser/v1/skills') {
    assert.equal(req.headers.authorization,'Bearer menu-token');requests.push({method:'skills.list'});
    if(failSkills){res.statusCode=503;return res.end(JSON.stringify({detail:'测试：Skill 列表暂时不可用'}));}
    return res.end(JSON.stringify({skills:skillsCatalog}));
  }
  if(req.url.startsWith('/api/browser/v1/uploads')) {
    assert.equal(req.headers.authorization,'Bearer menu-token');
    const chunks=[];for await(const chunk of req)chunks.push(chunk);
    const form=await new Response(Buffer.concat(chunks),{headers:{'Content-Type':req.headers['content-type']}}).formData();
    const files=[];for(const file of form.getAll('files'))files.push({name:file.name,type:file.type,size:file.size,bytes:[...new Uint8Array(await file.arrayBuffer())]});
    requests.push({method:'upload',params:Object.fromEntries(new URL(req.url,'http://local.test').searchParams),files});
    if(holdUpload)await new Promise(resolve=>releaseUpload=resolve);
    if(failUpload){res.statusCode=503;return res.end(JSON.stringify({detail:'测试：附件上传失败，请重试。'}));}
    const result=files.map(file=>{const id='upload-'+uploadedFiles.size;uploadedFiles.set(id,file);return{id,name:file.name,size:file.size};});
    return res.end(JSON.stringify({files:result}));
  }
  if (req.url === '/api/browser/v1/session-state') return res.end(JSON.stringify({permissions:permissionStatus(),context_tokens:{estimated:40960,threshold:128000,breakdown:{system_tokens:6000,tools_tokens:4960,message_tokens:30000}}}));
  if (req.url === '/api/browser/v1/permissions') {
    let body='';for await(const c of req)body+=c;const data=JSON.parse(body);requests.push({method:'permission',params:data});
    if(failPermission){res.statusCode=409;return res.end(JSON.stringify({detail:'权限保存失败，请重试'}));}
    if(data.mode==='full_access')assert.equal(data.confirmed_full_access,true);
    permissionMode=data.mode;return res.end(JSON.stringify({permissions:permissionStatus()}));
  }
  if (req.url.startsWith('/api/browser/v1/files')) {
    assert.equal(req.headers.authorization,'Bearer menu-token');
    const params=Object.fromEntries(new URL(req.url,'http://local.test').searchParams),path=params.rel || '';
    requests.push({method:'file.read',params});
    const directory='D:/AI/AI Agent/MyAgent Developer/workspace/zen-gate-obsolete-20261030';
    if(path===directory || path===directory+'/空文件夹') {
      res.setHeader('X-Resource-Type','directory');return res.end(JSON.stringify({name:path.split('/').at(-1),path,parent:path===directory ? null : directory,
        entries:path===directory ? [{name:'空文件夹',type:'directory'},{name:'说明 文档.md',type:'file'},{name:'图 1.png',type:'file'}] : [],truncated:false}));
    }
    res.setHeader('Content-Type','text/markdown; charset=utf-8');res.setHeader('X-File-Name',encodeURIComponent(path.split('/').at(-1) || 'guide.md'));
    return res.end('# 文档预览\n\n这是 **Markdown 文件**。\n\n![相对图片](picture.png)');
  }
  if (req.url === '/public-picture.png') {
    assert.equal(req.headers.authorization,undefined);res.setHeader('Content-Type','image/png');return res.end(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aBWQAAAAASUVORK5CYII=','base64'));
  }
  if (req.url.startsWith('/api/browser/v1/media')) {
    requests.push({method:'media.read',params:Object.fromEntries(new URL(req.url,'http://local.test').searchParams)});
    if(new URL(req.url,'http://local.test').searchParams.get('rel')?.endsWith('entry-late.svg')){
      await new Promise(resolve=>releaseEntryImage=resolve);res.setHeader('Content-Type','image/svg+xml');
      return res.end('<svg xmlns="http://www.w3.org/2000/svg" width="240" height="480"><rect width="240" height="480" fill="#64748b"/></svg>');
    }
    assert.equal(req.headers.authorization,'Bearer menu-token');res.setHeader('Content-Type','image/png');
    return res.end(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aBWQAAAAASUVORK5CYII=','base64'));
  }
  if (req.url === '/api/browser/v1/models') return res.end(JSON.stringify({ profiles: models }));
  if (req.url === '/api/browser/v1/workspaces') return res.end(JSON.stringify({ workspaces: Array.from({ length: 10 }, (_, i) => ({ path: i ? `D:\\Projects\\Workspace-${i}` : workspace, name: i ? `工作区 ${i}` : 'SugarAgent' })) }));
  if (req.url === '/api/browser/v1/plugins') return res.end(JSON.stringify({ plugins: Array.from({ length: 10 }, (_, i) => ({ id: 'plugin-' + i, name: i ? '项目插件 ' + i : '浏览器连接', description: '共享主程序中的插件状态和设置，这是一条较长的描述。', enabled: i % 2 === 0, loaded: i % 2 === 0, settings_section: 'plugins' })) }));
  if (req.url === '/api/browser/v1/workspaces/validate') { let body = ''; for await (const c of req) body += c; return res.end(JSON.stringify({ path: JSON.parse(body).path })); }
  if (req.url === '/api/control/v1/rpc' || req.url === '/api/browser/v1/messages') {
    let body = ''; for await (const c of req) body += c;
    const payload=JSON.parse(body);
    const { method, params } = req.url === '/api/browser/v1/messages' ? {method:'session.send',params:payload} : payload; requests.push({ method, params });
    if(method==='session.send' && (params.selected_skills || []).some(name=>!skillsCatalog.some(skill=>skill.name===name && skill.enabled))){res.statusCode=409;return res.end(JSON.stringify({detail:'所选 Skill 已停用或不可用，请重新选择。'}));}
    if (method === 'session.delete' && failDelete) { res.statusCode = 409; return res.end(JSON.stringify({ ok: false, error: { message: '删除未完成，请重试。' } })); }
    if (method === 'session.archive') sessions.find(s => s.id === params.session_id).archived = params.archived;
    if (method === 'session.delete') sessions.splice(sessions.findIndex(s => s.id === params.session_id), 1);
    if (method === 'session.update') {
      if ((failModel && 'model_profile_id' in params) || (failRename && 'name' in params)) { res.statusCode = 403; return res.end(JSON.stringify({ ok: false, error: { message: '操作未保存，请稍后重试。' } })); }
      if ('model_profile_id' in params) model = params.model_profile_id;
      if ('reasoning_effort' in params) effort = params.reasoning_effort;
      if ('work_dir' in params) workspace = params.work_dir;
      if ('name' in params) sessions.find(s => s.id === params.session_id).name = params.name;
      if ('pinned' in params) sessions.find(s => s.id === params.session_id).pinned = params.pinned;
    }
    const result = method === 'session.list' ? { sessions }
      : method === 'session.history' ? params.before_index ? {events:olderEvents,has_older:false,range_start:0} : {events,has_older:olderAvailable,range_start:olderAvailable ? 1000 : 0}
      : method === 'session.get' ? { session: { ...sessions.find(s => s.id === params.session_id), model_profile_id: model, reasoning_effort: effort, work_dir: workspace, stream_active: streamActive } }
      : method === 'approval.list' ? { approvals: [] }
      : { accepted: true, operation_id: 'send-operation', session_id: sessions[0].id };
    if (method === 'session.send') {
      const runId='sent-run-'+(++sendCount);
      pendingSend = () => {
        const stream = [{ type: 'run_started' }, { type: 'user', content: skillDisplayMessage(params.ui_message,params.selected_skills || []) }, { type: 'final', content: '消息已收到。' }, { type: 'run_finished', result_status: 'succeeded' }];
        for (const [i, event] of stream.entries()) {
          const fact = { ...event, run_id: runId, operation_id: 'send-operation', event_bus_epoch: 'audit', event_bus_seq: i + sendCount*10 };
          events.push(fact); for (const socket of sockets.clients) if (socket.readyState === 1) socket.send(JSON.stringify({ type: 'session.event', session_id: params.session_id, event: fact }));
        }
      };
      if (!delaySend) setTimeout(() => pendingSend(), 100);
    }
    return res.end(JSON.stringify({ ok: true, data: result }));
  }
  res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end('<title>菜单测试网页</title><h1>菜单测试网页</h1>');
});
const sockets = new WebSocketServer({ server });
sockets.on('connection', socket => socket.on('message', raw => { const data = JSON.parse(raw.toString()); if (data.type === 'hello') socket.send(JSON.stringify({ type: 'ready' })); if (data.type === 'subscribe') {socket.send(JSON.stringify({ type: 'subscribed', session_id: data.session_id }));if(executionRecords.length)socket.send(JSON.stringify({type:'session.executions',session_id:data.session_id,records:executionRecords}));} }));
await new Promise(yes => server.listen(0, '127.0.0.1', yes));
const baseUrl = `http://127.0.0.1:${server.address().port}`;
async function waitFor(fn, message) { for (let i = 0; i < 150; i++) { if (await fn()) return; await new Promise(yes => setTimeout(yes, 40)); } throw new Error(message); }
async function bounds(menu) {
  const box = await menu.boundingBox(), viewport = panel.viewportSize();
  assert.ok(box && box.width >= 170 && box.height > 30, 'Menu has collapsed');
  assert.ok(box.x >= 8 && box.y >= 8 && box.x + box.width <= viewport.width - 7 && box.y + box.height <= viewport.height - 7, `Menu is outside viewport: ${JSON.stringify(box)}`);
  assert.equal(await menu.evaluate(node => node.scrollWidth <= node.clientWidth + 1), true, 'Menu overflows horizontally');
  const clipped = await menu.locator('.menu-item').evaluateAll(nodes => nodes.filter(node => node.getBoundingClientRect().width < 120).map(node => node.textContent));
  assert.deepEqual(clipped, [], 'Menu rows inherit icon-button widths');
  const covered = await menu.evaluate(node => {
    const panel = node.getBoundingClientRect();
    return [...node.querySelectorAll('button,input')].filter(item => {
      const rect = item.getBoundingClientRect(), x = rect.x + rect.width / 2, y = rect.y + rect.height / 2;
      if (y < panel.top + 5 || y > panel.bottom - 5 || !rect.width || !rect.height) return false;
      return !item.contains(document.elementFromPoint(x, y));
    }).map(item => item.textContent);
  });
  assert.deepEqual(covered, [], 'Visible menu controls are covered by another layer');
}
try {
  context = await chromium.launchPersistentContext(resolve(work, 'profile'), { channel: 'msedge', headless: true, locale: 'zh-CN', viewport: { width: 400, height: 800 }, args: [`--disable-extensions-except=${resolve(import.meta.dirname, '../dist')}`, `--load-extension=${resolve(import.meta.dirname, '../dist')}`] });
  const site = await context.newPage(); await site.goto(baseUrl);
  panel = await context.newPage(); panel.on('pageerror', error => errors.push(error.message));
  await panel.goto('chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo/sidepanel.html');
  await panel.evaluate(async baseUrl => { await chrome.storage.local.set({ 'sugar.lastSession': 'session-0' }); const reply = await chrome.runtime.sendMessage({ type: 'pair', baseUrl, code: 'audit' }); if (!reply.ok) throw Error(reply.error); }, baseUrl);
  await panel.getByText('我会检查会话、工作区、插件和模型选择。', { exact: true }).waitFor();
  await panel.evaluate(()=>{
    window.fixtureCopied=[];
    Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,value:async text=>window.fixtureCopied.push(text)});
  });
  const copy=panel.locator('.answer-actions .copy-button').first();
  await copy.click();await copy.getByText('已复制',{exact:true}).waitFor();
  await panel.mouse.move(1,1);
  assert.equal(await copy.locator('span').evaluate(node=>getComputedStyle(node).opacity),'1');
  assert.equal(await panel.evaluate(()=>window.fixtureCopied.at(-1)),'我会检查会话、工作区、插件和模型选择。');
  await panel.screenshot({path:resolve(artifacts,'copy-success-400.png')});
  await waitFor(()=>copy.getAttribute('class').then(value=>value.includes('idle')),'Copy feedback did not reset');
  checks.push('copy-success-is-visible-without-hover-and-resets');
  await panel.evaluate(()=>Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,value:async()=>{throw Error('clipboard denied');}}));
  await copy.focus();await panel.keyboard.press('Enter');await copy.getByText('复制失败，请重试',{exact:true}).waitFor();
  assert.equal(await copy.locator('span').evaluate(node=>getComputedStyle(node).opacity),'1');
  checks.push('copy-failure-is-visible-and-keyboard-accessible');
  await panel.evaluate(()=>Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,value:text=>new Promise(yes=>window.releaseCopy=()=>{window.fixtureCopied.push(text);yes();})}));
  await copy.click();await copy.getByText('正在复制…',{exact:true}).waitFor();assert.equal(await copy.isDisabled(),true);
  await panel.evaluate(()=>window.releaseCopy());await copy.getByText('已复制',{exact:true}).waitFor();
  checks.push('copy-retry-confirms-only-after-clipboard-write-settles');
  await panel.evaluate(()=>Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,value:async text=>window.fixtureCopied.push(text)}));
  if(!process.env.SUGAR_TEST_REVEAL_ONLY){
  const menus = ['session-picker', 'header-more', 'workspace-picker', 'context-meter', 'permission-picker', 'model-picker', 'attachment-menu'];
  for (const theme of ['dark', 'light', 'purple']) {
    await panel.locator('.header-more>.popover-trigger').click(); await panel.locator('.theme-options button').nth(['light', 'dark', 'purple'].indexOf(theme)).click(); await panel.keyboard.press('Escape');
    for (const size of [{ width: 400, height: 800 }, { width: 320, height: 720 }, { width: 400, height: 480 }, { width: 320, height: 360 }]) {
      await panel.setViewportSize(size);
      for (const name of menus) {
        await panel.locator('.' + name + '>.popover-trigger').click();
        const menu = panel.locator('.' + name + ' .popover-panel'); await menu.waitFor(); await bounds(menu);
        if(name==='model-picker')assert.deepEqual(await menu.locator('.effort-options button>span').allTextContents(),['default','low','medium','high','xhigh','max']);
        assert.equal(await panel.locator('.popover-panel').count(), 1);
        if (theme === 'dark' && size.width === 400 && size.height === 800) await panel.screenshot({ path: resolve(artifacts, name + '-400.png') });
        await panel.keyboard.press('Escape'); assert.equal(await panel.locator('.popover-panel').count(), 0);
        assert.equal(await panel.locator('.' + name + '>.popover-trigger').evaluate(node => node === document.activeElement), true, 'Escape did not restore focus');
        checks.push(`${theme}-${size.width}x${size.height}-${name}`);
      }
    }
  }
  await panel.setViewportSize({ width: 400, height: 800 });
  await panel.locator('.header-more>.popover-trigger').click(); await panel.locator('.theme-options button').nth(1).click(); await panel.keyboard.press('Escape');
  assert.equal(await panel.locator('.plugin-picker,.stop-button').count(),0);
  await panel.locator('.context-meter>.popover-trigger').click();await panel.getByText('40,960 / 128,000 tokens · 32%',{exact:true}).waitFor();assert.deepEqual(await panel.locator('.context-breakdown dt').allTextContents(),['系统提示','工具','对话']);await panel.keyboard.press('Escape');
  const permission=panel.locator('.permission-picker>.popover-trigger');
  assert.equal(await permission.evaluate(node=>node.parentElement.previousElementSibling?.classList.contains('attachment-menu')),true);
  await permission.click();await panel.getByRole('button',{name:'替我审批',exact:false}).click();await waitFor(()=>Promise.resolve(permissionMode==='approve_for_me'),'Permission was not saved');
  await permission.click();await panel.getByRole('button',{name:'完全访问',exact:false}).click();
  const full=panel.getByRole('dialog',{name:'开启完全访问',exact:true});await full.waitFor();assert.equal(permissionMode,'approve_for_me');
  await full.getByRole('button',{name:'取消',exact:true}).click();assert.equal(permissionMode,'approve_for_me');
  await permission.click();await panel.getByRole('button',{name:'完全访问',exact:false}).click();await full.getByRole('button',{name:'确认开启',exact:true}).click();await waitFor(()=>Promise.resolve(permissionMode==='full_access'),'Confirmed full access did not save');
  failPermission=true;await permission.click();await panel.getByRole('button',{name:'请求批准',exact:false}).click();await panel.getByRole('alert').filter({hasText:'权限保存失败，请重试'}).waitFor();assert.equal(permissionMode,'full_access');
  failPermission=false;await panel.getByRole('button',{name:'请求批准',exact:false}).click();await waitFor(()=>Promise.resolve(permissionMode==='ask_for_approval'),'Permission retry did not work');
  checks.push('context-meter-real-count-and-plugin-entry-removed');checks.push('permissions-next-to-plus-save-readback-failure-retry-and-full-access-confirmation');
  await panel.locator('.session-title').click(); await panel.getByLabel('搜索会话', { exact: true }).fill('会话 8'); await panel.keyboard.press('ArrowDown'); await panel.keyboard.press('Enter');
  await waitFor(() => panel.locator('.session-title').innerText().then(t => t.includes('会话 8')), 'Session dropdown did not select');
  assert.equal(requests.filter(r => r.method === 'session.create').length, 0); checks.push('session-dropdown-search-selects-without-creating');
  await panel.locator('.session-title').click();
  assert.equal(await panel.locator('.session-picker-row time').count(),12);
  assert.equal(await panel.locator('.session-picker-row .history-menu>.popover-trigger').count(),12);
  const row = id => panel.locator('.session-picker-row[data-session-id="'+id+'"]');
  await row('session-2').getByLabel('会话操作', {exact:true}).click();
  assert.equal(await panel.locator('.session-picker .popover-panel').count(),2);
  assert.equal(await panel.locator('.session-picker>.popover-panel').evaluate(node=>node.scrollWidth<=node.clientWidth+1),true,'Nested session menu creates horizontal scrolling');
  await bounds(panel.locator('.session-picker .history-menu .popover-panel'));
  await panel.screenshot({path:resolve(artifacts,'session-row-actions-400.png')});
  await panel.keyboard.press('Escape'); assert.equal(await panel.locator('.session-picker .popover-panel').count(),1);
  await row('session-2').getByLabel('会话操作',{exact:true}).click(); await panel.getByRole('menuitem',{name:'置顶',exact:true}).click();
  await waitFor(()=>Promise.resolve(sessions.find(s=>s.id==='session-2').pinned),'Row pin did not persist');
  await row('session-2').getByLabel('会话操作',{exact:true}).click(); await panel.getByRole('menuitem',{name:'改名',exact:true}).click();
  const renameRow=panel.getByRole('dialog',{name:'修改会话名',exact:true});await renameRow.getByLabel('会话名称',{exact:true}).fill('菜单内重命名');await renameRow.getByRole('button',{name:'保存',exact:true}).click();
  await waitFor(()=>renameRow.count().then(n=>n===0),'Rename dialog did not close after saving');
  await panel.locator('.session-title').click(); await row('session-2').getByTitle('菜单内重命名',{exact:true}).waitFor();
  await row('session-2').getByLabel('会话操作',{exact:true}).click();await panel.getByRole('menuitem',{name:'归档',exact:true}).click();
  await waitFor(()=>row('session-2').count().then(n=>n===0),'Archived session remained in the picker');
  await row('session-3').getByLabel('会话操作',{exact:true}).click();await panel.getByRole('menuitem',{name:'删除',exact:true}).click();
  const deleteRow=panel.getByRole('dialog',{name:'删除会话',exact:true}); failDelete=true;await deleteRow.getByRole('button',{name:'删除',exact:true}).click();await deleteRow.getByRole('alert').getByText('删除未完成，请重试。',{exact:true}).waitFor();
  failDelete=false;await deleteRow.getByRole('button',{name:'删除',exact:true}).click();await waitFor(()=>deleteRow.count().then(n=>n===0),'Delete retry did not finish');
  assert.equal(sessions.some(s=>s.id==='session-3'),false);assert.equal(await panel.evaluate(async()=>(await chrome.storage.local.get('sugar.lastSession'))['sugar.lastSession']),'session-8');
  checks.push('each-session-row-has-time-and-independent-menu-with-nested-escape');
  checks.push('session-row-pin-rename-archive-delete-and-rejected-delete-retry');
  await panel.locator('.model-picker>.popover-trigger').click(); await panel.getByLabel('搜索模型', { exact: true }).fill('no-result'); await panel.getByText('没有匹配的模型。', { exact: true }).waitFor();
  await panel.getByLabel('搜索模型', { exact: true }).fill('模型 12'); await panel.locator('[data-model-id="model-12"]').click(); await waitFor(() => Promise.resolve(model === 'model-12'), 'Model not saved');
  await panel.locator('.model-picker>.popover-trigger').click(); await panel.locator('[data-effort="max"]').click(); await waitFor(() => Promise.resolve(effort === 'max'), 'Effort not saved'); checks.push('model-search-and-last-effort-option-save');
  await panel.locator('.model-picker>.popover-trigger').click();await panel.locator('[data-effort="max"]').scrollIntoViewIfNeeded();await panel.screenshot({path:resolve(artifacts,'model-effort-values-400.png')});await panel.keyboard.press('Escape');
  await panel.locator('.workspace-picker>.popover-trigger').click(); await panel.getByLabel('搜索工作区', { exact: true }).fill('工作区 9'); await panel.locator('.workspace-options button').click(); await waitFor(() => Promise.resolve(workspace.endsWith('Workspace-9')), 'Workspace not saved'); checks.push('workspace-search-and-last-option-save');
  await panel.locator('.context-meter>.popover-trigger').click(); await panel.locator('.model-picker>.popover-trigger').click(); assert.equal(await panel.locator('.popover-panel').count(), 1); await panel.locator('textarea').focus(); assert.equal(await panel.locator('.popover-panel').count(), 0); checks.push('single-menu-and-focus-out-close');
  await panel.locator('.attachment-menu>.popover-trigger').click(); const fileChoice = panel.waitForEvent('filechooser'); await panel.getByRole('menuitem', { name: '附加文件', exact: true }).click(); await (await fileChoice).setFiles([]);
  await panel.locator('.attachment-menu>.popover-trigger').click(); await panel.keyboard.press('End'); await panel.keyboard.press('Enter'); await panel.getByRole('dialog', { name: '选择网页', exact: true }).waitFor(); await panel.keyboard.press('Escape'); assert.equal(await panel.getByRole('dialog', { name: '选择网页', exact: true }).count(), 0); checks.push('file-chooser-and-fast-keyboard-tab-dialog-escape');
  failModel = true; await panel.locator('.model-picker>.popover-trigger').click(); await panel.locator('[data-model-id=""]').click(); await panel.getByRole('alert').waitFor(); await bounds(panel.getByRole('alert')); await panel.keyboard.press('Escape'); await panel.getByLabel('查看问题', { exact: true }).click(); await panel.getByLabel('关闭提示', { exact: true }).click(); failModel = false; checks.push('error-popover-fits-and-closes');
  await panel.locator('.header-more>.popover-trigger').click(); await panel.locator('.header-more .menu-item').filter({ hasText: '会话历史' }).click(); await panel.locator('.history-menu>.popover-trigger').last().click(); await bounds(panel.locator('.history-menu .popover-panel'));
  await panel.getByRole('menuitem', { name: '改名', exact: true }).click(); failRename = true; const rename = panel.getByRole('dialog', { name: '修改会话名', exact: true }); await rename.getByLabel('会话名称', { exact: true }).fill('保留未保存的名字'); await rename.getByRole('button', { name: '保存', exact: true }).click(); await rename.getByRole('alert').waitFor(); assert.equal(await rename.getByLabel('会话名称', { exact: true }).inputValue(), '保留未保存的名字'); await panel.keyboard.press('Escape'); failRename = false; await panel.getByRole('button', { name: '返回', exact: true }).click(); checks.push('last-session-menu-flips-and-rejected-rename-stays-open');
  let seq=2000;
  const emit = facts => { for(const fact of facts)for(const socket of sockets.clients)if(socket.readyState===1)socket.send(JSON.stringify({type:'session.event',session_id:'session-8',event:{...fact,run_id:'thinking-stream',ephemeral:true,event_bus_epoch:'thinking-audit',event_bus_seq:seq++}})); };
  emit([{type:'run_started'},{type:'llm_reasoning_delta',react_iter:1,delta:Array.from({length:70},(_,i)=>'思考内容 '+i+'：检查流式滚动与完成状态。').join('\n')}]);
  const thought=panel.locator('[data-run-id="thinking-stream"] .process-block.reason');await thought.locator('pre').waitFor();
  assert.equal(await thought.locator('pre').evaluate(node=>node.scrollHeight>node.clientHeight+200),true,'Reasoning fixture must actually overflow');
  const pre=thought.locator('pre'), gap=()=>pre.evaluate(node=>node.scrollHeight-node.scrollTop-node.clientHeight);
  await waitFor(async()=>await gap()<2,'Initial reasoning content did not scroll to its end');
  emit([{type:'llm_reasoning_delta',react_iter:1,delta:'\n新增末尾：仍应跟随置底。'}]);await waitFor(()=>pre.textContent().then(text=>text.includes('新增末尾：仍应跟随置底。')),'Reasoning delta was not displayed');await waitFor(async()=>await gap()<2,'Reasoning delta did not follow the bottom');
  await pre.evaluate(node=>{node.scrollTop=0;node.dispatchEvent(new Event('scroll'));});
  emit([{type:'llm_reasoning_delta',react_iter:1,delta:'\n向上阅读时保留位置。'}]);await waitFor(()=>pre.textContent().then(text=>text.includes('向上阅读时保留位置。')),'Reading-position delta was not displayed');assert.equal(await pre.evaluate(node=>node.scrollTop),0);
  await pre.evaluate(node=>{node.scrollTop=node.scrollHeight;node.dispatchEvent(new Event('scroll'));});emit([{type:'llm_reasoning_delta',react_iter:1,delta:'\n返回底部后恢复跟随。'}]);await waitFor(()=>pre.textContent().then(text=>text.includes('返回底部后恢复跟随。')),'Resumed delta was not displayed');await waitFor(async()=>await gap()<2,'Returning to the bottom did not resume following');
  await panel.screenshot({path:resolve(artifacts,'thinking-scroll-bottom-400.png')});
  assert.equal(await panel.locator('.send-button').count(),1);assert.equal(await panel.locator('.stop-button').count(),0);assert.equal(await panel.getByTitle('停止任务',{exact:true}).count(),1);
  await panel.locator('textarea').fill('停止时保留这段草稿');await panel.getByTitle('停止任务',{exact:true}).click();
  await waitFor(async()=>requests.filter(row=>row.method==='session.interrupt').length===1,'Stop request was not received');
  assert.equal(requests.filter(row=>row.method==='session.interrupt').length,1);assert.equal(await panel.locator('textarea').inputValue(),'停止时保留这段草稿');
  emit([{type:'status',content:'正在思考中 一'},{type:'status',content:'正在思考中 二'},{type:'status',content:'正在思考中 三'}]);
  await panel.getByText('正在思考中 三',{exact:true}).waitFor();assert.equal(await panel.getByText('正在思考中 一',{exact:true}).count(),0);
  checks.push('single-send-stop-button-interrupts-and-retains-draft');checks.push('transient-status-replaces-instead-of-accumulating');
  emit([{type:'llm_response_delta',delta:'思考完成，开始回答。'}]);await waitFor(()=>thought.getAttribute('open').then(value=>value===null),'Reasoning did not fold when answer began');
  assert.equal(await panel.locator('[data-run-id="thinking-stream"] .process-heading').getAttribute('aria-expanded'),'true');
  emit([{type:'tool_call',tool:'read_file',tool_call_id:'read',content:'工具结果'}]);
  const response=panel.locator('[data-run-id="thinking-stream"]>.answer').filter({hasText:'思考完成，开始回答。'});await response.waitFor();
  assert.equal(await response.evaluate(node=>!!node.closest('.process,.process-contents')),false);
  await panel.locator('[data-run-id="thinking-stream"] .process-heading').click();assert.equal(await response.isVisible(),true);await panel.locator('[data-run-id="thinking-stream"] .process-heading').click();
  emit([{type:'final',content:'思考与滚动检查完成。'},{type:'run_finished',result_status:'succeeded'}]);await waitFor(()=>panel.locator('[data-run-id="thinking-stream"] .process-heading').getAttribute('aria-expanded').then(value=>value==='false'),'Completed process did not fold');
  assert.equal(await panel.getByText('正在思考中 三',{exact:true}).count(),0);assert.equal(await response.isVisible(),true);
  emit([{type:'context_tokens',estimated:64000,threshold:128000}]);await panel.locator('.context-meter>.popover-trigger').getByText('50%',{exact:true}).waitFor();
  emit([{type:'user',content:'检查文件与图片'},{type:'final',content:[{type:'text',text:'**格式正确**\n\n[查看文档](docs/guide.md)\n\n![生成图片](docs/picture.png)\n\n![远程图片](' + baseUrl.replace('127.0.0.1','localhost') + '/public-picture.png)'},{type:'local_file',local_file:{path:'docs/other.txt',name:'其他文件'}}]}]);
  const result=panel.locator('[data-run-id="thinking-stream"]>.answer').last();await result.locator('strong').getByText('格式正确',{exact:true}).waitFor();
  await waitFor(()=>result.locator('img').evaluateAll(nodes=>nodes.length===2&&nodes.every(n=>n.complete&&n.naturalWidth>0)),'Inline local and remote images were not loaded');
  await result.getByRole('link',{name:'查看文档',exact:true}).click();const preview=panel.getByRole('dialog',{name:'文件预览',exact:true});await preview.getByRole('heading',{name:'文档预览',exact:true}).waitFor();
  assert.ok(await preview.locator('.file-preview>header').evaluate(node=>node.getBoundingClientRect().height<=24 && getComputedStyle(node).paddingTop==='0px'));
  checks.push('file-preview-title-is-one-compact-row-without-page-header-spacing');
  await waitFor(()=>preview.locator('img').evaluateAll(nodes=>nodes.length>0&&nodes.every(n=>n.complete&&n.naturalWidth>0)),'Relative image inside Markdown preview was not loaded');
  assert.ok(requests.some(row=>row.method==='media.read'&&row.params.rel==='docs/picture.png'),'Markdown document images must resolve from its directory');
  await preview.getByRole('link',{name:'下载文件',exact:true}).waitFor();await panel.screenshot({path:resolve(artifacts,'markdown-file-preview-400.png')});await panel.keyboard.press('Escape');
  checks.push('response-outside-process-and-visible-when-process-folded');checks.push('live-context-usage-updates');checks.push('structured-markdown-file-links-inline-images-and-relative-preview-assets');checks.push('remote-images-read-without-paired-credentials');
  await panel.screenshot({path:resolve(artifacts,'thinking-completed-folded-400.png'),animations:'disabled'});
  checks.push('reasoning-scroll-follows-bottom-respects-reading-and-resumes');checks.push('reasoning-folds-before-answer-and-process-folds-at-completion');
  await panel.locator('.header-more>.popover-trigger').click();await panel.locator('.header-more .menu-item').filter({hasText:'设置'}).click();
  await panel.locator('[data-pref-auto-page]').uncheck();await panel.reload();
  await panel.locator('.header-more>.popover-trigger').click();await panel.locator('.header-more .menu-item').filter({hasText:'设置'}).click();
  assert.equal(await panel.locator('[data-pref-auto-page]').isChecked(),false);
  assert.equal(await panel.locator('[data-extension-version]').innerText(),await panel.evaluate(()=>'v'+chrome.runtime.getManifest().version));
  checks.push('settings-displays-installed-extension-manifest-version');await panel.getByRole('button',{name:'返回',exact:true}).click();
  delaySend = true; await panel.locator('textarea').fill('发送后气泡应该立即可见，直到回复结束。'); await panel.getByTitle('发送', { exact: true }).click();
  const bubble = panel.locator('.user-message').filter({ hasText: '发送后气泡应该立即可见' }); await bubble.waitFor(); await panel.getByText('等待执行', { exact: true }).waitFor();
  assert.equal(requests.filter(row=>row.method==='session.send').at(-1).params.automatic,false);
  assert.equal(requests.filter(row=>row.method==='session.send').at(-1).params.browser_context,null);
  checks.push('auto-page-context-setting-persists-and-disables-automatic-association');
  assert.equal(await bubble.evaluate(node => getComputedStyle(node).backgroundColor === getComputedStyle(document.documentElement).backgroundColor), false); await panel.screenshot({ path: resolve(artifacts, 'pending-user-bubble-400.png') });
  pendingSend(); await panel.getByText('消息已收到。', { exact: true }).waitFor(); assert.equal(await bubble.count(), 1); assert.equal(await panel.locator('.user-delivery').count(), 0); checks.push('pending-user-bubble-visible-before-stream-and-reconciled-once');
  await panel.reload(); await panel.getByText('消息已收到。', { exact: true }).waitFor(); assert.equal(await bubble.count(), 1); checks.push('sent-user-bubble-survives-history-reload-without-duplication');
  events.push({ type: 'user', run_id: 'long-message', content: '多行消息也应保留气泡。\n\n' + 'long-token-'.repeat(32) });
  await panel.setViewportSize({ width: 320, height: 720 }); await panel.reload();
  const longBubble = panel.locator('.user-message').filter({ hasText: '多行消息也应保留气泡。' }); await longBubble.waitFor();
  assert.equal(await longBubble.evaluate(node => node.scrollWidth <= node.clientWidth + 1), true); assert.ok((await longBubble.boundingBox()).width < 280); await panel.screenshot({ path: resolve(artifacts, 'long-user-bubble-320.png') }); checks.push('multiline-and-long-token-user-bubble-fits-320px');

  await panel.setViewportSize({width:400,height:800});
  const selectedId=await panel.evaluate(async()=> (await chrome.storage.local.get('sugar.lastSession'))['sugar.lastSession']);
  const responseRun='early-tool-response',responseText='解压完成，我核对一下源码结构。';let responseSeq=1000;
  const emitResponse=fact=>{
    const event={...fact,run_id:fact.run_id || responseRun,event_bus_epoch:'response-order',event_bus_seq:responseSeq++};
    if(!fact.ephemeral)events.push(event);
    for(const socket of sockets.clients)if(socket.readyState===1)socket.send(JSON.stringify({type:'session.event',session_id:selectedId,event}));
  };
  for(const event of [
    {type:'user',content:'核对解压后的源码'},
    {type:'run_started',ephemeral:true},
    {type:'llm_reasoning',react_iter:1,content:'检查源码目录'},
    {type:'llm_response_delta',react_iter:1,stream_seq:8,delta:responseText,ephemeral:true},
    {type:'tool_pending',react_iter:1,tool_call_id:'early-shell',tool:'run_shell',ephemeral:true},
  ])emitResponse(event);
  const responseTurn=panel.locator(`[data-run-id="${responseRun}"]`);
  await responseTurn.locator('.process-block.tool').waitFor();
  const matchingAnswers=()=>responseTurn.locator('.answer').filter({hasText:responseText});
  assert.equal(await matchingAnswers().count(),1);
  for(const event of [
    {type:'llm_response',react_iter:1,content:responseText,metadata:{live_commit:true}},
    {type:'tool_execution_state',react_iter:1,tool_call_id:'early-shell',tool:'run_shell',status:'running',ephemeral:true},
    {type:'tool_call',react_iter:1,tool_call_id:'early-shell',tool:'run_shell',result:'src/',execution_status:'completed'},
    {type:'llm_reasoning',react_iter:2,content:'继续检查源码'},
  ])emitResponse(event);
  await responseTurn.locator('.process-block.tool summary').getByText('已完成',{exact:true}).waitFor();
  await responseTurn.getByText('继续检查源码',{exact:true}).waitFor({state:'attached'});
  assert.equal(await matchingAnswers().count(),1,'The committed snapshot duplicated the pre-tool response');
  assert.equal(await responseTurn.evaluate(node=>Boolean(node.querySelector('.answer').compareDocumentPosition(node.querySelector('.process-block.tool'))&Node.DOCUMENT_POSITION_FOLLOWING)),true);
  await panel.screenshot({path:resolve(artifacts,'early-tool-response-no-duplicate-400.png')});checks.push('early-tool-and-committed-response-render-once-before-tool');
  emitResponse({type:'llm_response_delta',react_iter:2,delta:'第二轮正在输出',ephemeral:true});
  await responseTurn.locator('.answer.streaming').getByText('第二轮正在输出',{exact:true}).waitFor();
  emitResponse({type:'tool_execution_state',react_iter:1,tool_call_id:'early-shell',status:'completed',ephemeral:true});
  emitResponse({type:'llm_response',react_iter:1,content:responseText,ephemeral:true});
  emitResponse({type:'status',content:'迟到事件检查完成',ephemeral:true});
  await responseTurn.locator('.process-heading').getByText('迟到事件检查完成',{exact:true}).waitFor();
  assert.equal(await matchingAnswers().count(),1);
  await responseTurn.locator('.answer.streaming').getByText('第二轮正在输出',{exact:true}).waitFor();checks.push('late-tool-and-response-from-old-iteration-preserve-new-stream');
  for(const event of [
    {type:'llm_response',react_iter:2,content:responseText},
    {type:'tool_pending',react_iter:2,tool_call_id:'second-shell',tool:'run_shell',ephemeral:true},
    {type:'tool_call',react_iter:2,tool_call_id:'second-shell',tool:'run_shell',result:'package.json',execution_status:'completed'},
    {type:'final',content:'源码核对完成。'},
    {type:'run_finished',result_status:'succeeded',ephemeral:true},
  ])emitResponse(event);
  await responseTurn.getByText('源码核对完成。',{exact:true}).waitFor();assert.equal(await matchingAnswers().count(),2,'Different iterations must retain their own responses');checks.push('equal-text-in-different-iterations-is-preserved');
  await panel.reload();await responseTurn.getByText('源码核对完成。',{exact:true}).waitFor();assert.equal(await matchingAnswers().count(),2);
  await responseTurn.locator('.process-heading').click();assert.equal(await responseTurn.locator('.process-block.tool').count(),2);
  assert.equal(await responseTurn.evaluate(node=>Boolean(node.querySelector('.answer').compareDocumentPosition(node.querySelector('.process-block.tool'))&Node.DOCUMENT_POSITION_FOLLOWING)),true);
  await panel.screenshot({path:resolve(artifacts,'early-tool-response-history-reload-400.png')});checks.push('history-reload-preserves-response-tool-order-without-duplicates');

  const timingRun='entry-timing',timed=event=>emitResponse({...event,run_id:timingRun});
  const started=Date.now()/1000;
  timed({type:'user',content:'检查条目用时和展开箭头'});timed({type:'run_started',ephemeral:true});
  timed({type:'llm_reasoning_delta',react_iter:1,delta:'计时中的思考',started_at:started,ephemeral:true});
  const timingTurn=panel.locator(`[data-run-id="${timingRun}"]`),reason=timingTurn.locator('.process-block.reason'),reasonTime=reason.locator('.process-elapsed');
  await reasonTime.waitFor();const firstTime=await reasonTime.innerText();await waitFor(()=>reasonTime.innerText().then(text=>text!==firstTime),'Active reasoning timer did not advance');checks.push('reasoning-item-timer-advances-live');
  const summary=reason.locator('summary'),arrow=summary.locator('.entry-chevron');
  const center=()=>arrow.evaluate(node=>{const r=node.getBoundingClientRect(),s=node.parentElement.getBoundingClientRect();return[r.x+r.width/2-s.x,r.y+r.height/2-s.y];});
  const opened=await center();const svg=await arrow.locator('svg').innerHTML();
  assert.equal(svg,await timingTurn.locator('.process-heading .chevron svg').innerHTML());
  assert.equal(await arrow.locator('svg').getAttribute('width'),'12');assert.equal(await timingTurn.locator('.process-heading .chevron svg').getAttribute('width'),'14');
  assert.equal(await arrow.evaluate(node=>getComputedStyle(node).transformOrigin),'6px 6px');
  assert.equal(await summary.evaluate(node=>getComputedStyle(node,'::before').content),'none');
  await summary.click();await waitFor(()=>reason.getAttribute('open').then(value=>value===null),'Reasoning did not close');
  await panel.waitForTimeout(240);const closed=await center();assert.ok(closed.every((value,index)=>Math.abs(value-opened[index])<.5),'Arrow center moved while closing');
  assert.equal(await arrow.locator('svg').innerHTML(),svg);await panel.screenshot({path:resolve(artifacts,'entry-chevron-closed-400.png')});
  await summary.click();await panel.waitForTimeout(240);const reopened=await center();assert.ok(reopened.every((value,index)=>Math.abs(value-closed[index])<.5),'Arrow center moved while opening');
  await panel.screenshot({path:resolve(artifacts,'entry-chevron-open-400.png')});checks.push('entry-chevron-reuses-aggregate-svg-and-rotates-around-fixed-center');
  timed({type:'llm_reasoning',react_iter:1,content:'计时中的思考',started_at:started,finished_at:started+1.6,duration_ms:1600});
  await reasonTime.getByText('1.6s',{exact:true}).waitFor();
  timed({type:'tool_pending',react_iter:1,tool_call_id:'timed-shell',tool:'run_shell',ephemeral:true});
  timed({type:'tool_execution_state',react_iter:1,tool_call_id:'timed-shell',tool:'run_shell',status:'running',started_at:Date.now()/1000,ephemeral:true});
  const tool=timingTurn.locator('.process-block.tool'),toolTime=tool.locator('.process-elapsed');await tool.getByText('执行中',{exact:true}).waitFor();
  const firstToolTime=await toolTime.innerText();await waitFor(()=>toolTime.innerText().then(text=>text!==firstToolTime),'Active tool timer did not advance');
  timed({type:'tool_call',react_iter:1,tool_call_id:'timed-shell',tool:'run_shell',result:'ok',execution_status:'completed',status:{ok:true,duration_ms:2345}});
  await tool.getByText('已完成',{exact:true}).waitFor();await toolTime.getByText('2.3s',{exact:true}).waitFor();
  assert.equal(await toolTime.getAttribute('data-timing-active'),null);await panel.waitForTimeout(350);assert.equal(await toolTime.innerText(),'2.3s');assert.equal(await reasonTime.innerText(),'1.6s');checks.push('tool-timer-uses-measured-duration-and-both-timers-freeze');
  for(const [index,state] of ['failed','timed_out','interrupted','denied'].entries())timed({type:'tool_call',react_iter:2+index,tool_call_id:'status-'+state,tool:'read_file',execution_status:state,result:'fixture',status:{duration_ms:10}});
  for(const text of ['执行失败','已超时','已停止','已拒绝'])await timingTurn.locator('.process-block.tool summary').getByText(text,{exact:true}).waitFor();
  assert.equal(await timingTurn.locator('.process-block.tool summary').filter({hasText:/completed|timed_out|interrupted/}).count(),0);checks.push('all-completion-and-failure-statuses-use-consistent-localized-labels');
  timed({type:'final',content:'条目计时检查完成'});timed({type:'run_finished',result_status:'succeeded',ephemeral:true});
  await timingTurn.getByText('条目计时检查完成',{exact:true}).waitFor();await panel.reload();await timingTurn.getByText('条目计时检查完成',{exact:true}).waitFor();await timingTurn.locator('.process-heading').click();
  assert.equal(await reasonTime.innerText(),'1.6s');assert.equal(await toolTime.first().innerText(),'2.3s');checks.push('recorded-reasoning-and-tool-times-survive-history-reload');
  for(const theme of ['dark','light','purple']) {
    await panel.locator('.header-more>.popover-trigger').click();await panel.locator('.theme-options button').nth(['light','dark','purple'].indexOf(theme)).click();await panel.keyboard.press('Escape');
    for(const width of [320,400]) {
      await panel.setViewportSize({width,height:800});
      assert.equal(await timingTurn.locator('.process-block>summary').evaluateAll(nodes=>nodes.every(node=>node.scrollWidth<=node.clientWidth+1)),true);
      assert.equal(await timingTurn.locator('.process-block>summary>.entry-chevron').evaluateAll(nodes=>nodes.every(node=>node.clientWidth===12&&node.clientHeight===12)),true);
    }
  }
  await panel.screenshot({path:resolve(artifacts,'entry-times-and-statuses-400.png')});checks.push('entry-timer-and-arrow-layout-fit-three-themes-at-320-and-400');

  const resourceRun='local-resource-links',directory='D:/AI/AI Agent/MyAgent Developer/workspace/zen-gate-obsolete-20261030';
  const resourceText=String.raw`&#x20;[workspace/zen-gate-obsolete-20261030/]\(D:\AI\AI Agent\MyAgent Developer\workspace\zen-gate-obsolete-20261030)

[说明文档]\(D:\AI\AI Agent\MyAgent Developer\workspace\zen-gate-obsolete-20261030\说明 文档.md)

[图片文件](D:\AI\AI Agent\MyAgent Developer\workspace\zen-gate-obsolete-20261030\图 1.png)

![本地截图]\(D:\AI\AI Agent\MyAgent Developer\workspace\zen-gate-obsolete-20261030\图 1.png)

[URI文件](file:///D:/AI/AI%20Agent/MyAgent%20Developer/workspace/zen-gate-obsolete-20261030/guide.md)
`+'\n\n```md\n'+String.raw`[代码示例]\(D:\AI\AI Agent\file.md)`+'\n```';
  emitResponse({run_id:resourceRun,type:'user',content:'检查本地资源链接'});emitResponse({run_id:resourceRun,type:'final',content:resourceText});
  const resources=panel.locator(`[data-run-id="${resourceRun}"]`),folderLink=resources.getByRole('link',{name:'workspace/zen-gate-obsolete-20261030/',exact:true});
  await folderLink.waitFor();assert.equal(await folderLink.getAttribute('data-reference'),directory);
  assert.equal(await resources.locator('pre code a').count(),0);
  await folderLink.click();let folderPreview=panel.getByRole('dialog',{name:'文件夹预览',exact:true});await folderPreview.getByRole('heading',{name:'zen-gate-obsolete-20261030',exact:true}).waitFor();
  await folderPreview.getByRole('button',{name:'空文件夹',exact:true}).click();await panel.getByText('文件夹为空',{exact:true}).waitFor();
  await folderPreview.getByRole('button',{name:'上一级',exact:true}).click();await folderPreview.getByRole('button',{name:'说明 文档.md',exact:true}).waitFor();
  await panel.screenshot({path:resolve(artifacts,'escaped-windows-directory-preview-400.png')});
  await folderPreview.getByRole('button',{name:'说明 文档.md',exact:true}).click();let documentPreview=panel.getByRole('dialog',{name:'文件预览',exact:true});
  await documentPreview.getByRole('heading',{name:'文档预览',exact:true}).waitFor();
  await waitFor(()=>documentPreview.locator('img').evaluateAll(nodes=>nodes.length>0&&nodes.every(node=>node.complete&&node.naturalWidth>0)),'Directory child Markdown image did not resolve');
  assert.ok(requests.some(row=>row.method==='media.read'&&row.params.rel===directory+'/picture.png'));
  await documentPreview.getByRole('link',{name:'下载文件',exact:true}).waitFor();await panel.keyboard.press('Escape');checks.push('exact-escaped-windows-directory-link-browses-children-within-preview');
  await resources.getByRole('link',{name:'说明文档',exact:true}).click();documentPreview=panel.getByRole('dialog',{name:'文件预览',exact:true});await documentPreview.getByRole('heading',{name:'说明 文档.md',exact:true}).waitFor();await panel.keyboard.press('Escape');
  await resources.getByRole('link',{name:'URI文件',exact:true}).click();await panel.getByRole('dialog',{name:'文件预览',exact:true}).getByRole('heading',{name:'guide.md',exact:true}).waitFor();await panel.keyboard.press('Escape');checks.push('windows-files-with-spaces-and-file-uris-open-and-keep-code-literal');
  const localImage=resources.getByRole('img',{name:'本地截图',exact:true});await waitFor(()=>localImage.evaluate(node=>node.complete&&node.naturalWidth>0),'Escaped local image did not render');
  await localImage.click();let imagePreview=panel.getByRole('dialog',{name:'图片预览',exact:true});await waitFor(()=>imagePreview.locator('img').evaluateAll(nodes=>nodes.length>0&&nodes.every(node=>node.complete&&node.naturalWidth>0)),'Inline image click did not open preview');
  await imagePreview.getByRole('link',{name:'下载文件',exact:true}).waitFor();await panel.screenshot({path:resolve(artifacts,'escaped-windows-image-preview-400.png')});await panel.keyboard.press('Escape');
  await resources.getByRole('link',{name:'图片文件',exact:true}).click();imagePreview=panel.getByRole('dialog',{name:'图片预览',exact:true});await imagePreview.getByRole('heading',{name:'图 1.png',exact:true}).waitFor();await panel.keyboard.press('Escape');checks.push('escaped-local-images-render-and-both-image-and-file-links-open-preview');
  await panel.setViewportSize({width:320,height:720});await panel.reload();await folderLink.waitFor();assert.equal(await resources.locator('.answer>.markdown').evaluate(node=>node.scrollWidth<=node.clientWidth+1),true);
  await folderLink.click();await panel.getByRole('dialog',{name:'文件夹预览',exact:true}).getByRole('heading',{name:'zen-gate-obsolete-20261030',exact:true}).waitFor();
  await panel.screenshot({path:resolve(artifacts,'escaped-windows-directory-reload-320.png')});await panel.keyboard.press('Escape');checks.push('local-resource-links-survive-history-reload-and-fit-320px');

  const composer=panel.getByLabel('消息',{exact:true}),pngBytes=[...Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aBWQAAAAASUVORK5CYII=','base64')];
  const paste=async(files,text='')=>composer.evaluate((input,{files,text})=>{
    const data=new DataTransfer();if(text)data.setData('text/plain',text);
    for(const file of files)data.items.add(new File([new Uint8Array(file.bytes)],file.name,{type:file.type}));
    const event=new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true});input.focus();input.dispatchEvent(event);return event.defaultPrevented;
  },{files,text});
  await composer.fill('普通文字');const uploadsBefore=requests.filter(row=>row.method==='upload').length;
  assert.equal(await paste([],'粘贴文字'),false);assert.equal(requests.filter(row=>row.method==='upload').length,uploadsBefore);checks.push('plain-text-paste-retains-native-input-behavior');
  await composer.fill('前后');await composer.evaluate(input=>input.setSelectionRange(1,1));
  assert.equal(await paste([{name:'剪贴板截图.png',type:'image/png',bytes:pngBytes}],'内容'),true);
  await panel.locator('.file-chip').filter({hasText:'剪贴板截图.png'}).waitFor();assert.equal(await composer.inputValue(),'前内容后');
  assert.equal(requests.filter(row=>row.method==='upload').at(-1).files.length,1);
  assert.deepEqual(requests.filter(row=>row.method==='upload').at(-1).files[0].bytes,pngBytes);checks.push('pasted-image-uploads-once-with-original-bytes-and-keeps-mixed-text-at-cursor');
  await paste([{name:'第二张.png',type:'image/png',bytes:pngBytes},{name:'说明.txt',type:'text/plain',bytes:[...Buffer.from('剪贴板文件内容')]}]);
  await panel.locator('.file-chip').filter({hasText:'说明.txt'}).waitFor();assert.equal(await panel.locator('.file-chip').count(),3);
  await panel.screenshot({path:resolve(artifacts,'pasted-images-and-files-320.png')});
  const attachmentIds=[...uploadedFiles.keys()];delaySend=false;
  await panel.getByTitle('发送',{exact:true}).click();await waitFor(()=>Promise.resolve(requests.filter(row=>row.method==='session.send').at(-1).params.attachments?.length===3),'Pasted uploads were not sent as attachments');
  assert.deepEqual(requests.filter(row=>row.method==='session.send').at(-1).params.attachments.map(item=>item.id),attachmentIds);
  await waitFor(()=>panel.locator('.file-chip').count().then(count=>count===0),'Sent upload chips were not cleared');
  await waitFor(()=>panel.getByTitle('发送',{exact:true}).count().then(count=>count===1),'Pasted attachment message did not finish');checks.push('multiple-pasted-files-share-one-batch-and-send-attachment-identities');
  failUpload=true;await composer.fill('上传失败时保留草稿');await paste([{name:'重试.png',type:'image/png',bytes:pngBytes}]);
  await panel.getByText('测试：附件上传失败，请重试。',{exact:true}).waitFor();assert.equal(await composer.inputValue(),'上传失败时保留草稿');assert.equal(await panel.locator('.file-chip').count(),0);
  await panel.getByLabel('关闭提示',{exact:true}).click();failUpload=false;await paste([{name:'重试.png',type:'image/png',bytes:pngBytes}]);
  await panel.locator('.file-chip').filter({hasText:'重试.png'}).waitFor();await panel.getByLabel('移除文件',{exact:true}).click();await waitFor(()=>panel.locator('.file-chip').count().then(count=>count===0),'Pasted attachment could not be removed');checks.push('failed-paste-upload-keeps-draft-and-retry-and-remove-work');
  const originalSession=await panel.evaluate(async()=> (await chrome.storage.local.get('sugar.lastSession'))['sugar.lastSession']);
  const switchedSession=originalSession==='session-0' ? 'session-1' : 'session-0';holdUpload=true;releaseUpload=undefined;
  await paste([{name:'切换期间.png',type:'image/png',bytes:pngBytes}]);await waitFor(()=>Promise.resolve(typeof releaseUpload==='function'),'Delayed paste upload did not start');
  const sendsBefore=requests.filter(row=>row.method==='session.send').length;await composer.press('Enter');assert.equal(requests.filter(row=>row.method==='session.send').length,sendsBefore);
  await paste([{name:'忙碌时.png',type:'image/png',bytes:pngBytes}]);await panel.getByText('正在处理附件或发送消息，请稍候再粘贴。',{exact:true}).waitFor();await panel.getByLabel('关闭提示',{exact:true}).click();checks.push('upload-in-progress-blocks-send-and-explains-a-second-file-paste');
  await panel.locator('.session-title').click();await panel.locator(`[data-session-id="${switchedSession}"] .history-open`).click();await panel.locator('.session-title').getByText(sessions.find(row=>row.id===switchedSession).name,{exact:true}).waitFor();
  holdUpload=false;releaseUpload();await waitFor(()=>panel.evaluate(async id=>(await chrome.storage.session.get('sugar.composer.'+id))['sugar.composer.'+id]?.uploads?.some(item=>item.name==='切换期间.png'),originalSession),'Upload was not retained with original session');assert.equal(await panel.locator('.file-chip').count(),0);
  await panel.locator('.session-title').click();await panel.locator(`[data-session-id="${originalSession}"] .history-open`).click();await panel.locator('.file-chip').filter({hasText:'切换期间.png'}).waitFor();assert.equal(await panel.locator('.file-chip').count(),1);
  await panel.reload();await panel.locator('.file-chip').filter({hasText:'切换期间.png'}).waitFor();assert.equal(await panel.locator('.file-chip').count(),1);checks.push('late-paste-upload-stays-in-original-session-and-survives-reload-without-duplicates');

  const openSkills=async()=>{await panel.getByTitle('附加资料',{exact:true}).click();await panel.getByRole('menuitem',{name:'选择 Skill',exact:true}).click();};
  const skillChip=name=>panel.locator('.skill-chip').filter({hasText:name});
  const createsBeforeSkills=requests.filter(row=>row.method==='session.create').length;
  failSkills=true;await openSkills();await panel.getByText('Skill 列表加载失败：测试：Skill 列表暂时不可用',{exact:true}).waitFor();
  failSkills=false;await panel.locator('.attachment-menu').getByRole('button',{name:'重试',exact:true}).click();
  await panel.getByRole('menuitemcheckbox',{name:/^repo-engineering/}).waitFor();assert.equal(await panel.getByRole('menuitemcheckbox',{name:/^disabled-skill/}).isDisabled(),true);
  await panel.getByLabel('搜索 Skill',{exact:true}).fill('工程');assert.equal(await panel.getByRole('menuitemcheckbox').count(),1);
  await panel.getByLabel('搜索 Skill',{exact:true}).press('ArrowDown');await panel.keyboard.press('Enter');assert.equal(await panel.getByRole('menuitemcheckbox',{name:/^repo-engineering/}).getAttribute('aria-checked'),'true');
  await panel.getByLabel('搜索 Skill',{exact:true}).fill('没有这种技能');await panel.getByText('没有匹配的 Skill。',{exact:true}).waitFor();
  await panel.getByLabel('搜索 Skill',{exact:true}).fill('');await panel.getByRole('menuitemcheckbox',{name:/^research/}).click();
  assert.equal(await panel.locator('.skill-option-check').evaluateAll(nodes=>nodes.every(node=>node.clientWidth===14)),true,'Skill check columns expanded into blank space');
  assert.equal(await panel.locator('.skill-option').evaluateAll(nodes=>nodes.every(node=>node.lastElementChild.getBoundingClientRect().left-node.getBoundingClientRect().left<36)),true,'Skill names are not aligned beside the check');
  await bounds(panel.locator('.attachment-menu>.popover-panel'));await panel.screenshot({path:resolve(artifacts,'skills-search-multiselect-320.png')});
  await panel.locator('.attachment-menu').getByRole('button',{name:'完成',exact:true}).click();await skillChip('repo-engineering').waitFor();await skillChip('research').waitFor();
  assert.equal(requests.filter(row=>row.method==='session.create').length,createsBeforeSkills);checks.push('skill-catalog-retry-search-keyboard-multiselect-and-disabled-state-without-session-creation');
  await panel.locator('.session-title').click();await panel.locator(`[data-session-id="${switchedSession}"] .history-open`).click();await panel.locator('.session-title').getByText(sessions.find(row=>row.id===switchedSession).name,{exact:true}).waitFor();assert.equal(await panel.locator('.skill-chip').count(),0);
  await panel.locator('.session-title').click();await panel.locator(`[data-session-id="${originalSession}"] .history-open`).click();await skillChip('repo-engineering').waitFor();await skillChip('research').waitFor();
  await panel.reload();await skillChip('repo-engineering').waitFor();assert.equal(await panel.locator('.skill-chip').count(),2);checks.push('selected-skills-are-scoped-to-conversation-drafts-and-survive-reload');
  await composer.fill('按选定技能检查项目');await panel.getByTitle('发送',{exact:true}).click();
  await waitFor(()=>Promise.resolve(requests.filter(row=>row.method==='session.send').at(-1).params.selected_skills?.length===2),'Selected Skills were not sent');
  assert.deepEqual(requests.filter(row=>row.method==='session.send').at(-1).params.selected_skills,['repo-engineering','research']);
  assert.equal(requests.filter(row=>row.method==='session.send').at(-1).params.attachments.length,1);
  const skillTurn=panel.locator(`[data-run-id="sent-run-${sendCount}"]`);await skillTurn.getByText('消息已收到。',{exact:true}).waitFor();
  assert.equal(await skillTurn.locator('.user-message').innerText(),'按选定技能检查项目\n\nActivated Skill: repo-engineering, research');
  assert.equal(await skillTurn.getByText('Activated Skill: repo-engineering, research',{exact:true}).count(),1);
  assert.equal(await panel.locator('.skill-chip').count(),0);await panel.reload();await skillTurn.getByText('消息已收到。',{exact:true}).waitFor();assert.equal(await panel.locator('.skill-chip').count(),0);checks.push('skill-selection-sends-with-attachments-clears-on-acceptance-and-matches-live-user-bubble');
  await openSkills();await panel.getByRole('menuitemcheckbox',{name:/^repo-engineering/}).click();await panel.locator('.attachment-menu').getByRole('button',{name:'完成',exact:true}).click();
  await composer.fill('失败保留 Skill 选择');skillsCatalog[0].enabled=false;await panel.getByTitle('发送',{exact:true}).click();
  await panel.getByText('所选 Skill 已停用或不可用，请重新选择。',{exact:true}).waitFor();assert.equal(await composer.inputValue(),'失败保留 Skill 选择');await skillChip('repo-engineering').waitFor();
  await panel.getByLabel('关闭提示',{exact:true}).click();skillsCatalog[0].enabled=true;await panel.getByTitle('发送',{exact:true}).click();
  await waitFor(()=>panel.locator('.skill-chip').count().then(count=>count===0),'Successful Skill retry did not clear selection');await waitFor(()=>panel.getByTitle('发送',{exact:true}).count().then(count=>count===1),'Skill retry did not finish');checks.push('stale-disabled-skill-send-keeps-draft-and-selection-for-retry');
  await openSkills();await panel.getByRole('menuitemcheckbox',{name:/^research/}).click();await panel.locator('.attachment-menu').getByRole('button',{name:'清空选择',exact:true}).click();assert.equal(await panel.getByRole('menuitemcheckbox',{name:/^research/}).getAttribute('aria-checked'),'false');
  await panel.getByRole('menuitemcheckbox',{name:/^research/}).click();await panel.locator('.attachment-menu').getByRole('button',{name:'完成',exact:true}).click();
  await skillChip('research').getByLabel('移除 Skill',{exact:true}).click();assert.equal(await panel.locator('.skill-chip').count(),0);checks.push('skill-selection-clear-and-chip-removal-work');
  await openSkills();await panel.getByRole('menuitemcheckbox',{name:/^research/}).click();await panel.locator('.attachment-menu').getByRole('button',{name:'完成',exact:true}).click();await composer.fill('');
  await panel.getByTitle('发送',{exact:true}).click();await waitFor(()=>Promise.resolve(requests.filter(row=>row.method==='session.send').at(-1).params.message==='请按所选 Skill 开始处理。'),'Skill-only message was not admitted');
  await waitFor(()=>panel.getByTitle('发送',{exact:true}).count().then(count=>count===1),'Skill-only message did not finish');checks.push('skill-only-send-is-supported-with-an-explicit-default-request');
  for(const theme of ['dark','light','purple']) {
    await panel.locator('.header-more>.popover-trigger').click();await panel.locator('.theme-options button').nth(['light','dark','purple'].indexOf(theme)).click();await panel.keyboard.press('Escape');
    for(const [width,height] of [[320,720],[400,480],[320,360]]) {
      await panel.setViewportSize({width,height});await openSkills();await panel.getByRole('menuitemcheckbox',{name:/^repo-engineering/}).waitFor();await bounds(panel.locator('.attachment-menu>.popover-panel'));await panel.keyboard.press('Escape');
    }
  }
  checks.push('skill-picker-search-results-and-actions-fit-three-themes-and-short-narrow-viewports');
  const previousCatalog=skillsCatalog;skillsCatalog=[];await openSkills();await panel.getByText('暂无可用 Skill，请先在主程序添加。',{exact:true}).waitFor();await panel.keyboard.press('Escape');skillsCatalog=previousCatalog;checks.push('empty-skill-catalog-has-an-actionable-state');
  await panel.setViewportSize({width:400,height:800});
  await panel.locator('.header-more>.popover-trigger').click();await panel.locator('.theme-options button').nth(1).click();await panel.keyboard.press('Escape');
  const streamRun='live-tool-stream',emitTool=event=>emitResponse({run_id:streamRun,react_iter:1,stream_seq:80,...event});streamActive=true;
  emitTool({type:'user',content:'逐步生成命令并读取实时输出'});emitTool({type:'run_started',ephemeral:true});
  const streamTurn=panel.locator(`[data-run-id="${streamRun}"]`),streamTool=streamTurn.locator('[data-execution-id="stream-execution"]');
  emitTool({type:'tool_call_delta',execution_id:'stream-execution',execution_runtime_seq:1,index:0,delta_seq:1,name_delta:'run_',arguments_delta:'{"command":"echo ',ephemeral:true});
  await streamTool.locator('.tool-arguments pre').getByText('{"command":"echo ',{exact:true}).waitFor();
  assert.equal(await streamTool.getAttribute('open'),'');assert.equal(await streamTool.locator('summary .process-command').innerText(),'echo');
  await streamTool.evaluate(node=>window.__streamToolNode=node);
  emitTool({type:'tool_call_delta',execution_id:'stream-execution',execution_runtime_seq:2,id:'stream-shell',index:0,delta_seq:2,name_delta:'shell',arguments_delta:'hello"}',ephemeral:true});
  await streamTool.locator('summary .process-command').getByText('echo hello',{exact:true}).waitFor();assert.equal(await streamTurn.locator('.process-block.tool').count(),1);
  assert.equal(await streamTool.evaluate(node=>node===window.__streamToolNode),true);checks.push('tool-name-arguments-and-command-render-before-execution-without-remount-or-duplicate');
  const call={execution_id:'stream-execution',tool_call_id:'stream-shell',tool_call_index:0,tool:'run_shell'};
  emitTool({...call,type:'tool_pending',execution_runtime_seq:3,args:{command:'echo hello'},ephemeral:true});
  emitTool({...call,type:'tool_execution_state',execution_runtime_seq:4,status:'running',started_at:Date.now()/1000,ephemeral:true});
  const lines=Array.from({length:70},(_,i)=>`stdout-${i}\n`).join('');
  emitTool({...call,type:'tool_command_delta',execution_runtime_seq:5,delta_seq:1,delta:lines,raw_delta:lines,stream:'stdout',ephemeral:true});
  await streamTool.locator('.tool-output pre').getByText(/stdout-69/).waitFor();
  const atBottom=()=>streamTool.locator('.tool-scroll').evaluate(node=>node.scrollHeight-node.scrollTop-node.clientHeight<3);
  await waitFor(atBottom,'Tool output did not follow to the bottom');
  await streamTool.locator('.tool-scroll').evaluate(node=>{node.scrollTop=0;node.dispatchEvent(new Event('scroll',{bubbles:true}));});
  emitTool({...call,type:'tool_command_delta',execution_runtime_seq:6,delta_seq:2,delta:'\nSTDERR:\nwarning-live\n',raw_delta:'warning-live\n',stream:'stderr',ephemeral:true});
  await streamTool.locator('.tool-output pre').getByText(/warning-live/).waitFor();assert.equal(await streamTool.locator('.tool-scroll').evaluate(node=>node.scrollTop),0);
  await streamTool.locator('.tool-scroll').evaluate(node=>{node.scrollTop=node.scrollHeight;node.dispatchEvent(new Event('scroll',{bubbles:true}));});
  emitTool({...call,type:'tool_command_delta',execution_runtime_seq:7,delta_seq:3,delta:'\nSTDOUT:\nend-live\n',stream:'stdout',ephemeral:true});
  await streamTool.locator('.tool-output pre').getByText(/end-live/).waitFor();await waitFor(atBottom,'Tool output did not resume following');
  await panel.screenshot({path:resolve(artifacts,'tool-stream-live-400.png')});checks.push('real-stdout-stderr-stream-in-order-follow-bottom-and-respect-manual-scroll');
  const savedOutput=lines+'\nSTDERR:\nwarning-live\n\nSTDOUT:\nend-live\n';
  executionRecords=[{...call,kind:'tool',run_id:streamRun,react_iter:1,stream_seq:80,args:{command:'echo hello'},arguments_raw:'{"command":"echo hello"}',status:'running',executed:true,output:savedOutput,last_runtime_seq:100,last_tool_call_delta_seq:2,last_tool_command_delta_seq:3,execution_started_at:Date.now()/1000}];
  await panel.reload();await streamTool.locator('.tool-output pre').getByText(/end-live/).waitFor();assert.equal(await streamTurn.locator('.process-block.tool').count(),1);
  emitTool({...call,type:'tool_command_delta',execution_runtime_seq:99,delta_seq:3,delta:'end-live\n',ephemeral:true});
  emitTool({...call,type:'tool_command_delta',execution_runtime_seq:101,delta_seq:4,delta:'after-reload\n',ephemeral:true});
  await streamTool.locator('.tool-output pre').getByText(/after-reload/).waitFor();
  assert.equal((await streamTool.locator('.tool-output pre').innerText()).match(/end-live/g).length,1);checks.push('reload-restores-running-tool-parameters-output-and-resumes-once-after-replay');
  emitTool({type:'tool_call_delta',execution_id:'parallel-tool',execution_runtime_seq:102,index:1,id:'stream-read',delta_seq:3,name_delta:'read_file',arguments_delta:'{"path":"README.md"}',ephemeral:true});
  const parallel=streamTurn.locator('[data-execution-id="parallel-tool"]');await parallel.locator('.tool-arguments pre').getByText('{"path":"README.md"}',{exact:true}).waitFor();
  assert.equal(await streamTurn.locator('.process-block.tool').count(),2);assert.equal(await streamTool.locator('summary .process-command').innerText(),'echo hello');checks.push('parallel-tool-streams-keep-distinct-parameters-and-output');
  emitTool({...call,type:'tool_call',execution_runtime_seq:103,args:{command:'echo hello'},result:savedOutput+'after-reload\n',execution_status:'completed',status:{ok:true,duration_ms:2345}});
  await streamTool.locator('summary').getByText('已完成',{exact:true}).waitFor();await waitFor(()=>streamTool.getAttribute('open').then(value=>value===null),'Completed tool did not auto-collapse');
  await streamTool.locator(':scope>summary').click();await streamTool.locator('.tool-result').getByText(/after-reload/).waitFor();
  assert.equal(await streamTool.locator('.tool-result pre').innerText(),savedOutput+'after-reload\n','Final shell output lost its original newlines');
  assert.equal(await streamTool.locator('.tool-output').count(),0);assert.equal(await streamTool.locator('.tool-arguments pre').innerText(),'{\n  "command": "echo hello"\n}');
  await streamTool.locator('.process-elapsed').getByText('2.3s',{exact:true}).waitFor();checks.push('completion-auto-collapses-and-reopening-shows-parameters-command-final-result-without-duplicate-output');
  emitTool({type:'tool_call',execution_id:'parallel-tool',execution_runtime_seq:104,tool_call_id:'stream-read',tool_call_index:1,tool:'read_file',args:{path:'README.md'},result:'独立文件结果',execution_status:'completed'});
  for(const theme of ['dark','light','purple']){
    await panel.locator('.header-more>.popover-trigger').click();await panel.locator('.theme-options button').nth(['light','dark','purple'].indexOf(theme)).click();await panel.keyboard.press('Escape');
    for(const width of [320,400]){await panel.setViewportSize({width,height:720});assert.equal(await streamTool.evaluate(node=>node.scrollWidth<=node.clientWidth+1),true);assert.equal(await streamTool.locator('.tool-scroll').evaluate(node=>node.scrollWidth<=node.clientWidth+1),true);}
  }
  await panel.screenshot({path:resolve(artifacts,'tool-stream-completed-400.png')});checks.push('streaming-tool-details-fit-three-themes-at-320-and-400px');
  streamActive=false;executionRecords=[];emitTool({type:'final',content:'流式工具检查完成'});emitTool({type:'run_finished',result_status:'succeeded',ephemeral:true});
  await panel.setViewportSize({width:400,height:720});
  const reading=panel.locator('.reading'),readingGap=()=>reading.evaluate(node=>node.scrollHeight-node.scrollTop-node.clientHeight);
  await reading.evaluate(node=>{node.scrollTop=node.scrollHeight;node.dispatchEvent(new Event('scroll'));});
  const smoothRun='smooth-body-scroll',smoothEvent=event=>emitResponse({run_id:smoothRun,react_iter:1,...event});
  smoothEvent({type:'user',content:'检查主界面同款平滑滚动'});smoothEvent({type:'run_started',ephemeral:true});
  const smoothTurn=panel.locator(`[data-run-id="${smoothRun}"]`);await smoothTurn.waitFor();await waitFor(async()=>await readingGap()<2,'Initial body viewport was not pinned');
  await reading.evaluate(node=>{const audit=window.__scrollMotion={samples:[],stop:false};const tick=()=>{audit.samples.push({top:node.scrollTop,floor:node.scrollHeight-node.clientHeight});if(!audit.stop)requestAnimationFrame(tick);};requestAnimationFrame(tick);});
  const paragraphs=Array.from({length:35},(_,i)=>`正文段落 ${i}：检查流式内容逐帧跟随，保留阅读位置。`).join('\n\n');
  smoothEvent({type:'llm_response_delta',delta:paragraphs,ephemeral:true});await smoothTurn.locator('.answer').getByText(/正文段落 34/).waitFor();
  await waitFor(async()=>await readingGap()<2,'Smooth body scroll did not converge');
  const motion=await panel.evaluate(()=>{window.__scrollMotion.stop=true;return window.__scrollMotion.samples;});
  const moves=motion.slice(1).map((row,i)=>row.top-motion[i].top).filter(value=>value>.01);
  assert.ok(moves.length>8,'Body content snapped directly to its end');assert.ok(Math.max(...moves)<=20.6,`A frame jumped ${Math.max(...moves)}px`);
  assert.ok(motion.some(row=>row.floor-row.top>10 && row.top>motion[0].top+1),'No intermediate scroll position was rendered');checks.push('body-stream-uses-main-ui-spring-with-bounded-frame-displacement');
  await reading.hover();const beforeWheel=await reading.evaluate(node=>node.scrollTop);await panel.mouse.wheel(0,-24);
  await waitFor(()=>reading.evaluate((node,top)=>node.scrollTop<top-4,beforeWheel),'Upward reader gesture was not applied');
  const readerTop=await reading.evaluate(node=>node.scrollTop);
  smoothEvent({type:'llm_response_delta',delta:'\n\n上翻后新增的正文不能抢走阅读位置。',ephemeral:true});
  await smoothTurn.getByText('上翻后新增的正文不能抢走阅读位置。',{exact:true}).waitFor();await panel.waitForTimeout(250);
  assert.ok(Math.abs(await reading.evaluate(node=>node.scrollTop)-readerTop)<2);await panel.locator('.jump-bottom').waitFor();checks.push('upward-gesture-near-bottom-stops-follow-and-new-content-does-not-reclaim-reader');
  await panel.locator('.jump-bottom').click();await waitFor(async()=>await readingGap()<2,'Jump button did not smoothly resume following');
  assert.equal(await panel.locator('.jump-bottom').count(),0);checks.push('new-content-button-resumes-the-shared-smooth-follower');
  const selectedText=await smoothTurn.locator('.answer p').first().textContent();
  await smoothTurn.locator('.answer p').first().evaluate(node=>{const range=document.createRange();range.selectNodeContents(node);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);});
  await panel.locator('.jump-bottom').waitFor();const selectionTop=await reading.evaluate(node=>node.scrollTop);
  smoothEvent({type:'llm_response_delta',delta:'\n\n选择正文时继续接收内容，保持位置。',ephemeral:true});await smoothTurn.getByText('选择正文时继续接收内容，保持位置。',{exact:true}).waitFor();
  assert.ok(selectedText?.length);assert.ok(Math.abs(await reading.evaluate(node=>node.scrollTop)-selectionTop)<2);
  await panel.evaluate(()=>getSelection().removeAllRanges());await panel.locator('.jump-bottom').click();await waitFor(async()=>await readingGap()<2,'Selection release could not resume');checks.push('text-selection-pauses-follow-without-touching-the-system-clipboard');
  await panel.emulateMedia({reducedMotion:'reduce'});smoothEvent({type:'llm_response_delta',delta:'\n\n'+paragraphs,ephemeral:true});
  await waitFor(async()=>await readingGap()<2,'Reduced motion did not follow to the floor');assert.equal(await reading.getAttribute('data-smooth-follow-owned'),null);
  await panel.emulateMedia({reducedMotion:'no-preference'});checks.push('reduced-motion-disables-glide-without-losing-bottom-follow');
  smoothEvent({type:'final',content:paragraphs+'\n\n平滑滚动检查完成。'});smoothEvent({type:'run_finished',result_status:'succeeded',ephemeral:true});
  await smoothTurn.getByText('平滑滚动检查完成。',{exact:true}).waitFor();await waitFor(()=>reading.getAttribute('data-smooth-follow-owned').then(value=>value===null),'Completed viewport kept an animation loop');
  await panel.screenshot({path:resolve(artifacts,'smooth-scroll-body-400.png')});checks.push('end-of-stream-settles-and-releases-scroll-animation-ownership');
  olderAvailable=true;olderEvents=[{type:'user',run_id:'older-smooth-history',content:'更早的历史消息'},{type:'final',run_id:'older-smooth-history',content:paragraphs}];
  await panel.reload();await panel.getByRole('button',{name:'加载更早的对话',exact:true}).waitFor();
  await reading.evaluate(node=>{node.scrollTop=0;node.dispatchEvent(new Event('scroll'));});
  const historyAnchor=panel.locator('[data-run-id="history"]'),anchorBefore=(await historyAnchor.boundingBox()).y;
  await panel.getByRole('button',{name:'加载更早的对话',exact:true}).click();
  await panel.locator('[data-run-id="older-smooth-history"]').waitFor();await panel.waitForTimeout(150);
  assert.ok(Math.abs((await historyAnchor.boundingBox()).y-anchorBefore)<2,'Prepending history moved the existing reading anchor');
  assert.equal(await reading.getAttribute('data-smooth-follow-owned'),null);checks.push('loading-older-history-preserves-reading-position-and-keeps-live-follow-cancelled');
  olderAvailable=false;
  events.push({type:'user',run_id:'entry-history',content:'直接打开历史会话'}, {type:'final',run_id:'entry-history',content:paragraphs+'\n\n![稍后加载的历史图片](D:/Projects/entry-late.svg)'});
  await panel.reload();const entryTurn=panel.locator('[data-run-id="entry-history"]');await entryTurn.getByText(/正文段落 34/).waitFor();
  await waitFor(()=>Promise.resolve(typeof releaseEntryImage==='function'),'Delayed history image did not start');
  assert.ok(await readingGap()<2,'Opening history did not immediately place the viewport at the bottom');
  await reading.evaluate(node=>{const audit=window.__entryMotion={samples:[],stop:false};const tick=()=>{audit.samples.push({top:node.scrollTop,floor:node.scrollHeight-node.clientHeight});if(!audit.stop)requestAnimationFrame(tick);};requestAnimationFrame(tick);});
  const entryTop=await reading.evaluate(node=>node.scrollTop);releaseEntryImage();
  await waitFor(()=>entryTurn.locator('img').evaluate(node=>node.complete && node.naturalHeight===480),'History image did not finish');
  await waitFor(async()=>await readingGap()<2,'Late history image did not retain instant bottom placement');
  const entryMotion=await panel.evaluate(()=>{window.__entryMotion.stop=true;return window.__entryMotion.samples;});
  assert.ok(await reading.evaluate(node=>node.scrollTop)>entryTop+300,'Image did not change the actual scroll range');
  assert.equal(entryMotion.some(row=>row.top>entryTop+2 && row.floor-row.top>2),false,'Opening history started a scroll glide after late content arrived');
  assert.equal(await reading.getAttribute('data-smooth-follow-owned'),null);checks.push('opening-history-and-late-history-image-snap-to-bottom-without-animation');
  const newLiveRun='after-history-live';emitResponse({run_id:newLiveRun,type:'run_started',ephemeral:true});
  emitResponse({run_id:newLiveRun,type:'llm_response_delta',react_iter:1,delta:paragraphs,ephemeral:true});
  await panel.locator(`[data-run-id="${newLiveRun}"]`).getByText(/正文段落 34/).waitFor();
  await waitFor(()=>reading.getAttribute('data-smooth-follow-owned').then(value=>value==='1'),'New live content did not resume smooth follow after history restoration');
  await waitFor(async()=>await readingGap()<2,'New live content did not converge after history restoration');checks.push('fresh-generation-restores-smooth-follow-after-instant-session-entry');
  }
  await panel.bringToFront();await panel.emulateMedia({reducedMotion:'no-preference'});
  streamActive=true;
  const characterSession=await panel.evaluate(async()=>(await chrome.storage.local.get('sugar.lastSession'))['sugar.lastSession']);let characterSeq=50000;
  const emitCharacter=fact=>{const event={...fact,event_bus_epoch:'character-playback',event_bus_seq:characterSeq++};if(!event.ephemeral)events.push(event);for(const socket of sockets.clients)if(socket.readyState===1)socket.send(JSON.stringify({type:'session.event',session_id:characterSession,event}));};
  async function auditReveal(run,selector,text,send){
    await panel.evaluate(({run,selector})=>{
      const audit=window.__textReveal={samples:[],stop:false};
      const initial=document.querySelector(`[data-run-id="${run}"] ${selector}`)?.textContent.trimEnd();let started=false;
      // The previous LLM phase can occupy the same body node until this event
      // arrives. Start measuring this stream at its first visible change.
      function frame(){const node=document.querySelector(`[data-run-id="${run}"] ${selector}`);if(node){const value=node.textContent.trimEnd();if(value!==initial)started=true;if(started)audit.samples.push(value);}if(!audit.stop)requestAnimationFrame(frame);}
      requestAnimationFrame(frame);
    },{run,selector});
    send();
    await waitFor(()=>panel.locator(`[data-run-id="${run}"] ${selector}`).evaluateAll((nodes,expected)=>nodes.some(node=>node.textContent.trimEnd()===expected),text),'Character reveal did not finish');
    const samples=await panel.evaluate(()=>{window.__textReveal.stop=true;return window.__textReveal.samples;});
    const partial=samples.filter(value=>value.length>0 && value.length<text.length);
    assert.ok(new Set(partial.map(value=>value.length)).size>=3,'Text was rendered as one whole chunk: '+JSON.stringify(samples.map(value=>value.length)));
    for(let i=0;i<samples.length;i++){
      assert.ok(text.startsWith(samples[i]) && !/[\uD800-\uDBFF]$/.test(samples[i]),'Invalid text prefix or split Unicode character');
      if(i)assert.ok(samples[i].length>=samples[i-1].length,'Character playback went backwards');
    }
    return samples.map(value=>value.length);
  }
  const revealRun='character-reveal',revealText='逐字显示中文与 emoji🙂，保留完整内容。'.repeat(35),revealSamples={};
  emitCharacter({run_id:revealRun,type:'run_started',ephemeral:true});
  await panel.locator(`[data-run-id="${revealRun}"]`).waitFor({state:'attached'});
  revealSamples.body=await auditReveal(revealRun,'.answer.streaming .markdown',revealText,()=>emitCharacter({run_id:revealRun,type:'llm_response_delta',react_iter:1,delta:revealText,ephemeral:true}));
  revealSamples.thinking=await auditReveal(revealRun,'.reason pre',revealText,()=>emitCharacter({run_id:revealRun,type:'llm_reasoning_delta',react_iter:2,delta:revealText,ephemeral:true}));
  const revealArgs=JSON.stringify({command:'echo '+revealText});
  revealSamples.arguments=await auditReveal(revealRun,'.tool-arguments pre',revealArgs,()=>emitCharacter({run_id:revealRun,type:'tool_call_delta',react_iter:2,stream_seq:100,tool_call_id:'reveal-shell',execution_id:'reveal-execution',name_delta:'run_shell',arguments_delta:revealArgs,delta_seq:1,ephemeral:true}));
  emitCharacter({run_id:revealRun,type:'tool_pending',tool_call_id:'reveal-shell',tool:'run_shell',args:{command:'echo '+revealText},ephemeral:true});
  emitCharacter({run_id:revealRun,type:'tool_execution_state',tool_call_id:'reveal-shell',status:'running',ephemeral:true});
  revealSamples.output=await auditReveal(revealRun,'.tool-output pre',revealText,()=>emitCharacter({run_id:revealRun,type:'tool_command_delta',tool_call_id:'reveal-shell',stream_seq:100,delta_seq:1,delta:revealText,raw_delta:revealText,stream:'stdout',ephemeral:true}));
  checks.push('body-thinking-tool-arguments-and-output-reveal-over-multiple-unicode-safe-frames');
  emitCharacter({run_id:revealRun,type:'tool_call',tool_call_id:'reveal-shell',tool:'run_shell',result:revealText,execution_status:'completed'});
  emitCharacter({run_id:revealRun,type:'final',content:'**回放完成**'});emitCharacter({run_id:revealRun,type:'run_finished',ephemeral:true});
  await panel.locator(`[data-run-id="${revealRun}"] .answer strong`).filter({hasText:'回放完成'}).waitFor();
  const cancelRun='character-cancel';emitCharacter({run_id:cancelRun,type:'run_started',ephemeral:true});
  emitCharacter({run_id:cancelRun,type:'llm_response_delta',react_iter:1,delta:revealText,ephemeral:true});
  await panel.locator(`[data-run-id="${cancelRun}"] .answer.streaming`).waitFor();
  emitCharacter({run_id:cancelRun,type:'run_interrupted',ephemeral:true});
  await waitFor(()=>panel.locator(`[data-run-id="${cancelRun}"] .answer.streaming .markdown`).evaluate((node,expected)=>node.textContent.trimEnd()===expected,revealText),'Interrupt left text buffered');
  checks.push('interruption-drains-character-playback-without-losing-received-text');
  const restoreRun='character-restore';emitCharacter({run_id:restoreRun,type:'run_started',ephemeral:true});
  emitCharacter({run_id:restoreRun,type:'llm_response_delta',react_iter:1,delta:revealText,ephemeral:true});
  events.push({run_id:restoreRun,type:'llm_response',react_iter:1,content:revealText});
  await panel.addInitScript(({run,text})=>{window.__restoreText=[];const start=performance.now();function frame(){const node=document.querySelector(`[data-run-id="${run}"] .answer .markdown`);if(node)window.__restoreText.push(node.textContent.trimEnd().length);if(performance.now()-start<15000)requestAnimationFrame(frame);}requestAnimationFrame(frame);},{run:restoreRun,text:revealText});
  await panel.reload();await panel.bringToFront();
  await waitFor(()=>panel.locator(`[data-run-id="${restoreRun}"] .answer .markdown`).evaluateAll((nodes,expected)=>nodes.some(node=>node.textContent.trimEnd()===expected),revealText),'Restored active text was not shown in full');
  assert.ok((await panel.evaluate(()=>window.__restoreText)).filter(Boolean).every(length=>length===revealText.length),'History was replayed character by character');
  revealSamples.afterRestore=await auditReveal(restoreRun,'.answer.streaming .markdown',revealText,()=>emitCharacter({run_id:restoreRun,type:'llm_response_delta',react_iter:2,delta:revealText,ephemeral:true}));
  checks.push('restored-active-history-is-instant-and-only-new-content-resumes-character-playback');
  await panel.emulateMedia({reducedMotion:'reduce'});
  emitCharacter({run_id:restoreRun,type:'llm_response_delta',react_iter:3,delta:revealText,ephemeral:true});
  await waitFor(()=>panel.locator(`[data-run-id="${restoreRun}"] .answer.streaming .markdown`).evaluate((node,expected)=>node.textContent.trimEnd()===expected,revealText),'Reduced motion left a character queue');
  checks.push('reduced-motion-shows-full-incoming-text-without-character-playback');
  await writeFile(resolve(artifacts,'character-reveal.json'),JSON.stringify(revealSamples,null,2));
  assert.deepEqual(errors, []); await writeFile(resolve(artifacts, 'menu-audit.json'), JSON.stringify({ passed: checks.length, checks, browser: context.browser()?.version() }, null, 2)); console.log(JSON.stringify({ passed: checks.length, checks }, null, 2));
} catch(error) {
  await writeFile(resolve(artifacts,'menu-audit.json'),JSON.stringify({passed:false,checks,error:error.stack,requests},null,2));
  await panel?.screenshot({path:resolve(artifacts,'failure.png')}).catch(()=>{});
  throw error;
} finally {
  releaseEntryImage?.();
  await context?.close(); for (const socket of sockets.clients) socket.close(); await new Promise(yes => server.close(yes));
  if (!resolve(work).startsWith(resolve(tmpdir()) + sep) || !basename(work).startsWith('sugar-menu-audit-')) throw new Error('Refusing unexpected temporary cleanup target');
  await rm(work, { recursive: true, force: true });
}
