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

function bindInputSubmit(input, options) {
    if (!input) return;
    options = options || {};
    const mode = options.mode || (input.tagName === 'TEXTAREA' ? 'editor' : 'single-line');
    input.addEventListener('keydown', function (event) {
        if (!isInputSubmitShortcut(event, mode)) return;
        event.preventDefault();
        if (typeof options.submit === 'function') void options.submit(event, input);
    });
}
