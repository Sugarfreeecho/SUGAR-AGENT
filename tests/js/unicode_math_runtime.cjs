const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const mathSource = fs.readFileSync(path.join(root, 'frontend/src/app/modules/unicode-math.js'), 'utf8');
const renderingSource = fs.readFileSync(path.join(root, 'frontend/src/app/modules/message-rendering.js'), 'utf8');
const marked = require(path.join(root, 'frontend/node_modules/marked'));

function loadMath() {
  const context = vm.createContext({ console, Array, String, Number, RegExp, Object, Math });
  vm.runInContext(mathSource, context);
  return context;
}

const math = loadMath();

function convert(text) {
  return math.replaceMarkdownMathWithUnicode(text);
}

function texts(text) {
  return Array.from(convert(text).items, item => item.text);
}

// Greek letters, subscripts and operators become Unicode math text.
assert.deepEqual(texts('速度 $v_0 + \\alpha t$'), ['v₀ + α t']);
assert.deepEqual(texts('$\\sum_{i=1}^{n} a_i$'), ['∑ᵢ₌₁ⁿ aᵢ']);
assert.deepEqual(texts('$\\frac{a+b}{2}$'), ['(a+b)/2']);
assert.deepEqual(texts('$\\sqrt{x^2+y^2}$'), ['√(x²+y²)']);
assert.deepEqual(texts('$\\sqrt[3]{8}$'), ['∛8']);
assert.deepEqual(texts('$\\lim_{x \\to 0} \\frac{\\sin x}{x} = 1$'), ['lim(x→0) (sin x)/x = 1']);
assert.deepEqual(texts('$25^\\circ$'), ['25°']);
assert.deepEqual(texts('$\\mathbb{R}^n$'), ['ℝⁿ']);
assert.deepEqual(texts('$\\hat{x} + \\vec{v}$'), ['x̂ + v⃗']);
assert.deepEqual(texts('$a \\not= b$'), ['a ≠ b']);

// Display delimiters keep the display flag; inline MathJax delimiters also convert.
const display = convert('$$\\int_0^1 x^2 \\, dx = \\frac{1}{3}$$');
assert.equal(display.items.length, 1);
assert.equal(display.items[0].display, true);
assert.equal(display.items[0].text, '∫₀¹ x² \u2009dx = 1/3');
assert.equal(display.text.includes('$$'), false);

const slashDelimited = convert('甲 \\(a^2+b^2=c^2\\) 乙 \\[\\sqrt{2}\\]');
assert.deepEqual(Array.from(slashDelimited.items, item => item.text), ['a²+b²=c²', '√2']);
assert.equal(slashDelimited.items[1].display, true);
assert.equal(slashDelimited.text.includes('\\('), false);

// Code is never rewritten: fenced blocks, inline spans and a stray backtick.
const codecase = '`$a_b$` 和\n```bash\necho $HOME $PATH\n```\n以及 `$c$` 与 $d^2$';
const kept = convert(codecase);
assert.equal(kept.text.includes('`$a_b$`'), true);
assert.equal(kept.text.includes('echo $HOME $PATH'), true);
assert.equal(kept.text.includes('`$c$`'), true);
assert.deepEqual(Array.from(kept.items, item => item.text), ['d²']);

// Currency and shell variables stay literal.
assert.equal(convert('价格是 $5 和 $10').items.length, 0);
assert.equal(convert('$HOME and $PATH').items.length, 0);
assert.equal(convert('costs $100.50 today').items.length, 0);

// A stray backtick must not swallow the rest of the card.
assert.deepEqual(texts('a stray ` tick then $z^2$'), ['z²']);

// Placeholder restore escapes the formula body and keeps the raw TeX for tooling.
const restored = math.restoreUnicodeMathPlaceholders(convert('$a<b$').text, convert('$a<b$').items);
assert.equal(restored.includes('&lt;'), true);
assert.equal(restored.includes('data-tex="$a'), false);
const quoteConvert = convert("$a''+b$");
const quoteHtml = math.restoreUnicodeMathPlaceholders(quoteConvert.text, quoteConvert.items);
assert.equal(quoteHtml.includes('data-tex="a&#39;&#39;+b"'), true);

// End-to-end through the real Markdown parser: the Final card opts in, other
// callers keep the previous output.
function loadRenderer() {
  const match = renderingSource.match(/^function renderMarkdown\([^]*?^}/m);
  assert.ok(match, 'renderMarkdown is missing');
  const context = vm.createContext({
    console,
    marked,
    markedOptionsApplied: false,
    escapeHtml(value) {
      return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    },
    escapeMarkdownSingleTildes(value) { return String(value); },
    normalizeExplicitMarkdownPathLinksOutsideFences(value) { return String(value); },
    configureWorkspaceMarkdownRenderer() {},
  });
  vm.runInContext(mathSource, context);
  vm.runInContext(match[0], context);
  return context;
}

const renderer = loadRenderer();
const finalHtml = renderer.renderMarkdown('速度为 $v_0$，公式 $$\\frac{a}{b}$$', { unicodeMath: true });
assert.equal(finalHtml.includes('<span class="unicode-math"'), true);
assert.equal(finalHtml.includes('v₀'), true);
assert.equal(finalHtml.includes('unicode-math--display'), true);
assert.equal(finalHtml.includes('$v_0$'), false);
assert.equal(finalHtml.includes('@@MYAGENT_UCMATH_'), false);

const plainHtml = renderer.renderMarkdown('速度为 $v_0$');
assert.equal(plainHtml.includes('$v_0$'), true);
assert.equal(plainHtml.includes('unicode-math'), false);

const codeHtml = renderer.renderMarkdown('```text\n$x_1$\n```\n\n行内 `$y_2$` 不变', { unicodeMath: true });
assert.equal(codeHtml.includes('$x_1$'), true);
assert.equal(codeHtml.includes('$y_2$'), true);

// Wiring: only the assistant Final-card branch opts in, and the module is part
// of the shared UI scope before message-rendering.
const indexSource = fs.readFileSync(path.join(root, 'frontend/src/app/index.js'), 'utf8');
assert.ok(
  /renderMarkdown\(displayStr, role === 'assistant' \? \{ unicodeMath: true \} : null\)/.test(renderingSource),
  'appendMessage must request Unicode math only for the Final card',
);
assert.ok(/import unicodeMathSource from '\.\/modules\/unicode-math\.js\?raw'/.test(indexSource));
const mathSlot = indexSource.indexOf('    unicodeMathSource,');
const renderSlot = indexSource.indexOf('    messageRenderingSource,');
assert.ok(mathSlot > 0 && renderSlot > mathSlot, 'unicode-math must load before message-rendering');

console.log('unicode math runtime checks passed');
