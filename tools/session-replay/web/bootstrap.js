/* Replay adapter; optional 1007 changes are guarded by exact source matches. */
window.__MYAGENT_FEATURES__ = Object.assign({}, window.__MYAGENT_FEATURES__, {smoothStream: true});
window.__CONTEXT_WINDOW__ = 512000;
window.__REPLAY_CONFIG__.plugins = new URLSearchParams(location.search).get('plugins') !== 'off';
window.__REPLAY_CONFIG__.observerTiming = new URLSearchParams(location.search).get('observers') === 'time';
window.__replayObserverMetrics = [];
window.__replayCallMetrics = [];
window.__realTraceEnabled = true;
window.__realMeasureRender = false;
window.__realRenderCallsDropped = 0;
window.__realRenderCalls = [];
const replayOff = window.__REPLAY_CONFIG__.experiments.disabled || [];
window.__replayFollowControl = {mode:replayOff.includes('auto_follow')?'off':replayOff.includes('smooth_follow')?'immediate':'smooth',blocked_calls:0,immediate_writes:0};
if (window.__REPLAY_CONFIG__.observerTiming) {
    for (const type of ['MutationObserver','ResizeObserver','IntersectionObserver']) {
        const Original = window[type];
        if (!Original) continue;
        window[type] = function(callback, options) {
            const metric = {type,callback:String(callback).slice(0,260),stack:new Error().stack,calls:0,totalMs:0,maxMs:0};
            __replayObserverMetrics.push(metric);
            return new Original(function(...args) {
                const start=performance.now();
                try{return callback.apply(this,args);}
                finally{const dt=performance.now()-start;metric.calls++;metric.totalMs+=dt;metric.maxMs=Math.max(metric.maxMs,dt);}
            },options);
        };
        window[type].prototype=Original.prototype;
    }
}
if (!window.__REPLAY_CONFIG__.plugins) {
    const originalFetch = window.fetch;
    window.fetch = function(input, options) {
        if (String(input) === '/api/extensions') return Promise.resolve(new Response('{"ui_contributions":[]}', {headers:{'content-type':'application/json'}}));
        return originalFetch.call(this,input,options);
    };
}
if(!localStorage.getItem('myagent-font-size-px'))localStorage.setItem('myagent-font-size-px', '16');
if(!localStorage.getItem('myagent-theme'))localStorage.setItem('myagent-theme', 'light');
window.__replayErrors = [];
window.addEventListener('error', event => __replayErrors.push(String(event.message)));
window.addEventListener('unhandledrejection', event => __replayErrors.push(String(event.reason)));
window.__replayExperimentState = {fingerprint:window.__REPLAY_CONFIG__.experiments.fingerprint, source_ready:false, source_operations:[], error:null};
const nativeFunction = window.Function;
window.Function = function (...args) {
    const last = args.length - 1;
    const isApplication = String(args[last]).includes('function newDomContext(');
    if (isApplication) {
        try {
            const operations = window.__REPLAY_CONFIG__.experiments.source_operations;
            if(operations.length) args[last] = String(args[last]).replace(/\r\n/g,'\n');
            for(const op of operations) {
                const parts = args[last].split(op.before);
                if(parts.length !== 2) throw new Error('开关适配失败：'+op.feature+' / '+op.name+'，匹配 '+(parts.length-1)+' 处');
                args[last] = parts.join(op.after);
                window.__replayExperimentState.source_operations.push({feature:op.feature,name:op.name});
            }
        } catch(error) {window.__replayExperimentState.error=String(error);throw error;}
        args[last] += `
        window.__archiveRuntime = {
            setup: function(tokenCount, options) {
                options = options || {};
                currentSessionId = 'replay-session';
                sessionStore.currentSessionId = currentSessionId;
                sessionStore.resetSseSeq(currentSessionId);
                if(typeof executionRecordsBySession!=='undefined')executionRecordsBySession.delete(currentSessionId);
                sessionStore.sessionsById.set(currentSessionId, {id:currentSessionId,name:options.name || 'Isolated stream replay',work_dir:''});
                var stream = getVisibleChatStream();
                if (!stream) { ensureVisibleChatStreamSlot(); stream = getVisibleChatStream(); }
                stream.replaceChildren();
                stream.dataset.sessionId = currentSessionId;
                var ctx = newDomContext(stream);
                ctx.runId = options.real ? '' : 'replay-run'; ctx.processGroupId = options.real ? '' : 'replay-process';
                ctx.runStartedAt = new Date().toISOString();
                setSessionRunState(currentSessionId, {ctx:ctx,runId:'replay-run',controller:new AbortController()});
                setContextTokensForSession(currentSessionId,tokenCount,options.threshold || 512000,{system:0,tools:0,messages:tokenCount});
                applyContextTokenLabelForCurrentSession();
                liveAutoFollow = window.__replayFollowControl.mode !== 'off'; streamChatNearBottom = liveAutoFollow; streamProcNearBottom = liveAutoFollow;
                return ctx;
            },
            seedReal: function(ctx, segment) {
                replayingMessages = true;
                try {
                    if(typeof beginMessageReplay==='function')beginMessageReplay(currentSessionId,{total:segment.history.length,range_start:0,range_end:segment.history.length});
                    if(typeof seedRenderContextRunGenerations==='function')seedRenderContextRunGenerations(ctx,segment.history,segment.history_records);
                    segment.history.forEach(function(event,i) {
                        if(typeof reduceAndRenderMessageEvent==='function')reduceAndRenderMessageEvent(ctx,event,{sessionId:currentSessionId,eventIndex:i,source:'history'});
                        else renderEvent(ctx,event,i,currentSessionId);
                    });
                    segment.history_records.forEach(function(record) {
                        if(typeof updateExecutionRecord==='function')updateExecutionRecord(currentSessionId,record);
                        if(!record.ui_committed && typeof renderExecutionRecord==='function')renderExecutionRecord(ctx,record,currentSessionId);
                    });
                    if(typeof mergeAdjacentExecutionGroups==='function')mergeAdjacentExecutionGroups(ctx.stream);
                } finally { replayingMessages = false; }
                ctx.runId=segment.run_id;
                if(ctx.reactGenerationsByRunId && ctx.reactGenerationsByRunId.has(ctx.runId))ctx.reactGeneration=ctx.reactGenerationsByRunId.get(ctx.runId);
                if(typeof selectExecutionProcessGroup==='function')selectExecutionProcessGroup(ctx,segment.process_group_id);
                ctx.processGroupId=segment.process_group_id;
                ctx.lastRuntimeSeq=segment.first_seq-1;
                if(ctx.currentProcessGroup) {
                    ctx.currentProcessGroup.classList.remove('is-collapsed');
                    ctx.currentProcessGroup.classList.add('is-running');
                    ctx.currentProcessGroup.dataset.processGroupId=segment.process_group_id;
                    delete ctx.currentProcessGroup.dataset.procEndedAt;
                    var body=ctx.currentProcessGroup.querySelector('.process-aggregate-body');
                    if(body)body.scrollTop=body.scrollHeight;
                }
                chatContainer.scrollTop=chatContainer.scrollHeight;
                liveAutoFollow=window.__replayFollowControl.mode !== 'off';streamChatNearBottom=liveAutoFollow;streamProcNearBottom=liveAutoFollow;
                setSessionRunState(currentSessionId,{ctx:ctx,runId:segment.run_id,controller:new AbortController()});
                if(typeof updateSessionTitle==='function')updateSessionTitle();
            },
            pauseReal: function(ctx) {
                if(ctx.llm && ctx.llm.llmDeltaFlushRaf) {
                    cancelAnimationFrame(ctx.llm.llmDeltaFlushRaf);
                    ctx.llm.llmDeltaFlushRaf=0;
                    ctx.llm.llmRevealLastTs=0;
                }
                if(typeof smoothFollowController!=='undefined') {
                    smoothFollowController.cancel(chatContainer);
                    var body=ctx.currentProcessGroup && ctx.currentProcessGroup.querySelector('.process-aggregate-body');
                    if(body)smoothFollowController.cancel(body);
                }
            },
            finishReal: function(ctx) {
                this.pauseReal(ctx);
                setSessionRunState(currentSessionId,null);
                if(ctx.currentProcessGroup)ctx.currentProcessGroup.classList.remove('is-running');
            },
            seed: function(ctx, rows) {
                replayingMessages = true;
                try {
                    rows.forEach(function(text, i) {
                        if (i % 80 === 0) renderEvent(ctx,{type:'user',content:'Replay history turn '+Math.floor(i/80)},i*2,currentSessionId);
                        renderEvent(ctx,{type:'llm_reasoning',content:text,react_iter:i+1,run_id:'history-'+Math.floor(i/80)},i*2+1,currentSessionId);
                    });
                } finally { replayingMessages = false; }
                // The final history process is also the current run's expanded
                // process, so hundreds of real archived feed rows remain present.
                if (ctx.currentProcessGroup) {
                    ctx.currentProcessGroup.classList.remove('is-collapsed');
                    ctx.currentProcessGroup.classList.add('is-running');
                    ctx.currentProcessGroup.dataset.processGroupId = 'replay-process';
                    ctx.currentProcessGroup.dataset.processRunId = 'replay-run';
                    ctx.runId = 'replay-run';
                    var body = ctx.currentProcessGroup.querySelector('.process-aggregate-body');
                    body.scrollTop = body.scrollHeight;
                }
                chatContainer.scrollTop = chatContainer.scrollHeight;
                liveAutoFollow = window.__replayFollowControl.mode !== 'off'; streamChatNearBottom = liveAutoFollow; streamProcNearBottom = liveAutoFollow;
            },
            consume: consumeAgentSseResponseInner,
            flush: flushLlmDeltaText,
            follow: function(ctx) {scrollContentAreaIfFollow(ctx,currentSessionId,'text');},
            followState: function(ctx) {
                var body=ctx && ctx.currentProcessGroup && ctx.currentProcessGroup.querySelector('.process-aggregate-body');
                return {mode:window.__replayFollowControl.mode,live_auto_follow:!!liveAutoFollow,
                    chat_following:!!smoothFollowController.isFollowing(chatContainer),process_following:!!(body && smoothFollowController.isFollowing(body)),
                    blocked_calls:window.__replayFollowControl.blocked_calls,immediate_writes:window.__replayFollowControl.immediate_writes};
            },
            verifyText: function(row, expected) {
                var sc=row && row.querySelector('.feed-chunk-scroller');
                var actual=sc ? (typeof getUiRuntimeText==='function' ? getUiRuntimeText(sc) : sc.textContent) : '';
                var records=typeof executionRecordsBySession!=='undefined' && executionRecordsBySession.get(currentSessionId);
                var record=records && records.get(expected.execution_id);
                var raw=String(expected.text || '');
                var display=raw;
                if(record) {
                    var labels={waiting_approval:'等待审批',waiting_input:'等待回答',interrupted:'已中断',unknown:'执行状态未知',timed_out:'已超时',failed:'执行失败'};
                    if(labels[record.status])display+='\\n['+labels[record.status]+']';
                }
                var projected=truncateLogTextForUi(display);
                var trimmed=truncateLogTextForUi(trimSurroundingBlankLines(display));
                var projectionMatches=!!sc && (actual===projected || (!record && actual===trimmed));
                var retained=record ? String(record.content || '') : sc && typeof sc._llmRawText==='string' ? sc._llmRawText : null;
                var sourceMatches=retained===null ? null : retained===raw;
                return {rendered_characters:actual.length,projected_characters:projectionMatches?actual.length:projected.length,
                    retained_characters:retained===null?null:retained.length,source_text_verified:sourceMatches,
                    ui_projection_verified:projectionMatches,found:!!sc,verified:projectionMatches && sourceMatches!==false,
                    check_mode:record?'execution_record_and_ui_projection':retained!==null?'retained_text_and_ui_projection':'ui_projection'};
            },
            capabilities: {executionRecords:typeof renderExecutionRecord==='function',smooth:typeof createSmoothFollowController==='function'},
            stop: function(ctx) {
                if(typeof smoothFollowController!=='undefined') {
                    smoothFollowController.cancel(chatContainer);
                    var body=ctx.currentProcessGroup && ctx.currentProcessGroup.querySelector('.process-aggregate-body');
                    if(body) smoothFollowController.cancel(body);
                }
                if(typeof discardLlmStreamChunks==='function') discardLlmStreamChunks(ctx);
                setSessionRunState(currentSessionId,null);
            }
        };
        if(window.__realTraceEnabled && typeof renderExecutionRecord==='function') {
            var realTraceOriginalRender=renderExecutionRecord;
            renderExecutionRecord=function(ctx,record,sid) {
                if(replayingMessages || !window.__realMeasureRender)return realTraceOriginalRender(ctx,record,sid);
                var started=performance.now();
                try{return realTraceOriginalRender(ctx,record,sid);}
                finally{if(window.__realRenderCalls.length<60000)window.__realRenderCalls.push({t:started,duration:performance.now()-started,
                    seq:record.last_runtime_seq,status:record.status,characters:String(record.content || '').length});else window.__realRenderCallsDropped++;}
            };
        }
        // Old renderers do not retain a durable journal cursor. Track it at
        // their normal accepted render calls for the replay's pause/resume UI.
        if(new URLSearchParams(location.search).get('real')==='1' && typeof renderExecutionRecord!=='function') {
            var realOriginalAppendDelta=appendLlmStreamDelta;
            appendLlmStreamDelta=function(ctx,event,sid) {
                var result=realOriginalAppendDelta(ctx,event,sid);
                if(ctx && event.runtime_seq)ctx.lastRuntimeSeq=Math.max(Number(ctx.lastRuntimeSeq || 0),Number(event.runtime_seq));
                return result;
            };
            ['appendToolCallDelta','appendToolCommandDelta','appendToolPendingRow','upsertToolCallResult'].forEach(function(name) {
                var original;try{original=eval(name);}catch(_e){return;}
                if(typeof original!=='function')return;
                var wrapper=function(ctx,event){
                    var value=original.apply(this,arguments);
                    if(ctx && event && event.runtime_seq)ctx.lastRuntimeSeq=Math.max(Number(ctx.lastRuntimeSeq || 0),Number(event.runtime_seq));
                    return value;
                };eval(name+' = wrapper');
            });
            var realOriginalRenderEvent=renderEvent;
            renderEvent=function(ctx,event,index,sid) {
                var result=realOriginalRenderEvent(ctx,event,index,sid);
                if(ctx && event.runtime_seq)ctx.lastRuntimeSeq=Math.max(Number(ctx.lastRuntimeSeq || 0),Number(event.runtime_seq));
                return result;
            };
        }
        if(window.__REPLAY_CONFIG__.observerTiming) {
            ['renderExecutionRecord','renderExecutionEvent','updateExecutionRecord','applyMessageEvent','scrollContentAreaIfFollow','refreshAggregateStatsSmart','registerProcessAggregateRow','syncRenderContextRunScope','renderDurableAttachmentImages','refreshFeedChunkOverflow','scheduleFeedChunkOverflowRefresh','applySkippedRuntimeV2EventMetadata'].forEach(function(name) {
                var original;
                try{original=eval(name);}catch(_e){return;}
                if(typeof original!=='function')return;
                var metric={name:name,calls:0,totalMs:0,maxMs:0};
                window.__replayCallMetrics.push(metric);
                var wrapper=function(){var start=performance.now();try{return original.apply(this,arguments);}finally{var dt=performance.now()-start;metric.calls++;metric.totalMs+=dt;metric.maxMs=Math.max(metric.maxMs,dt);}};
                eval(name+' = wrapper');
            });
        }
        `;
    }
    try {
        const result = Reflect.apply(nativeFunction, this, args);
        if(isApplication) window.__replayExperimentState.source_ready=true;
        return result;
    } catch(error) {if(isApplication)window.__replayExperimentState.error=String(error);throw error;}
};
window.Function.prototype = nativeFunction.prototype;
