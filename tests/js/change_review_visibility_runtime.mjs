import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const sourceUrl = new URL('../../plugins/change-review/web/change-review.js', import.meta.url);
const source = await readFile(sourceUrl, 'utf8');
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const { chooseVisibleChangeReviewIndex, pickReviewedTurnKey, viewportFallbackAllowed } = await import(moduleUrl);

// 审查关联以「正在查看的轮」为准；查看轮未知时退回最新轮。
assert.equal(pickReviewedTurnKey('5', '9'), '5');
assert.equal(pickReviewedTurnKey('', '9'), '9');
assert.equal(pickReviewedTurnKey(null, ''), '');

// “过程框收起也关联显示”的兜底仅当正在查看的轮就是最新轮时生效；切到别的轮次 → 收起。
assert.equal(viewportFallbackAllowed('5', '9'), false);
assert.equal(viewportFallbackAllowed('9', '9'), true);
assert.equal(viewportFallbackAllowed('', '9'), true);
assert.equal(viewportFallbackAllowed('9', ''), false);

assert.equal(chooseVisibleChangeReviewIndex([]), -1);
assert.equal(chooseVisibleChangeReviewIndex([
    { visibleHeight: 0, ratio: 0, centerDistance: 0, recency: 2 },
    { visibleHeight: 120, ratio: 1, centerDistance: 0.2, recency: 1 },
]), 1);

// A fully visible execution process should beat one that is only partially visible.
assert.equal(chooseVisibleChangeReviewIndex([
    { visibleHeight: 320, ratio: 0.5, centerDistance: 0, recency: 2 },
    { visibleHeight: 120, ratio: 1, centerDistance: 0.2, recency: 1 },
]), 1);

// If two expanded processes are equally visible, bind the review to the one
// nearest the center of the reader's viewport.
assert.equal(chooseVisibleChangeReviewIndex([
    { visibleHeight: 120, ratio: 1, centerDistance: 0.35, recency: 2 },
    { visibleHeight: 120, ratio: 1, centerDistance: 0.05, recency: 1 },
]), 1);

// Exact geometry ties stay on the current process to avoid flickering.
assert.equal(chooseVisibleChangeReviewIndex([
    { visibleHeight: 120, ratio: 1, centerDistance: 0.1, preferred: true, recency: 1 },
    { visibleHeight: 120, ratio: 1, centerDistance: 0.1, preferred: false, recency: 2 },
]), 0);

console.log('change review visibility runtime checks passed');
