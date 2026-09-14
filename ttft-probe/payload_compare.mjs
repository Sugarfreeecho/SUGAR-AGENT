/**
 * Compare the request payloads the two harnesses send for the same model.
 *
 * DSH persists its tool schemas in `request/header` events (only when the header
 * changes), so those give the real schema weight. MyAgent records only
 * `context.tools` (a count) per request in execution_metrics.json. This prints both
 * so the prefill weight of each can be set side by side.
 *
 * Usage: node ttft-probe/payload_compare.mjs
 */
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { readSessionEvents, listSessionLogs } from './session_events.mjs'

const MODEL = 'deepseek/deepseek-v4.1-flash'
const SESSIONS_ROOT = join(
  process.env.USERPROFILE, '.dsh', 'sessions', '--D-AI-AI~0020Agent-MyAgent~0020Developer--',
)
const MYAGENT_SESSIONS = 'D:\\AI\\AI Agent\\MyAgent Developer\\workspace\\sessions'

const median = (values) => {
  if (values.length === 0) return NaN
  const s = [...values].sort((a, b) => a - b)
  const mid = Math.floor(s.length / 2)
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2
}

console.log('=== DSH request/header tool payloads ===')
const dshRows = []
for (const log of listSessionLogs(SESSIONS_ROOT)) {
  for (const event of readSessionEvents(log.path)) {
    if (event.type !== 'request/header') continue
    const header = event.data?.header ?? {}
    if (header.config?.model !== MODEL) continue
    const tools = header.tools ?? []
    dshRows.push({
      session: log.sessionId,
      tools: tools.length,
      jsonChars: JSON.stringify(tools).length,
      names: tools.map(t => t?.name),
    })
  }
}
if (dshRows.length) {
  console.log(`samples: ${dshRows.length}`)
  console.log(`tools per request: median ${median(dshRows.map(r => r.tools))} `
    + `min ${Math.min(...dshRows.map(r => r.tools))} max ${Math.max(...dshRows.map(r => r.tools))}`)
  console.log(`tool-schema JSON chars: median ${median(dshRows.map(r => r.jsonChars))}`)
  for (const r of dshRows.slice(0, 6)) {
    console.log(`  ${r.session.slice(0, 22)} tools=${String(r.tools).padStart(3)} chars=${String(r.jsonChars).padStart(7)}`)
  }
  const names = dshRows[dshRows.length - 1].names
  console.log(`  last sample tool names (${names.length}): ${names.join(', ')}`)
}

console.log('\n=== MyAgent context.tools per request ===')
const byCount = new Map()
let maFiles = 0
for (const dir of readdirSync(MYAGENT_SESSIONS, { withFileTypes: true })) {
  if (!dir.isDirectory()) continue
  let data
  try {
    data = JSON.parse(readFileSync(join(MYAGENT_SESSIONS, dir.name, 'execution_metrics.json'), 'utf8'))
  } catch { continue }
  maFiles += 1
  for (const run of data.runs ?? []) {
    for (const req of run.requests ?? []) {
      const model = req.model ?? req.usage?.model
      if (model !== MODEL) continue
      const count = req.context?.tools
      if (typeof count === 'number') byCount.set(count, (byCount.get(count) ?? 0) + 1)
    }
  }
}
console.log(`files: ${maFiles}`)
console.log('tools per request distribution (tools: requests):')
for (const count of [...byCount.keys()].sort((a, b) => a - b)) {
  console.log(`  ${String(count).padStart(3)}: ${String(byCount.get(count)).padStart(5)}`)
}

console.log('\nnote: MyAgent records only the tool COUNT; DSH persists full schemas only when the')
console.log('header changes. Both are proxies for the prefill weight each request carries.')
