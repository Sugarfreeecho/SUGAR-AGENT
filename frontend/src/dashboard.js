import './styles/dashboard.css';

const openState = new Map();
let lastData = { sessions: [] };
let inflight = null;
let selectedRequestKey = '__total__';
const chartScrollState = new Map();
const PHASE_DEFS=[
  ['pre_api','API 发送前准备'],['api_send','API 发送'],['first_token','首 token'],
  ['llm_output','LLM 输出'],['tool_execution','工具执行'],['round_postprocess','本轮后处理'],
];

const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const ms = value => { const n=Number(value); if(!Number.isFinite(n)) return '—'; return n>=1000?(n/1000).toFixed(n>=10000?1:2)+' s':Math.max(0,Math.round(n))+' ms'; };
const num = value => Number.isFinite(Number(value)) ? Number(value) : 0;

function phaseData(req,key){
  const phases=req.phases||{};
  if(phases[key])return phases[key];
  const stream=((phases.llm_stream||{}).events)||[],at=name=>num((stream.find(e=>e.step===name)||{}).ms_since_api_start);
  if(key==='api_send'){const v=Math.max(0,at('stream_created')-at('request_start'));return{total_ms:v,events:{request_start_to_stream_created:v}};}
  if(key==='first_token'){const v=Math.max(0,at('first_delta')-at('stream_created'));return{total_ms:v,events:{stream_created_to_first_delta:v}};}
  if(key==='llm_output'){const v=Math.max(0,(at('stream_exhausted')||at('turn_ready'))-at('first_delta'));return{total_ms:v,events:{first_delta_to_stream_end:v}};}
  if(key==='tool_execution'){const values=(req.tools||[]).map(t=>num(t.duration_ms)),v=values.length?Math.max(...values):0;return{total_ms:v,events:{estimated_parallel_wall_time:v}};}
  if(key==='round_postprocess'){const a=num((phases.tool_result_post||{}).total_ms),b=num((phases.tool_to_next_api||{}).total_ms);return{total_ms:a+b,events:{tool_result_post:a,tool_to_next_api:b}};}
  return{total_ms:0,events:{}};
}

function flatten(data, sessionId='') {
  const rows=[];
  (data.sessions||[]).forEach(session => {
    if(sessionId && session.session_id!==sessionId) return;
    (session.runs||[]).forEach(run => (run.requests||[]).forEach(req => rows.push({session,run,req})));
  });
  rows.sort((a,b)=>String(a.req.started_at||a.run.started_at||'').localeCompare(String(b.req.started_at||b.run.started_at||'')));
  return rows;
}

function lineChart(target, rows, series, valueSuffix='ms') {
  const el=document.getElementById(target); if(!el) return;
  if(!rows.length){el.innerHTML='<div class="empty">暂无数据</div>';return;}
  const visiblePoints=20,baseWidth=900,widthScale=Math.max(1,rows.length/visiblePoints),W=baseWidth*widthScale,H=270,P={l:55,r:18,t:24,b:50};
  const values=[]; rows.forEach(row=>series.forEach(s=>values.push(num(s.value(row)))));
  const max=Math.max(1,...values), x=i=>P.l+(rows.length===1?0.5:i/(rows.length-1))*(W-P.l-P.r), y=v=>H-P.b-(num(v)/max)*(H-P.t-P.b);
  const colors=['#89b4fa','#f9e2af','#a6e3a1','#cba6f7','#f38ba8','#94e2d5','#fab387','#74c7ec'];
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" style="width:${widthScale*100}%">`;
  for(let i=0;i<=4;i++){const v=max*i/4, yy=y(v);svg+=`<line x1="${P.l}" y1="${yy}" x2="${W-P.r}" y2="${yy}" class="grid"/><text x="${P.l-8}" y="${yy+4}" text-anchor="end">${Math.round(v)}${valueSuffix}</text>`;}
  series.forEach((s,si)=>{const points=rows.map((r,i)=>`${x(i)},${y(s.value(r))}`).join(' ');svg+=`<polyline points="${points}" fill="none" stroke="${colors[si%colors.length]}" stroke-width="2"/>`;rows.forEach((r,i)=>{const raw=s.value(r),tip={session:r.session.session_name,session_id:r.session.session_id,run_id:r.run.run_id,time:r.req.started_at||r.run.started_at||'',react_iter:r.req.react_iter,model:r.req.model||'',metric:s.name,value:num(raw),display:valueSuffix==='ms'?ms(raw):num(raw).toLocaleString(),unit:valueSuffix};svg+=`<circle class="chart-point" data-tip="${esc(JSON.stringify(tip))}" cx="${x(i)}" cy="${y(raw)}" r="4" fill="${colors[si%colors.length]}"/>`;});});
  rows.forEach((r,i)=>{if(rows.length<=14||i%Math.ceil(rows.length/12)===0)svg+=`<text x="${x(i)}" y="${H-25}" text-anchor="middle">${esc(new Date(r.req.started_at||r.run.started_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}))}</text><text x="${x(i)}" y="${H-10}" text-anchor="middle">#${r.req.react_iter}</text>`;});
  svg+='</svg>';
  const legend='<div class="legend">'+series.map((s,i)=>`<span><i style="background:${colors[i%colors.length]}"></i>${esc(s.name)}</span>`).join('')+'</div>';
  const previous=chartScrollState.get(target);el.innerHTML='<div class="chart-scroll">'+svg+'</div>'+legend;
  const scrollEl=el.querySelector('.chart-scroll');
  requestAnimationFrame(()=>{
    const maxScroll=Math.max(0,scrollEl.scrollWidth-scrollEl.clientWidth);
    scrollEl.scrollLeft=previous==null||previous.atEnd?maxScroll:Math.min(maxScroll,previous.left);
  });
  scrollEl.onscroll=()=>chartScrollState.set(target,{left:scrollEl.scrollLeft,atEnd:scrollEl.scrollLeft>=scrollEl.scrollWidth-scrollEl.clientWidth-2});
}

