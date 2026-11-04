import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { BrowserEngine, ALLOWED_TOOLS } from '../engine.mjs';
import { BrowserRelay } from '../relay.mjs';

test('catalog preserves upstream actions and adds one read-only browser context tool', async () => {
  const engine = new BrowserEngine({ generation: 0 });
  try {
    const catalog = await engine.catalog();
    assert.ok(catalog.length > 10);
    assert.ok(catalog.every(tool => ALLOWED_TOOLS.has(tool.name)));
    assert.ok(!catalog.some(tool => ['browser_action', 'browser_files', 'browser_evaluate', 'browser_run_code'].includes(tool.name)));
    const tabs = catalog.find(tool => tool.name === 'browser_tabs');
    assert.deepEqual(tabs.inputSchema.properties.action.enum, ['list', 'new', 'close', 'select']);
    const context = catalog.find(tool => tool.name === 'browser_get_context');
    assert.equal(context.annotations.readOnlyHint, true);
    assert.deepEqual(context.inputSchema.properties, {});
  } finally { await engine.close(); }
});

test('relay requires both the extension origin and an unguessable connection token', async () => {
  const require = createRequire(import.meta.url);
  const { ws: WebSocket } = require('playwright-core/lib/utilsBundle');
  const relay = new BrowserRelay({ token: 'private-fixture-token', allowedOrigin: 'chrome-extension://fixture' });
  await relay.start();
  try {
    for (const [token, origin] of [['wrong-token', 'chrome-extension://fixture'], ['private-fixture-token', 'https://untrusted.test']]) {
      const rejected = await new Promise(resolve => {
        const socket = new WebSocket(`ws://127.0.0.1:${relay.port}/extension?token=${token}`, { origin });
        socket.on('error', error => resolve(error.message));
        socket.on('open', () => { socket.close(); resolve('unexpectedly opened'); });
      });
      assert.match(rejected, /403/);
    }
    assert.equal(relay.initialized, false);
  } finally { await relay.close(); }
});

test('cancelling an in-flight context read cannot leave a new run binding', async () => {
  let resolveContext, started;
  const entered=new Promise(resolve=>started=resolve);
  const relay={generation:1,browserContext:()=>{started();return new Promise(resolve=>resolveContext=resolve);}};
  const engine=new BrowserEngine(relay,{contextGetter:async()=>({pages:()=>[]})});
  engine.getClient=async()=>({selectedPage:null});
  const pending=engine.call({session_id:'session',run_id:'run',tool:'browser_get_context'});
  await entered;engine.cancel('run');resolveContext({page:null,status:'unavailable'});
  await assert.rejects(pending,/run_cancelled/);assert.equal(engine.runPages.has('run'),false);
});
