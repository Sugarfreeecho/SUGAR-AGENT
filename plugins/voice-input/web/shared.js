export function voiceText(zh, en) {
    return localStorage.getItem('myagent-language') === 'en' ? en : zh;
}

export async function voiceRequest(path, options = {}) {
    const response = await fetch('/api/speech/' + path, options);
    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const error = new Error(body.error || body.detail || 'HTTP ' + response.status);
        error.status = response.status;
        error.code = body.code;
        throw error;
    }
    return response;
}

export function splitSpeechText(text, limit = 1800) {
    // Small segments start playing sooner: the first request only covers one sentence
    // instead of an entire answer, and later segments are fetched while earlier ones play.
    const chunks = [];
    let remaining = text.replace(/\r\n/g, '\n').trim();
    if (!remaining) return chunks;
    const breaks = /[\n。！？!?；;…]/;
    while (remaining.length > limit) {
        const part = remaining.slice(0, limit);
        let split = -1;
        for (let index = part.length - 1; index >= 0; index -= 1) {
            if (breaks.test(part[index])) { split = index; break; }
        }
        // Keep a comma boundary rather than cutting a clause in half, but never return a stub.
        if (split < limit * 0.4) {
            const comma = Math.max(part.lastIndexOf('，'), part.lastIndexOf(','), part.lastIndexOf('、'));
            if (comma >= limit * 0.4) split = comma;
        }
        if (split < limit * 0.4) split = limit - 1;
        chunks.push(remaining.slice(0, split + 1).trim());
        remaining = remaining.slice(split + 1).trimStart();
    }
    if (remaining) chunks.push(remaining);
    return chunks.filter(Boolean);
}

// Pictographs and zero-width joiners carry no speech; left in, they turn into
// stray syllables or swallow the next character.
const SPEECH_NOISE = /[\u200B-\u200D\uFEFF\uFE0F\u20E3\u{1F000}-\u{1FAFF}\u{2190}-\u{21FF}\u{2300}-\u{27BF}]/gu;
const INLINE_CODE_LIMIT = 24;
// Stand-ins for spans nobody can follow by ear. They are typed so a run of file
// paths reads as "N files" rather than "N code spans", and links stay links.
const SPANS = { file: '\u0000', link: '\u0001', code: '\u0002' };
const FILE_PATTERN = /(?:^|[\\/])[^\s\\/]+\.[A-Za-z][A-Za-z0-9]{0,7}(?::\d+(?:-\d+)?)?$/;
let readParenthetical = false;

export function setSpeechOptions(options = {}) {
    if (typeof options.readParenthetical === 'boolean') readParenthetical = options.readParenthetical;
}

function inlineCode(value) {
    const text = value.trim();
    if (/^https?:\/\//i.test(text)) return SPANS.link;
    if (FILE_PATTERN.test(text)) {
        // A bare name such as chat.js is short enough to say out loud.
        return !/[\\/]/.test(text) && text.length <= INLINE_CODE_LIMIT ? text : SPANS.file;
    }
    return text.length > INLINE_CODE_LIMIT ? SPANS.code : text;
}

function spanPhrase(kind, count) {
    if (kind === 'file') {
        return count <= 1 ? voiceText('一个文件', 'a file') : voiceText(count + ' 个文件', count + ' files');
    }
    if (kind === 'link') {
        return count <= 1 ? voiceText('一个链接', 'a link') : voiceText(count + ' 个链接', count + ' links');
    }
    return count <= 1 ? voiceText('一段代码', 'a code span') : voiceText(count + ' 处代码', count + ' code spans');
}

function collapseSpans(text) {
    let out = text;
    for (const [kind, mark] of Object.entries(SPANS)) {
        const run = new RegExp(mark + '(?:\\s*[、，,；;和与]\\s*' + mark + ')*', 'g');
        out = out.replace(run, match => spanPhrase(kind, match.split(mark).length - 1));
    }
    return out;
}

/** Parentheses usually hold asides, dates and file paths - noise when listening. */
function stripParenthetical(text) {
    if (readParenthetical) return text;
    let out = text;
    for (let pass = 0; pass < 4; pass += 1) {
        const next = out.replace(/（[^（）]*）/g, '').replace(/\([^()]*\)/g, '');
        if (next === out) break;
        out = next;
    }
    return out;
}

/** Dropping parentheses leaves double spaces and gaps between Chinese characters. */
function tidy(text) {
    return text
        .replace(/[\t ]+/g, ' ')
        .replace(/\s+([，。；、！？：）」』】])/g, '$1')
        .replace(/([（「『【])\s+/g, '$1')
        .replace(/(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])/g, '')
        .trim();
}

