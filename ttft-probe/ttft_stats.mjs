/**
 * First-token latency (TTFT) statistics for DSH session logs.
 *
 * Reads every `.jsonl.zstd` session log of one workspace and reproduces DSH's own
 * `sessionStats` first-token rule: `step/start.time` -> the first token delta recorded
 * in that step's compact assistant stream (an `assistant/attempt` stream counts too,
 * so an in-step retry keeps the original step start as the baseline).
 *
 * Usage: node ttft_stats.mjs [--json out.json] [--md out.md] [--model <model>]
 */
import { writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { readSessionEvents, listSessionLogs } from './session_events.mjs'

const SESSIONS_ROOT = join(
  process.env.USERPROFILE, '.dsh', 'sessions', '--D-AI-AI~0020Agent-MyAgent~0020Developer--',
)

const argv = process.argv.slice(2)
const argValue = (flag, fallback) => {
  const i = argv.indexOf(flag)
  return i === -1 ? fallback : argv[i + 1]
}
const jsonOut = argValue('--json')
const mdOut = argValue('--md')
const modelFilter = argValue('--model', 'deepseek/deepseek-v4.1-flash')

/** Time of the first token in one compact stream, mirroring assistantStreamFirstTokenTime. */
function firstTokenTime(stream) {
  if (!Array.isArray(stream)) return undefined
  for (const record of stream) {
    if (record.type === 'chunk') {
      const chunk = record.chunk ?? {}
      const isToken = (chunk.type === 'text-delta' || chunk.type === 'reasoning-delta')
        ? chunk.text !== ''
        : chunk.type === 'tool-call-delta'
          ? (chunk.argumentsDelta !== '' || chunk.name !== undefined)
          : false
      if (isToken) return record.time
      continue
    }
    const members = record.type === 'tool-call-chunks' ? record.args : record.texts
    if (!Array.isArray(members)) continue
    if (record.type === 'tool-call-chunks' && record.name !== undefined) return record.time0
    let time = record.time0
    for (let i = 0; i < members.length; i += 1) {
      if (i > 0) time += record.dt[i - 1] ?? 0
      if (members[i] !== '') return time
    }
  }
  return undefined
}

/** One session log -> per-step TTFT rows. */
function collectSteps(log) {
  const events = readSessionEvents(log.path)
  const header = events.find(e => e.type === 'session')
  const steps = []
  let open = null
  let attempts = 0
  let retries = 0
  let retryDelayMs = 0
  for (const event of events) {
    const data = event.data ?? {}
    switch (event.type) {
      case 'step/start':
        open = { turn: data.turn, step: data.step, start: event.time, first: null, header: null }
        attempts = 0
        retries = 0
        retryDelayMs = 0
        break
      case 'request/header':
        // First request header recorded inside this step approximates "request built".
        if (open && open.header === null && event.data?.header?.config) open.header = event.time
        break
      case 'assistant/attempt':
        if (!open || open.turn !== data.turn || open.step !== data.step) break
        attempts += 1
        if (open.first === null) {
          const t = firstTokenTime(data.stream)
          if (t !== undefined) open.first = t
        }
        break
      case 'llm/retry':
        if (!open || open.turn !== data.turn || open.step !== data.step) break
        retries += 1
        retryDelayMs += typeof data.delayMs === 'number' ? data.delayMs : 0
        break
      case 'assistant/message': {
        if (!open || open.turn !== data.turn || open.step !== data.step) break
        const first = open.first ?? firstTokenTime(data.stream) ?? null
        const source = data.message?.source ?? {}
        steps.push({
          sessionId: log.sessionId,
          createdAt: header?.createdAt ?? null,
          cwd: header?.cwd ?? null,
          depth: header?.delegationDepth ?? 0,
          parentSession: header?.parentSession ?? null,
          turn: data.turn,
          step: data.step,
          startTime: open.start,
          firstTokenTime: first,
          endTime: event.time,
          ttftMs: first === null ? null : Math.max(0, first - open.start),
          apiOnlyMs: first === null || open.header === null ? null : Math.max(0, first - open.header),
          preRequestMs: open.header === null ? null : Math.max(0, open.header - open.start),
          llmMs: Math.max(0, event.time - open.start),
          decodeMs: first === null ? null : Math.max(0, event.time - first),
          outputTokens: typeof data.usage?.outputTokens === 'number' ? data.usage.outputTokens : null,
          promptTokens: typeof data.usage?.inputTokens === 'number' || typeof data.usage?.cacheReadTokens === 'number'
            ? (data.usage?.inputTokens ?? 0) + (data.usage?.cacheReadTokens ?? 0)
            : null,
          cacheReadTokens: typeof data.usage?.cacheReadTokens === 'number' ? data.usage.cacheReadTokens : null,
          model: source.model ?? null,
          provider: source.provider ?? null,
          attempts,
          retries,
          retryDelayMs,
        })
        open = null
        break
      }
      case 'step/end':
        if (open && open.turn === data.turn && open.step === data.step) {
          steps.push({
            sessionId: log.sessionId,
            createdAt: header?.createdAt ?? null,
            depth: header?.delegationDepth ?? 0,
            turn: data.turn,
            step: data.step,
            startTime: open.start,
            firstTokenTime: open.first,
            endTime: event.time,
            ttftMs: open.first === null ? null : Math.max(0, open.first - open.start),
            llmMs: Math.max(0, event.time - open.start),
            decodeMs: null,
            outputTokens: null,
            model: null,
            provider: null,
            attempts,
            retries,
            retryDelayMs,
            settled: false,
          })
          open = null
        }
        break
      default:
        break
    }
  }
  return { steps, events: events.length, createdAt: header?.createdAt ?? null, id: header?.id ?? log.sessionId }
}

const localDay = (ms) => {
  const d = new Date(ms)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function quantile(sorted, q) {
  if (sorted.length === 0) return null
  const pos = (sorted.length - 1) * q
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo)
}

function summarize(values) {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  const sum = sorted.reduce((a, b) => a + b, 0)
  return {
    n: sorted.length,
    mean: sum / sorted.length,
    min: sorted[0],
    p25: quantile(sorted, 0.25),
    median: quantile(sorted, 0.5),
    p75: quantile(sorted, 0.75),
    p90: quantile(sorted, 0.9),
    p95: quantile(sorted, 0.95),
    max: sorted[sorted.length - 1],
  }
}

const secs = ms => ms === null || ms === undefined ? '—' : (ms / 1000).toFixed(2)

// ---------------------------------------------------------------- collect

const logs = listSessionLogs(SESSIONS_ROOT)
const sessions = logs.map(collectSteps)
const allSteps = sessions.flatMap(s => s.steps)
const matching = allSteps.filter(s => s.model === modelFilter)
const ttftRows = matching.filter(s => s.ttftMs !== null)

const byDay = new Map()
for (const row of ttftRows) {
  const day = localDay(row.startTime)
  if (!byDay.has(day)) byDay.set(day, [])
  byDay.get(day).push(row)
}

// ---------------------------------------------------------------- report

const lines = []
const push = s => { lines.push(s) }
push('# DSH first-token latency (TTFT) report')
push('')
push(`- Workspace: \`D:\\AI\\AI Agent\\MyAgent Developer\``)
push(`- Session logs: ${logs.length} (${SESSIONS_ROOT})`)
push(`- Model filter: \`${modelFilter}\``)
push(`- Log window: ${localDay(Math.min(...allSteps.map(s => s.startTime)))} .. ${localDay(Math.max(...allSteps.map(s => s.startTime)))} (local time)`)
push(`- Latest recorded step: ${new Date(Math.max(...allSteps.map(s => s.startTime))).toLocaleString('sv-SE')}; report generated ${new Date().toLocaleString('sv-SE')}`)
push(`- Note: the session \`session-6fc3c8e9\` is still live and keeps appending steps, so its row grows after this cutoff.`)
push(`- Note: DSH home was initialized 2026-09-11, so no session logs exist for earlier days in this workspace.`)
push(`- Definition: \`step/start\` -> first non-empty token delta in the step stream (DSH sessionStats rule; an in-step retry keeps the original step start)`)
push('')
push('## Sessions')
push('')
push('| session | created | depth | steps | llm steps (model) | with first token |')
push('|---|---|---|---|---|---|')
for (const s of sessions) {
  const m = s.steps.filter(x => x.model === modelFilter).length
  const withToken = s.steps.filter(x => x.model === modelFilter && x.ttftMs !== null).length
  push(`| ${s.id} | ${localDay(s.createdAt)} ${new Date(s.createdAt).toTimeString().slice(0, 5)} | ${s.steps[0]?.depth ?? 0} | ${s.steps.length} | ${m} | ${withToken} |`)
}
push('')
push('## Per-day TTFT, `' + modelFilter + '`')
push('')
push('| day | n | mean | min | p25 | median | p75 | p90 | p95 | max |')
push('|---|---|---|---|---|---|---|---|---|---|')
const dayKeys = [...byDay.keys()].sort()
for (const day of dayKeys) {
  const rows = byDay.get(day)
  const s = summarize(rows.map(r => r.ttftMs))
  push(`| ${day} | ${s.n} | ${secs(s.mean)} | ${secs(s.min)} | ${secs(s.p25)} | ${secs(s.median)} | ${secs(s.p75)} | ${secs(s.p90)} | ${secs(s.p95)} | ${secs(s.max)} |`)
}
const total = summarize(ttftRows.map(r => r.ttftMs))
push(`| **all** | ${total.n} | ${secs(total.mean)} | ${secs(total.min)} | ${secs(total.p25)} | ${secs(total.median)} | ${secs(total.p75)} | ${secs(total.p90)} | ${secs(total.p95)} | ${secs(total.max)} |`)
push('')
push('All figures are seconds.')
push('')
const preReq = ttftRows.map(r => r.preRequestMs).filter(v => typeof v === 'number')
if (preReq.length) {
  const p = summarize(preReq)
  push(`- Harness-side pre-request work inside a step (\`step/start\` -> \`request/header\`): n=${p.n}, mean ${secs(p.mean)}s, median ${secs(p.median)}s, p90 ${secs(p.p90)}s, max ${secs(p.max)}s`)
  const api = ttftRows.map(r => r.apiOnlyMs).filter(v => typeof v === 'number')
  if (api.length) {
    const a = summarize(api)
    push(`- API-only view (\`request/header\` -> first token): mean ${secs(a.mean)}s, median ${secs(a.median)}s, p90 ${secs(a.p90)}s, max ${secs(a.max)}s`)
  }
}
push('')
push('## By hour of day (local)')
push('')
push('| hour | n | median | p90 | max | steps >= 10s |')
push('|---|---|---|---|---|---|')
const byHour = new Map()
for (const row of ttftRows) {
  const hour = new Date(row.startTime).getHours()
  if (!byHour.has(hour)) byHour.set(hour, [])
  byHour.get(hour).push(row)
}
for (const hour of [...byHour.keys()].sort((a, b) => a - b)) {
  const rows = byHour.get(hour)
  const q = summarize(rows.map(r => r.ttftMs))
  push(`| ${String(hour).padStart(2, '0')}:00 | ${q.n} | ${secs(q.median)} | ${secs(q.p90)} | ${secs(q.max)} | ${rows.filter(r => r.ttftMs >= 10000).length} |`)
}
push('')
push('## TTFT against prompt size (input + cache-read tokens)')
push('')
push('| prompt tokens | n | median | p90 | max |')
push('|---|---|---|---|---|')
const sizeBuckets = [[0, 10000], [10000, 30000], [30000, 100000], [100000, Infinity]]
const sized = ttftRows.filter(r => typeof r.promptTokens === 'number')
for (const [lo, hi] of sizeBuckets) {
  const rows = sized.filter(r => r.promptTokens >= lo && r.promptTokens < hi)
  if (rows.length === 0) continue
  const q = summarize(rows.map(r => r.ttftMs))
  const label = hi === Infinity ? `>=${lo / 1000}k` : `${lo / 1000}k-${hi / 1000}k`
  push(`| ${label} | ${q.n} | ${secs(q.median)} | ${secs(q.p90)} | ${secs(q.max)} |`)
}
const spearman = (() => {
  const rows = sized.filter(r => r.ttftMs !== null)
  if (rows.length < 5) return null
  const rank = (values) => {
    const order = values.map((v, i) => [v, i]).sort((a, b) => a[0] - b[0])
    const ranks = new Array(values.length)
    order.forEach(([, i], position) => { ranks[i] = position + 1 })
    return ranks
  }
  const rx = rank(rows.map(r => r.promptTokens))
  const ry = rank(rows.map(r => r.ttftMs))
  const n = rows.length
  const mx = (n + 1) / 2
  let num = 0, dx = 0, dy = 0
  for (let i = 0; i < n; i += 1) {
    num += (rx[i] - mx) * (ry[i] - mx)
    dx += (rx[i] - mx) ** 2
    dy += (ry[i] - mx) ** 2
  }
  return num / Math.sqrt(dx * dy)
})()
push('')
push(`Spearman rho (prompt tokens vs TTFT) = ${spearman === null ? 'n/a' : spearman.toFixed(3)} over ${sized.length} steps`)
push('')
push('## Distribution')
push('')
const buckets = [[0, 1000], [1000, 2000], [2000, 3000], [3000, 5000], [5000, 10000], [10000, 20000], [20000, Infinity]]
for (const day of [...dayKeys, 'all']) {
  const rows = day === 'all' ? ttftRows : byDay.get(day)
  const parts = buckets.map(([lo, hi]) => {
    const n = rows.filter(r => r.ttftMs >= lo && r.ttftMs < hi).length
    const label = hi === Infinity ? `>=${lo / 1000}s` : `${lo / 1000}-${hi / 1000}s`
    return `${label}:${n}`
  })
  push(`- ${day}: ${parts.join('  ')}`)
}
push('')
push('## Turn-opening TTFT (step 1 of each turn: what a human waits for after sending a prompt)')
push('')
push('| session | turn | start (local) | TTFT s | prompt tokens |')
push('|---|---|---|---|---|')
const turnOpeners = ttftRows.filter(r => r.step === 1).sort((a, b) => a.startTime - b.startTime)
for (const r of turnOpeners) {
  push(`| ${r.sessionId} | ${r.turn} | ${new Date(r.startTime).toLocaleString('sv-SE')} | ${secs(r.ttftMs)} | ${r.promptTokens ?? '—'} |`)
}
const openerStats = summarize(turnOpeners.map(r => r.ttftMs))
if (openerStats) push(`\nTurn-opening TTFT: n=${openerStats.n}, mean ${secs(openerStats.mean)}s, median ${secs(openerStats.median)}s, p90 ${secs(openerStats.p90)}s, max ${secs(openerStats.max)}s`)
push('')
push('## Outliers and retry-affected steps (top 15 by TTFT)')
push('')
push('| session | turn/step | start (local) | TTFT s | attempt retries | retry delay s | model |')
push('|---|---|---|---|---|---|---|')
for (const r of [...ttftRows].sort((a, b) => b.ttftMs - a.ttftMs).slice(0, 15)) {
  const t = new Date(r.startTime)
  push(`| ${r.sessionId} | ${r.turn}/${r.step} | ${t.toLocaleString('sv-SE')} | ${secs(r.ttftMs)} | ${r.retries} | ${(r.retryDelayMs / 1000).toFixed(2)} | ${r.model} |`)
}
push('')
const retryRows = ttftRows.filter(r => r.retries > 0)
const cleanRows = ttftRows.filter(r => r.retries === 0)
push(`- Steps with at least one in-step retry: ${retryRows.length} of ${ttftRows.length}`)
if (retryRows.length) {
  const rs = summarize(retryRows.map(r => r.ttftMs))
  push(`  - retry-affected TTFT: mean ${secs(rs.mean)}s, median ${secs(rs.median)}s, max ${secs(rs.max)}s`)
}
if (cleanRows.length) {
  const cs = summarize(cleanRows.map(r => r.ttftMs))
  push(`- Retry-free steps: mean ${secs(cs.mean)}s, median ${secs(cs.median)}s, p90 ${secs(cs.p90)}s, p95 ${secs(cs.p95)}s, max ${secs(cs.max)}s`)
}
push('')
const models = new Map()
for (const s of allSteps) models.set(`${s.provider ?? '?'} / ${s.model ?? '?'}`, (models.get(`${s.provider ?? '?'} / ${s.model ?? '?'}`) ?? 0) + 1)
push('## Every provider/model seen in these logs (all steps)')
push('')
for (const [k, n] of [...models].sort((a, b) => b[1] - a[1])) push(`- ${k}: ${n}`)
push('')
const missing = matching.filter(s => s.ttftMs === null)
push(`## Steps on the filtered model with no recorded first token: ${missing.length}`)
for (const r of missing) push(`- ${r.sessionId} turn ${r.turn} step ${r.step} (attempts ${r.attempts}, retries ${r.retries})`)
push('')
push('## Per-session TTFT (filtered model)')
push('')
push('| session | n | mean | median | p90 | max |')
push('|---|---|---|---|---|---|')
for (const s of sessions) {
  const rows = ttftRows.filter(r => r.sessionId === s.id)
  if (rows.length === 0) continue
  const q = summarize(rows.map(r => r.ttftMs))
  push(`| ${s.id} | ${q.n} | ${secs(q.mean)} | ${secs(q.median)} | ${secs(q.p90)} | ${secs(q.max)} |`)
}
push('')

const report = lines.join('\n')
console.log(report)

if (jsonOut) {
  writeFileSync(jsonOut, JSON.stringify({
    workspace: 'D:\\AI\\AI Agent\\MyAgent Developer',
    model: modelFilter,
    generatedAt: new Date().toISOString(),
    sessions: sessions.map(s => ({ id: s.id, createdAt: s.createdAt, events: s.events, steps: s.steps.length })),
    perDay: Object.fromEntries(dayKeys.map(d => [d, summarize(byDay.get(d).map(r => r.ttftMs))])),
    overall: total,
    retryFree: cleanRows.length ? summarize(cleanRows.map(r => r.ttftMs)) : null,
    rows: ttftRows,
  }, null, 2))
}
if (mdOut) writeFileSync(mdOut, report + '\n')
