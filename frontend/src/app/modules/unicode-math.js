/**
 * Unicode math conversion for the Final card.
 *
 * Model answers routinely contain LaTeX math (`$\alpha^2$`, `\[x=\frac{a}{b}\]`)
 * while the Final card renders Markdown only and ships no TeX engine. This module
 * rewrites MathJax-style delimiters into plain Unicode math text (`α²`, `x = a/b`)
 * so formulas read as formulas instead of raw TeX. Code is never touched, and the
 * raw Markdown kept for copy / export still carries the original TeX.
 *
 * The scan runs before Markdown parsing but emits numbered placeholders; the
 * Markdown parser therefore cannot mangle `_`, `*` or `\` inside a formula. The
 * placeholders are swapped for escaped `<span class="unicode-math">` nodes after
 * parsing (see restoreUnicodeMathPlaceholders).
 */

var UCM_PLACEHOLDER_PREFIX = '@@MYAGENT_UCMATH_';
var UCM_PLACEHOLDER_SUFFIX = '@@';

var UCM_GREEK = {
    alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', epsilon: 'ε', varepsilon: 'ε',
    zeta: 'ζ', eta: 'η', theta: 'θ', vartheta: 'ϑ', iota: 'ι', kappa: 'κ',
    lambda: 'λ', mu: 'μ', nu: 'ν', xi: 'ξ', omicron: 'ο', pi: 'π', varpi: 'ϖ',
    rho: 'ρ', varrho: 'ϱ', sigma: 'σ', varsigma: 'ς', tau: 'τ', upsilon: 'υ',
    phi: 'φ', varphi: 'φ', chi: 'χ', psi: 'ψ', omega: 'ω',
    Gamma: 'Γ', Delta: 'Δ', Theta: 'Θ', Lambda: 'Λ', Xi: 'Ξ', Pi: 'Π',
    Sigma: 'Σ', Upsilon: 'Υ', Phi: 'Φ', Psi: 'Ψ', Omega: 'Ω',
};

var UCM_SYMBOLS = {
    pm: '±', mp: '∓', times: '×', div: '÷', cdot: '⋅', ast: '∗', star: '⋆',
    circ: '∘', bullet: '∙', oplus: '⊕', ominus: '⊖', otimes: '⊗', oslash: '⊘',
    odot: '⊙', leq: '≤', le: '≤', geq: '≥', ge: '≥', neq: '≠', ne: '≠',
    approx: '≈', sim: '∼', simeq: '≃', cong: '≅', equiv: '≡', propto: '∝',
    ll: '≪', gg: '≫', prec: '≺', succ: '≻', preceq: '⪯', succeq: '⪰',
    subset: '⊂', supset: '⊃', subseteq: '⊆', supseteq: '⊇', subsetneq: '⊊',
    in: '∈', notin: '∉', ni: '∋', cup: '∪', cap: '∩', setminus: '∖',
    emptyset: '∅', varnothing: '∅', forall: '∀', exists: '∃', nexists: '∄',
    neg: '¬', lnot: '¬', land: '∧', wedge: '∧', lor: '∨', vee: '∨',
    implies: '⇒', impliedby: '⇐', iff: '⇔', therefore: '∴', because: '∵',
    perp: '⊥', parallel: '∥', mid: '∣', nmid: '∤',
    to: '→', rightarrow: '→', leftarrow: '←', leftrightarrow: '↔',
    Rightarrow: '⇒', Leftarrow: '⇐', Leftrightarrow: '⇔', mapsto: '↦',
    longrightarrow: '⟶', longleftarrow: '⟵', longleftrightarrow: '⟷',
    uparrow: '↑', downarrow: '↓', updownarrow: '↕', hookrightarrow: '↪',
    rightharpoonup: '⇀', rightleftharpoons: '⇌', nearrow: '↗', searrow: '↘',
    infty: '∞', partial: '∂', nabla: '∇', sum: '∑', prod: '∏', coprod: '∐',
    int: '∫', iint: '∬', iiint: '∭', oint: '∮', angle: '∠', measuredangle: '∡',
    triangle: '△', square: '□', blacksquare: '■', checkmark: '✓', degree: '°',
    prime: '′', ell: 'ℓ', hbar: 'ℏ', Re: 'ℜ', Im: 'ℑ', aleph: 'ℵ', wp: '℘',
    imath: 'ı', jmath: 'ȷ', dots: '…', ldots: '…', cdots: '⋯', vdots: '⋮',
    ddots: '⋱', dagger: '†', ddagger: '‡', sect: '§', P: '¶', copyright: '©',
    pounds: '£', euro: '€', colon: ':', lbrace: '{', rbrace: '}',
    langle: '⟨', rangle: '⟩', lceil: '⌈', rceil: '⌉', lfloor: '⌊', rfloor: '⌋',
    vert: '|', Vert: '‖', bigcup: '⋃', bigcap: '⋂', bigoplus: '⨁',
    bigotimes: '⨂', bigvee: '⋁', bigwedge: '⋀', bigsqcup: '⨆', bigodot: '⨀',
    top: '⊤', bot: '⊥', vdash: '⊢', models: '⊨', doteq: '≐', asymp: '≍',
    leftarrowtail: '↢', rightarrowtail: '↣', twoheadrightarrow: '↠',
};

