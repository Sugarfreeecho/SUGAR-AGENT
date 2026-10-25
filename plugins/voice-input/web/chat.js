import { SpeechCapture } from './capture.js';
import { voiceText as t, voiceRequest, splitSpeechText, buildSpeechPlan } from './shared.js';

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
    mic.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/></svg>';
    send.before(mic);
    const menu = document.createElement('div');
    menu.className = 'voice-popover'; menu.hidden = true;
    menu.setAttribute('role', 'dialog'); menu.setAttribute('aria-label', t('语音输入', 'Voice input'));
    menu.innerHTML = '<header><strong></strong><button type="button" data-close>×</button></header><p role="status" aria-live="polite"></p>'
        + '<meter min="0" max="0.2" hidden></meter><div data-transcript hidden tabindex="0"></div><footer>'
        + '<button type="button" data-record></button><button type="button" data-insert hidden></button><button type="button" data-cancel></button><button type="button" data-settings></button></footer>';
    document.body.append(menu);
    menu.querySelector('strong').textContent = t('语音输入', 'Voice input');
    menu.querySelector('[data-close]').setAttribute('aria-label', t('关闭', 'Close'));
    menu.querySelector('[data-cancel]').textContent = t('取消', 'Cancel');
    menu.querySelector('[data-insert]').textContent = t('插入文字', 'Insert text');
    menu.querySelector('[data-settings]').textContent = t('语音设置', 'Voice settings');
    menu.querySelector('meter').setAttribute('aria-label', t('麦克风音量', 'Microphone level'));
    let operation = null, pending = null, disposed = false, snapshot = null, checking = false, playback = null;
    // Auto reading stays disarmed until a run has actually streamed in, so opening an
    // old session never starts talking on its own.
    let autoRead = false, sawStreaming = false, autoTimer = null;
    const autoDone = new WeakSet();
    const readButtons = new Set();
    const status = message => { menu.querySelector('[role="status"]').textContent = message; };
    function position() {
        if (menu.hidden) return;
        const anchor = mic.getBoundingClientRect();
        const box = menu.getBoundingClientRect();
        menu.style.left = Math.max(8, Math.min(innerWidth - box.width - 8, anchor.right - box.width)) + 'px';
        menu.style.top = Math.max(8, Math.min(innerHeight - box.height - 8, anchor.top - box.height - 8)) + 'px';
    }
    function render() {
        const record = menu.querySelector('[data-record]');
        record.textContent = operation?.phase === 'recording' ? t('停止并识别', 'Stop and transcribe') : t('开始录音', 'Start recording');
        record.disabled = checking || !!pending || input.disabled || input.readOnly || !!operation && operation.phase !== 'recording';
        menu.querySelector('meter').hidden = operation?.phase !== 'recording';
        menu.querySelector('[data-insert]').hidden = !pending;
        menu.querySelector('[data-transcript]').hidden = !pending;
        menu.querySelector('[data-transcript]').textContent = pending?.text || '';
        position();
    }
    function stopPlayback() {
        const active = playback; playback = null;
        if (!active) return;
        active.abort.abort();
        if (active.id) void voiceRequest('transcriptions/' + active.id, { method: 'DELETE', keepalive: true }).catch(() => {});
        if (active.audio) { active.audio.pause(); active.audio.src = ''; active.finish?.(); }
        if (active.url) URL.revokeObjectURL(active.url);
        for (const source of active.sources || []) { try { source.stop(); } catch { /* already ended */ } }
        if (active.sources) active.sources.length = 0;
        if (active.ctx) void active.ctx.close().catch(() => {});
        for (const control of active.controls || []) control.remove();
        active.button.classList.remove('is-playing');
        active.button.textContent = t('朗读', 'Read aloud');
        active.button.setAttribute('aria-pressed', 'false');
    }
    async function cancel() {
        const active = operation; operation = null; pending = null;
        if (active) {
            clearInterval(active.tick); clearTimeout(active.limit); active.abort.abort();
            void voiceRequest('transcriptions/' + active.id, { method: 'DELETE', keepalive: true }).catch(() => {});
            await active.capture.dispose().catch(() => {});
        }
        render();
    }
    async function hide(restoreFocus = false) {
        const wasOpen = !menu.hidden;
        menu.hidden = true; mic.setAttribute('aria-expanded', 'false');
        await cancel();
        // Session changes and outside clicks must leave the user's focus alone.
        if (wasOpen && restoreFocus && !disposed && mic.isConnected && menu.hidden) mic.focus({ preventScroll: true });
    }
    async function open() {
        if (!menu.hidden) { await hide(true); return; }
        menu.hidden = false; mic.setAttribute('aria-expanded', 'true');
        status(t('正在检查语音设置…', 'Checking voice settings…')); checking = true; render();
        try {
            snapshot = await (await voiceRequest('status')).json();
            if (disposed || menu.hidden) return;
            status(!snapshot.enabled ? t('请先在语音设置中启用语音输入。', 'Enable voice input in Voice settings.')
                : snapshot.phase !== 'ready' ? t('请在语音设置中配置 API，或准备本地模型。', 'Configure an API or prepare a local model in Voice settings.')
                : t('点击开始录音；识别文字会插入草稿。', 'Start recording; the transcript will be inserted into your draft.'));
        } catch (error) { status(error.message); }
        finally { checking = false; render(); if (!menu.hidden) menu.querySelector('[data-record]').focus(); }
    }
    const alive = active => operation === active && !active.abort.signal.aborted && active.span.sessionId === composer.sessionId();
    async function failed(active, error) {
        if (!alive(active)) return;
        await cancel();
        if (!disposed && !operation) status(error.name === 'NotAllowedError' ? t('请允许麦克风访问。', 'Allow microphone access.') : error.message);
    }
    async function record() {
        if (operation?.phase === 'recording') { await finish(); return; }
        if (operation || pending || checking || input.disabled || input.readOnly) return;
        if (!snapshot?.enabled || snapshot.phase !== 'ready') { status(t('请先完成语音设置中的配置。', 'Complete voice configuration in Voice settings first.')); return; }
        stopPlayback();
        const active = { id: crypto.randomUUID(), capture: new SpeechCapture(), abort: new AbortController(), span: composer.capture(), phase: 'permission' };
        operation = active; status(t('正在请求麦克风权限…', 'Requesting microphone access…')); render();
        try {
            await active.capture.start(error => { void failed(active, error); });
            if (!alive(active)) { await active.capture.dispose(); return; }
            active.phase = 'recording'; active.started = Date.now(); render();
            active.tick = setInterval(() => {
                menu.querySelector('meter').value = active.capture.level();
                status(t('正在录音', 'Recording') + ' · ' + Math.floor((Date.now() - active.started) / 1000) + 's');
            }, 100);
            active.limit = setTimeout(() => { void finish(); }, snapshot.maxDurationSeconds * 1000);
        } catch (error) { await failed(active, error); }
    }
    async function finish() {
        const active = operation;
        if (!active || active.phase !== 'recording') return;
        active.phase = 'transcribing'; clearInterval(active.tick); clearTimeout(active.limit);
        status(t('正在识别…', 'Transcribing…')); render();
        try {
            const audio = await active.capture.stop(snapshot.maxDurationSeconds);
            if (!alive(active)) return;
            const result = await (await voiceRequest('transcribe', { method: 'POST', headers: { 'Content-Type': 'audio/wav', 'X-Speech-Request-Id': active.id }, body: audio, signal: active.abort.signal })).json();
            if (!alive(active)) return;
            operation = null;
            if (!result.text?.trim()) status(t('未识别到语音。', 'No speech detected.'));
            else if (composer.insert(result.text, active.span)) status(t('识别文字已插入草稿。', 'Transcript inserted into draft.'));
            else { pending = { text: result.text, sessionId: active.span.sessionId }; status(t('草稿已变化，请确认后插入或取消。', 'Draft changed; review before inserting or cancelling.')); }
            render();
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
                menu.hidden = false; mic.setAttribute('aria-expanded', 'true'); status(error.message); render();
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
        } catch { autoRead = false; }
    }
    void loadVoiceFlag();
    function queueAutoRead() {
        if (!autoRead || !sawStreaming || disposed) return;
        if (document.querySelector('.is-streaming')) return;
        const wraps = [...document.querySelectorAll('.msg-wrap--answer-frame')];
        const wrap = wraps[wraps.length - 1];
        if (!wrap || autoDone.has(wrap)) return;
        const button = wrap.querySelector('.voice-read');
        const content = wrap.querySelector('.message.assistant');
        if (!button || !content) return;
        clearTimeout(autoTimer);
        const text = content.textContent.trim();
        // Wait for the answer to stop changing before speaking, or the tail is cut off.
        autoTimer = setTimeout(() => {
            if (!autoRead || playback || disposed || !wrap.isConnected || autoDone.has(wrap)) return;
            if (document.querySelector('.is-streaming')) return;
            if ((wrap.querySelector('.message.assistant')?.textContent || '').trim() !== text || !text) return;
            autoDone.add(wrap);
            void read(wrap, button);
        }, 1200);
    }
    const observer = new MutationObserver(() => {
        if (document.querySelector('.is-streaming')) sawStreaming = true;
        scan();
        if (playback && !playback.button.isConnected) stopPlayback();
    });
    observer.observe(document.getElementById('chat-container') || document.body, { childList: true, subtree: true });
    const inputObserver = new MutationObserver(() => { if ((input.disabled || input.readOnly) && operation) void cancel(); render(); });
    inputObserver.observe(input, { attributes: true, attributeFilter: ['disabled', 'readonly'] });
    on(mic, 'click', () => { void open(); });
    on(menu.querySelector('[data-close]'), 'click', () => { void hide(true); });
    on(menu.querySelector('[data-record]'), 'click', () => { void record(); });
    on(menu.querySelector('[data-cancel]'), 'click', () => { void cancel(); status(t('已取消。', 'Cancelled.')); });
    on(menu.querySelector('[data-insert]'), 'click', () => {
        if (pending && pending.sessionId === composer.sessionId() && composer.insert(pending.text, composer.capture())) {
            pending = null; status(t('识别文字已插入草稿。', 'Transcript inserted into draft.')); render();
        }
    });
    on(menu.querySelector('[data-settings]'), 'click', () => { void hide(); globalThis.myagentOpenSettings?.('plugin:voice-input:voice'); });
    on(document, 'myagent:session-change', () => { sawStreaming = false; clearTimeout(autoTimer); void hide(); stopPlayback(); });
    on(document, 'myagent:settings-closed', () => { snapshot = null; void loadVoiceFlag(); });
    on(document, 'myagent:plugins-changed', () => { void loadVoiceFlag(); });
    on(document, 'keydown', event => { if (event.key === 'Escape' && !menu.hidden) { event.preventDefault(); void hide(true); } });
    on(document, 'pointerdown', event => { if (!menu.hidden && !menu.contains(event.target) && !mic.contains(event.target)) void hide(); });
    on(document, 'visibilitychange', () => { if (document.hidden && operation) void hide(); });
    on(window, 'blur', () => { if (operation?.phase === 'recording') void hide(); });
    on(window, 'resize', position); on(document, 'scroll', position, true);
    on(window, 'pagehide', () => { void cancel(); stopPlayback(); });
    scan();
    return () => {
        disposed = true; void cancel(); stopPlayback(); observer.disconnect(); inputObserver.disconnect();
        listeners.forEach(remove => remove()); readButtons.forEach(button => button.remove()); mic.remove(); menu.remove();
    };
}
