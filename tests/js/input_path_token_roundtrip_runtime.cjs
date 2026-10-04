/**
 * 输入框 @基名 胶囊：标签→真实路径映射不得在「发送」前丢失。
 *
 * 背景：输入框把绝对路径改写成 @基名 胶囊标签，真实路径只存在内存映射
 * inputPathTokenMap 里；入队/发送时映射会被 clearInputPathTokens() 清空。
 * 于是任何"把 display 文本（标签形式）当正文回填/落盘"的链路，都会在下一次
 * 发送时真的发出 "@文件名" —— 路径被吞。
 *
 * 断言：撤回回填与草稿恢复后，真正提交给模型的文本仍是完整真实路径；
 *       并附负向对照，确认缺映射时确实会丢路径（即修复前的行为）。
 *
 * 运行：node tests/js/input_path_token_roundtrip_runtime.cjs
 */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..', '..');
const read = (rel) => fs.readFileSync(path.join(root, ...rel.split('/')), 'utf8');

const rendering = read('frontend/src/app/modules/message-rendering.js');
const scroll = read('frontend/src/app/modules/session-scroll-history.js');
const sse = read('frontend/src/app/modules/sse-handling.js');
const shared = read('frontend/src/app/modules/shared-state-and-dialogs.js');

/** 按大括号配平抽取函数定义（被抽函数体内无字符串/正则花括号）。 */
function fn(source, name) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, `missing function: ${name}`);
  let depth = 0;
  for (let i = source.indexOf('{', start); i < source.length; i += 1) {
    if (source[i] === '{') depth += 1;
    else if (source[i] === '}') {
      depth -= 1;
      if (depth === 0) return source.slice(start, i + 1);
    }
  }
  throw new Error(`unbalanced function body: ${name}`);
}

/** 抽取唯一片段所在的整行声明。 */
function declaration(source, needle) {
  const line = source.split('\n').find((item) => item.includes(needle));
  assert(line, `missing declaration: ${needle}`);
  return line.trim();
}

const extStart = rendering.indexOf('var LINKIFY_EXT_FRAGMENT = (');
const extEnd = rendering.indexOf('\n);', extStart) + 3;
assert(extStart >= 0 && extEnd > 3, 'missing LINKIFY_EXT_FRAGMENT');

const script = [
  declaration(shared, 'const inputPathTokenMap ='),
  declaration(shared, 'let inputPathRewriteGuard ='),
  declaration(shared, 'const draftBySession ='),
  declaration(shared, 'const NEW_SESSION_DRAFT_KEY ='),
  declaration(shared, 'const LS_INPUT_DRAFT_PREFIX ='),
  'var _inputKnownExtWinPathRe = null;',
  rendering.slice(extStart, extEnd),
  fn(rendering, 'trimTrailingPathPunct'),
  fn(rendering, 'stripPathWrappingQuotes'),
  fn(rendering, 'escapeRegExpLiteral'),
  fn(rendering, 'quotePromptPath'),
  fn(rendering, 'expandInputPathTokens'),
  fn(rendering, 'normalizeInputPathTokenIdentity'),
  fn(rendering, 'workspaceOpenDisplayLabel'),
  fn(rendering, 'uniqueInputPathDisplayLabel'),
  fn(rendering, 'inputQuotedWindowsPathRegex'),
  fn(rendering, 'inputKnownExtWindowsPathRegex'),
  fn(rendering, 'inputSimpleWindowsPathRegex'),
  fn(rendering, 'rewriteInputWorkspacePaths'),
  fn(rendering, 'clearInputPathTokens'),
  fn(scroll, 'restoreInputDraft'),
  fn(scroll, 'inputDraftStorageKey'),
  fn(scroll, 'inputDraftPathTokenStorageKey'),
  fn(scroll, 'collectDraftPathTokens'),
  fn(scroll, 'persistDraftPathTokens'),
  fn(scroll, 'restoreDraftPathTokens'),
  fn(scroll, 'persistInputDraft'),
  fn(scroll, 'readStoredInputDraft'),
  fn(scroll, 'removeStoredInputDraft'),
  fn(sse, 'returnFollowupToInput'),
  'globalThis.__api = { inputPathTokenMap, persistInputDraft, restoreInputDraft, expandInputPathTokens, rewriteInputWorkspacePaths, returnFollowupToInput };',
].join('\n');

const storage = new Map();
const storageWrites = [];
const WORK_DIR = 'D:\\work';

const context = vm.createContext({
  console,
  JSON,
  Object,
  String,
  Number,
  Array,
  RegExp,
  Map,
  localStorage: {
    getItem: (key) => (storage.has(key) ? storage.get(key) : null),
    setItem: (key, value) => {
      storage.set(key, String(value));
      storageWrites.push(['set', key]);
    },
    removeItem: (key) => {
      storage.delete(key);
      storageWrites.push(['remove', key]);
    },
  },
  window: { __WORK_DIR__: WORK_DIR, MyAgentPathPicker: null },
  document: { activeElement: null, getElementById: () => null },
  messageInput: { value: '', focus() {}, setSelectionRange() {}, style: {} },
  currentSessionId: null,
  refreshInputPathChips() {},
  autoResizeTextarea() {},
  setSendButtonState() {},
  renderFollowupQueue() {},
  syncSessionDraftBadges() {},
  removePendingSteerFromProcess() {},
  /** 真实实现把解析结果交给胶囊渲染；这里只需"路径能否落到工作区相对路径"。 */
  pathTokenToWorkspaceOpenRel(token) {
    const workspace = String(WORK_DIR).replace(/\\/g, '/').replace(/\/+$/, '');
    const normalized = String(token || '').trim().replace(/\\/g, '/');
    if (!normalized || normalized.toLowerCase().indexOf(workspace.toLowerCase() + '/') !== 0) return null;
    return normalized.slice(workspace.length).replace(/^\/+/, '');
  },
});
vm.runInContext(script, context);
const api = context.__api;

