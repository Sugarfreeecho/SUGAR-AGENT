# 小Sugar助手 / Sugar Assistant

> 中文名 **小Sugar助手**；英文名 **Sugar Assistant**；插件 id `sugar-assistant`；Python 包 `sugar_assistant`。

统一 IM 接入的宿主插件：**一套 Core，多家通道**。每家 IM 只写一个薄 Adapter，
会话映射、幂等、配额、投递、提问/审批、角色权限都只有一份实现。

- 设计稿：`../../SugarAgent Demo/AI 项目学习/小Sugar助手/小Sugar助手-设计.md`
- 当前进度：**P4**（Core + 飞书 Adapter + 微信/QQ sidecar，**60 条用例全绿**；已在 `.config/plugins-state.json` 启用，等宿主重启加载）

## 装了会怎样

- 默认 `config.json` 不存在 → 只有默认值，没有 enabled 通道 → 插件启动后不连任何东西。
- 只有你把某家通道的 `enabled` 设为 `true` 并且实现了对应 Adapter，才会真正收发消息。
- 停用插件 → 不建连接、不建状态目录之外的副作用。

## 目录

```
plugins/sugar-assistant/
  .myagent-plugin/plugin.json   # id: sugar-assistant
  host.py                       # 生命周期入口（start/stop）
  config.example.json           # 复制成 config.json 再改
  sugar_assistant/          # Python 包不能用连字符
    models.py      # Inbound / Delivery / Capabilities
    config.py      # 多通道配置 + 明文密钥拒绝
    levels.py      # 五类身份 + 四轴档位（机主/白名单/私聊/群聊/陌生）
    admission.py   # 准入 + 定档（只判身份，不裁剪工具）
    sessionmap.py  # 对话 ⇄ 会话（只认当前绑定）
    opstore.py     # message_id 幂等 + 状态机
    quota.py       # none / window10（10 条，第 8 条提醒）/ rate
    prompts.py     # 提问与审批的统一 Prompt + short_code 消歧
    delivery.py    # 重试 · 三态确认 · 幂等键
    commands.py    # /new /list /use /whoami /stop /help
    runtime.py     # 编排：准入 → 幂等 → 会话 → 起一轮 → 投递
    relay.py       # 宿主事件（final / error / tool_approval_required）→ 出站与审批提示
    service.py     # 对 Adapter 的门面：await handle(inbound) 即可
    plugin.py      # 装配点（create_runtime）
    bridge/        # 唯一与宿主耦合的地方
    channels/      # base 协议 + fake 通道
      feishu.py     # 迁 feishu-transport：lark-oapi WS + 事件解析 + reply/create
      sidecar.py    # Node 子进程通道：JSON Lines 双向（微信/QQ 共用）
  sidecar/wechat.mjs             # 默认 import vendor/wechat-core（不再依赖 dsh-wechat 路径）
  sidecar/qq.mjs                 # 官方 @tencent-connect/qqbot-nodejs，只做私聊
  sidecar/package.json           # 只有 QQ 需要 npm install；微信已 vendored
  vendor/wechat-core/            # 复制自 dsh-wechat@e0e8cb3（0.46.0），见 VENDORED.md
  cli.py                         # CLI 启动器（python cli.py status --json）
  mcp/server.py, mcp/servers.json# 11 个 MCP 工具（状态/人物/历史/人设/通道/登录）
  skills/sugar-assistant/SKILL.md# 使用手册技能（安装/登录/CLI/MCP/排查）
  tests/test_core.py             # 60 条一致性用例
```

## 安装与登录（三步）

插件包自带微信连接层（`vendor/wechat-core`），不依赖任何其他插件。装一次依赖即可：

