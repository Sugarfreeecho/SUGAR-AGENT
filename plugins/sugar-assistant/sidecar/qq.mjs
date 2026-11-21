#!/usr/bin/env node
/**
 * QQ sidecar：只做协议桥，连接层用腾讯官方 `@tencent-connect/qqbot-nodejs`。
 *
 * 与 dsh-qq-plugin 的差别：那边把 SDK 包在 DSH 插件里（依赖 ctx.sessionController 等），
 * 不能脱离宿主跑；这里只保留「连、收、发」三件事，其余交给 Python Core。
 * 扫码登录也复用官方 connector（`login.mjs`），不在本文件里重写。
 *
 * 用法：
 *   QQBOT_APP_ID=... QQBOT_APP_SECRET=... node qq.mjs
 *
 * 协议：与 wechat.mjs 完全一致（JSON Lines），所以 Python 侧共用 SidecarChannel。
 */
const appId = process.env.QQBOT_APP_ID
const appSecret = process.env.QQBOT_APP_SECRET
if (!appId || !appSecret) {
  console.error("缺少 QQBOT_APP_ID / QQBOT_APP_SECRET（先跑 login.mjs 扫码，或手工填）")
  process.exit(2)
}

let QQBot
try {
  ;({ QQBot } = await import("@tencent-connect/qqbot-nodejs"))
} catch (error) {
  console.error(
    "缺少 QQ SDK，请在 plugins/sugar-assistant/sidecar 目录执行 `npm install`（package.json 已声明依赖）：",
    String(error?.message || error),
  )
  process.exit(3)
}

const emit = (payload) => process.stdout.write(JSON.stringify(payload) + "\n")

/**
 * SDK 会把 handler 里抛的异常吞进 logger，不给 logger 就完全静默。
 * dsh-qq 的注释里记过一次真实事故：handler 第一行 ReferenceError，
 * 现象只是「连上了但没反应」。所以这里必须接日志。
 */
const logger = {
  info: (message) => console.error(`[qq] info ${message}`),
  warn: (message) => console.error(`[qq] warn ${message}`),
  error: (message) => console.error(`[qq] error ${message}`),
}

const bot = new QQBot({ appId, appSecret, accountId: appId, logger })

/** conversationId → 最近一条入站 msgId（被动回复要用它） */
const lastMessage = new Map()

bot.on("ready", () => emit({ type: "ready", account: appId }))
bot.on("error", (error) => emit({ type: "error", error: String(error?.message || error) }))

bot.on("message", (_ctx, message) => {
  // 只做私聊：群事件直接忽略（与 dsh-qq 的行为一致）
  if (!message || message.kind !== "c2c") return
  const peerId = message.senderId
  if (!peerId) return
  if (message.messageId) lastMessage.set(peerId, message.messageId)
  emit({
    type: "inbound",
    peerId,
    chatId: peerId,
    messageId: message.messageId,
    contextToken: message.messageId,
    text: typeof message.content === "string" ? message.content : "",
    receivedAt: Date.now(),
  })
})

bot.start().catch((error) => emit({ type: "error", error: String(error?.message || error) }))

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
      try {
        await bot.stop?.()
      } catch {
        /* 尽力而为 */
      }
      process.exit(0)
    }
    if (command.type === "send") {
      try {
        const msgId = command.contextToken || lastMessage.get(command.to)
        const target = msgId
          ? { scope: "c2c", targetId: command.to, msgId }
          : { scope: "c2c", targetId: command.to }
        await bot.sendText(target, command.text)
        emit({ type: "sent", id: command.id, ok: true })
      } catch (error) {
        emit({ type: "sent", id: command.id, ok: false, error: String(error?.message || error) })
      }
    }
  }
})
