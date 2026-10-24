var composerDraftRevision = 0;

function normalizeSendableText(value) {
    return String(value == null ? '' : value).replace(/[\u200B-\u200D\uFEFF]/g, '').trim();
}

function hasSendableText(value) {
    return normalizeSendableText(value).length > 0;
}

function isInputMethodComposing(event) {
    return !!(event && (event.isComposing || event.keyCode === 229 || event.which === 229));
}

function isInputSubmitShortcut(event, mode) {
    if (!event || event.key !== 'Enter' || isInputMethodComposing(event)) return false;
    if (mode === 'editor') return !!(event.ctrlKey || event.metaKey) && !event.shiftKey && !event.altKey;
    return !event.shiftKey && !event.ctrlKey && !event.metaKey && !event.altKey;
}

function insertTextareaNewline(textarea, event) {
    if (!textarea) return false;
    const start = Number.isFinite(Number(textarea.selectionStart)) ? Number(textarea.selectionStart) : textarea.value.length;
    const end = Number.isFinite(Number(textarea.selectionEnd)) ? Number(textarea.selectionEnd) : start;
    textarea.value = textarea.value.substring(0, start) + '\n' + textarea.value.substring(end);
    textarea.selectionStart = textarea.selectionEnd = start + 1;
    if (event && typeof event.preventDefault === 'function') event.preventDefault();
    return true;
}

/** Remember the exact draft and selection owned by a recording. */
function captureComposerInsertion(textarea, sessionId, revision) {
    return { sessionId: sessionId || null, revision: revision, value: textarea.value,
        start: textarea.selectionStart, end: textarea.selectionEnd };
}

/** Insert only into the unchanged source draft; callers retain rejected text. */
function insertComposerTranscript(textarea, span, sessionId, revision, text) {
    if (!span || span.sessionId !== (sessionId || null) || span.revision !== revision
        || span.value !== textarea.value || textarea.disabled || textarea.readOnly || !text) return false;
    textarea.setRangeText(text, span.start, span.end, 'end');
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
}

