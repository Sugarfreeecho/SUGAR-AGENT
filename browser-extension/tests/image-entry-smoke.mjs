import assert from 'node:assert/strict';
import http from 'node:http';
import {createRequire} from 'node:module';
import {mkdtemp,mkdir,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'../..'),require=createRequire(resolve(root,'plugins/browser-use/node/package.json'));
const {chromium}=require('playwright'),{wsServer:WebSocketServer}=require('playwright-core/lib/utilsBundle');
const work=await mkdtemp(resolve(tmpdir(),'sugar-image-entry-')),artifacts=resolve(root,'browser-extension/artifacts/image-entry');await mkdir(artifacts,{recursive:true});
const sessions=['layout','cached','reader'].map(id=>({id,name:id})),pending=new Map(),released=new Set(),checks=[],errors=[];
let context,panel,seq=0;
const paragraphs=Array.from({length:32},(_,i)=>`段落 ${i+1}：用于确认刚打开会话时，图片延迟加载后的位置。`).join('\n\n');
const svg='<svg xmlns="http://www.w3.org/2000/svg" width="240" height="480"><rect width="240" height="480" fill="#64748b"/></svg>';
function finish(response){response.setHeader('Content-Type','image/svg+xml');response.end(svg);}
const server=http.createServer(async(req,res)=>{
 res.setHeader('Content-Type','application/json');
 if(req.url.startsWith('/api/browser/v1/media')){
  const key=new URL(req.url,'http://fixture').searchParams.get('rel');res.setHeader('Cache-Control','no-store');
  if(released.has(key))finish(res);else{const rows=pending.get(key)||[];rows.push(res);pending.set(key,rows);}return;
 }
 let body='';for await(const chunk of req)body+=chunk;const request=body?JSON.parse(body):{};
 if(req.url==='/api/browser/v1/claim')return res.end(JSON.stringify({token:'image-entry',browser_id:'image-entry'}));
 if(req.url==='/api/browser/v1/models')return res.end(JSON.stringify({profiles:[]}));
 if(req.url==='/api/browser/v1/human/list')return res.end(JSON.stringify({records:[]}));
 if(req.url==='/api/browser/v1/steers')return res.end(JSON.stringify({items:[],pending:[],started_pending:[]}));
 if(req.url==='/api/browser/v1/subagents')return res.end(JSON.stringify({session_id:request.session_id,root:{id:request.session_id},entries:[],parent:null,parent_available:true}));
 if(req.url==='/api/control/v1/rpc'){
  const id=request.params.session_id,session=sessions.find(row=>row.id===id),text=paragraphs+`\n\n![图片一](D:/entry/${id}/one.svg)\n\n`+paragraphs+`\n\n![图片二](D:/entry/${id}/two.svg)`;
  const data=request.method==='session.list'?{sessions}:request.method==='session.get'?{session:{...session,stream_active:id==='cached'}}:request.method==='session.history'?{events:[{type:'user',run_id:id,content:'历史提问 '+id},{type:id==='cached'?'llm_response':'final',run_id:id,react_iter:1,content:text}],has_older:false}:{};
  return res.end(JSON.stringify({ok:true,data}));
 }
 res.end('{}');
});
const sockets=new WebSocketServer({server});sockets.on('connection',socket=>socket.on('message',raw=>{const data=JSON.parse(raw.toString());if(data.type==='hello')socket.send(JSON.stringify({type:'ready'}));if(data.type==='subscribe')socket.send(JSON.stringify({type:'subscribed',session_id:data.session_id}));if(data.type==='ping')socket.send(JSON.stringify({type:'pong'}));}));
await new Promise(yes=>server.listen(0,'127.0.0.1',yes));const baseUrl='http://127.0.0.1:'+server.address().port;
async function waitFor(fn,message){for(let i=0;i<250;i++){if(await fn())return;await new Promise(yes=>setTimeout(yes,40));}throw Error(message);}
function emit(id,event){for(const socket of sockets.clients)if(socket.readyState===1)socket.send(JSON.stringify({type:'session.event',session_id:id,event:{run_id:id,event_bus_epoch:'entry',event_bus_seq:++seq,...event}}));}
function release(id,name){for(const [key,rows]of pending)if(key.includes('/'+id+'/')&&(!name||key.endsWith('/'+name))){released.add(key);rows.forEach(finish);pending.delete(key);}}
try{
 context=await chromium.launchPersistentContext(resolve(work,'profile'),{channel:'msedge',headless:true,locale:'zh-CN',viewport:{width:400,height:800},args:[`--disable-extensions-except=${resolve(root,'browser-extension/dist')}`,`--load-extension=${resolve(root,'browser-extension/dist')}`]});
 panel=await context.newPage();panel.on('pageerror',error=>errors.push(error.message));await panel.goto('chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo/sidepanel.html');
 await panel.evaluate(async baseUrl=>{await chrome.storage.local.set({'sugar.lastSession':'layout','sugar.preferences':{language:'zh-CN',theme:'dark',autoPageContext:false}});const response=await chrome.runtime.sendMessage({type:'pair',baseUrl,code:'fixture'});if(!response.ok)throw Error(response.error);},baseUrl);
 const reading=panel.locator('.reading'),gap=()=>reading.evaluate(node=>node.scrollHeight-node.clientHeight-node.scrollTop);
 for(const width of [400,320])for(const id of ['layout','cached','reader']){
  for(const key of [...released])if(key.includes('/'+id+'/'))released.delete(key);
  await panel.setViewportSize({width,height:800});await panel.evaluate(async id=>chrome.storage.local.set({'sugar.lastSession':id}),id);await panel.reload();
  await panel.locator('.session-title').getByText(id,{exact:true}).waitFor();
  await waitFor(()=>Promise.resolve([...pending.keys()].filter(key=>key.includes('/'+id+'/')).length===2),'Both late images did not start');
  await waitFor(async()=>await gap()<2,'History did not start at its bottom');
  if(id==='cached'){
   emit(id,{type:'run_started',ephemeral:true,replayed_recent:true});await panel.waitForTimeout(100);
  }
  await reading.evaluate((node,simulateLayoutScroll)=>{
   if(simulateLayoutScroll)node.addEventListener('load',()=>node.dispatchEvent(new Event('scroll')),{capture:true});
   const audit=window.__imageMotion={rows:[],stop:false};const tick=()=>{audit.rows.push({top:node.scrollTop,gap:node.scrollHeight-node.clientHeight-node.scrollTop,owned:node.hasAttribute('data-smooth-follow-owned')});if(!audit.stop)requestAnimationFrame(tick);};requestAnimationFrame(tick);
  },id==='layout');
  if(id==='reader'){await reading.hover();const top=await reading.evaluate(node=>node.scrollTop);await panel.mouse.wheel(0,-180);await waitFor(()=>reading.evaluate((node,top)=>node.scrollTop<top-20,top),'Upward gesture was not applied');}
  const before=await reading.evaluate(node=>node.scrollTop);release(id,'one.svg');
  await waitFor(()=>reading.locator('img').evaluateAll(nodes=>nodes.some(node=>node.complete&&node.naturalHeight===480)),'First image did not load');
  if(id!=='reader')await waitFor(async()=>await gap()<2,'First image lost bottom placement');
  await panel.evaluate(()=>new Promise(yes=>requestAnimationFrame(()=>requestAnimationFrame(yes))));release(id,'two.svg');
  await waitFor(()=>reading.locator('img').evaluateAll(nodes=>nodes.length===2&&nodes.every(node=>node.complete&&node.naturalHeight===480)),'Images did not load');
  if(id==='reader'){
   await panel.waitForTimeout(200);assert.ok(Math.abs(await reading.evaluate(node=>node.scrollTop)-before)<2,'Late image reclaimed reader scroll');
  }else{
   await waitFor(async()=>await gap()<2,'Image height changed but bottom placement was lost');
   const rows=await panel.evaluate(()=>window.__imageMotion.rows);
   assert.equal(rows.some((row,index)=>index>0&&row.top>rows[index-1].top+2&&row.gap>2),false,'Restored images started a scroll animation');
   assert.equal(await reading.getAttribute('data-smooth-follow-owned'),null,'Cached frames ended instant placement');
  }
  await panel.evaluate(()=>window.__imageMotion.stop=true);checks.push(`${id}-${width}: late images preserve bottom or intentional reader position without entry animation`);
  await panel.screenshot({path:resolve(artifacts,`${id}-${width}.png`)});
  if(id==='cached'){
   emit(id,{type:'llm_response_delta',react_iter:2,ephemeral:true,delta:paragraphs});
   await waitFor(()=>reading.getAttribute('data-smooth-follow-owned').then(value=>value==='1'),'Fresh generation failed to resume smooth follow');checks.push(`live-${width}: fresh output still uses smooth scrolling`);
  }
 }
 assert.deepEqual(errors,[]);checks.push('no-browser-runtime-errors');await writeFile(resolve(artifacts,'image-entry-regression.json'),JSON.stringify({passed:checks.length,checks},null,2));console.log(JSON.stringify({passed:checks.length,checks},null,2));
}catch(error){await panel?.screenshot({path:resolve(artifacts,'failure.png')}).catch(()=>{});throw error;}
finally{for(const rows of pending.values())rows.forEach(finish);await context?.close();for(const socket of sockets.clients)socket.close();await new Promise(yes=>server.close(yes));await rm(work,{recursive:true,force:true,maxRetries:5,retryDelay:250});}
