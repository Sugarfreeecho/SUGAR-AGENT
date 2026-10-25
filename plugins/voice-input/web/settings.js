import { voiceRequest } from './shared.js';

export async function mountSettings({ root, settings: A }) {
    const { t, esc, W } = A;
    root.classList.add('voice-settings');
    let state = null, disposed = false, timer = null, saving = false;
    const field = (section, key, label, type = 'text', value = '') => W.row(label, '',
        '<input class="st-input" data-voice-field="' + section + '.' + key + '" type="' + type + '" value="' + esc(value) + '" autocomplete="' + (type === 'password' ? 'new-password' : 'off') + '">');
    const select = (section, key, label, options, selected) => W.row(label, '',
        '<select class="st-input" data-voice-field="' + section + '.' + key + '">' + options.map(([value, name]) =>
            '<option value="' + value + '"' + (selected === value ? ' selected' : '') + '>' + name + '</option>').join('') + '</select>');
    const checked = (name, label, value) => W.row(label, '', '<input type="checkbox" data-voice-field="' + name + '"' + (value ? ' checked' : '') + '>');
    const languages = [['auto', t('自动', 'Auto')], ['zh', t('中文', 'Chinese')], ['en', t('英语', 'English')], ['yue', t('粤语（本地）', 'Cantonese (local)')], ['ja', t('日语（本地）', 'Japanese (local)')], ['ko', t('韩语（本地）', 'Korean (local)')]];
    const providers = [['openai-compatible', t('通用兼容接口', 'Compatible API')], ['mimo', 'Xiaomi MiMo']];
    function render() {
        const asr = state?.asr || { provider: 'openai-compatible' };
        const tts = state?.tts || { provider: 'mimo', base_url: 'https://api.xiaomimimo.com/v1', model: 'mimo-v2.5-tts', voice: 'mimo_default', speed: 1 };
        function apiFields(section, config) {
            return '<div data-api-fields="' + section + '">' +
                field(section, 'base_url', t('API 基础地址', 'API base URL'), 'url', config.base_url || '') +
                field(section, 'model', t('模型名称', 'Model name'), 'text', config.model || '') +
                W.row('API Key', config.api_key_set ? t('已配置；留空保留原密钥', 'Configured; leave blank to keep') : t('仅在后端保存，不回显', 'Write-only; stored on the backend'),
                    '<input class="st-input" type="password" autocomplete="new-password" data-voice-field="' + section + '.api_key" placeholder="' + (config.api_key_set ? '••••••' : '') + '">' +
                    '<label class="voice-clear-key"><input type="checkbox" data-clear-key="' + section + '"> ' + t('清除密钥', 'Clear key') + '</label>') + '</div>';
        }
        root.innerHTML = W.card(t('语音插件', 'Voice plugin'), t('语音识别与朗读由独立插件提供。', 'Speech recognition and reading are provided by a plugin.'),
            W.row(t('启用语音插件', 'Enable voice plugin'), '', '<input type="checkbox" data-plugin-enabled' + (state?.plugin_enabled ? ' checked' : '') + '>')) +
            W.card(t('语音输入（ASR）', 'Voice input (ASR)'), t('API 模式无需下载模型；录音会发送给所配置的服务。', 'API mode needs no local models; recordings go to your configured provider.'),
                checked('enabled', t('启用语音输入', 'Enable voice input'), state?.enabled) +
                select('asr', 'provider', t('识别方式', 'Recognition provider'), [...providers, ['local', 'SenseVoice · ' + t('本地离线', 'Local offline')]], asr.provider) +
                select('root', 'language', t('识别语言', 'Language'), languages, state?.language || 'auto') + apiFields('asr', asr) +
                '<div data-local-info>' + W.note(t('本地模式需另装插件 requirements.txt，首次下载约 241 MB 模型，并占用 CPU 和内存。API 模式不加载这些资源。', 'Local mode requires the plugin requirements.txt and about 241 MB of models, plus CPU and memory. API mode does not load them.')) + '</div>') +
            W.card(t('Final 卡片朗读（TTS）', 'Final-card reading (TTS)'), t('仅在点击朗读时发送卡片文字；不自动朗读，也不需要本地 TTS 模型。', 'Card text is sent only when you click Read aloud; no automatic playback or local TTS model.'),
                checked('tts.enabled', t('启用朗读', 'Enable reading'), tts.enabled) +
                checked('tts.autoRead', t('回答完成后自动朗读', 'Read answers automatically'), tts.autoRead) +
                select('tts', 'provider', t('合成接口', 'Speech provider'), providers, tts.provider) + apiFields('tts', tts) +
                field('tts', 'voice', t('音色 ID', 'Voice ID'), 'text', tts.voice || '') +
                W.note(t('小米音色：mimo_default、冰糖、茉莉、苏打、白桦、Mia、Chloe、Milo、Dean。音色名可直接填写。', 'MiMo voices: mimo_default, 冰糖, 茉莉, 苏打, 白桦, Mia, Chloe, Milo, Dean. Enter a voice ID directly.')) +
                field('tts', 'speed', t('语速（0.25–4）', 'Speed (0.25–4)'), 'number', tts.speed || 1) +
                field('tts', 'instructions', t('朗读风格（可选）', 'Reading style (optional)'), 'text', tts.instructions || '')) +
            '<div data-actions><button type="button" class="st-btn primary" data-save>' + t('保存语音配置', 'Save voice settings') + '</button>' +
            '<select class="st-input" data-source><option value="auto">' + t('自动下载源', 'Automatic source') + '</option><option value="mirror">HF-Mirror</option><option value="huggingface">Hugging Face</option></select>' +
            '<button type="button" class="st-btn" data-prepare>' + t('下载并准备本地模型', 'Prepare local model') + '</button>' +
            '<button type="button" class="st-btn" data-cancel-prepare>' + t('取消准备', 'Cancel preparation') + '</button></div><p data-status role="status" aria-live="polite"></p><progress max="1" hidden></progress><p class="voice-error" role="alert"></p>';
        updateVisibility(); updateStatus();
    }
    function value(name) { return root.querySelector('[data-voice-field="' + name + '"]'); }
    function updateVisibility() {
        const local = value('asr.provider').value === 'local';
        root.querySelector('[data-api-fields="asr"]').hidden = local;
        root.querySelector('[data-local-info]').hidden = !local;
        root.querySelector('[data-prepare]').hidden = !local;
        root.querySelector('[data-source]').hidden = !local;
        root.querySelectorAll('[data-voice-field], [data-save], [data-prepare], [data-clear-key]').forEach(node => { node.disabled = !state?.plugin_enabled || saving; });
    }
    function updateStatus() {
        if (!root.querySelector('[data-status]')) return;
        const phases = { ready: t('已就绪', 'Ready'), unconfigured: t('请配置 API 地址和模型', 'Configure an API URL and model'), unprepared: t('本地模型尚未准备', 'Local model setup required'), checking: t('检查中', 'Checking'), downloading: t('下载中', 'Downloading'), verifying: t('校验中', 'Verifying'), loading: t('加载中', 'Loading'), failed: t('准备失败', 'Setup failed'), cancelled: t('准备已取消', 'Setup cancelled') };
        root.querySelector('[data-status]').textContent = (phases[state?.phase] || '') + (state?.file ? ' · ' + state.file : '')
            + (state?.totalBytes ? ' · ' + Math.round(state.completedBytes / state.totalBytes * 100) + '%' : '')
            + (state?.runtimeAvailable === false ? ' · ' + t('本地运行库未安装', 'Local runtime not installed') : '');
        const progress = root.querySelector('progress');
        progress.hidden = state?.phase !== 'downloading'; progress.value = state?.totalBytes ? state.completedBytes / state.totalBytes : 0;
        root.querySelector('[data-cancel-prepare]').hidden = !['checking', 'downloading', 'verifying', 'loading'].includes(state?.phase);
        if (state?.error) error(state.error);
    }
    function error(message) { root.querySelector('.voice-error').textContent = message; }
    async function pull() {
        try { const next = await (await voiceRequest('status')).json(); if (!disposed) state = next; }
        catch (failure) { if (!state) state = { plugin_enabled: false }; else throw failure; }
    }
    async function save() {
        const patch = {};
        root.querySelectorAll('[data-voice-field]').forEach(node => {
            const name = node.dataset.voiceField;
            const content = node.type === 'checkbox' ? node.checked : node.type === 'number' ? Number(node.value) : node.value;
            const [section, key] = name.split('.');
            if (!key) patch[section] = content;
            else if (section === 'root') patch[key] = content;
            else {
                patch[section] ||= {};
                if (key !== 'api_key' || content) patch[section][key] = content;
            }
        });
        root.querySelectorAll('[data-clear-key]:checked').forEach(node => { patch[node.dataset.clearKey].api_key = null; });
        saving = true; updateVisibility();
        try {
            state = await (await voiceRequest('config', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch) })).json();
            state.plugin_enabled = true;
            if (!disposed) { render(); A.toast(t('语音配置已保存', 'Voice settings saved')); }
        } catch (failure) { if (!disposed) error(failure.message); }
        finally { saving = false; if (!disposed) updateVisibility(); }
    }
    async function click(event) {
        const node = event.target.closest('button');
        if (!node) return;
        if (node.hasAttribute('data-save')) { await save(); return; }
        if (node.hasAttribute('data-prepare') || node.hasAttribute('data-cancel-prepare')) {
            node.disabled = true;
            try {
                state = await (await voiceRequest('prepare', node.hasAttribute('data-prepare') ? {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ source: root.querySelector('[data-source]').value }),
                } : { method: 'DELETE' })).json(); updateStatus();
            } catch (failure) { error(failure.message); }
            finally { node.disabled = false; }
        }
    }
    async function change(event) {
        const node = event.target;
        if (node.hasAttribute('data-plugin-enabled')) {
            node.disabled = true;
            try {
                await A.api('/api/plugins/voice-input/enabled', { method: 'POST', body: { enabled: node.checked } });
                await pull(); if (!disposed) render();
            } catch (failure) { error(failure.message); node.disabled = false; }
            return;
        }
        if (node.dataset.voiceField?.endsWith('.provider')) {
            const section = node.dataset.voiceField.split('.')[0];
            if (node.value === 'mimo') {
                value(section + '.base_url').value = 'https://api.xiaomimimo.com/v1';
                value(section + '.model').value = section === 'tts' ? 'mimo-v2.5-tts' : 'mimo-v2.5-asr';
                if (section === 'tts') value('tts.voice').value = 'mimo_default';
                if (section === 'asr' && !['auto', 'zh', 'en'].includes(value('root.language').value)) value('root.language').value = 'auto';
            }
            updateVisibility();
        }
    }
    await pull(); if (disposed) return;
    render(); root.addEventListener('click', click); root.addEventListener('change', change);
    async function poll() {
        if (disposed || !root.isConnected) return;
        try { await pull(); if (!disposed) updateStatus(); } catch (failure) { if (!disposed) error(failure.message); }
        if (!disposed) timer = setTimeout(poll, state?.phase === 'downloading' ? 600 : 2500);
    }
    timer = setTimeout(poll, 1000);
    return () => { disposed = true; clearTimeout(timer); root.removeEventListener('click', click); root.removeEventListener('change', change); };
}
