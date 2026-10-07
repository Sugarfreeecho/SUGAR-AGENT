# SugarAgent 浏览器侧栏插件 · 完整设计文档

- 版本：**v0.9 草案（已归档）**
- ⚠️ 本文档已被 [browser_extension_sidebar_design_v2.md](browser_extension_sidebar_design_v2.md)（**v2 定稿**，19 项决策全部经用户确认）取代，此处仅作历史存档；实现请以 v2 为准。
- 关系：本文档是 [browser_extension_sidebar_plan.md](browser_extension_sidebar_plan.md)（现状分析 + 路线对比）的落地版。
- 状态说明：下表 5 项是**已确认决策**；其余章节（会话与标签页的绑定模型、消息渲染深度、附件身份链、协议缺口取舍、分发与工程形态、空态与文案等）目前仍是**设计假设**，须与用户逐条确认后才是定稿依据。
- 已确认决策（用户确认）：

| 议题 | 决策 |
|---|---|
| 目标浏览器/形态 | **Chrome / Edge 侧栏**（MV3 `sidePanel`）；不做 Firefox，不做独立整页 WebUI 入口 |
| 数据通道 | **Remote Control v1 WebSocket + 配对**（不用内部 WebUI HTTP/SSE，不用 iframe 壳） |
| 页面上下文 | **activeTab 按需提取**（点按钮/右键才读页面），不申请 `<all_urls>` |
| 功能边界 | 对话 + 停止 + 审批（基线） + **会话管理** + **附件（截图/图片/文档）** + **桌面通知/托盘联动**；不做 Tailscale 远程 |
| 会话管理形态 | **不占侧栏常驻列表**，采用 Page Assist 的 "chat history" 形态：顶部按钮唤起历史面板 |

---

## 1. 目标与非目标

**目标**

1. 在任意网页右侧栏打开 SugarAgent，完成完整一轮对话（流式输出、停止、继续）。
2. 工具审批卡片可在侧栏直接"允许/拒绝"，不强制回到主 WebUI。
3. 会话与主 WebUI / 手机端**同源共享**：同一会话可在多处同时订阅、事件一致、无重复。
4. 支持把**当前页正文或选中文本**作为上下文提问（"Chat with Webpage"）。
5. 支持附件：截图、图片、文档。
6. 与桌面端通知语义联动：侧栏开着时不被误判为"页面已关闭"。

**非目标（本期不做）**

- Firefox（`sidebar_action` 差异）、Safari。
- 独立整页 WebUI 入口、Chrome Web Store 上架（可作为 P3 之后）。
- 自动跟随页面/常驻全站注入/多标签 Tab Mention（用户选了 activeTab 按需路线）。
- 跨机远程（Tailscale）访问。
- 在侧栏内复刻主 WebUI 的全部能力（文件树、详情栏、Goal/子代理目录、技能选择器等）。侧栏只做"对话 + 上下文 + 审批 + 会话管理 + 附件"。

---

## 2. 现状约束（一句话版）

- 服务端：本机 FastAPI `127.0.0.1:8192`，**没有 CORS 中间件**（依据：全仓无 `CORSMiddleware/allow_origins`）。
- 已有正式外部客户端通道 **Remote Control v1**（默认关闭），提供配对、设备 token、scope 分级、幂等、审计、WS 事件流；方法与参数见 §5。
- 主前端是"单脚本 + 三栏 dock"结构、接口走相对路径，**不适合直接复用到窄侧栏**（依据：`frontend/src/app/index.js`、`frontend/vite.config.js`）。
- 结论：侧栏插件 = **新写的窄屏原生 UI + 复用 Remote Control 协议**，服务端只需配置级改动（+ 两个可选协议扩展，见 §12）。

---

## 3. 架构

```
┌──────────────────────────── 浏览器扩展（MV3, Chrome/Edge） ────────────────────────────┐
│                                                                                        │
│  sidepanel.html / sidepanel.js  ← 主界面（对话 / 历史面板 / 配对 / 设置）              │
│      │                 │                        │                                      │
│      │ chrome.runtime  │ chrome.runtime         │ WebSocket（侧栏页持有）              │
│      │ sendMessage     │ sendMessage            │ ws://127.0.0.1:8192/api/remote/v1/ws │
│      ▼                 ▼                        ▼                                      │
│  background.js                       [Remote Control v1：connect.challenge → connect]   │
│   · sidePanel.setPanelBehavior       [RPC: session.* / approval.*]                     │
│   · contextMenus（划词/整页）        [事件: session.event / connect.challenge]          │
│   · commands（快捷键）                          │                                      │
│   · chrome.scripting.executeScript              │                                      │
│      │                                          │                                      │
│      ▼                                          ▼                                      │
│  content/extract.js                     HTTP（仅附件上传，扩展页直连，loopback）        │
│  （activeTab 注入，提正文/选区）        POST /api/upload-chat-files                     │
└────────────────────────────────────────┬───────────────────────────────────────────────┘
                                         ▼
                     SessionControlService → 同一 Agent Runtime / 同一会话存储
                     （与主 WebUI、手机浏览器端、飞书适配器共享；见 app/remote_control/service.py）
```

