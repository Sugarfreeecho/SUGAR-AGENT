/**
 * Tab-type registration: what a type IS and how an address resolves to one.
 *
 * A registration is purely static — which addresses the type recognizes, how it
 * ranks against other types that recognize the same one, what the tab chip
 * says, and which element renders its body. Nothing here is per-tab or
 * per-session: the body renderer receives the tab record and the host context
 * and returns an element; everything else about a body (its stream, its scroll)
 * belongs to the embedder's renderer for that kind.
 *
 * Address recognition follows the dsh/VS Code editor resolver shape: a glob
 * declaration narrows the candidates, an optional `canOpen` predicate vetoes,
 * and the survivors rank by priority band, then by matched-pattern length, then
 * by registration order. Addresses are `myagent-resource://<type>/…` URIs; a
 * pattern containing `:` matches the whole address, one without matches the
 * path at any depth.
 *
 * Three bands, highest first:
 *   - 'extension' — a type from outside the product; a type that declares
 *     nothing is one of these, exactly as in VS Code;
 *   - 'builtin'   — the ordinary band for types shipped with the product;
 *   - 'fallback'  — plain-content viewers that anything more specific beats.
 */

/** Rank of each band, highest first. */
const DOCK_TAB_BAND_RANKS = { extension: 3, builtin: 2, fallback: 1 };

/** The band a definition that names none is in. */
const DOCK_TAB_DEFAULT_BAND = 'extension';

/**
 * Compile one declared glob into the test the router runs. `**` crosses
 * separators, `*` does not, `?` matches one character, and the whole match is
 * anchored the way an editor resolver globs an address.
 * @param {string} pattern The declared pattern.
 * @returns {Function} `(address) => boolean`.
 */
function dockCompileGlob(pattern) {
    let source = '';
    const text = String(pattern);
    for (let i = 0; i < text.length; i += 1) {
        const ch = text[i];
        if (ch === '*') {
            if (text[i + 1] === '*') {
                source += '.*';
                i += 1;
            } else {
                source += '[^/]*';
            }
        } else if (ch === '?') {
            source += '[^/]';
        } else if ('\\^$.|+()[]{}'.indexOf(ch) >= 0) {
            source += '\\' + ch;
        } else {
            source += ch;
        }
    }
    const re = new RegExp('^' + source + '$', 'i');
    return (address) => re.test(String(address));
}

/** The address's URI path, or undefined when it is not a URI. */
function dockAddressPath(address) {
    const text = String(address);
    const match = /^[a-z][a-z0-9+.-]*:\/\/[^/]*(\/.*)?$/i.exec(text);
    if (!match) return undefined;
    return match[1] || '';
}

/**
 * One registry of tab types. Registration order is part of the contract: it
 * breaks ties between types that recognize an address equally well.
 */
class DockTabRegistry {
    constructor() {
        this.byKind = new Map();
        this.byId = new Map();
        this.bodies = new Map();
        this.registrations = 0;
        this.listeners = [];
    }

    /**
     * Register one tab type.
     * @param {object} definition `{ id, kind, patterns?, priority?, canOpen?, title, body? }`.
     * @returns {Function} idempotent disposer.
     * @throws when the id is taken or the kind is already held in a way this one cannot coexist with.
     */
    register(definition) {
        if (!definition || !definition.id || !definition.kind) {
            throw new Error('dock: a tab type needs an id and a kind');
        }
        const id = String(definition.id);
        const kind = String(definition.kind);
        const band = definition.priority === undefined ? DOCK_TAB_DEFAULT_BAND : definition.priority;
        if (!DOCK_TAB_BAND_RANKS[band]) throw new Error('dock: unknown tab priority "' + band + '"');
        if (this.byId.has(id)) throw new Error('dock: tab type id "' + id + '" is already registered');
        const held = this.byKind.get(kind);
        if (held !== undefined && !this.canCoexist(held, band)) {
            throw new Error('dock: tab kind "' + kind + '" is already registered (' + held.inForce.band + ')');
        }
        this.registrations += 1;
        const entry = {
            definition: definition,
            band: band,
            patterns: (definition.patterns || []).map((pattern) => ({ pattern: pattern, test: dockCompileGlob(pattern) })),
            order: this.registrations,
        };
        this.byId.set(id, entry);
        this.enter(kind, entry);
        if (typeof definition.body === 'function') this.bodies.set(kind, definition.body);
        this.notify();
        return () => {
            if (this.byId.get(id) !== entry) return;
            this.byId.delete(id);
            this.leave(kind, entry);
            this.bodies.delete(kind);
            this.notify();
        };
    }

