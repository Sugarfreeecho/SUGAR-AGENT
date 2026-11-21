# 浏览器桥（方案 B）· 实现记录与事故说明

## 目标

让插件在官方 API 拒绝跨租户单聊（230038/230027）时，借用用户已登录的浏览器把消息发出去，
不导出 Cookie、不暴露裸 CDP。

## 架构

```
sugar-assistant
   │ manifest: permissions.services = ["browser"]
   ▼
app/plugin_bus.py        注册 / 权限校验 / 方法白名单 / 审计
   ▼
browser-use 注册的 browser 服务
   ▼
bridge.py（open_chat / send_text / send_media / read_recent）
   ▼
Playwright MCP 工具 → 用户已登录的 Edge
```

白名单四方法：`open_chat`、`send_text`、`send_media`、`read_recent`。
权限来自插件 manifest，未声明直接拒绝（已验证）。

## 已完成并验证

| 项 | 证据 |
| --- | --- |
| 服务总线 | `tests/test_plugin_bus.py` 3 条通过 |
| 权限拒绝 | 撤销声明后 probe 返回「未声明 browser 权限」 |
| 读会话 | `read_recent` 返回 `ok=true, chars=4000` |
| 发文本（定向） | 2026-11-19 15:57 发到小Sugar 私聊 `oc_9ffa0ae8…`，服务端回查 `msg_type=text`、发送者本人 |
| 定向王影（不发送） | `open_chat` 返回 marker `发送给 王影`，说明会话切换正确 |
| 自动降级 | 230002/230027/230038 触发 `_schedule_bridge`，2 条单测覆盖（会调 / 不会误调） |
| 发图片 | 未通过：`browser_file_upload` 需要先打开文件选择器（modal state），桥里未点附件按钮 |

## Web 内部接口：可行（2026-11-19 18:01 实测）

先说结论：**发送消息不走 `/web/common`**。那只是安全组件的外壳请求，真正的 IM 请求是：

```
POST https://internal-api-lark-api.feishu.cn/im/gateway/
content-type: application/x-protobuf
x-command: 5        # 发消息
x-appid: 161471
x-source: web
```

请求体是 protobuf `Packet{cmd=5, cid, payload=PutMessageRequest{type=4, chatId(数字), cid,
isNotified=1, version=1, content.richText{innerText, elements{tag=1, property=TextProperty}}}}`。

前置两件事：

1. **Cookie**：`session`、`swp_csrf_token` 等（浏览器登录态，HttpOnly，必须从浏览器取）；
2. **数字 chatId**：接口不吃 `oc_xxx`。用 `x-command: 11021` 搜索拿数字 user/group id，
   再用 `x-command: 13` 建/取会话，返回 `chat.id`（如小Sugar `7672443693084724515`、
   王影 `7708810438795856910`）。

实测证据：

- 18:00 发到小Sugar：`send status 200`，payload 含原文；`+messages-search` 查到 `total: 1`
- 18:01 发到王影（跨租户）：`send status 200`；`+chat-messages-list` 显示
  `18:01 | user | 接口测试，请忽略`

前人实现：`cv-cat/OpenFeiShuApis`（x-command 5 / protobuf / cookie 登录态）；
`lza6/feishu-message-2API` 只做了接收（发送仍是 TODO）。

**通道顺序改为：官方 API → Web 内部接口（已验证）→ DOM（最终兜底）。**

### 已落地的实现（2026-11-19 18:43）

- `sugar_assistant/web_api.py`：自实现 protobuf 编码器，输出与 `OpenFeiShuApis` 逐字节一致
  （`tests/test_web_api.py` 固定 hex 断言）
- Cookie 来源：`data/web-cookies.json`；配置 `cdp_url` 时每次从调试浏览器刷新
- 数字 chatId 映射：`data/webapi-chats.json`（`oc_xxx → 数字 id`）
- `runtime._try_webapi`：官方接口返回 230027/230038 时先走 Web API，失败再降级 DOM
- 实测：18:00 小Sugar、18:01 王影、18:34 群、18:43 模块自测，四条全部 200 且消息可查

### web API 发图片：卡在 key 命名空间（2026-11-19 23:1x）

- 用 OpenAPI（bot 或 user 身份）上传图片都成功，拿到 `img_v3_...`
- 用 `type=5(IMAGE) + Content.imageKey` 发 `/im/gateway`，返回：
  `[ValidateKey] found invalid image key`
