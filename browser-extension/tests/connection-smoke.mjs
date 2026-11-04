import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {createRequire} from 'node:module';
import {mkdtemp,mkdir,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'../..'),require=createRequire(resolve(root,'plugins/browser-use/node/package.json'));
const {chromium}=require('playwright');
const work=await mkdtemp(resolve(tmpdir(),'sugar-connection-')),artifacts=resolve(root,'browser-extension/artifacts/connection');await mkdir(artifacts,{recursive:true});
let runtime,diagnostics='',context,panel,snapshot=async()=>({});const checks=[],errors=[];
async function start(port=0){
  runtime=spawn(resolve(root,'python/python.exe'),['-u',resolve(import.meta.dirname,'session-runtime-fixture.py'),resolve(work,'backend'),String(port)],{cwd:root,windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8'}});
  runtime.stderr.on('data',data=>diagnostics=(diagnostics+data).slice(-8000));
  return Promise.race([new Promise((yes,no)=>{createInterface({input:runtime.stdout}).on('line',line=>{try{const data=JSON.parse(line);if(data.baseUrl)yes(data);}catch{}});runtime.once('exit',code=>no(Error('Fixture exited '+code+' '+diagnostics)));}),new Promise((_,no)=>setTimeout(()=>no(Error('Fixture timeout '+diagnostics)),90000).unref())]);
}
async function stop(){const previous=runtime;if(!previous)return;previous.kill();await new Promise(yes=>previous.exitCode!==null?yes():previous.once('exit',yes));}
async function waitFor(fn,message){for(let i=0;i<600;i++){if(await fn())return;await new Promise(yes=>setTimeout(yes,50));}throw Error(message);}
try{
  const {baseUrl,sessions:[sid]}=await start();
  async function fixture(body={}){const response=await fetch(baseUrl+'/__fixture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(response.status,200);return response.json();}
  snapshot=()=>fixture({inspect_session:sid});
  await waitFor(async()=>{try{await fixture();return true;}catch{return false;}},'Fixture not listening');await fixture({models_fail:false});
  context=await chromium.launchPersistentContext(resolve(work,'profile'),{channel:'msedge',headless:true,locale:'zh-CN',viewport:{width:400,height:800},args:[`--disable-extensions-except=${resolve(root,'browser-extension/dist')}`,`--load-extension=${resolve(root,'browser-extension/dist')}`]});
  panel=await context.newPage();panel.on('pageerror',error=>errors.push(error.message));
  await panel.addInitScript(()=>{window.__connectionFacts=[];const original=chrome.runtime.connect.bind(chrome.runtime);chrome.runtime.connect=(...args)=>{const port=original(...args);port.onMessage.addListener(message=>window.__connectionFacts.push(message));return port;};});
  await panel.goto('chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo/sidepanel.html');
  const {code}=await(await fetch(baseUrl+'/api/browser/v1/pairings',{method:'POST',headers:{Origin:baseUrl,'Content-Type':'application/json'},body:'{}'})).json();
  await panel.evaluate(async({baseUrl,code,sid})=>{await chrome.storage.local.set({'sugar.lastSession':sid,'sugar.preferences':{language:'zh-CN',theme:'dark',design:'selected-m-20261030',autoPageContext:false}});const reply=await chrome.runtime.sendMessage({type:'pair',baseUrl,code});if(!reply.ok)throw Error(reply.error);},{baseUrl,code,sid});
  const state=()=>panel.evaluate(async()=>(await chrome.runtime.sendMessage({type:'state'})).result);
  const saved=()=>panel.evaluate(async()=>(await chrome.storage.local.get('sugar.connection'))['sugar.connection']);
  const token=(await saved()).token;
  await panel.locator('.session-title').getByText('已有会话一',{exact:true}).waitFor();
  await panel.getByLabel('消息',{exact:true}).fill('断线期间保留草稿');await new Promise(resolve=>setTimeout(resolve,400));
  const assertRecovered=async()=>{
    await waitFor(async()=>(await state()).status==='connected','Connection did not recover');
    await panel.locator('.session-title').getByText('已有会话一',{exact:true}).waitFor();
    await waitFor(()=>panel.getByTitle('发送',{exact:true}).isEnabled(),'Sidebar hydration did not retain a sendable draft');
    assert.equal((await saved()).token,token);assert.equal(await panel.getByLabel('消息',{exact:true}).inputValue(),'断线期间保留草稿');
    assert.equal(await panel.getByPlaceholder('在主程序的浏览器连接设置中生成').count(),0);
    assert.equal((await fixture()).paired_browsers,1);
  };
  const management=await context.newPage();await management.goto('edge://extensions/');
  await management.getByText('SugarAgent',{exact:true}).waitFor();
  const nativeIcon=management.getByAltText('SugarAgent 扩展图标',{exact:true});await nativeIcon.waitFor();
  const iconPixels=await nativeIcon.evaluate(image=>{
    const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;canvas.getContext('2d').drawImage(image,0,0);
    const pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;let purple=0;
    for(let i=0;i<pixels.length;i+=4)if(pixels[i+2]-pixels[i]>20 && pixels[i+2]-pixels[i+1]>20 && pixels[i+3]>128)purple++;
    return {width:canvas.width,height:canvas.height,purpleRatio:purple/(pixels.length/4)};
  });
  assert.ok(iconPixels.purpleRatio>.3,'Native Edge extension card is using its fallback icon: '+JSON.stringify(iconPixels));
  await management.screenshot({path:resolve(artifacts,'native-brand-icon.png')});checks.push('native-edge-management-card-decodes-the-brand-icon-instead-of-default-letter');
  const generation=(await state()).generation;
  for(let attempt=0;attempt<2;attempt++){
    const oldWorker=context.serviceWorkers().find(row=>row.url().endsWith('/background.js'));
    const nextWorker=context.waitForEvent('serviceworker',{predicate:worker=>worker!==oldWorker,timeout:30000});
    await management.getByText('重新加载',{exact:true}).click();
    const worker=await nextWorker;
    await waitFor(()=>worker.evaluate(async()=>!!(await chrome.storage.local.get('sugar.connection'))['sugar.connection']?.token).catch(()=>false),'Saved credential disappeared after native extension reload');
    if(panel.isClosed())panel=await context.newPage();
    await panel.goto('chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo/sidepanel.html');
    await assertRecovered();assert.notEqual((await state()).generation,generation);
  }
  await management.close();checks.push('two-native-extension-reloads-preserve-the-same-pairing-session-and-draft');
  // The old backend reported some temporary failures as 4401. A real HTTP
  // probe must confirm that the original credential is still valid.
  await fixture({close_sockets:4401});await waitFor(async()=>(await state()).status!=='connected','False auth close was not observed');await assertRecovered();checks.push('false-auth-close-preserves-token-and-reconnects-without-new-pairing');
  await fixture({plugin_lease:false,connection_enabled:false,close_sockets:4403});
  await panel.locator('.connection-recovery').waitFor();
  assert.equal(await panel.getByPlaceholder('在主程序的浏览器连接设置中生成').count(),0);assert.equal((await saved()).token,token);
  await panel.screenshot({path:resolve(artifacts,'temporarily-unavailable-400.png')});
  await fixture({plugin_lease:true,connection_enabled:true});await assertRecovered();checks.push('plugin-disable-enable-keeps-pairing-session-and-draft-across-new-lease-epoch');
  // Stop the actual MV3 worker, then let the still-open sidebar recreate its
  // runtime port and subscription. Never touch the user's browser profile.
  const cdp=await context.browser().newBrowserCDPSession();
  const target=(await cdp.send('Target.getTargets')).targetInfos.find(row=>row.type==='service_worker' && row.url.endsWith('/background.js'));
  assert.ok(target,'MV3 worker target not found');
  assert.equal((await cdp.send('Target.closeTarget',{targetId:target.targetId})).success,true);
  await waitFor(async()=>!(await cdp.send('Target.getTargets')).targetInfos.some(row=>row.targetId===target.targetId),'Worker was not stopped');
  await assertRecovered();await cdp.detach();checks.push('actual-mv3-worker-eviction-restores-sidepanel-port-and-session-subscription');
  await stop();await panel.locator('.connection-recovery').waitFor();
  assert.equal(await panel.getByPlaceholder('在主程序的浏览器连接设置中生成').count(),0);assert.equal((await saved()).token,token);
  await start(Number(new URL(baseUrl).port));await waitFor(async()=>{try{await fixture({models_fail:false});return true;}catch{return false;}},'Restarted backend not listening');
  await assertRecovered();checks.push('real-backend-process-restart-restores-original-pairing-without-user-input');
  await panel.getByLabel('消息',{exact:true}).fill('重连后继续');await panel.getByTitle('发送',{exact:true}).click();await panel.locator('.answer').getByText('answer:重连后继续',{exact:true}).waitFor();
  checks.push('reply-stream-and-subscription-remain-functional-after-restarts');
  await panel.setViewportSize({width:320,height:720});await fixture({plugin_lease:false,connection_enabled:false,close_sockets:4403});await panel.locator('.connection-recovery').waitFor();
  assert.equal(await panel.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await panel.screenshot({path:resolve(artifacts,'temporarily-unavailable-320.png')});
  await fixture({plugin_lease:true,connection_enabled:true});await waitFor(async()=>(await state()).status==='connected','Final reconnect failed');
  const browserId=(await saved()).browserId;
  const revoked=await fetch(baseUrl+'/api/browser/v1/devices/'+browserId+'/revoke',{method:'POST',headers:{Origin:baseUrl,'Content-Type':'application/json'},body:'{}'});assert.equal(revoked.status,200);
  await fixture({close_sockets:4401});await panel.getByPlaceholder('在主程序的浏览器连接设置中生成').waitFor();
  assert.equal((await state()).status,'auth-required');assert.equal((await saved()).token,token);checks.push('real-device-revocation-still-requires-repairing-and-narrow-recovery-layout-fits');
  assert.deepEqual(errors,[]);await writeFile(resolve(artifacts,'connection-regression.json'),JSON.stringify({checks,passed:checks.length,errors},null,2));console.log(JSON.stringify({checks,passed:checks.length},null,2));
}catch(error){if(panel)await panel.screenshot({path:resolve(artifacts,'failure.png')}).catch(()=>{});const details=await snapshot().catch(()=>({})),facts=await panel?.evaluate(()=>window.__connectionFacts).catch(()=>[]);await writeFile(resolve(artifacts,'failure-details.json'),JSON.stringify({checks,details,facts,diagnostics},null,2));throw Error(error.message+'\nUI: '+(panel?await panel.locator('body').innerText().catch(()=>''):'')+'\nOperations: '+JSON.stringify(details.operations)+'\n'+diagnostics.slice(-1200),{cause:error});}
finally{if(context)await context.close();await stop();await rm(work,{recursive:true,force:true,maxRetries:5,retryDelay:250});}
