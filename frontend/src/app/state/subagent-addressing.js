/**
 * 子代理会话寻址 —— 让子代理会话在主对话区打开（学 dsh 的 addressed session）。
 *
 * 机制（复用既有的单主会话机制，不新造管线）：
 *   打开子会话 = （1）把父会话入栈 →（2）switchSession(childId)
 *   →（3）子会话走既有 stash/restore 与历史分页 →（4）面包屑显示「父 ← 子」+ 返回。
 *   返回父会话 = switchSession(父 id)（父会话的滚动位置由既有
 *   saveChatScrollForSession / restoreCachedSessionScrollPosition 自动恢复）。
 *
 * 与目录对象层的关系：
 *   - 地址与 mode 由 subagentCatalogStore 持有（getAddress / getSelectedAddress）；
 *   - 本模块持有"当前打开的是哪个子会话"的栈与面包屑状态，纯逻辑 + 少量 DOM。
 *
 * 后端契约（已核实）：
 *   GET /sessions/{childId}/messages 与 /history_snapshot 均可直接读子会话
 *   （子会话有独立 ui_events，路径由 _resolve_session_path 解析），因此子会话
 *   在对话区打开不需要新的后端接口。
 */
var subagentAddressing = (function () {
    var STACK = [];   // [{ parentSessionId, childSessionId, title, mode, parentTitle }]
    var SUBSCRIBERS = new Set();
    var NAVIGATION_HOOKS = [];
    var SEQ = 0;

    // 兼容全局函数缺失（例如测试环境只加载本模块）
    function callIfPresent(name, args) {
        if (typeof globalThis[name] === 'function') return globalThis[name].apply(null, args || []);
        return undefined;
    }

    function isEnabled() {
        return true;
    }

    function current() {
        return STACK.length ? STACK[STACK.length - 1] : null;
    }

    function isChildOpen() {
        return STACK.length > 0;
    }

    function depth() {
        return STACK.length;
    }

    function snapshot() {
        var top = current();
        return {
            seq: SEQ,
            open: !!top,
            depth: STACK.length,
            address: top ? {
                parentSessionId: top.parentSessionId,
                childSessionId: top.childSessionId,
                mode: top.mode,
            } : null,
            title: top ? top.title : '',
            parentTitle: top ? top.parentTitle : '',
        };
    }

    function notify() {
        SEQ += 1;
        var snap = snapshot();
        SUBSCRIBERS.forEach(function (fn) {
            try { fn(snap); } catch (e) {
                if (typeof console !== 'undefined' && console.error) console.error('[subagentAddressing] subscriber failed:', e);
            }
        });
    }

    function subscribe(fn) {
        if (typeof fn !== 'function') throw new Error('subagentAddressing.subscribe: fn must be a function');
        SUBSCRIBERS.add(fn);
        return function () { SUBSCRIBERS.delete(fn); };
    }

    function onNavigate(fn) {
        if (typeof fn === 'function') NAVIGATION_HOOKS.push(fn);
        return function () {
            var idx = NAVIGATION_HOOKS.indexOf(fn);
            if (idx >= 0) NAVIGATION_HOOKS.splice(idx, 1);
        };
    }

    function emitNavigation(info) {
        NAVIGATION_HOOKS.slice().forEach(function (fn) {
            try { fn(info); } catch (e) {
                if (typeof console !== 'undefined' && console.error) console.error('[subagentAddressing] navigation hook failed:', e);
            }
        });
    }

    function resolveTitle(childId, fallback) {
        var label = String(fallback || '').trim();
        if (label) return label;
        var entry = null;
        if (typeof subagentCatalogStore !== 'undefined' && subagentCatalogStore) {
            var addr = subagentCatalogStore.getAddress(childId);
            if (addr) {
                var parentId = addr.parentSessionId;
                var rows = subagentCatalogStore.entriesOf(parentId) || [];
                for (var i = 0; i < rows.length; i += 1) {
                    if (!rows[i].diagnostic && rows[i].childId === childId) { entry = rows[i]; break; }
                }
            }
        }
        if (entry && entry.label) return String(entry.label);
        return String(childId || '').slice(0, 12);
    }

    /**
     * 打开一个子会话（在对话区显示）。
     * @param {string} childId
     * @param {{parentSessionId?:string, title?:string, mode?:string}} [opts]
     * @returns {Promise<boolean>} 是否切换成功
     */
    async function openChild(childId, opts) {
        opts = opts || {};
        var cid = String(childId || '').trim();
        if (!cid) return false;
        var parentId = String(opts.parentSessionId || '').trim();
        var resolvedMode = String(opts.mode || '');
        if (!parentId) {
            if (typeof subagentCatalogStore !== 'undefined' && subagentCatalogStore) {
                var addr = subagentCatalogStore.getAddress(cid);
                parentId = addr ? String(addr.parentSessionId || '') : '';
            }
        }
        if (!resolvedMode && typeof subagentCatalogStore !== 'undefined' && subagentCatalogStore) {
            var addrForMode = subagentCatalogStore.getAddress(cid);
            if (addrForMode) resolvedMode = String(addrForMode.mode || '');
        }
        if (!parentId) return false;
        var parentTitle = String(opts.parentTitle || currentSessionTitleText() || '');
        STACK.push({
            parentSessionId: parentId,
            childSessionId: cid,
            title: resolveTitle(cid, opts.title),
            mode: resolvedMode,
            parentTitle: parentTitle,
        });
        notify();
        var switched = await doSwitch(cid);
        if (!switched) {
            STACK.pop();
            notify();
            return false;
        }
        emitNavigation({ kind: 'open', childSessionId: cid, parentSessionId: parentId });
        return true;
    }

    /** 返回上一层（父会话），并触发既有的镜像恢复。 */
    async function returnToParent() {
        var top = current();
        if (!top) return false;
        var parentId = top.parentSessionId;
        var childId = top.childSessionId;
        STACK.pop();
        notify();
        var switched = await doSwitch(parentId);
        emitNavigation({ kind: 'back', childSessionId: childId, parentSessionId: parentId });
        if (typeof subagentCatalogStore !== 'undefined' && subagentCatalogStore) {
            // 回到父会话后不再寻址子会话
            try { subagentCatalogStore.clearSelection(); } catch (e) { /* ignore */ }
        }
        return switched;
    }

    /** 清空寻址（如用户从侧栏切走会话时）。 */
    function reset(opts) {
        opts = opts || {};
        if (!STACK.length) return;
        STACK.length = 0;
        notify();
        if (opts.notifyStore !== false && typeof subagentCatalogStore !== 'undefined' && subagentCatalogStore) {
            try { subagentCatalogStore.clearSelection(); } catch (e) { /* ignore */ }
        }
    }

    /** 切换会话：优先走既有 switchSession（含 stash/restore），否则退化为 selectSession。 */
    async function doSwitch(sessionId) {
        try {
            if (typeof switchSession === 'function') {
                var ok = await switchSession(sessionId, { useSnapshot: true });
                return ok !== false;
            }
            if (typeof selectSession === 'function') {
                await selectSession(sessionId);
                return true;
            }
        } catch (e) {
            if (typeof console !== 'undefined' && console.error) console.error('[subagentAddressing] switch failed:', e);
            return false;
        }
        return false;
    }

    function currentSessionTitleText() {
        var br = (typeof document !== 'undefined') ? document.getElementById('breadcrumb-text') : null;
        return br ? String(br.textContent || '') : '';
    }

    function resetForTests() {
        STACK.length = 0;
        SUBSCRIBERS = new Set();
        NAVIGATION_HOOKS = [];
        SEQ = 0;
    }

    return {
        isEnabled: isEnabled,
        openChild: openChild,
        returnToParent: returnToParent,
        reset: reset,
        isChildOpen: isChildOpen,
        current: current,
        depth: depth,
        snapshot: snapshot,
        subscribe: subscribe,
        onNavigate: onNavigate,
        resetForTests: resetForTests,
    };
})();
