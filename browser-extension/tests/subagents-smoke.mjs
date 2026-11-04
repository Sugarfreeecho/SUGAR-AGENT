import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {createRequire} from 'node:module';
import {mkdtemp,mkdir,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'../..'),require=createRequire(resolve(root,'plugins/browser-use/node/package.json'));
const {chromium}=require('playwright'),work=await mkdtemp(resolve(tmpdir(),'sugar-subagents-'));
const artifacts=resolve(root,'browser-extension/artifacts/subagents');await mkdir(artifacts,{recursive:true});
const runtime=spawn(resolve(root,'python/python.exe'),['-u',resolve(import.meta.dirname,'session-runtime-fixture.py'),resolve(work,'backend')],{cwd:root,windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8'}});
let diagnostics='',context,panel;const checks=[],errors=[];
runtime.stderr.on('data',data=>diagnostics=(diagnostics+data).slice(-9000));
const ready=new Promise((yes,no)=>{createInterface({input:runtime.stdout}).on('line',line=>{try{const data=JSON.parse(line);if(data.baseUrl)yes(data);}catch{}});runtime.once('exit',code=>no(Error('Fixture exited '+code+' '+diagnostics)));});
async function waitFor(fn,message){for(let i=0;i<300;i++){if(await fn())return;await new Promise(yes=>setTimeout(yes,40));}throw Error(message);}
try{
  const {baseUrl,sessions:[parent,other]}=await Promise.race([ready,new Promise((_,no)=>setTimeout(()=>no(Error('Startup timeout '+diagnostics)),180000).unref())]);
  async function fixture(body={}){const response=await fetch(baseUrl+'/__fixture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(response.status,200);return response.json();}
  await waitFor(async()=>{try{await fixture();return true;}catch{return false;}},'Fixture not listening');
  const {child_sessions:[child,sibling,grandchild]}=await fixture({models_fail:false,create_subagents:true});
  context=await chromium.launchPersistentContext(resolve(work,'profile'),{channel:'msedge',headless:true,locale:'zh-CN',viewport:{width:400,height:800},args:[`--disable-extensions-except=${resolve(root,'browser-extension/dist')}`,`--load-extension=${resolve(root,'browser-extension/dist')}`]});
  panel=await context.newPage();panel.on('pageerror',error=>errors.push(error.message));
  await panel.goto('chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo/sidepanel.html');
  const {code}=await(await fetch(baseUrl+'/api/browser/v1/pairings',{method:'POST',headers:{Origin:baseUrl,'Content-Type':'application/json'},body:'{}'})).json();
  await panel.evaluate(async({baseUrl,code,parent})=>{await chrome.storage.local.set({'sugar.lastSession':parent,'sugar.preferences':{language:'zh-CN',theme:'dark',design:'selected-m-20261030',autoPageContext:false}});const paired=await chrome.runtime.sendMessage({type:'pair',baseUrl,code});if(!paired.ok)throw Error(paired.error);},{baseUrl,code,parent});
  const input=()=>panel.getByLabel('消息',{exact:true});
  const capsule=()=>panel.getByRole('button',{name:'子 Agent 会话',exact:true});
  const menu=()=>panel.getByRole('menu',{name:'子 Agent 会话',exact:true});
  const title=text=>panel.locator('.session-title').getByText(text,{exact:true});
  async function select(id,name){await capsule().click();await menu().locator(`[data-subagent-id="${id}"]`).click();await title(name).waitFor();await waitFor(async()=>!await input().isDisabled(),'Selected session is not writable');}
  async function emit(target,events){await fixture({emit_events:events.map(event=>({target,event}))});}
  await title('已有会话一').waitFor();await capsule().waitFor();assert.equal(await capsule().innerText(),'子 Agent 3');
  assert.equal(await panel.locator('.topbar').evaluate(node=>node.getBoundingClientRect().height),42);
  checks.push('real-nested-child-directory-is-a-compact-capsule-in-the-existing-42px-titlebar');
  await emit(parent,[{type:'run_started',run_id:'root-live',ephemeral:true},{type:'llm_response_delta',run_id:'root-live',delta:'主会话实时内容',ephemeral:true}]);
  await panel.locator('.commentary,.answer').getByText('主会话实时内容',{exact:true}).waitFor();
  await emit(parent,[...['llm_reasoning_delta','llm_response_delta','tool_call','final','run_finished','run_failed','interaction_requested','context_tokens'].map(type=>({type,session_id:child,agent_id:child,_subagent_forward:true,ephemeral:true,run_id:'root-live',content:'不应串入的子内容',delta:'不应串入的子内容',tool:'child-only-tool',estimated:99999})),{type:'final',session_id:child,run_id:'foreign-untagged',content:'没有标记的外来内容'}]);
  await panel.waitForTimeout(250);
  assert.equal(await panel.getByText('不应串入的子内容',{exact:false}).count(),0);
  assert.equal(await panel.getByText('没有标记的外来内容',{exact:false}).count(),0);
  await panel.locator('.send-button.is-stop').waitFor();
  checks.push('forwarded-child-body-tools-terminal-human-and-context-events-do-not-change-parent-view-or-running-state');
  await fixture({child_question:true});
  await panel.locator('.subagent-picker .subagent-dot.attention').waitFor();
  assert.equal(await panel.getByText('只在子会话显示的提问？',{exact:true}).count(),0);
  for(const theme of ['dark','light','purple']){
    await panel.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);await panel.setViewportSize({width:320,height:720});
    await capsule().click();await menu().waitFor();
    const bounds=await menu().boundingBox();assert.ok(bounds.x>=0&&bounds.x+bounds.width<=320);
    assert.equal(await menu().locator('[data-subagent-id]').count(),3);
    assert.ok(await menu().locator('[data-subagent-id]').evaluateAll(nodes=>nodes.every(node=>node.getBoundingClientRect().height<=32)));
    const dots=await menu().locator('.subagent-dot').evaluateAll(nodes=>nodes.map(node=>({width:node.getBoundingClientRect().width,height:node.getBoundingClientRect().height})));
    assert.ok(dots.every(dot=>dot.width===5&&dot.height===5),JSON.stringify(dots));
    assert.equal(await panel.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await panel.screenshot({path:resolve(artifacts,'capsule-'+theme+'-320.png')});await panel.keyboard.press('Escape');await menu().waitFor({state:'hidden'});
  }
  checks.push('capsule-menu-fits-320px-in-all-three-themes-with-30px-rows-and-keyboard-dismissal');
  await panel.setViewportSize({width:400,height:800});await input().fill('主会话独立草稿');
  await select(child,'[sub] 接口审查');await panel.locator('.user-message').getByText('子任务问题0',{exact:true}).waitFor();
  await panel.locator('.answer').getByText('子任务回答0',{exact:true}).waitFor();
  await panel.getByText('只在子会话显示的提问？',{exact:true}).waitFor();
  assert.equal(await panel.getByText('主会话实时内容',{exact:true}).count(),0);assert.equal(await input().inputValue(),'');
  await input().fill('子会话独立草稿');await panel.getByRole('button',{name:'返回父会话',exact:true}).click();await title('已有会话一').waitFor();
  await waitFor(async()=>await input().inputValue()==='主会话独立草稿','Parent draft lost on rapid switch');
  await select(child,'[sub] 接口审查');assert.equal(await input().inputValue(),'子会话独立草稿');
  checks.push('selecting-real-child-opens-only-owned-history-and-immediate-switch-preserves-separate-drafts');
  checks.push('child-pending-question-only-renders-in-child-view-and-parent-capsule-shows-attention');
  await emit(child,[{type:'run_started',session_id:child,run_id:'child-live',ephemeral:true},{type:'llm_response_delta',session_id:child,run_id:'child-live',delta:'子会话实时输出',ephemeral:true},{type:'final',session_id:grandchild,agent_id:grandchild,_subagent_forward:true,run_id:'grand-live',content:'孙会话不可串入'}]);
  await panel.getByText('子会话实时输出',{exact:true}).waitFor();assert.equal(await panel.getByText('孙会话不可串入',{exact:true}).count(),0);
  await panel.locator('.task-stop').waitFor();
  await select(grandchild,'[sub] 嵌套检查');await panel.locator('.answer').getByText('子任务回答2',{exact:true}).waitFor();
  await panel.getByRole('button',{name:'返回父会话',exact:true}).click();await title('[sub] 接口审查').waitFor();
  checks.push('child-direct-live-stream-works-and-grandchild-has-a-separate-view-with-immediate-parent-navigation');
  await panel.reload();await title('[sub] 接口审查').waitFor();assert.equal(await input().inputValue(),'子会话独立草稿');
  assert.equal(await panel.getByText('已有会话一的历史回答',{exact:true}).count(),0);
  checks.push('reload-restores-selected-child-and-draft-even-though-root-session-list-does-not-contain-child');
  await fixture({rename:{session_id:child,name:'已改名的子任务'}});await title('已改名的子任务').waitFor();
  await panel.locator('.session-title').click();
  const rootMenu=panel.getByRole('dialog',{name:'会话历史'});await rootMenu.waitFor();
  assert.equal(await rootMenu.getByText('已改名的子任务',{exact:true}).count(),0);
  assert.equal(await rootMenu.getByText('已有会话一',{exact:true}).count(),1);await panel.keyboard.press('Escape');
  checks.push('selected-child-title-follows-real-metadata-renames');
  await panel.getByRole('button',{name:'返回父会话',exact:true}).click();await title('已有会话一').waitFor();
  await fixture({history_fail:sibling});await capsule().click();await menu().locator(`[data-subagent-id="${sibling}"]`).click();
  await panel.locator('.feedback-control').getByRole('alert').getByText('测试：请求被拒绝',{exact:true}).waitFor();
  await waitFor(async()=>!await capsule().isDisabled(),'Failed selection did not settle');
  assert.equal(await title('已有会话一').count(),1);assert.equal(await input().inputValue(),'主会话独立草稿');
  assert.equal(await panel.getByText('子任务回答1',{exact:true}).count(),0);await panel.keyboard.press('Escape');await fixture({history_fail:''});
  checks.push('failed-child-selection-retains-parent-view-draft-and-subscription-without-leaking-child-history');
  await emit(parent,[{type:'run_finished',run_id:'root-live',result_status:'succeeded',ephemeral:true}]);
  assert.deepEqual(errors,[]);assert.equal((await fixture()).sessions.length,2);
  await panel.screenshot({path:resolve(artifacts,'parent-restored-400.png')});
  await writeFile(resolve(artifacts,'subagents-regression.json'),JSON.stringify({checks,passed:checks.length,errors},null,2));console.log(JSON.stringify({checks,passed:checks.length},null,2));
}catch(error){if(panel)await panel.screenshot({path:resolve(artifacts,'failure.png')}).catch(()=>{});throw Error(error.message+'\nUI: '+(panel?await panel.locator('body').innerText().catch(()=>''):'')+'\n'+diagnostics,{cause:error});}
finally{if(context)await context.close();runtime.kill();await new Promise(yes=>runtime.exitCode!==null?yes():runtime.once('exit',yes));await rm(work,{recursive:true,force:true,maxRetries:5,retryDelay:250});}