- 说明网关只认它自己（Service Worker 上传）产生的 key，OpenAPI 的 key 在同一字段里无效
- 结论：web API 通道不发附件，图片/文件继续由 user-cli 或 DOM 承担

### web API 其它消息类型（23:39-23:46）

| type | 内容 | 结果 |
| --- | --- | --- |
| 4 TEXT | richText 文本 | ✅ 文本 |
| 2 POST | 文本 | ✅ 落地为 post（23:39 验证，23:48 封装为 send_post） |
| 10 STICKER | `Content.fileKey` | ✅ msg_type=sticker |
| 14 CARD | richText / attachments 三种组合 | ❌ `PB payload unmarshal failed` |
| 5 IMAGE | `Content.imageKey`（OpenAPI 上传） | ❌ `invalid image key`（key 命名空间不同） |

### 抓包现状（2026-11-20 00:0x）

- 引擎已能记录 `postDataBuffer` 的 base64，但当前客户端发送不再出现在页面上下文：
  连续三次 `capture_send` 均 `requests=12 / frames=0`，无 `/im/gateway`、无 WS 帧。
- 推断发送由 Service Worker / 独立 worker 发起，页面级监听与 context 级监听都覆盖不到。
- 因此“抓真实卡片包”这条路暂时不可用，需要 CDP 级别 attach 到 worker target 才能继续。

### 突破：shared_worker 级抓包可用（00:2x）

- `/json/list` 里有 7 个 worker（1 个 service_worker + 6 个 shared_worker）
- 逐个 attach 并 `Network.enable` 后，一次文本发送抓到 3 条网关请求：
  `internal-api-lark-api.feishu.cn/im/gateway/`，postData 长度 85 / 247 / 41
- 说明页面级抓不到是因为请求由 shared_worker 发出；worker 级可以拿到明文 postData
- 下一步：用同样方式抓「转发卡片」的请求，解出 `type=14` 结构

补充：转发弹窗每次渲染不同（有时带搜索框，有时直接列最近会话），
固定 locator 会失败；`Ctrl+Enter` 也未能稳定触发发送。已成功转发过一次
（00:31 卡片进入会话），但当时的抓包输出因二进制被截断，未留存原始包。

### 卡片 type=14：字段试错记录（00:35）

| 组合 | 结果 |
| --- | --- |
| `Content.attachments` = 卡片 JSON | 400 `richText and card type need for card message`（包能解析） |
| `Content.richText` 字符串 | 400 `PB payload unmarshal failed` |
| `Content.text` + richText 字符串 | 同上 |
| RichText 消息（innerText/elements） | 同上 |

推断：服务端要求 `richText` + 一个 **card type** 字段，而本地 proto 里没有该字段
（`RichTextElement.tag` 枚举也没有 CARD），说明抓包用的 proto 版本落后于服务端。
继续盲试需要知道 card type 的字段号，否则无解。

### 字段号找到了（00:37）

对 `Content` 逐字段加 `varint 1` 试：

- 字段 **20** + richText → **HTTP 200**（其余字段仍报 card type 缺失）
- 但消息落地为 `msg_type=nonsupport`，说明 20 是“卡片类型”开关，取值 1 不对，
  或卡片正文的位置/编码仍不对
- 结论：`Content.cardType = field 20` 已确认；还需要 cardType 的正确枚举值
  与正文存放位置（richText 的 innerText 还是 element.property）

补充实测：

- `cardType` 只有 **1** 能过校验，0/2/3/4/5/10 全部 400
- 正文放 `Content.text` 或 `Content.attachments` 都会 `PB payload unmarshal failed`
- 唯一 200 的组合：`richText.innerText = 卡片 JSON` + `cardType=1`，
  但消息落地为 `msg_type=nonsupport`（客户端不认）
- 再试 element.tag = 11/14/18/37..43，全部 200 且全部 `nonsupport`：
  说明 tag 不是决定因素，正文位置/编码仍不对

### 抓到真实转发包（00:5x）

worker 级抓包记录到转发卡片时的网关请求：

| 长度 | cmd |
| --- | --- |
| 1425 | **77** |
| 558 | 77 |
| 125 / 105 / 95 | 77 |
| 其余 | 8 / 12 / 24 / 43 / 1009 / 12001 / 70006 / 70007 |

结论：**卡片不是走 cmd=5 + type=14**，而是 `cmd=77` 的另一套报文
（payload 是 4 个 field1 子消息，长度 186/341/689/168）。
这解释了为什么 cmd5 无论怎么填都只能得到 `nonsupport`。
真实字节已保存到 `workspace/TempOutput/card_packets.json`，可继续解析 cmd77 结构。