```powershell
# 1) 依赖：Python 侧（飞书）+ Node 侧（微信/QQ）
pip install -r requirements.txt
cd sidecar; npm install; cd ..

# 2) 登录：选一个通道
node sidecar/wechat-login.mjs      # 微信：打印扫码地址，手机确认后写入 state/wechat-account.json
#   飞书：去 open.feishu.cn 建企业自建应用，取 App ID / Secret，设 FEISHU_APP_ID / FEISHU_APP_SECRET
#   QQ  ：拿 QQ 开放平台的 AppID / Secret，设 QQBOT_APP_ID / QQBOT_SECRET

# 3) 打开通道：编辑 config.json，把对应通道的 enabled 改成 true，重启宿主
```

**准备清单**

| 通道 | 需要准备 | 登录/授权入口 |
| --- | --- | --- |
| 飞书 | 企业自建应用 + 机器人能力 + `im:message` 权限 | 开放平台后台，无需扫码 |
| 微信 | 一个微信小号（建议） | `node sidecar/wechat-login.mjs` 扫码 |
| QQ | 腾讯 QQ 开放平台机器人 | 后台取 AppID/Secret，扫码绑定在 `dsh-qq` 或后台完成 |

登录态与服务端凭据都不进 `config.json`（`Config.load` 会拒绝明文密钥）。

### 凭据存在哪

`<data>` = `%WORK_DIR%\\.config\\plugins\\sugar-assistant\\data`（宿主分配，不在插件包里；`SUGAR_DATA_DIR` 可覆盖）。


| 数据 | 位置 | 形态 |
| --- | --- | --- |
| 微信登录态 | `<data>/wechat-account.json` | 明文 JSON：`account.accountId / token / baseUrl / userId / boundAt` + `syncBuf` 游标 |
| 飞书 / QQ | **不落盘** | 只读环境变量 `FEISHU_*` / `QQBOT_*` |
| 会话映射 | `<data>/sessions.json` | 通道 + 对方 ID → 宿主 session_id，不含对话正文 |
| 幂等台账 | `<data>/ops.json` | `channel:account:message_id`、状态、时间戳 |

登录脚本按 `0600` 写文件（Windows 上该权限位不生效，
建议整个 `plugins/sugar-assistant` 目录放在只有你能读的位置）。

## 跑测试

## CLI、MCP 与技能

```powershell
python cli.py status --json            # 1 档：桥接/通道/会话/登录态
python cli.py person list --name 阿鱼  # 1 档：查人物
python cli.py channel enable feishu    # 2 档：开关通道（重启生效）
python cli.py wechat login             # 3 档：起扫码登录
```

档位沿用手册「会话控制」轴（1 只读 / 2 可逆写 / 3 不可逆 / 4 全部），越档返回
`{"error": "... 需要 2 档", "need":2,"have":1}` 且退出码 3。`--json` 放前放后都行。

MCP 工具（`mcp/server.py`，共 11 个）：`sugar_status` / `sugar_channels` / `sugar_conversations` /
`sugar_history` / `sugar_person_lookup` / `sugar_persona_show`（1 档），
`sugar_persona_set` / `sugar_person_add` / `sugar_person_remove` / `sugar_channel_set`（2 档），
`sugar_wechat_login`（3 档）。宿主按四轴工具集先拒一次，工具再按 `SUGAR_ACTOR_LEVEL` 兜一层。

使用手册技能在 `skills/sugar-assistant/SKILL.md`，覆盖安装、登录、命令表、MCP 与排查。

### 关于设置页

`web/` 控制台已按用户要求删除（改由他人实现）。后端 `/api/sugar-assistant/*` 接口仍在 `host.py`，
需要页面的人可以直接复用：status / conversations / logs / persona / persons / config / login/wechat。

## 配置

### 浏览器兜底（跨租户私聊）

飞书开放平台禁止 API 向跨租户单聊发消息（230038/230027），官方通道无解。
插件提供一条**只负责发送**的浏览器通道：复用本机已登录的飞书网页会话，走前端正常发送流程，
发送后用 `lark-cli` 只读回查判定成功。

启用步骤：

