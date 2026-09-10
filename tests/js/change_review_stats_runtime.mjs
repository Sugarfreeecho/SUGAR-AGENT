import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const sourceUrl = new URL('../../plugins/change-review/web/change-review.js', import.meta.url);
const source = await readFile(sourceUrl, 'utf8');
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const { stats, hasLineStats, acceptChangeUpdate, splitReviewRows } = await import(moduleUrl);

// A null added/removed pair must count as "not measured", not as zero.
assert.equal(hasLineStats({ added: null, removed: null }), false);
assert.equal(hasLineStats({ added: null, removed: 0 }), false);
assert.equal(hasLineStats({ added: 0, removed: 0 }), true);
assert.equal(hasLineStats({ added: 3, removed: 1 }), true);

assert.deepEqual(
    stats([{ added: 3, removed: 1 }, { added: 0, removed: 0 }]),
    { added: 3, removed: 1, omitted: 0, reasons: {} },
);

// Binary / oversized / complex / missing-baseline rows are omitted with a
// reason breakdown instead of silently contributing "0" lines.
const mixed = stats([
    { added: 3, removed: 1 },
    { added: null, removed: null, diff_omitted_reason: 'binary' },
    { added: null, removed: null, diff_omitted_reason: 'too_large_bytes' },
    { added: null, removed: null, diff_omitted_reason: 'snapshot_missing' },
    { added: null, removed: null, diff_omitted_reason: 'too_complex' },
    // A directory row carries explicit zeroes and must stay out of "omitted".
    { added: 0, removed: 0, diff_omitted_reason: 'directory' },
]);
assert.equal(mixed.added, 3);
assert.equal(mixed.removed, 1);
assert.equal(mixed.omitted, 4);
assert.deepEqual(mixed.reasons, {
    binary: 1, too_large_bytes: 1, snapshot_missing: 1, too_complex: 1,
});

// A newer run's record (lower revision, new snapshot) must replace the old
// one; only a stale event for the same snapshot may be ignored.
assert.equal(acceptChangeUpdate(null, { snapshot_id: 'a', revision: 1 }), true);
assert.equal(acceptChangeUpdate(
    { snapshot_id: 'a', revision: 2 }, { snapshot_id: 'a', revision: 1 }), false);
assert.equal(acceptChangeUpdate(
    { snapshot_id: 'a', revision: 1 }, { snapshot_id: 'a', revision: 2 }), true);
assert.equal(acceptChangeUpdate(
    { snapshot_id: 'a', revision: 2 }, { snapshot_id: 'b', revision: 1 }), true);

// Reverted rows split away from active rows so the panel can offer restore.
const split = splitReviewRows([
    { snapshot_id: 'a', reverted: false },
    { snapshot_id: 'b', reverted: true },
    { snapshot_id: 'c' },
]);
assert.deepEqual(split.active.map(row => row.snapshot_id), ['a', 'c']);
assert.deepEqual(split.reverted.map(row => row.snapshot_id), ['b']);
assert.deepEqual(splitReviewRows(null), { active: [], reverted: [] });

console.log('change review stats runtime checks passed');
