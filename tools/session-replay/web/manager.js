(() => {
    const $ = id => document.getElementById(id);
    let health, sessions = [], current, pendingImport;
    const status = (text, error = false) => { $('import-status').textContent = text; $('import-status').className = 'status' + (error ? ' error' : ''); };
    const api = window.createReplayApi();
    function option(select, value, label) {select.add(new Option(label, value));}
    function scopeLabel(unit) {
        const kind = {reasoning:'思考',response:'回复',llm_reasoning:'思考',llm_response:'回复'}[unit.kind] || unit.kind;
        return `${unit.iteration != null ? '第 ' + unit.iteration + ' 步 · ' : ''}${kind} · ${(unit.duration_ms / 1000).toFixed(1)} 秒 · ${unit.delta_count} 增量`;
    }
    function fillSegments() {
        const list = current?.units.filter(u => u.run_id === $('run').value && u.scope === $('scope').value) || [];
        $('segment').replaceChildren();
        list.forEach(u => option($('segment'), u.id, scopeLabel(u)));
        $('open-replay').disabled = !list.length;
        fillInfo();
    }
    function fillInfo() {
        const u = current?.units.find(u => u.id === $('segment').value);
        $('segment-info').textContent = u ? `${u.started_at ? new Date(u.started_at).toLocaleString() : '无时间戳'} · seq ${u.first_seq}–${u.last_seq}` + (u.delta_count ? ' · 按日志节奏重放' : ' · 没有流式增量，默认逐字模拟，可在重放页关闭') : '这个任务没有此类片段，请切换播放范围。';
    }
    async function selectSession() {
        current = sessions.find(s => s.id === $('session').value);
        $('run').replaceChildren();
        if (!current) {fillSegments(); return;}
        current.units.filter(u => u.scope === 'run').forEach(u => option($('run'), u.run_id, `任务 ${u.run_number} · ${u.started_at ? new Date(u.started_at).toLocaleString() : u.run_id}`));
        const playable = current.units.find(u => u.scope === $('scope').value);
        if(playable) $('run').value = playable.run_id;
        $('session-warning').hidden = !current.warnings.length;
        $('session-warning').textContent = current.warnings.join('；');
        $('download-report').href = '/api/replay/report.zip?session=' + current.id;
        fillSegments(); await loadResults();
    }
    async function refresh(preferred) {
        const selected = preferred || $('session').value;
        sessions = await api('/api/replay/sessions');
        $('session').replaceChildren();
        sessions.forEach(s => option($('session'), s.id, `${s.name} · ${s.run_count} 个任务`));
        if (sessions.some(s => s.id === selected)) $('session').value = selected;
        await selectSession();
    }
    async function loadResults() {
        const results = await api('/api/replay/results' + (current ? '?session=' + current.id : ''));
        $('records').replaceChildren(); $('record-count').textContent = results.length + ' 次';
        for (const r of results) {
            const tr = document.createElement('tr'), s = r.summary || {}, u = r.segment || {};
            const state = (r.status === 'completed' ? (r.text_verified===null ? '完成（无文本校验）' : r.text_verified ? '文字通过' : '文字不完整') : r.status) + (r.playback?.synthetic ? ' · 逐字模拟' : '');
            const disabled=r.experiments?.disabled||[];
            const changes=disabled.map(id=>r.experiments.features.find(f=>f.id===id)?.label||id);
            const configuration=r.experiments?(changes.length?'关闭：'+changes.slice(0,2).join('、')+(changes.length>2?' 等'+changes.length+'项':''):'全部开启 / 原版')+' · '+r.experiments.fingerprint:'旧记录：未记录开关';
            const values = [new Date(r.saved_at).toLocaleTimeString(), `${r.version} · 任务${u.run_number}/${u.iteration ?? '全部'}`, configuration, state + (r.eligible_for_comparison ? '' : ' · 条件已标注'), s.mean_raf_callbacks_per_second ?? '—', `${s.p95_gap_ms ?? '—'} / ${s.max_gap_ms ?? '—'} ms`, (r.markers || []).length];
            values.forEach((value,index) => {const td = document.createElement('td'); td.textContent = value;if(index===2)td.title=r.experiments?.label||configuration;tr.append(td);});
            const td = document.createElement('td'), a = document.createElement('a'); a.href = '/api/replay/result.json?record=' + r.record_id; a.textContent = 'JSON'; td.append(a); tr.append(td); $('records').append(tr);
        }
        if (!results.length) {const tr = document.createElement('tr'), td = document.createElement('td'); td.colSpan = 8; td.className = 'empty'; td.textContent = '播放结束后，卡顿记录会出现在这里。'; tr.append(td); $('records').append(tr);}
    }
    async function importSource(request) {
        try {
            $('candidate-area').hidden = true; status('正在读取日志、恢复引用并建立轮次索引…');
            const imported = await api('/api/replay/import', {method:'POST',body:request});
            status(`已导入「${imported.name}」：${imported.events.toLocaleString()} 条事件，${imported.run_count} 个任务。`);
            await refresh(imported.id);
        } catch (error) {
            if (error.data?.candidates) {
                pendingImport = request; $('candidate').replaceChildren();
                error.data.candidates.forEach(c => option($('candidate'), c, c || '根目录会话'));
                $('candidate-area').hidden = false; status('此材料含多个会话，请选择要导入的会话。');
            } else status(error.message, true);
        }
    }
    async function upload(files, zip) {
        const buttons = [$('choose-folder'),$('choose-zip'),$('import-path')]; buttons.forEach(b => b.disabled = true);
        try {
            const selected = zip ? Array.from(files).slice(0,1) : Array.from(files).filter(f => /(^|\/)(events\.jsonl|metadata\.json)$|\/blobs\/|\/snapshots\/ui_/.test(f.webkitRelativePath));
            if (!selected.length) throw new Error('所选文件夹没有 events.jsonl');
            const {job} = await api('/api/replay/upload/start', {method:'POST'});
            for (let i = 0; i < selected.length; i++) {
                const f = selected[i], path = zip ? 'session.zip' : f.webkitRelativePath;
                status(`正在导入文件 ${i + 1}/${selected.length}：${f.name}`);
                await api(`/api/replay/upload/file?job=${job}&path=${encodeURIComponent(path)}`, {method:'POST',body:f});
            }
            await importSource({job});
        } catch (error) {status(error.message==='Failed to fetch' ? '读取所选文件失败，文件可能正在变化。请先复制会话目录后导入，或改用本机路径／ZIP 导入。' : error.message, true);} finally {buttons.forEach(b => b.disabled = false);}
    }
    $('import-path').onclick = () => importSource({path:$('source-path').value});
    $('source-path').onkeydown = e => {if (e.key === 'Enter') $('import-path').click();};
    $('choose-zip').onclick = () => $('zip-input').click();
    $('choose-folder').onclick = () => $('folder-input').click();
    $('zip-input').onchange = e => {if(e.target.files.length) upload(e.target.files, true); e.target.value = '';};
    $('folder-input').onchange = e => {if(e.target.files.length) upload(e.target.files, false); e.target.value = '';};
    $('choose-candidate').onclick = () => importSource({...pendingImport,candidate:$('candidate').value});
    $('session').onchange = selectSession; $('run').onchange = fillSegments; $('scope').onchange = fillSegments; $('segment').onchange = fillInfo;
    $('refresh').onclick = () => refresh().catch(e => status(e.message,true));
    $('open-replay').onclick = () => { const url = `/view/${$('version').value}/?real=1&replay=${$('session').value}&segment=${$('segment').value}`; window.open(url,'_blank','noopener'); };
    $('stop-service').onclick = async () => {await api('/api/replay/shutdown',{method:'POST'}); status('服务已停止。双击启动.cmd 可再次打开。');};
    window.addEventListener('focus', () => {if(health) loadResults().catch(()=>{});});
    (async () => {try {health = await api('/api/replay/health'); health.versions.forEach(v => option($('version'),v.version,v.label || v.version)); $('version').value = health.versions.some(v=>v.version==='20261007')?'20261007':health.versions.at(-1).version; $('data-location').textContent = '工具 ' + health.tool_version + ' · 本机记录：' + health.data_dir; await refresh();} catch(e) {status(e.message,true);}})();
})();
