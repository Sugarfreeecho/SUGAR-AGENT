import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {createRequire} from 'node:module';
import {mkdtemp,mkdir,readFile,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'../..'),require=createRequire(resolve(root,'plugins/browser-use/node/package.json'));
const {chromium}=require('playwright'),work=await mkdtemp(resolve(tmpdir(),'sugar-recovery-'));
const artifacts=resolve(root,'browser-extension/artifacts/session-recovery');await mkdir(artifacts,{recursive:true});
let source=await readFile(resolve(root,'browser-extension/tests/session-runtime-fixture.py'),'utf8');
source=source.replace("ROOT = Path(__file__).resolve().parents[2]",`ROOT = Path(${JSON.stringify(root)})`);
source=source.replace('            await asyncio.sleep(.5)',"            while state.get('history_hold'): await asyncio.sleep(.02)\n            await asyncio.sleep(.5)");
source=source.replace('listener = socket.socket()',`
state['history_hold'] = False

@c.app.post('/__recovery/publish')
async def recovery_publish(request:Request):
    data=await request.json()
    await publish_session_event(data['session_id'],{**data['event'],'ephemeral':True})
    return {'ok':True}

@c.app.post('/__recovery/commit')
async def recovery_commit(request:Request):
    data=await request.json()
    ops.commit_user_turn(data['session_id'],data['content'],operation_id='recovery-user-'+data['run'],run_id=data['run'])
    return {'ok':True}

listener = socket.socket()`);
await writeFile(resolve(work,'runtime.py'),source);
const runtime=spawn(resolve(root,'python/python.exe'),['-u',resolve(work,'runtime.py'),resolve(work,'backend')],{cwd:root,windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8'}});
let context,panel,diagnostics='';const checks=[],errors=[];
const check=message=>{checks.push(message);console.log('PASS '+message);};
runtime.stderr.on('data',data=>diagnostics=(diagnostics+data).slice(-7000));
const ready=new Promise((yes,no)=>{createInterface({input:runtime.stdout}).on('line',line=>{try{const data=JSON.parse(line);if(data.baseUrl)yes(data);}catch{}});runtime.once('exit',code=>no(Error('Runtime exit '+code+' '+diagnostics)));});
async function until(fn,message){for(let n=0;n<400;n++){if(await fn())return;await new Promise(yes=>setTimeout(yes,50));}throw Error(message);}
try{
  const {baseUrl,sessions:[a,b]}=await Promise.race([ready,new Promise((_,no)=>setTimeout(()=>no(Error('Startup timeout '+diagnostics)),180000).unref())]);
  console.log('Isolated control fixture ready');
  async function post(path,body={}){const r=await fetch(baseUrl+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(r.status,200,await r.clone().text());return r.json();}
  const fixture=body=>post('/__fixture',body),publish=(id,event)=>post('/__recovery/publish',{session_id:id,event});
  const historyReads=async(id,turns)=>(await fixture()).requests.filter(row=>row.method==='session.history'&&row.params.session_id===id&&row.params.turns===turns).length;
  await until(async()=>{try{await fixture({models_fail:false});return true;}catch{return false;}},'Runtime not ready');
  context=await chromium.launchPersistentContext(resolve(work,'profile'),{channel:'msedge',headless:true,locale:'zh-CN',viewport:{width:400,height:800},args:[`--disable-extensions-except=${resolve(root,'browser-extension/dist')}`,`--load-extension=${resolve(root,'browser-extension/dist')}`]});
  panel=await context.newPage();panel.on('pageerror',error=>errors.push(error.message));await panel.goto('chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo/sidepanel.html');
  const {code}=await(await fetch(baseUrl+'/api/browser/v1/pairings',{method:'POST',headers:{Origin:baseUrl,'Content-Type':'application/json'},body:'{}'})).json();
  await panel.evaluate(async({baseUrl,code,a})=>{await chrome.storage.local.set({'sugar.lastSession':a,'sugar.preferences':{language:'zh-CN',theme:'dark',autoPageContext:false}});const r=await chrome.runtime.sendMessage({type:'pair',baseUrl,code});if(!r.ok)throw Error(r.error);},{baseUrl,code,a});
  const title=name=>panel.locator('.session-title').getByText(name,{exact:true});
  const choose=async name=>{await panel.locator('.session-title').click();await panel.locator('.session-row-open').filter({hasText:name}).click();};
  await title('已有会话一').waitFor();
  await fixture({history_fail:b,history_delay:b});
  await choose('已有会话二');
  await until(async()=>await historyReads(b,15)>0,'Switch did not begin');
  await publish(b,{type:'llm_response_delta',run_id:'failed-b',delta:'foreign B content'});
  await until(async()=>await title('已有会话一').count()===1&&await panel.getByLabel('消息',{exact:true}).isEditable(),'Failed switch did not settle');
  await panel.waitForTimeout(200);
  assert.equal(await panel.locator('[data-run-id="failed-b"]').count(),0);check('Failed B snapshot discards B buffer and retains A');
  await post('/__recovery/commit',{session_id:a,run:'rollback-a',content:'恢复订阅验证'});
  await publish(a,{type:'llm_response_delta',run_id:'rollback-a',delta:'A subscription is alive'});
  await panel.locator('[data-run-id="rollback-a"] .answer').waitFor();
  await publish(a,{type:'run_finished',run_id:'rollback-a',result_status:'succeeded'});check('Rollback restores the previous live subscription');
  await fixture({history_fail:''});const before=await historyReads(b,15);
  await choose('已有会话二');await until(async()=>await historyReads(b,15)>before,'Successful switch did not begin');
  await publish(b,{type:'llm_response_delta',run_id:'successful-b',delta:'buffered B content'});
  await title('已有会话二').waitFor();await panel.locator('[data-run-id="successful-b"] .answer').waitFor();
  assert.equal(await panel.locator('[data-run-id="successful-b"]').count(),1);assert.equal(await panel.locator('[data-run-id="rollback-a"]').count(),0);
  check('Successful snapshot replays its own buffer once and replaces A');
  await fixture({history_delay:''});await choose('已有会话一');await title('已有会话一').waitFor();
  const run='late-user',backfills=await historyReads(a,4);
  await publish(a,{type:'run_started',run_id:run});await publish(a,{type:'llm_response_delta',run_id:run,delta:'first chunk'});
  await until(async()=>await historyReads(a,4)>=backfills+3,'Three empty backfills were not retried');
  await post('/__recovery/commit',{session_id:a,run,content:'迟到的真实用户消息'});
  // No additional live event is sent. The timer must recover the user on its own.
  await until(async()=>await panel.locator(`[data-run-id="${run}"] .user-message`).count()===1,'Late user bubble did not recover without a new delta');
  check('Third empty history does not exhaust user recovery; timer restores the bubble without new deltas');
  await panel.screenshot({path:resolve(artifacts,'recovered-user.png')});
  await panel.reload();await title('已有会话一').waitFor();
  assert.equal(await panel.locator(`[data-run-id="${run}"] .user-message`).count(),1);check('Reload keeps the recovered bubble exactly once');
  const burst='coalesced-user',count=await historyReads(a,4);await fixture({history_delay:a,history_hold:true});
  await publish(a,{type:'run_started',run_id:burst});
  await until(async()=>await historyReads(a,4)>count,'Backfill did not start');
  await Promise.all(Array.from({length:20},(_,index)=>publish(a,{type:'llm_response_delta',run_id:burst,delta:' '+index})));
  assert.equal(await historyReads(a,4),count+1);check('Twenty live deltas share one in-flight backfill');
  await post('/__recovery/commit',{session_id:a,run:burst,content:'合并请求后的用户消息'});await fixture({history_delay:'',history_hold:false});
  await until(async()=>await panel.locator(`[data-run-id="${burst}"] .user-message`).count()===1,'Coalesced read did not recover');
  check('Coalescing still installs the real history fact');assert.deepEqual(errors,[]);check('No browser runtime errors');
  await writeFile(resolve(artifacts,'session-recovery-regression.json'),JSON.stringify({checks,errors},null,2));console.log(JSON.stringify({passed:checks.length,checks},null,2));
}catch(error){if(panel)await panel.screenshot({path:resolve(artifacts,'failure.png')}).catch(()=>{});throw Error(error.message+' '+diagnostics,{cause:error});}
finally{if(context)await context.close();runtime.kill();await new Promise(yes=>runtime.exitCode!==null?yes():runtime.once('exit',yes));await rm(work,{recursive:true,force:true,maxRetries:5,retryDelay:250});}
