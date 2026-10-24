/* Global lifecycle state survives the backend connection it observes. */
var runtimeLifecycle = { operation:null, instanceId:'', uiToken:'', offlineAt:0, confirming:false, serverDraining:false, supervisorUnavailable:false,
    resume:true, timer:null, busy:false, signature:'', dismissed:'', error:'' };

function runtimeLifecycleIsBlocked() {
    var operation = runtimeLifecycle.operation;
    return runtimeLifecycle.serverDraining || (!!operation && ['authorized','checkpointed','draining','stopping','starting','recovering'].includes(operation.phase));
}
function runtimeLifecycleStorageKey() { return 'myagent-lifecycle:' + location.origin; }
function acceptRuntimeLifecycleOperation(operation) {
    if (!operation || !operation.restart_id || !operation.phase) return false;
    var previous = runtimeLifecycle.operation;
    if (previous && previous.restart_id === operation.restart_id && Number(previous.revision) > Number(operation.revision)) return false;
    if (previous && previous.restart_id !== operation.restart_id && Number(previous.created_at) > Number(operation.created_at)) return false;
    if (!previous || previous.restart_id !== operation.restart_id) runtimeLifecycle.resume = operation.resume_requester !== false;
    runtimeLifecycle.operation = operation;
    try { sessionStorage.setItem(runtimeLifecycleStorageKey(), JSON.stringify(operation)); } catch (_) { /* retain memory */ }
    if (runtimeLifecycleIsBlocked() && typeof persistInputDraft === 'function' && typeof messageInput !== 'undefined') {
        persistInputDraft(currentSessionId || '', messageInput.value);
    }
    renderRuntimeLifecycle();
    return true;
}
function runtimeLifecycleText(operation) {
    if (runtimeLifecycle.confirming) return '正在提交重启确认';
    if (runtimeLifecycle.supervisorUnavailable) return '重启状态待核实：监督器暂不可用';
    if (runtimeLifecycle.offlineAt && runtimeLifecycleIsBlocked() && operation.phase !== 'failed') return '正在等待服务重新连接';
    return ({awaiting_confirmation:'Agent 请求重启服务，等待你确认', authorized:'已确认，正在保存任务状态',
        checkpointed:'任务已保存，正在交接重启', draining:'正在保存并停止运行任务', stopping:'正在重启服务',
        starting:'正在等待新服务启动', recovering:'服务已启动，正在同步任务状态', completed:'服务已重启',
        denied:'本次未重启', cancelled:'重启请求已取消', failed:'重启未完成'})[operation.phase] || '正在核实服务状态';
}
function lifecycleElement(tag, className, text) {
    var element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}
