/** Headless, fake-device checks of plugin settings, one-click capture and Final TTS. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const root = path.resolve(__dirname, '../..');
const { chromium } = require(process.env.SUGARAGENT_PLAYWRIGHT_PACKAGE || path.join(root, 'python/Lib/site-packages/playwright/driver/package'));
const output = path.join(root, '.analysis/voice-plugin');
let browser, page, server, heldResponse;
let hold = false;
let transcriptions = 0;
const synthesized = [];
const state = { plugin_enabled: true, enabled: false, language: 'auto', phase: 'unconfigured', runtimeAvailable: true,
    maxAudioBytes: 4194304, maxDurationSeconds: 120,
    asr: { provider: 'openai-compatible', base_url: '', model: '', api_key_set: false },
    tts: { enabled: false, provider: 'mimo', base_url: 'https://api.xiaomimimo.com/v1', model: 'mimo-v2.5-tts', voice: 'mimo_default', speed: 1, instructions: '', api_key_set: false } };
const contribution = { slot: 'settings.section', target: 'renderer', title: '语音输入与朗读', plugin_id: 'voice-input', id: 'voice',
    renderer: { module: '/plugin-assets/voice-input/settings.js', style: '/plugin-assets/voice-input/voice.css' } };
const timeout = setTimeout(() => { console.error('Voice plugin smoke timed out'); process.exit(1); }, 60000);
function wav() {
    const result = Buffer.alloc(32044); result.write('RIFF'); result.writeUInt32LE(result.length - 8, 4); result.write('WAVEfmt ', 8);
    result.writeUInt32LE(16, 16); result.writeUInt16LE(1, 20); result.writeUInt16LE(1, 22); result.writeUInt32LE(16000, 24);
    result.writeUInt32LE(32000, 28); result.writeUInt16LE(2, 32); result.writeUInt16LE(16, 34); result.write('data', 36); result.writeUInt32LE(32000, 40);
    return result;
}
async function run(code) { return page.evaluate(code); }
async function until(expression) { await page.waitForFunction(expression, null, { timeout: 10000 }); }
(async () => {
    server = http.createServer(async (request, response) => {
        const route = request.url.split('?')[0];
        if (route === '/') {
            response.setHeader('Content-Type', 'text/html; charset=utf-8');
            response.end('<!doctype html><html class="theme-dark"><head><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/plugin-assets/voice-input/voice.css"></head><body>'
                + '<main style="max-width:700px;margin:80px auto;padding:12px"><h1>SugarAgent</h1><div id="chat-container">'
                + '<div class="msg-wrap msg-wrap--assistant msg-wrap--answer-frame"><div class="message assistant"><p>这是最终回答，可以朗读。</p><pre>DO_NOT_READ_CODE</pre></div><div class="msg-toolbar"></div></div></div>'
                + '<div class="composer-row"><div class="input-wrapper"><textarea id="message-input"></textarea><button id="send-btn">发送</button></div></div></main>'
                + '<script src="/input-actions.js"></script><script>var currentSessionId="a",revision=0;var messageInput=document.querySelector("textarea");'
                + 'messageInput.addEventListener("input",()=>revision++);window.MyAgentComposer={sessionId:()=>currentSessionId,capture:()=>captureComposerInsertion(messageInput,currentSessionId,revision),insert:(text,span)=>insertComposerTranscript(messageInput,span,currentSessionId,revision,text)};'
                + 'window.myagentOpenSettings=section=>location.assign("/settings#"+section);</script>'
                + '<script type="module">import {installChatExtension} from "/plugin-assets/voice-input/chat.js";window.disposeVoice=installChatExtension();</script></body></html>'); return;
        }
        if (route === '/settings') {
            response.setHeader('Content-Type', 'text/html; charset=utf-8');
            response.end(fs.readFileSync(path.join(root, 'app/templates/settings_center.html'), 'utf8').replaceAll('__SETTINGS_ASSET_VERSION__', 'test').replace('__SETTINGS_BOOTSTRAP__', '{"section":"general"}')); return;
        }
        if (route === '/style.css') { response.setHeader('Content-Type', 'text/css'); response.end(fs.readFileSync(path.join(root, 'frontend/src/styles/app.css'))); return; }
        if (route === '/input-actions.js') { response.setHeader('Content-Type', 'text/javascript'); response.end(fs.readFileSync(path.join(root, 'frontend/src/app/modules/input-actions.js'))); return; }
        if (route.startsWith('/plugin-assets/voice-input/') || route.startsWith('/static/settings/')) {
            const name = path.basename(route);
            const directory = route.startsWith('/plugin-assets') ? 'plugins/voice-input/web' : 'app/templates/static/settings';
            const target = path.join(root, directory, name);
            if (!fs.existsSync(target)) { response.statusCode = 404; response.end(); return; }
            response.setHeader('Content-Type', name.endsWith('.css') ? 'text/css' : 'text/javascript; charset=utf-8'); response.end(fs.readFileSync(target)); return;
        }
        const chunks = []; for await (const chunk of request) chunks.push(chunk);
        const body = Buffer.concat(chunks);
        response.setHeader('Content-Type', 'application/json');
        if (route === '/api/extensions' || route === '/api/plugins/catalog') { response.end(JSON.stringify({ ui_contributions: [contribution], plugins: [] })); return; }
        if (route === '/api/speech/config') {
            const patch = JSON.parse(body);
            Object.keys(patch).forEach(key => {
                if (key === 'asr' || key === 'tts') {
                    for (const [field, value] of Object.entries(patch[key])) {
                        if (field === 'api_key') state[key].api_key_set = !!value;
                        else state[key][field] = value;
                    }
                } else state[key] = patch[key];
            });
            state.phase = state.asr.base_url && state.asr.model ? 'ready' : 'unconfigured';
        }
        if (route === '/api/plugins/voice-input/enabled') state.plugin_enabled = JSON.parse(body).enabled;
        if (route === '/api/speech/transcribe') {
            assert.equal(body.subarray(0, 4).toString(), 'RIFF'); assert.equal(body.readUInt32LE(24), 16000); assert.equal(body.readUInt16LE(22), 1);
            transcriptions++;
            if (hold) { heldResponse = response; return; }
            response.end(JSON.stringify({ text: '语音测试成功' })); return;
        }
        if (route === '/api/speech/synthesize') {
            const value = JSON.parse(body); synthesized.push(value.text);
            response.setHeader('Content-Type', 'audio/wav'); response.end(wav()); return;
        }
        if (route === '/api/speech/synthesize/stream') {
            const value = JSON.parse(body); synthesized.push(value.text);
            response.setHeader('Content-Type', 'audio/pcm');
            response.setHeader('X-Sample-Rate', '16000');
            response.setHeader('X-Channels', '1'); response.setHeader('X-Format', 'pcm16');
            response.end(wav().subarray(44)); return;
        }
        response.end(JSON.stringify(route.startsWith('/api/speech') ? state : {}));
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const origin = 'http://127.0.0.1:' + server.address().port;
    browser = await chromium.launch({ channel: process.env.SUGARAGENT_BROWSER_CHANNEL || 'msedge', headless: true, chromiumSandbox: true,
        args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--autoplay-policy=no-user-gesture-required'] });
    page = await browser.newPage({ viewport: { width: 1080, height: 820 } });
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin + '/settings');
    const voiceNav = page.locator('#st-nav-list [data-id="plugin:voice-input:voice"]');
    await voiceNav.click();
    await page.locator('[data-voice-field="asr.provider"]').waitFor();
    assert.equal(await voiceNav.innerText(), '语音输入与朗读');
    assert.equal(await page.locator('#st-nav-list [data-id="advanced"]').count(), 0);
    assert.equal(await page.locator('#st-title').innerText(), '语音输入与朗读');
    await page.locator('[data-voice-field="enabled"]').check();
    await page.locator('[data-voice-field="asr.provider"]').selectOption('mimo');
    assert.equal(await page.locator('[data-voice-field="asr.model"]').inputValue(), 'mimo-v2.5-asr');
    await page.locator('[data-voice-field="asr.api_key"]').fill('fixture-asr-key');
    await page.locator('[data-voice-field="tts.enabled"]').check();
    await page.locator('[data-voice-field="tts.api_key"]').fill('fixture-tts-key');
    await page.locator('[data-voice-field="tts.voice"]').fill('冰糖');
    await page.locator('[data-save]').click();
    await until("document.querySelector('[data-voice-field=\"asr.api_key\"]').value === ''");
    assert.equal(state.tts.voice, '冰糖'); assert.equal(state.enabled, true);
    fs.mkdirSync(output, { recursive: true }); await page.screenshot({ path: path.join(output, 'voice-settings.png'), fullPage: true });
    await page.goto(origin);
    // Right click (or long press) is the shortcut to voice settings.
    await page.locator('#speech-input-btn').click({ button: 'right' });
    await page.locator('[data-voice-field="asr.provider"]').waitFor();
    assert.equal(new URL(page.url()).hash, '#plugin:voice-input:voice');
    assert.equal(await page.locator('#st-title').innerText(), '语音输入与朗读');
    await page.goto(origin);
    await page.locator('#speech-input-btn').waitFor();
    await page.locator('#message-input').focus();
    await run('document.dispatchEvent(new CustomEvent("myagent:session-change"))');
    assert.equal(await run('document.activeElement.id'), 'message-input', 'initializing a session must not focus the microphone');
    assert.equal(await page.locator('#speech-input-btn').evaluate(node => getComputedStyle(node).outlineStyle), 'none');
    await page.locator('.composer-row').screenshot({ path: path.join(output, 'microphone-startup.png') });
    await page.keyboard.press('Tab');
    assert.equal(await run('document.activeElement.id'), 'speech-input-btn');
    for (const theme of ['theme-light', 'theme-dark']) {
        await page.locator('html').evaluate((node, value) => { node.className = value; }, theme);
        const focus = await page.locator('#speech-input-btn').evaluate(node => {
            const style = getComputedStyle(node);
            return { visible: node.matches(':focus-visible'), style: style.outlineStyle, width: style.outlineWidth, themed: style.outlineColor === style.color };
        });
        assert.deepEqual(focus, { visible: true, style: 'solid', width: '2px', themed: true });
    }
    await page.keyboard.press('Enter');
    await until('document.querySelector(".voice-dock").dataset.state === "recording"');
    assert.equal(await page.locator('#speech-input-btn').getAttribute('aria-pressed'), 'true');
    await page.locator('.composer-row').screenshot({ path: path.join(output, 'voice-recording.png') });
    await page.keyboard.press('Escape');
    await until('document.querySelector(".voice-dock").hidden && document.activeElement.id === "message-input"');
    await page.locator('#speech-input-btn').click();
    await page.locator('#message-input').click();
    assert.equal(await run('document.activeElement.id'), 'message-input', 'leaving the bar must not take focus away from the draft');
    assert.equal(await page.locator('.voice-dock').evaluate(node => node.hidden), true);
    await page.locator('#speech-input-btn').click();
    await until('document.querySelector(".voice-dock").dataset.state === "recording"');
    assert.equal(await page.locator('.speech-activity, .speech-options-btn').count(), 0);
    // The bar sits on the composer instead of floating anywhere on screen.
    assert.equal(await page.locator('.voice-dock').evaluate(node => getComputedStyle(node).position), 'absolute');
    assert.equal(await page.locator('.voice-dock').evaluate(node => node.getBoundingClientRect().bottom
        <= node.closest('.composer-row').getBoundingClientRect().top + 1), true);
    await page.waitForTimeout(350);
    await page.locator('#speech-input-btn').click();
    await until('document.querySelector("textarea").value === "语音测试成功"');
    assert.equal(transcriptions, 1);
    hold = true;
    await page.locator('#speech-input-btn').click();
    await until('document.querySelector(".voice-dock").dataset.state === "recording"');
    await page.waitForTimeout(250); await page.locator('#speech-input-btn').click();
    const end = Date.now() + 5000;
    while (!heldResponse) { if (Date.now() > end) throw new Error('No ASR request'); await new Promise(resolve => setTimeout(resolve, 20)); }
    await run('messageInput.value="正在编辑";messageInput.dispatchEvent(new Event("input"))');
    heldResponse.end(JSON.stringify({ text: '保留文字' })); heldResponse = null;
    await page.locator('[data-insert]').waitFor({ state: 'visible' });
    assert.equal(await page.locator('textarea').inputValue(), '正在编辑');
    await page.locator('[data-insert]').click();
    assert.ok((await page.locator('textarea').inputValue()).includes('保留文字'));
    // A successful insert closes the bar on its own.
    await until('document.querySelector(".voice-dock").hidden');
    const audioResponse = page.waitForResponse(response => response.url().endsWith('/api/speech/synthesize/stream'));
    await page.locator('.voice-read').click();
    await until('document.querySelector(".voice-read").classList.contains("is-playing")');
    await audioResponse;
    assert.ok(synthesized[0].includes('最终回答')); assert.ok(!synthesized[0].includes('DO_NOT_READ_CODE'));
    await page.locator('.voice-read').click();
    await until('!document.querySelector(".voice-read").classList.contains("is-playing")');
    await run('window.disposeVoice()');
    assert.equal(await page.locator('#speech-input-btn,.voice-read,.voice-dock').count(), 0);
    assert.deepEqual(errors, []);
    console.log('voice plugin browser passed: startup focus, themed keyboard focus, direct settings navigation, one-click capture, draft conflict, Final TTS, stop and disposal');
    clearTimeout(timeout); await browser.close(); server.close();
})().catch(async error => {
    console.error(error); clearTimeout(timeout);
    if (page) { fs.mkdirSync(output, { recursive: true }); await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }); }
    if (browser) await browser.close(); if (server) server.close(); process.exitCode = 1;
});
