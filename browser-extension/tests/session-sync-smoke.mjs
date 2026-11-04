import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {createRequire} from 'node:module';
import {mkdtemp,mkdir,readFile,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve,sep,basename} from 'node:path';
const root=resolve(import.meta.dirname,'../..'),require=createRequire(resolve(root,'plugins/browser-use/node/package.json'));
const {chromium}=require('playwright');
const work=await mkdtemp(resolve(tmpdir(),'sugar-session-sync-'));
const artifacts=resolve(root,'browser-extension/artifacts/sync');await mkdir(artifacts,{recursive:true});
const runtime=spawn(resolve(root,'python/python.exe'),['-u',resolve(import.meta.dirname,'session-runtime-fixture.py'),resolve(work,'backend')],{cwd:root,windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8'}});
let diagnostics='',context,panel;const checks=[],errors=[];
runtime.stderr.on('data',data=>diagnostics=(diagnostics+data).slice(-7000));
const ready=new Promise((yes,no)=>{createInterface({input:runtime.stdout}).on('line',line=>{try{const data=JSON.parse(line);if(data.baseUrl)yes(data);}catch{}});runtime.once('exit',code=>no(Error('Fixture exited '+code+' '+diagnostics)));});
async function waitFor(fn,message){for(let i=0;i<250;i++){if(await fn())return;await new Promise(yes=>setTimeout(yes,40));}throw Error(message);}
const mainPermissions=await readFile(resolve(root,'frontend/src/app/modules/permissions.js'),'utf8');
const modes=['ask_for_approval','approve_for_me','full_access'];
const mainIcons=Object.fromEntries(modes.map(mode=>{const raw=mainPermissions.match(new RegExp(mode+":\\s*'([^']+)'"))?.[1];assert.ok(raw,'Missing main icon '+mode);return[mode,raw];}));
const palette={dark:['rgb(78, 209, 126)','rgb(103, 158, 254)','rgb(247, 173, 49)'],purple:['rgb(166, 227, 161)','rgb(137, 180, 250)','rgb(249, 226, 175)'],light:['rgb(21, 128, 61)','rgb(37, 99, 235)','rgb(180, 83, 9)']};
try{
  const {baseUrl,sessions:[sid]}=await Promise.race([ready,new Promise((_,no)=>setTimeout(()=>no(Error('Fixture startup timeout '+diagnostics)),90000).unref())]);
  async function fixture(body={}){const response=await fetch(baseUrl+'/__fixture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(response.status,200,await response.clone().text());return response.json();}
  await waitFor(async()=>{try{await fixture();return true;}catch{return false;}},'Fixture did not listen');
  await fixture({models_fail:false,auto_name:true,stream_deltas:true,rename:{session_id:sid,name:'新会话'}});
  context=await chromium.launchPersistentContext(resolve(work,'profile'),{channel:'msedge',headless:true,locale:'zh-CN',viewport:{width:400,height:800},args:[`--disable-extensions-except=${resolve(root,'browser-extension/dist')}`,`--load-extension=${resolve(root,'browser-extension/dist')}`]});
  panel=await context.newPage();panel.on('pageerror',error=>errors.push(error.message));
  await panel.addInitScript(()=>{window.__focusEvents=[];const record=event=>window.__focusEvents.push({event:event.type,visible:document.visibilityState,focused:document.hasFocus()});for(const type of ['focus','blur'])window.addEventListener(type,record);document.addEventListener('visibilitychange',record);});
  await panel.goto('chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo/sidepanel.html');
  const pairing=await fetch(baseUrl+'/api/browser/v1/pairings',{method:'POST',headers:{Origin:baseUrl,'Content-Type':'application/json'},body:'{}'});const {code}=await pairing.json();
  await panel.evaluate(async({baseUrl,code,sid})=>{await chrome.storage.local.set({'sugar.lastSession':sid,'sugar.preferences':{language:'zh-CN',theme:'dark',design:'selected-m-20261030',autoPageContext:false}});const paired=await chrome.runtime.sendMessage({type:'pair',baseUrl,code});if(!paired.ok)throw Error(paired.error);window.receivedFacts=[];window.testPort=chrome.runtime.connect({name:'sugaragent-sidepanel'});window.testPort.onMessage.addListener(message=>{if(message.type==='session.event')window.receivedFacts.push(message.event);});},{baseUrl,code,sid});
  const title=panel.locator('.session-title'),trigger=panel.locator('.permission-picker>.popover-trigger');
  await title.getByText('新会话',{exact:true}).waitFor();
  await fixture({rename:{session_id:sid,name:'主界面修改的标题'}});await title.getByText('主界面修改的标题',{exact:true}).waitFor();
  await title.click();await panel.locator(`[data-session-id="${sid}"] strong`).getByText('主界面修改的标题',{exact:true}).waitFor();await panel.keyboard.press('Escape');checks.push('main-app-rename-syncs-header-and-session-menu-without-reload');
  for(const text of ['第一轮同步验证','第二轮同步验证','第三轮同步验证']){
    await panel.getByLabel('消息',{exact:true}).fill(text);await panel.getByTitle('发送',{exact:true}).click();
    await panel.locator('.answer').getByText('answer:'+text,{exact:true}).waitFor();await panel.getByTitle('发送',{exact:true}).waitFor();
    await title.getByText('自动命名：'+text,{exact:true}).waitFor();
    assert.equal(await panel.locator('.user-message').filter({hasText:text}).count(),1);
  }
  const facts=await panel.evaluate(()=>window.receivedFacts);
  assert.equal(new Set(facts.filter(event=>event.type==='run_started').map(event=>event.run_id)).size,3);
  assert.ok(facts.filter(event=>event.type==='llm_response_delta').length>=9);
  assert.equal(new Set(facts.filter(event=>event.type==='run_finished').map(event=>event.run_id)).size,3);
  checks.push('three-consecutive-turns-deliver-live-deltas-and-finals-across-production-stream-close');checks.push('asynchronous-title-after-terminal-updates-without-opening-menu');
  await panel.screenshot({path:resolve(artifacts,'three-turns-and-title-400.png')});
  async function assertIcon(mode,color){
    await panel.locator('.permission-picker.permission-'+mode).waitFor();
    const actual=await trigger.locator(':scope>svg').first().evaluate(svg=>[...svg.children].map(node=>({tag:node.tagName,d:node.getAttribute('d'),r:node.getAttribute('r'),stroke:node.getAttribute('stroke')})));
    const expected=await panel.evaluate(raw=>{const div=document.createElement('div');div.innerHTML='<svg>'+raw+'</svg>';return[...div.firstChild.children].map(node=>({tag:node.tagName,d:node.getAttribute('d'),r:node.getAttribute('r'),stroke:node.getAttribute('stroke')}));},mainIcons[mode]);
    assert.deepEqual(actual,expected,'Permission icon differs from main UI: '+mode);
    if(color)assert.equal(await trigger.evaluate(node=>getComputedStyle(node).color),color);
  }
  for(const theme of ['dark','light','purple']){
    await panel.locator('.header-more>.popover-trigger').click();await panel.locator('.theme-options button').nth(['light','dark','purple'].indexOf(theme)).click();await panel.keyboard.press('Escape');
    for(const [index,mode] of modes.entries()){
      await fixture({permission_mode:mode,session_id:sid});await assertIcon(mode,palette[theme][index]);
      await trigger.click();const option=panel.locator(`[data-permission-mode="${mode}"]`);assert.equal(await option.getAttribute('aria-pressed'),'true');assert.equal(await option.evaluate(node=>getComputedStyle(node).color),palette[theme][index]);await panel.keyboard.press('Escape');
      await panel.screenshot({path:resolve(artifacts,`permission-${theme}-${mode}-400.png`)});
    }
  }
  checks.push('all-main-ui-shield-paths-and-three-theme-semantic-colors-match');checks.push('external-global-permission-changes-arrive-after-turn-close');
  await fixture({permission_mode:'ask_for_approval',session_id:sid});await assertIcon('ask_for_approval');
  await trigger.click();await panel.locator('[data-permission-mode="approve_for_me"]').click();await assertIcon('approve_for_me');
  checks.push('sidebar-permission-selection-changes-icon-and-preserves-main-mode');
  await fixture({permission_mode:'ask_for_approval',session_id:sid,state_delay:.7});
  const heldBefore=(await fixture()).requests.filter(row=>row.method==='state_response_held').length;
  await trigger.click();await waitFor(()=>fixture().then(data=>data.requests.filter(row=>row.method==='state_response_held').length>heldBefore),'Snapshot was not delayed');
  await fixture({permission_mode:'full_access',session_id:sid});await assertIcon('full_access');await new Promise(yes=>setTimeout(yes,850));await assertIcon('full_access');await panel.keyboard.press('Escape');await fixture({state_delay:0});
  checks.push('late-snapshot-cannot-roll-back-newer-global-permission-event');
  await fixture({permission_mode:'ask_for_approval',session_id:sid,permission_delay:.7});
  const writesBefore=(await fixture()).requests.filter(row=>row.method==='permission_response_held').length;
  await trigger.click();await panel.locator('[data-permission-mode="approve_for_me"]').click();
  await waitFor(()=>fixture().then(data=>data.requests.filter(row=>row.method==='permission_response_held').length>writesBefore),'Permission receipt was not delayed');
  await fixture({permission_mode:'full_access',session_id:sid});await assertIcon('full_access');await new Promise(yes=>setTimeout(yes,850));await assertIcon('full_access');await fixture({permission_delay:0});
  checks.push('late-write-receipt-keeps-a-newer-change-from-main-ui');
  await panel.setViewportSize({width:320,height:720});await trigger.waitFor();assert.equal(await trigger.locator(':scope>span').isVisible(),false);await assertIcon('full_access');
  await panel.screenshot({path:resolve(artifacts,'permission-full-320.png')});checks.push('narrow-sidebar-keeps-visible-stateful-colored-icon');
  await panel.reload();await title.getByText('自动命名：第三轮同步验证',{exact:true}).waitFor();await assertIcon('full_access');
  await panel.getByLabel('消息',{exact:true}).fill('重开侧栏后的第四轮');await panel.getByTitle('发送',{exact:true}).click();await panel.locator('.answer').getByText('answer:重开侧栏后的第四轮',{exact:true}).waitFor();await title.getByText('自动命名：重开侧栏后的第四轮',{exact:true}).waitFor();checks.push('sidebar-reopen-retains-title-permission-and-next-turn-stream');
  await panel.bringToFront();await panel.getByLabel('消息',{exact:true}).focus();await waitFor(()=>fixture().then(data=>data.attention_active),'Focused sidebar was not reported through the authenticated socket');
  for(const notify_reason of ['completed','failed','pending'])assert.equal((await fixture({notify_reason})).notifications.length,0);
  checks.push('focused-extension-suppresses-completion-failure-and-pending-system-notifications');
  const webpage=await context.newPage();await webpage.goto(baseUrl);await webpage.bringToFront();
  // Playwright forces headless targets to report focus simultaneously. Release
  // that override on the backgrounded extension to exercise its real blur path.
  const focusProtocol=await context.newCDPSession(panel);await focusProtocol.send('Emulation.setFocusEmulationEnabled',{enabled:false});
  await waitFor(()=>fixture().then(data=>!data.attention_active),'Switching to a normal webpage did not release sidebar focus').catch(async error=>{const details={panel:await panel.evaluate(()=>({visible:document.visibilityState,focused:document.hasFocus(),events:window.__focusEvents})),page:await webpage.evaluate(()=>({visible:document.visibilityState,focused:document.hasFocus()})),backend:await fixture()};await writeFile(resolve(artifacts,'focus-diagnostics.json'),JSON.stringify(details,null,2));throw error;});
  assert.equal((await fixture({notify_reason:'completed'})).notifications.length,1);assert.equal((await fixture({notify_reason:'pending'})).notifications.length,2);
  checks.push('normal-webpage-focus-restores-notifications-while-extension-remains-open');
  await panel.bringToFront();await focusProtocol.send('Emulation.setFocusEmulationEnabled',{enabled:true});await panel.getByLabel('消息',{exact:true}).focus();await waitFor(()=>fixture().then(data=>data.attention_active),'Returning to extension did not renew focus');
  const codeAgain=(await(await fetch(baseUrl+'/api/browser/v1/pairings',{method:'POST',headers:{Origin:baseUrl,'Content-Type':'application/json'},body:'{}'})).json()).code;
  await panel.evaluate(async({baseUrl,code})=>{const reply=await chrome.runtime.sendMessage({type:'pair',baseUrl,code});if(!reply.ok)throw Error(reply.error);},{baseUrl,code:codeAgain});
  await waitFor(()=>fixture().then(data=>data.attention_active && data.attention_surfaces===1),'Reconnection did not recover a single live focus lease');
  assert.equal((await fixture({notify_reason:'failed'})).notifications.length,2);checks.push('socket-reconnect-reprobes-live-sidebar-without-retaining-old-focus-lease');
  await panel.close();panel=null;await waitFor(()=>fixture().then(data=>!data.attention_active),'Closing extension did not clear its focus lease');
  assert.equal((await fixture({notify_reason:'completed'})).notifications.length,3);checks.push('closing-extension-releases-focus-and-restores-system-notifications');
  assert.deepEqual(errors,[]);await Promise.all(['failure.png','failure.json','focus-diagnostics.json'].map(file=>rm(resolve(artifacts,file),{force:true})));await writeFile(resolve(artifacts,'session-sync.json'),JSON.stringify({passed:checks.length,checks,browser:context.browser().version()},null,2));console.log(JSON.stringify({passed:checks.length,checks},null,2));
}catch(error){await panel?.screenshot({path:resolve(artifacts,'failure.png')}).catch(()=>{});await writeFile(resolve(artifacts,'failure.json'),JSON.stringify({error:error.stack,checks,errors,diagnostics},null,2));throw error;}
finally{await context?.close();runtime.kill();await new Promise(yes=>runtime.exitCode!==null?yes():runtime.once('exit',yes));if(!resolve(work).startsWith(resolve(tmpdir())+sep)||!basename(work).startsWith('sugar-session-sync-'))throw Error('Unexpected cleanup path');await rm(work,{recursive:true,force:true,maxRetries:5,retryDelay:250});}
