'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const sessions = new Map([
  ['B', { work_dir: 'D:/projects/B' }],
  ['C', { work_dir: 'E:/projects/C' }],
  ['child', { work_dir: 'D:/projects/B', effective_work_dir: 'D:/trees/child/src' }],
]);
const context = {
  URLSearchParams, Map, Set, Number, Object, String, Promise,
  __WORK_DIR__: 'D:/global', currentSessionId: 'B',
  newSessionWorkDir: '', pendingNewSession: null,
  sessionStore: { get: sid => sessions.get(sid) },
  escapeHtmlAttr: value => String(value),
  cleanPathTokenForLink: value => value,
  stripWorkspaceRootPrefixFromRelPath: value => value,
  workspaceRelativePathAutoLinkOk: () => true,
  workspaceRelativePathNoSlashAutoLinkOk: () => true,
  workspaceRelFromNormalizedAbs: () => null,
};
context.window = context;
vm.createContext(context);
vm.runInContext(read('frontend/src/app/config.js').replace(/^export\s+/gm, ''), context);
context.readRuntimeConfig(context);
assert.equal(context.getActiveWorkDir(), 'D:/projects/B');
const requestB = context.getWorkspaceRequestContext();
assert.match(context.workspaceApiUrl('/api/workspace-files'), /session_id=B/);
assert.equal(context.workspaceAbsolutePath('same.png'), 'D:/projects/B/same.png');
assert.equal(context.workspaceAbsolutePath('.config/history-media/hash.png'), 'D:/global/.config/history-media/hash.png');
const rendering = read('frontend/src/app/modules/message-rendering.js');
const start = rendering.indexOf('function pathTokenToWorkspaceOpenRel(');
const end = rendering.indexOf('\nfunction decodeMarkdownHrefPathTarget(', start);
vm.runInContext(rendering.slice(start, end), context);
assert.equal(context.pathTokenToWorkspaceOpenRel('D:/projects/B/same.png'), 'D:/projects/B/same.png');
assert.equal(context.pathTokenToWorkspaceOpenRel('same.png'), 'D:/projects/B/same.png');
context.markdownHrefToWorkspaceOpenRel = context.pathTokenToWorkspaceOpenRel;
vm.runInContext(read('frontend/src/app/modules/workspace-media.js'), context);
context.workspaceImageMetadataCache.set('D:/projects/B/same.png', { width: 20, height: 30 });
const imageB = context.workspaceMarkdownImageHtml({ href: 'same.png', text: 'B' });
assert.match(imageB, /width="20"/);
assert.match(imageB, /D:\/projects\/B\/same.png/);
context.currentSessionId = 'C';
const imageC = context.workspaceMarkdownImageHtml({ href: 'same.png', text: 'C' });
assert.ok(!imageC.includes('width="20"'));
assert.match(imageC, /E:\/projects\/C\/same.png/);
assert.equal(context.workspaceAbsolutePath('same.png', requestB), 'D:/projects/B/same.png');
assert.match(context.workspaceAssetUrl('site/page.html', requestB), /^\/api\/sessions\/B\/workspace-assets\/D%3A\/projects\/B\/site\/page.html$/);
context.currentSessionId = 'child';
assert.equal(context.getActiveWorkDir(), 'D:/trees/child/src');
sessions.delete('child');
context.subagentCatalogStore = { getAddress: () => ({ parentSessionId: 'B' }),
  entriesOf: () => [{ childId: 'child', raw: { effective_work_dir: 'D:/trees/child/src' } }] };
assert.equal(context.getActiveWorkDir(), 'D:/trees/child/src');
context.currentSessionId = '';
context.newSessionWorkDir = 'D:/draft';
assert.equal(context.getActiveWorkDir(), 'D:/draft');
assert.match(context.workspaceApiUrl('/api/workspace-files'), /work_dir=D%3A%2Fdraft/);
console.log('session workspace frontend checks passed');
