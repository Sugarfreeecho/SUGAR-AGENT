/**
 * 迷你 slot 注册表 —— 学 dsh `ui-slots` 的核心子集，零框架依赖。
 *
 * 纪律（与 dsh 对齐）：
 * 1. 声明即授权：任何 slot 必须由某个"宿主"在 children 表里先声明；
 *    注册未声明的 slot、或重复声明他人已声明的 slot，立刻抛错。
 * 2. 生命周期 = disposer 级联：卸载一个入口会递归收掉它声明的所有子 slot。
 * 3. 选举：chain 按 priority 升序取第一个 ctx.select() 返回非空者；
 *    同优先级重复注册 single/chain 直接抛错（防静默覆盖）。
 * 4. 失败不静默：入口抛错时调用 ctx.onError 并让位（abdicate），下一个赢家接手。
 *
 * 用法（宿主）：
 *   uiSlots.declareSlot('conversation.header.lineage', { kind: 'single', owner: 'conversation' });
 *   uiSlots.declareSlot('conversation.composer', { kind: 'chain', owner: 'conversation' });
 *   uiSlots.declareSlot('conversation.header.lineage.count', { kind: 'single', parent: 'conversation.header.lineage' });
 *
 * 用法（功能插件）：
 *   const dispose = uiSlots.register({ name: 'conversation.composer', priority: -10, select(owner) {...} }, 'my-feature');
 *   uiSlots.electChain('conversation.composer', owner);   // → { matched, entry } | null
 */