**组件职责**

| 组件 | 职责 | 关键 API/依据 |
|---|---|---|
| `sidepanel`（扩展页） | 拥有 WS 长连接；渲染消息流、审批卡片、历史面板、配对与设置；发起附件上传 | `WebSocket`、`fetch`、`chrome.storage.local` |
| `background.js`（SW） | 侧栏行为开关、右键菜单、快捷键、按需注入提取脚本、角标 | `chrome.sidePanel.setPanelBehavior/open/setOptions`、`chrome.contextMenus`、`chrome.commands`、`chrome.scripting.executeScript` |
| `content/extract.js` | 在页面上下文里提取正文/选区/标题/URL，返回纯数据 | `document`、`getSelection()` |
| Remote Control 服务端 | 鉴权、scope、幂等、审计、事件扇出 | `app/remote_control/{gateway,service,store}.py` |

**为什么 WS 放在侧栏页而不是 SW**：MV3 的 Service Worker 会因空闲被回收（Chrome 116+ 才支持 SW 内 WebSocket，且需保活），而侧栏页是普通扩展页，生命周期跟用户可见状态一致——面板关闭即断开、打开即重连，语义最简单。若将来需要"面板关着也收推送/角标"，再单列一个 SW 持有连接的任务（本文档 §14 P3）。

---

## 4. 连接与配对

### 4.1 时序（首次使用）

```
用户：在电脑端生成一次性配对码
      （主 WebUI 远控页/命令行 POST /api/remote/v1/pairings，仅本机 loopback 可创建）

扩展侧栏：
  1. new WebSocket("ws://127.0.0.1:8192/api/remote/v1/ws")
  2. 收到 event: connect.challenge { nonce, protocol_version:1, auth_timeout_seconds:15 }
  3. 15s 内发送 req: {type:"req", id, method:"connect",
        params:{ nonce, pairing_code:"XXXX-XXXX-XXXX", device_name:"Chrome 侧栏 · <主机名>" }}
  4. res: {ok:true, result:{ connected:true, device:{device_id,name,scopes}, device_token:"<明文，仅此一次>" }}
  5. device_token 写入 chrome.storage.local（key: rc.deviceToken），UI 切到"已连接"
  6. 后续重连：步骤 1-3，params 里用 device_token（不再需要配对码）
```

依据：`app/remote_control/gateway.py:279-345`（握手 15s 超时、`connect` 必须是第一帧、nonce 校验、成功响应携带 `device_token`）、`_authenticate`（`device_token` / `token` / Cookie / `pairing_code` 四种凭据）、`app/templates/remote_control.html`（同款流程的参考实现）。

### 4.2 客户端状态机

```
unpaired ──(用户输入配对码 / connect{pairing_code})──► pairing ──成功──► connected
   ▲                                                        │失败(4401)      │
   └────────────────────────────────────────────────────────┘                │
                                                                   断线───────┘
                                                                     │
                                                                     ▼
                                                                 reconnecting（指数退避 2s→30s）
                                                                     │
                                        device_token 失效(4401/4402) ▼
                                                                  unpaired（提示重新配对）
```

### 4.3 错误码 → UI 文案映射

| 关闭码/错误 | 触发场景 | UI 表现 |
|---|---|---|
| `4404 remote control disabled` | 服务端未开远控 | 设置页提示：需在 `app/.env` 设 `MYAGENT_REMOTE_CONTROL_ENABLED=1` 并重启 |
| `4403 origin not allowed` | Origin 不在白名单 | 提示把 `chrome-extension://<ID>` 加入 `MYAGENT_REMOTE_CONTROL_ALLOWED_ORIGINS` |
| `4401 authentication timeout / failed` | 15s 内没握手 / 凭据无效 | 回到配对页，清空本地 token |
| `4400 invalid frame` | 协议帧不合法 | 仅日志；提示版本不匹配 |
| `4429 outbound queue overflow` | 客户端太慢，服务端主动断 | 自动重连 + 补历史（去重） |
| `session_busy` | 该会话已有运行 | 自动降级为 `session.steer{mode:"append"}`（参考实现做法） |
| `idempotency_key_required` | 写操作漏带幂等键 | 客户端 bug：所有写方法统一 `crypto.randomUUID()` |
| `approval_not_pending` | 审批已被别处处理 | 卡片置灰并提示"已在其他端处理" |
| 请求超时（客户端 20s 无响应） | 网络/服务端卡住 | 单条提示 + 重连检测 |

---

## 5. 协议使用清单

### 5.1 方法（全部来自 Remote Control v1，见 `app/remote_control/service.py`）

