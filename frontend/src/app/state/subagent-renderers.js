function subagentMoreDotsHtml() {
    return '<span class="session-more-dots" aria-hidden="true"><span></span><span></span><span></span></span>';
}

function subagentSortKey(n) {
    var t = Date.parse(String((n && (n.updated_at || n.created_at)) || ''));
    return isNaN(t) ? 0 : t;
}

function sortSubagentsByUpdated(flat) {
    return (flat || []).slice().sort(function (a, b) {
        return subagentSortKey(b) - subagentSortKey(a);
    });
}

function subagentStatusFromNode(n) {
    var taskStatus = String((n && (n.task_status || n.status)) || '').toLowerCase();
    var hasFinalKnown = !!(n && Object.prototype.hasOwnProperty.call(n, 'has_final'));
    var hasPreview = !!String((n && n.result_preview) || '').trim();
    var hasFinal = !n || !hasFinalKnown ? hasPreview : !!n.has_final;
    var canTreatCompleted = hasFinal || (!hasFinalKnown && hasPreview) || (n && n.virtual_task && hasPreview && !hasFinalKnown);
    if (n && n.running) {
        return { label: n.background ? '后台运行' : '运行中', dotCls: 'is-running' };
    }
    if (taskStatus === 'running') return { label: '后台运行', dotCls: 'is-running' };
    if (taskStatus === 'completed' && canTreatCompleted) return { label: '完成', dotCls: 'is-done' };
    if (taskStatus === 'completed') return { label: '缺少 final 结果', dotCls: 'is-error' };
    if (taskStatus === 'failed') return { label: '失败', dotCls: 'is-error' };
    if (taskStatus === 'interrupted') return { label: '已中断', dotCls: 'is-error' };
    if (n && n.ok === false) {
        var err = String(n.error || n.result_preview || '').trim();
        if (/interrupt/i.test(err)) return { label: '已中断', dotCls: 'is-error' };
        return { label: '失败', dotCls: 'is-error' };
    }
    if (n && n.status === 'interrupted') return { label: '已中断', dotCls: 'is-error' };
    if (n && n.status === 'failed') return { label: '失败', dotCls: 'is-error' };
    var prev = String((n && n.result_preview) || '').trim();
    if (/^Error:|^错误|失败|异常|interrupt/i.test(prev)) {
        return { label: '失败', dotCls: 'is-error' };
    }
    return { label: '完成', dotCls: 'is-done' };
}

function subagentCardViewModel(n) {
    n = n || {};
    var id = String(n.id || '');
    var running = !!n.running && !n.virtual_task;
    var name = n.description || id.slice(0, 8);
    return {
        id: id,
        running: running,
        name: name,
        idShort: id.length > 5 ? id.slice(0, 5) + '...' : id,
        typeLabel: n.subagent_type || 'subagent',
        status: subagentStatusFromNode(n),
        resultPreview: String(n.result_preview || '').trim(),
        outputFile: !!n.output_file,
        taskStatus: n.task_status || n.status || '',
        hasFinalKnown: Object.prototype.hasOwnProperty.call(n, 'has_final'),
        hasFinal: !!n.has_final,
        executorModel: n.executor_model || '',
    };
}

function renderSubagentCardHtml(n) {
    var vm = subagentCardViewModel(n);
    if (!vm.id) return '';
    var stopBtn = vm.running ? '<button type="button" class="subagent-card-menu-item subagent-card-stop" role="menuitem" data-agent-id="' + escapeHtml(vm.id) + '">停止</button>' : '';
    var outputBtn = vm.outputFile ? '<button type="button" class="subagent-card-menu-item subagent-card-output" role="menuitem" data-agent-id="' + escapeHtml(vm.id) + '">查看输出</button>' : '';
    var html = '<div class="process-aggregate subagent-grid-card" data-agent-id="' + escapeHtml(vm.id) + '"';
    if (vm.executorModel) html += ' data-executor-model="' + escapeHtml(String(vm.executorModel)) + '"';
    if (vm.outputFile) html += ' data-output-file="1"';
    if (vm.taskStatus) html += ' data-task-status="' + escapeHtml(String(vm.taskStatus)) + '"';
    if (vm.hasFinalKnown) html += ' data-has-final="' + (vm.hasFinal ? '1' : '0') + '"';
    html += ' data-subagent-running="' + (vm.running ? '1' : '0') + '"';
    html += ' data-description="' + escapeHtml(String(vm.name || '')) + '"';
    html += '>';
    html += '<div class="subagent-card-head">';
    html += '<div class="subagent-card-head-line">';
    html += '<span class="process-aggregate-title-wrap">';
    html += '<div class="subagent-card-title-row">';
    html += '<span class="subagent-status"><span class="subagent-status-dot ' + vm.status.dotCls + '" data-ui-tip="' + escapeHtml(vm.status.label) + '"></span></span>';
    html += '<span class="subagent-card-name">' + escapeHtml(vm.name) + '</span>';
    html += '<span class="subagent-card-type">' + escapeHtml(vm.typeLabel) + '</span>';
    html += '<span class="subagent-card-id">' + escapeHtml(vm.idShort) + '</span>';
    html += '</div>';
    html += '<span class="process-aggregate-stats" aria-live="polite"></span>';
    html += '</span>';
    html += '<span class="subagent-card-head-actions">';
    html += '<button type="button" class="subagent-card-expand" data-agent-id="' + escapeHtml(vm.id) + '" aria-label="放大显示" aria-pressed="false" data-ui-tip="在浮窗内全屏显示"><svg class="subagent-card-expand-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M3 6V3h3M10 3h3v3M13 10v3h-3M6 13H3v-3" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"/></svg></button>';
    html += '<span class="subagent-card-menu">'
        + '<button type="button" class="subagent-card-menu-btn" aria-label="更多操作" aria-expanded="false" data-ui-tip="更多操作">' + subagentMoreDotsHtml() + '</button>'
        + '<span class="subagent-card-menu-pop" role="menu">'
        + outputBtn
        + stopBtn
        + '<button type="button" class="subagent-card-menu-item subagent-card-delete" role="menuitem" data-agent-id="' + escapeHtml(vm.id) + '">删除</button>'
        + '</span></span>';
    html += '</span>';
    html += '</div></div>';
    html += '<div class="subagent-card-body subagent-dialogue-body" data-agent-id="' + escapeHtml(vm.id) + '"'
        + (vm.resultPreview ? ' data-result-preview="' + escapeHtml(vm.resultPreview.slice(0, 400)) + '"' : '')
        + '></div>';
    html += '</div>';
    return html;
}

function buildSubagentGridHtml(flat) {
    var sorted = sortSubagentsByUpdated(flat);
    if (!sorted.length) return '<div class="subagent-grid-empty">无 Subagent</div>';
    return sorted.map(renderSubagentCardHtml).join('');
}
