const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../frontend/src/app/modules/message-rendering.js'), 'utf8');
const helpers = source.slice(source.indexOf('async function historyOperationJson'), source.indexOf('function hasPreviousUserMessageBefore'));

function context(fetch, extra = {}) {
  const ctx = vm.createContext({ console, fetch, AbortController, Date, Map, Promise,
    setTimeout, clearTimeout, currentSessionId: 's1',
    window: { crypto: { randomUUID: () => 'request-unique-1' } }, ...extra });
  vm.runInContext(helpers, ctx);
  return ctx;
}
const reply = (body) => ({ ok: true, json: async () => body });

async function main() {
  {
    const calls = [];
    const responses = [{ ok: true, status: 'pending' }, { ok: true, status: 'completed' }];
    const ctx = context(async (url, options) => { calls.push([url, options.method]); return reply(responses.shift()); });
    const result = await ctx.truncateSessionOnServer(2, { beforeSeq: 10 });
    assert.equal(result.ok, true);
    assert.equal(calls[0][1], 'POST');
    assert.equal(calls[1][1], 'GET');
    assert(calls[0][0].includes('request_id=request-unique-1'));
  }
  {
    let posts = 0, reads = 0;
    const ctx = context(async (_url, options) => {
      if (options.method === 'POST') { posts++; const e = new Error('aborted'); e.name = 'AbortError'; throw e; }
      reads++;
      return reply({ ok: true, status: 'completed' });
    });
    assert.equal((await ctx.truncateSessionOnServer(2, {})).ok, true);
    assert.equal(posts, 1); assert.equal(reads, 1);
  }
  {
    let posts = 0, reads = 0;
    const ctx = context(async (_url, options) => {
      if (options.method === 'POST') { posts++; throw new Error('connection reset'); }
      reads++;
      return reply({ ok: false, status: 'unknown', error: 'truncate_result_unknown' });
    });
    const first = await ctx.truncateSessionOnServer(2, {});
    assert.equal(first.error, 'truncate_result_unknown');
    const second = await ctx.truncateSessionOnServer(2, {});
    assert.equal(second.ok, false);
    assert.equal(posts, 1, 'retry must never resubmit an inconclusive destructive edit');
    assert.equal(reads, 2);
    assert(!ctx.describeServerSyncFailure(first, '改写未生效').includes('改写未生效'));
  }
  {
    let release, posts = 0;
    const gate = new Promise(resolve => { release = resolve; });
    const ctx = context(async (_url, options) => {
      if (options.method === 'POST') { posts++; await gate; return reply({ ok: true, status: 'pending' }); }
      return reply({ ok: true, status: 'completed' });
    });
    const a = ctx.truncateSessionOnServer(2, {}), b = ctx.truncateSessionOnServer(2, {});
    release();
    assert.equal((await a).ok, true); assert.equal((await b).ok, true);
    assert.equal(posts, 1);
  }
  {
    const ctx = context(async () => ({ ok: true, json: async () => { throw new Error('bad json'); } }));
    const result = await ctx.historyOperationJson('/test', {}, 10);
    assert.equal(result.ok, false);
    assert.equal(result.error, 'invalid_server_response');
  }
  {
    let clock = 0, posts = 0, completed = false;
    const ctx = context(async (_url, options) => {
      if (options.method === 'POST') posts++;
      return reply({ ok: true, status: completed ? 'completed' : 'pending' });
    }, {
      Date: { now: () => clock },
      setTimeout(resolve, delay) { clock += delay; resolve(); }, clearTimeout() {},
    });
    const result = await ctx.truncateSessionOnServer(2, { timeoutMs: 500 });
    assert.equal(result.ok, false);
    assert.equal(result.error, 'truncate_result_pending');
    assert(!ctx.describeServerSyncFailure(result, '改写未生效').includes('改写未生效'));
    completed = true;
    assert.equal((await ctx.truncateSessionOnServer(2, { timeoutMs: 500 })).ok, true);
    assert.equal(posts, 1, 'retry after the waiting limit must only read the existing receipt');
  }
  {
    let posts = 0;
    const ctx = context(async (_url, options) => {
      if (options.method === 'POST') { posts++; throw new Error('lost acknowledgement'); }
      return { ok: false, status: 404, json: async () => ({ detail: 'Not Found' }) };
    });
    assert.equal((await ctx.truncateSessionOnServer(2, {})).error, 'truncate_result_unknown');
    assert.equal(posts, 1);
  }
  {
    let clock = 0, posts = 0;
    const ctx = context(async (_url, options) => {
      if (options.method === 'POST') { posts++; return reply({ ok: true, status: 'pending' }); }
      clock += 20000;
      return reply({ ok: true, status: clock > 45000 ? 'completed' : 'pending' });
    }, {
      Date: { now: () => clock },
      setTimeout(resolve, delay) { if (delay === 1000) { clock += delay; resolve(); } return 1; },
      clearTimeout() {},
    });
    assert.equal((await ctx.truncateSessionOnServer(2, {})).ok, true);
    assert(clock > 45000, 'long-running truncation must recover beyond the old 45s limit');
    assert.equal(posts, 1);
  }
  {
    // 停止是异步的：服务端先回 run_active，客户端必须用同一个 request_id 有界重试，
    // 否则用户点一次发送就被 409 打断。
    let clock = 0, posts = 0, ids = new Set();
    const ctx = context(async (url, options) => {
      if (options.method !== 'POST') return reply({ ok: true, status: 'completed' });
      posts++;
      ids.add((url.match(/request_id=([^&]+)/) || [])[1]);
      if (posts < 3) return { ok: false, status: 409, json: async () => ({ ok: false, error: 'run_active', retry_after_ms: 1200 }) };
      return reply({ ok: true, status: 'pending' });
    }, {
      Date: { now: () => clock },
      // 只让"重试等待"推进假时钟；请求超时计时器不推进，否则一次 POST 就把
      // 20s 的重试窗口耗尽。
      setTimeout(resolve, delay) { if (delay <= 3000) { clock += delay; resolve(); } return 1; },
      clearTimeout() {},
    });
    const result = await ctx.truncateSessionOnServer(2, {});
    assert.equal(result.ok, true);
    assert.equal(posts, 3, 'run_active must be retried, not surfaced immediately');
    assert.equal(ids.size, 1, 'the retry must reuse the same request receipt');
    assert(ctx.describeServerSyncFailure({ error: 'run_active' }, '改写未生效').includes('停止'));
  }
  {
    // 重试窗口用完仍被拒：返回可读原因，且不把这次收据留成"已完成"，
    // 让用户停掉任务后还能重新发起。
    let clock = 0, posts = 0;
    const ctx = context(async () => {
      if (clock >= 0) posts++;
      return { ok: false, status: 409, json: async () => ({ ok: false, error: 'run_active', retry_after_ms: 3000 }) };
    }, {
      Date: { now: () => clock },
      setTimeout(resolve, delay) { if (delay <= 3000) { clock += delay; resolve(); } return 1; },
      clearTimeout() {},
    });
    const first = await ctx.truncateSessionOnServer(2, {});
    assert.equal(first.error, 'run_active');
    const message = ctx.describeServerSyncFailure(first, '改写未生效');
    assert(message.includes('运行'), 'the failure must explain the running turn');
    assert(message.includes('停止'), 'the failure must tell the user how to proceed');
    const postsBefore = posts;
    const second = await ctx.truncateSessionOnServer(2, {});
    assert.equal(second.error, 'run_active');
    assert(posts > postsBefore, 'a later attempt must submit again, not poll a stale receipt');
  }
  console.log('truncate reliability runtime: 10 scenarios passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
