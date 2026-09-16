/**
 * 子代理只读编辑器占位 + 续接提示（dsh 的 `SubagentReadOnlyComposer` 与
 * 「结果未纳入父回答」提示的 MyAgent 载体）。
 *
 * 编辑器三态由 subagentUiDecisions 判定，本模块只负责呈现：
 *   - read-only：在输入区上方插入一条只读说明，并锁死输入/发送；
 *   - locked-stop：插入说明但保留发送按钮可作 Stop；
 *   - writable / none：移除占位，恢复普通输入。
 *
 * 续接提示：父会话存在"已结束且结果未纳入父回答"的子代理时，在输入区上方显示
 * 一条轻量提示，点击调用既有的 startContinueAfterSubagents()（能力未删除，只换载体）。
 */
var subagentComposerUi = (function () {
    var READONLY_ID = 'subagent-composer-readonly';
    var CONTINUE_ID = 'subagent-continue-hint';
    var inputWasDisabled = null;
    // slot chain 选举：编辑器座位的竞争者（当前仅本模块一个实现）
    var SLOT_NAME = 'conversation.composer';
    var chainDisposer = null;

    /** 取得（或惰性建立）slot 注册表引用。 */
    function slots() {
        return (typeof uiSlots !== 'undefined' && uiSlots) ? uiSlots : null;
    }

    /**
     * 把编辑器接管声明为一个 chain 座位：竞争者是「只读占位」与「不接管」。
     * 按 dsh 的 electChain 语义，select() 返回非空即赢得选举；这里由本模块
     * 单独实现，但走同一套注册/选举机制，便于后续增加第二个竞争者。
     */
    function registerComposerSeat() {
        var registry = slots();
        if (!registry || chainDisposer) return false;
        if (!registry.isDeclared(SLOT_NAME)) {
            registry.declareSlot(SLOT_NAME, { kind: 'chain', owner: 'conversation' });
        }
        chainDisposer = registry.register({
            name: SLOT_NAME,
            priority: -10,
            select: function (owner) {
                var decisionsRef = decisions();
                if (!decisionsRef) return null;
                var decision = (owner && owner.decision) || null;
                if (!decision || !decisionsRef.shouldRenderReadOnlyComposer(decision)) return null;
                return { reason: decision.reason, mode: decision.mode };
            },
        }, 'ui-subagent');
        return true;
    }

    /** 走 chain 选举决定当前编辑器是否被接管（返回 matched 或 null）。 */
    function electComposerSeat(decision) {
        var registry = slots();
        if (!registry) return null;
        if (!registry.isDeclared(SLOT_NAME)) registerComposerSeat();
        return registry.electChain(SLOT_NAME, { decision: decision });
    }

    function decisions() {
        return (typeof subagentUiDecisions !== 'undefined' && subagentUiDecisions) ? subagentUiDecisions : null;
    }

    function addressing() {
        return (typeof subagentAddressing !== 'undefined' && subagentAddressing) ? subagentAddressing : null;
    }

    function store() {
        return (typeof subagentCatalogStore !== 'undefined' && subagentCatalogStore) ? subagentCatalogStore : null;
    }

    function escapeText(value) {
        var s = String(value == null ? '' : value);
        if (typeof escapeHtml === 'function') return escapeHtml(s);
        return s.replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function panelInner() {
        return document.querySelector('.panel-inner');
    }

    function composerRow() {
        return document.querySelector('.composer-row');
    }

    // ── 编辑器三态 ──────────────────────────────────────────────────────────
    /** 由当前寻址状态推导编辑器三态决策。 */
    function resolveEditorDecision() {
        var decisionsRef = decisions();
        var addrRef = addressing();
        var storeRef = store();
        if (!decisionsRef) return { mode: 'none', reason: '', canStop: false, canWrite: true };
        var top = addrRef ? addrRef.current() : null;
        if (!top) return decisionsRef.decideEditorState({ addressing: null });
        var entry = null;
        if (storeRef) {
            var entries = storeRef.entriesOf(top.parentSessionId) || [];
            for (var i = 0; i < entries.length; i += 1) {
                if (!entries[i].diagnostic && entries[i].childId === top.childSessionId) { entry = entries[i]; break; }
            }
        }
        var parentAvailable = true;
        if (typeof sessionStore !== 'undefined' && sessionStore && sessionStore.get) {
            var parent = sessionStore.get(top.parentSessionId);
            if (parent && parent.stream_active === false && parent.run_active === false) parentAvailable = true;
        }
        return decisionsRef.decideEditorState({
            addressing: top,
            entry: entry,
            parentAvailable: parentAvailable,
        });
    }

    /** 渲染（或移除）只读占位，并按决策禁用输入。 */
    function syncComposer(decisionOverride) {
        var decisionsRef = decisions();
        var row = composerRow();
        if (!decisionsRef || !row) return;
        var decision = decisionOverride || resolveEditorDecision();
        // 走 slot chain 选举：只有赢得选座的竞争者才接管编辑器
        var elected = electComposerSeat(decision);
        var existing = document.getElementById(READONLY_ID);
        if (elected) {
            var text = decisionsRef.readOnlyReasonText(decision);
            if (!existing) {
                existing = document.createElement('div');
                existing.id = READONLY_ID;
                existing.className = 'subagent-readonly-composer';
                existing.setAttribute('role', 'status');
                row.parentNode.insertBefore(existing, row);
                if (typeof initUiHoverTips === 'function') initUiHoverTips(existing);
            }
            if (existing.textContent !== text) existing.textContent = text;
            existing.hidden = false;
        } else if (existing) {
            existing.remove();
        }
        disableComposerInput(decisionsRef.shouldDisableInput(decision));
    }

    /** 只读/锁定时禁用输入与发送；恢复时还原（不覆盖其它原因造成的禁用）。 */
    function disableComposerInput(disabled) {
        var input = document.getElementById('message-input');
        var send = document.getElementById('send-btn');
        if (disabled) {
            if (inputWasDisabled === null) {
                inputWasDisabled = {
                    input: !!(input && input.disabled),
                    send: !!(send && send.disabled),
                };
            }
            if (input) input.disabled = true;
            if (send) send.disabled = true;
        } else if (inputWasDisabled !== null) {
            if (input && !inputWasDisabled.input) input.disabled = false;
            if (send && !inputWasDisabled.send) send.disabled = false;
            inputWasDisabled = null;
        }
    }

    // ── 续接提示 ────────────────────────────────────────────────────────────
    /** 渲染（或移除）续接提示。 */
    function syncContinueHint(facts) {
        var decisionsRef = decisions();
        var row = composerRow();
        if (!decisionsRef || !row) return;
        var existing = document.getElementById(CONTINUE_ID);
        var decision = decisionsRef.decideContinuationPrompt(facts || {});
        if (!decision.show) {
            if (existing) existing.remove();
            return;
        }
        if (!existing) {
            existing = document.createElement('div');
            existing.id = CONTINUE_ID;
            existing.className = 'subagent-continue-hint';
            existing.setAttribute('role', 'status');
            var msgEl = document.createElement('span');
            msgEl.className = 'subagent-continue-hint-msg';
            var btnEl = document.createElement('button');
            btnEl.type = 'button';
            btnEl.className = 'subagent-continue-hint-btn';
            btnEl.textContent = '继续综合子任务';
            existing.appendChild(msgEl);
            existing.appendChild(btnEl);
            btnEl.addEventListener('click', function (event) {
                event.preventDefault();
                onContinueClick();
            });
            row.parentNode.insertBefore(existing, row);
            if (typeof initUiHoverTips === 'function') initUiHoverTips(existing);
        }
        var count = Number((facts && facts.pendingCount) || 0);
        var msg = existing.querySelector ? existing.querySelector('.subagent-continue-hint-msg') : null;
        var text = count + ' 个子任务结果尚未纳入上方回答，点击补充综合。';
        if (msg && msg.textContent !== text) msg.textContent = text;
        existing.hidden = false;
    }

    function onContinueClick() {
        var sid = '';
        try {
            if (typeof currentSessionId !== 'undefined' && currentSessionId) sid = String(currentSessionId);
        } catch (e) { sid = ''; }
        if (!sid) return;
        if (typeof startContinueAfterSubagents === 'function') {
            void startContinueAfterSubagents(sid);
        }
    }

    function removeContinueHint() {
        var existing = document.getElementById(CONTINUE_ID);
        if (existing) existing.remove();
    }

    function resetForTests() {
        inputWasDisabled = null;
        if (chainDisposer) {
            try { chainDisposer(); } catch (e) { /* ignore */ }
            chainDisposer = null;
        }
    }

    /**
     * 依据会话摘要同步续接提示。
     * 摘要字段（来自 GET /sessions/{id}?include_subagents=true）：
     *   subagent_pending_continue / subagent_running / subagent_can_continue /
     *   subagent_continuation { state, pending_count, reason }
     * 仅在父会话（未寻址子会话）且当前会话就是该会话时展示。
     */
    function syncFromSessionSummary(sessionId, summary) {
        if (!summary || typeof summary !== 'object') return;
        var current = '';
        try {
            if (typeof currentSessionId !== 'undefined' && currentSessionId) current = String(currentSessionId);
        } catch (e) { current = ''; }
        if (!current || String(sessionId || '') !== current) return;
        var addrRef = addressing();
        if (addrRef && addrRef.isChildOpen()) {
            removeContinueHint();
            return;
        }
        var continuation = summary.subagent_continuation || null;
        var pending = Number(
            (continuation && continuation.pending_count != null ? continuation.pending_count : null)
            != null
                ? continuation.pending_count
                : (summary.subagent_pending_continue || 0)
        );
        var canContinue = summary.subagent_can_continue !== false;
        var running = Number(summary.subagent_running || 0);
        if (!canContinue) pending = 0;
        if (continuation && continuation.state === 'wait_children') pending = 0;
        syncContinueHint({ pendingCount: pending, runningCount: running });
    }

    return {
        READONLY_ID: READONLY_ID,
        CONTINUE_ID: CONTINUE_ID,
        SLOT_NAME: SLOT_NAME,
        registerComposerSeat: registerComposerSeat,
        electComposerSeat: electComposerSeat,
        resolveEditorDecision: resolveEditorDecision,
        syncComposer: syncComposer,
        disableComposerInput: disableComposerInput,
        syncContinueHint: syncContinueHint,
        syncFromSessionSummary: syncFromSessionSummary,
        removeContinueHint: removeContinueHint,
        onContinueClick: onContinueClick,
        resetForTests: resetForTests,
    };
})();
