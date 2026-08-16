const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..', '..');
const source = fs.readFileSync(path.join(root, 'frontend/src/app/modules/input-actions.js'), 'utf8');
const sseSource = fs.readFileSync(path.join(root, 'frontend/src/app/modules/sse-handling.js'), 'utf8');

function between(text, start, end) {
  const from = text.indexOf(start);
  const to = text.indexOf(end, from + start.length);
  assert.notEqual(from, -1, `missing start marker: ${start}`);
  assert.notEqual(to, -1, `missing end marker: ${end}`);
  return text.slice(from, to);
}

const context = vm.createContext({});
vm.runInContext(source, context);

assert.equal(context.normalizeSendableText(' \u200B\uFEFF '), '');
assert.equal(context.normalizeSendableText('  hello \u200B '), 'hello');
assert.equal(context.hasSendableText('\u200C'), false);
assert.equal(context.hasSendableText(' 任务 '), true);

assert.equal(context.isInputMethodComposing({ isComposing: true }), true);
assert.equal(context.isInputMethodComposing({ keyCode: 229 }), true);
assert.equal(context.isInputSubmitShortcut({ key: 'Enter' }, 'chat'), true);
assert.equal(context.isInputSubmitShortcut({ key: 'Enter', shiftKey: true }, 'chat'), false);
assert.equal(context.isInputSubmitShortcut({ key: 'Enter', isComposing: true }, 'chat'), false);
assert.equal(context.isInputSubmitShortcut({ key: 'Enter', ctrlKey: true }, 'editor'), true);
assert.equal(context.isInputSubmitShortcut({ key: 'Enter', metaKey: true }, 'editor'), true);
assert.equal(context.isInputSubmitShortcut({ key: 'Enter' }, 'editor'), false);
assert.equal(context.isInputSubmitShortcut({ key: 'Enter', altKey: true }, 'single-line'), false);

const textarea = {
  value: 'ab',
  selectionStart: 1,
  selectionEnd: 1,
};
let prevented = false;
context.insertTextareaNewline(textarea, { preventDefault() { prevented = true; } });
assert.equal(textarea.value, 'a\nb');
assert.equal(textarea.selectionStart, 2);
assert.equal(textarea.selectionEnd, 2);
assert.equal(prevented, true);

let pausedDuringUpload = 0;
let sentDuringUpload = 0;
const composerContext = vm.createContext({
  readComposerActionState() {
    return { uploadBusy: true, running: true, sendable: false, sessionId: 's' };
  },
  pauseCurrentRun() { pausedDuringUpload += 1; },
  sendMessage() { sentDuringUpload += 1; },
});
vm.runInContext(
  between(sseSource, 'function dispatchComposerAction', "messageInput.addEventListener('keydown'"),
  composerContext,
);
assert.equal(composerContext.dispatchComposerAction(true), false);
assert.equal(pausedDuringUpload, 0);
assert.equal(sentDuringUpload, 0);

console.log('input action runtime checks passed');
