const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const source = file => fs.readFileSync(path.join(root, 'frontend/src/app', file), 'utf8');
const fetchSnapshot = source('modules/session-management.js').match(
  /^async function fetchSessionsStateSnapshot\([^]*?^}/m)[0];

function setup(diagnostics) {
  let respond;
  const context = vm.createContext({
    console, currentSessionId: 'other', sessionsList: null,
    document: {getElementById: () => null},
    fetchWithTimeout: async (_url, _opts, _timeout, consume) => {
      const payload = await new Promise(resolve => { respond = resolve; });
      return consume({ok: true, json: async () => payload});
    },
  });
  if (diagnostics) context.sessionLoadingDiagnostics = {
    start: () => ({}), end() {},
    fetchJSON: async () => ({response: {ok: true},
      data: await new Promise(resolve => { respond = resolve; })}),
  };
  vm.runInContext(source('state/session-store.js') + '\nglobalThis.store = sessionStore;', context);
  vm.runInContext(source('modules/human-interactions.js'), context);
  vm.runInContext(source('state/session-actions.js') + '\n' + fetchSnapshot, context);
  return {context, respond: payload => respond(payload)};
}

async function main() {
  for (const diagnostics of [false, true]) {
    for (const kind of ['question', 'approval']) {
      for (const status of ['pending', 'resolved']) {
        const {context: c, respond} = setup(diagnostics);
        const counts = pending => ({questions: pending && kind === 'question' ? 1 : 0,
          approvals: pending && kind === 'approval' ? 1 : 0, total: pending ? 1 : 0});
        const event = {type: kind === 'question' ? 'interaction_requested' : 'approval_requested',
          interaction_id: 'ask', approval_id: 'approve', status: 'pending', request_version: 1};
        c.store.applySnapshot([{id: 'background', pending_human_interactions: counts(status === 'resolved')}], 0);
        if (status === 'resolved') c.applyHumanInteractionEvent('background', event);
        const pending = c.fetchSessionsStateSnapshot();
        c.applyHumanInteractionEvent('background', {...event,
          type: status === 'pending' ? event.type : event.type.replace('_requested', '_resolved'), status});
        respond({sessions: [{id: 'background', pending_human_interactions: counts(status === 'resolved')}]});
        c.applySessionSnapshot(await pending);
        assert.equal(c.sessionPendingHumanCounts('background').total, status === 'pending' ? 1 : 0,
          `pre-event snapshot cannot undo live ${kind} ${status} (diagnostics=${diagnostics})`);
        // A later request remains authoritative when the reader misses events.
        const next = c.fetchSessionsStateSnapshot();
        respond({sessions: [{id: 'background', pending_human_interactions: counts(status !== 'pending')}]});
        c.applySessionSnapshot(await next);
        assert.equal(c.sessionPendingHumanCounts('background').total, status === 'pending' ? 0 : 1,
          'a fresh sidebar snapshot must replace the cached interaction counts');
      }
    }
    for (const refreshSucceeds of [false, true]) {
      const {context: c, respond} = setup(diagnostics);
      c.console = {log() {}, error() {}};
      c.store.applySnapshot([{id: 'background', pending_human_interactions: {total: 0}}], 0);
      const pending = c.fetchSessionsStateSnapshot();
      c.fetch = async url => ({ok: refreshSucceeds, status: refreshSucceeds ? 200 : 503,
        json: async () => url.includes('/approvals?') ? {approvals: []} : {interactions: [
          {kind: 'question', interaction_id: 'refresh-ask', status: 'pending'},
        ]}});
      assert.equal(await c.refreshHumanInteractions('background', {render: false}), refreshSucceeds);
      respond({sessions: [{id: 'background', pending_human_interactions:
        {questions: refreshSucceeds ? 0 : 1, approvals: 0, total: refreshSucceeds ? 0 : 1}}]});
      c.applySessionSnapshot(await pending);
      assert.equal(c.sessionPendingHumanCounts('background').total, 1,
        refreshSucceeds ? 'completed inbox refresh wins over an older snapshot'
          : 'a failed inbox request must not suppress a valid sidebar snapshot');
    }
  }
  console.log('human interaction attention snapshot ordering checks passed');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