| UI 场景 | 方法 | 参数 | scope | 幂等键 |
|---|---|---|---|---|
| 连接自检 | `system.health` | — | read | 否 |
| 历史面板列表 | `session.list` | `{include_archived?}` | read | 否 |
| 打开某会话前校验 | `session.get` | `{session_id}` | read | 否 |
| 进入会话补历史 | `session.history` | `{session_id, turns:20}` 或 `{session_id, limit, before_index}` | read | 否 |
| 进入会话订阅 | `session.subscribe` | `{session_id, after_seq}` | read | 否 |
| 离开会话 | `session.unsubscribe` | `{session_id}` | read | 否 |
| 新建会话 | `session.create` | `{name?}` | write | **是** |
| 发送消息 | `session.send` | `{session_id, message, ui_message?, ui_language?, run_id?}` | write | **是** |
| 运行中追加/打断 | `session.steer` | `{session_id, message, mode:"append"│"interrupt", client_id}` | write | **是** |
| 停止 | `session.interrupt` | `{session_id, run_id?, reason?}` | write | **是** |
| 审批列表 | `approval.list` | `{session_id?}` | approvals | 否 |
| 审批处理 | `approval.resolve` | `{session_id, approval_id, approve, rejection_reason?}` | approvals | **是** |

### 5.2 事件映射（`session.event` 帧的 `payload.type` → UI）

| payload.type | UI 呈现 |
|---|---|
| `user` | 用户消息气泡 |
| `status` / `warning` / `error` | 灰色状态行（`error` 用红色）；与主 UI 一致 |
| `llm_response_delta` / `llm_reasoning_delta` | 打字机增量（**不进历史去重游标之外**；增量按 run 聚合后再落 DOM，参考 `smooth-stream` 思路） |
| `sse_keepalive` | 忽略（仅维持连接） |
| `tool_call` | 工具行（可折叠，展示命令/结果摘要） |
| `tool_approval_required` / `approval_requested` | **审批卡片**（允许/拒绝 → `approval.resolve`） |
| `context_trim_progress` / `context_summary_progress` / `key_context_progress` | 折叠进度条 |
| `subagent_start` / `subagent_finish` | 子代理徽标行（可选，P2） |
| `run_interrupted` | 中断提示 |
| `validate_final` | 完成态（配合 `finish` 收起"停止"按钮） |

> 参考实现里对 `llm_*_delta` 与 `sse_keepalive` 直接跳过渲染（`app/templates/remote_control.html:157`）；侧栏要做打字机效果，则对 `llm_response_delta` 做聚合渲染，其余同主 UI。

### 5.3 一致性与分页

- **先订阅后补历史**：`session.subscribe{after_seq: lastSeq}` → `session.history{turns:20}` → 历史渲染期间把新到事件放进 buffer，渲染完再 flush（参考实现 `selectSession` 的 `hydrating/hydrationBuffer`）。
- **去重游标**：每个会话维护 `lastSeq`，取值 `event.event_bus_seq ?? event.seq`，`Math.max` 单调递增。
- **向上翻页**：`session.history{session_id, before_index, limit}`（服务端 `_session_history` 支持 `before_index`），滚动到顶时加载。
- **提示词语言**：发送时带 `ui_language: "zh-CN" | "en"`，与服务端 `normalize_prompt_language` 对齐。

---

## 6. 侧栏 UI 设计

### 6.1 信息架构（4 个视图，均在同一 320–480px 面板内切换）

| 视图 | 入口 | 内容 |
|---|---|---|
| **对话**（默认） | 打开侧栏 | 消息流 + 上下文芯片 + composer（附件、发送、停止）+ 顶部工具条 |
| **历史**（Page Assist 式 chat history） | 顶部"历史"按钮（时钟图标） | 全屏覆盖层：搜索框 + 时间分组（今天/昨天/更早）+ 会话项（标题、最后消息时间、待审批徽标）+ 每项操作菜单（打开/改名/归档） |
| **配对** | 未配对时自动 | 配对码输入（`XXXX-XXXX-XXXX`）、设备名、连接状态、错误提示、"如何生成配对码"折叠说明 |
| **设置** | 顶部齿轮 | 服务地址（默认 `http://127.0.0.1:8192`，只读 + 高级可改）、上下文长度上限、语言、主题、清除本设备凭据（本地）+ 提示"撤销设备需在主 WebUI/命令行" |

### 6.2 线框图（对话视图）

