const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const sse = fs.readFileSync(path.join(root, 'frontend/src/app/modules/sse-handling.js'), 'utf8');
const ref = { attachmentId: 'sha256:' + 'c'.repeat(64), name: 'shot.png', bytes: 2048, mediaType: 'image/png', width: 640, height: 480 };

/* The optimistic user bubble is drawn before /chat starts. It must carry the
   same durable image refs as the persisted user event, otherwise the image
   card only appears after a history replay (page refresh or stream reattach). */
function optimisticRenderBlock() {
  const start = sse.indexOf('const renderAsSteer = !!options.asSteer;');
  const end = sse.indexOf('optimisticRunState.suppressFollowupButton = false;', start);
  assert.ok(start >= 0 && end > start, 'optimistic render block anchors are missing');
  return sse.slice(start, end);
}

function runOptimisticRender(options) {
  options = options || {};
  const calls = { appendMessage: [], applySessionEvent: [], appendSteerProcessMessage: [] };
  const composerAttachments = options.composerAttachments || [];
  const context = vm.createContext({
    options: { asSteer: !!options.asSteer, attachments: options.runAttachments },
    window: {
      MyAgentPathPicker: {
        chatAttachments: () => composerAttachments,
      },
    },
    rawMessage: options.rawMessage || '',
    displayMessage: options.rawMessage || '',
    userSentAt: '2026-10-25T00:00:00Z',
    preCount: 7,
    clientRunId: 'run-1',
    switchedAway: false,
    runCtx: { stream: null },
    runSessionId: 'session-1',
    messageInput: { value: options.rawMessage || '' },
    optimisticRunState: {},
    lastUserMessageBySession: {},
    uiEventCountCache: { updateFromServer() {} },
    reportClientPipelineStep() {},
    nowPipelineMs: () => 1,
    _clientStepStart: 0,
    prepareSteerProcessBoundary() {},
    updateSidebarLastUserPreviewImmediate() {},
    persistInputDraft() {},
    clearInputPathTokens() {},
    autoResizeTextarea() {},
    setSendButtonState() {},
    applySessionEvent(event, opts) { calls.applySessionEvent.push({ event, opts }); },
    appendMessage(ctx, role, content, meta, sid) { calls.appendMessage.push({ ctx, role, content, meta, sid }); },
    appendSteerProcessMessage(sid, ctx, content, opId, mode, pending, attachments) {
      calls.appendSteerProcessMessage.push({ sid, ctx, content, opId, mode, pending, attachments });
      return { dataset: {} };
    },
  });
  vm.runInContext('(function(){' + optimisticRenderBlock() + '})()', context);
  return calls;
}

function attachmentIds(list) {
  return Array.from(list || [], item => item && item.attachmentId);
}

test('the optimistic user bubble carries durable image refs before /chat starts', () => {
  const pathName = 'C:\\work\\shot.png';
  const calls = runOptimisticRender({
    rawMessage: 'look "' + pathName + '"',
    composerAttachments: [{ path: pathName, name: 'shot.png', size: 2048, attachment: ref }],
  });

  assert.equal(calls.appendMessage.length, 1);
  assert.equal(calls.appendMessage[0].role, 'user');
  assert.equal(calls.appendMessage[0].meta.eventIndex, 7);
  assert.deepEqual(Array.from(calls.appendMessage[0].meta.attachments, item => item.attachmentId), [ref.attachmentId]);
  // The in-memory record must match the persisted event shape, not the composer entry.
  assert.deepEqual(Array.from(calls.applySessionEvent[0].event.attachments, item => item.attachmentId), [ref.attachmentId]);
  assert.equal(calls.applySessionEvent[0].opts.source, 'local-send');
});

test('composer uploads whose path left the message are not attached to the bubble', () => {
  const calls = runOptimisticRender({
    rawMessage: 'plain text',
    composerAttachments: [{ path: 'C:\\work\\removed.png', name: 'removed.png', attachment: ref }],
  });

  assert.equal(calls.appendMessage.length, 1);
  assert.equal(calls.appendMessage[0].meta.attachments.length, 0);
  assert.equal(calls.applySessionEvent[0].event.attachments.length, 0);
});

test('queued follow-up runs reuse the run attachments for the optimistic bubble', () => {
  const pathName = 'C:\\work\\queued.png';
  const calls = runOptimisticRender({
    rawMessage: 'queued "' + pathName + '"',
    runAttachments: [{ path: pathName, name: 'queued.png', attachment: ref }],
    composerAttachments: [],
  });

  assert.deepEqual(attachmentIds(calls.appendMessage[0].meta.attachments), [ref.attachmentId]);
});

test('optimistic steer rows receive the same durable image refs', () => {
  const pathName = 'C:\\work\\steer.png';
  const calls = runOptimisticRender({
    asSteer: true,
    rawMessage: 'steer "' + pathName + '"',
    composerAttachments: [{ path: pathName, name: 'steer.png', attachment: ref }],
  });

  assert.equal(calls.appendMessage.length, 0);
  assert.equal(calls.appendSteerProcessMessage.length, 1);
  assert.deepEqual(attachmentIds(calls.appendSteerProcessMessage[0].attachments), [ref.attachmentId]);
});