function spoken(node) {
    const clone = node.cloneNode(true);
    clone.querySelectorAll('button, script, style').forEach(child => child.remove());
    clone.querySelectorAll('code').forEach(child => child.replaceWith(document.createTextNode(inlineCode(child.textContent))));
    return tidy(collapseSpans(stripParenthetical(clone.textContent)).replace(SPEECH_NOISE, ''));
}

function cellText(node) {
    const clone = node.cloneNode(true);
    clone.querySelectorAll('code').forEach(child => child.replaceWith(document.createTextNode(inlineCode(child.textContent))));
    return tidy(collapseSpans(stripParenthetical(clone.textContent)).replace(SPEECH_NOISE, ''));
}

function tableItems(table, t) {
    const headers = [...table.querySelectorAll('thead th, thead td')].map(cellText).filter(Boolean);
    const rows = [...table.querySelectorAll('tbody tr')];
    const body = rows.length ? rows : [...table.querySelectorAll('tr')].filter(row => row.querySelector('td'));
    if (!body.length) return [];
    const items = [{ kind: 'table', gap: .5, text: headers.length
        ? t('下面是一张表格，共 ' + body.length + ' 行，列有：' + headers.join('、') + '。',
            'Here is a table with ' + body.length + ' rows and these columns: ' + headers.join(', ') + '.')
        : t('下面是一张表格，共 ' + body.length + ' 行。', 'Here is a table with ' + body.length + ' rows.') }];
    // Reading every row of a long table is unbearable; cover the head and say how much is left.
    const spokenRows = body.slice(0, 8);
    spokenRows.forEach((row, index) => {
        const cells = [...row.children].map(cellText);
        const pairs = cells.map((value, column) => (headers[column] ? headers[column] + '，' + value : value)).filter(Boolean);
        if (!pairs.length) return;
        items.push({ kind: 'table-row', gap: .18,
            text: t('第 ' + (index + 1) + ' 行：' + pairs.join('；') + '。',
                'Row ' + (index + 1) + ': ' + pairs.join('; ') + '.') });
    });
    if (body.length > spokenRows.length) {
        items.push({ kind: 'table-row', gap: .2,
            text: t('其余 ' + (body.length - spokenRows.length) + ' 行请查看原文。',
                'The remaining ' + (body.length - spokenRows.length) + ' rows are in the message.') });
    }
    return items;
}

function codeItems(block, t) {
    const lines = block.textContent.replace(/\r\n/g, '\n').trim().split('\n').filter(line => line.trim()).length;
    const language = (block.querySelector('code')?.className || '').replace(/^language-/, '').trim();
    const label = language ? t(' ' + language + ' ', ' ' + language + ' ') : '';
    const body = lines
        ? t('这里有一段' + label + '代码，共 ' + lines + ' 行，就不逐行念了，请查看原文。',
            'There is a' + label + 'code block with ' + lines + ' lines; see the message instead.')
        : t('这里有一段代码，请查看原文。', 'There is a code block; see the message.');
    return [{ kind: 'code', gap: .45, text: body }];
}

function imageItems(root, t) {
    return [...root.querySelectorAll('img, figure')].map(node => {
        const image = node.tagName === 'IMG' ? node : node.querySelector('img');
        const caption = (node.tagName === 'FIGURE' ? node.querySelector('figcaption')?.textContent : '') || '';
        const name = (image?.alt || image?.title || caption || '').replace(SPEECH_NOISE, '').trim();
        return { kind: 'image', gap: .45,
            text: name ? t('此处有一张图片：' + name + '。', 'There is an image here: ' + name + '.')
                : t('此处有一张图片，请查看原文。', 'There is an image here; see the message.') };
    });
}

/**
 * Turn rendered answer markup into speaking units.
 *
 * Every unit becomes its own synthesis request, so block boundaries land on real
 * pauses instead of running a table cell into the next heading. `gap` is the
 * silence inserted before the unit, in seconds.
 */