var UCM_FUNCTIONS = {
    sin: 1, cos: 1, tan: 1, cot: 1, sec: 1, csc: 1, arcsin: 1, arccos: 1,
    arctan: 1, sinh: 1, cosh: 1, tanh: 1, coth: 1, log: 1, ln: 1, lg: 1,
    exp: 1, lim: 1, liminf: 1, limsup: 1, max: 1, min: 1, sup: 1, inf: 1,
    det: 1, dim: 1, ker: 1, hom: 1, deg: 1, gcd: 1, Pr: 1, arg: 1, mod: 1,
    bmod: 1,
};

var UCM_SUP = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶',
    '7': '⁷', '8': '⁸', '9': '⁹', '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽',
    ')': '⁾', 'a': 'ᵃ', 'b': 'ᵇ', 'c': 'ᶜ', 'd': 'ᵈ', 'e': 'ᵉ', 'f': 'ᶠ',
    'g': 'ᵍ', 'h': 'ʰ', 'i': 'ⁱ', 'j': 'ʲ', 'k': 'ᵏ', 'l': 'ˡ', 'm': 'ᵐ',
    'n': 'ⁿ', 'o': 'ᵒ', 'p': 'ᵖ', 'r': 'ʳ', 's': 'ˢ', 't': 'ᵗ', 'u': 'ᵘ',
    'v': 'ᵛ', 'w': 'ʷ', 'x': 'ˣ', 'y': 'ʸ', 'z': 'ᶻ', 'A': 'ᴬ', 'B': 'ᴮ',
    'D': 'ᴰ', 'E': 'ᴱ', 'G': 'ᴳ', 'H': 'ᴴ', 'I': 'ᴵ', 'J': 'ᴶ', 'K': 'ᴷ',
    'L': 'ᴸ', 'M': 'ᴹ', 'N': 'ᴺ', 'O': 'ᴼ', 'P': 'ᴾ', 'R': 'ᴿ', 'T': 'ᵀ',
    'U': 'ᵁ', 'V': 'ⱽ', 'W': 'ᵂ',
};

var UCM_SUB = {
    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆',
    '7': '₇', '8': '₈', '9': '₉', '+': '₊', '-': '₋', '=': '₌', '(': '₍',
    ')': '₎', 'a': 'ₐ', 'e': 'ₑ', 'h': 'ₕ', 'i': 'ᵢ', 'j': 'ⱼ', 'k': 'ₖ',
    'l': 'ₗ', 'm': 'ₘ', 'n': 'ₙ', 'o': 'ₒ', 'p': 'ₚ', 'r': 'ᵣ', 's': 'ₛ',
    't': 'ₜ', 'u': 'ᵤ', 'v': 'ᵥ', 'x': 'ₓ', 'β': 'ᵦ', 'γ': 'ᵧ', 'ρ': 'ᵨ',
    'φ': 'ᵩ', 'χ': 'ᵪ',
};

var UCM_BOLD_UPPER = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
var UCM_BOLD_LOWER = 'abcdefghijklmnopqrstuvwxyz';
var UCM_BOLD_DIGIT = '0123456789';

var UCM_SCRIPT_UPPER = '𝒜ℬ𝒞𝒟ℰℱ𝒢ℋℐ𝒥𝒦ℒℳ𝒩𝒪𝒫𝒬ℛ𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵';
var UCM_SCRIPT_LOWER = '𝒶𝒷𝒸𝒹ℯ𝒻ℊ𝒽𝒾𝒿𝓀𝓁𝓂𝓃ℴ𝓅𝓆𝓇𝓈𝓉𝓊𝓋𝓌𝓍𝓎𝓏';
var UCM_SCRIPT_UPPER_CHARS = Array.from(UCM_SCRIPT_UPPER);
var UCM_SCRIPT_LOWER_CHARS = Array.from(UCM_SCRIPT_LOWER);
var UCM_DOUBLE_UPPER_CHARS = Array.from('𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ');
var UCM_DOUBLE_LOWER_CHARS = Array.from('𝕒𝕓𝕔𝕕𝕖𝕗𝕘𝕙𝕚𝕛𝕜𝕝𝕞𝕟𝕠𝕡𝕢𝕣𝕤𝕥𝕦𝕧𝕨𝕩𝕪𝕫');
var UCM_FRAKTUR_UPPER_CHARS = Array.from('𝔄𝔅ℭ𝔇𝔈𝔉𝔊ℌℑ𝔍𝔎𝔏𝔐𝔑𝔒𝔓𝔔ℜ𝔖𝔗𝔘𝔙𝔚𝔛𝔜ℨ');
var UCM_FRAKTUR_LOWER_CHARS = Array.from('𝔞𝔟𝔠𝔡𝔢𝔣𝔤𝔥𝔦𝔧𝔨𝔩𝔪𝔫𝔬𝔭𝔮𝔯𝔰𝔱𝔲𝔳𝔴𝔵𝔶𝔷');

