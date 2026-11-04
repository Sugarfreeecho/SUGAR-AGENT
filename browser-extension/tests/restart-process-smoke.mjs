import assert from 'node:assert/strict';
import http from 'node:http';
import {createRequire} from 'node:module';
import {mkdtemp,mkdir,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'../..'),require=createRequire(resolve(root,'plugins/browser-use/node/package.json'));
const {chromium}=require('playwright'),{wsServer:WebSocketServer}=require('playwright-core/lib/utilsBundle');
const work=await mkdtemp(resolve(tmpdir(),'sugar-restart-process-')),artifacts=resolve(root,'browser-extension/artifacts/restart-process');await mkdir(artifacts,{recursive:true});
const sid='restart-session',group='turn:10',events=[
  {type:'user',run_id:'original',runtime_seq:10,content:'重启后继续完成这轮任务'},
  {type:'llm_reasoning',run_id:'original',process_group_id:group,react_iter:1,content:'重启前的思考'},
  {type:'tool_call',run_id:'original',process_group_id:group,react_iter:1,tool_call_id:'restart',tool:'request_restart',args:{reason:'测试后端恢复'},result:'authorized',status:{ok:true,duration_ms:1000}},
  {type:'run_interrupted',run_id:'original',reason:'process_restart'},
  {type:'llm_reasoning',run_id:'recovery',process_group_id:group,react_iter:1,content:'重启后的思考，仍属于原消息'},
  {type:'user_steer',run_id:'recovery',process_group_id:group,steer_id:'followup',content:'插话气泡仍单独可见'},
  ...Array.from({length:5},(_,i)=>({type:'tool_call',run_id:'recovery',process_group_id:group,react_iter:i+1,tool_call_id:'verify-'+i,tool:'run_shell',args:{command:'verify '+i},result:'verified '+i,status:{ok:true,duration_ms:100}})),
  {type:'final',run_id:'recovery',content:'重启后这轮任务已完成。'},
];
const baseHistory=[...events];
let active=false,seq=1,context,panel,pageMode=false;const checks=[],errors=[];
const server=http.createServer(async(req,res)=>{
  res.setHeader('Content-Type','application/json');
  const path=req.url.split('?')[0];
  if(path==='/api/browser/v1/claim')return res.end(JSON.stringify({token:'restart-token',browser_id:'restart-browser'}));
  if(path==='/api/browser/v1/connection')return res.end(JSON.stringify({paired:true,browser_id:'restart-browser'}));
  if(path==='/api/browser/v1/models')return res.end(JSON.stringify({profiles:[]}));
  if(path==='/api/browser/v1/workspaces')return res.end(JSON.stringify({workspaces:[]}));
  if(path==='/api/browser/v1/session-state')return res.end(JSON.stringify({permissions:{mode:'ask_for_approval'},context_tokens:null}));
  if(path==='/api/browser/v1/human/list')return res.end(JSON.stringify({records:[]}));
  if(path==='/api/browser/v1/steers')return res.end(JSON.stringify({items:[]}));
  if(path==='/api/control/v1/rpc'){
    let raw='';for await(const part of req)raw+=part;const {method,params={}}=JSON.parse(raw);
    const session={id:sid,name:'重启衔接测试',stream_active:active};
    const data=method==='session.list'?{sessions:[session]}:method==='session.get'?{session}:method==='session.history'?pageMode?{events:params.before_index?baseHistory.slice(0,4):baseHistory.slice(4),has_older:!params.before_index,range_start:params.before_index?0:1000}:{events,has_older:false,range_start:0}:{};
    return res.end(JSON.stringify({ok:true,data}));
  }
  res.end('{}');
});
const sockets=new WebSocketServer({server});
sockets.on('connection',socket=>socket.on('message',raw=>{const data=JSON.parse(raw.toString());if(data.type==='hello')socket.send(JSON.stringify({type:'ready'}));if(data.type==='subscribe')socket.send(JSON.stringify({type:'subscribed',session_id:data.session_id}));}));
await new Promise(yes=>server.listen(0,'127.0.0.1',yes));const baseUrl='http://127.0.0.1:'+server.address().port;
async function emit(event){events.push(event);for(const socket of sockets.clients)if(socket.readyState===1)socket.send(JSON.stringify({type:'session.event',session_id:sid,event:{...event,event_bus_epoch:'restart-test',event_bus_seq:seq++}}));}
async function until(fn,message){for(let n=0;n<250;n++){if(await fn())return;await new Promise(yes=>setTimeout(yes,40));}throw Error(message);}
try{
  context=await chromium.launchPersistentContext(resolve(work,'profile'),{channel:'msedge',headless:true,locale:'zh-CN',viewport:{width:400,height:800},args:[`--disable-extensions-except=${resolve(root,'browser-extension/dist')}`,`--load-extension=${resolve(root,'browser-extension/dist')}`]});
  panel=await context.newPage();panel.on('pageerror',error=>errors.push(error.message));
  await panel.goto('chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo/sidepanel.html');
  await panel.evaluate(async({baseUrl,sid})=>{await chrome.storage.local.set({'sugar.lastSession':sid,'sugar.preferences':{language:'zh-CN',theme:'dark',autoPageContext:false}});const r=await chrome.runtime.sendMessage({type:'pair',baseUrl,code:'fixture'});if(!r.ok)throw Error(r.error);},{baseUrl,sid});
  await panel.getByText('重启后这轮任务已完成。',{exact:true}).waitFor();
  assert.equal(await panel.locator('.process-heading').count(),1);assert.equal(await panel.locator('.process-count').innerText(),'6 次操作');
  assert.equal(await panel.locator('.process-heading').getAttribute('aria-expanded'),'false');
  assert.equal(await panel.getByText('插话气泡仍单独可见',{exact:true}).count(),1);checks.push('history-restart-runs-share-one-folded-heading-count-and-keep-steer-and-final-visible');
  await panel.locator('.process-heading').click();assert.equal(await panel.locator('.process-block.tool').count(),6);assert.equal(await panel.locator('.process-block.reason').count(),2);
  const before=await panel.locator('[data-run-id=original] .process-block').last().boundingBox(),after=await panel.locator('[data-run-id=recovery] .process-block').first().boundingBox();
  assert.ok(after.y>=before.y+before.height-1 && after.y-(before.y+before.height)<14,JSON.stringify({before,after}));
  await panel.screenshot({path:resolve(artifacts,'joined-history-400.png')});checks.push('both-run-segments-expand-together-and-vertical-process-spacing-remains-continuous');
  for(const theme of ['dark','light','purple']){
    await panel.setViewportSize({width:320,height:720});await panel.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
    assert.equal(await panel.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await panel.screenshot({path:resolve(artifacts,'joined-'+theme+'-320.png')});
  }
  checks.push('joined-process-fits-three-themes-at-320px');
  await panel.reload();await panel.getByText('重启后这轮任务已完成。',{exact:true}).waitFor();assert.equal(await panel.locator('.process-heading').count(),1);
  await panel.locator('.process-heading').click();assert.equal(await panel.locator('.process-block.tool').count(),6);checks.push('reload-reconstructs-the-same-single-process-without-duplicate-entries');
  active=true;
  await emit({type:'user',run_id:'next',runtime_seq:100,content:'下一条独立问题'});await emit({type:'run_started',run_id:'next'});
  await emit({type:'tool_pending',run_id:'next',process_group_id:'turn:100',react_iter:1,tool_call_id:'next-tool',tool:'read_file',args:{path:'README.md'}});
  await until(()=>panel.locator('.process-heading').count().then(n=>n===2),'Independent user turn was merged');checks.push('next-official-user-message-starts-a-separate-process');
  await emit({type:'run_interrupted',run_id:'next',reason:'process_restart'});await emit({type:'run_started',run_id:'next-recovery'});
  await emit({type:'llm_reasoning_delta',run_id:'next-recovery',process_group_id:'turn:100',react_iter:1,delta:'继续执行下一条问题'});
  await panel.getByText('继续执行下一条问题',{exact:true}).waitFor();assert.equal(await panel.locator('.process-heading').count(),2);
  const second=panel.locator('.turn-group').last();await second.locator('.process-heading').click();assert.equal(await second.locator('.process-block').count(),0);
  await emit({type:'llm_reasoning_delta',run_id:'next-recovery',process_group_id:'turn:100',react_iter:1,delta:'，持续流式输出'});
  await panel.waitForTimeout(150);assert.equal(await second.locator('.process-heading').getAttribute('aria-expanded'),'false');
  checks.push('live-recovery-attaches-to-its-user-and-honors-shared-manual-collapse');
  await emit({type:'final',run_id:'next-recovery',content:'下一轮恢复完成'});await emit({type:'run_finished',run_id:'next-recovery',result_status:'succeeded'});active=false;
  await panel.getByText('下一轮恢复完成',{exact:true}).waitFor();assert.equal(await second.locator('.process-heading').getAttribute('aria-expanded'),'false');
  assert.deepEqual(errors,[]);checks.push('terminal-recovery-keeps-answer-visible-and-collapses-one-combined-process');
  pageMode=true;await panel.reload();await panel.getByText('重启后这轮任务已完成。',{exact:true}).waitFor();
  await panel.locator('.process-heading').click();
  await panel.locator('[data-run-id=recovery] .process-block.tool').first().evaluate(node=>window.__keptRestartTool=node);
  await panel.getByText('加载更早的对话',{exact:true}).click();
  await panel.getByText('重启后继续完成这轮任务',{exact:true}).waitFor();
  assert.equal(await panel.locator('.process-heading').count(),1);assert.equal(await panel.locator('.process-heading').getAttribute('aria-expanded'),'true');
  assert.equal(await panel.locator('.process-count').innerText(),'6 次操作');
  assert.equal(await panel.locator('[data-run-id=recovery] .process-block.tool').first().evaluate(node=>node===window.__keptRestartTool),true);
  checks.push('loading-the-pre-restart-history-preserves-expansion-and-live-tool-dom-identity');
  await emit({type:'run_started',run_id:'late-identity'});
  await emit({type:'tool_pending',run_id:'late-identity',tool_call_id:'late-tool',tool:'read_file',args:{path:'README.md'}});
  const late=panel.locator('[data-run-id=late-identity] .process-block.tool');await late.waitFor();
  await late.locator('summary').click();await late.evaluate(node=>window.__lateGroupTool=node);
  await emit({type:'user',run_id:'late-identity',runtime_seq:500,content:'较晚补齐的用户消息'});
  await panel.getByText('较晚补齐的用户消息',{exact:true}).waitFor();
  assert.equal(await late.evaluate(node=>node===window.__lateGroupTool),true);assert.equal(await late.getAttribute('open'),null);
  checks.push('late-user-and-group-metadata-preserve-mounted-tool-controls-and-local-state');
  await writeFile(resolve(artifacts,'restart-process-regression.json'),JSON.stringify({passed:checks.length,checks,errors},null,2));console.log(JSON.stringify({passed:checks.length,checks},null,2));
}catch(error){if(panel)await panel.screenshot({path:resolve(artifacts,'failure.png')}).catch(()=>{});throw Error(error.message+'\n'+(panel?await panel.locator('body').innerText().catch(()=>''):''),{cause:error});}
finally{if(context)await context.close();for(const socket of sockets.clients)socket.terminate();await new Promise(yes=>server.close(yes));await rm(work,{recursive:true,force:true,maxRetries:5,retryDelay:250});}
