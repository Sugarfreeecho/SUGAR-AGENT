const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..', '..');
const source = fs.readFileSync(
  path.join(root, 'frontend', 'src', 'app', 'modules', 'session-management.js'),
  'utf8',
);
const renderingSource = fs.readFileSync(
  path.join(root, 'frontend', 'src', 'app', 'modules', 'message-rendering.js'),
  'utf8',
);
const start = source.indexOf('async function createNewSession(');
assert(start >= 0, 'new-session lifecycle functions are missing');
const lifecycleSource = source.slice(start);
const welcomeSyncStart = renderingSource.indexOf('function syncWelcomeSessionDirectory(');
const welcomeSyncEnd = renderingSource.indexOf('function setWelcome()', welcomeSyncStart);
assert(welcomeSyncStart >= 0 && welcomeSyncEnd > welcomeSyncStart, 'welcome directory renderer is missing');
const welcomeSyncSource = renderingSource.slice(welcomeSyncStart, welcomeSyncEnd);

let fetchCalls = 0;
let postCalls = 0;
let failPrefetch = false;
let releaseCreate;
let restoredRealSession = false;
let createRequestOptions = null;
let committedModelSession = '';
let committedPermissionStatus = null;
const createGate = new Promise((resolve) => { releaseCreate = resolve; });
const directoryName = {
  textContent: '',
  attributes: Object.create(null),
  setAttribute(name, value) { this.attributes[name] = String(value); },
  removeAttribute(name) { delete this.attributes[name]; },
};
const directoryPath = {
  textContent: '',
  title: '',
  setAttribute() {},
  removeAttribute() {},
};
const directoryCard = {
  hidden: true,
  querySelector(selector) {
    if (selector === '[data-welcome-session-directory-name]') return directoryName;
    if (selector === '[data-welcome-session-directory-path]') return directoryPath;
    return null;
  },
};
const stream = {
  querySelector(selector) {
    if (selector === '.welcome-session-directory') return directoryCard;
    if (selector === '.welcome') return {};
    return null;
  },
};
const messageInput = { value: '', focus() {} };
const pendingStorage = new Map();
const legacyStorage = new Map();
let welcomeDirectoryClickHandler = null;
const ctx = vm.createContext({
  console: { warn() {}, error: console.error.bind(console), log: console.log.bind(console) },
  Promise,
  String,
  CustomEvent: function CustomEvent(name, init) { this.name = name; this.detail = init.detail; },
  performance: { now: () => 1 },
  document: {
    dispatchEvent() {},
    addEventListener(type, handler) { if (type === 'click') welcomeDirectoryClickHandler = handler; },
    getElementById() { return null; },
  },
  window: {
    __WORK_DIR__: 'C:\\default-workspace',
    MyAgentPathPicker: { async pickPath() { return ''; } },
  },
  localStorage: {
    getItem(key) { return legacyStorage.get(key) || null; },
    setItem(key, value) { legacyStorage.set(key, value); },
    removeItem(key) { legacyStorage.delete(key); },
  },
  sessionStorage: {
    getItem(key) { return pendingStorage.get(key) || null; },
    setItem(key, value) { pendingStorage.set(key, value); },
    removeItem(key) { pendingStorage.delete(key); },
  },
  NEW_SESSION_DRAFT_KEY: '__new_session_draft__',
  messageInput,
  currentSessionId: 'existing',
  newSessionWorkDir: '',
  newSessionWorkDirRevision: 0,
  materializeNewSessionQueue: null,
  switchSessionEpoch: 0,
  messageLoadEpoch: 0,
  replayingMessages: false,
  cancelSmoothStreamFollowForSessionSwitch() {},
  saveChatScrollForSession() {},
  stashInputDraft() {},
  stashSkillPickerDraft() {},
  prepareStashLeaving() {},
  hideSubagentContinueBanner() {},
  resetSubagentPanelForSession() {},
  clearOptionalPanelsForSessionLoad() {},
  clearTocForSessionLoad() {},
  setCurrentSessionState(sessionId) {
    ctx.currentSessionId = sessionId || null;
    vm.runInContext(`currentSessionId = ${JSON.stringify(sessionId || null)}`, ctx);
  },
  getVisibleChatStream: () => stream,
  ensureVisibleChatStreamSlot() {},
  setWelcome() {},
  restoreInputDraft(sessionId) {
    if (sessionId) restoredRealSession = true;
    else messageInput.value = 'draft text';
  },
  restoreSkillPickerDraft() {},
  renderFollowupQueue() {},
  refreshModelProfileSelector() {},
  updateSessionTitle() {},
  syncSessionListIndicatorClasses() {},
  hideLoading() {},
  setSendButtonState() {},
  sessionStore: {
    protected: null,
    protectFromSnapshots(session) { this.protected = session; },
  },
  newSessionModelProfileId: () => 'profile-fast',
  selectedNewSessionPermissionMode: () => 'approve_for_me',
  commitNewSessionModelProfile(sessionId) { committedModelSession = sessionId; },
  commitNewSessionPermissionMode(status) { committedPermissionStatus = status; },
  readStoredInputDraft: () => 'stored draft',
  persisted: [],
  persistInputDraft(sessionId, value) { ctx.persisted.push([sessionId, value]); },
  removeStoredInputDraft() {},
  updateHumanInteractionBanner() {},
  syncFollowupQueueFromServer() {},
  syncArchivedSessionStateFromStore() {},
  renderSessionListIfChanged() {},
  refreshSingleSessionRow() {},
  loadSessions: async () => true,
  maybeStartStreamPollForSession() {},
  scheduleContextTokensAfterPaint() {},
  uiPerformance: undefined,
  appendLogVisible() {},
  fetch: async (url, options) => {
    fetchCalls += 1;
    if (String(url) === '/sessions/stored-draft' || String(url) === '/sessions/legacy-draft') {
      const id = String(url).split('/').pop();
      return { ok: true, json: async () => ({ id, draft: true, work_dir: 'C:\\default-workspace' }) };
    }
    postCalls += 1;
    createRequestOptions = options;
    if (failPrefetch && JSON.parse(options.body).prefetch) {
      return { ok: false, status: 503 };
    }
    await createGate;
    return {
      ok: true,
      json: async () => ({
        session_id: 'created',
        session: {
          id: 'created',
          name: 'New',
          draft: true,
          work_dir: JSON.parse(options.body).work_dir || 'C:\\default-workspace',
        },
        model_profile_id: 'profile-fast',
        permission_status: { mode: 'approve_for_me' },
      }),
    };
  },
});