```
┌────────────────────────────────────────┐
│ ⟳ 已连接 · 会话：角标修复   ⏱历史 ＋ ⚙ │  ← header（状态点/标题/历史/新建/设置）
├────────────────────────────────────────┤
│                                        │
│            用户消息气泡（右）          │
│                                        │
│  助手消息（左，Markdown 渲染）         │
│  ▸ 工具：read_file agent_loop.py …     │  ← 可折叠
│  ┌ 需要确认：执行命令 ──────────────┐  │
│  │ rm -rf build/                    │  │
│  │           [拒绝]      [允许]     │  │  ← 审批卡片
│  └──────────────────────────────────┘  │
│                                        │
│  ── 运行中…  [停止]                    │
├────────────────────────────────────────┤
│ 📄 当前页：设计文档 · 3.2k 字  ✕       │  ← 上下文芯片（可移除/可换"仅选中"）
│ ┌────────────────────────────────────┐ │
│ │ 输入消息…                     📎 ➤ │ │  ← composer
│ └────────────────────────────────────┘ │
└────────────────────────────────────────┘
```

### 6.3 交互细节

- **上下文芯片**：三种来源——「当前页正文」「当前页选中文本」「仅 URL（让 Agent 自己抓）」。默认不自动附加：用户点 `📄` 或右键菜单才注入；芯片可编辑（改标题/删正文）与参数（截断长度）。
- **附件**：`📎` → 截图当前可见区域 / 选择本机文件（`<input type=file>`，含拖拽）。
- **停止 / 追加**：运行中 `➤` 变为 `停止`；输入框仍可用，回车即 `session.steer{mode:"append"}`（失败则提示）。
- **审批卡片**：`tool_approval_required` 到达即插入卡片（置顶滚动）；处理成功后卡片就地变为结果行。
- **快捷键**：`Ctrl+Shift+M` 打开/聚焦侧栏（`chrome.commands`，避免与 Page Assist 的 `Ctrl+Shift+Y` 冲突）；侧栏内 `Esc` 关历史面板、`Enter` 发送、`Shift+Enter` 换行。
- **右键菜单**（`chrome.contextMenus`）：选中文本 →「就选中内容提问」；页面空白 →「把当前页发给 SugarAgent」。
- **空态**：无会话时显示"新建会话"；未配对显示配对引导；服务端不可达显示排障三步（服务未启动 / 远控未开启 / 白名单缺失）。
- **窄宽适配**：content 区 `min-width: 300px`；消息气泡左右边距 8px；工具行长文本折行 + 一键复制；表格式工具结果默认折叠为"展开查看"。
- **主题**：默认跟随系统 `prefers-color-scheme`；提供深/浅手动覆盖（与主 UI 的深色令牌风格近似，但不复用其 CSS 文件）。
- **i18n**：内置 zh-CN / en 两份文案（扩展内自维护，独立于主 UI 的 `i18n.js`）。

---

## 7. 页面上下文提取（activeTab 按需）

**授权模型**：不申请 `<all_urls>`。用户点击扩展图标打开侧栏、或使用右键菜单/快捷键时，浏览器授予该标签页的 `activeTab`，此刻注入才合法。

**流程**

```
侧栏点「📄 当前页」→ runtime.sendMessage({type:"extract-page", mode:"auto"|"selection"})
   → SW：chrome.tabs.query({active:true, currentWindow:true}) 取 tabId
   → SW：chrome.scripting.executeScript({target:{tabId}, files:["content/extract.js"]})
   → content 脚本返回 { url, title, selection, text, truncated, charCount, siteName }
   → 侧栏渲染上下文芯片（可预览前 N 字）
```

**提取算法（readability 简化版）**

1. 若 `mode === "selection"` 且 `getSelection().toString()` 非空 → 直接用它（≤ 上限则全文）。
2. 否则：克隆 `document.body`，移除 `script/style/noscript/svg/iframe/nav/header/footer/aside/form/[aria-hidden=true]`；按块级元素文本长度打分，选主容器（`article`/`main`/最大文本块）。
3. 归一化空白，保留段落换行；
4. 输出上限默认 **8000 字符**（设置可调 2000–20000），超出截断并标注 `…（已截断，原 N 字）`；
5. 附 `title`、`url`、`siteName`，供 Agent 判别来源。

**消息拼装（客户端固定格式，便于主 UI 侧回看）**

```
[网页上下文]
标题: <title>
网址: <url>
内容:
<正文>

<用户真正的问题>
```

**隐私与安全**：页面内容只在用户显式操作后才读取；不写入扩展日志、不同步到远端（`chrome.storage` 仅存设置与凭据）；设置页提供"禁用页面上下文"总开关。

---

## 8. 附件（截图 / 图片 / 文档）

### 8.1 服务端现有契约（已核对）

- 上传：`POST /api/upload-chat-files`（multipart，字段名 `files`，可多文件）。限制：单文件 100 MB、合计 200 MB（依据 `app/webui.py:2543`）。
  - 图片（`image/*` 或 `.png/.jpg/.jpeg/.webp/.gif/.bmp`）：落盘后转成附件仓库对象，返回 `files[i].attachment`（ref）+ `files[i].url = /api/attachments/<id>`，并 `AttachmentRegistry.grant(actor.device_id, ids)`。
  - 非图片：返回 `files[i].path`（绝对路径，位于 `<WORK_DIR>/uploads/chat/YYYYMMDD/`）与 `rel`（工作区相对路径）。