var UCM_ACCENTS = {
    hat: '\u0302', widehat: '\u0302', bar: '\u0304', overline: '\u0305',
    vec: '\u20D7', dot: '\u0307', ddot: '\u0308', tilde: '\u0303',
    widetilde: '\u0303', check: '\u030C', breve: '\u0306', acute: '\u0301',
    grave: '\u0300', underline: '\u0332',
};

var UCM_ENV_OPEN = {
    matrix: '', pmatrix: '(', bmatrix: '[', Bmatrix: '{', vmatrix: '|',
    Vmatrix: '‖', cases: '{', aligned: '', align: '', alignat: '', gather: '',
    gathered: '', split: '', array: '', tabular: '', smallmatrix: '',
};

var UCM_ENV_CLOSE = {
    matrix: '', pmatrix: ')', bmatrix: ']', Bmatrix: '}', vmatrix: '|',
    Vmatrix: '‖', cases: '', aligned: '', align: '', alignat: '', gather: '',
    gathered: '', split: '', array: '', tabular: '', smallmatrix: '',
};

var UCM_DELIMITERS = {
    '(': '(', ')': ')', '[': '[', ']': ']', '|': '‖', '/': '/', '.': '',
    '{': '{', '}': '}', 'langle': '⟨', 'rangle': '⟩', 'lvert': '|', 'rvert': '|',
    'vert': '|', 'Vert': '‖', 'lVert': '‖', 'rVert': '‖', 'lfloor': '⌊',
    'rfloor': '⌋', 'lceil': '⌈', 'rceil': '⌉', 'backslash': '\\',
};

function unicodeMathEscapeHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function unicodeMathSkipSpaces(source, index) {
    var i = index;
    while (i < source.length && /\s/.test(source.charAt(i))) i += 1;
    return i;
}

function unicodeMathReadGroup(source, index) {
    var i = index;
    if (source.charAt(i) !== '{') return { body: '', next: i };
    var depth = 0;
    var body = '';
    while (i < source.length) {
        var ch = source.charAt(i);
        if (ch === '\\') {
            body += source.substr(i, 2);
            i += 2;
            continue;
        }
        if (ch === '{') {
            depth += 1;
            if (depth === 1) {
                i += 1;
                continue;
            }
            body += ch;
            i += 1;
            continue;
        }
        if (ch === '}') {
            depth -= 1;
            if (depth === 0) return { body: body, next: i + 1 };
            body += ch;
            i += 1;
            continue;
        }
        body += ch;
        i += 1;
    }
    return { body: body, next: i };
}

function unicodeMathReadOptional(source, index) {
    var i = unicodeMathSkipSpaces(source, index);
    if (source.charAt(i) !== '[') return { body: null, next: index };
    var depth = 0;
    var body = '';
    i += 1;
    while (i < source.length) {
        var ch = source.charAt(i);
        if (ch === '\\') {
            body += source.substr(i, 2);
            i += 2;
            continue;
        }
        if (ch === '[') depth += 1;
        else if (ch === ']') {
            if (depth === 0) return { body: body, next: i + 1 };
            depth -= 1;
        }
        body += ch;
        i += 1;
    }
    return { body: body, next: i };
}

function unicodeMathReadCommandName(source, index) {
    var i = index + 1;
    if (i >= source.length) return { name: '', next: i };
    var ch = source.charAt(i);
    if (/[a-zA-Z]/.test(ch)) {
        var start = i;
        while (i < source.length && /[a-zA-Z]/.test(source.charAt(i))) i += 1;
        return { name: source.slice(start, i), next: i };
    }
    return { name: ch, next: i + 1 };
}

