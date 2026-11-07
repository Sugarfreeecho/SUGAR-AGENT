/**
 * 子代理寻址页的右上角上下文读数。
 *
 * 侧栏每次刷新都会走 updateSessionTitle，而寻址分支一旦在这里清空读数，就没有
 * 任何路径再回填：子代理页会永远停在「— / —」。这个用例锁住两点：
 *  1. 寻址分支按当前（子）会话重绘，而不是固定置空；
 *  2. 没有读数时的补取只发起一次，不会随每次侧栏刷新变成轮询。
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..', '..');
const source = fs.readFileSync(
  path.join(root, 'frontend/src/app/modules/message-rendering.js'),
  'utf8',
);
const start = source.indexOf('var addressedContextFetchRequested');
const end = source.indexOf('/**\n * 子代理会话寻址下的标题渲染');
assert.ok(start >= 0 && end > start, 'missing updateSessionTitle source');
const functionSource = source.slice(start, end);

function makeNode() {
  return {
    dataset: {},
    textContent: '',
    innerHTML: '',
    parentNode: null,
    closest() { return { appendChild() {} }; },
    appendChild() {},
  };
}

function run({ tokens, addressed }) {
  const br = makeNode();
  const sub = makeNode();
  const calls = { apply: 0, clear: 0, schedule: 0 };
  const ctx = vm.createContext({
    console,
    currentSessionId: addressed ? 'child-1' : 'parent-1',
    document: {
      getElementById(id) {
        return id === 'breadcrumb-text' ? br : id === 'breadcrumb-sub' ? sub : null;
      },
      querySelector() { return null; },
    },
    subagentAddressing: { current: () => (addressed ? { childSessionId: 'child-1' } : null) },
    renderSubagentAddressedTitle(node) {
      if (!addressed) return false;
      node.dataset.addressing = 'child';
      return true;
    },
    setContextTokenLabel() { calls.clear += 1; },
    applyContextTokenLabelForCurrentSession() { calls.apply += 1; },
    selectContextTokens() { return tokens; },
    scheduleContextTokensAfterPaint() { calls.schedule += 1; },
    bindUiHoverTip() {},
    initUiHoverTips() {},
    localizeSessionPlaceholderName: value => value,
    selectCurrentSession: () => null,
    getActiveWorkDir: () => '',
    buildSessionWorkspaceSubtitle: () => '',
    syncTitlebarSessionMenu() {},
    updateHumanInteractionBanner() {},
  });
  vm.runInContext(functionSource, ctx);
  ctx.updateSessionTitle();
  return { ctx, calls };
}

// 1) 寻址态：必须重绘子会话读数，不能固定清空
{
  const { ctx, calls } = run({ tokens: { estimated: 223639, threshold: 512000 }, addressed: true });
  assert.equal(calls.apply, 1);
  assert.equal(calls.clear, 0, 'subagent page must not wipe the context meter');
  assert.equal(calls.schedule, 0, 'existing value needs no refetch');
  // 再次刷新（侧栏 5s 节拍）仍然要保留读数
  ctx.updateSessionTitle();
  assert.equal(calls.clear, 0);
}

// 2) 无读数：补取只发起一次
{
  const { ctx, calls } = run({ tokens: null, addressed: true });
  assert.equal(calls.apply, 1);
  assert.equal(calls.schedule, 1);
  ctx.updateSessionTitle();
  ctx.updateSessionTitle();
  assert.equal(calls.schedule, 1, 'missing reading must not become a polling loop');
}

// 3) 普通会话不受影响
{
  const { calls } = run({ tokens: { estimated: 1, threshold: 10 }, addressed: false });
  assert.equal(calls.apply, 0);
  assert.equal(calls.clear, 0);
}

console.log('subagent context meter runtime: 3 scenarios passed');
