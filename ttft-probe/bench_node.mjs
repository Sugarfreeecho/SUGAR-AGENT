// Local-range bench: N sequential requests on one warm connection, raw fetch.
// Env: BENCH_URL, BENCH_N, BENCH_SHAPE, BENCH_WARMUP
const URL_ = process.env.BENCH_URL
const N = Number(process.env.BENCH_N || 200)
const WARMUP = Number(process.env.BENCH_WARMUP || 5)

function body() {
  return {
    model: 'bench',
    messages: [{ role: 'user', content: 'ping' }],
    stream: true,
    stream_options: { include_usage: true },
    thinking: { type: 'enabled' },
    reasoning_effort: 'max',
    max_tokens: 256000,
  }
}

function headers() {
  return {
    authorization: 'Bearer bench',
    'content-type': 'application/json',
    accept: 'text/event-stream',
    'user-agent': 'deepseek-harness/0.1.5-rc.2 (+https://github.com/deepseek-ai/deepseek-harness)',
  }
}

// A faithful TTFT needs incremental reads, so do the real measurement with a
// streamed body while still draining to the end.
async function oneStreamed() {
  const t0 = performance.now()
  const res = await fetch(URL_, { method: 'POST', headers: headers(), body: JSON.stringify(body()) })
  const tHeaders = performance.now()
  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  let ttft = null
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    if (ttft === null) {
      buf += dec.decode(value, { stream: true })
      let nl
      while ((nl = buf.indexOf('\n')) !== -1) {
        const line = buf.slice(0, nl).trim()
        buf = buf.slice(nl + 1)
        if (!line.startsWith('data:')) continue
        const payload = line.slice(5).trim()
        if (!payload || payload === '[DONE]') continue
        try {
          const d = JSON.parse(payload)?.choices?.[0]?.delta
          if (d && (d.reasoning_content || d.reasoning || d.content)) { ttft = performance.now(); break }
        } catch {}
      }
    }
  }
  const tDone = performance.now()
  return { ttft: ttft === null ? null : ttft - t0, t_headers: tHeaders - t0, total: tDone - t0 }
}

for (let i = 0; i < WARMUP; i++) await oneStreamed()
const rows = []
for (let i = 0; i < N; i++) rows.push(await oneStreamed())
const ttfts = rows.map(r => r.ttft).filter(v => v !== null)
const hdrs = rows.map(r => r.t_headers)
const totals = rows.map(r => r.total)
const q = (a, p) => { const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(p * s.length))] }
const mean = a => a.reduce((x, y) => x + y, 0) / a.length
const sd = a => { const m = mean(a); return Math.sqrt(a.reduce((x, y) => x + (y - m) ** 2, 0) / (a.length - 1)) }
console.log(JSON.stringify({
  stack: 'node-fetch', n: ttfts.length,
  ttft: { mean: mean(ttfts), p50: q(ttfts, 0.5), p90: q(ttfts, 0.9), min: Math.min(...ttfts), max: Math.max(...ttfts), sd: sd(ttfts) },
  headers: { mean: mean(hdrs), sd: sd(hdrs) },
  total: { mean: mean(totals), sd: sd(totals) },
  samples: ttfts.slice(0, 20),
}))