function unicodeMathLetterForm(text, upperChars, lowerChars, digitsAt) {
    var src = String(text == null ? '' : text);
    var out = '';
    for (var i = 0; i < src.length; i += 1) {
        var ch = src.charAt(i);
        var upper = UCM_BOLD_UPPER.indexOf(ch);
        var lower = UCM_BOLD_LOWER.indexOf(ch);
        var digit = digitsAt ? UCM_BOLD_DIGIT.indexOf(ch) : -1;
        if (upper >= 0) out += upperChars[upper];
        else if (lower >= 0) out += lowerChars[lower];
        else if (digit >= 0) out += String.fromCodePoint(digitsAt + digit);
        else out += ch;
    }
    return out;
}

function unicodeMathBold(text) {
    var src = String(text == null ? '' : text);
    var out = '';
    for (var i = 0; i < src.length; i += 1) {
        var ch = src.charAt(i);
        var lower = UCM_BOLD_LOWER.indexOf(ch);
        var upper = UCM_BOLD_UPPER.indexOf(ch);
        var digit = UCM_BOLD_DIGIT.indexOf(ch);
        if (upper >= 0) out += String.fromCodePoint(0x1D400 + upper);
        else if (lower >= 0) out += String.fromCodePoint(0x1D41A + lower);
        else if (digit >= 0) out += String.fromCodePoint(0x1D7CE + digit);
        else out += ch;
    }
    return out;
}

function unicodeMathScriptCapital(text) {
    var src = String(text == null ? '' : text);
    var out = '';
    for (var i = 0; i < src.length; i += 1) {
        var ch = src.charAt(i);
        var upper = UCM_BOLD_UPPER.indexOf(ch);
        var lower = UCM_BOLD_LOWER.indexOf(ch);
        if (upper >= 0) out += UCM_SCRIPT_UPPER_CHARS[upper];
        else if (lower >= 0) out += UCM_SCRIPT_LOWER_CHARS[lower];
        else out += ch;
    }
    return out;
}

function unicodeMathScript(text, kind) {
    var body = String(text == null ? '' : text).replace(/\s+/g, '');
    if (!body) return '';
    var table = kind === 'sup' ? UCM_SUP : UCM_SUB;
    var mapped = '';
    var complete = true;
    for (var i = 0; i < body.length; i += 1) {
        var ch = body.charAt(i);
        if (table[ch] == null) {
            complete = false;
            break;
        }
        mapped += table[ch];
    }
    if (complete) return mapped;
    if (body.length === 1) return (kind === 'sup' ? '^' : '_') + body;
    return (kind === 'sup' ? '^(' : '_(') + body + ')';
}

function unicodeMathNeedsParens(text) {
    var body = String(text == null ? '' : text).trim();
    if (!body) return false;
    return /[\s+\-=<>±∓×÷·/,;:]/.test(body);
}

function unicodeMathWrap(text) {
    var body = String(text == null ? '' : text).trim();
    return unicodeMathNeedsParens(body) ? '(' + body + ')' : body;
}

function unicodeMathApplyAccent(text, mark) {
    var body = String(text == null ? '' : text);
    if (!body) return '';
    if (mark === '\u0305' || mark === '\u0332') {
        var out = '';
        for (var i = 0; i < body.length; i += 1) out += body.charAt(i) + mark;
        return out;
    }
    return body + mark;
}

function unicodeMathRenderText(source) {
    var src = String(source == null ? '' : source);
    var out = '';
    var i = 0;
    while (i < src.length) {
        var ch = src.charAt(i);
        if (ch === '\\') {
            var token = unicodeMathReadCommandName(src, i);
            var name = token.name;
            i = token.next;
            if (name === '\\') { out += '\n'; continue; }
            if (name === ',' || name === 'thinspace') { out += '\u2009'; continue; }
            if (name === ';') { out += '\u2005'; continue; }
            if (name === ':') { out += '\u2004'; continue; }
            if (name === '!') { continue; }
            if (name === ' ') { out += ' '; continue; }
            if (name === 'quad') { out += '\u2003'; continue; }
            if (name === 'qquad') { out += '\u2003\u2003'; continue; }
            if ('%$&_#{}'.indexOf(name) >= 0) { out += name; continue; }
            out += UCM_SYMBOLS[name] != null ? UCM_SYMBOLS[name] : (UCM_GREEK[name] != null ? UCM_GREEK[name] : name);
            continue;
        }
        if (ch === '~') { out += ' '; i += 1; continue; }
        if (ch === '{' || ch === '}') { i += 1; continue; }
        out += ch;
        i += 1;
    }
    return out;
}

function unicodeMathReadArgument(source, index, state) {
    var i = unicodeMathSkipSpaces(source, index);
    if (i >= source.length) return { text: '', body: null, next: i };
    if (source.charAt(i) === '{') {
        var group = unicodeMathReadGroup(source, i);
        return { text: unicodeMathRender(group.body, state), body: group.body, next: group.next };
    }
    var unit = unicodeMathReadUnit(source, i, state);
    return { text: unit.text, body: null, next: unit.next };
}