function buildLifecycleCard(operation, inline) {
    var card = lifecycleElement('section','runtime-lifecycle-card' + (inline ? ' runtime-lifecycle-inline' : ''));
    card.dataset.restartId = operation.restart_id;
    card.setAttribute('role','status'); card.setAttribute('aria-live','polite');
    card.appendChild(lifecycleElement('strong','',runtimeLifecycleText(operation)));
    card.appendChild(lifecycleElement('span','runtime-lifecycle-clock'));
    var details = lifecycleElement('details','runtime-lifecycle-details');
    details.open = ['awaiting_confirmation','failed'].includes(operation.phase);
    details.appendChild(lifecycleElement('summary','','查看重启原因与影响'));
    details.appendChild(lifecycleElement('p','',operation.reason || '用户请求重启服务'));
    if (operation.change_summary) details.appendChild(lifecycleElement('p','',operation.change_summary));
    var impact = operation.impact || {};
    details.appendChild(lifecycleElement('p','','当前影响：' + Number(impact.running_tasks || 0) + ' 个运行任务、'
        + Number(impact.background_jobs || 0) + ' 个后台命令、' + Number(impact.terminals || 0) + ' 个终端。'));
    details.appendChild(lifecycleElement('p','','运行任务将保存进度后按策略恢复；后台命令和终端会中断。'));
    card.appendChild(details);
    [operation.error,runtimeLifecycle.error,operation.recovery_summary].filter(Boolean).forEach(function(text) {
        card.appendChild(lifecycleElement('p','runtime-lifecycle-note',text));
    });
    if (runtimeLifecycle.supervisorUnavailable) card.appendChild(lifecycleElement('p','runtime-lifecycle-note',
        '尚未确认重启结果。请查看日志，必要时退出并重新打开完整应用。'));
    var actions = lifecycleElement('div','runtime-lifecycle-actions');
    function button(label, callback, primary) {
        var item = lifecycleElement('button',primary ? 'runtime-lifecycle-primary' : '',label);
        item.type = 'button'; item.disabled = runtimeLifecycle.confirming;
        item.addEventListener('click',callback); actions.appendChild(item);
    }
    if (operation.phase === 'awaiting_confirmation') {
        if (operation.session_id) {
            var label = lifecycleElement('label','runtime-lifecycle-resume');
            var checkbox = document.createElement('input');
            checkbox.type = 'checkbox'; checkbox.checked = runtimeLifecycle.resume;
            checkbox.dataset.lifecycleResume = 'true';
            checkbox.addEventListener('change',function() {
                runtimeLifecycle.resume = checkbox.checked;
                document.querySelectorAll('[data-lifecycle-resume]').forEach(function(item) { item.checked = runtimeLifecycle.resume; });
            });
            label.append(checkbox,document.createTextNode('重启后继续本次任务')); card.appendChild(label);
        }
        button('暂不重启',function() { void decideRuntimeRestart('deny'); });
        button('确认重启',function() { void decideRuntimeRestart('allow_once'); },true);
    } else if (operation.phase === 'failed' || runtimeLifecycle.offlineAt || runtimeLifecycle.supervisorUnavailable) {
        button('重试连接',function() { void refreshRuntimeLifecycle(); });
        if (operation.phase === 'failed') button('重新申请重启',function() { void requestRuntimeRestartAgain(); });
        if (window.sugarAgentDesktop && window.sugarAgentDesktop.openLogs) button('查看日志',function() { void window.sugarAgentDesktop.openLogs(); });
    }
    if (['completed','denied','cancelled','failed'].includes(operation.phase) && !inline) {
        button('收起',function() { runtimeLifecycle.dismissed = operation.restart_id; renderRuntimeLifecycle(); });
    }
    card.appendChild(actions); return card;
}
function renderRuntimeLifecycle() {
    var operation = runtimeLifecycle.operation;
    if (!operation) return;
    document.documentElement.classList.toggle('runtime-restarting',runtimeLifecycleIsBlocked());
    var signature = [operation.restart_id,operation.revision,runtimeLifecycle.confirming,!!runtimeLifecycle.offlineAt,
        runtimeLifecycle.error,runtimeLifecycle.dismissed,runtimeLifecycle.supervisorUnavailable].join(':');
    if (signature !== runtimeLifecycle.signature) {
        runtimeLifecycle.signature = signature;
        var panel = document.getElementById('runtime-lifecycle-panel');
        if (!panel) { panel = lifecycleElement('aside','runtime-lifecycle-panel'); panel.id = 'runtime-lifecycle-panel'; document.body.appendChild(panel); }
        panel.replaceChildren(); panel.hidden = runtimeLifecycle.dismissed === operation.restart_id;
        if (!panel.hidden) panel.appendChild(buildLifecycleCard(operation,false));
    }
    if (operation.tool_call_id && typeof currentSessionId !== 'undefined' && currentSessionId === operation.session_id
        && typeof humanInteractionToolSlot === 'function' && typeof getVisibleChatStream === 'function') {
        var slot = humanInteractionToolSlot(getVisibleChatStream(),operation.tool_call_id,operation);
        if (slot && slot.dataset.lifecycleRevision !== signature) {
            var old = slot.querySelector('.runtime-lifecycle-inline'); if (old) old.remove();
            slot.appendChild(buildLifecycleCard(operation,true)); slot.dataset.lifecycleRevision = signature;
        }
    }
    var waited = runtimeLifecycle.offlineAt ? Math.floor((Date.now() - runtimeLifecycle.offlineAt) / 1000) : 0;
    document.querySelectorAll('.runtime-lifecycle-clock').forEach(function(element) {
        element.textContent = waited ? ' · 已等待 ' + waited + ' 秒' + (waited > 180 ? '，状态仍待核实' : '') : '';
    });
}
async function lifecycleFetch(path,options) {
    var controller = new AbortController();
    var timer = setTimeout(function() { controller.abort(); },5000);
    try {
        var response = await fetch(path,Object.assign({cache:'no-store'},options || {},{signal:controller.signal}));
        var payload = await response.json();
        if (!response.ok) {
            if (payload.operation && payload.operation.confirmation_changed) acceptRuntimeLifecycleOperation(payload.operation);
            throw new Error(payload.error || (payload.operation && payload.operation.confirmation_changed
                ? '运行任务数量已变化，请核对后重新确认' : '服务暂不可用'));
        }
        return payload;
    } finally { clearTimeout(timer); }
}
async function decideRuntimeRestart(decision) {
    if (runtimeLifecycle.confirming || !runtimeLifecycle.operation) return;
    var operation = runtimeLifecycle.operation;
    runtimeLifecycle.confirming = true; runtimeLifecycle.error = ''; renderRuntimeLifecycle();
    try {
        var payload = await lifecycleFetch('/api/lifecycle/restarts/' + encodeURIComponent(operation.restart_id) + '/decision',{
            method:'POST',headers:{'Content-Type':'application/json','X-MyAgent-Lifecycle-UI':runtimeLifecycle.uiToken},
            body:JSON.stringify({decision:decision,request_digest:operation.request_digest,resume_requester:runtimeLifecycle.resume})});
        acceptRuntimeLifecycleOperation(payload.operation);
    } catch(error) {
        runtimeLifecycle.error = error.message + '；将查询原重启请求的状态。'; void refreshRuntimeLifecycle();
    } finally { runtimeLifecycle.confirming = false; runtimeLifecycle.signature = ''; renderRuntimeLifecycle(); }
}
async function requestRuntimeRestartAgain() {
    if (runtimeLifecycle.confirming) return;
    runtimeLifecycle.confirming = true;
    try {
        var payload = await lifecycleFetch('/api/lifecycle/restarts', {method:'POST',
            headers:{'Content-Type':'application/json','X-MyAgent-Lifecycle-UI':runtimeLifecycle.uiToken},
            body:JSON.stringify({reason:'用户在重启失败后重新申请重启服务'})});
        runtimeLifecycle.error = '';
        acceptRuntimeLifecycleOperation(payload.operation);
    } catch(error) { runtimeLifecycle.error = error.message; }
    finally { runtimeLifecycle.confirming = false; renderRuntimeLifecycle(); }
}
async function refreshRuntimeLifecycle() {
    if (runtimeLifecycle.busy) return;
    runtimeLifecycle.busy = true;
    try {
        var query = runtimeLifecycle.operation && runtimeLifecycleIsBlocked() ? '?restart_id=' + encodeURIComponent(runtimeLifecycle.operation.restart_id) : '';
        var payload = await lifecycleFetch('/api/lifecycle/status' + query);
        runtimeLifecycle.uiToken = payload.ui_token || '';
        var changed = runtimeLifecycle.instanceId && runtimeLifecycle.instanceId !== payload.instance_id;
        var operation = (payload.operations || [])[0];
        if (operation && operation.phase === 'completed' && operation.expected_new_instance_id !== payload.instance_id) throw new Error('服务实例身份尚未核实');
        runtimeLifecycle.instanceId = payload.instance_id;
        runtimeLifecycle.offlineAt = 0;
        runtimeLifecycle.serverDraining = !!payload.draining;
        runtimeLifecycle.supervisorUnavailable = payload.restart_available === false && operation
            && ['authorized','checkpointed','draining','stopping','starting','recovering'].includes(operation.phase);
        if (operation) acceptRuntimeLifecycleOperation(operation);
        if (changed && payload.ready) {
            if (typeof reconcileRunStateFromServer === 'function') void reconcileRunStateFromServer({silent:true});
            if (typeof currentSessionId !== 'undefined' && currentSessionId && typeof switchSession === 'function') void switchSession(currentSessionId,{forceReload:true});
        }
    } catch(_) {
        if (runtimeLifecycle.operation && runtimeLifecycleIsBlocked() && !runtimeLifecycle.offlineAt) runtimeLifecycle.offlineAt = Date.now();
    } finally {
        runtimeLifecycle.busy = false; renderRuntimeLifecycle(); clearTimeout(runtimeLifecycle.timer);
        runtimeLifecycle.timer = setTimeout(refreshRuntimeLifecycle,runtimeLifecycleIsBlocked() ? 1000 : (document.hidden ? 8000 : 3000));
    }
}
function initRuntimeLifecycle() {
    try {
        var saved = JSON.parse(sessionStorage.getItem(runtimeLifecycleStorageKey()) || 'null');
        if (saved && Date.now()/1000 - Number(saved.created_at) < 86400) acceptRuntimeLifecycleOperation(saved);
    } catch(_) { /* no saved request */ }
    if (window.sugarAgentDesktop && window.sugarAgentDesktop.onLifecycleStatus) {
        window.sugarAgentDesktop.onLifecycleStatus(function(operation) {
            if (operation && operation.phase === 'completed') void refreshRuntimeLifecycle();
            else acceptRuntimeLifecycleOperation(operation);
        });
    }
    window.addEventListener('online',function() { void refreshRuntimeLifecycle(); });
    void refreshRuntimeLifecycle();
}
