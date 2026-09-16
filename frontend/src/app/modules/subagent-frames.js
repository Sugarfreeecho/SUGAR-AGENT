/**
 * 子代理成员帧桥接 —— 把父会话流里的子代理事件转成目录对象层的成员帧。
 *
 * 学 dsh 的纪律："不建子代理专属事件流"——成员变化复用父会话既有的 SSE
 * （带 agent_id 的事件），这里只做归一化与转交，不新增订阅、不缓存业务数据。
 *
 * 输入（父会话 SSE）：
 *   - ephemeral 事件：agent_id + llm_*_delta / tool_* → 表示该子代理正在活动；
 *   - durable 事件：subagent_start / subagent_finish → 成员增减与终态。
 */
var subagentFrames = (function () {
    var ACTIVITY_THROTTLE_MS = 1500;
    var lastActivityAt = Object.create(null);   // childId → 上次写入时间戳
    var lastActivityValue = Object.create(null); // childId → 上次写入的 activity
    var unknownStarts = Object.create(null);     // parentId → 目录尚未覆盖的 start 帧数

    function store() {
        return (typeof subagentCatalogStore !== 'undefined' && subagentCatalogStore) ? subagentCatalogStore : null;
    }

    function now() {
        return Date.now();
    }

    /**
     * 子代理活动帧：把该子代理标记为 running（节流，避免每个 token 增量都写）。
     */
    function noteSubagentActivity(childId, running) {
        var cid = String(childId || '');
        if (!cid) return false;
        var storeRef = store();
        if (!storeRef) return false;
        if (!storeRef.getAddress(cid)) return false;   // 尚未在目录中登记：等目录刷新
        var next = running !== false ? 'running' : 'inactive';
        var ts = now();
        if (lastActivityValue[cid] === next && (ts - (lastActivityAt[cid] || 0)) < ACTIVITY_THROTTLE_MS) return false;
        lastActivityValue[cid] = next;
        lastActivityAt[cid] = ts;
        return storeRef.handleSessionStatus(cid, next === 'running');
    }

    /**
     * 子代理生命周期帧：subagent_start → 成员新增；subagent_finish → 终态。
     * 后端字段：{ type, agent_id, description, subagent_type, resumed, background,
     *             ok?, result_preview?, error? }
     */
    function noteSubagentLifecycleFrame(event) {
        if (!event || typeof event !== 'object') return false;
        var type = String(event.type || '');
        var cid = String(event.agent_id || event.agentId || '').trim();
        if (!cid) return false;
        var storeRef = store();
        if (!storeRef) return false;
        var parentId = currentParentSessionId();
        if (type === 'subagent_start' || type === 'subagent_started') {
            if (!parentId) return false;
            if (storeRef.getAddress(cid)) {
                return storeRef.handleSessionStatus(cid, true);
            }
            var added = storeRef.handleSessionAdded({
                id: cid,
                parent_id: parentId,
                subagent_type: event.subagent_type || event.subagentType || '',
                description: event.description || '',
                running: true,
                status: 'running',
            });
            if (!added) {
                // 目录尚未覆盖该子代理：记下"有此会话存在子代理"作为证据，
                // 并触发一次去抖刷新（学 dsh：成员帧只做证据，权威仍来自目录）。
                unknownStarts[parentId] = (unknownStarts[parentId] || 0) + 1;
                if (typeof subagentCatalogUi !== 'undefined' && subagentCatalogUi
                    && typeof subagentCatalogUi.noteUnknownChildEvidence === 'function') {
                    subagentCatalogUi.noteUnknownChildEvidence(parentId);
                }
            }
            return true;
        }
        if (type === 'subagent_finish' || type === 'subagent_finished') {
            lastActivityValue[cid] = 'inactive';
            lastActivityAt[cid] = now();
            return storeRef.handleSessionStatus(cid, false);
        }
        return false;
    }

    /** 当前父会话 id（子代理事件只会出现在父会话的流里）。 */
    function currentParentSessionId() {
        var sid = '';
        try {
            if (typeof currentSessionId !== 'undefined' && currentSessionId) sid = String(currentSessionId);
        } catch (e) { sid = ''; }
        if (!sid && typeof sessionStore !== 'undefined' && sessionStore && sessionStore.currentSessionId) {
            sid = String(sessionStore.currentSessionId);
        }
        if (!sid) return '';
        // 若当前正寻址在某个子会话上，父会话是它的直接父
        if (typeof subagentAddressing !== 'undefined' && subagentAddressing && subagentAddressing.isChildOpen()) {
            var top = subagentAddressing.current();
            if (top && top.parentSessionId) return String(top.parentSessionId);
        }
        return sid;
    }

    function resetForTests() {
        lastActivityAt = Object.create(null);
        lastActivityValue = Object.create(null);
        unknownStarts = Object.create(null);
    }

    /** 某父会话是否存在"目录尚未覆盖的子代理"证据（供触发器显示与刷新）。 */
    function hasUnknownChildEvidence(parentId) {
        return !!unknownStarts[String(parentId || '')];
    }

    function clearUnknownChildEvidence(parentId) {
        delete unknownStarts[String(parentId || '')];
    }

    return {
        ACTIVITY_THROTTLE_MS: ACTIVITY_THROTTLE_MS,
        noteSubagentActivity: noteSubagentActivity,
        noteSubagentLifecycleFrame: noteSubagentLifecycleFrame,
        currentParentSessionId: currentParentSessionId,
        hasUnknownChildEvidence: hasUnknownChildEvidence,
        clearUnknownChildEvidence: clearUnknownChildEvidence,
        resetForTests: resetForTests,
    };
})();