export function buildSpeechPlan(root, t = (zh) => zh) {
    const items = [];
    const blocks = [...root.children];
    for (const block of blocks) {
        const tag = block.tagName.toLowerCase();
        if (tag === 'hr' || block.classList.contains('mermaid')) continue;
        const table = block.matches('table') ? block : block.querySelector('table');
        if (block.classList.contains('msg-table-scroll') || block.matches('table')) {
            items.push(...tableItems(table || block, t));
            continue;
        }
        if (tag === 'pre') { items.push(...codeItems(block, t)); continue; }
        if (tag === 'table') { items.push(...tableItems(block, t)); continue; }
        if (tag === 'figure' || tag === 'img') { items.push(...imageItems(block, t)); continue; }
        if (/^h[1-6]$/.test(tag)) {
            const text = spoken(block);
            if (text) items.push({ kind: 'heading', gap: .4, text });
            continue;
        }
        if (tag === 'ul' || tag === 'ol') {
            [...block.querySelectorAll(':scope > li')].forEach((item, index) => {
                const text = spoken(item);
                if (text) items.push({ kind: 'list', gap: .22, text: t('第 ' + (index + 1) + '，', 'Item ' + (index + 1) + ', ') + text });
            });
            continue;
        }
        if (tag === 'blockquote') {
            const text = spoken(block);
            if (text) items.push({ kind: 'quote', gap: .35, text: t('引用：', 'Quoted: ') + text });
            continue;
        }
        // Generic wrapper: keep descending so nested tables and code are not lost.
        if (block.querySelector('table, pre, figure, h1, h2, h3, h4, ul, ol')) {
            items.push(...buildSpeechPlan(block, t));
            continue;
        }
        const text = spoken(block);
        if (text) items.push({ kind: 'paragraph', gap: .3, text });
    }
    if (!items.length) {
        const text = spoken(root);
        if (text) items.push({ kind: 'paragraph', gap: 0, text });
    }
    if (items.length) items[0].gap = 0;
    return items;
}

// ---------------------------------------------------------------- markdown ---

/** Strip markdown syntax down to something worth hearing. */
function speechText(raw) {
    const text = String(raw == null ? '' : raw)
        .replace(/!\[([^\]]*)\]\([^)]*\)/g, '')
        .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
        .replace(/`([^`]+)`/g, (_, code) => inlineCode(code))
        .replace(/(\*\*|__)(.+?)\1/g, '$2')
        .replace(/(\*|_)(.+?)\1/g, '$2')
        .replace(/~~(.+?)~~/g, '$1')
        .replace(/^\s{0,3}>\s?/gm, '');
    return tidy(collapseSpans(stripParenthetical(text)).replace(SPEECH_NOISE, ''));
}

function splitRow(line) {
    return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(cell => speechText(cell));
}

const isBlankLine = line => !line.trim();
const isFenceLine = line => /^\s{0,3}(```|~~~)/.test(line);
const isHeadingLine = line => /^\s{0,3}#{1,6}\s+/.test(line);
const isRuleLine = line => /^\s{0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$/.test(line);
const isItemLine = line => /^\s{0,3}(?:[-*+]|\d+[.)])\s+/.test(line);
const isQuoteLine = line => /^\s{0,3}>\s?/.test(line);
const isTableRow = line => line.includes('|');
const isTableSep = line => /^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?\s*$/.test(line);
const itemLabel = line => /^\s{0,3}([-*+]|\d+[.)])\s+/.exec(line);

/**
 * Parse streamed markdown into speaking units, keeping only what is settled.
 *
 * While an answer streams, the trailing block is still growing - a half-written
 * table is indistinguishable from a paragraph until its separator row lands. So
 * everything except the last block counts as settled, and the last block counts
 * only once something follows it (or when `final` says the stream ended).
 */
