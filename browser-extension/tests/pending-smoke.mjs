import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {createRequire} from 'node:module';
import {mkdtemp,mkdir,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'../..'),require=createRequire(resolve(root,'plugins/browser-use/node/package.json'));
const {chromium}=require('playwright'),work=await mkdtemp(resolve(tmpdir(),'sugar-pending-'));
const artifacts=resolve(root,'browser-extension/artifacts/pending');await mkdir(artifacts,{recursive:true});
const runtime=spawn(resolve(root,'python/python.exe'),['-u',resolve(import.meta.dirname,'session-runtime-fixture.py'),resolve(work,'backend')],{cwd:root,windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8'}});
let diagnostics='',context,panel;const checks=[],errors=[];
runtime.stderr.on('data',data=>diagnostics=(diagnostics+data).slice(-9000));
const ready=new Promise((yes,no)=>{createInterface({input:runtime.stdout}).on('line',line=>{try{const data=JSON.parse(line);if(data.baseUrl)yes(data);}catch{}});runtime.once('exit',code=>no(Error('Fixture exited '+code+' '+diagnostics)));});
async function waitFor(fn,message){for(let i=0;i<300;i++){if(await fn())return;await new Promise(yes=>setTimeout(yes,40));}throw Error(message);}
try{
  const {baseUrl,sessions:[sid]}=await Promise.race([ready,new Promise((_,no)=>setTimeout(()=>no(Error('Startup timeout '+diagnostics)),180000).unref())]);
  async function fixture(body={}){const response=await fetch(baseUrl+'/__fixture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(response.status,200);return response.json();}
  await waitFor(async()=>{try{await fixture();return true;}catch{return false;}},'Fixture not listening');
  await fixture({models_fail:false,steer_test:true});
  context=await chromium.launchPersistentContext(resolve(work,'profile'),{channel:'msedge',headless:true,locale:'zh-CN',viewport:{width:400,height:800},args:[`--disable-extensions-except=${resolve(root,'browser-extension/dist')}`,`--load-extension=${resolve(root,'browser-extension/dist')}`]});
  panel=await context.newPage();panel.on('pageerror',error=>errors.push(error.message));
  await panel.goto('chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo/sidepanel.html');
  const {code}=await(await fetch(baseUrl+'/api/browser/v1/pairings',{method:'POST',headers:{Origin:baseUrl,'Content-Type':'application/json'},body:'{}'})).json();
  await panel.evaluate(async({baseUrl,code,sid})=>{await chrome.storage.local.set({'sugar.lastSession':sid,'sugar.preferences':{language:'zh-CN',theme:'dark',design:'selected-m-20261030',autoPageContext:false}});const paired=await chrome.runtime.sendMessage({type:'pair',baseUrl,code});if(!paired.ok)throw Error(paired.error);},{baseUrl,code,sid});
  await panel.locator('.session-title').getByText('已有会话一',{exact:true}).waitFor();
  const input=()=>panel.getByLabel('消息',{exact:true});
  const rows=()=>panel.locator('.pending-queue-row');
  const row=text=>rows().filter({has:panel.getByText(text,{exact:true})});
  async function queue(text){await input().fill(text);await input().press('Enter');await row(text).waitFor();await waitFor(async()=>await input().inputValue()==='','Pending composer did not clear');return row(text);}
  await input().fill('换行测试');await input().press('Control+Enter');assert.equal(await input().inputValue(),'换行测试\n');
  await input().press('Shift+Enter');assert.equal(await input().inputValue(),'换行测试\n\n');
  await input().evaluate(node=>node.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',isComposing:true,bubbles:true})));
  assert.equal((await fixture()).calls.length,0);checks.push('ctrl-enter-shift-enter-and-composing-enter-preserve-main-ui-editing-behavior');
  await input().fill('持续执行测试任务');await input().press('Enter');await panel.locator('.send-button.is-stop').waitFor();
  await fixture({message_delay:.45});
  await input().fill('快速连按只提交一次');await input().press('Enter');await input().press('Enter');
  await panel.locator('.pending-steer').getByText('快速连按只提交一次',{exact:true}).waitFor();
  let data=await fixture({message_delay:0});
  assert.equal(data.requests.filter(row=>row.method==='browser.message' && row.params.message==='快速连按只提交一次' && row.params.mode==='pending').length,1);
  assert.equal(data.requests.filter(row=>row.method==='browser.message' && row.params.message==='快速连按只提交一次' && row.params.mode==='append').length,1);
  assert.equal(data.calls.length,1);assert.equal(data.steer_interrupts,0);
  checks.push('first-enter-pending-second-enter-append-even-before-admission-acknowledgement-with-no-duplicate');
  await fixture({steer_consume:true});await panel.locator('.steer-message').getByText('快速连按只提交一次',{exact:true}).waitFor();await fixture({steer_consume:false});
  await panel.locator('input[type=file]').setInputFiles([
    {name:'reference.txt',mimeType:'text/plain',buffer:Buffer.from('reference file')},
    {name:'reference.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aU1cAAAAASUVORK5CYII=','base64')},
  ]);
  await panel.locator('.file-chip').getByText('▤ reference.png',{exact:true}).waitFor();
  await queue('第一条保留附件');await queue('第二条改为打断');await queue('第三条撤回');
  assert.equal(await rows().count(),3);assert.equal((await fixture()).calls.length,1);
  const compact=await rows().evaluateAll(nodes=>nodes.every(node=>node.getBoundingClientRect().height<=32&&getComputedStyle(node.querySelector('.pending-queue-copy>span')).whiteSpace==='nowrap'));
  assert.ok(compact);assert.equal(await panel.locator('.pending-queue>header').count(),0);
  await panel.screenshot({path:resolve(artifacts,'compact-three-400.png')});
  checks.push('pending-has-one-compact-line-per-task-with-no-separate-title-or-status-row');
  checks.push('pending-turns-wait-for-current-run-and-keep-text-and-image-attachments');
  await input().fill('尚未发送的独立草稿');await panel.waitForTimeout(350);await panel.reload();
  await row('第一条保留附件').waitFor();assert.equal(await rows().count(),3);assert.equal(await input().inputValue(),'尚未发送的独立草稿');
  checks.push('reload-restores-durable-queue-in-order-and-preserves-separate-composer');
  await row('第一条保留附件').getByLabel('编辑待发消息',{exact:true}).click();
  const dialog=panel.getByRole('dialog',{name:'编辑待发消息'});await dialog.getByLabel('待发消息内容').fill('第一条已经编辑');
  assert.match(await dialog.innerText(),/reference.txt.*reference.png/);
  await dialog.getByText('保存并排队',{exact:true}).click();await dialog.waitFor({state:'hidden'});
  assert.equal(await rows().first().locator('.pending-queue-copy>span').innerText(),'第一条已经编辑');
  assert.equal(await input().inputValue(),'尚未发送的独立草稿');
  await row('第三条撤回').getByLabel('撤回待发消息').click();await row('第三条撤回').waitFor({state:'hidden'});
  assert.equal((await fixture()).calls.length,1);
  checks.push('editing-updates-original-queue-position-and-retains-attachments-withdrawal-does-not-stop-run');
  for(const theme of ['dark','light','purple']){
    await panel.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
    await panel.setViewportSize({width:320,height:720});
    await row('第二条改为打断').getByLabel('插话方式',{exact:true}).click();
    const menu=panel.getByRole('menu',{name:'插话方式'});await menu.waitFor();
    const bounds=await menu.boundingBox();assert.ok(bounds.x>=0 && bounds.x+bounds.width<=320 && bounds.y>=0);
    assert.equal(await panel.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await panel.screenshot({path:resolve(artifacts,'pending-'+theme+'-320.png')});
    await panel.keyboard.press('Escape');await menu.waitFor({state:'hidden'});
  }
  checks.push('pending-mode-menu-and-all-row-buttons-fit-320px-in-three-themes');
  await row('第二条改为打断').getByLabel('插话方式',{exact:true}).click();
  await panel.locator('[data-send-mode=interrupt]').click();await row('第二条改为打断').getByLabel('立即插话').click();
  await panel.locator('.steer-message').getByText('第二条改为打断',{exact:true}).waitFor();
  data=await fixture();assert.equal(data.steer_interrupts,1);assert.equal(data.calls.length,1);
  assert.ok(data.steer_inputs.some(item=>item.content==='第二条改为打断'));
  assert.equal(await input().inputValue(),'尚未发送的独立草稿');assert.equal(await rows().count(),1);
  checks.push('per-item-interrupt-aborts-real-run-control-and-consumes-input-without-losing-composer');
  await fixture({send_fail:true});await row('第一条已经编辑').getByLabel('立即插话').click();
  await row('第一条已经编辑').getByRole('status').getByText('待重试',{exact:true}).waitFor();
  await panel.reload();await row('第一条已经编辑').waitFor();
  assert.equal(await input().inputValue(),'尚未发送的独立草稿');
  await fixture({send_fail:false,steer_consume:true});await row('第一条已经编辑').getByLabel('立即插话').click();
  await panel.locator('.steer-message').getByText('第一条已经编辑',{exact:true}).waitFor();
  await panel.locator('.steer-message img.attachment-image').waitFor();
  await panel.locator('.steer-message .msg-attachment-name').getByText('reference.png',{exact:true}).waitFor();
  data=await fixture();const canonical=data.steer_inputs.find(item=>Array.isArray(item.content) && item.content.some(block=>block.type==='image'));
  assert.ok(canonical);assert.match(JSON.stringify(canonical),/reference.txt/);assert.equal(data.steer_interrupts,1);
  checks.push('failed-conversion-survives-reload-and-retry-consumes-edited-text-file-and-image-once');
  await queue('自动续发甲');await queue('自动续发乙');
  await fixture({steer_test:false,steer_finish:true});
  await panel.locator('.answer').getByText('answer:自动续发甲',{exact:true}).waitFor();
  await panel.locator('.answer').getByText('answer:自动续发乙',{exact:true}).waitFor();
  await waitFor(async()=>await rows().count()===0,'Finished queue did not clear');
  data=await fixture();assert.deepEqual(data.calls.map(item=>item.message),['持续执行测试任务','自动续发甲','自动续发乙']);
  assert.equal(await panel.locator('.user-message').getByText('自动续发甲',{exact:true}).count(),1);
  assert.equal(await panel.locator('.user-message').getByText('自动续发乙',{exact:true}).count(),1);
  assert.ok(!data.calls.some(item=>item.message==='第三条撤回'));
  checks.push('remaining-pending-turns-auto-run-fifo-with-one-visible-user-bubble-each');
  await fixture({shared_run_followups:['主队列自动续发甲','主队列自动续发乙']});
  await input().fill('同一运行内的第一轮');await input().press('Enter');
  for(const text of ['主队列自动续发甲','主队列自动续发乙']){
    await panel.locator('.user-message').getByText(text,{exact:true}).waitFor();
    await panel.locator('.answer').getByText('answer:'+text,{exact:true}).waitFor();
  }
  const shared=(await fixture({inspect_session:sid})).history.events.filter(event=>event.type==='user'&&event.content.startsWith('主队列自动续发'));
  assert.equal(shared.length,2);assert.equal(shared[0].run_id,shared[1].run_id);
  assert.equal(await panel.locator(`[data-run-id="${shared[0].run_id}"]`).count(),3);
  checks.push('real-main-queue-consumer-keeps-one-run-and-renders-each-followup-as-a-normal-user-bubble');
  await panel.reload();await panel.locator('.session-title').getByText('已有会话一',{exact:true}).waitFor();
  for(const text of ['主队列自动续发甲','主队列自动续发乙'])assert.equal(await panel.locator('.user-message').getByText(text,{exact:true}).count(),1);
  assert.equal(await panel.locator(`[data-run-id="${shared[0].run_id}"]`).count(),3);
  checks.push('shared-run-pending-history-reloads-with-three-distinct-turns-and-no-duplicate-messages');
  assert.equal(await panel.locator('.send-button').count(),1);assert.deepEqual(errors,[]);
  await panel.screenshot({path:resolve(artifacts,'completed-320.png')});
  await writeFile(resolve(artifacts,'pending-regression.json'),JSON.stringify({checks,passed:checks.length,errors},null,2));
  console.log(JSON.stringify({checks,passed:checks.length},null,2));
}catch(error){if(panel)await panel.screenshot({path:resolve(artifacts,'failure.png')}).catch(()=>{});throw Error(error.message+'\nUI: '+(panel?await panel.locator('body').innerText().catch(()=>''):'')+'\n'+diagnostics,{cause:error});}
finally{if(context)await context.close();runtime.kill();await new Promise(yes=>runtime.exitCode!==null?yes():runtime.once('exit',yes));await rm(work,{recursive:true,force:true,maxRetries:5,retryDelay:250});}
