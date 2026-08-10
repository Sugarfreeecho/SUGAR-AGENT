const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..', '..');
const source = fs.readFileSync(path.join(root, 'frontend/src/app/modules/input-actions.js'), 'utf8');

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

console.log('input action runtime checks passed');
