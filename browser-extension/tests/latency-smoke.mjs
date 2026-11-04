import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {createRequire} from 'node:module';
import {mkdtemp,mkdir,rm,writeFile,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'../..'),require=createRequire(resolve(root,'plugins/browser-use/node/package.json'));
const extensionDir=resolve(process.env.SUGAR_LATENCY_EXTENSION || resolve(root,'browser-extension/dist'));
const {chromium}=require('playwright');
const work=await mkdtemp(resolve(tmpdir(),'sugar-latency-')),artifacts=resolve(root,'browser-extension/artifacts/latency');await mkdir(artifacts,{recursive:true});
const backend=spawn(resolve(root,'python/python.exe'),['-u',resolve(import.meta.dirname,'session-runtime-fixture.py'),resolve(work,'backend')],{cwd:root,windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8'}});
let context,panel,diagnostics='';const errors=[];
backend.stderr.on('data',data=>diagnostics=(diagnostics+data).slice(-4000));
const ready=new Promise((yes,no)=>{createInterface({input:backend.stdout}).on('line',line=>{try{const data=JSON.parse(line);if(data.baseUrl)yes(data);}catch{}});backend.once('exit',code=>no(Error('Fixture exited '+code+' '+diagnostics)));});
async function waitFor(fn,message){for(let i=0;i<500;i++){if(await fn())return;await new Promise(yes=>setTimeout(yes,30));}throw Error(message);}
try{
  const {baseUrl,sessions:[sid]}=await ready;
  async function fixture(body){const result=await fetch(baseUrl+'/__fixture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});assert.equal(result.status,200);return result.json();}
  await waitFor(async()=>{try{await fixture({models_fail:false,latency_history:true});return true;}catch{return false;}},'Fixture unavailable');
  context=await chromium.launchPersistentContext(resolve(work,'profile'),{channel:'msedge',headless:true,locale:'zh-CN',viewport:{width:400,height:800},args:['--disable-background-timer-throttling','--disable-renderer-backgrounding',`--disable-extensions-except=${extensionDir}`,`--load-extension=${extensionDir}`]});
  panel=await context.newPage();panel.on('pageerror',error=>errors.push(error.message));
  await panel.addInitScript(()=>{
    window.samples=[];
    const original=chrome.runtime.connect.bind(chrome.runtime);
    chrome.runtime.connect=(...args)=>{const port=original(...args);port.onMessage.addListener(message=>{
      const event=message.event;
      if(!event?.fixture_emitted_ms || !['llm_reasoning_delta','llm_response_delta'].includes(event.type))return;
      const row={type:event.type,run:event.run_id,received:Date.now(),emitted:event.fixture_emitted_ms,marker:event.delta};samples.push(row);
      function findNode(){
        const article=document.querySelector(`article[data-run-id="${row.run}"]`),selector=row.type==='llm_reasoning_delta'?'.reason pre':'.answer';
        return article && [...article.querySelectorAll(selector)].find(node=>{
          const text=node.textContent.trim();
          return text && (row.marker.startsWith(text) || text.includes(row.marker));
        });
      }
      const observer=new MutationObserver(()=>{if(findNode()){row.dom=Date.now();observer.disconnect();}});
      observer.observe(document.getElementById('root'),{childList:true,subtree:true,characterData:true});
      function inspect(){
        const node=findNode();
        if(node){const viewport=document.querySelector('.reading').getBoundingClientRect(),rect=node.getBoundingClientRect();
          if(node.getClientRects().length && rect.top<viewport.bottom && rect.bottom>viewport.top && getComputedStyle(node).visibility!=='hidden'){row.visible=Date.now();return;}}
        if(Date.now()-row.received<5000)requestAnimationFrame(inspect);else observer.disconnect();
      }
      inspect();
    });return port;};
  });
  await panel.goto('chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo/sidepanel.html');
  const {code}=await(await fetch(baseUrl+'/api/browser/v1/pairings',{method:'POST',headers:{Origin:baseUrl,'Content-Type':'application/json'},body:'{}'})).json();
  await panel.evaluate(async({baseUrl,code,sid})=>{await chrome.storage.local.set({'sugar.lastSession':sid,'sugar.preferences':{language:'zh-CN',theme:'dark',design:'selected-m-20261030',autoPageContext:false}});const result=await chrome.runtime.sendMessage({type:'pair',baseUrl,code});if(!result.ok)throw Error(result.error);},{baseUrl,code,sid});
  await waitFor(async()=>await panel.locator('.turn').count()>=15 && await panel.locator('.model-picker>.popover-trigger').isEnabled(),'History not loaded');
  const reference=await context.newPage();await reference.goto(baseUrl+'/__latency/reference');await waitFor(()=>reference.evaluate(()=>window.ready),'SSE reference not ready');
  await panel.bringToFront();
  for(const mode of ['collapsed','expanded']){
    if(mode==='expanded')for(let i=0;i<3;i++)await panel.locator('.process-heading').nth(i).click();
    await panel.locator('.reading').evaluate(node=>node.scrollTop=node.scrollHeight);await panel.waitForTimeout(150);
    for(let i=0;i<5;i++){
      const run='latency-'+mode+'-'+i;
      const response=await fetch(baseUrl+'/__latency/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run})});assert.equal(response.status,200);
      await waitFor(()=>panel.evaluate(run=>window.samples.filter(row=>row.run===run).length===2 && window.samples.filter(row=>row.run===run).every(row=>row.dom),run),'Delta did not render');
    }
  }
  await panel.waitForTimeout(200);
  const received=await reference.evaluate(()=>window.samples),samples=await panel.evaluate(()=>window.samples);
  const rows=samples.map(row=>{const match=received.find(other=>other.run===row.run && other.type===row.type);assert.ok(match);return{run:row.run,type:row.type,wire_ms:row.received-row.emitted,sse_ms:match.received-match.emitted,extra_wire_ms:row.received-match.received,render_ms:row.dom-row.received,visible_ms:row.visible?row.visible-row.received:null};});
  assert.equal(rows.length,20);assert.deepEqual(errors,[]);
  const metrics=Object.fromEntries(['collapsed','expanded'].map(mode=>{const list=rows.filter(row=>row.run.includes(mode));return[mode,Object.fromEntries(['wire_ms','extra_wire_ms','render_ms','visible_ms'].map(key=>{const values=list.map(row=>row[key]).filter(Number.isFinite).sort((a,b)=>a-b);return[key,{median:values[Math.floor(values.length/2)],max:values.at(-1)}];}))];}));
  const version=JSON.parse(await readFile(resolve(extensionDir,'manifest.json'),'utf8')).version;
  await writeFile(resolve(artifacts,`first-delta-${version}.json`),JSON.stringify({version,reference:'same-event direct SSE, no model wait',metrics,rows},null,2));
  console.log(JSON.stringify({version,metrics},null,2));
}catch(error){const samples=await panel?.evaluate(()=>window.samples).catch(()=>[]);throw Error(error.message+'\nSamples: '+JSON.stringify(samples)+'\n'+diagnostics.slice(-1200),{cause:error});}
finally{if(context)await context.close();backend.kill();await new Promise(yes=>backend.exitCode!==null?yes():backend.once('exit',yes));await rm(work,{recursive:true,force:true,maxRetries:5,retryDelay:250});}
