---
name: sugar-assistant
description: 小Sugar助手（Sugar Assistant）的使用手册与操作规程：安装/启用插件、微信扫码登录、飞书与QQ凭据、CLI 命令与四档权限、MCP 工具（状态/人物/历史）。用户问"小Sugar助手怎么装/怎么登录/为什么没反应/某个命令什么意思"，或 Agent 需要替用户查桥接状态、人物卡片、运行日志、开关通道时使用。
---

# 小Sugar助手 · 使用手册

一套 Core 接多个 IM：会话映射、幂等投递、身份定档、提问/审批都在 Core；每家只写一个薄 Adapter。

## 一、它由什么组成

| 部分 | 作用 | 在哪 |
| --- | --- | --- |
| CLI | agent 与人共用的控制口，带 1–4 档 | `python cli.py <命令>` |
| MCP 工具 | 把查询/操作注入 agent | `mcp/server.py`（11 个工具） |
| Node sidecar | 微信（vendored core）与 QQ（官方 SDK）的连接层 | `sidecar/*.mjs` |
| 状态 | 会话映射、日志、人设、人物、登录态 | `<data>`＝`<WORK_DIR>/.config/plugins/sugar-assistant/data` |

## 二、安装（迁移到新机器也照这个来）

```powershell
cd plugins/sugar-assistant
pip install -r requirements.txt     # 飞书用 lark-oapi
cd sidecar; npm install; cd ..      # 微信/QQ 的 Node 依赖
python cli.py status --json         # 能打印 JSON 就算装好
```

插件包**自带**微信连接层（`vendor/wechat-core`，来自 dsh-wechat `e0e8cb3`），不需要另一个仓库。

## 三、登录 / 授权

| 通道 | 准备 | 入口 |
| --- | --- | --- |
| 微信 | 一个微信小号（建议） | `python cli.py wechat login`；`node sidecar/wechat-login.mjs --web` 会开本地扫码页 |
| 飞书 | 企业自建应用 + 机器人 + `im:message` 权限 + 长连接订阅 `im.message.receive_v1` | 设 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` |
| QQ | QQ 开放平台机器人 | 设 `QQBOT_APP_ID` / `QQBOT_SECRET` |

微信登录成功会写 `<data>/wechat-account.json`（明文 token，仅本机可读）。
**凭据不进 `config.json`**：`Config.load()` 见到 `token/secret` 之类字段会直接报错。

## 四、CLI 与四档权限

档位沿用手册「会话控制」轴：1 只读 / 2 可逆写 / 3 不可逆 / 4 全部。
本机命令行默认 4 档；越档返回 `{"error": "... 需要 2 档", "need":2,"have":1}` 且退出码 3。

| 命令 | 档 | 说明 |
| --- | --- | --- |
| `status` | 1 | 通道开关、会话数、微信是否已登录 |
| `conversations` | 1 | 对话键 → 宿主 session_id |
| `logs --limit 50` | 1 | 最近运行事件（不含正文） |
| `persona show` | 1 | 人设 |
| `person list [--name 阿鱼]` | 1 | 人物卡片，按名字/别名模糊查 |
| `channel list` | 1 | 通道清单 |
| `identity show` | 1 | 当前收发身份（bot / user）与 user 模式轮询的会话 |
| `identity set user --chat oc_xxx` | 2 | 切到用户本人账号收发；`--chat` 可重复 |
| `identity set bot` | 2 | 切回助手账号（默认） |
| `persona set --name --tone --rules` | 2 | 改人设（留空=不改） |
| `person add --name --relation --alias --note` | 2 | 加人物 |
| `person remove --id p-xxxx` | 2 | 删人物 |
| `channel enable|disable <名字>` | 2 | 写 config.json，重启生效 |
| `wechat login` | 3 | 起扫码登录（会换登录态） |

`--json` 放前放后都行，便于 agent 解析。

## 五、MCP 工具

宿主按四轴工具集做**第一道**拒绝；工具自己按 `SUGAR_ACTOR_LEVEL`（默认 4）做第二道。

| 工具 | 档 | 返回 |
| --- | --- | --- |
| `sugar_status` | 1 | 桥接状态、通道、会话数、登录态 |
| `sugar_channels` | 1 | 通道清单 |
| `sugar_conversations` | 1 | 对话映射 |
| `sugar_history(session_id?, limit)` | 1 | 最近事件 |
| `sugar_person_lookup(name?)` | 1 | 人物卡片 |
| `sugar_persona_show` | 1 | 人设 |
| `sugar_persona_set` | 2 | 改人设 |
| `sugar_person_add` / `sugar_person_remove` | 2 | 人物增删 |
| `sugar_channel_set(name, enabled)` | 2 | 开关通道 |
| `sugar_wechat_login` | 3 | 起扫码登录 |

## 六、排查

| 现象 | 先看 |
| --- | --- |
| 发消息没反应 | `sugar_status`：通道是否 `enabled` + 是否 `running`；`sugar_history` 有没有 `denied`（准入拒绝） |
| 日志里 `通道未启用` | 该通道 `enabled=false`，或 `config.json` 没写这个通道 |
| 微信报「还没有微信登录态」 | 跑 `wechat login`，确认 `<data>/wechat-account.json` 出现 |
| 群里 @ 了也不回 | 飞书默认 `group_require_mention`（必须 @）且群成员 ≥5 走 group 档（只读工具） |
| 审批卡片发了但点「1」没反应 | 该会话没有待答卡片；用 `sugar_history` 看有没有 `prompt` 事件 |
| `session.list` 报 `Session service has not started` | 在宿主进程外调用属正常；桥接只在宿主内有效 |

## 七、边界

- 不改宿主代码（`question.resolve` 缺口未补时，IM 上答不了 `ask_user`）。
- 不做多账号并发、不做 Web 设置以外的管理界面。
- 日志只记 ID 与状态，不记消息正文；人物/人设是本地文件，不上传。