function renderCharts(rows){
  let cumulativeInput=0,cumulativeOutput=0;
  const cumulativeRows=rows.map(row=>{
    cumulativeInput+=num((row.req.usage||{}).prompt_tokens||(row.req.context||{}).estimated_tokens);
    cumulativeOutput+=num((row.req.usage||{}).completion_tokens);
    return Object.assign({},row,{cumulativeInput,cumulativeOutput});
  });
  lineChart('api-chart',cumulativeRows,[
    {name:'累计输入 token',value:r=>r.cumulativeInput},
    {name:'累计输出 token',value:r=>r.cumulativeOutput},
    {name:'上下文长度',value:r=>num((r.req.context||{}).estimated_tokens)},
  ],'');
  lineChart('phase-chart',rows,PHASE_DEFS.map(([key,label])=>({name:label,value:r=>num(phaseData(r.req,key).total_ms)})));
}

function eventsHtml(events){
  if(Array.isArray(events)) return events.map(e=>`<div class="event-row"><span>${esc(e.step||'event')}</span><b>${esc(ms(e.ms_since_api_start))}</b><small>${esc(Object.keys(e).filter(k=>!['step','ms_since_api_start','model'].includes(k)).map(k=>k+'='+e[k]).join(' · '))}</small></div>`).join('');
  return Object.keys(events||{}).map(k=>`<div class="event-row"><span>${esc(k)}</span><b>${esc(ms(events[k]))}</b></div>`).join('')||'<div class="empty-inline">暂无子事件</div>';
}

function phaseHtml(session,run,req,name,phase){
  const key=[session.session_id,run.run_id,req.react_iter,name].join('|');
  const opened=openState.has(key)?openState.get(key):(name==='llm_stream');
  const label=(PHASE_DEFS.find(item=>item[0]===name)||[null,name])[1];
  return `<details class="phase" data-open-key="${esc(key)}" ${opened?'open':''}><summary><span>${esc(label)}</span><b>${esc(ms(phase.total_ms))}</b></summary><div>${eventsHtml(phase.events)}</div></details>`;
}

function toolsHtml(session,run,req){
  if(!(req.tools||[]).length)return '';
  const key=[session.session_id,run.run_id,req.react_iter,'tools'].join('|');
  const opened=openState.get(key)===true;
  return `<details class="phase" data-open-key="${esc(key)}" ${opened?'open':''}><summary><span>tools</span><b>${req.tools.length}</b></summary><div>${req.tools.map(t=>`<div class="event-row"><span>${esc(t.tool)}</span><b>${esc(ms(t.duration_ms))}</b><small>${t.failed?'失败':'成功'}</small></div>`).join('')}</div></details>`;
}

const requestKey=row=>[row.session.session_id,row.run.run_id,row.req.react_iter].join('|');

