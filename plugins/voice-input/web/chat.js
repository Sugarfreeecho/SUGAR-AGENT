import { SpeechCapture } from './capture.js';
import { voiceText as t, voiceRequest, splitSpeechText, buildSpeechPlan, parseSpeechMarkdown, setSpeechOptions } from './shared.js';

export function installChatExtension() {
    const composer = globalThis.MyAgentComposer;
    const input = document.getElementById('message-input');
    const send = document.getElementById('send-btn');
    if (!composer || !input || !send) return;
    const listeners = [];
    const on = (node, type, callback, options) => {
        node.addEventListener(type, callback, options);
        listeners.push(() => node.removeEventListener(type, callback, options));
    };
    const mic = document.createElement('button');
    mic.type = 'button'; mic.id = 'speech-input-btn'; mic.className = 'voice-mic';
    mic.setAttribute('aria-label', t('语音输入', 'Voice input'));
    mic.setAttribute('aria-haspopup', 'dialog'); mic.setAttribute('aria-expanded', 'false');
    mic.setAttribute('aria-pressed', 'false');
    mic.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/></svg>';
    send.before(mic);
    // A compact bar that sits on top of the composer instead of a dialog: the mic
    // starts recording on the first click and the bar only reports state.
    const dock = document.createElement('div');
    dock.className = 'voice-dock'; dock.hidden = true; dock.dataset.state = 'idle';
    dock.setAttribute('role', 'group'); dock.setAttribute('aria-label', t('语音输入', 'Voice input'));
    dock.innerHTML = '<span class="voice-dock-led" aria-hidden="true"></span><span class="voice-dock-time" aria-hidden="true">0:00</span>'
        + '<div class="voice-wave" aria-hidden="true">' + '<i></i>'.repeat(14) + '</div>'
        + '<p class="voice-dock-text" role="status" aria-live="polite"></p><div class="voice-dock-actions">'
        + '<button type="button" data-settings></button><button type="button" data-cancel></button>'
        + '<button type="button" data-finish></button><button type="button" data-insert></button></div>';
    dock.querySelector('[data-settings]').textContent = t('语音设置', 'Settings');
    dock.querySelector('[data-cancel]').textContent = t('取消', 'Cancel');
    dock.querySelector('[data-finish]').textContent = t('完成', 'Done');
    dock.querySelector('[data-insert]').textContent = t('插入', 'Insert');
    const dockText = dock.querySelector('.voice-dock-text');
    const dockTime = dock.querySelector('.voice-dock-time');
    const waveBars = [...dock.querySelectorAll('.voice-wave i')];
    const host = input.closest('.composer-row') || input.parentElement;
    host.classList.add('voice-host');
    host.append(dock);
    let operation = null, pending = null, disposed = false, snapshot = null, checking = false, playback = null;
    // Progressive reading of the answer while it is still being generated.
    let live = null;
    // Auto reading stays disarmed until a run has actually streamed in, so opening an
    // old session never starts talking on its own.
    let autoRead = false, sawStreaming = false, autoTimer = null;
    // "all" also follows runs that are not in the open session; "current" stays local.
    let autoReadScope = 'all', focusOnly = false;
    let autoPending = null;
    // Set once a run has been read progressively; its answer card must not be read again.
    let liveCovered = false;
    // Frames that already existed when this run started must never be auto read.
    let preRunWraps = null;
    const autoDone = new WeakSet();
    const readButtons = new Set();
    let dockState = 'idle', hideTimer = null;
    const levels = new Array(14).fill(0);
    const WAVE_SHAPE = [.38, .62, .9, .55, .78, 1, .68, .45, .82, .58, .95, .5, .72, .4];
    const status = message => { dockText.textContent = message; };
    const ACTIONS = { checking: [], recording: ['cancel', 'finish'], transcribing: ['cancel'],
        confirm: ['cancel', 'insert'], error: ['settings', 'cancel'], done: [] };
    const actionName = button => ['settings', 'cancel', 'finish', 'insert']
        .find(name => button.getAttribute('data-' + name) !== null);
    function pushLevel(value) {
        // Square root gives quiet speech visible movement; the floor keeps the
        // envelope readable in a silent room.
        const raw = Math.max(0, Math.min(.2, Number(value) || 0)) / 0.2;
        levels.push(Math.min(1, Math.max(.45, Math.sqrt(raw))));
        levels.shift();
        // A fixed envelope keeps the row readable as a waveform when the input is
        // quiet, instead of collapsing into a dashed line.
        waveBars.forEach((bar, index) => {
            const shape = WAVE_SHAPE[index % WAVE_SHAPE.length];
            bar.style.transform = 'scaleY(' + (.12 + levels[index] * shape * .88).toFixed(2) + ')';
        });
    }
    function setState(next, message) {
        dockState = next;
        clearTimeout(hideTimer);
        dock.hidden = false;
        dock.dataset.state = next;
        const recording = next === 'recording';
        if (recording && levels.every(level => level <= .06)) {
            levels.forEach((_, index) => { levels[index] = .35 + .65 * WAVE_SHAPE[index % WAVE_SHAPE.length]; });
            pushLevel(.04);
        }
        mic.classList.toggle('is-recording', recording);
        mic.setAttribute('aria-pressed', recording ? 'true' : 'false');
        mic.setAttribute('aria-expanded', recording ? 'true' : 'false');
        mic.setAttribute('aria-label', recording ? t('停止录音', 'Stop recording') : t('语音输入', 'Voice input'));
        if (message !== undefined) dockText.textContent = message;
        const allowed = ACTIONS[next] || [];
        for (const button of dock.querySelectorAll('.voice-dock-actions button')) {
            button.hidden = !allowed.includes(actionName(button));
        }
    }
    // Kept as the single re-render entry point used across the recording flow.
    function render() { if (!dock.hidden) setState(dockState); }
    function stopPlayback() {
        const active = playback; playback = null; live = null;
        if (!active) return;
        active.abort.abort();
        if (active.id) void voiceRequest('transcriptions/' + active.id, { method: 'DELETE', keepalive: true }).catch(() => {});
        if (active.audio) { active.audio.pause(); active.audio.src = ''; active.finish?.(); }
        if (active.url) URL.revokeObjectURL(active.url);
        for (const source of active.sources || []) { try { source.stop(); } catch { /* already ended */ } }
        if (active.sources) active.sources.length = 0;
        if (active.ctx) void active.ctx.close().catch(() => {});
        for (const control of active.controls || []) control.remove();
        if (active.button) {
            active.button.classList.remove('is-playing');
            active.button.textContent = t('朗读', 'Read aloud');
            active.button.setAttribute('aria-pressed', 'false');
        }
    }
    async function cancel() {
        const active = operation; operation = null; pending = null;
        if (active) {
            clearInterval(active.tick); clearTimeout(active.limit); active.abort.abort();
            void voiceRequest('transcriptions/' + active.id, { method: 'DELETE', keepalive: true }).catch(() => {});
            await active.capture.dispose().catch(() => {});
        }
    }
    async function hide(restoreFocus = false) {
        const wasOpen = !dock.hidden;
        clearTimeout(hideTimer);
        dock.hidden = true; dockState = 'idle';
        mic.classList.remove('is-recording');
        mic.setAttribute('aria-expanded', 'false'); mic.setAttribute('aria-pressed', 'false');
        mic.setAttribute('aria-label', t('语音输入', 'Voice input'));
        await cancel();
        // Session changes and outside clicks must leave the user's focus alone.
        if (wasOpen && restoreFocus && !disposed && input.isConnected) input.focus({ preventScroll: true });
    }
    function hideSoon(delay = 1500) {
        clearTimeout(hideTimer);
        hideTimer = setTimeout(() => { if (!operation && !pending) void hide(); }, delay);
    }
    // One click starts recording; clicking again stops it. Configuration problems
    // surface in the bar instead of costing an extra click to find out.
    async function open() {
        if (operation?.phase === 'recording') { await finish(); return; }
        if (checking || operation || pending) return;
        if (input.disabled || input.readOnly) return;
        checking = true; setState('checking', t('正在检查语音设置…', 'Checking voice settings…'));
        try {
            snapshot = await (await voiceRequest('status')).json();
            if (disposed) return;
            if (!snapshot.enabled) {
                setState('error', t('语音输入未启用。', 'Voice input is off.'));
                return;
            }
            if (snapshot.phase !== 'ready') {
                setState('error', t('尚未配置识别接口或本地模型。', 'No speech API or local model configured yet.'));
                return;
            }
        } catch (error) {
            setState('error', error.message);
            return;
        } finally { checking = false; }
        await record();
    }
    const alive = active => operation === active && !active.abort.signal.aborted && active.span.sessionId === composer.sessionId();
    async function failed(active, error) {
        if (!alive(active)) return;
        await cancel();
        if (!disposed && !operation) {
            setState('error', error.name === 'NotAllowedError'
                ? t('请允许麦克风访问。', 'Allow microphone access.')
                : error.message || t('录音失败。', 'Recording failed.'));
        }
    }
    async function record() {
        if (operation?.phase === 'recording') { await finish(); return; }
        if (operation || pending || checking || input.disabled || input.readOnly) return;
        if (!snapshot?.enabled || snapshot.phase !== 'ready') {
            setState('error', t('尚未配置识别接口或本地模型。', 'No speech API or local model configured yet.'));
            return;
        }
        stopPlayback();
        const active = { id: crypto.randomUUID(), capture: new SpeechCapture(), abort: new AbortController(), span: composer.capture(), phase: 'permission' };
        operation = active;
        setState('checking', t('正在请求麦克风权限…', 'Requesting microphone access…'));
        try {
            await active.capture.start(error => { void failed(active, error); });
            if (!alive(active)) { await active.capture.dispose(); return; }
            active.phase = 'recording'; active.started = Date.now();
            // The mic itself stops the take; say so instead of repeating "recording".
            setState('recording', t('再点一下麦克风结束', 'Tap the mic again to stop'));
            active.tick = setInterval(() => {
                const seconds = Math.max(0, Math.floor((Date.now() - active.started) / 1000));
                dockTime.textContent = Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0');
                pushLevel(active.capture.level());
            }, 100);
            active.limit = setTimeout(() => { void finish(); }, snapshot.maxDurationSeconds * 1000);
        } catch (error) { await failed(active, error); }
    }
    async function finish() {
        const active = operation;
        if (!active || active.phase !== 'recording') return;
        active.phase = 'transcribing'; clearInterval(active.tick); clearTimeout(active.limit);
        setState('transcribing', t('正在识别…', 'Transcribing…'));
        try {
            const audio = await active.capture.stop(snapshot.maxDurationSeconds);
            if (!alive(active)) return;
            const result = await (await voiceRequest('transcribe', { method: 'POST', headers: { 'Content-Type': 'audio/wav', 'X-Speech-Request-Id': active.id }, body: audio, signal: active.abort.signal })).json();
            if (!alive(active)) return;
            operation = null;
            if (!result.text?.trim()) {
                setState('done', t('没听清，再说一次？', "Didn't catch that; try again?"));
                hideSoon(1800);
            } else if (composer.insert(result.text, active.span)) {
                setState('done', t('已插入草稿', 'Inserted'));
                hideSoon(1200);
            } else {
                // The draft moved while recording; never overwrite it silently.
                pending = { text: result.text, sessionId: active.span.sessionId };
                setState('confirm', result.text);
            }
        } catch (error) { await failed(active, error); }
    }
    async function read(wrap, button) {
        if (playback?.button === button) { stopPlayback(); return; }
        stopPlayback();
        const content = wrap.querySelector('.message.assistant');
        if (!content) return;
        const items = buildSpeechPlan(content, t);
        if (!items.length) return;
        const active = { button, wrap, items, abort: new AbortController() }; playback = active;
        button.classList.add('is-playing'); button.textContent = t('停止朗读', 'Stop reading'); button.setAttribute('aria-pressed', 'true');
        mountControls(active);
        try {
            try { await stream(active); }
            catch (error) {
                if (error.code !== 'streaming-unsupported' || playback !== active) throw error;
                // The provider has no incremental audio: fall back to one buffered request per segment.
                if (active.ctx) { void active.ctx.close().catch(() => {}); active.ctx = null; active.sources = null; }
                await buffered(active);
            }
        } catch (error) {
            if (playback === active && error.name !== 'AbortError') {
                setState('error', error.message);
            }
        } finally { if (playback === active) stopPlayback(); }
    }
    function mountControls(active) {
        const bar = active.button.parentElement;
        if (!bar) return;
        const pause = document.createElement('button');
        pause.type = 'button'; pause.className = 'msg-tb voice-pause';
        pause.textContent = t('暂停', 'Pause');
        pause.setAttribute('aria-pressed', 'false');
        pause.onclick = event => {
            event.stopPropagation();
            active.paused = !active.paused;
            if (active.ctx) {
                // Suspending the clock holds every scheduled buffer at its position.
                if (active.paused) void active.ctx.suspend().catch(() => {}); else void active.ctx.resume().catch(() => {});
            } else if (active.audio) {
                if (active.paused) active.audio.pause(); else void active.audio.play().catch(() => {});
            }
            pause.textContent = active.paused ? t('继续', 'Resume') : t('暂停', 'Pause');
            pause.setAttribute('aria-pressed', active.paused ? 'true' : 'false');
        };
        const restart = document.createElement('button');
        restart.type = 'button'; restart.className = 'msg-tb voice-restart';
        restart.textContent = t('从头', 'Restart');
        restart.onclick = event => {
            event.stopPropagation();
            const wrap = active.wrap;
            stopPlayback();
            void read(wrap, active.button);
        };
        active.controls = [pause, restart];
        for (const control of active.controls) active.button.after(control);
    }
    const AudioContextClass = globalThis.AudioContext || globalThis.webkitAudioContext;
    function startSpeech(part, active) {
        active.id = crypto.randomUUID();
        return voiceRequest('synthesize/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ requestId: active.id, text: part }), signal: active.abort.signal });
    }
    // Scheduling ahead of the clock turns per-chunk arrivals into gapless speech,
    // so playback starts on the first fragment instead of after a whole answer.
    function schedule(active, samples, rate) {
        const ctx = active.ctx;
        const buffer = ctx.createBuffer(1, samples.length, rate);
        buffer.getChannelData(0).set(samples);
        const source = ctx.createBufferSource();
        source.buffer = buffer; source.connect(ctx.destination);
        const start = Math.max(ctx.currentTime + .04, active.next);
        source.start(start);
        active.next = start + buffer.duration;
        active.sources.push(source);
        source.onended = () => { const at = active.sources.indexOf(source); if (at >= 0) active.sources.splice(at, 1); };
    }
    async function consume(response, active) {
        const rate = Number(response.headers.get('X-Sample-Rate')) || 24000;
        const reader = response.body.getReader();
        let carry = null;
        try {
            for (;;) {
                const { done, value } = await reader.read();
                if (playback !== active) return;
                if (done) break;
                let bytes = value;
                if (carry) {
                    bytes = new Uint8Array(carry.length + value.length);
                    bytes.set(carry); bytes.set(value, carry.length);
                }
                // A chunk may split a 16-bit sample; keep the stray byte for the next read.
                const usable = bytes.length - (bytes.length % 2);
                carry = usable === bytes.length ? null : bytes.slice(usable);
                if (!usable) continue;
                // Int16Array needs an even offset, which a transport chunk need not provide.
                const aligned = bytes.byteOffset % 2 ? bytes.slice(0, usable) : bytes.subarray(0, usable);
                const pcm = new Int16Array(aligned.buffer, aligned.byteOffset, usable / 2);
                const samples = new Float32Array(pcm.length);
                for (let index = 0; index < pcm.length; index += 1) samples[index] = pcm[index] / 32768;
                schedule(active, samples, rate);
            }
        } finally { reader.cancel().catch(() => {}); }
    }
    async function stream(active) {
        const Ctx = AudioContextClass;
        if (!Ctx) throw new Error(t('当前浏览器不支持流式播放。', 'This browser cannot stream audio.'));
        const ctx = new Ctx(); active.ctx = ctx; active.sources = []; active.next = ctx.currentTime + .1;
        if (ctx.state === 'suspended') await ctx.resume();
        const items = active.items;
        let ahead = items.length ? startSpeech(items[0].text, active) : null;
        for (let index = 0; index < items.length; index += 1) {
            const request = ahead;
            // The next segment is already in flight while this one is still arriving.
            ahead = index + 1 < items.length ? startSpeech(items[index + 1].text, active) : null;
            if (ahead) ahead.catch(() => {});
            // Keep roughly one segment of scheduled audio in hand instead of buffering the answer.
            while (playback === active && active.next - ctx.currentTime > 24) {
                await new Promise(resolve => setTimeout(resolve, 200));
            }
            if (playback !== active) return;
            // A table or code block starts after a real pause, not mid-sentence.
            active.next += items[index].gap || 0;
            await consume(await request, active);
            if (playback !== active) return;
        }
        while (playback === active && ctx.currentTime < active.next - .02) {
            await new Promise(resolve => setTimeout(resolve, 120));
        }
    }
    async function buffered(active) {
        for (const item of active.items) {
            if (playback !== active || disposed) break;
            if (item.gap) await new Promise(resolve => setTimeout(resolve, item.gap * 1000));
            while (playback === active && active.paused) await new Promise(resolve => setTimeout(resolve, 120));
            if (playback !== active) break;
            active.id = crypto.randomUUID();
            const response = await voiceRequest('synthesize', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ requestId: active.id, text: item.text }), signal: active.abort.signal });
            const blob = await response.blob();
            if (playback !== active) break;
            active.url = URL.createObjectURL(blob); active.audio = new Audio(active.url);
            await new Promise((resolve, reject) => {
                active.finish = resolve; active.audio.onended = resolve;
                active.audio.onerror = () => reject(new Error(t('无法播放语音。', 'Unable to play audio.')));
                active.audio.play().catch(reject);
            });
            if (active.url) { URL.revokeObjectURL(active.url); active.url = null; }
        }
    }
    // The answer streams into a plain-text row long before the card is rendered,
    // so auto reading follows that row and speaks each block once it settles.
    function liveScroller() {
        // Reading the whole document used to pick up other sessions' runs, which is
        // now a choice rather than an accident.
        const scope = autoReadScope === 'all' ? document : (document.getElementById('chat-container') || document);
        const rows = [...scope.querySelectorAll('.feed-item[data-log-type="llm-response"]')];
        const row = rows.reverse().find(node => node.querySelector('.feed-chunk.is-streaming'));
        return row ? (row.querySelector('.feed-chunk-scroller') || row.querySelector('.feed-chunk')) : null;
    }
    function startLive() {
        if (!autoRead || playback || disposed) return null;
        if (focusOnly && !document.hasFocus()) return null;
        const scroller = liveScroller();
        if (!scroller) return null;
        const active = { live: true, queue: [], fed: [], text: '', scroller,
            chunk: scroller.closest('.feed-chunk'), abort: new AbortController() };
        playback = active; live = active;
        liveCovered = true;
        void streamLive(active).catch(error => {
            if (error.name !== 'AbortError' && playback === active) stopPlayback();
        });
        return active;
    }
    function pumpLive() {
        const active = live;
        if (!active || playback !== active) return;
        if (active.scroller.isConnected) active.text = active.scroller.textContent || '';
        // Only this run's own state counts; another session streaming must not keep
        // this one open, and must not close it either.
        const ended = !active.chunk || !active.chunk.isConnected || !active.chunk.classList.contains('is-streaming');
        if (!active.text.trim() && !ended) return;
        // Settled prefix only: the trailing block may still be receiving tokens.
        const units = parseSpeechMarkdown(active.text, ended, t);
        for (let index = 0; index < units.length; index += 1) {
            const text = units[index].text;
            if (active.fed[index] !== undefined) {
                // The text under an already queued block changed; stop rather than
                // speak something the user never saw.
                if (active.fed[index] !== text) { stopPlayback(); return; }
                continue;
            }
            active.fed[index] = text;
            active.queue.push(units[index]);
        }
        if (!active.button) {
            const wraps = [...document.querySelectorAll('.msg-wrap--answer-frame')];
            const wrap = wraps[wraps.length - 1];
            const button = wrap && wrap.querySelector('.voice-read');
            if (button && button.parentElement) {
                active.button = button; active.wrap = wrap;
                autoDone.add(wrap);
                button.classList.add('is-playing'); button.textContent = t('停止朗读', 'Stop reading');
                button.setAttribute('aria-pressed', 'true');
                mountControls(active);
            }
        }
        active.ended = ended;
    }
    async function streamLive(active) {
        const Ctx = AudioContextClass;
        if (!Ctx) throw new Error(t('当前浏览器不支持流式播放。', 'This browser cannot stream audio.'));
        const ctx = new Ctx(); active.ctx = ctx; active.sources = []; active.next = ctx.currentTime + .1;
        if (ctx.state === 'suspended') await ctx.resume();
        let at = 0, aheadIndex = -1, ahead = null;
        const prepare = index => {
            if (index >= active.queue.length) return null;
            if (aheadIndex === index) return ahead;
            aheadIndex = index; ahead = startSpeech(active.queue[index].text, active);
            ahead.catch(() => {});
            return ahead;
        };
        for (;;) {
            while (at >= active.queue.length) {
                if (playback !== active || active.ended) break;
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            if (playback !== active) return;
            if (at >= active.queue.length) break;
            const request = prepare(at);
            const item = active.queue[at];
            at += 1;
            // A block that already arrived is requested now, so the pause between
            // blocks is the gap we chose rather than the synthesis latency.
            prepare(at);
            while (playback === active && active.next - ctx.currentTime > 24) {
                await new Promise(resolve => setTimeout(resolve, 200));
            }
            if (playback !== active) return;
            active.next += item.gap || 0;
            await consume(await request, active);
        }
        while (playback === active && ctx.currentTime < active.next - .02) {
            await new Promise(resolve => setTimeout(resolve, 120));
        }
        if (playback === active) stopPlayback();
    }
    function scan() {
        document.querySelectorAll('.msg-wrap--answer-frame .msg-toolbar').forEach(toolbar => {
            if (toolbar.querySelector('.voice-read')) return;
            const button = document.createElement('button'); button.type = 'button'; button.className = 'msg-tb voice-read';
            button.textContent = t('朗读', 'Read aloud'); button.setAttribute('aria-pressed', 'false');
            toolbar.append(button); readButtons.add(button);
            button.onclick = event => { event.stopPropagation(); void read(toolbar.closest('.msg-wrap--answer-frame'), button); };
        });
        queueAutoRead();
    }
    async function loadVoiceFlag() {
        try {
            const state = await (await voiceRequest('status')).json();
            autoRead = !!(state?.tts?.enabled && state?.tts?.autoRead);
            autoReadScope = state?.tts?.autoReadScope === 'current' ? 'current' : 'all';
            focusOnly = !!state?.tts?.autoReadOnlyFocused;
            setSpeechOptions({ readParenthetical: !!state?.tts?.readParenthetical });
            applyScope();
        } catch { autoRead = false; }
    }
    void loadVoiceFlag();
    function scopedRoot() {
        return autoReadScope === 'all' ? document : (document.getElementById('chat-container') || document);
    }
    function streamingNow() { return !!scopedRoot().querySelector('.feed-chunk.is-streaming'); }
    function queueAutoRead() {
        if (!autoRead || !sawStreaming || disposed) return;
        if (streamingNow()) return;
        if (focusOnly && !document.hasFocus()) return;
        const wraps = [...scopedRoot().querySelectorAll('.msg-wrap--answer-frame')];
        const fresh = wraps.filter(node => !preRunWraps || !preRunWraps.has(node));
        // This run was already spoken while it streamed; do not repeat its card.
        if (liveCovered) { for (const node of fresh) autoDone.add(node); return; }
        const wrap = fresh[fresh.length - 1];
        if (!wrap || autoDone.has(wrap)) return;
        const button = wrap.querySelector('.voice-read');
        const content = wrap.querySelector('.message.assistant');
        if (!button || !content) return;
        const text = content.textContent.trim();
        // Re-arming on every mutation would let page activity starve the timer.
        if (autoPending && autoPending.wrap === wrap && autoPending.text === text) return;
        clearTimeout(autoTimer);
        autoPending = { wrap, text };
        // The answer card is rendered once, complete, when the run commits, so this
        // only guards against a card that is still being assembled - not a delay.
        autoTimer = setTimeout(() => {
            autoPending = null;
            if (!autoRead || playback || disposed || !wrap.isConnected || autoDone.has(wrap)) return;
            if (focusOnly && !document.hasFocus()) return;
            if (streamingNow()) return;
            if ((wrap.querySelector('.message.assistant')?.textContent || '').trim() !== text || !text) return;
            autoDone.add(wrap);
            void read(wrap, button);
        }, 150);
    }
    const observer = new MutationObserver(() => {
        if (streamingNow()) {
            if (!sawStreaming) preRunWraps = new Set(scopedRoot().querySelectorAll('.msg-wrap--answer-frame'));
            sawStreaming = true;
        }
        scan();
        if (autoRead && sawStreaming && !disposed) {
            if (!playback) startLive();
            pumpLive();
        }
        if (playback && playback.button && !playback.button.isConnected) stopPlayback();
    });
    observer.observe(document.getElementById('chat-container') || document.body, { childList: true, subtree: true });
    // Scope "all" also follows runs rendered outside the message container (other
    // sessions, docks), so the observer has to cover the document; else it stays off.
    const wideObserver = new MutationObserver(() => {
        if (!autoRead || disposed || autoReadScope !== 'all') return;
        if (!playback && startLive()) sawStreaming = true;
        pumpLive();
    });
    function applyScope() {
        wideObserver.disconnect();
        if (autoReadScope === 'all' && autoRead) wideObserver.observe(document.body, { childList: true, subtree: true });
    }
    applyScope();
    const inputObserver = new MutationObserver(() => { if ((input.disabled || input.readOnly) && operation) void cancel(); render(); });
    inputObserver.observe(input, { attributes: true, attributeFilter: ['disabled', 'readonly'] });
    // A long press (or right click) is the shortcut to settings, as in chat apps
    // where the mic button has no room for a second control.
    let longPressed = false, pressTimer = null;
    const openSettings = () => { void hide(); globalThis.myagentOpenSettings?.('plugin:voice-input:voice'); };
    on(mic, 'pointerdown', () => {
        longPressed = false;
        pressTimer = setTimeout(() => { longPressed = true; openSettings(); }, 550);
    });
    for (const type of ['pointerup', 'pointerleave', 'pointercancel']) on(mic, type, () => clearTimeout(pressTimer));
    on(mic, 'contextmenu', event => { event.preventDefault(); clearTimeout(pressTimer); openSettings(); });
    on(mic, 'click', () => {
        if (longPressed) { longPressed = false; return; }
        void open();
    });
    on(dock.querySelector('[data-cancel]'), 'click', () => { void hide(true); });
    on(dock.querySelector('[data-finish]'), 'click', () => { void finish(); });
    on(dock.querySelector('[data-insert]'), 'click', () => {
        if (pending && pending.sessionId === composer.sessionId() && composer.insert(pending.text, composer.capture())) {
            pending = null;
            setState('done', t('已插入草稿', 'Inserted'));
            hideSoon(1200);
        }
    });
    on(dock.querySelector('[data-settings]'), 'click', openSettings);
    on(document, 'myagent:session-change', () => {
        sawStreaming = false; liveCovered = false; preRunWraps = null; clearTimeout(autoTimer); void hide(); stopPlayback();
    });
    on(document, 'myagent:settings-closed', () => { snapshot = null; void loadVoiceFlag(); });
    on(document, 'myagent:plugins-changed', () => { void loadVoiceFlag(); });
    on(document, 'keydown', event => { if (event.key === 'Escape' && !dock.hidden) { event.preventDefault(); void hide(true); } });
    on(document, 'pointerdown', event => { if (!dock.hidden && !dock.contains(event.target) && !mic.contains(event.target)) void hide(); });
    on(document, 'visibilitychange', () => { if (document.hidden && operation) void hide(); });
    on(window, 'blur', () => { if (operation?.phase === 'recording') void hide(); });
    // With "focused only" on, losing focus pauses the voice instead of talking to an
    // empty desk; refocusing resumes the same position, not a restart.
    on(window, 'blur', () => {
        const active = playback;
        if (!focusOnly || !active?.ctx || active.focusPaused) return;
        active.focusPaused = true;
        if (!active.paused) void active.ctx.suspend().catch(() => {});
    });
    on(window, 'focus', () => {
        const active = playback;
        if (!active?.focusPaused) return;
        active.focusPaused = false;
        if (!active.paused) void active.ctx.resume().catch(() => {});
    });
    on(window, 'pagehide', () => { void cancel(); stopPlayback(); });
    scan();
    return () => {
        disposed = true; void cancel(); stopPlayback(); observer.disconnect(); inputObserver.disconnect(); wideObserver.disconnect();
        listeners.forEach(remove => remove()); readButtons.forEach(button => button.remove());
        mic.remove(); dock.remove(); host.classList.remove('voice-host');
    };
}
