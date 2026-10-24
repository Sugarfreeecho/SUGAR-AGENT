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