function unicodeMathRenderCommand(source, index, state) {
    var token = unicodeMathReadCommandName(source, index);
    var name = token.name;
    var i = token.next;
    if (!name) return { text: '', next: i };

    if (name === '\\') return { text: '\n', next: i };
    if (name === ',') return { text: '\u2009', next: i };
    if (name === ';') return { text: '\u2005', next: i };
    if (name === ':') return { text: '\u2004', next: i };
    if (name === '!') return { text: '', next: i };
    if (name === ' ') return { text: ' ', next: i };
    if (name === 'quad') return { text: '\u2003', next: i };
    if (name === 'qquad') return { text: '\u2003\u2003', next: i };
    if (name === 'thinspace') return { text: '\u2009', next: i };
    if (name === 'enspace') return { text: ' ', next: i };

    if ('%$&_#{}'.indexOf(name) >= 0 && name.length === 1) return { text: name, next: i };
    if (name === '|') return { text: '‖', next: i };
    if (name === 'backslash') return { text: '\\', next: i };

    if (name === 'left' || name === 'right' || name === 'middle') {
        var delimIndex = unicodeMathSkipSpaces(source, i);
        var delim = '';
        if (source.charAt(delimIndex) === '\\') {
            var delimToken = unicodeMathReadCommandName(source, delimIndex);
            delim = UCM_DELIMITERS[delimToken.name] != null ? UCM_DELIMITERS[delimToken.name] : '';
            delimIndex = delimToken.next;
        } else if (delimIndex < source.length) {
            var rawDelim = source.charAt(delimIndex);
            delim = UCM_DELIMITERS[rawDelim] != null ? UCM_DELIMITERS[rawDelim] : rawDelim;
            delimIndex += 1;
        }
        return { text: delim, next: delimIndex };
    }

    if (/^(big|Big|bigg|Bigg)(l|r|m)?$/.test(name)) return { text: '', next: i };
    if (/^(displaystyle|textstyle|scriptstyle|scriptscriptstyle|limits|nolimits|nonumber|notag)$/.test(name)) {
        return { text: '', next: i };
    }

    if (name === 'begin' || name === 'end') {
        var envArg = unicodeMathReadGroup(source, unicodeMathSkipSpaces(source, i));
        var env = envArg.body.trim();
        var next = envArg.next;
        if (env === 'array' || env === 'tabular' || env === 'alignat') {
            var spec = unicodeMathReadGroup(source, unicodeMathSkipSpaces(source, next));
            if (spec.next > next) next = spec.next;
        }
        if (name === 'begin') {
            state.env = env;
            return { text: UCM_ENV_OPEN[env] || '', next: next };
        }
        state.env = null;
        return { text: UCM_ENV_CLOSE[env] || '', next: next };
    }

    if (name === 'frac' || name === 'dfrac' || name === 'tfrac' || name === 'cfrac') {
        var numerator = unicodeMathReadArgument(source, i, state);
        var denominator = unicodeMathReadArgument(source, numerator.next, state);
        return {
            text: unicodeMathWrap(numerator.text) + '/' + unicodeMathWrap(denominator.text),
            next: denominator.next,
        };
    }

    if (name === 'binom' || name === 'dbinom' || name === 'tbinom') {
        var top = unicodeMathReadArgument(source, i, state);
        var bottom = unicodeMathReadArgument(source, top.next, state);
        return { text: 'C(' + top.text.trim() + ', ' + bottom.text.trim() + ')', next: bottom.next };
    }

    if (name === 'sqrt') {
        var option = unicodeMathReadOptional(source, i);
        var radicand = unicodeMathReadArgument(source, option.next, state);
        var rootText = unicodeMathWrap(radicand.text);
        if (option.body != null) {
            var order = unicodeMathRender(option.body, state).replace(/\s+/g, '');
            if (order === '3') return { text: '∛' + rootText, next: radicand.next };
            if (order === '4') return { text: '∜' + rootText, next: radicand.next };
            return { text: unicodeMathScript(order, 'sup') + '√' + rootText, next: radicand.next };
        }
        return { text: '√' + rootText, next: radicand.next };
    }

    if (UCM_ACCENTS[name]) {
        var accented = unicodeMathReadArgument(source, i, state);
        return { text: unicodeMathApplyAccent(accented.text, UCM_ACCENTS[name]), next: accented.next };
    }

    if (name === 'text' || name === 'textrm' || name === 'textnormal' || name === 'textup'
        || name === 'textit' || name === 'textbf' || name === 'emph' || name === 'mbox' || name === 'hbox') {
        var textArg = unicodeMathReadArgument(source, i, state);
        var textBody = textArg.body != null ? textArg.body : textArg.text;
        return { text: unicodeMathRenderText(textBody), next: textArg.next };
    }

    if (name === 'operatorname') {
        var opArg = unicodeMathReadArgument(source, i, state);
        var opBody = opArg.body != null ? opArg.body : opArg.text;
        return { text: unicodeMathRenderText(opBody), next: opArg.next };
    }

    if (name === 'mathbf') {
        var boldArg = unicodeMathReadArgument(source, i, state);
        return { text: unicodeMathBold(boldArg.text), next: boldArg.next };
    }

    if (name === 'mathbb') {
        var doubleArg = unicodeMathReadArgument(source, i, state);
        return { text: unicodeMathLetterForm(doubleArg.text, UCM_DOUBLE_UPPER_CHARS, UCM_DOUBLE_LOWER_CHARS, 0x1D7D8), next: doubleArg.next };
    }

    if (name === 'mathcal') {
        var scriptArg = unicodeMathReadArgument(source, i, state);
        return { text: unicodeMathScriptCapital(scriptArg.text), next: scriptArg.next };
    }

    if (name === 'mathfrak') {
        var frakturArg = unicodeMathReadArgument(source, i, state);
        return { text: unicodeMathLetterForm(frakturArg.text, UCM_FRAKTUR_UPPER_CHARS, UCM_FRAKTUR_LOWER_CHARS, 0), next: frakturArg.next };
    }

    if (name === 'mathrm' || name === 'mathit' || name === 'mathsf' || name === 'mathtt' || name === 'mathnormal') {
        var plainArg = unicodeMathReadArgument(source, i, state);
        return { text: plainArg.text, next: plainArg.next };
    }

    if (name === 'pmod') {
        var modArg = unicodeMathReadArgument(source, i, state);
        return { text: '  (mod ' + modArg.text.trim() + ')', next: modArg.next };
    }

    if (name === 'overset' || name === 'stackrel') {
        var overTop = unicodeMathReadArgument(source, i, state);
        var overBase = unicodeMathReadArgument(source, overTop.next, state);
        return { text: overBase.text + ' (' + overTop.text + ')', next: overBase.next };
    }

    if (name === 'underset') {
        var underBottom = unicodeMathReadArgument(source, i, state);
        var underBase = unicodeMathReadArgument(source, underBottom.next, state);
        return { text: underBase.text + ' (' + underBottom.text + ')', next: underBase.next };
    }

    if (name === 'boxed') {
        var boxedArg = unicodeMathReadArgument(source, i, state);
        return { text: boxedArg.text, next: boxedArg.next };
    }

    if (name === 'tag') {
        var tagArg = unicodeMathReadArgument(source, i, state);
        return { text: '  (' + tagArg.text.trim() + ')', next: tagArg.next };
    }

    if (name === 'label' || name === 'phantom' || name === 'hphantom' || name === 'vphantom' || name === 'hspace') {
        var skipArg = unicodeMathReadArgument(source, i, state);
        return { text: name === 'hspace' ? ' ' : '', next: skipArg.next };
    }

    if (name === 'color' || name === 'textcolor') {
        var colorArg = unicodeMathReadArgument(source, i, state);
        var colored = name === 'color'
            ? { text: '', next: colorArg.next }
            : unicodeMathReadArgument(source, colorArg.next, state);
        return { text: colored.text, next: colored.next };
    }

    if (name === 'not') {
        var negated = unicodeMathReadArgument(source, i, state);
        var negMap = { '=': '≠', '∈': '∉', '<': '≮', '>': '≯', '≤': '≰', '≥': '≱', '⊂': '⊄' };
        var negText = negMap[negated.text] || (negated.text + '\u0338');
        return { text: negText, next: negated.next };
    }

    if (UCM_FUNCTIONS[name]) return { text: name, next: i };
    if (UCM_SYMBOLS[name] != null) return { text: UCM_SYMBOLS[name], next: i };
    if (UCM_GREEK[name] != null) return { text: UCM_GREEK[name], next: i };

    return { text: name, next: i };
}

