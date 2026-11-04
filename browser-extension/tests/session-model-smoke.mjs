import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { createRequire } from 'node:module';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { extensionFixture } from './extension-fixture.mjs';

const root = resolve(import.meta.dirname, '../..');
const require = createRequire(resolve(root, 'plugins/browser-use/node/package.json'));
const { chromium } = require('playwright');
const work = await mkdtemp(resolve(tmpdir(), 'sugar-session-model-'));
const runtime = spawn(resolve(root, 'python/python.exe'), ['-u', resolve(import.meta.dirname, 'session-runtime-fixture.py'), resolve(work, 'backend')], {
  cwd: root, windowsHide: true, env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
});
let context, panel, diagnostics = '';
runtime.stderr.on('data', chunk => { diagnostics = (diagnostics + chunk).slice(-7000); });
const ready = new Promise((yes, no) => {
  createInterface({ input: runtime.stdout }).on('line', line => { try { const data = JSON.parse(line); if (data.baseUrl) yes(data); } catch {} });
  runtime.once('exit', code => no(new Error(`Fixture exited ${code}: ${diagnostics}`)));
});
const checks = [];
async function waitFor(condition, message, timeout = 15000) {
  const until = Date.now() + timeout;
  while (Date.now() < until) { if (await condition()) return; await new Promise(yes => setTimeout(yes, 60)); }
  throw new Error(message);
}
try {
  const { baseUrl, sessions: [a, b] } = await Promise.race([ready, new Promise((_, no) => setTimeout(() => no(new Error('Fixture startup timed out: ' + diagnostics)), 30000).unref())]);
  const fixture = async (patch = {}) => {
    const response = await fetch(baseUrl + '/__fixture', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch) });
    assert.equal(response.status, 200); return response.json();
  };
  await waitFor(async () => { try { await fixture(); return true; } catch { return false; } }, 'Fixture did not listen');
  const extensionPath = await extensionFixture(work);
  context = await chromium.launchPersistentContext(resolve(work, 'profile'), {
    ...(process.env.SUGAR_TEST_BROWSER_PATH ? { executablePath: process.env.SUGAR_TEST_BROWSER_PATH } : { channel: 'msedge' }),
    headless: true, locale: 'zh-CN', viewport: { width: 400, height: 800 },
    args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
  });
  panel = await context.newPage();
  await panel.goto('chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo/sidepanel.html');
  await panel.evaluate(id => chrome.storage.local.set({ 'sugar.lastSession': id }), a);
  const pairing = await fetch(baseUrl + '/api/browser/v1/pairings', { method: 'POST', headers: { Origin: baseUrl, 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'Session regression browser' }) });
  assert.equal(pairing.status, 200, await pairing.clone().text());
  const { code } = await pairing.json();
  const paired = await panel.evaluate(async ({ baseUrl, code }) => chrome.runtime.sendMessage({ type: 'pair', baseUrl, code }), { baseUrl, code });
  assert.equal(paired.ok, true, JSON.stringify(paired));
  const title = panel.locator('.session-title');
  const modelTrigger = panel.locator('.model-picker>.popover-trigger');
  const model = {
    isEnabled: () => modelTrigger.isEnabled(), isDisabled: () => modelTrigger.isDisabled(),
    inputValue: () => modelTrigger.getAttribute('data-value'),
    selectOption: async value => { await modelTrigger.click(); await panel.locator('button[data-model-id="'+value+'"]').click(); },
  };
  const selected = () => panel.evaluate(async () => (await chrome.storage.local.get('sugar.lastSession'))['sugar.lastSession']);
  const modelStored = id => panel.evaluate(async id => {
    const reply = await chrome.runtime.sendMessage({ type: 'rpc', method: 'session.get', params: { session_id: id, include_runtime: true } });
    if (!reply.ok) throw Error(reply.error); return reply.result.session.model_profile_id;
  }, id);
  const runtimeStored = id => panel.evaluate(async id => {
    const reply = await chrome.runtime.sendMessage({ type: 'rpc', method: 'session.get', params: { session_id: id, include_runtime: true } });
    if (!reply.ok) throw Error(reply.error); return reply.result.session;
  }, id);
  const chooseEffort = async value => { await modelTrigger.click(); await panel.locator('button[data-effort="'+value+'"]').click(); };
  await panel.getByText('已有会话一的历史回答', { exact: true }).waitFor();
  assert.equal(await selected(), a);
  await panel.getByRole('button', { name: '重试加载模型' }).waitFor();
  assert.equal((await fixture()).sessions.length, 2);
  checks.push('model-list-failure-still-opens-existing-session');

  await fixture({ models_fail: false });
  await panel.getByRole('button', { name: '重试加载模型' }).click();
  await waitFor(() => model.isEnabled(), 'Model menu did not recover');
  assert.ok((await fixture()).requests.some(row => row.method === 'models' && row.origin === ''), 'Real worker GET did not exercise the missing-Origin path');
  await model.selectOption('model-b');
  await waitFor(async () => await modelStored(a) === 'model-b' && await model.inputValue() === 'model-b' && await model.isEnabled(), 'Model B did not persist');
  await panel.reload();
  await panel.getByText('已有会话一的历史回答', { exact: true }).waitFor();
  assert.equal(await model.inputValue(), 'model-b');
  await model.selectOption('');
  await waitFor(async () => await modelStored(a) === '' && await model.isEnabled(), 'Default model did not persist');
  assert.equal((await fixture()).sessions.length, 2);
  checks.push('model-switch-and-default-save-readback-reload-without-creation');

  await chooseEffort('high');
  await waitFor(async () => (await runtimeStored(a)).reasoning_effort === 'high' && await model.isEnabled(), 'Reasoning effort did not persist');
  await panel.reload(); await panel.getByText('已有会话一的历史回答', { exact: true }).waitFor();
  assert.equal(await panel.locator('.model-effort').innerText(), 'high');
  await chooseEffort('');
  await waitFor(async () => (await runtimeStored(a)).reasoning_effort === '' && await model.isEnabled(), 'Default effort did not persist');
  checks.push('reasoning-effort-and-model-default-save-readback-reload');

  const workspacePath = (await fixture()).workspace;
  await panel.locator('.workspace-picker>.popover-trigger').click();
  await panel.getByRole('button', { name: '选择其他文件夹…', exact: true }).click();
  await waitFor(async () => (await runtimeStored(a)).work_dir === workspacePath && await model.isEnabled(), 'Picked workspace did not persist');
  assert.match(await panel.locator('.workspace-picker>.popover-trigger').innerText(), /picked-workspace/);
  await panel.locator('.workspace-picker>.popover-trigger').click();
  await panel.getByRole('button', { name: '输入目录路径…', exact: true }).click();
  await panel.getByLabel('工作区路径', { exact: true }).fill(workspacePath + '/missing');
  await panel.getByRole('button', { name: '使用此目录', exact: true }).click();
  await panel.getByRole('alert').getByText('请选择已存在的绝对目录', { exact: true }).waitFor();
  assert.equal((await runtimeStored(a)).work_dir, workspacePath);
  assert.equal((await fixture()).sessions.length, 2);
  assert.equal(await panel.getByLabel('工作区路径', {exact:true}).inputValue(), workspacePath + '/missing');
  await panel.keyboard.press('Escape');
  await fixture({picker_cancelled:true});
  await panel.locator('.workspace-picker>.popover-trigger').click();
  await panel.getByRole('button', {name:'选择其他文件夹…',exact:true}).click();
  await waitFor(()=>panel.locator('.workspace-picker>.popover-trigger').isEnabled(),'Cancelled picker remained busy');
  assert.equal((await runtimeStored(a)).work_dir,workspacePath);
  assert.equal(await panel.getByRole('alert').count(),0);
  await fixture({picker_cancelled:false});
  checks.push('native-workspace-picker-save-and-invalid-path-rollback-without-creation');

  const bWorkspace=(await runtimeStored(b)).work_dir;
  const workspaceWrites=(await fixture()).requests.filter(row=>row.method==='session.update'&&'work_dir' in row.params).length;
  await fixture({picker_delay:0.6});
  await panel.locator('.workspace-picker>.popover-trigger').click();
  await panel.getByRole('button',{name:'选择其他文件夹…',exact:true}).click();
  await title.click();await panel.locator('.history-open').filter({hasText:'已有会话二'}).click();
  await panel.getByText('已有会话二的历史回答',{exact:true}).waitFor();
  await panel.getByRole('alert').getByText('选择目录期间会话已切换，请重新选择目录',{exact:true}).waitFor();
  assert.equal((await runtimeStored(b)).work_dir,bWorkspace);
  assert.equal((await fixture()).requests.filter(row=>row.method==='session.update'&&'work_dir' in row.params).length,workspaceWrites);
  await fixture({picker_delay:0});
  await title.click();await panel.locator('.history-open').filter({hasText:'已有会话一'}).click();await panel.getByText('已有会话一的历史回答',{exact:true}).waitFor();
  checks.push('late-native-picker-result-cannot-change-another-session');

  assert.equal(await panel.locator('.plugin-picker').count(),0);
  await panel.locator('.context-meter>.popover-trigger').click();await panel.getByRole('dialog',{name:'上下文使用占比',exact:true}).waitFor();await panel.keyboard.press('Escape');
  checks.push('plugin-entry-replaced-with-context-meter');

  const managed = await panel.evaluate(async () => {
    const reply = await chrome.runtime.sendMessage({type:'rpc',method:'session.create',params:{name:'菜单管理回归'}});
    if(!reply.ok) throw Error(reply.error);return reply.result.session_id;
  });
  await title.click();
  const managedRow=panel.locator('.session-picker-row[data-session-id="'+managed+'"]');await managedRow.waitFor();
  assert.equal(await managedRow.locator('time').count(),1);
  await managedRow.getByLabel('会话操作',{exact:true}).click();await panel.getByRole('menuitem',{name:'置顶',exact:true}).click();
  await waitFor(async()=>(await fixture()).sessions.find(row=>row.id===managed)?.pinned===true,'Session row pin was not saved by the real backend');
  await managedRow.getByLabel('会话操作',{exact:true}).click();await panel.getByRole('menuitem',{name:'改名',exact:true}).click();
  const renameDialog=panel.getByRole('dialog',{name:'修改会话名',exact:true});await renameDialog.getByLabel('会话名称',{exact:true}).fill('菜单管理已改名');await renameDialog.getByRole('button',{name:'保存',exact:true}).click();
  await waitFor(()=>renameDialog.count().then(n=>n===0),'Session row rename did not finish');
  await title.click();await managedRow.getByTitle('菜单管理已改名',{exact:true}).waitFor();
  await managedRow.getByLabel('会话操作',{exact:true}).click();await panel.getByRole('menuitem',{name:'归档',exact:true}).click();
  await waitFor(()=>managedRow.count().then(n=>n===0),'Archived session did not leave the picker');
  await panel.getByRole('button',{name:'管理会话',exact:true}).click();await panel.getByLabel('显示已归档',{exact:true}).check();
  const archived=panel.locator('.history-item').filter({hasText:'菜单管理已改名'});await archived.getByLabel('会话操作',{exact:true}).click();await panel.getByRole('menuitem',{name:'删除',exact:true}).click();
  const deletion=panel.getByRole('dialog',{name:'删除会话',exact:true});await deletion.getByRole('button',{name:'删除',exact:true}).click();
  await waitFor(()=>deletion.count().then(n=>n===0),'Archived session deletion did not finish');
  assert.equal((await fixture()).sessions.length,2);assert.equal(await selected(),a);
  await panel.getByRole('button',{name:'返回',exact:true}).click();
  checks.push('session-row-time-pin-rename-archive-delete-persist-on-real-control-backend');

  await fixture({ model_write_fail: true });
  await model.selectOption('model-a');
  await panel.getByRole('alert').getByText('测试：模型保存被拒绝').waitFor();
  assert.equal(await model.inputValue(), ''); assert.equal(await modelStored(a), '');
  await fixture({ model_write_fail: false, model_write_noop: true });
  await model.selectOption('model-a');
  await panel.getByRole('alert').getByText('后端未保存模型选择，请重试').waitFor();
  assert.equal(await model.inputValue(), '');
  await fixture({ model_write_noop: false });
  checks.push('rejected-and-unsaved-model-changes-preserve-selection');

  await title.click(); await panel.locator('.history-open').filter({ hasText: '已有会话二' }).click();
  await panel.getByText('已有会话二的历史回答', { exact: true }).waitFor();
  assert.equal(await selected(), b); assert.equal(await model.inputValue(), 'model-b');
  assert.equal(await panel.getByText('已有会话一的历史回答', { exact: true }).count(), 0);
  await fixture({ history_fail: a });
  await title.click(); await panel.locator('.history-open').filter({ hasText: '已有会话一' }).click();
  await panel.getByRole('alert').getByText('测试：请求被拒绝').waitFor();
  assert.equal(await selected(), b); assert.match(await title.innerText(), /已有会话二/);
  await panel.getByLabel('关闭提示', { exact: true }).click();
  await panel.getByText('已有会话二的历史回答', { exact: true }).waitFor();
  assert.equal((await fixture()).sessions.length, 2);
  checks.push('session-switch-selects-id-history-model-and-failure-retains-previous');

  await fixture({ history_fail: '', history_delay: a });
  await title.click(); await panel.locator('.history-open').filter({ hasText: '已有会话一' }).click();
  // While A history is delayed, reopen the dropdown and request B.
  await title.click(); await panel.locator('.history-open').filter({ hasText: '已有会话二' }).click();
  await panel.getByText('已有会话二的历史回答', { exact: true }).waitFor();
  await waitFor(async () => !(await model.isDisabled()), 'Session selection remained loading');
  await new Promise(yes => setTimeout(yes, 650));
  assert.equal(await selected(), b); assert.match(await title.innerText(), /已有会话二/);
  assert.equal((await fixture()).sessions.length, 2);
  checks.push('late-session-history-cannot-replace-newer-selection');

  await fixture({ history_delay: '', create_delay: true });
  const before = (await fixture()).requests.filter(row => row.method === 'session.create').length;
  await panel.getByTitle('新会话', { exact: true }).evaluate(button => { button.click(); button.click(); });
  await waitFor(async () => (await fixture()).sessions.length === 3 && await panel.getByTitle('新会话', { exact: true }).isEnabled(), 'Explicit new session failed');
  const after = (await fixture()).requests.filter(row => row.method === 'session.create').length;
  assert.equal(after - before, 1);
  checks.push('rapid-new-session-clicks-create-one-session');
  await panel.setViewportSize({width:400,height:800});
  await panel.screenshot({path:resolve(root,'browser-extension/artifacts/edge/selected-m-empty-400.png')});

  await fixture({ clear: true, create_delay: false, send_fail: true });
  await panel.evaluate(() => chrome.storage.local.remove('sugar.lastSession'));
  await panel.reload(); await panel.getByText('继续最近的会话', { exact: true }).waitFor();
  await waitFor(() => model.isEnabled(), 'Empty session model menu did not load');
  await model.selectOption('model-b');
  assert.equal(await model.inputValue(), 'model-b');
  assert.equal((await fixture()).sessions.length, 0);
  await chooseEffort('high');
  await panel.locator('.workspace-picker>.popover-trigger').click();
  await panel.getByRole('button', { name: '选择其他文件夹…', exact: true }).click();
  await waitFor(async () => /picked-workspace/.test(await panel.locator('.workspace-picker>.popover-trigger').innerText()), 'Unsent workspace choice did not stage');
  assert.equal((await fixture()).sessions.length, 0);
  checks.push('model-choice-with-no-session-creates-zero-sessions');

  const message = panel.getByLabel('消息', { exact: true });
  await message.fill('验证第一条消息只创建一个会话');
  await fixture({effort_write_fail:true,create_delay:true});
  await panel.getByTitle('发送', { exact: true }).click();
  await panel.locator('.user-message').getByText('验证第一条消息只创建一个会话', {exact:true}).waitFor();
  await panel.getByRole('alert').getByText('测试：思考强度保存被拒绝').waitFor();
  assert.equal(await panel.locator('.user-message').filter({hasText:'验证第一条消息只创建一个会话'}).count(),0);
  assert.equal(await message.inputValue(),'验证第一条消息只创建一个会话');
  assert.equal((await fixture()).sessions.length,1);
  await fixture({effort_write_fail:false,create_delay:false});
  await chooseEffort('high');
  await waitFor(async()=>await model.isEnabled()&&(await runtimeStored(await selected())).reasoning_effort==='high','Retrying effort did not reuse created session');
  checks.push('new-session-settings-rejection-keeps-draft-and-retry-reuses-created-identity');
  await panel.getByTitle('发送', { exact: true }).click();
  await panel.getByRole('alert').getByText('测试：请求被拒绝').waitFor();
  assert.equal(await message.inputValue(), '验证第一条消息只创建一个会话');
  const created = await selected();
  assert.ok(created); assert.equal(await modelStored(created), 'model-b');
  assert.equal((await runtimeStored(created)).reasoning_effort, 'high');
  assert.equal((await runtimeStored(created)).work_dir, workspacePath);
  assert.equal((await fixture()).sessions.length, 1);
  await fixture({ send_fail: false });
  await panel.getByTitle('发送', { exact: true }).click();
  await panel.getByText('answer:验证第一条消息只创建一个会话', { exact: true }).waitFor();
  assert.equal((await fixture()).sessions.length, 1);
  assert.equal((await fixture()).calls.at(-1).session_id, created);
  checks.push('first-send-uses-staged-model-preserves-rejected-draft-and-retry-reuses-session');

  await panel.setViewportSize({width:400,height:800});
  await panel.screenshot({path:resolve(root,'browser-extension/artifacts/edge/selected-m-chat-400.png')});
  assert.equal(await panel.locator('.answer').first().evaluate(node=>getComputedStyle(node).fontSize), '12px');
  assert.equal(await panel.locator('.welcome-actions,.welcome-symbol,.composer-model').count(),0);
  await panel.setViewportSize({width:320,height:720});
  for (const selector of ['.model-picker','.context-meter','.permission-picker','.workspace-picker']) {
    await panel.locator(selector+'>.popover-trigger').click();
    const menu=panel.locator(selector+' .popover-panel');await menu.waitFor();
    const bounds=await menu.boundingBox();assert.ok(bounds.x>=0&&bounds.x+bounds.width<=320&&bounds.y>=0&&bounds.y+bounds.height<=720,selector+' menu overflows narrow sidebar: '+JSON.stringify(bounds));
    await panel.keyboard.press('Escape');
  }
  checks.push('selected-m-popovers-fit-320px-and-dense-body-is-12px');
  if (process.env.SUGAR_TEST_LEGACY_API === '1') {
    const rejects = await panel.evaluate(async () => (await chrome.storage.session.get('sugar.testLegacyApiRejects'))['sugar.testLegacyApiRejects']);
    assert.ok(rejects >= 6, 'Legacy worker did not actually reject the workspace APIs');
    assert.equal(await panel.evaluate(async()=>(await chrome.storage.session.get('sugar.testLegacyMessageRejected'))['sugar.testLegacyMessageRejected']),true);
    checks.push('legacy-worker-rejects-new-routes-and-authenticated-workspace-fallback-remains-functional');
  }

  const output = resolve(root, 'browser-extension/artifacts', process.env.SUGAR_TEST_LEGACY_API === '1' ? 'legacy-worker' : process.env.SUGAR_TEST_BROWSER_PATH ? 'chrome' : 'edge');
  await mkdir(output, { recursive: true });
  await panel.screenshot({ path: resolve(output, 'session-model-regression.png') });
  const result = { browser: context.browser().version(), checks, passed: checks.length };
  await writeFile(resolve(output, 'session-model-regression.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} catch (error) {
  if(panel)await panel.screenshot({path:resolve(root,'browser-extension/artifacts/edge/selected-m-failure.png')}).catch(()=>{});
  const ui = panel ? await panel.locator('body').innerText().catch(() => '') : '';
  throw new Error(error.message + '\nUI: ' + ui + '\n' + diagnostics.slice(-1000), { cause: error });
} finally {
  if (context) await context.close();
  runtime.kill();
  await new Promise(yes => runtime.exitCode !== null ? yes() : runtime.once('exit', yes));
  await rm(work, { recursive: true, force: true, maxRetries: 5, retryDelay: 250 });
}
