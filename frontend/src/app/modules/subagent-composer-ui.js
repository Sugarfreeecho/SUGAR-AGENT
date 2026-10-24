/** 子代理只读编辑器占位与输入权限；结果续跑由服务端调度。 */
var subagentComposerUi = (function () {
    var READONLY_ID = 'subagent-composer-readonly';
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

    function resetForTests() {
        inputWasDisabled = null;
        if (chainDisposer) {
            try { chainDisposer(); } catch (e) { /* ignore */ }
            chainDisposer = null;
        }
    }

    return {
        READONLY_ID: READONLY_ID,
        SLOT_NAME: SLOT_NAME,
        registerComposerSeat: registerComposerSeat,
        electComposerSeat: electComposerSeat,
        resolveEditorDecision: resolveEditorDecision,
        syncComposer: syncComposer,
        disableComposerInput: disableComposerInput,
        resetForTests: resetForTests,
    };
})();