- 鉴权（`app/attachments/access.py`）：**loopback 直连 → `DevicePrincipal("local", …, {"admin"})`**；非 loopback 才需要 `Authorization: Bearer <device_token>` 或远控 Cookie；**带 Origin 且与 Host 不一致时必须在 `allowed_origins` 白名单内**，否则 403 `Cross-origin attachment access denied`。
- 发送：`/chat` 接受 `attachments`（JSON 字符串），逐项解析为结构化内容：`{"type":"image","attachment":ref}` 或 `{"type":"local_file","local_file":{path,name}}`，最终经 `user_content=...` 交给 `astream_events`（依据 `app/webui.py:5259-5304, 5340`）。
- **Remote Control 的 `session.send` 目前不支持附件**（依据 `app/remote_control/service.py::_session_send` 只读 `message/ui_message/ui_language/run_id`）。

### 8.2 设计（推荐路径：协议增加 `attachments`）

1. 扩展页/SW 直连 loopback 上传（`host_permissions` 覆盖 `http://127.0.0.1:8192/*`；扩展页与 SW 的跨源 fetch 不受 CORS 约束）。
2. 拿到的附件项原样放进 `session.send` 的新参数：
   ```json
   {"method":"session.send","params":{
     "session_id":"…","message":"…",
     "attachments":[
       {"type":"image","attachment":{"attachmentId":"…"}},
       {"type":"local_file","local_file":{"path":"D:\\…\\uploads\\chat\\20260930\\spec.pdf","name":"spec.pdf"}}
     ]}}
   ```
3. 服务端 `_session_send` 里校验并转结构化内容（复用 `/chat` 的解析逻辑），`user_content=` 传给 `astream_events`（`astream_events` 已支持 `user_content`，无需改签名）。
4. **身份链说明**：上传走 loopback → 归属 `local`(admin) 主体；而 WS 侧主体是设备（非 admin）。因此协议扩展里对 `image` 项做 `require_attachment` 时需按"本机来源"主体校验（或在上传响应里由扩展显式把 ref 授权给自己的 device_id）。**这是本设计唯一一处需要明确取舍的安全细节**，建议实现时二选一并在代码注释中写明理由：
   - (A) 服务端按 `local`(admin) 校验（因为上传本身要求本机可达、文件已在本机工作区内）；
   - (B) 上传时用 `Authorization: Bearer <device_token>` 并把 ref 直接 grant 给设备（更严格，但需绕过 loopback 短路分支，改动更大）。

### 8.3 零服务端改动回退方案（若暂不做协议扩展）

- **文档类**：上传后拿 `files[].rel`（工作区相对路径）或 `files[].path`（绝对路径），以一行文本追加到消息里，例如：
  `[附件] uploads/chat/20260930/spec.pdf`，由 Agent 自行用工具读取。
- **截图/图片**：`chrome.tabs.captureVisibleTab` 得到 dataURL → 上传（图片走附件仓库）→ 同上把 `rel` 路径写入消息，Agent 可在工作区内读取该图片。
- 代价：附件不是"一等公民"（不参与多模态自动装配、不显示为附件缩略图），仅作为可用性兜底。**推荐 P2 直接做 §8.2，回退方案仅用于过渡。**

---

## 9. 会话管理（Page Assist 式历史面板）

**只读部分（协议已覆盖，P0 即可做）**：`session.list`（含归档开关）、`session.get`、`session.history` 分页；客户端搜索 = 按标题/时间本地过滤（协议没有全文搜索，若要跨会话搜内容需另立需求）。

**写操作缺口**：远控协议目前**没有**改名/归档/置顶/待办/删除方法；这些能力只存在于 loopback 的 WebUI 路由（`PUT /sessions/{id}/name`、`/archive`、`/pin`、`/todo`、`DELETE /sessions/{id}`，依据 `app/webui.py:6631/6712/6719/6726/3981`）与 `session_manager`（`set_session_name`/`set_session_archived`/`set_session_todo`，依据 `app/agent_harness.py:7158/7209/7262`）。

三个选项：

| 选项 | 做法 | 评价 |
|---|---|---|
| **① 协议扩展（推荐）** | 在 `service.py` 增加 `session.update`（params: `{session_id, name?, archived?, todo?}`，scope=write，幂等），handler 调 `session_manager.set_session_name/set_session_archived/set_session_todo` | 契约清晰、可审计、手机端将来同样受益；服务端改动小（约 20 行 + 方法表一行） |
| ② SW 直连 loopback 内部路由 | 扩展后台调 `PUT /sessions/{id}/name` 等 | 零服务端改动，但把**未鉴权内部路由**变成事实契约，未来服务端重构会打破客户端 |
| ③ 只做新建/切换（不复刻改名） | 改名/归档仍回主 WebUI | 最省事，但历史面板体验不完整 |