vm.runInContext(
  `let materializeNewSessionQueue = null;\n`
    + `let pendingNewSession = null;\nlet prefetchNewSessionPromise = null;\n`
    + `const PENDING_NEW_SESSION_KEY = 'myagent-pending-new-session-id';\n`
    + `${lifecycleSource}\n`
    + `${welcomeSyncSource}\n`
    + 'globalThis.__createNewSession = createNewSession;\n'
    + 'globalThis.__materializeNewSession = materializeNewSession;\n'
    + 'globalThis.__ensurePrefetchedNewSession = ensurePrefetchedNewSession;\n'
    + 'globalThis.__startNewSessionInDir = startNewSessionInDir;',
  ctx,
);

(async () => {
  await ctx.__createNewSession();
  await Promise.resolve();
  assert.strictEqual(fetchCalls, 1, 'opening a new page starts one background prefetch');
  assert.strictEqual(ctx.currentSessionId, null);
  assert.strictEqual(messageInput.value, 'draft text');
  assert.deepStrictEqual(JSON.parse(createRequestOptions.body), {
    prefetch: true,
    model_profile_id: 'profile-fast',
    permission_mode: 'approve_for_me',
  });

  messageInput.value = 'live text must survive';
  const materializing = ctx.__materializeNewSession();
  await Promise.resolve();
  assert.strictEqual(fetchCalls, 1, 'the first send reuses the in-flight prefetch');
  releaseCreate();
  assert.strictEqual(await materializing, 'created');
  assert.strictEqual(messageInput.value, 'live text must survive');
  assert.strictEqual(restoredRealSession, false, 'POST completion must not restore over live input');
  assert.deepStrictEqual(ctx.persisted[0], ['created', 'live text must survive']);
  assert.strictEqual(ctx.sessionStore.protected.id, 'created');
  assert.strictEqual(committedModelSession, 'created');
  assert.deepStrictEqual(committedPermissionStatus, { mode: 'approve_for_me' });
  assert.strictEqual(pendingStorage.size, 0, 'first send clears the pending draft pointer');

  // A reload clears page memory but keeps this tab's sessionStorage. The
  // existing hidden draft must be reused without creating a second session.
  pendingStorage.set('myagent-pending-new-session-id', JSON.stringify({
    session_id: 'stored-draft',
    model_profile_id: 'profile-fast',
    permission_mode: 'approve_for_me',
  }));
  ctx.setCurrentSessionState(null);
  vm.runInContext('pendingNewSession = null; prefetchNewSessionPromise = null;', ctx);
  const restored = await ctx.__ensurePrefetchedNewSession();
  assert.strictEqual(restored.sessionId, 'stored-draft');
  assert.strictEqual(postCalls, 1, 'reload must reuse the stored draft');

  // An existing draft from the previous build is adopted into per-tab storage.
  pendingStorage.clear();
  legacyStorage.set('myagent-pending-new-session-id', JSON.stringify({
    session_id: 'legacy-draft',
  }));
  vm.runInContext('pendingNewSession = null; prefetchNewSessionPromise = null;', ctx);
  const migrated = await ctx.__ensurePrefetchedNewSession();
  assert.strictEqual(migrated.sessionId, 'legacy-draft');
  assert.strictEqual(postCalls, 1, 'migration must reuse the legacy draft');
  assert.strictEqual(legacyStorage.has('myagent-pending-new-session-id'), false);
  assert.strictEqual(pendingStorage.has('myagent-pending-new-session-id'), true);

  pendingStorage.clear();
  vm.runInContext('pendingNewSession = null; prefetchNewSessionPromise = null;', ctx);
  failPrefetch = true;
  await ctx.__createNewSession();
  const fallbackId = await ctx.__materializeNewSession();
  assert.strictEqual(fallbackId, 'created', 'failed prefetch falls back to ordinary creation');
  assert.strictEqual(JSON.parse(createRequestOptions.body).prefetch, undefined);

  // Choosing a directory must put that exact path on the hidden-draft POST;
  // the server fixes a session's work_dir at creation time.
  pendingStorage.clear();
  ctx.setCurrentSessionState(null);
  vm.runInContext(
    'pendingNewSession = null; prefetchNewSessionPromise = null; '
      + 'prefetchNewSessionWorkDir = null; newSessionWorkDir = ""; newSessionWorkDirRevision = 0;',
    ctx,
  );
  failPrefetch = false;
  createRequestOptions = null;
  const chosenWorkDir = 'C:\\selected-workspace';
  await ctx.__startNewSessionInDir(chosenWorkDir);
  assert.strictEqual(JSON.parse(createRequestOptions.body).work_dir, chosenWorkDir);
  assert.strictEqual(
    vm.runInContext('pendingNewSession.workDir', ctx),
    chosenWorkDir,
    'the selected directory remains attached to the pending draft',
  );

  // The welcome-card picker follows the same path and updates the visible path
  // before the asynchronous draft prefetch finishes.
  const cardWorkDir = 'D:\\card-workspace';
  ctx.window.MyAgentPathPicker.pickPath = async () => cardWorkDir;
  const clickEvent = {
    target: {
      closest(selector) {
        return selector === '[data-welcome-session-directory-picker]' ? this : null;
      },
      disabled: false,
    },
    preventDefault() {},
    stopPropagation() {},
  };
  await welcomeDirectoryClickHandler(clickEvent);
  assert.strictEqual(directoryPath.textContent, cardWorkDir);
  assert.strictEqual(directoryName.textContent, 'card-workspace');
  assert.strictEqual(JSON.parse(createRequestOptions.body).work_dir, cardWorkDir);

  process.stdout.write('new session lifecycle runtime checks passed\n');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