function unicodeMathReadUnit(source, index, state) {
    var i = unicodeMathSkipSpaces(source, index);
    if (i >= source.length) return { text: '', next: i };
    var ch = source.charAt(i);
    if (ch === '{') {
        var group = unicodeMathReadGroup(source, i);
        return { text: unicodeMathRender(group.body, state), next: group.next };
    }
    if (ch === '\\') return unicodeMathRenderCommand(source, i, state || {});
    if (ch === '^' || ch === '_') return { text: ch, next: i + 1 };
    return { text: ch, next: i + 1 };
}

function unicodeMathRender(source, state) {
    state = state || {};
    var src = String(source == null ? '' : source);
    var out = '';
    var i = 0;
    while (i < src.length) {
        var ch = src.charAt(i);
        if (ch === '\\') {
            var command = unicodeMathRenderCommand(src, i, state);
            out += command.text;
            i = command.next;
            continue;
        }
        if (ch === '{') {
            var group = unicodeMathReadGroup(src, i);
            out += unicodeMathRender(group.body, state);
            i = group.next;
            continue;
        }
        if (ch === '}') { i += 1; continue; }
        if (ch === '^' || ch === '_') {
            var unit = unicodeMathReadUnit(src, i + 1, state);
            while (out && (out.charAt(out.length - 1) === ' ' || out.charAt(out.length - 1) === '\u2009'
                || out.charAt(out.length - 1) === '\u2005' || out.charAt(out.length - 1) === '\u2004')) {
                out = out.slice(0, -1);
            }
            var scripted = (ch === '^' && unit.text === '∘')
                ? '°'
                : unicodeMathScript(unit.text, ch === '^' ? 'sup' : 'sub');
            if (ch === '_' && scripted.indexOf('_(') === 0
                && /(?:lim|max|min|sup|inf|log|ln|lg|det|dim|ker|hom|deg|gcd|Pr|arg)$/.test(out)) {
                scripted = scripted.slice(1);
            }
            out += scripted;
            i = unit.next;
            continue;
        }
        if (ch === '&') { out += '\u00A0\u00A0'; i += 1; continue; }
        if (ch === '~') { out += ' '; i += 1; continue; }
        if (ch === "'") {
            var primes = 0;
            while (src.charAt(i) === "'") { primes += 1; i += 1; }
            out += primes === 1 ? '′' : primes === 2 ? '″' : primes === 3 ? '‴' : new Array(primes + 1).join('′');
            continue;
        }
        if (/\s/.test(ch)) {
            i += 1;
            if (out && !/\s$/.test(out)) out += ' ';
            continue;
        }
        out += ch;
        i += 1;
    }
    return out.trim();
}

