// TCP+TLS handshake cost to the real host, per fresh process-connection.
// Node's undici path. Env: TLS_HOST, TLS_N
import net from 'node:net'
import tls from 'node:tls'

const HOST = process.env.TLS_HOST
const PORT = Number(process.env.TLS_PORT || 443)
const N = Number(process.env.TLS_N || 15)

function once() {
  return new Promise((resolve) => {
    const t0 = performance.now()
    let tTcp = null
    const sock = net.connect({ host: HOST, port: PORT })
    sock.once('connect', () => {
      tTcp = performance.now()
      const tlsSock = tls.connect({ socket: sock, servername: HOST }, () => {
        const tDone = performance.now()
        const out = { tcp: tTcp - t0, tls: tDone - tTcp, total: tDone - t0 }
        tlsSock.destroy()
        resolve(out)
      })
      tlsSock.once('error', () => resolve({ tcp: tTcp - t0, tls: null, total: null }))
    })
    sock.once('error', () => resolve({ tcp: null, tls: null, total: null }))
  })
}

const rows = []
for (let i = 0; i < N; i++) rows.push(await once())
const totals = rows.map(r => r.total).filter(v => v !== null)
const tcps = rows.map(r => r.tcp).filter(v => v !== null)
const tlss = rows.map(r => r.tls).filter(v => v !== null)
const mean = a => a.reduce((x, y) => x + y, 0) / a.length
const sd = a => { const m = mean(a); return Math.sqrt(a.reduce((x, y) => x + (y - m) ** 2, 0) / (a.length - 1)) }
console.log(JSON.stringify({
  stack: 'node-tls', host: HOST, n: totals.length,
  total: { mean: mean(totals), sd: sd(totals), min: Math.min(...totals), max: Math.max(...totals) },
  tcp: { mean: mean(tcps), sd: sd(tcps) },
  tls: { mean: mean(tlss), sd: sd(tlss) },
  samples: totals.map(v => +v.toFixed(1)),
}))