function requestDetailHtml(row){
  if(!row)return '<div class="empty">暂无执行统计</div>';
  const {session,run,req}=row,c=req.context||{},u=req.usage||{};
  return `<section class="session-block"><header><div><h2>${esc(session.session_name)}</h2><code>${esc(session.session_id)}</code></div><span>${esc(new Date(req.started_at||run.started_at||'').toLocaleString())}</span></header><article class="run-block"><header><div><strong>${esc(run.mode||'chat')}</strong><code>${esc(run.run_id)}</code></div><em class="${esc(run.status||'')}">${esc(run.status||'')}</em></header><div class="request-card"><header><div><strong>LLM #${req.react_iter}</strong><span>${esc(req.model||'')}</span></div><em>${esc(req.status||'')}</em></header><div class="metrics"><span>首 token<b>${esc(ms(req.first_token_ms))}</b></span><span>API 总耗时<b>${esc(ms(req.duration_ms))}</b></span><span>输入 token<b>${esc(u.prompt_tokens??c.estimated_tokens??'—')}</b></span><span>输出 token<b>${esc(u.completion_tokens??'—')}</b></span><span>上下文<b>${esc(c.estimated_tokens??'—')} / ${esc(c.context_window??'—')}</b></span><span>消息 / 工具<b>${esc(c.messages??'—')} / ${esc(c.tools??'—')}</b></span></div>${PHASE_DEFS.map(([n])=>phaseHtml(session,run,req,n,phaseData(req,n))).join('')}${toolsHtml(session,run,req)}</div></article></section>`;
}

function cumulativeDetailHtml(rows){
  if(!rows.length)return '<div class="empty">暂无执行统计</div>';
  const input=rows.reduce((n,r)=>n+num((r.req.usage||{}).prompt_tokens||(r.req.context||{}).estimated_tokens),0);
  const output=rows.reduce((n,r)=>n+num((r.req.usage||{}).completion_tokens),0);
  const apiTotal=rows.reduce((n,r)=>n+num(r.req.duration_ms),0);
  const ttftRows=rows.filter(r=>Number.isFinite(Number(r.req.first_token_ms)));
  const avgTtft=ttftRows.length?ttftRows.reduce((n,r)=>n+num(r.req.first_token_ms),0)/ttftRows.length:0;
  const latest=rows[rows.length-1],phaseTotals={},phaseEvents={},tools=[];
  rows.forEach(row=>{PHASE_DEFS.forEach(([name])=>{const p=phaseData(row.req,name);phaseTotals[name]=(phaseTotals[name]||0)+num(p.total_ms);Object.keys(p.events||{}).forEach(event=>phaseEvents[name]=Object.assign(phaseEvents[name]||{},{[event]:(phaseEvents[name]||{})[event]?num((phaseEvents[name]||{})[event])+num(p.events[event]):num(p.events[event])}));});(row.req.tools||[]).forEach(t=>tools.push(t));});
  return `<section class="session-block"><header><div><h2>累计总值</h2><code>${esc(document.getElementById('session-filter').value?'当前会话筛选':'全部会话')}</code></div><span>${rows.length} 次 LLM 请求</span></header><article class="run-block"><div class="request-card"><div class="metrics"><span>平均首 token<b>${esc(ms(avgTtft))}</b></span><span>API 累计耗时<b>${esc(ms(apiTotal))}</b></span><span>累计输入 token<b>${input.toLocaleString()}</b></span><span>累计输出 token<b>${output.toLocaleString()}</b></span><span>最新上下文<b>${esc((latest.req.context||{}).estimated_tokens??'—')} / ${esc((latest.req.context||{}).context_window??'—')}</b></span><span>工具调用<b>${tools.length}</b></span></div>${PHASE_DEFS.map(([name,label])=>`<details class="phase" data-open-key="total|${esc(name)}"><summary><span>${esc(label)}</span><b>${esc(ms(phaseTotals[name]))}</b></summary><div>${eventsHtml(phaseEvents[name])}</div></details>`).join('')}</div></article></section>`;
}

