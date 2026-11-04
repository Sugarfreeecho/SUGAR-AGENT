import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {createRequire} from 'node:module';
import {mkdtemp,mkdir,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'../..'),require=createRequire(resolve(root,'plugins/browser-use/node/package.json'));
const {chromium}=require('playwright'),work=await mkdtemp(resolve(tmpdir(),'s34-'));
const artifacts=resolve(root,'browser-extension/artifacts/run-outcome');await mkdir(artifacts,{recursive:true});
const runtime=spawn(resolve(root,'python/python.exe'),['-u',resolve(import.meta.dirname,'session-runtime-fixture.py'),resolve(work,'backend')],{cwd:root,windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8'}});
let diagnostics='',context,panel;const checks=[],errors=[];
const pass=value=>{checks.push(value);console.log('PASS '+value);};
runtime.stderr.on('data',data=>diagnostics=(diagnostics+data).slice(-10000));
const ready=new Promise((yes,no)=>{createInterface({input:runtime.stdout}).on('line',line=>{try{const data=JSON.parse(line);if(data.baseUrl)yes(data);}catch{}});runtime.once('exit',code=>no(Error('Fixture exited '+code+' '+diagnostics)));});
async function waitFor(fn,message,timeout=60000){const until=Date.now()+timeout;while(Date.now()<until){if(await fn())return;await new Promise(yes=>setTimeout(yes,80));}throw Error(message);}
try{
  const {baseUrl,sessions:[sid]}=await Promise.race([ready,new Promise((_,no)=>setTimeout(()=>no(Error('Startup timeout '+diagnostics)),180000).unref())]);
  async function fixture(body={}){const response=await fetch(baseUrl+'/__fixture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(response.status,200,await response.clone().text());return response.json();}
  await waitFor(async()=>{try{await fixture();return true;}catch{return false;}},'Fixture not listening');
  await fixture({native_stream:true,native_hold:true,native_failure:'exception',models_fail:false});
  context=await chromium.launchPersistentContext(resolve(work,'profile'),{channel:'msedge',headless:true,locale:'zh-CN',viewport:{width:400,height:800},args:[`--disable-extensions-except=${resolve(root,'browser-extension/dist')}`,`--load-extension=${resolve(root,'browser-extension/dist')}`]});
  panel=await context.newPage();panel.setDefaultTimeout(60000);panel.on('pageerror',error=>errors.push(error.message));await panel.goto('chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo/sidepanel.html');
  const {code}=await(await fetch(baseUrl+'/api/browser/v1/pairings',{method:'POST',headers:{Origin:baseUrl,'Content-Type':'application/json'},body:'{}'})).json();
  await panel.evaluate(async({baseUrl,code,sid})=>{await chrome.storage.local.set({'sugar.lastSession':sid,'sugar.preferences':{language:'zh-CN',theme:'dark',design:'selected-m-20261030',autoPageContext:false}});window.facts=[];window.testPort=chrome.runtime.connect({name:'sugaragent-sidepanel'});window.testPort.onMessage.addListener(message=>{if(message.type==='session.event')window.facts.push(message.event);});const paired=await chrome.runtime.sendMessage({type:'pair',baseUrl,code});if(!paired.ok)throw Error(paired.error);},{baseUrl,code,sid});
  await panel.locator('.session-title').getByText('已有会话一',{exact:true}).waitFor();
  const turn=text=>panel.locator('.turn').filter({has:panel.locator('.user-message').getByText(text,{exact:true})});
  const idle=()=>waitFor(()=>panel.evaluate(async sid=>{const result=await chrome.runtime.sendMessage({type:'rpc',method:'session.get',params:{session_id:sid,include_runtime:true}});return result.ok && result.result.session.stream_active===false;},sid),'Backend did not become idle');
  await fixture({main_message:'terminal-error'});await turn('terminal-error').getByText('native thinking 1',{exact:true}).waitFor();
  await fixture({native_hold:false});
  await waitFor(()=>panel.evaluate(()=>window.facts.some(event=>event.type==='run_failed')),'Production run_failed was not emitted');
  // A green WebSocket already delivered run_failed in the old release, but
  // its error-only payload had no notice. Keep this first for baseline proof.
  await turn('terminal-error').locator('.run-notice.failed').getByText('fixture provider connection lost',{exact:true}).waitFor({timeout:15000});
  assert.equal(await panel.getByText('Agent 正在执行',{exact:true}).count(),0);
  const heading=turn('terminal-error').locator('.process-heading');if(await heading.getAttribute('aria-expanded')==='true')await heading.click();
  await turn('terminal-error').locator('.run-notice').waitFor({state:'visible'});
  assert.equal(await turn('terminal-error').getByText('正在思考',{exact:true}).count(),0);
  pass('production-error-field-is-visible-outside-collapsed-process-and-running-indicators-stop');
  await idle();await panel.reload();await turn('terminal-error').locator('.run-notice.failed').waitFor();
  assert.equal(await turn('terminal-error').locator('.run-notice').count(),1);
  pass('durable-failure-survives-history-reload-without-duplicate-notices');
  await panel.evaluate(()=>{window.facts=[];window.testPort=chrome.runtime.connect({name:'sugaragent-sidepanel'});window.testPort.onMessage.addListener(message=>{if(message.type==='session.event')window.facts.push(message.event);});});
  await fixture({native_hold:true,native_failure:'',main_message:'main-stop'});await turn('main-stop').getByText('native thinking 2',{exact:true}).waitFor();
  await fixture({main_interrupt:true});await turn('main-stop').locator('.run-notice.interrupted').getByText('已停止',{exact:true}).waitFor();
  await idle();assert.equal(await panel.getByText('Agent 正在执行',{exact:true}).count(),0);
  pass('main-program-interrupt-is-visible-in-observer-sidebar-and-clears-stop-mode');
  await fixture({native_hold:true,native_failure:'exception',drop_terminal:true,main_message:'lost-terminal'});await turn('lost-terminal').getByText('native thinking 3',{exact:true}).waitFor();
  const lostRun=await turn('lost-terminal').getAttribute('data-run-id');
  await fixture({native_hold:false});await idle();
  await turn('lost-terminal').locator('.run-notice.failed').getByText('fixture provider connection lost',{exact:true}).waitFor();
  assert.equal(await panel.evaluate(run=>window.facts.some(event=>event.run_id===run&&event.type==='run_started'),lostRun),true);
  assert.equal(await panel.evaluate(run=>window.facts.some(event=>event.run_id===run&&['run_failed','run_interrupted','run_finished'].includes(event.type)),lostRun),false);
  assert.equal(await panel.getByText('Agent 正在执行',{exact:true}).count(),0);
  pass('omitted-live-terminal-recovers-authoritative-failure-after-inactivity-checks-without-reload');
  await fixture({native_hold:true,native_failure:'exception',hide_terminal_history:true,main_message:'unknown-terminal'});await turn('unknown-terminal').getByText('native thinking 4',{exact:true}).waitFor();
  await fixture({native_hold:false});await idle();
  await turn('unknown-terminal').locator('.run-notice.unknown').getByText('后端已停止执行，但未收到完成状态。',{exact:true}).waitFor();
  assert.equal(await panel.getByText('Agent 正在执行',{exact:true}).count(),0);
  pass('missing-live-and-durable-terminal-is-explicitly-unconfirmed-not-silent-or-successful');
  await fixture({native_hold:true,native_failure:'structured',drop_terminal:false,hide_terminal_history:false,main_message:'structured-error'});await turn('structured-error').getByText('native thinking 5',{exact:true}).waitFor();
  await fixture({native_hold:false});await idle();
  const notice=turn('structured-error').locator('.run-notice.failed');await notice.getByText('模型请求失败：连接已断开',{exact:true}).waitFor();
  assert.equal(await notice.count(),1);assert.equal(await panel.getByText('__ERR_CARD__',{exact:false}).count(),0);
  await notice.locator('summary').click();await notice.getByText(/检查模型服务/).waitFor();assert.match(await notice.innerText(),/fixture socket reset/);
  pass('structured-provider-error-renders-readable-summary-and-expandable-solution-with-one-notice');
  for(const width of [400,320]){
    await panel.setViewportSize({width,height:800});
    assert.equal(await panel.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    assert.ok((await notice.locator('summary').boundingBox()).height<65);
    await panel.screenshot({path:resolve(artifacts,'failure-'+width+'.png')});
  }
  pass('compact-notice-fits-400-and-320-pixel-sidebars-without-horizontal-overflow');
  await fixture({native_hold:true,native_failure:'',main_message:'after-failures'});await turn('after-failures').getByText('native thinking 6',{exact:true}).waitFor();
  await fixture({native_hold:false});await turn('after-failures').locator('.answer').getByText('native answer:after-failures · done',{exact:true}).waitFor();
  await idle();assert.equal(await turn('after-failures').locator('.run-notice').count(),0);assert.deepEqual(errors,[]);
  pass('next-main-originated-run-streams-and-finishes-normally-after-all-failure-paths');
  await writeFile(resolve(artifacts,'run-outcome-regression.json'),JSON.stringify({passed:checks.length,checks,errors},null,2));console.log(JSON.stringify({passed:checks.length,checks},null,2));
}catch(error){if(panel)await panel.screenshot({path:resolve(artifacts,'failure.png')}).catch(()=>{});throw Error(error.message+'\nUI: '+(panel?await panel.locator('body').innerText().catch(()=>''):'')+'\n'+diagnostics,{cause:error});}
finally{if(context)await context.close();runtime.kill();await new Promise(yes=>runtime.exitCode!==null?yes():runtime.once('exit',yes));await rm(work,{recursive:true,force:true,maxRetries:5,retryDelay:250});}
