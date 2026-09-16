/**
 * 子代理界面决策层（纯函数）——编辑器三态与续接提示的条件判定。
 *
 * 学 dsh 的 `selectReadOnlySubagent` 思路：把"该由谁接管编辑器"做成**纯函数**，
 * 与 DOM 无关，便于测试与复用。这里的输入是快照式事实，输出是决策。
 *
 * 编辑器三态（在子代理会话被寻址打开时）：
 *   - 'writable'       父会话可用且子会话可续接 → 正常输入（走 steer/queue）
 *   - 'locked-stop'    父会话不可用但子代理仍在运行 → 输入锁死，仅保留 Stop
 *   - 'read-only'      一次性子代理，或父不可用且已停止 → 只读说明
 *   - 'none'           未寻址（普通会话），不接管
 */
var subagentUiDecisions = (function () {
    /**
     * @param {{addressing:?object, entry:?object, parentAvailable:boolean}} facts
     *   addressing: subagentAddressing.current() 或 null
     *   entry: 目录行（含 mode / activity），可为 null
     *   parentAvailable: 父会话是否可用（可写前提）
     * @returns {{mode:string, reason:string, canStop:boolean, canWrite:boolean}}
     */
    function decideEditorState(facts) {
        facts = facts || {};
        var addressing = facts.addressing || null;
        if (!addressing) {
            return { mode: 'none', reason: '', canStop: false, canWrite: true };
        }
        var entry = facts.entry || null;
        var mode = entry && entry.mode ? String(entry.mode) : 'continuable';
        var running = !!(entry && entry.activity === 'running');
        var parentAvailable = facts.parentAvailable !== false;

        if (mode === 'one-shot') {
            return {
                mode: 'read-only',
                reason: 'one-shot',
                canStop: false,
                canWrite: false,
            };
        }
        if (parentAvailable) {
            return { mode: 'writable', reason: '', canStop: running, canWrite: true };
        }
        if (running) {
            return {
                mode: 'locked-stop',
                reason: 'parent-unavailable',
                canStop: true,
                canWrite: false,
            };
        }
        return {
            mode: 'read-only',
            reason: 'parent-unavailable',
            canStop: false,
            canWrite: false,
        };
    }

    /**
     * 是否应显示只读编辑器占位（true 时编辑器被只读说明替换）。
     */
    function shouldRenderReadOnlyComposer(decision) {
        return !!decision && decision.mode === 'read-only';
    }

    /**
     * 是否禁用输入与发送（locked-stop 与 read-only 都要禁用输入）。
     */
    function shouldDisableInput(decision) {
        return !!decision && (decision.mode === 'locked-stop' || decision.mode === 'read-only');
    }

    /**
     * 只读说明文案（中文，与既有 UI 文案风格一致）。
     */
    function readOnlyReasonText(decision) {
        if (!decision) return '';
        if (decision.reason === 'one-shot') {
            return '这是一次性子代理的执行记录，只读；如需继续工作请回到父会话另起任务。';
        }
        if (decision.reason === 'parent-unavailable') {
            return '父会话当前不可用，无法从此处继续该子代理；可返回父会话后再试。';
        }
        return '';
    }

    /**
     * 续接提示条件：父会话有"已结束但结果未纳入父回答"的子代理。
     * 输入 facts.pendingCount（服务端口径）与 running 数。
     * @returns {{show:boolean, reason:string}}
     */
    function decideContinuationPrompt(facts) {
        facts = facts || {};
        var pending = Number(facts.pendingCount || 0);
        var running = Number(facts.runningCount || 0);
        if (pending <= 0) return { show: false, reason: 'nothing-pending' };
        if (running > 0) return { show: false, reason: 'children-running' };
        return { show: true, reason: 'pending-results' };
    }

    return {
        decideEditorState: decideEditorState,
        shouldRenderReadOnlyComposer: shouldRenderReadOnlyComposer,
        shouldDisableInput: shouldDisableInput,
        readOnlyReasonText: readOnlyReasonText,
        decideContinuationPrompt: decideContinuationPrompt,
    };
})();
