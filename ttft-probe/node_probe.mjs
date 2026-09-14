// TTFT probe: raw fetch + hand-rolled SSE, the way DSH's dsh-llm-deepseek adapter does it.
//
// Env contract:
//   PROBE_SHAPE       dsh | myagent
//   PROBE_BASE_URL    e.g. https://api.commandcode.ai/provider/v1
//   PROBE_API_KEY
//   PROBE_MODEL
//   PROBE_PROMPT
//   PROBE_MAX_TOKENS  number, or empty for "omit"
//   PROBE_TIMEOUT_MS
//   PROBE_GRACE_MS    how long to keep reading after the first delta (then abort)
//   PROBE_WARM        "1" to issue a throwaway request first (warm connection)
//
// Prints exactly one JSON line.

const env = process.env
const SHAPE = env.PROBE_SHAPE || 'dsh'
const BASE = (env.PROBE_BASE_URL || '').replace(/\/+$/, '')
const KEY = env.PROBE_API_KEY || ''
const MODEL = env.PROBE_MODEL || ''
const PROMPT = env.PROBE_PROMPT || 'hi'
const MAX_TOKENS = env.PROBE_MAX_TOKENS ? Number(env.PROBE_MAX_TOKENS) : undefined
const TIMEOUT_MS = Number(env.PROBE_TIMEOUT_MS || 120000)
const GRACE_MS = Number(env.PROBE_GRACE_MS || 250)
const WARM = env.PROBE_WARM === '1'

const URL_ = `${BASE}/chat/completions`

const SESSION_HEX = '6d1f4b2e8a90c3'

function buildMyAgent() {
  return {
    headers: {
      'content-type': 'application/json',
      'accept': 'application/json',
      Authorization: `Bearer ${KEY}`,
      // model_profiles.json -> profile["headers"], sent verbatim
      'x-opencode-client': 'myagent',
      'x-opencode-session': `ses-myagent-${SESSION_HEX}`,
      'x-opencode-project': 'myagent-workspace',
      'x-opencode-request': 'req-myagent-0a3c9e1d7f52',
      'User-Agent': 'my-coding-agent/1.0',
    },
    body: {
      model: MODEL,
      messages: [{ role: 'user', content: PROMPT }],
      max_tokens: MAX_TOKENS,
      parallel_tool_calls: true,          // always sent by the streaming worker
      stream: true,
      stream_options: { include_usage: true },
      temperature: 0.7,                   // EXECUTOR_TEMPERATURE default
      thinking: { type: 'enabled' },      // profile extra_body_json -> thinking_mode=enabled
      reasoning_effort: 'max',            // profile reasoning_effort
    },
  }
}

function buildDsh() {
  return {
    headers: {
      authorization: `Bearer ${KEY}`,
      'content-type': 'application/json',
      // DSH sends an SSE accept; the OpenAI Python SDK sends application/json
      // on a streaming request, so this is the single-variable probe for it.
      accept: process.env.PROBE_ACCEPT_JSON === '1' ? 'application/json' : 'text/event-stream',
      'user-agent': 'deepseek-harness/0.1.5-rc.2 (+https://github.com/deepseek-ai/deepseek-harness)',
      'x-deepseek-harness-user-id': '00000000-0000-4000-8000-000000000000',
      'x-deepseek-harness-session-id': '1',
    },
    body: {
      model: MODEL,
      messages: [{ role: 'user', content: PROMPT }],
      stream: true,
      stream_options: { include_usage: true },
      thinking: { type: 'enabled' },
      reasoning_effort: 'max',
      ...(MAX_TOKENS === undefined ? {} : { max_tokens: MAX_TOKENS }),
    },
  }
}

function firstDeltaKind(delta) {
  if (!delta) return null
  if (delta.reasoning_content) return 'reasoning_content'
  if (delta.reasoning) return 'reasoning'
  if (delta.content) return 'content'
  if (Array.isArray(delta.tool_calls) && delta.tool_calls.length) return 'tool_calls'
  return null
}

async function oneRequest() {
  const { headers, body } = SHAPE === 'myagent' ? buildMyAgent() : buildDsh()
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)

  const t0 = performance.now()
  let res
  try {
    res = await fetch(URL_, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: controller.signal,
    })
  } catch (err) {
    clearTimeout(timer)
    return { ok: false, error: `transport: ${err?.message || err}`, ttft_ms: null }
  }
  const tHeaders = performance.now()

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    clearTimeout(timer)
    return {
      ok: false,
      http_status: res.status,
      error: text.slice(0, 600),
      t_headers_ms: +(tHeaders - t0).toFixed(1),
    }
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  let tFirstByte = null
  let tFirstDelta = null
  let firstKind = null
  let nEvents = 0
  let sawDone = false
  let aborted = false

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const now = performance.now()
      if (tFirstByte === null) tFirstByte = now
      buf += decoder.decode(value, { stream: true })

      let nl
      while ((nl = buf.indexOf('\n')) !== -1) {
        const line = buf.slice(0, nl).trim()
        buf = buf.slice(nl + 1)
        if (!line.startsWith('data:')) continue
        const payload = line.slice(5).trim()
        if (!payload || payload === '[DONE]') {
          if (payload === '[DONE]') sawDone = true
          continue
        }
        nEvents++
        let ev
        try { ev = JSON.parse(payload) } catch { continue }
        if (tFirstDelta === null) {
          const delta = ev?.choices?.[0]?.delta
          const kind = firstDeltaKind(delta)
          if (kind || (Array.isArray(ev?.choices) && ev.choices[0]?.message)) {
            tFirstDelta = now
            firstKind = kind || 'complete_message'
          }
        }
      }
      if (tFirstDelta !== null && now - tFirstDelta > GRACE_MS) {
        aborted = true
        try { await reader.cancel() } catch {}
        break
      }
    }
  } catch (err) {
    if (controller.signal.aborted) aborted = true
  } finally {
    clearTimeout(timer)
  }

  return {
    ok: true,
    http_status: res.status,
    t_headers_ms: +(tHeaders - t0).toFixed(1),
    ttfb_ms: tFirstByte === null ? null : +(tFirstByte - t0).toFixed(1),
    ttft_ms: tFirstDelta === null ? null : +(tFirstDelta - t0).toFixed(1),
    server_think_ms: tFirstDelta === null ? null : +(tFirstDelta - tHeaders).toFixed(1),
    first_kind: firstKind,
    events: nEvents,
    saw_done: sawDone,
    aborted,
  }
}

if (process.env.PROBE_DUMP === '1') {
  const { headers, body } = SHAPE === 'myagent' ? buildMyAgent() : buildDsh()
  const safe = { ...headers }
  for (const k of Object.keys(safe)) {
    if (k.toLowerCase() === 'authorization') safe[k] = 'Bearer <redacted>'
  }
  console.log(JSON.stringify({ stack: 'node-fetch', shape: SHAPE, url: URL_, headers: safe, body }, null, 2))
  process.exit(0)
}

if (WARM) {
  try { await oneRequest() } catch {}
}
const result = await oneRequest()
console.log(JSON.stringify({ stack: 'node-fetch', shape: SHAPE, ...result }))
