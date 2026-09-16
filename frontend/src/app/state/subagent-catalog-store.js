/**
 * 子代理目录对象层（dsh 式）——纯逻辑，零 DOM、零框架、零全局 UI 依赖。
 *
 * 学 dsh 的三条纪律：
 * 1. 业务数据只在这里：地址、目录快照、成员帧修补、刷新调度。
 * 2. 对外只给「引用稳定的快照」：getSnapshot() 在事实未变时返回同一引用，
 *    消费方（未来的目录树 / 编辑器选举）通过 subscribe() 得到变更通知。
 * 3. 单飞 + 去抖 + 只刷新被消费的目录（openCatalogs），成员帧只做乐观修补，
 *    不建子代理专属事件流。
 *
 * 数据来源：GET /sessions/{parentId}/subagents?lite=1
 *   旧版节点字段：id, parent_id, subagent_type, running, ok, status, depth,
 *                description, has_final, result_preview, output_file, …
 *   Runtime V2 节点字段：task_id, parent_id, running, status, has_final, …
 *   归一化后每个健康行：
 *     { childId, parentId, activity: 'running'|'inactive', hasChildren, mode, label, depth, raw }
 *
 * 说明：MyAgent 后端目前没有 dsh 的 descriptor mode 字段，因此 mode 采用
 * 「可续接」推断规则而不是持久化描述符（见 inferMode），新 UI 应用它来选举
 * 编辑器；后续若后端补 descriptor，只需替换 inferMode 的实现。
 */