function render(data){
  const visibleSessions=(data.sessions||[]).filter(s=>!['s-followup','s-final-first'].includes(String(s.session_id||'').toLowerCase())&&!['s-followup','s-final-first'].includes(String(s.session_name||'').toLowerCase()));
  data=Object.assign({},data,{sessions:visibleSessions});lastData=data; const filter=document.getElementById('session-filter'), selected=filter.value;
  filter.innerHTML='<option value="">全部会话</option>'+visibleSessions.map(s=>`<option value="${esc(s.session_id)}">${esc(s.session_name)} · ${esc(s.session_id.slice(0,8))}</option>`).join('');
  if(selected && visibleSessions.some(s=>s.session_id===selected))filter.value=selected;
  const rows=flatten(data,filter.value); renderCharts(rows);
  const input=rows.reduce((n,r)=>n+num((r.req.usage||{}).prompt_tokens||(r.req.context||{}).estimated_tokens),0), output=rows.reduce((n,r)=>n+num((r.req.usage||{}).completion_tokens),0);
  document.getElementById('summary').innerHTML=`<div><span>会话</span><b>${new Set(rows.map(r=>r.session.session_id)).size}</b></div><div><span>LLM 请求</span><b>${rows.length}</b></div><div><span>输入 token</span><b>${input.toLocaleString()}</b></div><div><span>输出 token</span><b>${output.toLocaleString()}</b></div>`;
  const requestFilter=document.getElementById('request-filter'),latest=rows.length?rows[rows.length-1]:null;
  if(selectedRequestKey!=='__total__'&&!rows.some(row=>requestKey(row)===selectedRequestKey))selectedRequestKey='__total__';
  requestFilter.innerHTML='<option value="__total__">累计总值</option>'+rows.slice().reverse().map(row=>`<option value="${esc(requestKey(row))}">${esc(row.session.session_name)} · ${esc(new Date(row.req.started_at||row.run.started_at||'').toLocaleString())} · LLM #${row.req.react_iter}</option>`).join('');
  requestFilter.value=selectedRequestKey;
  const selectedRow=rows.find(row=>requestKey(row)===selectedRequestKey)||latest;
  document.getElementById('dashboard-body').innerHTML=selectedRequestKey==='__total__'?cumulativeDetailHtml(rows):requestDetailHtml(selectedRow);
  document.querySelectorAll('details[data-open-key]').forEach(d=>d.addEventListener('toggle',()=>openState.set(d.dataset.openKey,d.open)));
}

async function refresh(){
  if(inflight)inflight.abort(); inflight=new AbortController();
  try{const r=await fetch('/api/execution-metrics',{cache:'no-store',signal:inflight.signal});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'加载失败');render(p.data||{sessions:[]});}
  catch(e){if(e.name!=='AbortError')document.getElementById('dashboard-body').innerHTML=`<div class="empty">加载失败：${esc(e.message||e)}</div>`;}
}
document.getElementById('session-filter').addEventListener('change',()=>{selectedRequestKey='__total__';render(lastData);});
document.getElementById('request-filter').addEventListener('change',event=>{selectedRequestKey=event.target.value;render(lastData);});
document.getElementById('refresh-btn').addEventListener('click',refresh);
document.getElementById('back-to-chat-btn').addEventListener('click',()=>{
  if(window.opener && !window.opener.closed){
    try{window.opener.focus();window.close();return;}catch(_error){}
  }
  location.href='/';
});
const chartTooltip=document.getElementById('chart-tooltip');
document.addEventListener('pointerover',event=>{
  const point=event.target.closest&&event.target.closest('.chart-point');
  if(!point||!chartTooltip)return;
  try{
    const t=JSON.parse(point.dataset.tip||'{}');
    chartTooltip.innerHTML=`<strong>${esc(t.metric)}</strong><b>${esc(t.display)}</b><dl><dt>会话</dt><dd>${esc(t.session)}</dd><dt>时间</dt><dd>${esc(t.time?new Date(t.time).toLocaleString():'—')}</dd><dt>执行轮次</dt><dd>LLM #${esc(t.react_iter)}</dd><dt>模型</dt><dd>${esc(t.model||'—')}</dd><dt>Run ID</dt><dd>${esc(t.run_id||'—')}</dd><dt>Session ID</dt><dd>${esc(t.session_id||'—')}</dd></dl>`;
    chartTooltip.classList.add('is-visible');chartTooltip.setAttribute('aria-hidden','false');
  }catch(_error){}
});
document.addEventListener('pointermove',event=>{
  if(!chartTooltip||!chartTooltip.classList.contains('is-visible'))return;
  const gap=14,w=chartTooltip.offsetWidth||280,h=chartTooltip.offsetHeight||180;
  chartTooltip.style.left=Math.max(8,Math.min(innerWidth-w-8,event.clientX+gap))+'px';
  chartTooltip.style.top=Math.max(8,Math.min(innerHeight-h-8,event.clientY+gap))+'px';
});
document.addEventListener('pointerout',event=>{
  if(!chartTooltip)return;
  const point=event.target.closest&&event.target.closest('.chart-point');
  if(point){chartTooltip.classList.remove('is-visible');chartTooltip.setAttribute('aria-hidden','true');}
});
refresh(); setInterval(refresh,1000);
