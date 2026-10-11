/* Archived application owns rendering. Measurements use lightweight RAF timing;
 * scroll-position reads and render-function timers are opt-in. */
(() => {
    const query = new URLSearchParams(location.search), config = window.__REPLAY_CONFIG__;
    const importId = query.get('replay') || query.get('session');
    const panel = document.createElement('aside'); panel.id = 'replay-tool';
    panel.style.cssText = 'position:fixed;top:6px;left:280px;right:14px;z-index:99999;padding:9px 12px;border:1px solid #bfc9db;border-radius:8px;background:#fff;color:#263246;font:12px/1.6 "Segoe UI","Microsoft YaHei",sans-serif;box-shadow:0 2px 9px #0002';
    panel.innerHTML = `<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><a href="/" style="color:#4165ae">会话重放工具</a>
    <label>版本 <select id="replay-version" aria-label="重放版本"></select></label>
    <label>任务 <select id="replay-run" aria-label="重放任务"></select></label>
    <label>范围 <select id="replay-scope" aria-label="重放范围"><option value="text">流式文本</option><option value="step">执行轮次（含工具）</option><option value="run">整次任务</option></select></label>
    <label>轮次 <select id="replay-segment" aria-label="重放轮次" style="max-width:210px"></select></label>
    <label>速度 <select id="replay-speed" aria-label="播放速度"><option value="1">原速</option><option value="0.5">半速</option><option value="2">2倍</option><option value="4">4倍</option><option value="8">8倍</option></select></label>
    <label><input id="replay-simulate" type="checkbox" checked>缺少增量时逐字模拟</label><label>模拟 <input id="replay-cps" aria-label="模拟字速" type="number" min="10" max="1000" value="120" style="width:58px"> 字/秒</label>
    <button id="replay-play" disabled>播放</button><button id="replay-restart" disabled>重新播放</button><button id="replay-stop" disabled>结束并保存</button>
    <select id="replay-marker-kind" aria-label="卡顿类型"><option>停顿</option><option>轻微抖动</option><option>文字看不清</option><option>其他</option></select><button id="replay-mark" disabled>标记卡顿（Alt+M）</button>
    <label><input id="replay-record" type="checkbox" checked>记录帧间隔</label></div>
    <div id="replay-source" style="color:#67768e;font-size:11px"></div><div id="replay-status" role="status">读取会话…</div><div id="replay-result" style="color:#4666a7"></div>
    <details><summary style="cursor:pointer;color:#65748b">测量与对照选项</summary><div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <label>卡顿阈值 <input id="replay-threshold" type="number" min="20" max="1000" value="50" style="width:58px"> ms</label>
    <label><input id="replay-scroll" type="checkbox">记录滚动位置（增加测量开销）</label>
    <label><input id="replay-render" type="checkbox">记录渲染函数耗时</label>
    <label><input id="replay-skip-idle" type="checkbox">将超过2秒的空档缩至2秒（改变节奏）</label>
    <label>历史 <select id="replay-history"><option value="full">完整历史</option><option value="hidden">临时隐藏旧条目</option></select></label>
    <label>本次备注 <input id="replay-note" type="text" maxlength="2000" placeholder="播放结束时保存"></label></div>
    <div style="font-size:11px;color:#78859a">只记录动画回调时刻时，不逐帧读取布局。暂停、切后台、变速及隐藏历史都会记录条件；回调频率不是屏幕实际FPS。</div></details>
    <details id="replay-experiment-panel"><summary style="cursor:pointer;color:#4165ae">1007 对照开关（勾选 = 启用；含共有滚动路径）</summary>
    <div id="replay-experiment-list" style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;max-height:260px;overflow:auto;padding:8px 0"></div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><label>对照组合 <select id="replay-experiment-preset" aria-label="对照组合"><option value="manual">手动选择</option><option value="original">1007 原版</option><option value="baseline">1004 完整基线（保留平滑）</option><option value="js">1004 脚本 + 1007 样式</option><option value="css">1007 脚本 + 1004 样式</option><option value="modules">模块回退（保留平滑）</option></select></label><button id="replay-experiment-all">全部开启（原版）</button><button id="replay-experiment-none">全部关闭</button><button id="replay-experiment-apply">应用并重载本段</button><span id="replay-experiment-pending"></span></div>
    <div style="font-size:11px;color:#67768e">关闭资源／模块开关 = 回退到 1004；整套回退优先于细项，已覆盖操作会写入记录。比较连续上滑时请保留自动跟随和平滑动画。</div>
    <div id="replay-experiment-status" style="font-size:11px;white-space:pre-wrap;margin-top:6px"></div>
    <div id="replay-experiment-coverage" style="font-size:11px;color:#78859a"></div></details>`;
    document.body.append(panel);
    const fold=document.createElement('button');fold.id='replay-tool-toggle';fold.textContent='收起面板';panel.firstElementChild.prepend(fold);
    const setFold=value=>{panel.classList.toggle('is-minimized',value);fold.textContent=value?'展开面板':'收起面板';};
    fold.onclick=()=>setFold(!panel.classList.contains('is-minimized'));
    const toolStyle=document.createElement('style');
    toolStyle.textContent='#replay-tool button,#replay-tool select,#replay-tool input{font:inherit;line-height:1.4;color:#263246;border:1px solid #bfc9db;border-radius:4px;padding:3px 6px;background:#fff;width:auto;min-height:0;box-shadow:none}#replay-tool button:disabled{opacity:.5}#replay-tool label{display:inline-flex;align-items:center;gap:3px;margin:0}#replay-tool input[type=checkbox]{width:13px;padding:0}';
    document.head.append(toolStyle);
    toolStyle.textContent+='#replay-tool.is-minimized>div:first-child>:not(#replay-tool-toggle):not(#replay-play):not(#replay-mark){display:none}#replay-tool.is-minimized #replay-source,#replay-tool.is-minimized details{display:none}#replay-tool.is-minimized #replay-result{font-size:10px}';
    const $ = id => document.getElementById('replay-' + id);
    const experiment = config.experiments;
    let experimentReceipt;
    const settingIds=['speed','simulate','cps','record','scroll','render','skip-idle','history','threshold','note'];
    for(const id of settingIds)if(query.has('setting_'+id)){
        const el=$(id),value=query.get('setting_'+id);
        if(el.type==='checkbox')el.checked=value==='1';else el.value=value;
    }
    function settingsUrl() {
        const url=new URL(location.href);
        for(const id of settingIds){const el=$(id);url.searchParams.set('setting_'+id,el.type==='checkbox'?(el.checked?'1':'0'):el.value);}
        url.searchParams.set('replay',importId);if(segment)url.searchParams.set('segment',segment.id);
        return url;
    }
    function selectedDisabled() {return experiment.features.filter(f=>!document.getElementById('exp-'+f.id).checked).map(f=>f.id);}
    const experimentPresets={original:[],baseline:['frontend_bundle'],js:['js_bundle'],css:['css_bundle'],modules:['session_modules','context_refresh','stream_pipeline','history_module','interaction_modules','media_module','review_updates','plugin_style_wait']};
    function showPending() {
        const selected=selectedDisabled();
        $('experiment-preset').value=Object.keys(experimentPresets).find(id=>{const off=experimentPresets[id];return off.length===selected.length&&off.every(value=>selected.includes(value));})||'manual';
        const changed=JSON.stringify(selected)!==JSON.stringify(experiment.disabled);
        $('experiment-pending').textContent=changed?'待应用；当前播放仍使用已加载配置':'与已加载配置一致';
        $('experiment-apply').disabled=!changed||playing||paused||loading;
    }
    $('experiment-panel').hidden=!experiment.supported;
    if(experiment.supported){
        for(const feature of [...experiment.features].sort((a,b)=>(a.commit==='shared'?0:a.scope==='group'?1:2)-(b.commit==='shared'?0:b.scope==='group'?1:2))){
            const item=document.createElement('div'),label=document.createElement('label'),input=document.createElement('input');
            input.type='checkbox';input.id='exp-'+feature.id;input.className='replay-exp-input';input.checked=!experiment.disabled.includes(feature.id);input.onchange=showPending;
            label.append(input,document.createTextNode(feature.label));item.append(label);
            const description=document.createElement('div');description.style.cssText='font-size:11px;color:#67768e;padding-left:17px';description.textContent=feature.description;item.append(description);$('experiment-list').append(item);
        }
        $('experiment-panel').open=true;
        $('experiment-coverage').textContent='未覆盖：'+experiment.uncovered.join(' ');
        for(const [id,value] of [['experiment-all',true],['experiment-none',false]])$(id).onclick=()=>{document.querySelectorAll('.replay-exp-input').forEach(el=>el.checked=value);showPending();};
        $('experiment-preset').onchange=()=>{
            const off=experimentPresets[$('experiment-preset').value];if(!off)return;
            for(const feature of experiment.features)document.getElementById('exp-'+feature.id).checked=!off.includes(feature.id);
            showPending();
        };
        $('experiment-apply').onclick=()=>{const url=settingsUrl(),off=selectedDisabled();if(off.length)url.searchParams.set('exp_off',off.join(','));else url.searchParams.delete('exp_off');location.href=url.href;};
    }
    let catalog, segment, ctx, playing = false, paused = false, finished = false, loading = false;
    let controller, consuming, frameHandle, lastFrame = 0, trial, startClock, pauseCount = 0, measured, threshold;
    let markers = [], visibility = [], focusEvents = [], observers = [], tally, saved = false;
    let frames, inputs, longtasks, loaf, scrolls;
    const LIMIT = 60000;
    class Ring {
        constructor(limit = LIMIT) {this.limit = limit; this.values = []; this.next = 0; this.total = 0;}
        push(value) {this.total++; if(this.values.length < this.limit) this.values.push(value); else {this.values[this.next] = value; this.next = (this.next + 1) % this.limit;}}
        all() {return this.values.length < this.limit ? this.values.slice() : this.values.slice(this.next).concat(this.values.slice(0,this.next));}
        dropped() {return Math.max(0,this.total - this.limit);}
    }
    const api = window.createReplayApi(config.token);
    const rest = ms => new Promise(resolve => setTimeout(resolve,ms));
    const relative = () => Number((performance.now() - startClock).toFixed(3));
    function controls() {
        ['version','run','scope','segment','speed','simulate','cps','record','scroll','render','skip-idle','history','threshold'].forEach(id => $(id).disabled = playing || paused || loading);
        $('play').disabled = loading || !segment; $('restart').disabled = loading || !segment;
        $('stop').disabled = !playing && !paused; $('mark').disabled = !playing;
        $('play').textContent = playing ? '暂停' : paused ? '继续' : finished ? '再播放' : '播放';
        document.querySelectorAll('.replay-exp-input').forEach(el=>el.disabled=playing||paused||loading);
        $('experiment-all').disabled=$('experiment-none').disabled=$('experiment-preset').disabled=playing||paused||loading;
        if(experiment.supported)showPending();
    }
    function currentPacket() {return segment?.packets.findLast(p => p.seq <= Number(ctx?.lastRuntimeSeq || 0));}
    function progress() {
        const count = segment?.packets.filter(p => p.seq <= Number(ctx?.lastRuntimeSeq || 0)).length || 0;
        const followLabel=experiment.follow_mode==='off'?'关闭自动跟随 · ':experiment.follow_mode==='immediate'?'直接贴底 · ':'';
        return `${followLabel}${segment?.playback?.synthetic?'逐字模拟 · ':''}${((currentPacket()?.at_ms || 0)/1000).toFixed(1)} / ${((segment?.duration_ms || 0)/1000).toFixed(1)} 秒 · ${count}/${segment?.packet_count || 0} 条事件`;
    }
    function sample(t) {
        if(!playing || !measured) return;
        if(lastFrame && document.visibilityState === 'visible') {
            const gap = t - lastFrame;
            tally.count++; tally.total += gap; tally.max = Math.max(tally.max,gap); if(gap > threshold) tally.over++;
            const bucket = Math.round(gap*10); tally.hist[bucket] = (tally.hist[bucket] || 0) + 1;
            frames.push({t_ms:Number((t-startClock).toFixed(3)),gap_ms:Number(gap.toFixed(3)),seq:ctx.lastRuntimeSeq});
        }
        lastFrame = t; frameHandle = requestAnimationFrame(sample);
    }
    function captureEntry(type, entry) {
        if(type === 'longtask') longtasks.push({t_ms:Number((entry.startTime-startClock).toFixed(3)),duration_ms:entry.duration});
        else loaf.push({t_ms:Number((entry.startTime-startClock).toFixed(3)),duration_ms:entry.duration,blocking_ms:entry.blockingDuration,
            render_start_ms:entry.renderStart-startClock,style_layout_start_ms:entry.styleAndLayoutStart-startClock,
            scripts:entry.scripts?.map(s=>({name:s.sourceFunctionName,url:s.sourceURL,duration_ms:s.duration,forced_style_layout_ms:s.forcedStyleAndLayoutDuration}))});
    }
    function beginObservers() {
        for (const type of ['longtask','long-animation-frame']) {
            try {const observer = new PerformanceObserver(list=>list.getEntries().forEach(e=>captureEntry(type,e))); observer.observe({type}); observers.push({type,observer});} catch {}
        }
    }
    function endObservers() {for(const {type,observer} of observers) {observer.takeRecords().forEach(e=>captureEntry(type,e)); observer.disconnect();} observers=[];}
    function initRecord() {
        trial = Date.now(); startClock = performance.now(); markers=[]; visibility=[{t_ms:0,state:document.visibilityState}]; focusEvents=[{t_ms:0,state:document.hasFocus()?'focus':'blur'}]; pauseCount=0; saved=false;
        frames=new Ring();inputs=new Ring();longtasks=new Ring(12000);loaf=new Ring(12000);scrolls=new Ring();
        tally={count:0,total:0,max:0,over:0,hist:{}}; window.__realRenderCalls=[];window.__realRenderCallsDropped=0;window.__replayErrors=[];
        window.__realMeasureRender=$('render').checked;
        window.__replayFollowControl.blocked_calls=0;window.__replayFollowControl.immediate_writes=0;
        threshold=Math.max(20,Math.min(1000,Number($('threshold').value)||50)); measured=$('record').checked;
        $('mark').textContent='标记卡顿（Alt+M）'; $('result').textContent='';
        beginObservers();
    }
    function expectedChecks() {
        return segment.expected_texts.map(expected=>{
            const rows=Array.from(ctx.stream.querySelectorAll('[data-execution-id]'));
            let row=rows.find(r=>r.dataset.executionId===expected.execution_id);
            if(!row) {
                const type=expected.kind==='response'?'llm-response':'llm-reasoning';
                let candidates=Array.from(ctx.stream.querySelectorAll(`.feed-item[data-log-type="${type}"]`)).filter(r=>Number(r.dataset.reactIter)===Number(expected.iteration));
                if(expected.process_group_id) candidates=candidates.filter(r=>r.closest('.process-aggregate')?.dataset.processGroupId===expected.process_group_id);
                if(expected.run_id) {const same=candidates.filter(r=>r.closest('.process-aggregate')?.dataset.processRunId===expected.run_id);if(same.length)candidates=same;}
                row=candidates.at(-1);
            }
            return {execution_id:expected.execution_id,expected_sha256:expected.sha256,expected_characters:expected.text.length,
                ...__archiveRuntime.verifyText(row,expected)};
        });
    }
    function summary() {
        let n=0,p95=null;
        for(const [bin,count] of Object.entries(tally.hist).sort((a,b)=>Number(a[0])-Number(b[0]))) {n+=count;if(n>=tally.count*.95) {p95=Number(bin)/10;break;}}
        return {frame_count:tally.count,mean_raf_callbacks_per_second:tally.total?Number((tally.count/tally.total*1000).toFixed(1)):null,
            p95_gap_ms:p95,max_gap_ms:Number(tally.max.toFixed(3)),gaps_over_threshold:tally.over,threshold_ms:threshold,
            quantile_precision_ms:0.1,frame_note:'Visible-page RAF callback intervals; not display FPS.'};
    }
    function result(status, compact=false) {
        const checks=expectedChecks(),verified=checks.length ? checks.every(c=>c.verified) : null;
        return {import_id:importId,segment_id:segment.id,version:config.version,trial,speed:Number($('speed').value),
            playback:segment.playback,
            experiments:{...experimentReceipt,follow_runtime:__archiveRuntime.followState(ctx)},assets:{base_js_sha256:config.js_sha256,base_css_sha256:config.css_sha256,served_js_sha256:experiment.js.served_sha256,served_css_sha256:experiment.css.served_sha256},
            skip_idle:$('skip-idle').checked,status,measured,started_at:new Date(trial).toISOString(),
            pause_count:pauseCount,visibility:visibility.slice(),focus_events:focusEvents.slice(),markers:markers.slice(),note:$('note').value,
            text_verified:verified,text_checks:checks,errors:window.__replayErrors.slice(),summary:summary(),
            eligible_for_comparison:status==='completed'&&!segment.playback.synthetic&&measured&&$('speed').value==='1'&&!$('skip-idle').checked&&$('history').value==='full'&&!pauseCount&&verified!==false&&!visibility.some(v=>v.state==='hidden')&&!window.__replayErrors.length&&experimentReceipt?.ready,
            frames:compact?frames.all().slice(-100):frames.all(),inputs:compact?inputs.all().slice(-30):inputs.all(),
            longtasks:compact?longtasks.all().slice(-30):longtasks.all(),long_animation_frames:compact?[]:loaf.all(),
            scroll_positions:compact?[]:scrolls.all(),render_calls:compact?[]:window.__realRenderCalls.slice(-LIMIT),
            capture_limits:{frames_dropped:frames.dropped(),inputs_dropped:inputs.dropped(),longtasks_dropped:longtasks.dropped(),long_animation_frames_dropped:loaf.dropped(),scrolls_dropped:scrolls.dropped(),render_calls_dropped:window.__realRenderCallsDropped,compact_page_exit:compact},
            environment:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio,ua:navigator.userAgent,language:navigator.language,
                hardware_concurrency:navigator.hardwareConcurrency,root_font_px:parseFloat(getComputedStyle(document.documentElement).fontSize),
                visibility:document.visibilityState,focus:document.hasFocus(),theme:localStorage.getItem('myagent-theme')},
            settings:{history:$('history').value,scroll_positions:$('scroll').checked,render_timing:$('render').checked},
            timing_source:segment.timing_source};
    }
    async function save(status) {
        if(saved) return;
        endObservers(); saved=true;
        try {const r=await api('/api/replay/result',{method:'POST',body:result(status)});window.__portableReplayLastResult=r;
            const s=r.summary; $('result').replaceChildren(document.createTextNode(`已保存 · 平均回调 ${s.mean_raf_callbacks_per_second ?? '—'} 次/秒 · P95 ${s.p95_gap_ms ?? '—'} ms · 最长 ${s.max_gap_ms} ms · 标记 ${r.markers.length} 处 · `));
            const a=document.createElement('a');a.href='/api/replay/result.json?record='+r.record_id;a.textContent='下载JSON';a.style.color='#4165ae';$('result').append(a);
            const report=document.createElement('a');report.href='/api/replay/report.zip?session='+importId;report.textContent='　导出报告ZIP';report.style.color='#4165ae';$('result').append(report);
        }catch(e){saved=false;$('result').textContent='记录保存失败：'+e.message;}
    }
    async function prepare() {
        if(playing||paused) await stop('interrupted');
        loading=true;segment=null;controls();$('status').textContent='准备所选轮次的真实历史…';
        try {
            const segmentId=$('segment').value;
            segment=await api(`/api/replay/segment?session=${importId}&segment=${segmentId}&simulate=${$('simulate').checked?1:0}&cps=${$('cps').value}`);
            ctx=__archiveRuntime.setup(segment.context_tokens,{real:true,name:catalog.name+'（历史重放）',threshold:segment.context_threshold});
            __archiveRuntime.seedReal(ctx,segment);
            if($('history').value==='hidden') {const group=ctx.currentProcessGroup;for(const el of Array.from(ctx.stream.children))if(el!==group&&!el.contains(group))el.style.display='none';group?.querySelectorAll('.process-aggregate-body > *').forEach(el=>el.style.display='none');}
            finished=false;paused=false;
            $('source').textContent=`${catalog.name} · 任务${segment.run_number} / ${segment.iteration!=null?'第'+segment.iteration+'步':'整次任务'} · ${segment.context_tokens.toLocaleString()} input tokens · 历史 ${segment.history.length} 条 / ${(segment.history_characters/10000).toFixed(1)} 万字符`;
            if(segment.warnings.length) $('source').textContent+=' · '+segment.warnings.join('；');
            await rest(700); __archiveRuntime.follow(ctx);
            verifyExperiments();
            if(!experimentReceipt.ready)throw new Error('开关生效校验失败：'+experimentReceipt.error);
            const savedUrl=new URL(location.href);savedUrl.searchParams.set('replay',importId);savedUrl.searchParams.set('segment',segment.id);history.replaceState(history.state,'',savedUrl.href);
            $('status').textContent='就绪 · '+progress();
            window.__portableReplay={get ctx(){return ctx;},get segment(){return segment;},get playing(){return playing;}};
        }catch(e){segment=null;$('status').textContent='准备失败：'+e.message;}finally{loading=false;controls();}
    }
    function verifyExperiments() {
        const state=window.__replayExperimentState,checks=[];
        const follow=__archiveRuntime.followState(ctx);
        checks.push({feature:'follow_mode',property:'runtime-mode',actual:follow.mode,passed:follow.mode===experiment.follow_mode});
        if(follow.mode==='off')checks.push({feature:'auto_follow',property:'live-follow-disabled',actual:follow.live_auto_follow||follow.chat_following||follow.process_following,passed:!follow.live_auto_follow&&!follow.chat_following&&!follow.process_following});
        const off=new Set(experiment.disabled),body=ctx.stream.querySelector('.process-aggregate-body');
        const folded=ctx.stream.querySelector('.process-aggregate.is-collapsed > .process-aggregate-body');
        if(experiment.supported&&off.has('collapsed_layout')&&folded)checks.push({feature:'collapsed_layout',property:'display',actual:getComputedStyle(folded).display,passed:getComputedStyle(folded).display==='none'});
        if(experiment.supported&&off.has('size_motion')&&experiment.asset_versions.css==='20261007'){
            const intrinsic=getComputedStyle(document.documentElement).getPropertyValue('interpolate-size');
            checks.push({feature:'size_motion',property:'interpolate-size',actual:intrinsic,passed:!intrinsic||intrinsic.trim()==='numeric-only'});
            if(body){const transitions=getComputedStyle(body).transitionProperty;checks.push({feature:'size_motion',property:'transition-property',actual:transitions,passed:!/(^|,\s*)(height|min-height|max-height|padding-block|all)(,|$)/.test(transitions)});}
        }
        const wires=[...segment.history,...segment.packets.map(p=>p.wire)];
        const compression=wires.filter(w=>String(w.type||'').includes('compression')||String(w.type||'').includes('summary_reasoning')).length;
        const media=wires.filter(w=>w.attachments?.length||w.update?.attachments?.length).length;
        const review=wires.filter(w=>w.type==='file_changes_updated'||w.ui||w.update?.ui).length;
        const pluginLink=Array.from(document.querySelectorAll('link[data-plugin-chat-style]')).find(el=>el.href.includes('change-review'));
        experimentReceipt={supported:experiment.supported,label:experiment.label,fingerprint:experiment.fingerprint,disabled:experiment.disabled,features:experiment.features,follow_mode:follow.mode,
            asset_versions:experiment.asset_versions,html_source_sha256:experiment.html_source_sha256,covered_operations:experiment.covered_operations,
            definition_sha256:experiment.definition_sha256,source_operations:state?.source_operations||[],module_operations:experiment.js.operations,css_operations:experiment.css.operations,
            checks,ready:!!state?.source_ready&&!state?.error&&checks.every(c=>c.passed),error:state?.error||checks.filter(c=>!c.passed).map(c=>c.feature+':'+c.actual).join(';'),
            plugin:{enabled:config.plugins,version:experiment.plugin_version,sha256:experiment.plugin_sha256,style_requested:!!pluginLink,style_loaded:!!pluginLink?.sheet,module_requested:performance.getEntriesByType('resource').some(entry=>entry.name.includes('/plugin-assets/change-review/web/change-review.js'))},
            coverage:{history_paging:false,backend_services:false,upload_batching:false,compression_events:compression,attachment_events:media,review_events:review,sidebar_session_count:1},uncovered:experiment.uncovered};
        window.__portableReplayExperiments=experimentReceipt;
        if(experiment.supported)$('experiment-status').textContent=(experimentReceipt.ready?'配置已加载并通过校验：':'校验失败：')+experiment.label+'\n配置 ID '+experiment.fingerprint+' · 源码替换 '+experimentReceipt.source_operations.length+' 处 · 模块替换 '+experiment.js.operations.length+' 处 · CSS 覆盖 '+experiment.css.operations.length+' 组\n'+
            `资源来源：脚本 ${experiment.asset_versions.js.slice(-4)} · 样式 ${experiment.asset_versions.css.slice(-4)} · 页面 ${experiment.asset_versions.html.slice(-4)} · 插件 ${experiment.asset_versions.plugin.slice(-4)}；被整套回退覆盖的细项 ${experiment.covered_operations.length} 处。\n`+
            `滚动模式：${{smooth:'原版平滑跟随',immediate:'直接贴底（无持续跟随 RAF）',off:'关闭自动跟随'}[follow.mode]}。当前片段：压缩事件 ${compression} · 附件事件 ${media} · 审阅元数据事件 ${review}。`+(config.plugins?'':' 插件已通过 URL 参数禁用。');
    }
    async function pause() {
        playing=false;paused=true;pauseCount++;cancelAnimationFrame(frameHandle);lastFrame=0;controller.abort();
        await consuming; __archiveRuntime.pauseReal(ctx); $('status').textContent='已暂停 · '+progress();controls();
    }
    async function stop(status='stopped') {
        const hadRun=playing||paused;
        playing=false;paused=false;cancelAnimationFrame(frameHandle);lastFrame=0;controller?.abort();
        if(consuming) await consuming;
        if(ctx) __archiveRuntime.finishReal(ctx);
        if(hadRun) {await save(status);finished=true;$('status').textContent='已结束 · '+progress();}
        controls();
    }
    async function start() {
        if(loading||!segment)return;
        if(playing)return pause();
        if(finished)await prepare();
        if(!segment)return;
        if(!paused)initRecord();
        setFold(true);
        paused=false;playing=true;controller=new AbortController();controls();$('status').textContent='播放中 · '+progress();
        if(measured)frameHandle=requestAnimationFrame(sample);
        consuming=(async()=>{
            let timing;
            try{
                let response=await fetch(`/api/replay/stream?session=${importId}&segment=${segment.id}&version=${config.version}&speed=${$('speed').value}&after=${ctx.lastRuntimeSeq||0}&skip_idle=${$('skip-idle').checked?1:0}&simulate=${$('simulate').checked?1:0}&cps=${$('cps').value}`,{signal:controller.signal});
                if(!response.ok)throw new Error((await response.json()).error||'读取事件失败');
                const [renderBody,timingBody]=response.body.tee();
                timing=(async()=>{const reader=timingBody.getReader(),decoder=new TextDecoder();let buffer='';for(;;){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const lines=buffer.split('\n');buffer=lines.pop();for(const line of lines)if(line.startsWith('data: ')){const event=JSON.parse(line.slice(6));inputs.push({t_ms:relative(),seq:event.runtime_seq,server_ms:event.__server_elapsed_ms,planned_ms:event.__server_planned_ms,original_ms:event.__original_offset_ms,type:event.type});}}})();timing.catch(()=>{});
                response=new Response(renderBody,{status:response.status,headers:response.headers});
                await __archiveRuntime.consume(response,ctx,'replay-session',segment.history.length);
                await timing;if(!playing)return;
                await new Promise(resolve=>requestAnimationFrame(resolve));if(!playing)return;
                playing=false;finished=true;cancelAnimationFrame(frameHandle);lastFrame=0;
                __archiveRuntime.finishReal(ctx);await save('completed');
                const checks=window.__portableReplayLastResult?.text_checks || [];
                $('status').textContent=(checks.length?(checks.every(c=>c.verified)?'完成，文字校验通过':'完成，文字校验未通过'):'完成，此范围没有文字校验项目')+' · '+progress();controls();
            }catch(e){if(e.name!=='AbortError'){playing=false;finished=true;cancelAnimationFrame(frameHandle);__archiveRuntime.finishReal(ctx);window.__replayErrors.push(String(e));await save('failed');$('status').textContent='重放失败：'+e.message;controls();}}
        })();
    }
    function mark() {if(!playing)return;markers.push({t_ms:relative(),original_ms:currentPacket()?.at_ms||0,seq:ctx.lastRuntimeSeq,kind:$('marker-kind').value,note:$('note').value});$('mark').textContent=`已标记 ${markers.length} 处（Alt+M）`;}
    function fillUnits(preferred) {
        const units=catalog.units.filter(u=>u.run_id===$('run').value&&u.scope===$('scope').value);$('segment').replaceChildren();
        units.forEach(u=>{$('segment').add(new Option(`${u.iteration!=null?'第'+u.iteration+'步 · ':''}${{reasoning:'思考',response:'回复',llm_reasoning:'思考',llm_response:'回复'}[u.kind]||u.kind} · ${(u.duration_ms/1000).toFixed(1)}秒`,u.id));});
        if(units.some(u=>u.id===preferred))$('segment').value=preferred;
        if(units.length)prepare();else{segment=null;$('status').textContent='这个任务没有此类片段，请切换范围';controls();}
    }
    $('play').onclick=start;$('restart').onclick=async()=>{await prepare();await start();};$('stop').onclick=()=>stop();$('mark').onclick=mark;
    $('run').onchange=()=>fillUnits();$('scope').onchange=()=>fillUnits();$('segment').onchange=prepare;$('history').onchange=prepare;$('simulate').onchange=prepare;$('cps').onchange=prepare;
    $('version').onchange=async()=>{if(playing||paused)await stop('interrupted');const url=settingsUrl();url.pathname='/view/'+$('version').value+'/';if($('version').value!=='20261007')url.searchParams.delete('exp_off');location.href=url.href;};
    document.addEventListener('keydown',e=>{if(e.altKey&&e.code==='KeyM'){e.preventDefault();mark();}});
    document.addEventListener('visibilitychange',()=>{if(playing||paused){visibility.push({t_ms:relative(),state:document.visibilityState,seq:ctx.lastRuntimeSeq});lastFrame=0;}});
    for(const event of ['focus','blur'])window.addEventListener(event,()=>{if(playing)focusEvents.push({t_ms:relative(),state:event});});
    document.addEventListener('scroll',e=>{if(playing&&$('scroll').checked&&e.target instanceof Element&&e.target.matches('.chat-container,.process-aggregate-body'))scrolls.push({t_ms:relative(),port:e.target.classList.contains('process-aggregate-body')?'process':'chat',top:e.target.scrollTop,seq:ctx.lastRuntimeSeq});},true);
    window.addEventListener('pagehide',()=>{if((playing||paused)&&!saved){try{const partial=result('page_closed',true);fetch('/api/replay/result',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-Replay-Token':api.token()},body:JSON.stringify(partial)});}catch{}}});
    setInterval(()=>{if(playing)$('status').textContent='播放中 · '+progress();},500);
    (async()=>{try{const deadline=performance.now()+15000;while(!window.__archiveRuntime){if(window.__replayExperimentState?.error)throw new Error(window.__replayExperimentState.error);if(performance.now()>deadline)throw new Error('前端启动适配未完成，请检查 versions 资源是否完整');await rest(100);}catalog=await api('/api/replay/session?id='+importId);const requested=catalog.units.find(u=>u.id===query.get('segment'))||catalog.units.find(u=>u.scope==='text')||catalog.units[0];config.versions.forEach(v=>$('version').add(new Option(v.label,v.version,false,v.version===config.version)));catalog.units.filter(u=>u.scope==='run').forEach(u=>$('run').add(new Option('任务'+u.run_number,u.run_id)));$('run').value=requested.run_id;$('scope').value=requested.scope;document.title='会话重放 · '+catalog.name;fillUnits(requested.id);}catch(e){$('status').textContent='初始化失败：'+e.message;}})();
})();