1. 控制台 → 配置 → 浏览器兜底，确认租户域名（如 `xxx.feishu.cn`）；
2. 点「扫码登录」，会弹出独立 Edge 窗口，用手机飞书扫码；
3. 登录成功后点「保存浏览器通道」，`data/web.json` 里 `enabled` 置 true；
4. `GET /api/sugar-assistant/config` 的 `web.available` 变为 true 即可用。

规则：默认关闭；只在 `230038/230027` 时降级；同 `(chat_id, 文本)` 60 秒只发一次；
串行执行；已点发送但回查不到一律判 `unknown`，不重发。

配置文件 `data/web.json`：

```jsonc
{
  "enabled": false,
  "tenant": "xxx.feishu.cn",
  "profile": "…/data/browser-profile",
  "headless": true,
  "timeout_ms": 15000,
  "allow": []            // 空 = 所有外部单聊；填了则只允许这些会话名
}
```

复制 `config.example.json` 为 `config.json`。**密钥不写在这里**，只从环境变量读
（`SUGAR_ASSISTANT_<CHANNEL>_SECRET` 之类），配置文件里出现 `secret/token/password/apikey`
字样会直接拒绝启动 —— 这是有意为之：这类错误一旦提交进仓库就收不回来了。

```jsonc
{
  "enabled": true,
  "session_scope": "chat",              // chat | thread | user
  "channels": {
    "feishu": { "enabled": false, "quota": "rate", "allow": ["feishu:ou_xxx"] }
  },
  "channels": {
    "feishu": {
      "enabled": true,
      "quota": "rate",
      "allow": ["ou_owner"],                 // 白名单个人 → whitelist 档
      "allow_groups": ["oc_vip"],            // 白名单群 → 整群提到 private 档
      "group_members": { "oc_team": 30 }     // 已知人数；不填按 ≥5 处理
    }
  },
  "principals": { "feishu:ou_owner": "机主" }
}
```

**权限不在这里配**：五类身份与四轴档位由 `levels.py` 按当轮身份现算（依据产品手册
`references/09-session-permissions.md`）。配置文件里只有"谁算白名单 / 哪个群算白名单群"这类判定证据，
没有任何 `tools` / `read_only` 键 —— 那是宿主执行层的事，写进配置就会被当成会话权限持久化。

## 与宿主对接的三个已知缺口

1. **`question.resolve` 不存在**：`app/remote_control/service.py` 只暴露 `approval.list/resolve`，
   没有 `question.*`。所以 `runtime.answer()` 里对提问会返回「宿主缺少 question.resolve」。
   这是 P0.5，必须先补宿主方法，Adapter 才能答 `ask_user`。
2. **`session.create` 已对齐**：按 `session_control/service.py` 传 `{"name", "_subject"}` 并读回 `session_id`；
   但还没在真机上建过一次会话（无 Adapter），**未验证**。
3. **同步/异步**：Core 目前同步（便于测），宿主 `execute` 是 async。P1 要加一层 `BackgroundHost`
   或者把 Core 改成 async —— 现在遇到 awaitable 会明确报错，不会静默吞掉。

## 下一步

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| P0 | Core + fake 通道 + 用例 | ✅ 60 条全绿 |
| P0.5 | 桥接对齐（`name`/`_subject`、`session_id`/`message`、`mode=queue`）+ 异步桥 + 事件转接 | ✅ 已完成 |
| P1 | `feishu.py`：直接迁 `feishu-transport`（Python + lark-oapi WS） | 🟡 已写（解析/回复/主动发送 + 群 @ 过滤），待真机验证 |
| P2 | 微信 sidecar：已把 `dsh-wechat/packages/core` 复制进 `vendor/`（commit `e0e8cb3`） | 🟡 管道与契约已验，登录/真机未验 |
| P3 | `qq.py`：用 `@tencent-connect/qqbot-nodejs` 写薄 sidecar | 🟡 已写，未真机 |
| P4 | 注册进 `.config/plugins-state.json` + 两条真实消息验收 | 🟡 已启用（`enabled=true`），待重启 + 凭据 |
