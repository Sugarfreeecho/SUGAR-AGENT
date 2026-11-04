import { Console, badge, button, count, detail, duration, time, budget as readBudget } from '/static/workflow-console.js?v=20261030-native';
import { markup } from './view.js?v=20261030-native';

export function mountConsole({ root = document, sessionId } = {}) {
    const $ = id => root.querySelector("#" + CSS.escape(id));
    const budget = id => readBudget(id, root);

    let goal = null;
    let reviewIdentity = '';
    const reasons = {
        token_budget_exhausted: 'Token 预算已耗尽，请追加预算后恢复。', manual: 'Goal 已暂停，当前任务继续执行；后续不再检查或自动续跑。',
        run_failed: '最近一次运行失败，请检查错误后恢复。', consecutive_run_failures: '连续运行失败，目标已暂停。',
        judge_parse_failures: 'Judge 结论连续解析失败，请检查模型输出。', judge_transport_failures: 'Judge 调用连续失败，请检查模型连接。',
        react_iteration_limit: '已达到 ReAct 轮次上限。',
    };
    function reset() {
        goal = null;
        reviewIdentity = '';
        $('goal-view').hidden = true;
        $('create-card').hidden = true;
        $('empty').hidden = false;
        $('empty').querySelector('h2').textContent = '选择会话以查看目标';
        root.querySelectorAll('dialog[open]').forEach(dialog => dialog.close());
        root.querySelectorAll('#workspace form').forEach(form => form.reset());
    }
    function fields(id, values) { $(id).replaceChildren(...values.map(([key, value]) => detail(key, value))); }
    function render(body) {
        const previousId = goal?.id;
        goal = body.goal?.deleted ? null : body.goal;
        if (previousId !== goal?.id) root.querySelectorAll('dialog[open]').forEach(dialog => dialog.close());
        const enabled = body.enabled !== false;
        $('empty').hidden = Boolean(goal);
        $('empty').querySelector('h2').textContent = enabled ? '此会话尚无当前目标' : 'Goal 功能未启用';
        $('create-card').hidden = !enabled || Boolean(goal && goal.status !== 'cancelled');
        $('goal-view').hidden = !goal;
        if (!goal) return;
        $('objective').textContent = goal.objective || '';
        $('goal-status').replaceChildren(badge(goal.status));
        const stage = goal.status === 'completed' ? 3 : goal.completion_request_id ? 2 : 1;
        root.querySelectorAll('[data-goal-stage]').forEach((el, index) => {
            el.dataset.state = index < stage ? 'done' : index === stage ? 'current' : 'pending';
            if (index === stage) el.setAttribute('aria-current', 'step'); else el.removeAttribute('aria-current');
        });
        $('used').textContent = count(goal.used_tokens);
        $('remaining').textContent = goal.token_budget == null ? '不限' : count(goal.remaining_tokens);
        $('continuations').textContent = count(goal.continuation_count);
        $('elapsed').textContent = duration(goal.elapsed_seconds);
        $('budget-progress').hidden = goal.token_budget == null;
        $('budget-progress').value = goal.token_budget > 0 ? Math.min(100, (goal.used_tokens || 0) / goal.token_budget * 100) : 0;
        $('budget-copy').textContent = goal.token_budget == null ? '未设置 Token 预算上限' : `Token 预算：${count(goal.used_tokens)} / ${count(goal.token_budget)}`;
        const progress = body.continuation;
        const progressText = goal.status === 'active' && progress?.label
            ? progress.label + (progress.since && progress.phase !== 'running'
                ? ` · 用时 ${duration(Math.max(0, Date.now() / 1000 - progress.since))}` : '') : '';
        const diagnostic = goal.blocked_reason || reasons[goal.pause_reason] || goal.pause_reason || (goal.completion_request_id ? '已提交完成请求，等待独立 Judge 评估。' : goal.next_retry_at ? `等待重试：${time(goal.next_retry_at)}` : '');
        $('health').textContent = [progressText, diagnostic].filter(Boolean).join(' · ');
        const actions = [];
        if (goal.status === 'active') actions.push(button('暂停目标', () => void consoleUi.action('/pause', {}, 'Goal 已暂停，当前任务继续执行')));
        if (['paused', 'blocked'].includes(goal.status)) actions.push(button('恢复目标', () => { $('resume-budget').value = ''; $('resume-dialog').showModal(); }, 'primary'));
        if (goal.status !== 'completed') actions.push(button('编辑目标', () => { $('edit-objective').value = goal.objective || ''; $('edit-dialog').showModal(); }));
        if (['active', 'paused'].includes(goal.status)) actions.push(button('取消目标', () => {
            if (confirm('取消此目标并停止自动续跑？')) void consoleUi.action('/cancel', {}, '目标已取消');
        }, 'danger'));
        actions.push(button('删除目标', () => {
            if (confirm('移除此会话的当前目标？目标历史仍保留在会话中。')) void consoleUi.action('/delete', {}, '当前目标已移除');
        }, 'danger'));
        $('goal-actions').replaceChildren(...actions);
        fields('goal-meta', [['目标 ID', goal.id], ['创建时间', time(goal.created_at)], ['最近更新', time(goal.updated_at)]]);
        $('judge-verdict').replaceChildren(badge(goal.last_judge_verdict));
        $('judge-reason').textContent = goal.last_judge_reason || '尚无 Judge 结论。模型提交完成请求后，将由独立 Judge 评估。';
        fields('judge-meta', [['审核次数', count(goal.judge_count)], ['最近审核', time(goal.last_judged_at)], ['审核模型', goal.last_judge_diagnostics?.actual_model || goal.last_judge_diagnostics?.requested_model]]);
        $('judge-raw').textContent = JSON.stringify({ diagnostics: goal.last_judge_diagnostics, raw: goal.last_judge_raw }, null, 2);
        fields('run-meta', [['总运行次数', count(goal.run_count)], ['连续失败', count(goal.consecutive_failures)], ['重复阻塞', count(goal.blocked_streak)], ['最近错误', goal.last_error], ['当前运行', goal.current_run_id], ['重试时间', time(goal.next_retry_at)]]);
        $('review-card').hidden = goal.status !== 'completed';
        // Polling must never overwrite an unsaved human review.
        if (goal.status === 'completed' && reviewIdentity !== goal.id) {
            $('review-objective').value = goal.objective || '';
            $('feedback').value = goal.review_judge_result || goal.last_judge_reason || '';
            $('review-budget').value = '';
            reviewIdentity = goal.id;
        }
        $('state').textContent = JSON.stringify(goal, null, 2);
    }
    const consoleUi = new Console({ root, sessionId, path: sid => `/sessions/${encodeURIComponent(sid)}/goal`, render, reset,
        prepare: payload => goal ? { ...payload, expected_goal_id: goal.id } : payload });

    $('create').onsubmit = async event => {
        event.preventDefault();
        try {
            await consoleUi.action('/create', { objective: $('new-objective').value.trim(), token_budget: budget('new-budget') }, '目标已创建，自动续跑已启用');
        } catch (error) { consoleUi.message(error.message, true); }
    };
    $('edit-form').onsubmit = async event => {
        event.preventDefault();
        if (await consoleUi.action('/edit', { objective: $('edit-objective').value.trim() }, '目标已更新')) $('edit-dialog').close();
    };
    $('resume-form').onsubmit = async event => {
        event.preventDefault();
        try {
            if (await consoleUi.action('/resume', { additional_budget: budget('resume-budget') }, '目标已恢复')) $('resume-dialog').close();
        } catch (error) { consoleUi.message(error.message, true); }
    };
    root.querySelectorAll('[data-review]').forEach(el => {
        el.onclick = async () => {
            if (!$('review-form').reportValidity()) return;
            try {
                await consoleUi.action('/review', { decision: el.dataset.review, objective: $('review-objective').value.trim(),
                    judge_result: $('feedback').value.trim(), additional_budget: budget('review-budget') },
                    { approve: '验收已确认，当前目标已移除', save: '审核内容已保存', continue: '反馈已提交，目标继续执行' }[el.dataset.review]);
            } catch (error) { consoleUi.message(error.message, true); }
        };
    });
    root.querySelectorAll('[data-close]').forEach(el => { el.onclick = () => $(el.dataset.close).close(); });

    return consoleUi;
}

if (document.body.dataset.console === 'goal') {
    document.querySelector('main').innerHTML = markup;
    mountConsole();
}
