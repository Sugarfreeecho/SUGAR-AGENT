const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const source = name => fs.readFileSync(path.join(root, 'frontend/src/app', name), 'utf8');
const fn = (text, name) => {
  const match = text.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'));
  assert(match, `missing ${name}`);
  return match[0];
};

async function main() {
  const sessions = new Map([
    ['parent', {id: 'parent'}],
    ['child', {id: 'child', is_subagent: true, parent_session_id: 'parent'}],
  ]);
  const cards = [], posts = [];
  const stream = {querySelectorAll: () => cards};
  const context = vm.createContext({
    console, Date, TextDecoder, Promise, Set, Map, setTimeout,
    currentSessionId: 'parent', sessionsList: null,
    document: {getElementById: () => null, createElement: () => ({})},
    requestAnimationFrame: callback => callback(),
    sessionStore: {get: sid => sessions.get(sid), list: () => [...sessions.values()]},
    sessionStorage: {removeItem() {}},
    SSE_IDLE_TIMEOUT_MS: 1000,
    readSseChunkWithIdleTimeout: reader => reader.read(),
    applySessionEvent() { throw new Error('child event reached parent reducer'); },
    noteSubagentLifecycleFrame() {},
    scheduleFinalVisibleAfterRunIfEnabled() {},
  });
  vm.runInContext(source('modules/human-interactions.js'), context);
  function makeCard(record, sid) {
    const title = {appendChild() {}};
    return {dataset: {sessionId: sid, interactionId: record.approval_id || record.interaction_id,
      requestVersion: '1', kind: record.kind},
      contains: () => false, querySelector: selector => selector === '.human-card-title' ? title : null,
      querySelectorAll: () => [], setAttribute() {}};
  }
  Object.assign(context, {
    createHumanQuestionCard: makeCard, createHumanApprovalCard: makeCard, createHumanTerminalCard: makeCard,
    ensurePendingHumanInteractionToolRow() { throw new Error('child tool row inserted in parent'); },
    humanInteractionToolSlot() { throw new Error('child card attached to parent tool'); },
    placeHumanInteractionCardFallback(_stream, card) { cards.push(card); card.parentNode = stream; },
    autoRevealPendingHumanCard() {}, setHumanInteractionSubmitting() {},
    collectHumanQuestionAnswers: () => ({answers: [{question_id: 'q1', selected_option_ids: ['q1o1']}]}),
    fetch: async (url, init) => {
      posts.push({url, body: JSON.parse(init.body)});
      return {ok: true, json: async () => ({ok: true, interaction: {
        interaction_id: 'ask-child', session_id: 'child', status: 'resolved', request_version: 1,
      }})};
    },
  });
  stream.querySelectorAll = () => cards;
  stream.replaceChild = (replacement, old) => {
    cards[cards.indexOf(old)] = replacement;
    replacement.parentNode = stream;
  };
  vm.runInContext(fn(source('modules/sse-handling.js'), 'consumeAgentSseResponseInner'), context);
  const events = [
    {type: 'interaction_requested', interaction_id: 'ask-child', session_id: 'child',
      agent_id: 'child', _subagent_forward: true, tool_call_id: 'same-tool-as-parent', status: 'pending'},
    {protocol: 'runtime_v2', seq: 999, session_id: 'parent', ui_event: {
      type: 'approval_requested', approval_id: 'approve-child', session_id: 'child',
      agent_id: 'child', _subagent_forward: true, tool_call_id: 'same-tool-as-parent', status: 'pending'}},
    {type: 'run_finished', session_id: 'child', agent_id: 'child', _subagent_forward: true},
  ];
  let read = false;
  const response = {ok: true, headers: {get: () => 'text/event-stream'}, body: {getReader: () => ({read: async () => {
    if (read) return {done: true};
    read = true;
    return {done: false, value: new TextEncoder().encode(events.map(event => 'data: ' + JSON.stringify(event) + '\n').join(''))};
  }})}};
  const run = {stream, lastRuntimeSeq: 5};
  assert.equal(await context.consumeAgentSseResponseInner(response, run, 'parent', 7), 7);
  assert.equal(run.lastRuntimeSeq, 5, 'child sequences never advance parent cursor');
  assert.equal(cards.length, 2, 'parent displays both child request kinds');
  assert(cards.every(card => card.dataset.sessionId === 'child'), 'card actions remain child-owned');
  assert.equal(context.humanInteractionPendingCounts('parent').total, 2);
  await context.submitHumanQuestion(cards[0]);
  assert.equal(posts.length, 1);
  assert.equal(posts[0].url, '/sessions/child/interactions/ask-child/resolve');
  assert.equal(context.humanInteractionPendingCounts('parent').total, 1, 'answer clears the parent inbox copy');
  assert.equal(context.globalHumanInteractionPendingCounts().total, 1, 'cached child is not counted twice');

  // An idle parent also restores pending child cards from the descendant API.
  const requests = [];
  context.fetch = async url => {
    requests.push(url);
    return {ok: true, json: async () => url.includes('/approvals?')
      ? {approvals: [{approval_id: 'restore-child', session_id: 'child', status: 'pending'}]}
      : {interactions: []}};
  };
  assert(await context.refreshHumanInteractions('parent', {render: false}));
  assert(requests.every(url => url.includes('include_descendants=1')));
  assert.equal(context.pendingHumanInteractionRecords('parent')[0].session_id, 'child');
  console.log('subagent parent interaction synchronization checks passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
