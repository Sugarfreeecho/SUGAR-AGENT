const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { installSpeechPermissions } = require('../../packaging/electron/speech-permissions');
const root = path.resolve(__dirname, '../..');
const context = vm.createContext({ Uint8Array, Float32Array, DataView, Event, Blob, navigator: {}, console });
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/src/app/modules/input-actions.js'), 'utf8')
    + '\n' + fs.readFileSync(path.join(root, 'plugins/voice-input/web/capture.js'), 'utf8').replace(/^export /gm, '')
    + '\nglobalThis.Capture = SpeechCapture;', context);

const input = { value: 'hello world', selectionStart: 6, selectionEnd: 11, disabled: false, readOnly: false,
    setRangeText(text, start, end) { this.value = this.value.slice(0, start) + text + this.value.slice(end); },
    dispatchEvent(event) { assert.equal(event.type, 'input'); this.events = (this.events || 0) + 1; } };
const span = context.captureComposerInsertion(input, 'a', 1);
assert.equal(context.insertComposerTranscript(input, span, 'b', 1, '测试'), false);
assert.equal(context.insertComposerTranscript(input, span, 'a', 2, '测试'), false);
input.value = 'changed';
assert.equal(context.insertComposerTranscript(input, span, 'a', 1, '测试'), false);
input.value = span.value; input.readOnly = true;
assert.equal(context.insertComposerTranscript(input, span, 'a', 1, '测试'), false);
input.readOnly = false;
assert.equal(context.insertComposerTranscript(input, span, 'a', 1, '测试'), true);
assert.equal(input.value, 'hello 测试');
assert.equal(input.events, 1);
assert.equal(context.insertComposerTranscript(input, span, 'a', 1, 'again'), false);
const bytes = context.encodeSpeechWave(new Float32Array([-2, -1, 0, 1, 2]));
const view = new DataView(bytes.buffer);
assert.equal(Buffer.from(bytes).subarray(0, 4).toString(), 'RIFF');
assert.equal(view.getUint32(24, true), 16000);
assert.equal(view.getUint16(22, true), 1);
assert.deepEqual(Array.from({ length: 5 }, (_, i) => view.getInt16(44 + i * 2, true)), [-32768, -32768, 0, 32767, 32767]);

async function captureChecks() {
    let grant, stopped = 0;
    context.MediaRecorder = class {};
    context.navigator.mediaDevices = { getUserMedia: () => new Promise(resolve => { grant = resolve; }) };
    const capture = new context.Capture();
    const starting = capture.start();
    const disposal = capture.dispose();
    grant({ getTracks: () => [{ stop: () => stopped++ }] });
    await assert.rejects(starting, /cancelled/);
    await disposal;
    assert.equal(stopped, 1, 'late microphone grants release their tracks');
    assert.equal(capture.dispose(), disposal, 'disposal is shared');

    let recorder, closed = 0, rendered = 0;
    const track = { stop() { stopped++; } };
    context.navigator.mediaDevices = { getUserMedia: async () => ({ getTracks: () => [track] }) };
    context.AudioContext = class {
        constructor() { this.state = 'running'; }
        createAnalyser() { return { getFloatTimeDomainData(samples) { samples.fill(.1); } }; }
        createMediaStreamSource() { return { connect() {} }; }
        async decodeAudioData() { return { duration: 1 }; }
        async close() { this.state = 'closed'; closed++; }
    };
    context.OfflineAudioContext = class {
        createBufferSource() { return { connect() {}, start() {} }; }
        async startRendering() { rendered++; return { getChannelData: () => new Float32Array(16000) }; }
    };
    context.MediaRecorder = class {
        constructor() { recorder = this; this.state = 'inactive'; this.mimeType = 'audio/webm'; }
        start() { this.state = 'recording'; }
        stop() { this.state = 'inactive'; queueMicrotask(() => {
            if (this.ondataavailable) this.ondataavailable({ data: new Blob(['final-chunk']) });
            if (this.onstop) this.onstop();
        }); }
    };
    const complete = new context.Capture();
    await complete.start();
    assert.ok(complete.level() > 0);
    const wav = await complete.stop(120);
    assert.equal(wav.length, 32044);
    assert.equal(rendered, 1);
    assert.equal(closed, 1);
    assert.equal(recorder.state, 'inactive');
    assert.equal(track.onended, null);
}

function permissionChecks() {
    let check, request;
    const contents = { getURL: () => 'http://127.0.0.1:8192/', session: {
        setPermissionCheckHandler(handler) { check = handler; },
        setPermissionRequestHandler(handler) { request = handler; },
    } };
    installSpeechPermissions(contents, () => 'http://127.0.0.1:8192');
    assert.equal(check(contents, 'media', 'http://127.0.0.1:8192', { mediaType: 'audio', isMainFrame: true }), true);
    assert.equal(check(contents, 'media', 'https://evil.example', { mediaType: 'audio' }), false);
    assert.equal(check(contents, 'media', 'http://127.0.0.1:8192', { mediaType: 'video' }), false);
    assert.equal(check(contents, 'media', 'http://127.0.0.1:8192', { mediaType: 'audio', isMainFrame: false }), false);
    assert.equal(check(contents, 'media', 'http://127.0.0.1:8192', { mediaType: 'audio' }), false);
    // UI permissions stay available, but only from the trusted application frame.
    assert.equal(check(contents, 'clipboard-sanitized-write', 'http://127.0.0.1:8192',
        { isMainFrame: true, requestingUrl: contents.getURL() }), true);
    assert.equal(check(contents, 'fullscreen', 'http://127.0.0.1:8192',
        { isMainFrame: true, requestingUrl: contents.getURL() }), true);
    assert.equal(check(contents, 'clipboard-sanitized-write', 'https://evil.example',
        { isMainFrame: true, requestingUrl: 'https://evil.example/' }), false);
    assert.equal(check(contents, 'unknown-permission', 'http://127.0.0.1:8192',
        { isMainFrame: true, requestingUrl: contents.getURL() }), false);
    let allowed;
    request(contents, 'media', value => { allowed = value; }, { requestingUrl: contents.getURL(), mediaTypes: ['audio'], isMainFrame: true });
    assert.equal(allowed, true);
    request(contents, 'media', value => { allowed = value; }, { requestingUrl: contents.getURL(), mediaTypes: ['audio', 'video'], isMainFrame: true });
    assert.equal(allowed, false);
}

captureChecks().then(() => { permissionChecks(); console.log('speech input runtime checks passed'); }).catch(error => { console.error(error); process.exitCode = 1; });
