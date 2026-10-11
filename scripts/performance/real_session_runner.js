/* Real durable history; the archived app owns rendering and automatic follow. */
(() => {
    const panel = document.createElement('aside');
    panel.id = 'real-replay-controls';
    panel.style.cssText = 'position:fixed;top:6px;left:280px;right:16px;z-index:99999;background:#fff;color:#222;border:1px solid #c8c8c8;border-radius:8px;padding:8px 12px;font:13px/1.6 sans-serif;box-shadow:0 2px 8px #0002';
    panel.innerHTML = `<div style="display:flex;flex-wrap:wrap;align-items:center;gap:9px">
        <strong>真实会话重放</strong>
        <label>版本 <select id="real-version" aria-label="前端版本"></select></label>
        <label>片段 <select id="real-segment" aria-label="会话片段"></select></label>
        <label>速度 <select id="real-speed" aria-label="播放速度"><option value="1">原速</option><option value="0.5">半速</option><option value="2">两倍速</option></select></label>
        <button id="real-play" disabled>播放</button><button id="real-restart" disabled>重新播放</button>
        <button id="real-mark" disabled>标记卡顿</button>
        <label><input type="checkbox" id="real-measure" checked>记录帧间隔</label>
        <span id="real-status">读取真实历史…</span>
        </div><div id="real-source" style="color:#666;font-size:12px"></div>
        <div id="real-notes" style="color:#666;font-size:12px">请观察执行过程框内文字在换行上移时，是否停住后突然继续。时间间隔来自服务端日志；原浏览器画面未保存。</div>`;
    document.body.appendChild(panel);
    const byId = id => document.getElementById(id);
    const status = byId('real-status'), play = byId('real-play'), restart = byId('real-restart');
    const select = byId('real-segment'), version = byId('real-version'), speed = byId('real-speed');
    const mark = byId('real-mark'), measure = byId('real-measure');
    let data, segment, ctx, controller, consuming, playing = false, finished = false, loading = false;
    let frames = [], markers = [], visibility = [], lastFrame = 0, frameHandle, trial, paused = false;
    const tracing = window.__realTraceEnabled;
    let idleFrames = [];
    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
    function latestPacket() {
        return segment?.packets.findLast(packet => packet.seq <= Number(ctx?.lastRuntimeSeq || 0));
    }
    function statusText() {
        const seconds = ((latestPacket()?.at_ms || 0) / 1000).toFixed(1);
        const count = segment.packets.filter(packet => packet.seq <= Number(ctx.lastRuntimeSeq || 0) && 'text_delta' in packet.update).length;
        return `${seconds} / ${(segment.duration_ms / 1000).toFixed(1)} 秒 · ${count}/${segment.delta_count} 增量`;
    }
    function sample(t) {
        if (!playing || !measure.checked) return;
        if (lastFrame) frames.push({t: Number(t.toFixed(3)), gap_ms: Number((t - lastFrame).toFixed(3)), seq: ctx.lastRuntimeSeq});
        lastFrame = t;
        frameHandle = requestAnimationFrame(sample);
    }
    function stopSampling() {
        cancelAnimationFrame(frameHandle);
        lastFrame = 0;
    }
    async function pause() {
        if (!playing) return;
        playing = false;
        paused = true;
        stopSampling();
        controller.abort();
        await consuming;
        __archiveRuntime.pauseReal(ctx);
        play.textContent = '继续';
        status.textContent = '已暂停 · ' + statusText();
        mark.disabled = true;
    }
    async function loadSegment() {
        loading = true;
        if (playing) await pause();
        play.disabled = restart.disabled = select.disabled = true;
        finished = false;
        segment = data.segments.find(row => row.id === select.value);
        status.textContent = '准备真实历史…';
        ctx = __archiveRuntime.setup(segment.context_tokens, {real: true, name: data.name + '（重放）'});
        __archiveRuntime.seedReal(ctx, segment);
        frames = []; markers = []; visibility = []; paused = false; trial = Date.now();
        idleFrames = [];
        mark.textContent = '标记卡顿';
        const originalTime = new Date(segment.started_at).toLocaleString('zh-CN', {timeZone: 'Asia/Shanghai', hour12: false});
        byId('real-source').textContent = `${data.name} · ${data.session_id} · ${originalTime} · ${segment.context_tokens.toLocaleString()} input tokens · 历史 ${segment.history.length} 条 / ${(segment.history_characters / 10000).toFixed(1)} 万字符`;
        byId('real-notes').textContent = '请观察执行过程框内文字在换行上移时，是否停住后突然继续。时间间隔来自服务端日志；原浏览器画面未保存。';
        // Let history hydration settle before the user begins the replay.
        await sleep(700);
        __archiveRuntime.follow(ctx);
        if (tracing) {
            await new Promise(resolve => {
                let last = 0;
                const until = performance.now() + 1200;
                function idle(t) {
                    if (last) idleFrames.push(t - last);
                    last = t;
                    if (t < until) requestAnimationFrame(idle); else resolve();
                }
                requestAnimationFrame(idle);
            });
        }
        status.textContent = '就绪 · ' + statusText();
        play.textContent = '播放';
        play.disabled = restart.disabled = select.disabled = false;
        loading = false;
    }
    async function start() {
        if (loading) return;
        if (playing) return pause();
        if (finished) await loadSegment();
        playing = true;
        controller = new AbortController();
        play.textContent = '暂停'; mark.disabled = false;
        speed.disabled = select.disabled = version.disabled = measure.disabled = true;
        status.textContent = '播放中 · ' + statusText();
        lastFrame = 0;
        if (measure.checked) frameHandle = requestAnimationFrame(sample);
        consuming = (async () => {
            const traceStarted = performance.now(), longtasks = [], loaf = [], inputs = [];
            const observers = [];
            let timingTask;
            try {
                if (tracing) {
                    window.__realRenderCalls = [];
                    window.__MYAGENT_UI_PERF__?.reset();
                    for (const type of ['longtask', 'long-animation-frame']) {
                        try {
                            const observer = new PerformanceObserver(list => {
                                for (const entry of list.getEntries()) {
                                    if (type === 'longtask') longtasks.push({t: entry.startTime, duration: entry.duration});
                                    else loaf.push({t: entry.startTime, duration: entry.duration, blocking: entry.blockingDuration,
                                        renderStart: entry.renderStart, styleAndLayoutStart: entry.styleAndLayoutStart,
                                        paintTime: entry.paintTime, presentationTime: entry.presentationTime,
                                        scripts: entry.scripts?.map(script => ({name: script.sourceFunctionName,
                                            url: script.sourceURL, char: script.sourceCharPosition,
                                            invoker: script.invoker, duration: script.duration,
                                            forced: script.forcedStyleAndLayoutDuration}))});
                                }
                            });
                            observer.observe({type}); observers.push(observer);
                        } catch {}
                    }
                }
                let response = await fetch(`/__real/stream?segment=${segment.id}&speed=${speed.value}&after=${ctx.lastRuntimeSeq || 0}`, {signal: controller.signal});
                if (tracing) {
                    const [renderBody, timingBody] = response.body.tee();
                    timingTask = (async () => {
                        const reader = timingBody.getReader(), decoder = new TextDecoder();
                        let buffer = '';
                        for (;;) {
                            const {done, value} = await reader.read();
                            if (done) break;
                            buffer += decoder.decode(value, {stream: true});
                            const lines = buffer.split('\n'); buffer = lines.pop();
                            for (const line of lines) if (line.startsWith('data: ')) {
                                const event = JSON.parse(line.slice(6));
                                inputs.push({t: performance.now(), seq: event.runtime_seq,
                                    server_ms: event.__server_elapsed_ms, planned_ms: event.__server_planned_ms,
                                    original_ms: event.__original_offset_ms,
                                    characters: event.update?.text_delta?.length || 0});
                            }
                        }
                    })();
                    // Attach a rejection handler immediately, including aborts.
                    timingTask.catch(() => {});
                    response = new Response(renderBody, {status: response.status, headers: response.headers});
                }
                await __archiveRuntime.consume(response, ctx, 'replay-session', segment.history.length);
                if (timingTask) await timingTask;
                if (!playing) return;
                finished = true; playing = false; stopSampling();
                __archiveRuntime.finishReal(ctx);
                const row = Array.from(ctx.stream.querySelectorAll('[data-execution-id]')).find(item => item.dataset.executionId === segment.execution_id)
                    || Array.from(ctx.currentProcessGroup?.querySelectorAll('.feed-item[data-log-type="llm-reasoning"]') || []).findLast(item => Number(item.dataset.reactIter) === segment.iteration);
                const scroller = row?.querySelector('.feed-chunk-scroller');
                const text = scroller?._llmRawText || scroller?.textContent || '';
                const maxGap = Math.max(0, ...frames.map(frame => frame.gap_ms));
                const result = {version: __REPLAY_CONFIG__.version, session_id: data.session_id,
                    journal_sha256: data.journal_sha256, segment: segment.id, trial, speed: Number(speed.value),
                    paused, measured: measure.checked, verified_text: text === segment.text,
                    expected_characters: segment.text.length, rendered_characters: text.length,
                    max_raf_gap_ms: maxGap, frames, markers, visibility, errors: __replayErrors.slice(),
                    environment: {width: innerWidth, height: innerHeight, dpr: devicePixelRatio, ua: navigator.userAgent}};
                if (tracing) {
                    observers.forEach(observer => observer.disconnect());
                    result.trace = {start: traceStarted, idle_frame_gaps_ms: idleFrames,
                        inputs, longtasks, loaf, renders: window.__realRenderCalls.slice(),
                        runtime_metrics: window.__MYAGENT_UI_PERF__?.snapshot(),
                        focus: document.hasFocus(), visible: document.visibilityState};
                }
                window.__realReplayLastResult = result;
                await fetch('/__real/result', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(result)});
                status.textContent = `${result.verified_text ? '完成，文字校验通过' : '文字校验失败'} · ${statusText()}`;
                byId('real-notes').textContent = `${measure.checked ? '动画回调最大间隔 ' + maxGap.toFixed(1) + ' ms（不是屏幕实际帧率）；' : ''}已标记 ${markers.length} 处。可重新播放，或切换备份版本对照同一段真实内容。`;
                play.textContent = '再播放'; mark.disabled = true;
            } catch (error) {
                if (error.name !== 'AbortError') {
                    playing = false; stopSampling();
                    status.textContent = '重放失败：' + error.message;
                    console.error(error);
                }
            } finally {
                observers.forEach(observer => observer.disconnect());
                speed.disabled = select.disabled = version.disabled = measure.disabled = false;
            }
        })();
        window.__realReplay = {get ctx() {return ctx;}, get segment() {return segment;}, get playing() {return playing;}};
    }
    play.addEventListener('click', start);
    restart.addEventListener('click', async () => {await loadSegment(); await start();});
    select.addEventListener('change', loadSegment);
    mark.addEventListener('click', () => {
        markers.push({at_ms: latestPacket()?.at_ms || 0, seq: ctx.lastRuntimeSeq, wall_time: Date.now()});
        mark.textContent = `标记卡顿 (${markers.length})`;
    });
    version.addEventListener('change', () => {
        const dest = new URL(version.value);
        dest.searchParams.set('real', '1'); dest.searchParams.set('segment', select.value);
        location.href = dest.href;
    });
    document.addEventListener('visibilitychange', () => {if (playing) visibility.push({state: document.visibilityState, seq: ctx.lastRuntimeSeq});});
    setInterval(() => {if (playing) status.textContent = '播放中 · ' + statusText();}, 500);
    (async () => {
        try {
            while (!window.__archiveRuntime) await sleep(100);
            [data, window.__realReplayVersions] = await Promise.all([
                fetch('/__real/session').then(response => response.json()),
                fetch('/__real/versions').then(response => response.json())
            ]);
            document.title = '真实会话重放 · ' + data.name;
            const requested = new URLSearchParams(location.search).get('segment') || '37';
            for (const row of data.segments) select.add(new Option(`第 ${row.iteration} 步 · ${(row.duration_ms / 1000).toFixed(0)} 秒`, row.id, false, row.id === requested));
            for (const row of window.__realReplayVersions) version.add(new Option(row.version.slice(4, 6) + '/' + row.version.slice(6), row.url, false, row.version === __REPLAY_CONFIG__.version));
            await loadSegment();
        } catch (error) {status.textContent = '初始化失败：' + error.message; console.error(error);}
    })();
})();