**建议**：P2 实施 ①，并在文档中标注"客户端不得使用内部路由"这一约束。

**历史面板细节**：分组（今天/昨天/本周/更早）、每项显示标题 + 最后活动时间 + 待审批徽标、点击进入会话、长按时长出现操作菜单（改名/归档）；面板顶部一个"新建会话"按钮（`session.create`）。

---

## 10. 与桌面端联动（presence / 托盘 / 通知）

- 服务端语义：`POST /api/ui-presence {action: register|update|unregister, token, active, session_id}`；**有 UI 存在时**不发"页面已关闭但仍运行"的桌面通知；最后一份 token 过期（TTL 默认 300s、下限 90s）或注销后才通知（依据 `app/webui.py:237-242, 4690-4712, 5012-5050`）。
- 侧栏做法（对齐主 UI 的调用方式：`navigator.sendBeacon` 优先、10s 心跳、`pagehide` 注销，依据 `frontend/src/app/modules/message-rendering.js:1735-1783`）：
  - 面板加载 → `register`（token = `crypto.randomUUID()` 存内存 + `session` 级存储）；
  - 每 10s → `update`（带上当前 `session_id`）；
  - 面板卸载/浏览器关闭 → `unregister`（`sendBeacon` + `keepalive`）。
- `active` 语义：面板可见且有焦点 → `true`；侧栏被切换到后台标签页不可见 → `false`（与服务端"注意力"语义一致）。
- 可选（P3）：待审批数 > 0 时用 `chrome.action.setBadgeText` 显示角标；审批到达而面板未打开时，可通过 `chrome.notifications` 提示（需要 SW 侧连接或额外轮询，不在本期）。

---

## 11. 权限与安全

**manifest 权限（最小集）**

| 权限 | 用途 | 说明 |
|---|---|---|
| `sidePanel` | 侧栏 | 必需 |
| `storage` | 存 device_token 与设置 | `chrome.storage.local` |
| `activeTab` | 按需读当前页 | 用户手势触发，不申请 `<all_urls>` |
| `scripting` | 注入提取脚本 | 配合 `activeTab` |
| `contextMenus` | 划词/整页入口 | 可选但推荐 |
| `host_permissions: http://127.0.0.1:8192/*, http://localhost:8192/*` | WS/HTTP 访问本机 Agent | 不申请任何公网域 |

**安全约束**

1. 配对凭据只存 `chrome.storage.local`，不进 `sync`、不外传、不写日志；提供"清除本机凭据"入口。
2. 请求 scope 只用默认三元组 `read/write/approvals`，**不要 `admin`**（与手机端默认一致，依据 `app/remote_control/store.py:16-17`）。
3. 白名单只加本扩展 ID：`MYAGENT_REMOTE_CONTROL_ALLOWED_ORIGINS=chrome-extension://<固定ID>`。该白名单同时被附件接口的跨源校验复用（依据 `app/attachments/access.py`），因此**不要**写通配符。
4. **不新增服务端 CORS 中间件**：主通道是 WebSocket（不受 CORS 约束），附件走 loopback + 白名单校验；避免把 `127.0.0.1:8192` 的未鉴权 WebUI 路由暴露给任意网页。
5. 服务端保持只监听 `127.0.0.1`（依据 `docs/remote_control.md` 的安全模型）。
6. 页面内容只在用户显式操作时读取；提供总开关。
7. 设备撤销：撤销需在电脑端执行（`DELETE /api/remote/v1/devices/<id>`，本机专用）；扩展侧只清本地凭据（依据 `app/remote_control/gateway.py:196+`）。

---

## 12. 服务端改动清单

| # | 改动 | 级别 | 位置与做法 |
|---|---|---|---|
| 1 | 开启远控 | **必须** | `app/.env`：`MYAGENT_REMOTE_CONTROL_ENABLED=1`（改后重启；`app/.env.example:176` 已列出该键） |
| 2 | Origin 白名单 | **必须（实测确认）** | `app/.env`：`MYAGENT_REMOTE_CONTROL_ALLOWED_ORIGINS=chrome-extension://<ID>`；若实测发现扩展页 WS 不带 `Origin`，该项可省，但仍建议保留 |
| 3 | 固定扩展 ID | **必须（工程）** | `manifest.json` 的 `"key"` 字段；否则 ID 随加载路径变化，白名单反复失效 |
| 4 | `session.send` 支持 `attachments` | 可选（P2 推荐） | `app/remote_control/service.py::_session_send` 解析 `params.attachments` → 复用 `/chat` 的解析逻辑（`app/webui.py:5259-5304`）→ `astream_events(..., user_content=structured)`（签名已支持，`app/agent_loop.py:9475` 的 `user_content`） |
| 5 | `session.update`（改名/归档/待办） | 可选（P2 推荐） | `service.py`：`METHOD_SCOPES` 加 `session.update: "write"`、`IDEMPOTENT_METHODS` 加它、handlers 加实现，调 `session_manager.set_session_name/set_session_archived/set_session_todo` |
| 6 | 文档 | 建议 | `docs/remote_control.md` 补两节：浏览器扩展客户端接入、附件与 `session.update` 新参数 |
| 7 | 测试 | 建议 | `tests/` 下加：`session.send` 带附件的单测、`session.update` 权限与幂等单测（沿用现有远控测试风格） |