var subagentCatalogStore = (function () {
    var CATALOG_DEBOUNCE_MS = 50;
    var DEFAULT_FETCH_TIMEOUT_MS = 15000;

    var IMPL = {
        fetchJson: null,     // 注入：async (url) => json
        now: function () { return Date.now(); },
        setTimeout: null,    // 注入：浏览器 setTimeout；测试可换成手动时钟
        clearTimeout: null,
    };

    function setImplementation(patch) {
        patch = patch || {};
        ['fetchJson', 'now', 'setTimeout', 'clearTimeout'].forEach(function (key) {
            if (patch[key] !== undefined) IMPL[key] = patch[key];
        });
    }

    function defaultFetchJson(url) {
        if (typeof fetch !== 'function') return Promise.reject(new Error('fetch is unavailable'));
        return fetch(url).then(function (res) {
            if (!res || !res.ok) throw new Error('subagents request failed: ' + (res && res.status));
            return res.json();
        });
    }

    function fetchJson(url) {
        var fn = IMPL.fetchJson || defaultFetchJson;
        // 同步进入（不额外排队微任务）：单飞计数与"在途"观察点都依赖它立即开始。
        try {
            return Promise.resolve(fn(url));
        } catch (err) {
            return Promise.reject(err);
        }
    }

    function defer(fn, ms) {
        if (IMPL.setTimeout) return IMPL.setTimeout(fn, ms);
        if (typeof setTimeout === 'function') return setTimeout(fn, ms);
        fn();
        return 0;
    }

    function cancelDefer(handle) {
        if (handle == null) return;
        if (IMPL.clearTimeout) { IMPL.clearTimeout(handle); return; }
        if (typeof clearTimeout === 'function') clearTimeout(handle);
    }

    // ── 状态 ────────────────────────────────────────────────────────────────
    var STATE = null;         // 当前快照（引用稳定）
    var SUBSCRIBERS = new Set();
    var ADDRESSES = new Map();     // childId → { parentSessionId, childSessionId, mode }
    var SELECTED = null;           // 当前寻址的完整地址（含父 id）
    var INFLIGHT = new Map();      // parentId → { promise, patches: [] }
    var STALE = new Set();         // 刷新在途期间成员变化过的 parentId（尾随刷新）
    var OPEN = new Set();          // 被 UI 消费（菜单打开/被选中）的 parentId
    var TIMERS = new Map();        // parentId → 去抖 handle
    var TOKENS = new Map();        // childId → { estimated, threshold }（按需拉取，UI 指标用）
    var TOKEN_INFLIGHT = new Set(); // childId（避免重复请求）
    var TOKEN_MISSES = new Set();  // childId（取不到时不再重试）
    var READ_IDS = new Set();      // childId（已读：用户打开过该子会话）
    var READ_STORAGE_KEY = 'myagent.subagent.read.v1';
    var readLoaded = false;

    /** 惰性读取已读集合（localStorage 不可用时退化为内存态）。 */
    function ensureReadLoaded() {
        if (readLoaded) return;
        readLoaded = true;
        try {
            var raw = (typeof localStorage !== 'undefined') ? localStorage.getItem(READ_STORAGE_KEY) : null;
            if (raw) {
                var parsed = JSON.parse(raw);
                if (parsed && typeof parsed === 'object') {
                    Object.keys(parsed).forEach(function (key) {
                        if (parsed[key]) READ_IDS.add(String(key));
                    });
                }
            }
        } catch (e) { /* ignore：隐私模式等场景下仅内存态生效 */ }
    }

    function persistReadIds() {
        try {
            if (typeof localStorage === 'undefined') return;
            var out = {};
            READ_IDS.forEach(function (id) { out[id] = 1; });
            localStorage.setItem(READ_STORAGE_KEY, JSON.stringify(out));
        } catch (e) { /* ignore */ }
    }

    /** 某子代理是否已读（用户打开过它的会话）。 */
    function isSubagentRead(childId) {
        ensureReadLoaded();
        return READ_IDS.has(String(childId || ''));
    }

    /** 标记一个子代理为已读（打开子会话时调用）。 */
    function markSubagentRead(childId) {
        var cid = String(childId || '');
        if (!cid) return false;
        ensureReadLoaded();
        if (READ_IDS.has(cid)) return false;
        READ_IDS.add(cid);
        persistReadIds();
        rebuildSnapshot({});
        return true;
    }

    function initialState() {
        return {
            seq: 0,
            selected: null,
            addresses: {},
            catalogsByParent: {},
            openCatalogs: {},
            tokensByChild: {},
        };
    }

    function rebuildSnapshot(patch) {
        var prev = STATE || initialState();
        var next = {
            seq: prev.seq + 1,
            selected: patch.selected !== undefined ? patch.selected : prev.selected,
            addresses: patch.addresses !== undefined ? patch.addresses : prev.addresses,
            catalogsByParent: patch.catalogsByParent !== undefined ? patch.catalogsByParent : prev.catalogsByParent,
            openCatalogs: patch.openCatalogs !== undefined ? patch.openCatalogs : prev.openCatalogs,
            tokensByChild: patch.tokensByChild !== undefined ? patch.tokensByChild : prev.tokensByChild,
        };
        STATE = next;
        notify();
        return next;
    }

    function notify() {
        var snapshot = STATE;
        SUBSCRIBERS.forEach(function (fn) {
            try { fn(snapshot); } catch (e) {
                if (typeof console !== 'undefined' && console.error) console.error('[subagentCatalog] subscriber failed:', e);
            }
        });
    }

    function getSnapshot() {
        return STATE || (STATE = initialState());
    }

    function subscribe(fn) {
        if (typeof fn !== 'function') throw new Error('subagentCatalogStore.subscribe: fn must be a function');
        SUBSCRIBERS.add(fn);
        return function () { SUBSCRIBERS.delete(fn); };
    }

    function addressesObject() {
        var out = {};
        ADDRESSES.forEach(function (addr, childId) { out[childId] = addr; });
        return out;
    }

    function tokensObject() {
        var out = {};
        TOKENS.forEach(function (value, childId) { out[childId] = value; });
        return out;
    }

    /** 已缓存的 token 指标（未拉取时为 null）。 */
    function getTokens(childId) {
        return TOKENS.get(String(childId || '')) || null;
    }

    /**
     * 按需拉取某子代理的上下文 token 占用（UI 指标用，惰性 + 去重 + 失败不重试）。
     * @returns {Promise<object|null>}
     */
    function fetchTokens(childId) {
        var cid = String(childId || '');
        if (!cid) return Promise.resolve(null);
        if (TOKENS.has(cid)) return Promise.resolve(TOKENS.get(cid));
        if (TOKEN_INFLIGHT.has(cid) || TOKEN_MISSES.has(cid)) return Promise.resolve(null);
        TOKEN_INFLIGHT.add(cid);
        var url = '/sessions/' + encodeURIComponent(cid) + '/context_tokens';
        return fetchJson(url).then(function (data) {
            TOKEN_INFLIGHT.delete(cid);
            if (!data || data.ok === false || data.estimated == null) {
                TOKEN_MISSES.add(cid);
                return null;
            }
            var entry = {
                estimated: Number(data.estimated) || 0,
                threshold: Number(data.threshold) || 0,
            };
            TOKENS.set(cid, entry);
            rebuildSnapshot({ tokensByChild: tokensObject() });
            return entry;
        }).catch(function () {
            TOKEN_INFLIGHT.delete(cid);
            TOKEN_MISSES.add(cid);
            return null;
        });
    }

    // ── 归一化 ──────────────────────────────────────────────────────────────

    /**
     * 把后端节点归一化为目录行。健康行与诊断行分开：
     *  - 健康行：有 childId；activity 由 running 推导；mode 由可续接性推导。
     *  - 诊断行：缺 id、状态损坏；保留可读性但不可导航。
     */
    function normalizeEntry(node) {
        if (!node || typeof node !== 'object') {
            return { diagnostic: true, reason: 'corrupt', label: '', raw: node || null };
        }
        var childId = String(node.id || node.task_id || '').trim();
        if (!childId) {
            return { diagnostic: true, reason: 'corrupt', label: String(node.description || ''), raw: node };
        }
        var running = !!node.running;
        var status = String(node.status || node.task_status || '').toLowerCase();
        if (status === 'running') running = true;
        // orphaned / stale = 父进程丢失或过期，按"错误"处理（不再视为运行中）
        if (status === 'orphaned' || status === 'stale') running = false;
        var hasChildren = node.has_children != null ? !!node.has_children
            : (node.depth == null ? false : false);
        // 行的显示名优先用子代理自己的名称/描述，subagent_type 仅作最后兜底
        // （否则目录里每一行都显示成 "explore"/"generalPurpose"）。
        var label = String(
            node.name
            || node.title
            || node.description
            || node.subagent_type
            || ''
        ).trim().slice(0, 80);
        return {
            diagnostic: false,
            childId: childId,
            parentId: String(node.parent_id || '').trim(),
            activity: running ? 'running' : 'inactive',
            outcome: inferOutcome(node, running),
            hasChildren: hasChildren,
            mode: inferMode(node),
            label: label,
            depth: Number.isFinite(Number(node.depth)) ? Number(node.depth) : 0,
            startedAt: Number(node.started_at || 0) || 0,
            finishedAt: Number(node.finished_at || 0) || 0,
            updatedAt: Number(node.updated_at || 0) || 0,
            raw: node,
        };
    }

    /**
     * 结果语义（与 activity 分离，供圆点着色的"错误 / 正常完成"判定）：
     *   'running'  仍在运行/排队
     *   'failed'   报错、被中断、被取消，或完成后缺结果
     *   'ok'       正常结束
     *   'unknown'  字段不足以判定
     */
    function inferOutcome(node, running) {
        var status = String(node.status || node.task_status || '').toLowerCase();
        // 终态优先：即使 running 标志陈旧（如 interrupted 后未刷新），终态也应胜出
        if (status === 'failed' || status === 'error') return 'failed';
        if (status === 'interrupted' || status === 'cancelled' || status === 'canceled') return 'failed';
        if (status === 'orphaned' || status === 'stale') return 'failed';
        if (status === 'completed' || status === 'finished' || status === 'done') return 'ok';
        // 后端有时只在 ok/error 字段上表达结果，需先于 running 判定
        if (node.ok === false) return 'failed';
        if (node.ok === true) return 'ok';
        if (node.error) return 'failed';
        if (running) return 'running';
        if (status === 'queued' || status === 'pending') return 'running';
        return 'unknown';
    }

    /**
     * 可续接性推断（MyAgent 暂无 descriptor）：
     *  - simple / virtual 无独立会话 → one-shot（best-of-n-runner 等汇总行）；
     *  - 有独立会话目录（可通过 /sessions/{id}/messages 读）→ continuable。
     * 这里用「是否有 output_file / 是否为 virtual_task」保守判断，宁可标 one-shot。
     */
    function inferMode(node) {
        if (node && (node.virtual_task || node.virtualTask)) return 'one-shot';
        if (node && (node.source === 'legacy' || node.source === 'runtime_v2')) return 'continuable';
        return 'continuable';
    }

    function catalogSnapshotFrom(entries, parentId) {
        return {
            parentSessionId: String(parentId || ''),
            state: 'ready',
            error: null,
            entries: entries,
            fetchedAt: IMPL.now(),
        };
    }

    function catalogsObjectWith(parentId, catalog) {
        var next = Object.assign({}, getSnapshot().catalogsByParent);
        next[String(parentId)] = catalog;
        return next;
    }

    function openObjectWith(parentId, isOpen) {
        var next = Object.assign({}, getSnapshot().openCatalogs);
        if (isOpen) next[String(parentId)] = true;
        else delete next[String(parentId)];
        return next;
    }

    // ── 公开 API ────────────────────────────────────────────────────────────

    function getCatalog(parentId) {
        return getSnapshot().catalogsByParent[String(parentId || '')] || null;
    }

    function entriesOf(parentId) {
        var catalog = getCatalog(parentId);
        return catalog && Array.isArray(catalog.entries) ? catalog.entries : [];
    }

    function getSelectedAddress() {
        return getSnapshot().selected;
    }

    function getAddress(childId) {
        return ADDRESSES.get(String(childId || '')) || null;
    }

    /**
     * 选择/寻址一个子会话。地址必须来自已加载目录中的健康行（与 dsh 的
     * 「selectSubagent 只接受健康 catalog child」一致），否则返回 null 且不改状态。
     */
    function selectSubagent(childId) {
        var cid = String(childId || '');
        if (!cid) return null;
        var addr = ADDRESSES.get(cid) || null;
        if (!addr) return null;
        SELECTED = addr;
        rebuildSnapshot({ selected: addr });
        return addr;
    }

    function clearSelection() {
        if (!SELECTED) return;
        SELECTED = null;
        rebuildSnapshot({ selected: null });
    }

    /**
     * 刷新某父会话的直接目录（单飞 + 可选去抖）。
     * @param {string} parentId
     * @param {{debounce?:boolean, force?:boolean}} [opts]
     * @returns {Promise<object|null>} 目录快照
     */
    function refreshCatalogs(parentId, opts) {
        var pid = String(parentId || '');
        if (!pid) return Promise.resolve(null);
        opts = opts || {};
        if (opts.debounce) {
            var existingTimer = TIMERS.get(pid);
            if (existingTimer != null) cancelDefer(existingTimer);
            var handle = defer(function () {
                TIMERS.delete(pid);
                void refreshCatalogs(pid);
            }, Number.isFinite(Number(opts.debounceMs)) ? Number(opts.debounceMs) : CATALOG_DEBOUNCE_MS);
            TIMERS.set(pid, handle);
            return Promise.resolve(getCatalog(pid));
        }
        var inflight = INFLIGHT.get(pid);
        if (inflight) {
            if (opts.force) STALE.add(pid);   // 在途期间的强制刷新 → 结算后补一次
            return inflight.promise;
        }
        var previous = getCatalog(pid);
        rebuildSnapshot({
            catalogsByParent: catalogsObjectWith(pid, {
                parentSessionId: pid,
                state: 'loading',
                error: null,
                entries: previous ? previous.entries : [],
                fetchedAt: previous ? previous.fetchedAt : 0,
            }),
        });
        var patches = [];
        var url = '/sessions/' + encodeURIComponent(pid) + '/subagents?lite=1';
        var request;
        try {
            request = fetchJson(url);
        } catch (err) {
            request = Promise.reject(err);
        }
        var entry = { patches: patches, promise: null };
        var promise = request.then(function (data) {
                var rows = (data && Array.isArray(data.subagents)) ? data.subagents : [];
                var entries = normalizeEntries(rows);
                // 请求在途期间到达的成员帧：折入结果，避免旧响应覆盖新事实
                patches.forEach(function (patchFn) { patchFn(entries); });
                var catalog = catalogSnapshotFrom(entries, pid);
                INFLIGHT.delete(pid);
                commitCatalog(pid, catalog);
                if (STALE.delete(pid)) void refreshCatalogs(pid);
                return catalog;
            }).catch(function (err) {
                INFLIGHT.delete(pid);
                var prev = getCatalog(pid);
                commitCatalog(pid, {
                    parentSessionId: pid,
                    state: 'error',
                    error: err && err.message ? String(err.message) : String(err),
                    entries: prev ? prev.entries : [],
                    fetchedAt: prev ? prev.fetchedAt : 0,
                });
                return null;
            });
        entry.promise = promise;
        INFLIGHT.set(pid, entry);
        return promise;
    }

    function normalizeEntries(rows) {
        var entries = [];
        rows.forEach(function (node) {
            var entry = normalizeEntry(node);
            if (entry && !entry.diagnostic && entry.parentId && !entry.childId) return;
            entries.push(entry);
        });
        return entries;
    }

    function commitCatalog(parentId, catalog) {
        var pid = String(parentId || '');
        (catalog.entries || []).forEach(function (entry) {
            if (entry.diagnostic) return;
            if (entry.parentId && entry.parentId !== pid) return;   // 只登记直接子
            ADDRESSES.set(entry.childId, {
                parentSessionId: pid,
                childSessionId: entry.childId,
                mode: entry.mode,
            });
        });
        var nextSelected = SELECTED;
        if (SELECTED && !ADDRESSES.has(SELECTED.childSessionId)) nextSelected = SELECTED;   // 保留寻址，即使目录暂无该行
        rebuildSnapshot({
            catalogsByParent: catalogsObjectWith(pid, catalog),
            addresses: addressesObject(),
            selected: nextSelected,
        });
    }

    function setCatalogOpen(parentId, isOpen) {
        var pid = String(parentId || '');
        if (!pid) return;
        var alreadyOpen = OPEN.has(pid);
        if (isOpen === alreadyOpen) return;
        if (isOpen) {
            OPEN.add(pid);
            rebuildSnapshot({ openCatalogs: openObjectWith(pid, true) });
            void refreshCatalogs(pid);        // 打开即刷新（单飞）
        } else {
            OPEN.delete(pid);
            var timer = TIMERS.get(pid);
            if (timer != null) { cancelDefer(timer); TIMERS.delete(pid); }
            rebuildSnapshot({ openCatalogs: openObjectWith(pid, false) });
        }
    }

    function isCatalogOpen(parentId) {
        return OPEN.has(String(parentId || ''));
    }

    // ── 成员帧（来自父会话流，不新建事件流） ─────────────────────────────────

    /** host/session-added 等价：已知直接子出现 → 父行 hasChildren 立即置真。 */
    function handleSessionAdded(node) {
        if (!node || typeof node !== 'object') return false;
        var childId = String(node.id || node.session_id || '').trim();
        var parentId = String(node.parent_id || node.parentSessionId || '').trim();
        if (!childId || !parentId) return false;
        return patchCatalog(parentId, function (entries) {
            var addr = ADDRESSES.get(childId);
            if (!addr) {
                ADDRESSES.set(childId, {
                    parentSessionId: parentId,
                    childSessionId: childId,
                    mode: inferMode(node),
                });
                entries.push(normalizeEntry(Object.assign({}, node, { id: childId, parent_id: parentId })));
                return true;
            }
            return false;
        }, { addresses: true });
    }

    /** host/session-removed 等价：不删行，只降级为 inactive。 */
    function handleSessionRemoved(nodeOrId) {
        var childId = String(
            (nodeOrId && typeof nodeOrId === 'object')
                ? (nodeOrId.id || nodeOrId.session_id || '')
                : (nodeOrId || '')
        ).trim();
        if (!childId) return false;
        var addr = ADDRESSES.get(childId);
        if (!addr) return false;
        return patchCatalog(addr.parentSessionId, function (entries) {
            var changed = false;
            entries.forEach(function (entry) {
                if (!entry.diagnostic && entry.childId === childId && entry.activity !== 'inactive') {
                    entry.activity = 'inactive';
                    changed = true;
                }
            });
            return changed;
        });
    }

    /** host/session-status 等价：原地更新 activity。 */
    function handleSessionStatus(nodeOrId, running) {
        var childId = String(
            (nodeOrId && typeof nodeOrId === 'object')
                ? (nodeOrId.id || nodeOrId.session_id || '')
                : (nodeOrId || '')
        ).trim();
        if (!childId) return false;
        var nextActivity = (typeof running === 'boolean')
            ? (running ? 'running' : 'inactive')
            : ((nodeOrId && nodeOrId.running) ? 'running' : 'inactive');
        var addr = ADDRESSES.get(childId);
        if (!addr) return false;
        return patchCatalog(addr.parentSessionId, function (entries) {
            var changed = false;
            entries.forEach(function (entry) {
                if (!entry.diagnostic && entry.childId === childId && entry.activity !== nextActivity) {
                    entry.activity = nextActivity;
                    changed = true;
                }
            });
            return changed;
        });
    }

    /**
     * 对某父目录做一次「乐观修补」：在途请求则记入 patch 队列，结算时折入；
     * 否则直接改当前快照。
     */
    function patchCatalog(parentId, mutate, opts) {
        var pid = String(parentId || '');
        var inflight = INFLIGHT.get(pid);
        if (inflight) {
            var applied = false;
            inflight.patches.push(function (entries) {
                applied = mutate(entries);
                return applied;
            });
            return true;   // 在途期间已登记，视为已处理
        }
        var catalog = getCatalog(pid);
        if (!catalog) {
            if (opts && opts.addresses) {
                rebuildSnapshot({ addresses: addressesObject() });
                return true;
            }
            return false;
        }
        var entries = (catalog.entries || []).map(function (entry) { return Object.assign({}, entry); });
        var changed = mutate(entries);
        if (!changed && !(opts && opts.addresses)) return false;
        commitCatalog(pid, Object.assign({}, catalog, { entries: entries }));
        return true;
    }

    /** 供测试/会话切换清理：丢弃某父目录的全部状态。 */
    function forgetParent(parentId) {
        var pid = String(parentId || '');
        INFLIGHT.delete(pid);
        STALE.delete(pid);
        OPEN.delete(pid);
        var timer = TIMERS.get(pid);
        if (timer != null) { cancelDefer(timer); TIMERS.delete(pid); }
        var nextCatalogs = Object.assign({}, getSnapshot().catalogsByParent);
        delete nextCatalogs[pid];
        (getSnapshot().addresses ? Object.keys(getSnapshot().addresses) : []).forEach(function (childId) {
            var addr = ADDRESSES.get(childId);
            if (addr && addr.parentSessionId === pid) ADDRESSES.delete(childId);
        });
        rebuildSnapshot({
            catalogsByParent: nextCatalogs,
            addresses: addressesObject(),
        });
    }

    /** 汇总：某会话的后代数与运行中数量（供标题栏计数触发器）。 */
    function summarizeDescendants(parentId) {
        var entries = entriesOf(parentId);
        var total = 0;
        var running = 0;
        entries.forEach(function (entry) {
            if (entry.diagnostic) return;
            total += 1;
            if (entry.activity === 'running') running += 1;
        });
        return { total: total, running: running };
    }

    function resetForTests() {
        STATE = null;
        SUBSCRIBERS = new Set();
        ADDRESSES = new Map();
        SELECTED = null;
        INFLIGHT = new Map();
        STALE = new Set();
        OPEN = new Set();
        TIMERS = new Map();
        TOKENS = new Map();
        TOKEN_INFLIGHT = new Set();
        TOKEN_MISSES = new Set();
        READ_IDS = new Set();
        readLoaded = false;
        IMPL.fetchJson = null;
        IMPL.setTimeout = null;
        IMPL.clearTimeout = null;
        IMPL.now = function () { return Date.now(); };
    }

    return {
        CATALOG_DEBOUNCE_MS: CATALOG_DEBOUNCE_MS,
        setImplementation: setImplementation,
        getSnapshot: getSnapshot,
        subscribe: subscribe,
        getCatalog: getCatalog,
        entriesOf: entriesOf,
        getAddress: getAddress,
        getSelectedAddress: getSelectedAddress,
        selectSubagent: selectSubagent,
        clearSelection: clearSelection,
        refreshCatalogs: refreshCatalogs,
        setCatalogOpen: setCatalogOpen,
        isCatalogOpen: isCatalogOpen,
        handleSessionAdded: handleSessionAdded,
        handleSessionRemoved: handleSessionRemoved,
        handleSessionStatus: handleSessionStatus,
        summarizeDescendants: summarizeDescendants,
        forgetParent: forgetParent,
        getTokens: getTokens,
        fetchTokens: fetchTokens,
        isSubagentRead: isSubagentRead,
        markSubagentRead: markSubagentRead,
        inferMode: inferMode,
        normalizeEntry: normalizeEntry,
        resetForTests: resetForTests,
    };
})();
