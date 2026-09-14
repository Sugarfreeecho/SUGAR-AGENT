/**
 * Read DSH .jsonl.zstd session logs (concatenated zstd frames) and report
 * event-shape statistics. Exploratory helper for TTFT analysis.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { zstdDecompressSync } from 'node:zlib'

const ZSTD_MAGIC = 0xfd2fb528

export function scanFrames(buffer) {
  const frames = []
  let offset = 0
  while (offset < buffer.length) {
    const start = offset
    if (buffer.length - offset < 4) return { frames, tornStart: start }
    if (buffer.readUInt32LE(offset) !== ZSTD_MAGIC) throw new Error(`bad magic at ${offset}`)
    offset += 4
    if (offset === buffer.length) return { frames, tornStart: start }
    const descriptor = buffer.readUInt8(offset)
    offset += 1
    const contentSizeFlag = descriptor >>> 6
    const singleSegment = (descriptor & 0x20) !== 0
    const checksum = (descriptor & 0x04) !== 0
    const dictionaryFlag = descriptor & 0x03
    const dictionaryBytes = dictionaryFlag === 3 ? 4 : dictionaryFlag
    const contentSizeBytes = contentSizeFlag === 0 ? (singleSegment ? 1 : 0) : 1 << contentSizeFlag
    const remainingHeaderBytes = (singleSegment ? 0 : 1) + dictionaryBytes + contentSizeBytes
    if (buffer.length - offset < remainingHeaderBytes) return { frames, tornStart: start }
    offset += remainingHeaderBytes
    for (;;) {
      if (buffer.length - offset < 3) return { frames, tornStart: start }
      const blockHeader = buffer.readUIntLE(offset, 3)
      offset += 3
      const lastBlock = (blockHeader & 1) !== 0
      const blockType = (blockHeader >>> 1) & 0x03
      const blockSize = blockHeader >>> 3
      if (blockType === 0x03) throw new Error(`reserved block type at ${offset - 3}`)
      const payloadBytes = blockType === 0x01 ? 1 : blockSize
      if (buffer.length - offset < payloadBytes) return { frames, tornStart: start }
      offset += payloadBytes
      if (lastBlock) break
    }
    if (checksum) {
      if (buffer.length - offset < 4) return { frames, tornStart: start }
      offset += 4
    }
    frames.push({ start, end: offset })
  }
  return { frames }
}

export function readSessionEvents(path) {
  const raw = readFileSync(path)
  const { frames } = scanFrames(raw)
  const out = []
  for (const f of frames) {
    const text = zstdDecompressSync(raw.subarray(f.start, f.end)).toString('utf8')
    for (const line of text.split('\n')) {
      if (!line.trim()) continue
      try {
        out.push(JSON.parse(line))
      } catch {
        out.push({ type: '__unparsed__', raw: line.slice(0, 200) })
      }
    }
  }
  return out
}

export function listSessionLogs(dir) {
  const out = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue
    const nested = join(dir, entry.name)
    for (const file of readdirSync(nested)) {
      if (!file.endsWith('.jsonl.zstd') && !file.endsWith('.jsonl')) continue
      const path = join(nested, file)
      out.push({ sessionId: entry.name, path, size: statSync(path).size })
    }
  }
  return out
}

if (process.argv[1] && process.argv[1].endsWith('session_events.mjs')) {
  const root = process.argv[2]
    ?? join(process.env.USERPROFILE, '.dsh', 'sessions', '--D-AI-AI~0020Agent-MyAgent~0020Developer--')
  const logs = listSessionLogs(root)
  console.log('logs:', logs.length)
  const typeCounts = new Map()
  const samples = new Map()
  for (const log of logs) {
    const events = readSessionEvents(log.path)
    console.log(`\n=== ${log.sessionId} (${events.length} events) ===`)
    for (const e of events) {
      typeCounts.set(e.type, (typeCounts.get(e.type) ?? 0) + 1)
      if (!samples.has(e.type)) samples.set(e.type, e)
    }
  }
  console.log('\n--- event type counts ---')
  for (const [t, n] of [...typeCounts].sort((a, b) => b[1] - a[1])) console.log(String(n).padStart(6), t)
  console.log('\n--- first sample per type ---')
  for (const [t, e] of samples) {
    console.log(`\n[${t}]`, JSON.stringify(e).slice(0, 900))
  }
}