export function parseSpeechMarkdown(markdown, final = false, t = (zh) => zh) {
    const lines = String(markdown == null ? '' : markdown).replace(/\r\n?/g, '\n').split('\n');
    const units = [];
    let index = 0;
    // True when the text simply ran out mid-block, so that block may still grow.
    let tailOpen = false;
    while (index < lines.length) {
        const line = lines[index];
        if (isBlankLine(line)) { index += 1; continue; }
        if (isRuleLine(line)) { index += 1; continue; }

        if (isFenceLine(line)) {
            const marker = line.trim().slice(0, 3);
            let end = index + 1;
            while (end < lines.length && !lines[end].trim().startsWith(marker)) end += 1;
            const closed = end < lines.length;
            if (closed) {
                const body = lines.slice(index + 1, end).join('\n');
                const language = line.trim().slice(3).trim();
                units.push(...codeItems({ textContent: body, querySelector: () => (language ? { className: 'language-' + language } : null) }, t));
            }
            index = closed ? end + 1 : lines.length;
            if (closed) tailOpen = false;
            continue;
        }

        if (isHeadingLine(line)) {
            const text = speechText(line.replace(/^\s{0,3}#{1,6}\s+/, '').replace(/\s*#+\s*$/, ''));
            if (text) units.push({ kind: 'heading', gap: .4, text });
            index += 1;
            tailOpen = index >= lines.length;
            continue;
        }

        if (isTableRow(line) && index + 1 < lines.length && isTableSep(lines[index + 1])) {
            const headers = splitRow(line).filter(Boolean);
            index += 2;
            const rows = [];
            while (index < lines.length && isTableRow(lines[index]) && !isBlankLine(lines[index])) { rows.push(splitRow(lines[index])); index += 1; }
            // An unterminated table is still growing: its row count would be wrong,
            // and the hint would have to be re-read on every new row.
            if (index >= lines.length && !final) continue;
            tailOpen = index >= lines.length;
            if (rows.length) {
                // No row count here: rows keep arriving while streaming, and a hint
                // that changes after being spoken cannot be taken back.
                units.push({ kind: 'table', gap: .5, text: headers.length
                    ? t('下面是一张表格，列有：' + headers.join('、') + '。',
                        'Here is a table with these columns: ' + headers.join(', ') + '.')
                    : t('下面是一张表格。', 'Here is a table.') });
                const spokenRows = rows.slice(0, 8);
                spokenRows.forEach((cells, at) => {
                    const pairs = cells.map((value, column) => (headers[column] ? headers[column] + '，' + value : value)).filter(Boolean);
                    if (!pairs.length) return;
                    units.push({ kind: 'table-row', gap: .18,
                        text: t('第 ' + (at + 1) + ' 行：' + pairs.join('；') + '。',
                            'Row ' + (at + 1) + ': ' + pairs.join('; ') + '.') });
                });
                if (rows.length > spokenRows.length) {
                    units.push({ kind: 'table-row', gap: .2,
                        text: t('其余行请查看原文。', 'The remaining rows are in the message.') });
                }
            }
            continue;
        }

        if (isItemLine(line)) {
            let count = 0;
            while (index < lines.length && isItemLine(lines[index])) {
                let body = lines[index].replace(/^\s{0,3}(?:[-*+]|\d+[.)])\s+/, '');
                index += 1;
                // Wrapped continuation lines belong to the same item.
                while (index < lines.length && !isBlankLine(lines[index])
                    && !isItemLine(lines[index]) && !isHeadingLine(lines[index])
                    && !isFenceLine(lines[index]) && !isQuoteLine(lines[index])) {
                    body += ' ' + lines[index].trim();
                    index += 1;
                }
                count += 1;
                const text = speechText(body);
                if (text) units.push({ kind: 'list', gap: .22, text: t('第 ' + count + '，', 'Item ' + count + ', ') + text });
            }
            tailOpen = index >= lines.length;
            continue;
        }

        if (isQuoteLine(line)) {
            const body = [];
            while (index < lines.length && isQuoteLine(lines[index])) { body.push(lines[index].replace(/^\s{0,3}>\s?/, '')); index += 1; }
            const text = speechText(body.join(' '));
            if (text) units.push({ kind: 'quote', gap: .35, text: t('引用：', 'Quoted: ') + text });
            tailOpen = index >= lines.length;
            continue;
        }

        const body = [];
        while (index < lines.length && !isBlankLine(lines[index]) && !isFenceLine(lines[index])
            && !isHeadingLine(lines[index]) && !isItemLine(lines[index]) && !isQuoteLine(lines[index])
            && !isRuleLine(lines[index])
            && !(isTableRow(lines[index]) && index + 1 < lines.length && isTableSep(lines[index + 1]))) {
            body.push(lines[index]);
            index += 1;
        }
        const text = speechText(body.join(' '));
        if (text) units.push({ kind: 'paragraph', gap: .3, text });
        // A trailing line with pipes may still turn into a table header once its
        // separator row arrives, so hold it while the answer is streaming.
        tailOpen = index >= lines.length
            || (!final && body.length > 0 && body[body.length - 1].includes('|'));
    }
    if (!final && tailOpen && units.length) units.pop();
    if (units.length) units[0].gap = 0;
    return units;
}