function unicodeMathConvertLatex(latex) {
    return unicodeMathRender(latex, {});
}

function unicodeMathFindClose(source, start, closer, allowNewline) {
    var i = start;
    while (i < source.length) {
        if (source.substr(i, closer.length) === closer) return i;
        var ch = source.charAt(i);
        if (ch === '\\') { i += 2; continue; }
        if (ch === '\n' && !allowNewline) return -1;
        i += 1;
    }
    return -1;
}

function unicodeMathInlineCandidate(content) {
    var body = String(content || '');
    if (!body || body.length > 200) return false;
    if (/^\s/.test(body) || /\s$/.test(body)) return false;
    if (/[\r\n]/.test(body)) return false;
    if (/^[A-Z][A-Z0-9_]*$/.test(body)) return false;
    if (/^[0-9][0-9.,:]*$/.test(body)) return false;
    var strong = /\\[a-zA-Z]+|[\^_{}=<>]|[+\-*/]\s*[A-Za-z0-9(\u0370-\u03FF]|[\u0370-\u03FF\u2200-\u22FF\u2190-\u21FF]|∑|∫|√|≤|≥|≠|≈|∞/;
    if (strong.test(body)) return true;
    return /^[A-Za-z]$/.test(body);
}

function unicodeMathLooksBalanced(body) {
    var depth = 0;
    for (var i = 0; i < body.length; i += 1) {
        var ch = body.charAt(i);
        if (ch === '\\') { i += 1; continue; }
        if (ch === '{') depth += 1;
        else if (ch === '}') {
            depth -= 1;
            if (depth < 0) return false;
        }
    }
    return depth === 0;
}

function unicodeMathPush(items, body, display) {
    if (!body) return null;
    var text = unicodeMathRender(body, {});
    if (!text) return null;
    var index = items.length;
    items.push({ text: text, display: !!display, tex: body });
    return UCM_PLACEHOLDER_PREFIX + index + UCM_PLACEHOLDER_SUFFIX;
}

/** Index of the next backtick run of the same length on this line, or -1. */
function unicodeMathFindTickRun(source, start, length) {
    var i = start;
    while (i < source.length) {
        var ch = source.charAt(i);
        if (ch === '\n') return -1;
        if (ch === '`') {
            var run = 1;
            while (source.charAt(i + run) === '`') run += 1;
            if (run === length) return i;
            i += run;
            continue;
        }
        i += 1;
    }
    return -1;
}

/**
 * Replace `$...$`, `$$...$$`, `\(...\)` and `\[...\]` with Unicode math
 * placeholders. Fenced code, inline code and escaped dollars stay untouched.
 */
function replaceMarkdownMathWithUnicode(source) {
    var src = String(source == null ? '' : source);
    var out = '';
    var items = [];
    var i = 0;
    var fence = null;
    var inlineTicks = 0;
    var lineStart = true;
    while (i < src.length) {
        if (lineStart) {
            var fenceMatch = /^[ \t]{0,3}(`{3,}|~{3,})/.exec(src.slice(i, i + 16));
            if (fenceMatch) {
                var lineEnd = src.indexOf('\n', i);
                if (lineEnd < 0) lineEnd = src.length;
                out += src.slice(i, lineEnd);
                if (fence) {
                    if (fenceMatch[1].charAt(0) === fence.marker && fenceMatch[1].length >= fence.length) fence = null;
                } else {
                    fence = { marker: fenceMatch[1].charAt(0), length: fenceMatch[1].length };
                }
                i = lineEnd;
                continue;
            }
            lineStart = false;
        }
        var ch = src.charAt(i);
        if (ch === '\n') {
            out += ch;
            i += 1;
            lineStart = true;
            continue;
        }
        if (fence) {
            out += ch;
            i += 1;
            continue;
        }
        if (ch === '`') {
            var run = 1;
            while (src.charAt(i + run) === '`') run += 1;
            if (inlineTicks) {
                out += src.slice(i, i + run);
                i += run;
                if (run === inlineTicks) inlineTicks = 0;
                continue;
            }
            // Only treat the run as a code opener when a matching run closes it
            // on the same line; a stray backtick must not hide the rest of the card.
            if (unicodeMathFindTickRun(src, i + run, run) >= 0) inlineTicks = run;
            out += src.slice(i, i + run);
            i += run;
            continue;
        }
        if (inlineTicks) {
            out += ch;
            i += 1;
            continue;
        }
        if (ch === '\\') {
            var escaped = src.charAt(i + 1);
            if (escaped === '(' || escaped === '[') {
                var closer = escaped === '(' ? '\\)' : '\\]';
                var closeAt = unicodeMathFindClose(src, i + 2, closer, true);
                if (closeAt >= 0) {
                    var inner = src.slice(i + 2, closeAt);
                    if (unicodeMathLooksBalanced(inner)) {
                        var token = unicodeMathPush(items, inner, escaped === '[');
                        if (token) {
                            out += token;
                            i = closeAt + 2;
                            continue;
                        }
                    }
                }
                out += ch;
                i += 1;
                continue;
            }
            out += src.slice(i, i + 2);
            i += 2;
            continue;
        }
        if (ch === '$') {
            if (src.substr(i, 2) === '$$') {
                var displayAt = unicodeMathFindClose(src, i + 2, '$$', true);
                if (displayAt >= 0) {
                    var displayBody = src.slice(i + 2, displayAt);
                    if (unicodeMathLooksBalanced(displayBody)) {
                        var displayToken = unicodeMathPush(items, displayBody, true);
                        if (displayToken) {
                            out += displayToken;
                            i = displayAt + 2;
                            continue;
                        }
                    }
                }
                out += '$';
                i += 1;
                continue;
            }
            var inlineAt = unicodeMathFindClose(src, i + 1, '$', false);
            if (inlineAt >= 0) {
                var inlineBody = src.slice(i + 1, inlineAt);
                if (unicodeMathInlineCandidate(inlineBody) && unicodeMathLooksBalanced(inlineBody)) {
                    var inlineToken = unicodeMathPush(items, inlineBody, false);
                    if (inlineToken) {
                        out += inlineToken;
                        i = inlineAt + 1;
                        continue;
                    }
                }
            }
            out += '$';
            i += 1;
            continue;
        }
        out += ch;
        i += 1;
    }
    return { text: out, items: items };
}

function restoreUnicodeMathPlaceholders(html, items) {
    var out = String(html == null ? '' : html);
    if (!out || !items || !items.length) return out;
    for (var i = 0; i < items.length; i += 1) {
        var token = UCM_PLACEHOLDER_PREFIX + i + UCM_PLACEHOLDER_SUFFIX;
        if (out.indexOf(token) < 0) continue;
        var item = items[i] || {};
        var body = unicodeMathEscapeHtml(item.text || '').replace(/\n/g, '<br>');
        var span = '<span class="unicode-math' + (item.display ? ' unicode-math--display' : '')
            + '" data-tex="' + unicodeMathEscapeHtml(item.tex || '') + '">' + body + '</span>';
        out = out.split(token).join(span);
    }
    return out;
}
