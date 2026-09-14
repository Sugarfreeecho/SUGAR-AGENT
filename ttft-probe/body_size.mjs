/**
 * How big are the two harnesses' request bodies, actually?
 *
 * DSH's session log persists the system prompt, every message and the tool schemas, so its
 * real body can be rebuilt and serialised. MyAgent records only token counts, so its size is
 * bounded from DSH's measured bytes-per-token ratio.
 *
 * Then, using the upload cost measured in upload_probe.py (~0.0488 ms per KiB), the transfer
 * time difference is computed -- which decides whether packaging explains the gap.
 *
 * Usage: node ttft-probe/body_size.mjs
 */
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { readSessionEvents, listSessionLogs } from './session_events.mjs'

const MODEL = 'deepseek/deepseek-v4.1-flash'
const MS_PER_KIB = 0.0488 // measured slope from upload_probe.py
const SESSIONS_ROOT = join(
  process.env.USERPROFILE, '.dsh', 'sessions', '--D-AI-AI~0020Agent-MyAgent~0020Developer--',
)
const MYAGENT_SESSIONS = 'D:\\AI\\AI Agent\\MyAgent Developer\\workspace\\sessions'

const median = (v) => {
  if (!v.length) return NaN
  const s = [...v].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

console.log('='.repeat(78))
console.log('A) DSH: rebuild the real request body from its own session log')
console.log('='.repeat(78))

const bodies = []
for (const log of listSessionLogs(SESSIONS_ROOT)) {
  const events = readSessionEvents(log.path)
  let tools = null
  const systemText = []
  const msgs = []
  let promptTokens = null

  for (const e of events) {
    const d = e.data ?? {}
    if (e.type === 'request/header') {
      const hdr = d.header ?? {}
      if ((hdr.config ?? {}).model === MODEL) tools = hdr.tools ?? []
    } else if (e.type === 'system/message') {
      for (const b of (d.message ?? {}).content ?? []) {
        if (b?.type === 'text' && b.text) systemText.push(b.text)
      }
    } else if (e.type === 'user/message') {
      msgs.push(d.content ?? [])
    } else if (e.type === 'assistant/message') {
      msgs.push((d.message ?? {}).content ?? [])
      const u = d.usage ?? {}
      const t = (u.inputTokens ?? 0) + (u.cacheReadTokens ?? 0)
      // keep the LAST usage: the reconstructed body is the session's final state, so the
      // byte/token ratio is only meaningful against the final prompt size
      if (t) promptTokens = t
    }
  }
  if (tools === null) continue

  const body = {
    model: MODEL,
    messages: [
      ...(systemText.length ? [{ role: 'system', content: systemText.join('\n') }] : []),
      ...msgs.map(m => ({ role: 'user', content: m })),
    ],
    tools,
    stream: true,
    stream_options: { include_usage: true },
  }
  const bytes = Buffer.byteLength(JSON.stringify(body))
  const toolsBytes = Buffer.byteLength(JSON.stringify(tools))
  bodies.push({ id: log.sessionId, bytes, toolsBytes, messages: msgs.length, promptTokens })
}

if (bodies.length) {
  const biggest = bodies.reduce((a, b) => (b.bytes > a.bytes ? b : a))
  console.log(`  sessions rebuilt: ${bodies.length}`)
  console.log(`  largest: ${biggest.id.slice(0, 42)}`)
  console.log(`    body          : ${biggest.bytes.toLocaleString()} bytes `
    + `(${(biggest.bytes / 1024).toFixed(0)} KiB)`)
  console.log(`    of which tools: ${biggest.toolsBytes.toLocaleString()} bytes `
    + `(${(biggest.toolsBytes / biggest.bytes * 100).toFixed(1)}%)`)
  console.log(`    messages      : ${biggest.messages}`)
  if (biggest.promptTokens) {
    console.log(`    prompt tokens : ${biggest.promptTokens.toLocaleString()}`)
    console.log(`    bytes/token   : ${(biggest.bytes / biggest.promptTokens).toFixed(2)}`)
  }
  console.log(`\n  body bytes across sessions: median `
    + `${median(bodies.map(b => b.bytes)).toLocaleString()}`)
  console.log(`  tool schema bytes          : median ${median(bodies.map(b => b.toolsBytes)).toLocaleString()}`)
}

console.log()
console.log('='.repeat(78))
console.log('B) MyAgent: bound it from its recorded token counts')
console.log('='.repeat(78))

const toks = []
const toolCounts = []
for (const dir of readdirSync(MYAGENT_SESSIONS, { withFileTypes: true })) {
  if (!dir.isDirectory()) continue
  let data
  try {
    data = JSON.parse(readFileSync(join(MYAGENT_SESSIONS, dir.name, 'execution_metrics.json'), 'utf8'))
  } catch { continue }
  for (const run of data.runs ?? []) {
    for (const q of run.requests ?? []) {
      const u = q.usage ?? {}
      if ((q.model ?? u.model) !== MODEL) continue
      if (u.prompt_tokens) toks.push(u.prompt_tokens)
      const tc = q.context?.tools
      if (typeof tc === 'number') toolCounts.push(tc)
    }
  }
}
console.log(`  requests: ${toks.length}   prompt tokens median ${median(toks).toLocaleString()}`
  + `   max ${Math.max(...toks).toLocaleString()}`)
console.log(`  tools per request: median ${median(toolCounts)}   (DSH: 27)`)
const dshToolsBytes = bodies.length ? median(bodies.map(b => b.toolsBytes)) : 28490
const maSchema = dshToolsBytes * 61 / 27
console.log(`  MyAgent tool schema, scaled from DSH's ${dshToolsBytes.toLocaleString()} B / 27 tools:`
  + ` ~${maSchema.toLocaleString()} B`)

console.log()
console.log('='.repeat(78))
console.log('C) WHAT THE TRANSFER COSTS EACH SIDE')
console.log('='.repeat(78))
console.log(`  measured upload cost: ${MS_PER_KIB} ms per KiB `
  + `(${(1024 / MS_PER_KIB).toFixed(0)} KiB/s ~= ${(1 / MS_PER_KIB).toFixed(1)} MiB/s)`)

const rows = [
  ['DSH main session (156k tok)', 156368, dshToolsBytes],
  ['MyAgent typical (122k tok)', 122067, maSchema],
]
// bytes per token measured on DSH above; fall back to 2.5 only if that failed
const measuredBpt = (() => {
  const withTok = bodies.filter(b => b.promptTokens)
  if (!withTok.length) return 2.5
  const b = withTok.reduce((a, x) => (x.promptTokens > a.promptTokens ? x : a))
  return b.bytes / b.promptTokens
})()
console.log(`\n  bytes per token (measured on DSH): ${measuredBpt.toFixed(2)}`)
const cost = []
for (const [label, tok, schema] of rows) {
  const total = tok * measuredBpt + schema
  const ms = total / 1024 * MS_PER_KIB
  cost.push(ms)
  console.log(`  ${label.padEnd(30)} ~${(total / 1024).toFixed(0).padStart(6)} KiB  ->  `
    + `${ms.toFixed(1).padStart(6)} ms of upload`)
}
const diff = Math.abs(cost[0] - cost[1])
console.log(`\n  difference in transfer time: ~${diff.toFixed(1)} ms`)
console.log(`  the gap being explained    : ~1500 ms`)
console.log(`\n  => packaging/upload is about ${(diff / 1500 * 100).toFixed(2)}% of the gap.`)
console.log('     Direction matters too: DSH carries MORE prompt tokens (156k vs 122k), so it')
console.log('     uploads MORE bytes. The hypothesis predicts the opposite of what is observed.')
console.log()
console.log('  Even a full extra megabyte of body would cost only '
  + `${(1024 * MS_PER_KIB).toFixed(0)} ms.`)
