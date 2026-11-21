#!/usr/bin/env node
/**
 * 微信扫码登录：插件的登录入口（命令行 + 本地网页两种）。
 *
 *   node sidecar/wechat-login.mjs          # 只走命令行：打印扫码地址
 *   node sidecar/wechat-login.mjs --web    # 同时起本地页面（默认打开浏览器）
 *
 * 成功后凭据写到 `state/wechat-account.json`，`wechat.mjs` 自动读取。
 * 登录协议来自 vendored 的 @dsh-wechat/core（`login()` 异步生成器），这里只做交互与落盘。
 */
import fs from "node:fs"
import http from "node:http"
import path from "node:path"
import readline from "node:readline/promises"
import { exec } from "node:child_process"
import { fileURLToPath, pathToFileURL } from "node:url"

// 数据目录优先用宿主分配的 SUGAR_DATA_DIR，脱离宿主时退回插件内 state/
const dataDir = process.env.SUGAR_DATA_DIR || fileURLToPath(new URL("../state", import.meta.url))
const statePath = process.env.WECHAT_STATE || path.join(dataDir, "wechat-account.json")
const loginModule = fileURLToPath(new URL("../vendor/wechat-core/src/login.ts", import.meta.url))
const { login } = await import(pathToFileURL(loginModule).href)

const useWeb = process.argv.includes("--web")
const view = { phase: "starting", qrUrl: "", message: "", error: "" }
let verifyWaiter = null

const previous = fs.existsSync(statePath)
  ? (() => {
      try {
        const token = JSON.parse(fs.readFileSync(statePath, "utf8"))?.account?.token
        return token ? [String(token)] : []
      } catch {
        return []
      }
    })()
  : []

const controller = new AbortController()
process.on("SIGINT", () => controller.abort())

// ---------------------------------------------------------------- 本地页面
if (useWeb) {
  const page = `<!doctype html><meta charset="utf-8"><title>微信扫码登录 · 小Sugar助手</title>
<style>body{background:#0f1115;color:#e6e8ee;font:14px/1.6 "Microsoft YaHei",system-ui;display:flex;
justify-content:center;padding-top:8vh}main{width:420px}h1{font-size:18px;margin:0 0 6px}
p{color:#8b93a7;font-size:13px}img{width:240px;height:240px;background:#fff;padding:8px;border-radius:10px}
input{width:100%;padding:10px;border-radius:8px;border:1px solid #262b36;background:#1d212a;color:#e6e8ee;margin:10px 0}
button{background:#f2b544;border:0;border-radius:8px;padding:10px 16px;font-weight:600;cursor:pointer}
code{color:#c9d1e6}</style>
<main><h1>微信扫码登录</h1><p id="msg">正在获取二维码…</p>
<img id="qr" alt="二维码" style="display:none"/>
<div id="codebox" style="display:none"><p>手机上显示配对验证码时填这里：</p>
<input id="code" placeholder="6 位验证码"/><button onclick="submitCode()">提交</button></div>
<p id="foot"></p></main>
<script>
let timer=setInterval(refresh,1200);
async function refresh(){
  const s=await (await fetch('/state')).json();
  document.getElementById('msg').textContent =
    ({starting:'正在获取二维码…',running:'请用手机微信扫码',need_code:'请输入手机上的配对验证码',
      scanned:'已扫码，请在手机上确认',succeeded:'登录成功，可以关闭此页',failed:'登录失败：'+s.error})[s.phase]||s.phase;
  if(s.qrUrl){const img=document.getElementById('qr');img.style.display='block';img.src=s.qrUrl}
  document.getElementById('codebox').style.display = s.phase==='need_code'?'block':'none';
  if(s.phase==='succeeded'||s.phase==='failed')clearInterval(timer);
}
async function submitCode(){
  const code=document.getElementById('code').value.trim();
  if(!code)return;
  await fetch('/verify?code='+encodeURIComponent(code));
  document.getElementById('code').value='';
}
</script>`

  const server = http.createServer((req, res) => {
    if (req.url === "/") {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" })
      res.end(page)
      return
    }
    if (req.url === "/state") {
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" })
      res.end(JSON.stringify(view))
      return
    }
    if (req.url.startsWith("/verify")) {
      const code = new URL(req.url, "http://127.0.0.1").searchParams.get("code") || ""
      if (verifyWaiter) verifyWaiter(code)
      res.writeHead(200, { "Content-Type": "application/json" })
      res.end('{"ok":true}')
      return
    }
    res.writeHead(404)
    res.end()
  })
  await new Promise((resolve) => server.listen(8787, "127.0.0.1", resolve))
  const url = "http://127.0.0.1:8787/"
  console.log(`登录页面：${url}`)
  if (process.platform === "win32" && !process.env.SUGAR_NO_OPEN) exec(`start "" "${url}"`)
}

// ---------------------------------------------------------------- 登录流程
const rl = readline.createInterface({ input: process.stdin, output: process.stdout })
const ask = async (question) => {
  if (useWeb) {
    view.phase = "need_code"
    return await new Promise((resolve) => {
      verifyWaiter = (code) => {
        verifyWaiter = null
        resolve(code)
      }
    })
  }
  return await rl.question(question)
}

let answer
const session = login(
  { existingTokens: previous, reuseExisting: "adopt", timeoutMs: 5 * 60 * 1000 },
  controller.signal,
)

try {
  while (true) {
    const step = await session.next(answer)
    answer = undefined
    if (step.done) {
      const result = step.value || {}
      if (result.account) {
        fs.mkdirSync(path.dirname(statePath), { recursive: true })
        fs.writeFileSync(statePath, JSON.stringify({ account: result.account, syncBuf: "" }, null, 2),
          { encoding: "utf8", mode: 0o600 })
        view.phase = "succeeded"
        console.log(`登录成功，凭据已保存：${statePath}`)
        process.exit(0)
      }
      view.phase = "failed"
      view.error = result.reason || (result.alreadyBound ? "该账号已绑定其他客户端" : "未知原因")
      console.log(`没有拿到凭据：${view.error}`)
      process.exit(1)
    }
    const event = step.value
    switch (event.kind) {
      case "qr":
        view.phase = "running"
        view.qrUrl = event.qrUrl
        console.log("\n请用手机微信扫码或在微信里打开这个地址：\n")
        console.log(event.qrUrl)
        break
      case "scanned":
        view.phase = "scanned"
        console.log("已扫码，请在手机上点确认。")
        break
      case "verifycode-required":
        view.message = "需要配对验证码"
        answer = await ask("手机上显示的配对验证码：")
        view.phase = "running"
        break
      case "expired":
        console.log(event.willRetry ? "二维码过期，已自动刷新。" : "二维码过期。")
        break
      case "redirected":
        console.log(`登录服务切换到 ${event.host}，继续等待…`)
        break
      case "already-bound":
        console.log("服务端认为该微信已绑定其他客户端；如需接管请先解绑。")
        break
      case "failed":
        view.phase = "failed"
        view.error = event.reason
        console.log(`登录失败：${event.reason}`)
        process.exit(1)
      default:
        break
    }
  }
} finally {
  rl.close()
}
