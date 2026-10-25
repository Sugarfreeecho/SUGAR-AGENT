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

function inlineCode(value) {
    const text = value.trim();
    // A URL or a long identifier is unlistenable; name it instead of spelling it out.
    if (/^https?:\/\//i.test(text)) return '链接';
    return text.length > INLINE_CODE_LIMIT ? '一段代码' : text;
}

function spoken(node) {
    const clone = node.cloneNode(true);
    clone.querySelectorAll('button, script, style').forEach(child => child.remove());
    clone.querySelectorAll('code').forEach(child => child.replaceWith(document.createTextNode(inlineCode(child.textContent))));
    return clone.textContent.replace(SPEECH_NOISE, '').replace(/\s+/g, ' ').trim();
}

function cellText(node) {
    const clone = node.cloneNode(true);
    clone.querySelectorAll('code').forEach(child => child.replaceWith(document.createTextNode(inlineCode(child.textContent))));
    return clone.textContent.replace(SPEECH_NOISE, '').replace(/\s+/g, ' ').trim();
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
