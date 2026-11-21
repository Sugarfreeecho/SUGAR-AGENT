#!/usr/bin/env node
/**
 * 微信 sidecar：把 `dsh-wechat/packages/core` 当库用（零 DSH 依赖），
 * 只做协议桥：stdin 的 send 指令 → core 的 sendText；core 的入站 → stdout 的 inbound。
 *
 * 用法：
 *   WECHAT_CORE="D:/.../dsh-wechat/packages/core/src/index.ts" \
 *   WECHAT_STATE="D:/.../wechat-state.json" node wechat.mjs
 *
 * 状态文件由 `dsh-wechat` 自己的登录流程生成（含 account.token / baseUrl），
 * 这里不重复实现扫码：登录是它的强项，重复写等于重踩协议坑。
 */
// 默认用插件内 vendored 副本的公开入口（与上游 index.ts 一致），
// 也可用 WECHAT_CORE 指回上游仓库
const corePath =
  process.env.WECHAT_CORE ||
  new URL("../vendor/wechat-core/src/index.ts", import.meta.url).href

const { ChannelMonitor, sendText } = await import(corePath)
const fs = await import("node:fs")
const { fileURLToPath } = await import("node:url")
const pathMod = await import("node:path")

// 数据目录优先用宿主分配的 SUGAR_DATA_DIR，脱离宿主时退回插件内 state/
const dataDir = process.env.SUGAR_DATA_DIR || fileURLToPath(new URL("../state", import.meta.url))
const statePath =
  process.env.WECHAT_STATE ||
  pathMod.join(dataDir, "wechat-account.json")
if (!statePath || !fs.existsSync(statePath)) {
  console.error("还没有微信登录态，请先执行：node sidecar/wechat-login.mjs")
  process.exit(2)
}

const state = JSON.parse(fs.readFileSync(statePath, "utf8"))
const account = state.account || state.accounts?.default
if (!account?.token) {
  console.error("状态文件里没有 account.token，请先用 dsh-wechat 登录")
  process.exit(2)
}

const emit = (payload) => process.stdout.write(JSON.stringify(payload) + "\n")
const controller = new AbortController()

const monitor = new ChannelMonitor({
  account,
  initialSyncBuf: state.syncBuf || undefined,
  onSyncBuf: (buf) => {
    state.syncBuf = buf
    fs.writeFileSync(statePath, JSON.stringify(state, null, 2))
  },
  onMessage: async (message) => {
    emit({
      type: "inbound",
      peerId: message.peerId,
      chatId: message.groupId || message.peerId,
      groupId: message.groupId,
      messageId: message.messageId,
      contextToken: message.contextToken,
      text: message.text,
      receivedAt: message.receivedAt,
    })
  },
  onError: (error) => emit({ type: "error", error: String(error?.message || error) }),
  onStop: (reason, detail) => emit({ type: "error", error: `monitor stopped: ${reason} ${detail || ""}` }),
})

emit({ type: "ready", account: account.accountId || "default" })
monitor.run(controller.signal).catch((error) => emit({ type: "error", error: String(error) }))

let buffer = ""
process.stdin.setEncoding("utf8")
process.stdin.on("data", async (chunk) => {
  buffer += chunk
  let index
  while ((index = buffer.indexOf("\n")) >= 0) {
    const line = buffer.slice(0, index).trim()
    buffer = buffer.slice(index + 1)
    if (!line) continue
    let command
    try {
      command = JSON.parse(line)
    } catch {
      continue
    }
    if (command.type === "stop") {
      controller.abort()
      process.exit(0)
    }
    if (command.type === "send") {
      try {
        const result = await sendText({
          account,
          to: command.to,
          text: command.text,
          contextToken: command.contextToken,
        })
        emit({ type: "sent", id: command.id, ok: true, serverMessageId: result?.serverMessageId })
      } catch (error) {
        emit({ type: "sent", id: command.id, ok: false, error: String(error?.message || error) })
      }
    }
  }
})
