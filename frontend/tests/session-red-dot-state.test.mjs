/**
 * A failure dot must disappear once the server snapshot no longer reports the
 * failure: a leaked metadata mutation or an inherited local failure used to
 * keep `unread_result_status='failed'` forever on an otherwise healthy session.
 *
 * Run: node tests/session-red-dot-state.test.mjs
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const storeSource = readFileSync(new URL('../src/app/state/session-store.js', import.meta.url), 'utf8');
const storeContext = vm.createContext({
    console,
    Date,
    localStorage: { getItem: () => null, setItem: () => {} },
});
vm.runInContext(`${storeSource}\nthis.sessionStore = sessionStore;`, storeContext);
const store = storeContext.sessionStore;

// 1. A failure the incoming snapshot no longer asserts must not be inherited.
const cleared = store.inheritUnreadResult(
    { id: 's1', unread_result: false, unread_result_status: 'success' },
    { id: 's1', unread_result: true, unread_result_status: 'failed', unread_result_run_id: 'run-old' }
);
assert.equal(cleared.unread_result_status, undefined, 'inherited success must drop the stale failure');
assert.equal(cleared.unread_result, false, 'inherited success must not keep the unread failure flag');

// 2. An explicit failure snapshot still wins.
const kept = store.inheritUnreadResult(
    { id: 's2', unread_result: true, unread_result_status: 'failed' },
    { id: 's2', unread_result: true, unread_result_status: 'failed', unread_result_run_id: 'run-x' }
);
assert.equal(kept.unread_result_status, 'failed', 'an explicit failure snapshot must still inherit the failure');

// 3. A leaked metadata mutation expires instead of rejecting every snapshot forever.
const token = store.beginMetadataMutation();
assert.equal(store.shouldAcceptSnapshot({}), false, 'a fresh mutation still defers snapshots');
store.metadataMutationStartedAt.set(token, Date.now() - 60000);
assert.equal(store.shouldAcceptSnapshot({}), true, 'an expired mutation must not block snapshots');

// 4. Reconcile keeps the server's success for a newer run generation.
const reconciled = store.reconcileSessionUnreadResult(
    {
        id: 's3',
        unread_result: false,
        unread_result_status: 'success',
        unread_result_run_id: 'run-new',
        unread_result_run_order: 9,
    },
    {
        id: 's3',
        unread_result: true,
        unread_result_status: 'failed',
        unread_result_run_id: 'run-old',
        unread_result_run_order: 5,
    }
);
assert.equal(reconciled.unread_result_status, 'success', 'server success must survive reconciliation');

// 5. A newer run's success terminal clears the dot; the failed run's own replay does not.
const sharedSource = readFileSync(
    new URL('../src/app/modules/shared-state-and-dialogs.js', import.meta.url),
    'utf8'
);
const start = sharedSource.indexOf('function markSessionResultComplete(');
const end = sharedSource.indexOf('\nfunction ', start + 10);
assert.ok(start >= 0 && end > start, 'markSessionResultComplete must be findable');

function buildHarness(session) {
    const context = vm.createContext({
        console,
        Date,
        sessionUnreadClearInFlight: Object.create(null),
        sessionUnreadComplete: new Set(),
        sessionStore: {
            get: () => session,
            resolveSessionResult: (_sid, _rid, status) => status,
            recordConfirmedResult: () => 'failed',
        },
        persistSessionUnread: () => {},
        syncSessionListIndicatorClasses: () => {},
    });
    vm.runInContext(
        `${sharedSource.slice(start, end)}\nthis.markSessionResultComplete = markSessionResultComplete;`,
        context
    );
    return context;
}

const newer = { unread_result: true, unread_result_status: 'failed', unread_result_run_id: 'run-old' };
buildHarness(newer).markSessionResultComplete('s4', 'success', 'run-new', 9);
assert.equal(newer.unread_result_status, 'success', "a newer run's success must clear the failure");

const replay = { unread_result: true, unread_result_status: 'failed', unread_result_run_id: 'run-old' };
buildHarness(replay).markSessionResultComplete('s5', 'success', 'run-old', 5);
assert.equal(replay.unread_result_status, 'failed', 'the failed run replay must not clear the failure');

console.log('Session red-dot state: snapshot success clears stale failure; leaked mutations expire.');