> P0/P1 阶段**不需要改任何 Python 代码**；#4/#5 只在要做"一等附件"与"侧栏内改名/归档"时才动。

---

## 13. 目录结构与模块接口

```
browser-extension/
  manifest.json
  background.js
  sidepanel.html
  sidepanel.js
  styles/theme.css, styles/panel.css
  content/extract.js
  lib/rc-client.js        # 协议客户端（唯一与后端耦合的模块）
  lib/format.js           # 事件 → DOM 片段、Markdown 渲染（不引入构建链）
  lib/i18n.js             # zh-CN / en
  README.md               # 安装、固定 ID、.env 配置、配对、排障
```

**manifest 骨架**

```json
{
  "manifest_version": 3,
  "name": "SugarAgent Sidebar",
  "version": "0.1.0",
  "minimum_chrome_version": "116",
  "key": "<用于固定扩展 ID 的 base64 公钥>",
  "permissions": ["sidePanel", "storage", "scripting", "contextMenus", "activeTab"],
  "host_permissions": ["http://127.0.0.1:8192/*", "http://localhost:8192/*"],
  "action": { "default_title": "打开 SugarAgent 侧栏" },
  "side_panel": { "default_path": "sidepanel.html" },
  "background": { "service_worker": "background.js" },
  "commands": {
    "toggle-side-panel": {
      "suggested_key": { "default": "Ctrl+Shift+M" },
      "description": "打开/聚焦 SugarAgent 侧栏"
    }
  }
}
```

**`lib/rc-client.js` API 面**

```js
createRcClient({ baseUrl, onEvent, onStateChange, storage })
  .connect({ pairingCode?, deviceName?, deviceToken? })   // → { device:{device_id,name,scopes}, deviceToken? }
  .rpc(method, params, { idempotencyKey }?)               // → result（内部超时 20s）
  .subscribe(sessionId, { afterSeq })                     // 包装 session.subscribe
  .close()                                                // 主动断开（不触发重连）
  // 自动重连：2s→4s→8s…上限 30s；重连后按 lastSeq 补拉
```

**side panel ↔ SW 的 IPC 消息**

| type | 方向 | 载荷 | 说明 |
|---|---|---|---|
| `extract-page` | panel → SW | `{mode:"auto"│"selection"}` | SW 注入并回传 `{url,title,selection,text,charCount,truncated}` |
| `capture-visible` | panel → SW | `{}` | 回传 `dataUrl`（截图附件） |
| `open-side-panel` | SW → (self) | `{tabId}` | 记录"哪个标签页打开了侧栏"用于上下文 |

**`chrome.storage.local` 结构**

```json
{
  "rc.baseUrl": "http://127.0.0.1:8192",
  "rc.deviceToken": "<secret>",
  "rc.device": { "device_id": "…", "name": "Chrome 侧栏 · PC", "scopes": ["read","write","approvals"] },
  "prefs.language": "zh-CN",
  "prefs.contextChars": 8000,
  "prefs.theme": "system",
  "prefs.pageContextEnabled": true,
  "ui.lastSessionId": "…"
}
```

---

## 14. 分阶段计划与验收

| 阶段 | 交付 | 验收（DoD） |
|---|---|---|
| **P0 骨架** | manifest + sidepanel 基础布局 + `rc-client`（握手/重连/RPC/去重）+ 配对视图 + 会话读取 + 发送/停止 | 侧栏完成一整轮对话；主 WebUI 同时打开同一会话，两端事件一致无重复；杀掉 Agent 后能自动重连并补历史 |
| **P1 页面上下文** | `content/extract.js` + 上下文芯片 + 右键菜单 + 快捷键 | 文章页点一次即得正文上下文；回答确实引用了页面内容；未点击时不注入（可在页面里用 `chrome://extensions` 的 service worker 日志核实） |
| **P2 完整功能** | 历史面板（Page Assist 式：搜索/分组/新建/改名/归档）+ 审批卡片 + presence 注册 + 附件（截图/图片/文档）+ 未读/待审批提示 | 历史面板可改名归档（走 `session.update`）；截图与 PDF 能进入同一条消息且 Agent 正确读到；侧栏打开时不再被误判为"页面已关闭" |
| **P3 增强（可选）** | 角标通知（SW 持有连接）、Markdown 增强（代码块复制、Mermaid 按需）、`.crx` 打包、（若将来需要）远程地址复用 | 面板关闭时仍能收到"需要审批"的角标；打包产物可在干净浏览器加载 |