    /** Whether a band may join a held kind: an extension and a builtin pair once; a fallback shares with nothing. */
    canCoexist(slot, band) {
        return band !== 'fallback' && slot.inForce.band !== 'fallback' && slot.inForce.band !== band && slot.shadowed === undefined;
    }

    /** Add a registration to its kind's slot, the higher band in force. */
    enter(kind, entry) {
        const held = this.byKind.get(kind);
        if (held === undefined) {
            this.byKind.set(kind, { inForce: entry, shadowed: undefined });
            return;
        }
        if (DOCK_TAB_BAND_RANKS[entry.band] > DOCK_TAB_BAND_RANKS[held.inForce.band]) {
            held.shadowed = held.inForce;
            held.inForce = entry;
        } else {
            held.shadowed = entry;
        }
    }

    /** Remove a registration from its kind's slot: a shadowed builtin resumes, an emptied kind is freed. */
    leave(kind, entry) {
        const slot = this.byKind.get(kind);
        if (!slot) return;
        if (slot.inForce !== entry) {
            slot.shadowed = undefined;
        } else if (slot.shadowed === undefined) {
            this.byKind.delete(kind);
        } else {
            slot.inForce = slot.shadowed;
            slot.shadowed = undefined;
        }
    }

    /** Registered types in registration order. @returns {object[]} */
    entries() {
        const out = [];
        for (const slot of this.byKind.values()) out.push(slot.inForce);
        out.sort((left, right) => left.order - right.order);
        return out.map((entry) => entry.definition);
    }

    /** The type in force for a kind, or undefined. */
    get(kind) {
        const slot = this.byKind.get(String(kind));
        return slot === undefined ? undefined : slot.inForce.definition;
    }

    /** The body renderer registered for a kind, or undefined. */
    bodyFor(kind) {
        return this.bodies.get(String(kind));
    }

    /**
     * Every type that would open an address, best first.
     * Ranked by priority band, then by the length of the pattern that matched,
     * then by registration order. Types whose `canOpen` vetoes are absent.
     */
    candidates(address) {
        const ranked = [];
        for (const slot of this.byKind.values()) {
            const entry = slot.inForce;
            let length = -1;
            for (let i = 0; i < entry.patterns.length; i += 1) {
                const matcher = entry.patterns[i];
                if (matcher.test(address) && matcher.pattern.length > length) length = matcher.pattern.length;
            }
            if (length < 0) continue;
            const definition = entry.definition;
            if (definition.canOpen && !definition.canOpen(address)) continue;
            ranked.push({ definition: definition, rank: DOCK_TAB_BAND_RANKS[entry.band], length: length, order: entry.order });
        }
        ranked.sort((left, right) => right.rank - left.rank || right.length - left.length || left.order - right.order);
        return ranked.map((entry) => entry.definition);
    }

    /**
     * Decide which type opens an address, and as what.
     * @param {string} address A `myagent-resource://<type>/…` address.
     * @param {string} [kind] A type named by the caller, overriding the ranking.
     * @returns {{kind:string,contentId:string,title:string}}
     * @throws when nothing registered will open it — a wiring mistake, not a user error.
     */
    claim(address, kind) {
        if (kind !== undefined) {
            const definition = this.get(kind);
            if (!definition) throw new Error('dock: no tab type is registered as "' + kind + '"');
            if (definition.canOpen && !definition.canOpen(address)) throw new Error('dock: tab type "' + kind + '" refuses "' + address + '"');
            return { kind: definition.kind, contentId: address, title: dockTitleOf(definition, address) };
        }
        const candidates = this.candidates(address);
        if (candidates.length === 0) throw new Error('dock: no registered tab type claims "' + address + '"');
        return { kind: candidates[0].kind, contentId: address, title: dockTitleOf(candidates[0], address) };
    }

    /** Observe low-frequency registry changes. */
    subscribe(listener) {
        this.listeners.push(listener);
        return () => {
            const index = this.listeners.indexOf(listener);
            if (index >= 0) this.listeners.splice(index, 1);
        };
    }

    notify() {
        const listeners = this.listeners.slice();
        for (let i = 0; i < listeners.length; i += 1) listeners[i]();
    }
}

/** The title a definition gives an address, read again on every use so a language change needs no re-registration. */
function dockTitleOf(definition, address) {
    const title = typeof definition.title === 'function' ? definition.title(address) : definition.title;
    return String(title === undefined || title === null ? address : title);
}

/** The product's page address for a kind: what makes a page tab's identity its kind. */
function dockPageAddress(kind) {
    return 'myagent-page://' + String(kind);
}

/** The one tab-type registry the embedder fills. */
const dockTabRegistry = new DockTabRegistry();