### cmd77 解包结果（01:0x）

cmd77 的 payload 是**批量信封**，里面并排 4 条子命令：

| 子命令 | 载荷 | 推测 |
| --- | --- | --- |
| 5101 | 140B 二进制 | 卡片/资源相关 |
| 24 | 296B，含多组 `chatId + messageId` | 转发引用（forward refs） |
| 12 | 644B，含 `7672443693084724515 → 7709922…` 对 | 会话/消息映射 |
| 5500 | 123B，`zh_CN` + 长 token | 国际化/资源 token |

结论：转发卡片不是"构造一张新卡片"，而是**提交一组消息引用**（cmd 24）。
这也解释了为什么 cmd5+type14 永远只能得到 `nonsupport`。
若要实现 Web API 发卡片，正确方向是复用一条已存在的卡片消息并对其做 forward（cmd 24）。

进一步解 cmd24：payload 是 **15 个 19 字节条目**，每个条目就是一个 19 位数字 id
（形如 7672443693084724515），即**内部消息 id 列表**，不是 chat+msg 组合。
要复刻转发，必须先把 `om_…` 映射到这种内部数字 id；当前 API 不返回该映射。

复核：这批抓包中 **没有任何卡片正文字符串**（`卡片`/`"title"`/`elements` 均未出现），
cmd24 的 19 位数字实际是小Sugar 的**会话 id**，不是消息 id。
说明这次 3 分钟窗口抓到的只是转发后的周边同步（feed/已读），
真正的卡片发送包没有被捕获，cmd77/cmd24 推断不成立。

再次干净窗口（先 attach 7 个 worker 再操作）：只抓到 12 条 20–94B 的小包，
对话框自动转发未真正发出（聊天最新消息仍停在 00:50），依旧没有卡片正文。
结论：卡片 Web API 的抓包复现成本已高于收益，建议长期由 CLI 发卡片。

### 同批修掉的隐蔽 bug（19:0x）

- `_poll_messages` 把含空格的绝对路径塞给 `lark-cli --params`，命令被拆开、返回空列表：
  表现是 user 模式「收不到消息」且回查永远失败。改为临时目录相对文件名 + `cwd`。
- `_send_as_user` 同样问题：`--params/--data` 绝对路径含空格 → `invalid file path`。
  统一走 `_cli_run`（`.cmd` 加引号 + cwd），并在发送后强制只读回查，查不到即报错。

### 定向做法（已验证）

不碰搜索页，直接点左侧会话行：

1. 导航到 `/next/messenger/`
2. `browser_find` 目标名，取**名字上方最近的 `cursor=pointer` 祖先**作为会话行 ref
3. 点击该行
4. 校验输入框占位符 `发送给 <名字>`，不匹配就中止

## 事故：2026-11-19 15:03

- 目标：私聊「小Sugar」
- 实际：消息发到了群「吴淑舸, 王影」（`om_x100b60ddbaebd4b0c4e6bf02e918ad6`）
- 用户选择保留，未撤回

### 根因

1. `browser_find("小Sugar")` 命中的是**外层容器**（`ref=f2e1`），点击后打开的是当时选中的会话，不是目标会话；
2. 所谓的“标题校验”读的是整页快照前 3000 字，侧边栏里本来就含「小Sugar」，**校验形同虚设**；
3. `send_text` 只在输入框写入后检查文本，未校验“当前会话”；
4. 返回 `ok=true` 只代表流程跑完，不代表发对了人——这是最严重的设计缺陷。

## 当前状态

- `permissions.services` 已清空，桥被总线拒绝，**不会再误发**
- 代码保留在 `plugins/browser-use/bridge.py`，未删除

## 若要继续，先改这四件事

1. **会话定位**：不点容器，改用快照里“会话列表项”节点（含未读数/时间的那个 group），或直接按 chat_id 打开深链；
2. **目标校验**：读会话头部标题（右侧聊天窗顶部），必须**完全等于**目标名，否则中止；
3. **发送前 dry-run**：先只填入不发送，返回截图与输入框内容，人工确认后再发；
4. **结果判定**：`ok` 必须来自“服务端回查到该会话新消息”，否则返回 `unknown`。

## 教训

- 自动化能点页面 ≠ 点对了地方；凡涉及“发给谁”，必须用**会话身份**校验，不能用页面里出现过名字来判断。
- 返回成功要绑定可验证的外部事实（服务端回查），不能只信流程跑完。
