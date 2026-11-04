import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {createRequire} from 'node:module';
import {mkdtemp,mkdir,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'../..'),require=createRequire(resolve(root,'plugins/browser-use/node/package.json'));
const {chromium}=require('playwright'),work=await mkdtemp(resolve(tmpdir(),'s32-'));
const artifacts=resolve(root,'browser-extension/artifacts/stream-continuity');await mkdir(artifacts,{recursive:true});
const runtime=spawn(resolve(root,'python/python.exe'),['-u',resolve(import.meta.dirname,'session-runtime-fixture.py'),resolve(work,'backend')],{cwd:root,windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8'}});
let diagnostics='',context,panel;const checks=[],errors=[];
runtime.stderr.on('data',data=>diagnostics=(diagnostics+data).slice(-14000));
const ready=new Promise((yes,no)=>{createInterface({input:runtime.stdout}).on('line',line=>{try{const data=JSON.parse(line);if(data.baseUrl)yes(data);}catch{}});runtime.once('exit',code=>no(Error('Fixture exited '+code+' '+diagnostics)));});
async function waitFor(fn,message){for(let i=0;i<500;i++){if(await fn())return;await new Promise(yes=>setTimeout(yes,40));}throw Error(message);}
try{
 const {baseUrl,sessions:[sid]}=await Promise.race([ready,new Promise((_,no)=>setTimeout(()=>no(Error('Startup timeout '+diagnostics)),180000).unref())]);
 async function fixture(body={}){const response=await fetch(baseUrl+'/__fixture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(response.status,200,await response.clone().text());return response.json();}
 await waitFor(async()=>{try{await fixture();return true;}catch{return false;}},'Fixture not listening');
 await fixture({native_stream:true,native_hold:true,models_fail:false});
 context=await chromium.launchPersistentContext(resolve(work,'profile'),{channel:'msedge',headless:true,locale:'zh-CN',viewport:{width:400,height:800},args:[`--disable-extensions-except=${resolve(root,'browser-extension/dist')}`,`--load-extension=${resolve(root,'browser-extension/dist')}`]});
 panel=await context.newPage();panel.setDefaultTimeout(60000);panel.on('pageerror',error=>errors.push(error.message));await panel.goto('chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo/sidepanel.html');
 const {code}=await(await fetch(baseUrl+'/api/browser/v1/pairings',{method:'POST',headers:{Origin:baseUrl,'Content-Type':'application/json'},body:'{}'})).json();
 await panel.evaluate(async({baseUrl,code,sid})=>{await chrome.storage.local.set({'sugar.lastSession':sid,'sugar.preferences':{language:'zh-CN',theme:'dark',design:'selected-m-20261030',autoPageContext:false}});window.facts=[];window.snapshots=[];window.testPort=chrome.runtime.connect({name:'sugaragent-sidepanel'});window.testPort.onMessage.addListener(message=>{if(message.type==='session.event')window.facts.push(message.event);if(message.type==='session.executions')window.snapshots.push(...message.records);});const paired=await chrome.runtime.sendMessage({type:'pair',baseUrl,code});if(!paired.ok)throw Error(paired.error);},{baseUrl,code,sid});
 await panel.locator('.session-title').getByText('已有会话一',{exact:true}).waitFor();
 const answer=text=>panel.locator('.answer').getByText('native answer:'+text+' · done',{exact:true});
 const user=text=>panel.locator('.user-message').getByText(text,{exact:true});
 await fixture({main_message:'main-start'});await user('main-start').waitFor();await panel.getByText('native thinking 1',{exact:true}).waitFor();
 checks.push('main-originated-run-starts-live-thinking-in-observer-sidebar-without-local-send');
 await fixture({main_queue:['main-pending-a','main-pending-b'],native_hold:false});
 for(const text of ['main-start','main-pending-a','main-pending-b']){
  await user(text).waitFor();await answer(text).waitFor();
  const turn=panel.locator('.turn').filter({has:user(text)});
  const heading=turn.locator('.process-heading');if(await heading.getAttribute('aria-expanded')==='false')await heading.click();
  await turn.locator('.process-block.tool').waitFor();assert.equal(await turn.locator('.process-block.tool').count(),1);
 }
 let facts=await panel.evaluate(()=>window.facts);const queued=facts.filter(event=>event.type==='user'&&event.queued_followup);
 assert.equal(queued.length,2);assert.equal(new Set(queued.map(row=>row.run_id)).size,1);
 assert.equal(new Set(queued.map(row=>row.process_group_id)).size,2);
 await waitFor(()=>panel.evaluate(()=>window.facts.some(row=>row.type==='run_finished'&&row.run_id===window.facts.find(event=>event.type==='user'&&event.queued_followup)?.run_id)),'Shared pending run did not finish');
 checks.push('production-astream-and-main-pending-consumer-deliver-each-user-tool-and-answer-in-one-shared-run');
 await fixture({native_hold:true,native_response_hold:true,main_message:'recovery-input'});
 await user('recovery-input').waitFor();await panel.getByText('native thinking 4',{exact:true}).waitFor();
 await fixture({close_sockets:1012});
 await waitFor(()=>panel.evaluate(()=>window.snapshots.some(row=>row.kind==='reasoning'&&row.content==='native thinking 4')),'Active thinking was not recovered from execution journal');
 await panel.getByText('native thinking 4',{exact:true}).waitFor();
 assert.equal(await panel.getByText('native thinking 4',{exact:true}).count(),1);
 checks.push('reconnect-restores-in-progress-thinking-from-durable-execution-journal');
 await fixture({forwarder_fail_once:true,native_add_chunk:true});
 await panel.getByText('native thinking 4 plus',{exact:true}).waitFor();
 await waitFor(()=>panel.evaluate(()=>window.snapshots.some(row=>row.kind==='reasoning'&&row.content==='native thinking 4 plus')),'Silent forwarder failure did not reconnect and recover');
 checks.push('failed-forwarder-closes-green-transport-and-recovers-the-lost-durable-thought-on-reconnect');
 await fixture({native_hold:false});await panel.getByText('native answer:recovery-input',{exact:true}).waitFor();
 await fixture({close_sockets:1012});
 await waitFor(()=>panel.evaluate(()=>window.snapshots.some(row=>row.kind==='response'&&row.content==='native answer:recovery-input')),'Active answer was not recovered');
 await fixture({native_response_hold:false});await answer('recovery-input').waitFor();
 assert.equal(await answer('recovery-input').count(),1);assert.equal(await user('recovery-input').count(),1);
 checks.push('partial-answer-snapshot-resumes-with-next-delta-without-repetition-or-truncation');
 await fixture({main_message:'after-close'});await answer('after-close').waitFor();await user('after-close').waitFor();
 checks.push('external-next-message-still-streams-after-pending-completion-and-repeated-reconnects');
 await panel.reload();await answer('after-close').waitFor();
 for(const text of ['main-start','main-pending-a','main-pending-b','recovery-input','after-close'])assert.equal(await user(text).count(),1);
 assert.deepEqual(errors,[]);await panel.screenshot({path:resolve(artifacts,'recovered-main-pending-400.png')});
 checks.push('history-reload-keeps-all-five-official-users-and-own-processes-with-no-browser-errors');
 await writeFile(resolve(artifacts,'stream-continuity-regression.json'),JSON.stringify({passed:checks.length,checks,errors},null,2));console.log(JSON.stringify({passed:checks.length,checks},null,2));
}catch(error){if(panel)await panel.screenshot({path:resolve(artifacts,'failure.png')}).catch(()=>{});throw Error(error.message+'\nUI: '+(panel?await panel.locator('body').innerText().catch(()=>''):'')+'\n'+diagnostics,{cause:error});}
finally{if(context)await context.close();runtime.kill();await new Promise(yes=>runtime.exitCode!==null?yes():runtime.once('exit',yes));await rm(work,{recursive:true,force:true,maxRetries:5,retryDelay:250});}
