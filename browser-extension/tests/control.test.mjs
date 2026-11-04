import test from 'node:test';
import assert from 'node:assert/strict';
import { controlResult } from '../src/control.mjs';

test('control envelopes and mutation receipts reject failures before UI commits', () => {
  assert.deepEqual(controlResult({ ok: true, data: { session_id: 'created', accepted: true, status: 'succeeded', error: null } }),
    { session_id: 'created', accepted: true, status: 'succeeded', error: null });
  assert.throws(() => controlResult({ ok: false, error: { message: 'not authorized' } }), /not authorized/);
  assert.throws(() => controlResult({ ok: true, data: { accepted: false, status: 'rejected', error: { message: 'write rejected' } } }), /write rejected/);
  assert.throws(() => controlResult({ ok: true, data: { status: 'failed', error: { message: 'save failed' } } }), /save failed/);
  assert.deepEqual(controlResult({ profiles: [] }), { profiles: [] });
});