const REAL_PATH = `${WORK_DIR}\\报告\\report.md`;
const QUOTED = `"${REAL_PATH}"`;
const LABEL = '@report.md';
const DRAFT_KEY = 'myagent-input-draft-s1';

function sendText() {
  return api.expandInputPathTokens(context.messageInput.value);
}

/* ① 草稿落盘 + 刷新恢复：恢复后发送的必须是真实路径 */
{
  context.messageInput.value = `帮我看看 ${REAL_PATH} 里的结论`;
  api.rewriteInputWorkspacePaths();
  assert.strictEqual(context.messageInput.value, `帮我看看 ${LABEL} 里的结论`, '输入框应把绝对路径改写成胶囊标签');
  assert.deepStrictEqual({ ...api.inputPathTokenMap }, { [LABEL]: REAL_PATH }, '标签映射应指向真实路径');

  api.persistInputDraft('s1', context.messageInput.value);
  assert.strictEqual(storage.get(DRAFT_KEY), `帮我看看 ${LABEL} 里的结论`, '草稿文本落盘的是标签形式');
  assert.strictEqual(
    storage.get(`${DRAFT_KEY}::path-tokens`),
    JSON.stringify({ [LABEL]: REAL_PATH }),
    '标签→真实路径映射必须与草稿一起落盘',
  );

  // 模拟刷新：内存映射清空
  Object.keys(api.inputPathTokenMap).forEach((key) => delete api.inputPathTokenMap[key]);
  context.messageInput.value = '';

  api.restoreInputDraft('s1');
  assert.strictEqual(context.messageInput.value, `帮我看看 ${LABEL} 里的结论`, '恢复后显示形态仍为胶囊标签');
  assert.deepStrictEqual({ ...api.inputPathTokenMap }, { [LABEL]: REAL_PATH }, '恢复时应重建标签映射');
  assert.strictEqual(sendText(), `帮我看看 ${QUOTED} 里的结论`, '草稿恢复后发送的真实路径不得被吞');

  // 负向对照：缺映射（修复前行为）时确实只剩标签
  Object.keys(api.inputPathTokenMap).forEach((key) => delete api.inputPathTokenMap[key]);
  context.messageInput.value = '';
  storage.delete(`${DRAFT_KEY}::path-tokens`);
  api.restoreInputDraft('s1');
  const lost = sendText();
  assert(lost.indexOf(REAL_PATH) < 0 && lost.indexOf(LABEL) >= 0, `缺映射时应复现丢路径：${lost}`);

  // 清空草稿必须同时清掉映射键，避免陈旧映射串到后面的输入
  api.persistInputDraft('s1', '');
  assert.strictEqual(storage.get(`${DRAFT_KEY}::path-tokens`), undefined, '清空草稿必须同时清掉映射键');
  assert.strictEqual(storage.get(DRAFT_KEY), undefined, '清空草稿必须清掉草稿键');
}

/* ② 撤回 / steer 失败回填：回填的是发送原文，重新发送不得丢路径 */
{
  Object.keys(api.inputPathTokenMap).forEach((key) => delete api.inputPathTokenMap[key]); // 入队时映射已被清空
  context.messageInput.value = '';
  context.currentSessionId = 's1';

  api.returnFollowupToInput('s1', {
    text: `帮我看看 ${QUOTED} 里的结论`,
    display: `帮我看看 ${LABEL} 里的结论`,
    skills: [],
    attachments: [],
  });

  assert.strictEqual(context.messageInput.value, `帮我看看 ${LABEL} 里的结论`, '回填后显示形态仍为胶囊标签');
  assert.deepStrictEqual({ ...api.inputPathTokenMap }, { [LABEL]: REAL_PATH }, '回填应重建标签映射');
  assert.strictEqual(sendText(), `帮我看看 ${QUOTED} 里的结论`, '撤回后重新发送的真实路径不得被吞');

  // 负向对照：旧实现用 display 回填时只会发出死标签
  Object.keys(api.inputPathTokenMap).forEach((key) => delete api.inputPathTokenMap[key]);
  context.messageInput.value = `帮我看看 ${LABEL} 里的结论`;
  const oldFlow = sendText();
  assert(oldFlow.indexOf(REAL_PATH) < 0 && oldFlow.indexOf(LABEL) >= 0, `旧回填方式应复现丢路径：${oldFlow}`);
}

/* ③ 模型侧与显示侧分路：steer / 队列 /chat 一律提交发送原文 */
{
  assert(
    /sendSteerMessage\(\s*sid,\s*item\.text,/.test(sse),
    'steer 提交给模型侧必须是 item.text（展开后的真实路径）',
  );
  const queuedChatCalls = (sse.match(/message: item\.text,/g) || []).length;
  assert(queuedChatCalls >= 3, `队列 /chat 重发应统一用 item.text，实际命中 ${queuedChatCalls} 处`);
  assert(sse.includes("formData.append('ui_message', uiBaseMessage);"), 'ui_message 仍走 display（显示形态不变）');
  assert(
    sse.includes('const rawMessage = options.fromQueue ? visibleMessage : expandInputPathTokens(visibleMessage);'),
    'fromInlineRewrite 也必须做标签展开',
  );
}

console.log('input_path_token_roundtrip_runtime: all assertions passed');
