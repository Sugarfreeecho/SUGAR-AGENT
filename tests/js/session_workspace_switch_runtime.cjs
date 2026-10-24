'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const source = read('frontend/src/app/modules/session-management.js');

function environment() {
  const sessions = new Map([['S', { id: 'S', name: 'History', work_dir: 'D:/old' }]]);
  const calls = [];
  const ctx = { console, String, Promise, JSON, Object, Set, Map, Number,
    currentSessionId: 'S',
    sessionStore: { get: id => sessions.get(id) },
    pickNewSessionWorkDir: async initial => { calls.push(['pick', initial]); return 'E:/new'; },
    beginSidebarMetadataMutation: () => 7,
    commitSidebarMetadataMutation: (token, payload) => calls.push(['commit', token, payload.state_revision]),
    cancelSidebarMetadataMutation: token => calls.push(['cancel', token]),
    fetchWithTimeout: async (url, options) => {
      calls.push(['put', url, JSON.parse(options.body)]);
      return { ok: true, json: async () => ({ ok: true, state_revision: 9,
        session: { id: 'S', work_dir: 'E:/new', effective_work_dir: 'E:/new' } }) };
    },
    applyOptimisticSessionUpdate: (id, patch) => sessions.set(id, { ...sessions.get(id), ...patch }),
    getActiveWorkDir: () => sessions.get('S').effective_work_dir || sessions.get('S').work_dir,
    updateSessionTitle: () => calls.push(['title']),
    dockRightHandleSessionSwitch: id => calls.push(['files', id]),
    openUiModal: async options => calls.push(['error', options.message]),
    document: { dispatchEvent: event => calls.push(['event', event.type]) },
    CustomEvent: function(type, init) { this.type = type; this.detail = init.detail; },
  };
  vm.createContext(ctx);
  vm.runInContext(read('frontend/src/app/state/session-actions.js'), ctx);
  vm.runInContext(read('frontend/src/app/state/session-event-reducer.js'), ctx);
  vm.runInContext(source.slice(source.indexOf('async function changeSessionWorkDirFromMenu('),
    source.indexOf('async function renameSessionFromMenu(')), ctx);
  return { ctx, calls, sessions };
}

test('existing conversation menu switches in place and refreshes active workspace', async () => {
  const {ctx, calls, sessions} = environment();
  assert.match(source, /class="session-menu-workdir"[^>]*>切换工作区/);
  await ctx.changeSessionWorkDirFromMenu(sessions.get('S'));
  assert.deepEqual(calls[0], ['pick', 'D:/old']);
  assert.deepEqual(calls[1], ['put', '/sessions/S/work-dir', {work_dir: 'E:/new'}]);
  assert.equal(sessions.get('S').name, 'History');
  assert.equal(sessions.get('S').effective_work_dir, 'E:/new');
  assert.ok(calls.some(call => call[0] === 'files' && call[1] === 'S'));
  assert.ok(calls.some(call => call[0] === 'commit' && call[2] === 9));
});

test('failed and cancelled switches preserve the previous directory', async () => {
  const {ctx, calls, sessions} = environment();
  ctx.fetchWithTimeout = async () => ({ok: false, json: async () => ({error: '会话正在执行'})});
  await ctx.changeSessionWorkDirFromMenu(sessions.get('S'));
  assert.equal(sessions.get('S').work_dir, 'D:/old');
  assert.ok(calls.some(call => call[0] === 'error' && call[1] === '会话正在执行'));
  assert.ok(calls.some(call => call[0] === 'cancel'));
  calls.length = 0;
  ctx.pickNewSessionWorkDir = async () => null;
  await ctx.changeSessionWorkDirFromMenu(sessions.get('S'));
  assert.equal(calls.length, 0);
});

test('agent event merges metadata and refreshes the current directory', () => {
  const {ctx, calls, sessions} = environment();
  const result = ctx.applySessionEvent({type: 'session_work_dir_changed', ephemeral: true,
    session_id: 'S', session: {id: 'S', work_dir: 'E:/new', effective_work_dir: 'E:/new'}});
  assert.equal(result.handled, true);
  assert.equal(sessions.get('S').name, 'History');
  assert.equal(sessions.get('S').work_dir, 'E:/new');
  assert.ok(calls.some(call => call[0] === 'files'));
});

test('file tree reloads when the same session changes its root', () => {
  const {ctx} = environment();
  const column = read('frontend/src/app/modules/dock/embedder/right-column.js');
  let reloads = 0;
  ctx.dockRightState = {workSessionId: 'S', workDir: 'D:/old', sessionId: 'S',
    host: {querySelectorAll: () => [{__dockWorkspaceReload: () => reloads++}]}};
  ctx.dockRightSurfaceKey = id => id;
  ctx.getActiveWorkDir = () => 'E:/new';
  vm.runInContext(column.slice(column.indexOf('function dockRightHandleSessionSwitch('),
    column.indexOf('function dockRightWatchSessions(')), ctx);
  ctx.dockRightHandleSessionSwitch('S');
  assert.equal(reloads, 1);
  ctx.dockRightHandleSessionSwitch('S');
  assert.equal(reloads, 1);
});