var uiSlots = (function () {
    var DECLARED = Object.create(null);   // name → { kind, owner, parent, declaredAt }
    var ENTRIES = Object.create(null);    // name → [ entry ]
    var REGISTRANTS = Object.create(null); // name → [ registrant ]
    var DECLARATION_EPOCH = 0;
    var SUBSCRIBERS = new Set();
    var SEQ = 0;

    var KINDS = ['single', 'chain'];

    var ERROR_HOOK = null;
    function setErrorHook(fn) {
        ERROR_HOOK = (typeof fn === 'function') ? fn : null;
    }
    function onError(err, entry) {
        if (ERROR_HOOK) {
            try { ERROR_HOOK(err, entry); return; } catch (e) { /* hook 自身失败不再递归 */ }
        }
        if (typeof console !== 'undefined' && console.error) {
            console.error('[ui-slots] entry failed:', entry && entry.name, err);
        }
    }

    function notify() {
        SEQ += 1;
        var snapshot = getSnapshot();
        SUBSCRIBERS.forEach(function (fn) {
            try { fn(snapshot); } catch (e) { onError(e, null); }
        });
    }

    function assertDeclared(name, kind) {
        var decl = DECLARED[name];
        if (!decl) {
            throw new Error('slot "' + name + '" is not declared (a host must declare it first)');
        }
        if (kind && decl.kind !== kind) {
            throw new Error('slot "' + name + '" is declared as "' + decl.kind + '", not "' + kind + '"');
        }
        return decl;
    }

    /**
     * 宿主声明一个 slot。父声明存在时才允许声明子 slot。
     * @param {string} name
     * @param {{kind?: 'single'|'chain', owner?: string, parent?: string}} [def]
     */
    function declareSlot(name, def) {
        name = String(name || '');
        def = def || {};
        if (!name) throw new Error('declareSlot: name is required');
        var kind = def.kind || 'single';
        if (KINDS.indexOf(kind) < 0) throw new Error('declareSlot("' + name + '"): unsupported kind "' + kind + '"');
        if (DECLARED[name]) {
            throw new Error('slot "' + name + '" is already declared'
                + (DECLARED[name].owner ? ' (by ' + DECLARED[name].owner + ')' : ''));
        }
        if (def.parent && !DECLARED[def.parent]) {
            throw new Error('declareSlot("' + name + '"): parent slot "' + def.parent + '" is not declared');
        }
        DECLARED[name] = { kind: kind, owner: def.owner ? String(def.owner) : '', parent: def.parent ? String(def.parent) : '', declaredAt: DECLARATION_EPOCH };
        DECLARATION_EPOCH += 1;
        notify();
    }

    function isDeclared(name) {
        return !!DECLARED[String(name || '')];
    }

    function declaredKind(name) {
        var decl = DECLARED[String(name || '')];
        return decl ? decl.kind : '';
    }

    function ownerOf(name) {
        var decl = DECLARED[String(name || '')];
        return decl ? decl.owner : '';
    }

    function entriesOf(name) {
        return (ENTRIES[String(name || '')] || []).filter(function (e) { return !e.abdicated; });
    }

    function registrantsOf(name) {
        return (REGISTRANTS[String(name || '')] || []).slice();
    }

    function pickWinner(entries) {
        var best = null;
        for (var i = 0; i < entries.length; i += 1) {
            var e = entries[i];
            if (e.abdicated) continue;
            if (!best || e.priority < best.priority) best = e;
        }
        return best;
    }

    function assertPriorityFree(name, priority, kind, registrant) {
        var list = ENTRIES[name] || [];
        for (var i = 0; i < list.length; i += 1) {
            if (list[i].abdicated) continue;
            if (list[i].priority === priority) {
                throw new Error('slot "' + name + '" already has a "' + kind + '" registration at priority '
                    + priority + ' (by ' + list[i].registrant + ') — use a different priority to shadow it'
                    + (registrant ? ' (registering: ' + registrant + ')' : ''));
            }
        }
    }

    /**
     * 注册一个功能入口。
     * @param {{name:string, priority?:number, select?:Function, meta?:object, children?:string[]}} def
     * @param {string} [registrant] 诊断用来源
     * @returns {Function} disposer
     */
    function register(def, registrant) {
        def = def || {};
        var name = String(def.name || '');
        if (!name) throw new Error('register: def.name is required');
        var decl = assertDeclared(name);
        var kind = decl.kind;
        var priority = Number.isFinite(Number(def.priority)) ? Number(def.priority) : 0;
        if (kind === 'single' || kind === 'chain') assertPriorityFree(name, priority, kind, registrant);
        if (kind === 'chain' && typeof def.select !== 'function') {
            throw new Error('chain slot "' + name + '" requires def.select');
        }

        // 声明子 slot（此入口存活期间有效；disposer 会级联回收）
        var declaredChildren = [];
        if (Array.isArray(def.children)) {
            def.children.forEach(function (childSpec) {
                var childName = typeof childSpec === 'string' ? childSpec : (childSpec && childSpec.name);
                if (!childName) throw new Error('register("' + name + '"): child slot needs a name');
                declareSlot(childName, {
                    kind: (childSpec && childSpec.kind) || 'single',
                    owner: registrant || name,
                    parent: name,
                });
                declaredChildren.push(childName);
            });
        }

        var entry = {
            id: 'slotentry-' + (SEQ + 1) + '-' + Math.random().toString(36).slice(2, 7),
            name: name,
            kind: kind,
            priority: priority,
            registrant: String(registrant || ''),
            select: typeof def.select === 'function' ? def.select : null,
            meta: def.meta && typeof def.meta === 'object' ? def.meta : null,
            abdicated: false,
            children: declaredChildren,
            disposed: false,
        };
        if (!ENTRIES[name]) ENTRIES[name] = [];
        ENTRIES[name].push(entry);
        if (!REGISTRANTS[name]) REGISTRANTS[name] = [];
        if (entry.registrant) REGISTRANTS[name].push(entry.registrant);
        notify();

        var disposed = false;
        return function dispose() {
            if (disposed) return;   // stale disposer 是 no-op（dsh releaseEntry 语义）
            disposed = true;
            releaseEntry(entry);
        };
    }

    function releaseEntry(entry) {
        if (!entry || entry.disposed) return;
        entry.disposed = true;
        var list = ENTRIES[entry.name];
        if (list) {
            var idx = list.indexOf(entry);
            if (idx >= 0) list.splice(idx, 1);
        }
        // 级联：该入口声明的子 slot 一并回收（含其上的注册）
        entry.children.forEach(function (childName) {
            var childEntries = ENTRIES[childName] || [];
            childEntries.slice().forEach(function (child) { releaseEntry(child); });
            delete ENTRIES[childName];
            delete DECLARED[childName];
            delete REGISTRANTS[childName];
        });
        notify();
    }

    /**
     * chain 选举：按 priority 升序调用 select(owner)，第一个非空即赢家。
     * @returns {{matched:*, entry:object}|null}
     */
    function electChain(name, owner) {
        var decl = assertDeclared(name, 'chain');
        void decl;
        var list = (ENTRIES[String(name || '')] || []).slice().sort(function (a, b) { return a.priority - b.priority; });
        for (var i = 0; i < list.length; i += 1) {
            var e = list[i];
            if (e.abdicated || !e.select) continue;
            var matched = null;
            try {
                matched = e.select(owner);
            } catch (err) {
                onError(err, e);
                continue;   // 抛错的 select 退化为"弃权"，不影响后面的赢家
            }
            if (matched !== null && matched !== undefined) return { matched: matched, entry: e };
        }
        return null;
    }

    /**
     * 入口渲染/执行失败时让位：abdicate 后下一个赢家接手。
     */
    function abdicate(name, entryId, err) {
        var list = ENTRIES[String(name || '')] || [];
        for (var i = 0; i < list.length; i += 1) {
            if (list[i].id === entryId) {
                list[i].abdicated = true;
                if (err) onError(err, list[i]);
                notify();
                return true;
            }
        }
        return false;
    }

    function subscribe(fn) {
        if (typeof fn !== 'function') throw new Error('uiSlots.subscribe: fn must be a function');
        SUBSCRIBERS.add(fn);
        return function () { SUBSCRIBERS.delete(fn); };
    }

    function getSnapshot() {
        var out = { seq: SEQ, epoch: DECLARATION_EPOCH, slots: {} };
        Object.keys(DECLARED).forEach(function (name) {
            out.slots[name] = {
                kind: DECLARED[name].kind,
                owner: DECLARED[name].owner,
                parent: DECLARED[name].parent,
                entries: entriesOf(name).map(function (e) {
                    return { id: e.id, priority: e.priority, registrant: e.registrant };
                }),
            };
        });
        return out;
    }

    /** 仅测试用：清空全部状态。 */
    function resetForTests() {
        DECLARED = Object.create(null);
        ENTRIES = Object.create(null);
        REGISTRANTS = Object.create(null);
        SUBSCRIBERS = new Set();
        SEQ = 0;
        DECLARATION_EPOCH = 0;
        ERROR_HOOK = null;
    }

    return {
        KINDS: KINDS,
        declareSlot: declareSlot,
        isDeclared: isDeclared,
        declaredKind: declaredKind,
        ownerOf: ownerOf,
        register: register,
        entriesOf: entriesOf,
        registrantsOf: registrantsOf,
        pickWinner: pickWinner,
        electChain: electChain,
        abdicate: abdicate,
        subscribe: subscribe,
        getSnapshot: getSnapshot,
        setErrorHook: setErrorHook,
        resetForTests: resetForTests,
    };
})();