---

## 15. 测试计划

**手工用例（必须）**

1. 首次配对：错误码 → 正确码；配对码过期（10 分钟）后的提示。
2. 端到端对话：普通问答 / 长回答流式 / 中断 / 追加（`steer append`）。
3. 审批：触发一次需要审批的工具调用 → 侧栏允许 → 主 WebUI 同步看到结果；两侧同时打开时的竞态（后点的一侧应提示"已在其他端处理"）。
4. 页面上下文：文章页 / SPA（懒加载）/ 选中文本 / 超长页（截断提示）。
5. 附件：截图、PNG、PDF 各一；超限文件（>100MB）的错误提示。
6. 稳定性：断网、服务重启、`4429` 溢出断开后的自动恢复。
7. 桌面联动：侧栏开 → 关闭 → 观察托盘/通知行为（`app/desktop_notify.py`）。

**负向用例（必须）**

- 白名单移除后连接应被 `4403` 拒绝（证明校验真的生效）。
- 远端 token 撤销后，侧栏应报 `4401` 并回到配对页。
- 不带 `idempotency_key` 的写操作应被拒（客户端不应出现此路径，作为断言）。

**可自动化（P2 起）**

- `rc-client` 的纯逻辑（帧解析、去重、退避）用 Node 单测（无浏览器依赖）。
- 服务端新增的 `session.send` 附件解析与 `session.update` 用 pytest（沿用 `tests/` 现有远控测试风格）。

---

## 16. 风险、待实测与待定

**风险**

| 风险 | 影响 | 缓解 |
|---|---|---|
| MV3 生命周期（SW 回收） | WS 若放在 SW 会频繁断线 | 本期 WS 固定由侧栏页持有 |
| 侧栏宽度 320–480px | 信息密度不足、工具行难读 | 工具行默认折叠；不做三栏；上线前用 380/420/480 三档真机截图定稿 |
| 内部实现变动 | 若误用 WebUI 内部路由会随版本失效 | 只走 Remote Control 契约；改名/归档也建议做成协议方法（§9①） |
| 附件身份链（loopback=admin） | 安全语义边界模糊 | §8.2 明确二选一并在代码注释写明理由；白名单不写通配符 |
| 浏览器差异（Edge） | 白名单/Origin 用 `edge-extension://` | README 分别给出两行配置示例 |

**待实测（实现第一步就验证，别先写 UI）**

1. 扩展页发起 WS 是否携带 `Origin: chrome-extension://<id>` → 决定 #2 是否必须。
2. 扩展页/SW 连 `ws://127.0.0.1:8192` 是否被 CSP/host 权限拦截（预期不拦）。
3. loopback 上传 + 协议扩展后的附件校验路径是否符合预期（§8.2 A/B 二选一）。

**待定**

- 上下文默认长度（先 8000 字符，按实测 token 消耗调整）。
- 是否需要"会话内搜索"（协议无全文搜索，需单独立项）。
- 图标与品牌色（暂用现有 `app/assets/sugar-logo.png` 的视觉基调）。

---

## 17. 参考依据

- 服务端与协议：`app/main.py`、`app/webui.py:1862`（`/`）、`:2543`（上传）、`:5012`（presence）、`:5120`（`/chat`）、`:5259-5304,5340`（结构化附件 → `user_content`）、`:6631/6712/6719/6726/3981`（会话改名/归档/置顶/待办/删除）、`app/agent_loop.py:9475`（`astream_events` 签名含 `user_content`）。
- 远控：`app/remote_control/gateway.py:48-59,99-106,136+,239-345`、`service.py`（方法表/幂等/`_session_send`/`_session_steer`/`_approval_*`）、`store.py:16-17`、`config.py`、`docs/remote_control.md`、`app/templates/remote_control.html`（参考客户端）。
- 附件：`app/attachments/access.py`（loopback→admin、Origin 校验、`require_attachment`）、`app/webui.py:2543`（100MB/200MB 限制与返回结构）。
- 会话：`app/agent_harness.py:7158/7209/7262`（归档/待办/改名）、`list_sessions`。
- 前端参考：`frontend/src/app/modules/message-rendering.js:1735-1783`（presence 心跳与 sendBeacon 用法）、`frontend/vite.config.js`。
- 外部依据：Chrome 官方 `sidePanel` API（`setPanelBehavior`/`setOptions`/`open`、`action` 必需、`side_panel.default_path`）、MV3 跨源访问（`host_permissions` 下扩展页/SW 的 fetch 不受 CORS 约束，content script 仍受限）、Page Assist 的 sidebar + chat history + Chat With Webpage 形态。
