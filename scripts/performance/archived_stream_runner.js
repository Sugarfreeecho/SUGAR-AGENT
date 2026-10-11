/* Foreground browser replay. RAF cadence is a timing proxy, not compositor FPS. */
(() => {
    const panel = document.createElement('div');
    panel.id = 'replay-controls';
    panel.style.cssText = 'position:fixed;top:4px;left:320px;z-index:99999;padding:5px 9px;background:#fff;color:#111;border:1px solid #999;font:12px sans-serif';
    panel.innerHTML = `<strong>隔离测试 ${__REPLAY_CONFIG__.version}</strong> <select id="replay-scenario"><option value="small">8k 历史</option><option value="large" selected>128k 历史</option><option value="label">128k 标记 / 8k 历史</option></select> <select id="replay-probe"><option value="motion">位移采样</option><option value="cadence">轻量帧间隔</option></select> <button id="replay-start">开始测量</button> <span id="replay-status">初始化</span>`;
    document.body.appendChild(panel);
    const status = document.getElementById('replay-status');
    const button = document.getElementById('replay-start');
    let trial = 0;
    const round = v => Number(v.toFixed(3));
    const quantile = (a,q) => {const s=a.slice().sort((x,y)=>x-y);return s[Math.min(s.length-1,Math.floor(q*s.length))]||0;};
    const sleep = ms => new Promise(resolve => setTimeout(resolve,ms));
    async function run() {
        button.disabled = true;
        const scenario = document.getElementById('replay-scenario').value;
        const probe = document.getElementById('replay-probe').value;
        try {
            while (!window.__archiveRuntime) await sleep(100);
            const corpus = await (await fetch('/__bench/corpus')).json();
            const tokenSize = scenario==='small'?8000:128000;
            const data = corpus[scenario==='large'?'128000':'8000'];
            const rows = [];
            // Fixed row size keeps the same text and row count across versions.
            for(let start=0;start<data.text.length;start+=1000) rows.push(data.text.slice(start,start+1000));
            const emptyBaseline=[];
            await new Promise(resolve=>{let last=0;const until=performance.now()+1200;function step(t){if(last)emptyBaseline.push(t-last);last=t;if(t<until)requestAnimationFrame(step);else resolve();}requestAnimationFrame(step);});
            const emptyFrameMs=quantile(emptyBaseline,.5);
            status.textContent = '准备历史';
            const ctx = __archiveRuntime.setup(tokenSize);
            __archiveRuntime.seed(ctx, rows);
            await sleep(1500);
            __archiveRuntime.follow(ctx);
            await sleep(500);
            let proc = ctx.currentProcessGroup.querySelector('.process-aggregate-body');
            const chat = document.getElementById('chat-container');
            const baseline=[];
            await new Promise(resolve=>{let last=0; const until=performance.now()+1200; function step(t){if(last)baseline.push(t-last);last=t;if(t<until)requestAnimationFrame(step);else resolve();}requestAnimationFrame(step);});
            const frameMs=quantile(baseline,.5);
            window.__MYAGENT_UI_PERF__?.reset();
            __replayObserverMetrics.forEach(m=>{m.calls=0;m.totalMs=0;m.maxMs=0;});
            __replayCallMetrics.forEach(m=>{m.calls=0;m.totalMs=0;m.maxMs=0;});
            const start=performance.now(), frames=[], longtasks=[], loaf=[], visibility=[], inputs=[];
            let sampling=true, previous=0, observer, loafObserver, textAnchor=null, anchorOffset=0, scroller=null, portId=0;
            function frame(t) {
                if(!sampling)return;
                const s={t:round(t-start),dt:previous?round(t-previous):0,visibility:document.visibilityState};previous=t;
                if(probe==='motion') {
                    const active=ctx.currentProcessGroup?.querySelector('.process-aggregate-body');
                    if(active && active!==proc){proc=active;portId++;scroller=null;textAnchor=null;}
                    s.port=portId;
                    s.top=round(proc.scrollTop);s.chatTop=round(chat.scrollTop);
                    // Reads are deliberately after the archived follower RAFs.
                    // A second cadence-only run controls for their layout cost.
                    s.height=proc.scrollHeight;s.client=proc.clientHeight;
                    const found=proc.querySelector('.feed-chunk.is-streaming .feed-chunk-scroller');
                    if(found!==scroller){scroller=found;textAnchor=null;}
                    if(scroller){
                        s.textLength=(scroller._llmRawText || scroller.textContent || '').length;
                        if(!textAnchor && scroller.textContent.length>80){
                            const walker=document.createTreeWalker(scroller,NodeFilter.SHOW_TEXT);let node;
                            while(node=walker.nextNode()){if(node.length>40){textAnchor=node;anchorOffset=20;break;}}
                        }
                        if((!textAnchor?.isConnected || textAnchor.length<=anchorOffset) && scroller.firstChild?.nodeType===3 && scroller.firstChild.length>40){textAnchor=scroller.firstChild;anchorOffset=20;}
                        if(textAnchor?.isConnected && textAnchor.length>anchorOffset){
                            const range=document.createRange();range.setStart(textAnchor,anchorOffset);range.setEnd(textAnchor,anchorOffset+1);
                            s.anchorY=round(range.getBoundingClientRect().top);
                        }
                        // Execution-record rendering replaces text nodes; use
                        // a stable character offset for this same logical row.
                        else if(scroller.firstChild?.nodeType===3 && scroller.firstChild.length>40){
                            textAnchor=scroller.firstChild;anchorOffset=20;
                        }
                    }
                }
                frames.push(s);requestAnimationFrame(frame);
            }
            try {observer=new PerformanceObserver(list=>list.getEntries().forEach(e=>longtasks.push({t:round(e.startTime-start),duration:round(e.duration)})));observer.observe({type:'longtask'});}catch{}
            try {loafObserver=new PerformanceObserver(list=>list.getEntries().forEach(e=>loaf.push({t:round(e.startTime-start),duration:round(e.duration),blocking:round(e.blockingDuration),renderStart:round(e.renderStart-start),styleAndLayoutStart:round(e.styleAndLayoutStart-start),scripts:e.scripts?.map(s=>({name:s.sourceFunctionName,url:s.sourceURL,char:s.sourceCharPosition,invoker:s.invoker,duration:round(s.duration),forced:round(s.forcedStyleAndLayoutDuration)}))})));loafObserver.observe({type:'long-animation-frame'});}catch{}
            const onVisibility=()=>visibility.push({t:round(performance.now()-start),state:document.visibilityState});
            document.addEventListener('visibilitychange',onVisibility);
            requestAnimationFrame(frame);
            status.textContent='测量输出与 3 次停顿';
            const response=await fetch('/__bench/stream?sid=replay-session');
            // Tee the response only to timestamp input delivery, then feed the
            // unmodified archive's SSE consumer the other branch.
            const [renderBody,timingBody]=response.body.tee();
            const timingTask=(async()=>{const reader=timingBody.getReader(),dec=new TextDecoder();let buf='';for(;;){const {value,done}=await reader.read();if(done)break;buf+=dec.decode(value,{stream:true});const lines=buf.split('\n');buf=lines.pop();for(const line of lines)if(line.startsWith('data: ')){const e=JSON.parse(line.slice(6));inputs.push({t:round(performance.now()-start),planned:e.__replay_planned_ms,seq:e.stream_seq,characters:e.delta.length});}}})();
            const streamResponse=new Response(renderBody,{status:200,headers:{'content-type':'text/event-stream'}});
            await __archiveRuntime.consume(streamResponse,ctx,'replay-session',0);
            await timingTask;
            await sleep(1500);
            sampling=false;observer?.disconnect();loafObserver?.disconnect();document.removeEventListener('visibilitychange',onVisibility);
            const gaps=frames.slice(1).map(f=>f.dt),moving=frames.slice(1).filter((f,i)=>f.top!==undefined && f.port===frames[i].port && Math.abs(f.top-frames[i].top)>.01);
            const steps=moving.map(f=>Math.abs(f.top-frames[frames.indexOf(f)-1].top));
            const summary={duration_ms:round(performance.now()-start),empty_frame_ms:round(emptyFrameMs),baseline_frame_ms:round(frameMs),raf_hz:round(1000*frames.length/(frames.at(-1).t-frames[0].t)),p95_gap_ms:round(quantile(gaps,.95)),p99_gap_ms:round(quantile(gaps,.99)),max_gap_ms:round(Math.max(...gaps)),gaps_over_1_5_frames:gaps.filter(g=>g>emptyFrameMs*1.5).length,gaps_over_50ms:gaps.filter(g=>g>50).length,longtasks:longtasks.length,longtask_ms:round(longtasks.reduce((n,e)=>n+e.duration,0)),moving_frames:moving.length,max_scroll_step_px:steps.length?round(Math.max(...steps)):null,reverse_steps:frames.slice(1).filter((f,i)=>f.port===frames[i].port && f.top<frames[i].top-.1).length};
            const generatedScroller=ctx.stream.querySelector('[data-execution-id="replay-live"] .feed-chunk-scroller') || ctx.llm.llmStreamReasoningScroller || ctx.stream.querySelector('.feed-chunk.is-streaming .feed-chunk-scroller');
            const generatedText=generatedScroller && (generatedScroller._llmRawText || generatedScroller.textContent) || '';
            const result={version:__REPLAY_CONFIG__.version,assets:__REPLAY_CONFIG__,scenario,probe,trial:Date.now(),context_label_tokens:tokenSize,history_tokenizer:'cl100k_base',history_tokens:data.token_count,history_characters:data.characters,history_rows:rows.length,dom_elements:ctx.stream.querySelectorAll('*').length,capabilities:__archiveRuntime.capabilities,environment:{ua:navigator.userAgent,width:innerWidth,height:innerHeight,dpr:devicePixelRatio,reducedMotion:matchMedia('(prefers-reduced-motion:reduce)').matches},valid:emptyFrameMs<40&&visibility.every(e=>e.state==='visible')&&frames.every(f=>f.visibility==='visible')&&inputs.length===240,errors:__replayErrors.slice(),summary,frames,inputs,longtasks,loaf,visibility};
            window.__replayLastResult=result;
            result.generated_characters=generatedText.length;
            result.valid=result.valid && generatedText.length>=900;
            result.archived_runtime_metrics=window.__MYAGENT_UI_PERF__?.snapshot();
            result.observer_metrics=__replayObserverMetrics;
            result.call_metrics=__replayCallMetrics;
            await fetch('/__bench/result',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(result)});
            status.textContent=`完成 ${summary.raf_hz.toFixed(1)} Hz / 最大间隔 ${summary.max_gap_ms} ms / 长任务 ${summary.longtasks}`;
            __archiveRuntime.stop(ctx);
        }catch(error){status.textContent='失败 '+error.message;console.error(error);}
        finally{button.disabled=false;}
    }
    button.addEventListener('click',run);
    const timer=setInterval(()=>{if(window.__archiveRuntime){clearInterval(timer);status.textContent='就绪';}},100);
})();
