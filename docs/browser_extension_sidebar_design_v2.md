# SugarAgent 浏览器侧栏插件 · 设计文档（定稿）

- 版本：**v2.1 定稿**（2026-09）｜v2 → v2.1：并入 D20（交付形态：独立扩展，不纳入插件体系）｜最早稿：`browser_extension_sidebar_design.md`（v0.9 草案，仅存档）
- 关系：上游分析见 [browser_extension_sidebar_plan.md](browser_extension_sidebar_plan.md)（代码现状 + 三条路线对比）
- 本文档中所有决策均由用户逐条确认（见 §0 决策台账）；未经确认的内容一律集中在 §18「默认假设与遗留项」，不散落在正文。

---

## 0. 决策台账（20 项，全部为用户确认）

| # | 议题 | 决策 |
|---|---|---|
| D1 | 目标浏览器/形态 | **Chrome / Edge 侧栏**（MV3 `sidePanel`）；不做 Firefox，不做独立整页 WebUI 入口 |
| D2 | 数据通道 | **Remote Control v1 WebSocket + 配对**（不用内部 WebUI HTTP/SSE，不用 iframe 壳） |
| D3 | 页面上下文 | **activeTab 按需提取**，不申请 `<all_urls>` |
| D4 | 功能边界 | 对话 + 停止 + 审批基线，外加会话管理、附件、桌面通知联动；**不做** Tailscale 远程 |
| D5 | 会话管理形态 | **Page Assist 式 chat history 面板**（顶部按钮唤起），不占侧栏常驻列表 |
| D6 | 会话 ↔ 标签页绑定 | **全局单会话、手动切换**；页面上下文随当前标签页变化 |
| D7 | 渲染深度 | **全量对齐主 UI**（Markdown/高亮/表格/Mermaid/工作区图片/思考过程/工具行/进度条/子代理徽标） |
| D8 | 协议扩展 | **直接做**（不走"路径写进消息"的回退方案作为最终形态） |
| D9 | 工程形态 | **无构建链**（原生 ESM）+ 开发者模式加载本地扩展 |
| D10 | 渲染资源复用 | **复用主 UI 同源的库与主题令牌**，文件**打包进扩展包**（MV3 禁止远程脚本） |
| D11 | 协议补齐清单 | 四项全要：`session.update`、模型档案、技能、审批 AI 分析 |
| D12 | 附件校验口径 | **A：按本机来源校验**（上传走 loopback 即 `local`/admin 主体） |
| D13 | 未读与推送 | **侧栏内多订阅 + 未读徽标**；不做浏览器级角标/系统通知 |
| D14 | 打开方式 | 点图标=开侧栏 + 快捷键 `Ctrl+Shift+M` + 右键菜单两项 |
| D15 | 语言与主题 | 深浅色跟随系统；界面 **zh-CN / en 双语**，可手动切换 |
| D16 | 历史面板操作 | 改名、归档、置顶、标记待办、删除会话、**会话内容搜索** |
| D17 | 审批卡片 | 允许 / 拒绝（理由**选填**）+ **AI 分析**按钮 |
| D18 | 启用与固定 ID | **文档指引 · 手动两步**（改 `app/.env` 两行；扩展用 `manifest.key` 固定 ID） |
| D19 | 上下文默认行为 | **手动点才附加**，含"仅发网址"模式（受信/预批准域名限制，可能被拦） |
| D20 | 交付形态 | **独立 MV3 扩展目录 `browser-extension/`**，**不纳入**仓库插件体系（Plugin API v1）；备选方案与证据见 §18「已评估并否决」 |

---

## 1. 目标与非目标

**目标**

1. 任意网页右侧栏打开 SugarAgent，完成完整一轮对话（流式输出、停止、运行中追加）。
2. 工具审批可在侧栏完成：允许 / 拒绝（理由选填）+ AI 分析。
3. 会话与主 WebUI、手机端**同源共享**：会话列表、历史、实时事件一致。
4. 页面上下文问答：当前页正文 / 选中文本 / 仅网址三种来源，手动触发。
5. 附件：截图、图片、文档，可随消息发送。
6. 会话管理：历史面板内改名 / 归档 / 置顶 / 待办 / 删除 / 内容搜索。
7. 未读提示：其它会话有新事件时在侧栏内显示徽标。
8. 渲染与主 UI 对齐；中英双语；深浅色跟随系统。
9. 桌面端联动：侧栏在线时不被误判为"页面已关闭"。

**非目标（本期不做）**

- Firefox / Safari；独立整页 WebUI 入口；Chrome Web Store 上架。
- 跨机远程（Tailscale）访问；`<all_urls>` 全站常驻注入。
- **面板级**复刻主 UI 的独立面板（详情栏文件树、Goal 面板、待办计划面板、子代理目录面板、技能市场等）——见 §18 L1。
- 浏览器级通知（工具栏角标、系统通知）——见 D13。
- 不把扩展纳入仓库插件体系（Plugin API v1）——见 D20 与 §18「已评估并否决的备选方案」。

---

## 2. 现状约束（一句话版）

- 服务端：本机 FastAPI `127.0.0.1:8192`，**无 CORS 中间件**（依据：全仓无 `CORSMiddleware/allow_origins`）。
- 已有正式外部客户端通道 **Remote Control v1**（默认关闭）：配对码 → `device_token`、scope 分级（默认 `read/write/approvals`）、写方法强制幂等键、审计日志、WS 事件流。
- 主前端是"单脚本 + 三栏 dock"结构、接口走相对路径，**不适合复用到窄侧栏**；但它的**第三方库与视觉令牌可以复用**（D10）。
- 侧栏 = **新写的窄屏原生 UI + Remote Control 协议**；服务端需要按 §14 补若干方法（已确认要做）。

---

## 3. 架构

```
┌──────────────────────────── 浏览器扩展（MV3, Chrome/Edge） ────────────────────────────┐
│  sidepanel.html / sidepanel.js  ← 主界面（对话 / 历史面板 / 配对 / 设置）              │
│      │                 │                        │                                      │
│      │ chrome.runtime  │ chrome.runtime         │ WebSocket（侧栏页持有，单连接）       │
│      ▼                 ▼                        ▼                                      │
│  background.js                          ws://127.0.0.1:8192/api/remote/v1/ws            │
│   · sidePanel 行为/开关                  [connect.challenge → connect{device_token}]     │
│   · contextMenus（2 项）                  [RPC：session.* / approval.* / model.* …]      │
│   · commands（Ctrl+Shift+M）              [event：connect.challenge / session.event]     │
│   · scripting.executeScript                       │                                     │
│      │                                            │                                     │
│      ▼                                            ▼                                     │
│  content/extract.js                        HTTP（仅附件上传，loopback 直连）             │
│  （activeTab 注入：正文/选区）              POST /api/upload-chat-files                  │
└────────────────────────────────────────┬───────────────────────────────────────────────┘
                                         ▼
                     SessionControlService → 同一 Agent Runtime / 同一会话存储
                     （与主 WebUI、手机浏览器端、飞书适配器共享）
```

**组件职责**

| 组件 | 职责 |
|---|---|
| `sidepanel`（扩展页） | 持有 WS 单连接；渲染消息流/审批卡/历史面板/设置；发起附件上传；维护多会话订阅与未读计数；注册 UI presence |
| `background.js`（SW） | 侧栏行为（`setPanelBehavior`）、右键菜单、快捷键、activeTab 注入、`captureVisibleTab` 截图 |
| `content/extract.js` | 页面内提取标题/URL/选中文本/正文（纯数据返回，不渲染） |
| 服务端 | 鉴权、scope、幂等、审计、事件扇出 + §14 新增方法 |

**WS 归属决策**：连接由**侧栏页**持有（普通扩展页无空闲回收问题）；SW 不持有连接，因此本期不做"面板关闭后仍推送"（与 D13 一致）。

---

## 4. 连接、配对与启用流程（对应 D18）

### 4.1 首次配对时序

```
① 电脑端：创建一次性配对码（默认 10 分钟、一次性）
   POST http://127.0.0.1:8192/api/remote/v1/pairings   ← 仅本机 loopback 可创建
   {"label":"Chrome 侧栏","scopes":["read","write","approvals"]}   ← 不给 admin

② 侧栏：
   new WebSocket("ws://127.0.0.1:8192/api/remote/v1/ws")
   ← event connect.challenge { nonce, protocol_version:1, auth_timeout_seconds:15 }
   → req   {type:"req", id, method:"connect", params:{ nonce, pairing_code:"XXXX-XXXX-XXXX", device_name:"Chrome 侧栏 · <主机名>" }}
   ← res   {ok:true, result:{ connected:true, device:{device_id,name,scopes}, device_token:"<仅此一次明文>" }}
   把 device_token 存 chrome.storage.local

③ 之后重连：同一地址，params 用 device_token（不再需要配对码）
```

依据：`app/remote_control/gateway.py:279-345`（握手/15s 超时/`connect` 必须是首帧/nonce 校验/成功响应含 `device_token`）、`_authenticate`（`device_token`｜`token`｜Cookie｜`pairing_code` 四种凭据）、参考客户端 `app/templates/remote_control.html`。

### 4.2 启用步骤（文档要写进扩展 README）

1. `app/.env` 增：`MYAGENT_REMOTE_CONTROL_ENABLED=1`
2. `app/.env` 增：`MYAGENT_REMOTE_CONTROL_ALLOWED_ORIGINS=chrome-extension://<固定ID>`（Edge 另加 `edge-extension://<ID>`）
3. 重启 SugarAgent；`manifest.json` 的 `"key"`（公钥，非机密）保证扩展 ID 跨机器稳定
4. 按 §4.1 配对；如需撤销设备，在电脑端 `DELETE /api/remote/v1/devices/<id>`（本机专用）

> 该白名单同时被附件接口的跨源校验复用（`app/attachments/access.py`），因此**不要写通配符**。

### 4.3 客户端状态机与错误码映射

```
unpaired ──(配对码)──► pairing ──成功──► connected ──断线──► reconnecting(2s→30s 退避)
   ▲                        │失败 4401          │                    │
   └────────────────────────┴───────────────────┴─ 凭据失效 ─► unpaired（提示重新配对）
```

| 错误 | 场景 | UI |
|---|---|---|
| `4404` | 远控未启用 | 设置页给出"改 `.env` + 重启"指引 |
| `4403` | Origin 不在白名单 | 提示把扩展 ID 加入白名单 |
| `4401` | 握手超时 / 凭据无效/被撤销 | 回配对页，清本地 token |
| `4400` | 帧不合法 | 仅日志 + "版本不匹配"提示 |
| `4429` | 出站队列溢出（客户端太慢） | 自动重连 + 补历史（去重） |
| `session_busy` | 会话已在运行 | 自动降级 `session.steer{mode:"append"}` |
| `approval_not_pending` | 审批已被别处处理 | 卡片置灰 + "已在其他端处理" |
| `idempotency_key_required` | 客户端漏带幂等键 | 视为客户端 bug；所有写方法统一 `crypto.randomUUID()` |

---

## 5. 协议使用清单

### 5.1 现有方法（P0 起用）

| 场景 | 方法 | 参数 | scope | 幂等键 |
|---|---|---|---|---|
| 自检 | `system.health` | — | read | 否 |
| 历史面板列表 | `session.list` | `{include_archived?}` | read | 否 |
| 会话详情 | `session.get` | `{session_id}` | read | 否 |
| 补历史 | `session.history` | `{session_id, turns:20}` 或 `{limit, before_index}` | read | 否 |
| 订阅/退订（**支持多会话并存**） | `session.subscribe` / `session.unsubscribe` | `{session_id, after_seq}` | read | 否 |
| 新建会话 | `session.create` | `{name?}` | write | **是** |
| 发消息 | `session.send` | `{session_id, message, ui_message?, ui_language?, run_id?}`（本期扩展 attachments/selected_skills，见 5.2） | write | **是** |
| 运行中追加/打断 | `session.steer` | `{session_id, message, mode:"append"│"interrupt", client_id}` | write | **是** |
| 停止 | `session.interrupt` | `{session_id, run_id?, reason?}` | write | **是** |
| 审批列表 | `approval.list` | `{session_id?}` | approvals | 否 |
| 审批处理 | `approval.resolve` | `{session_id, approval_id, approve, rejection_reason?}` | approvals | **是** |

> 多订阅可行性依据：`gateway.py` 内按连接维护 `subscriptions: dict[str, Task]`，一个连接可订阅多个会话——这正是 D13"侧栏内未读"的基础。

### 5.2 本期新增方法（对应 D8 / D11 / D16，服务端改动见 §14）

> 命名沿用现有风格（`session.*` / `approval.*`）；下表为**实现时定稿**的建议签名。

| 方法 | 参数 | scope | 幂等 | 用途 | 服务端实现落点 |
|---|---|---|---|---|---|
| `session.update` | `{session_id, name?, archived?, pinned?, todo?}` | write | **是** | 历史面板：改名/归档/置顶/待办 | `service.py` + `session_manager.set_session_name`(:7262)/`set_session_archived`(:7158)/`set_session_pinned`(:7181)/`set_session_todo`(:7209) |
| `session.delete` | `{session_id}` | write | **是** | 删除会话（二次确认） | `session_manager.delete_session`(:6923) |
| `session.search` | `{terms:[...], session_id?, scope:"session"│"global", limit}` | read | 否 | 历史面板内容搜索 | 复用 `app/history_context.py` 的 `_search_session`(:401)/`_search_snippet`(:354)/`_iter_archive_paths` + 最近会话枚举（:330-352），需要抽出公开包装 |
| `model.list` | `{include_disabled?}` | read | 否 | 侧栏模型选择器数据 | `app/model_profiles.py`（主 UI 走 `GET /api/model_profiles`，`webui.py:3509`） |
| `session.model_profile` | `{session_id, profile_id}` | write | **是** | 切换会话模型 | 主 UI 走 `POST /sessions/{id}/model_profile`（`webui.py:3922`） |
| `skill.list` | `{}` | read | 否 | 技能选择器数据 | 主 UI 走 `GET /api/skills`（`webui.py:2504`） |
| `approval.analyze` | `{session_id, approval_id}` | approvals | 否 | 审批卡"AI 分析" | 复用主 UI 路由 `/sessions/{id}/approvals/{id}/analyze`（`webui.py:4226`）的实现（抽共享函数） |
| `session.send`（扩展） | 追加 `attachments?:[...]`、`selected_skills?:"a,b"` | write | **是** | 附件 + 技能随消息发送 | `service.py::_session_send` + 复用 `webui.py` 的 `selected_skill_names/build_agent_message`（:5258-5259）与附件解析（:5259-5304）→ `astream_events(..., user_content=structured)`（`agent_loop.py:9475` 已支持 `user_content`） |

**`session.search` 的语义与约束（已核对实现）**

- 匹配语义：**所有词都命中**（AND）、`casefold` 不区分大小写；先按原始 JSONL 行粗筛再解析，去重同内容；
- 覆盖范围：会话归档分片（archive JSONL）的 `kind == "message"` 行 + 会话 `events.jsonl`；
- 返回：`{ref, content(≤700 字摘要), session_id?}`，`ref` 可直接用于后续读取；
- **无索引**（按 I/O 线性扫描）：实现时必须 `asyncio.to_thread` + 结果上限 + 超时保护，默认只搜当前会话，全局搜索需显式切换。

### 5.3 事件映射（`session.event` 帧 `payload.type` → UI）

| payload.type | UI 呈现 |
|---|---|
| `user` | 用户消息气泡 |
| `status` / `warning` / `error` | 状态行（error 红色） |
| `llm_response_delta` / `llm_reasoning_delta` | 正文打字机 / 思考过程折叠区（全量对齐 D7） |
| `sse_keepalive` | 忽略 |
| `tool_call` | 工具行（可折叠，含命令与结果摘要、复制按钮） |
| `tool_approval_required` / `approval_requested` | 审批卡片（允许/拒绝 + AI 分析） |
| `context_trim_progress` / `context_summary_progress` / `key_context_progress` | 进度条 |
| `subagent_start` / `subagent_finish` | 子代理徽标行（只读展示） |
| `run_interrupted` | 中断提示 |
| `validate_final` / finish | 收起"停止"，恢复发送态 |

### 5.4 一致性与分页

- **先订阅后补历史**：`session.subscribe{after_seq:lastSeq}` → `session.history{turns:20}` → 渲染期间的实时事件进 buffer，渲染完 flush。
- **去重游标**：每会话 `lastSeq = max(lastSeq, event.event_bus_seq ?? event.seq)`。
- **向上翻页**：`session.history{before_index}`。
- **语言**：发送时带 `ui_language:"zh-CN"│"en"`（服务端 `normalize_prompt_language`）。
- **未读（D13）**：对**所有**"会话列表里可见的会话"保持订阅（上限建议 20 条按最近活动排序）；非当前会话收到事件时 `unread[sid]++` 并打点；进入该会话即清零；连接断开重连后按各会话 `lastSeq` 补拉。未读是**客户端本地状态**，不与服务端 `unread_result` 联动（见 §18 L3）。

---

## 6. 侧栏 UI 设计

### 6.1 信息架构

| 视图 | 入口 | 内容 |
|---|---|---|
| **对话**（默认） | 打开侧栏 | 消息流 + 上下文芯片 + composer（附件/发送/停止）+ 顶部条（状态点、会话名、历史、新建、设置） |
| **历史** | 顶部时钟按钮 | 搜索框 + 分组（今天/昨天/本周/更早）+ 会话项（标题、最后活动、未读徽标、待审批徽标）+ 操作菜单（打开/改名/归档/置顶/待办/删除） |
| **配对** | 未配对时 | 配对码、设备名、错误提示、"如何生成配对码"说明（折叠） |
| **设置** | 顶部齿轮 | 服务地址（高级可改）、上下文长度、语言（跟随浏览器/中/英）、主题（跟随系统/深/浅）、页面上下文总开关、清除本机凭据、连接诊断（版本、设备、scope） |

### 6.2 对话视图线框

```
┌────────────────────────────────────────┐
│ ● 已连接  角标修复会话     ⏱历史  ＋  ⚙ │
├────────────────────────────────────────┤
│                         用户消息（右） │
│ 助手消息（左，Markdown/表格/代码高亮） │
│ ▸ 工具：read_file agent_loop.py …      │
│ ▾ 思考过程（默认折叠）                 │
│ ┌ 需要确认：执行命令 ──────────────┐   │
│ │ rm -rf build/                    │   │
│ │   [AI 分析]  [拒绝]   [允许]      │   │
│ └──────────────────────────────────┘   │
│ ── 运行中…  [停止]                     │
├────────────────────────────────────────┤
│ 📄 当前页：设计文档 · 3.2k 字  ✕       │
│ ┌──────────────────────────────────┐   │
│ │ 输入消息…                   📎 ➤ │   │
│ └──────────────────────────────────┘   │
└────────────────────────────────────────┘
```

### 6.3 交互细节

- **上下文芯片（D19）**：来源三选一——「当前页正文」「当前页选中文本」「仅网址」；**默认不附加**，点 `📄` 或右键菜单才注入；芯片可预览、可移除、可切换来源（仅网址模式会提示"受受信/预批准域名限制，可能被拦"）。
- **附件（§8）**：`📎` → 截图当前可见区域 / 选择文件（含拖拽、剪贴板粘贴图片）；发送前显示缩略图与大小。
- **审批卡（D17）**：`[AI 分析]`（调 `approval.analyze`，结果就地展示，可折叠）｜`[允许]` / `[拒绝]`（拒绝理由选填，展开一个小输入框）；处理成功就地变结果行。
- **运行中**：`➤` 变 `[停止]`；输入框仍可用，回车即 `session.steer{mode:"append"}`。
- **快捷键与菜单（D14）**：`Ctrl+Shift+M` 打开/聚焦侧栏；右键菜单两项——「就选中内容提问」「把当前页发给 SugarAgent」。
- **未读（D13）**：历史面板会话项右侧数字徽标；当前会话不做徽标；打开即清零。
- **语言与主题（D15）**：`prefers-color-scheme` 跟随系统；文案 zh-CN/en 两套；列表/时间格式按语言本地化。
- **窄宽适配**：`min-width:300px`；工具行默认折叠；表格/长代码块横向滚动并给"复制"按钮；宽度 ≥460px 时历史面板改为两栏（列表 + 预览）。
- **空态**：无会话 → "新建会话"；未配对 → 配对引导；服务不可达 → 三步排障（服务是否启动 / 远控是否开启 / 白名单是否含本扩展 ID）。

---

## 7. 页面上下文提取（D3 / D19）

**授权模型**：不申请 `<all_urls>`。用户点图标（action）、右键菜单、快捷键时浏览器授予该标签页 `activeTab`，此刻注入才合法。

```
侧栏点「📄 当前页」→ SW: chrome.tabs.query(active,currentWindow) → tabId
    → chrome.scripting.executeScript({target:{tabId}, files:["content/extract.js"], args:[mode]})
    → 回传 {url,title,selection,text,charCount,truncated,siteName}
    → 侧栏渲染上下文芯片（可预览、可移除）
```

**算法**：① `mode=selection` 且选区非空 → 用选区；② 否则克隆 `body`，去 `script/style/noscript/svg/iframe/nav/header/footer/aside/form/[aria-hidden]`，按文本量选主容器（`article`/`main`/最大文本块）；③ 空白归一化、保留段落；④ 上限默认 **8000 字符**（设置 2000–20000），超出截断并标注；⑤ 附 `title/url/siteName`。

**消息拼装（固定格式）**

```
[网页上下文]
标题: <title>
网址: <url>
内容:
<正文>

<用户问题>
```

**隐私**：仅用户显式操作后读取；不写日志、不外传；设置页提供总开关。

---

## 8. 附件（D8 / D12 / D17 配套）

### 8.1 服务端现有契约（已核对 `app/webui.py:2543`、`app/attachments/access.py`）

- `POST /api/upload-chat-files`（multipart，字段 `files`，可多文件）：单文件 ≤100 MB、合计 ≤200 MB；
  - 图片（`image/*` 或 `.png/.jpg/.jpeg/.webp/.gif/.bmp`）→ 附件仓库对象，返回 `attachment` ref + `url=/api/attachments/<id>`；
  - 非图片 → 落 `<WORK_DIR>/uploads/chat/YYYYMMDD/`，返回 `path`（绝对）与 `rel`（工作区相对）。
- 鉴权顺序：**loopback 直连 → `local`(admin) 主体**；带 Origin 且与 Host 不同时必须在 `allowed_origins` 白名单内。
- 结构化内容形状（`/chat` 解析后交给 `astream_events(user_content=...)`）：`{"type":"image","attachment":ref}` 或 `{"type":"local_file","local_file":{path,name}}`。

### 8.2 本期设计（口径 A）

1. 侧栏/SW 直连 loopback 上传 → 得到附件项；
2. 放入 `session.send` 的 `attachments`：
   ```json
   {"method":"session.send","params":{
     "session_id":"…","message":"…",
     "attachments":[
       {"type":"image","attachment":{"attachmentId":"…"}},
       {"type":"local_file","local_file":{"path":"D:\\…\\uploads\\chat\\20260930\\spec.pdf","name":"spec.pdf"}}
     ]}}
   ```
3. 服务端 `_session_send` 按 §5.2 解析（复用 `/chat` 的解析逻辑）→ `astream_events(user_content=structured)`；
4. **口径 A 的具体含义**：上传来自 loopback（`local`/admin），发送校验按"本机来源"处理——实现时在 `service.py` 内显式注释该前提，避免后人误读为"设备可借本机附件"。若将来要多设备隔离，再切 B（见 §18 L2）。

### 8.3 截图规格与限制

- 截图：`chrome.tabs.captureVisibleTab` 可见区域 PNG，最长边 ≤1600px（超限压缩为 JPEG q=0.85）；
- 单条消息附件数：沿用服务端 `max_images_per_message` 限制，超限在 UI 前置提示；
- 上传失败/超限：复用服务端文案（413/400），UI 顶部提示条 + 保留草稿。

---

## 9. 会话管理（D5 / D16）

**历史面板（Page Assist 式）**：顶部搜索框（默认搜标题 + **可选择搜内容**）、时间分组（今天/昨天/本周/更早）、归档区折叠、每项右侧未读徽标与待审批徽标、长按/悬浮出操作菜单。

**操作与协议映射**

| 操作 | 协议 | 说明 |
|---|---|---|
| 新建 | `session.create` | 新建后进入该会话 |
| 改名 / 归档 / 置顶 / 待办 | `session.update` | 归档项在"归档"区展示（`session.list{include_archived:true}`） |
| 删除 | `session.delete` | **二次确认**（输入数量/标题确认二选一），不可恢复 |
| 标题搜索 | 客户端本地过滤 | 无服务端依赖 |
| 内容搜索 | `session.search` | 复用 `history_context` 实现（AND 语义、无索引、限额+超时）；默认搜当前会话，切换"全部会话"再走 `scope:"global"` |

**约束**：客户端**不得**调用 loopback 内部路由（如 `PUT /sessions/{id}/name`、`DELETE /sessions/{id}`）——这些是主 UI 的实现细节，随版本变动。

---

## 10. 渲染对齐（D7 / D10）

**对齐清单**（侧栏实现，与主 UI 视觉/行为保持一致）

| 元素 | 做法 |
|---|---|
| Markdown（标题、列表、引用、表格、链接） | 打包 `marked`（与主 UI 同版本），自定义渲染器约束内联 HTML |
| 代码块 | 基础高亮（轻量自研 tokenizer 或打包 highlight.js 子集）+ 复制按钮 + 语言标签 |
| 数学/Mermaid | 打包 Mermaid vendor（来源：`app/templates/dist/assets/vendor/mermaid.min.js`，构建时从主 UI 产物同步），按需渲染，默认折叠"查看图表" |
| 工作区图片 | `<img src="http://127.0.0.1:8192/api/workspace-image?rel=…">`（扩展页 `img-src` 不受默认 CSP 限制；需 host_permissions） |
| 思考过程 | 折叠区，默认收起，可展开/复制 |
| 工具行 | 折叠卡片：工具名 + 关键参数 + 结果摘要；失败红色；复制原始输出 |
| 进度类事件 | 细条进度 + 文案（上下文压缩/摘要/键上下文） |
| 子代理 | 徽标行（"子代理 · 运行中/完成"），**只读**，不做目录面板（§18 L1） |
| 主题令牌 | 从主 UI CSS 提取副本到扩展 `styles/tokens.css`，附一个"差异巡检"脚本说明（比对主 UI 令牌与扩展副本） |

**硬约束**：MV3 默认 CSP 禁止远程脚本 → 所有第三方 JS **必须打包进扩展**，不能像主 UI 那样从 `127.0.0.1:8192/assets` 动态加载；样式同理建议打包（避免远程样式被策略或离线场景影响）。

---

## 11. 未读与多订阅（D13）

- 连接建立后：`session.list` 取最近会话（默认 20 条）→ 逐条 `session.subscribe{after_seq:lastSeq}`（历史游标从本地缓存读取）。
- 事件到达：当前会话直接渲染；其它会话 `unread[sid]++`，历史面板对应项显示数字徽标。
- 进入会话：`unread[sid]=0`，必要时 `session.history` 补拉缺失区间。
- 订阅回收：超出窗口（>20 条）或长期无活动的会话退订，避免连接负载；退订阈值可在设置中调。
- 不做浏览器级通知（无 SW 连接、无 `chrome.notifications`、无工具栏角标）——与 D13 一致。

---

## 12. 桌面端联动（presence）

- 服务端语义：`POST /api/ui-presence {action, token, active, session_id}`；只要有 UI 在线，就不发"页面已关闭但仍在运行"的桌面通知；TTL 默认 300s（下限 90s）。
- 侧栏做法（对齐主 UI）：面板加载 `register`；每 10s `update`（带当前 `session_id`）；`pagehide` 用 `sendBeacon` `unregister`；面板不可见时 `active:false`。
- 依据：`app/webui.py:237-242, 4690-4712, 5012-5050`；`frontend/src/app/modules/message-rendering.js:1735-1783`。

---

## 13. 权限与安全

| 权限 | 用途 |
|---|---|
| `sidePanel` | 侧栏 |
| `storage` | `device_token` 与设置 |
| `activeTab` | 按需读当前页（不申请 `<all_urls>`） |
| `scripting` | 注入提取脚本 |
| `contextMenus` | 两项右键菜单 |
| `commands` | `Ctrl+Shift+M` |
| `host_permissions` | `http://127.0.0.1:8192/*`、`http://localhost:8192/*`（不含公网域） |

约束：① `device_token` 只存 `local`，不进 `sync`、不写日志；② 配对只用 `read/write/approvals`，**不要 `admin`**；③ 白名单只列本扩展 ID（同时被附件接口复用），**不写通配符**；④ **不新增服务端 CORS 中间件**；⑤ 服务端保持只监听 `127.0.0.1`；⑥ 页面内容仅用户显式操作后读取；⑦ 撤销设备必须在电脑端执行，侧栏只清本地凭据。

---

## 14. 服务端改动清单（本期必做，按依赖排序）

| # | 改动 | 位置 | 规模 | 测试 |
|---|---|---|---|---|
| S1 | 启用远控 + 白名单（配置） | `app/.env`，手工两行（备选：将来若改做插件向导页，可经 `POST /api/env` 自动写入，见 §18 备选方案） | 2 行 | 手工负向：移除白名单应 4403 |
| S2 | `session.update`（改名/归档/置顶/待办） | `service.py`：`METHOD_SCOPES`、`IDEMPOTENT_METHODS`、handlers → `session_manager.set_session_*` | ~30 行 | pytest：scope 校验、幂等重放、参数校验 |
| S3 | `session.delete` | 同上 → `session_manager.delete_session`(:6923) | ~15 行 | pytest：二次确认由客户端保证；服务端幂等 |
| S4 | `session.send` 支持 `attachments` + `selected_skills` | `service.py::_session_send`；复用 `webui.py:5258-5304` 的 `selected_skill_names/build_agent_message` 与附件解析 → `astream_events(user_content=…)`（`agent_loop.py:9475`） | ~40 行（含抽出共享函数） | pytest：本地文件/图片两种形状、超限与非法 ref |
| S5 | `model.list` + `session.model_profile` | `service.py` → `app/model_profiles.py`；对齐 `webui.py:3509/3922` | ~30 行 | pytest：切换后 `session.get` 反映新档案 |
| S6 | `skill.list` | `service.py` → 对齐 `webui.py:2504` 的技能枚举 | ~20 行 | pytest：列表结构 |
| S7 | `approval.analyze` | `service.py` → 抽出 `webui.py:4226` 的实现为共享函数 | ~25 行 | pytest：无待审批时报错、正常返回 |
| S8 | `session.search` | `service.py` → `history_context.py` 公开包装（`_search_session`:401 等） | ~35 行（含限额/超时） | pytest：AND 语义、去重、限额、跨会话 scope |
| S9 | 文档与协议说明 | `docs/remote_control.md` 增"浏览器扩展客户端接入"+"新增方法/参数"两节 | 文档 | — |

> 实现顺序建议：S1 → S2/S3 → S4 → S5/S6/S7 → S8；S2–S8 均为**新增方法/参数**，不改既有行为（回归风险低）。

---

## 15. 目录结构与模块接口

```
browser-extension/
  manifest.json            # MV3（含 key 固定 ID）
  background.js            # sidePanel 行为、菜单、快捷键、注入、截图
  sidepanel.html / sidepanel.js
  styles/tokens.css        # 主题令牌（主 UI 副本）
  styles/panel.css
  vendor/marked.js         # 打包的第三方（与主 UI 同版本）
  vendor/mermaid.min.js    # 从 app/templates/dist/assets/vendor 同步
  content/extract.js
  lib/rc-client.js         # 协议客户端（唯一与后端耦合处）
  lib/render.js            # 事件 → DOM（Markdown/工具行/审批卡/进度）
  lib/unread.js            # 多订阅与未读计数
  lib/i18n.js              # zh-CN / en
  README.md                # 启用两步、配对、白名单、排障、令牌同步说明
```

**manifest 骨架**

```json
{
  "manifest_version": 3,
  "name": "SugarAgent Sidebar",
  "version": "0.1.0",
  "minimum_chrome_version": "116",
  "key": "<固定扩展 ID 的公钥，非机密>",
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

**`lib/rc-client.js` API**

```js
createRcClient({baseUrl, onEvent, onStateChange, storage})
  .connect({pairingCode?, deviceName?, deviceToken?})   // → {device:{device_id,name,scopes}, deviceToken?}
  .rpc(method, params, {idempotencyKey}?)               // → result（内部超时 20s）
  .subscribe(sessionId, {afterSeq}) / .unsubscribe(sessionId)
  .searchInSession(sessionId, terms, {limit})           // 包装 session.search
  .close()
```

**IPC（panel ↔ SW）**

| type | 载荷 | 说明 |
|---|---|---|
| `extract-page` | `{mode:"auto"│"selection"}` | → `{url,title,selection,text,charCount,truncated,siteName}` |
| `capture-visible` | `{}` | → `dataUrl`（截图） |
| `panel-opened` | `{tabId}` | SW 记录侧栏来源标签页 |

**`chrome.storage.local`**

```json
{
  "rc.baseUrl": "http://127.0.0.1:8192",
  "rc.deviceToken": "<secret>",
  "rc.device": {"device_id":"…","name":"Chrome 侧栏 · PC","scopes":["read","write","approvals"]},
  "prefs.language": "auto",
  "prefs.theme": "system",
  "prefs.contextChars": 8000,
  "prefs.pageContextEnabled": true,
  "prefs.unreadWindow": 20,
  "ui.lastSessionId": "…",
  "cache.lastSeq": {"<session_id>": 123}
}
```

---

## 16. 分阶段计划与验收

| 阶段 | 交付 | 验收（DoD） |
|---|---|---|
| **P0 骨架** | manifest + 侧栏骨架 + `rc-client`（握手/重连/RPC/去重）+ 配对页 + 会话读取 + 发送/停止 | 侧栏完成一轮对话；主 WebUI 同开会话两端一致；杀进程后自动重连并补历史 |
| **P1 上下文 + 渲染对齐** | `extract.js`、上下文芯片（三种来源）、右键菜单、快捷键、Markdown/代码/表格/Mermaid/图片/思考折叠/工具行/进度条 | 文章页一次点击即带上下文；渲染与主 UI 目视一致；未点击不注入 |
| **P2 服务端扩展 + 历史面板** | S2–S7 上线；历史面板（搜索标题、改名/归档/置顶/待办/删除、新建）；审批卡（允许/拒绝 + AI 分析）；技能与模型选择器 | 面板内可完成会话治理；审批在侧栏闭环；技能/模型切换后 `session.get` 正确 |
| **P3 附件 + 搜索 + 未读** | S4 附件（截图/图片/文档）、S8 `session.search` 接入面板、多订阅未读徽标、presence 注册 | 截图与 PDF 随消息送达并被 Agent 正确读取；内容搜索命中归档与事件；其它会话未读可计数清零 |
| **P4 打磨（可选）** | 令牌差异巡检脚本、i18n 补全、性能（长会话虚拟滚动）、`.crx` 打包说明 | 长会话（>2000 条）滚动不卡；双语无缺字 |

---

## 17. 测试计划

**手工（必须）**

1. 配对：错码/过期码/正确码；撤销设备后重连失败并回配对页。
2. 对话：流式长回答、停止、运行中追加（`steer append`）。
3. 审批：允许 / 拒绝（有理由/无理由）/ AI 分析；两端同时操作时后点者收到 `approval_not_pending`。
4. 上下文：文章页 / SPA / 选中文本 / 超长页（截断）/ 仅网址（受信域名命中与被拦两种）。
5. 历史面板：改名、归档、置顶、待办、删除（二次确认）、标题搜索、内容搜索（含跨会话）。
6. 附件：截图、PNG、PDF；>100 MB 报错；多图超限提示。
7. 未读：A 会话运行中切到 B 会话浏览，回 A 后徽标清零；重连后计数不重复。
8. 桌面联动：侧栏开/关时托盘通知行为（`app/desktop_notify.py`）。

**负向（必须）**

- 移除白名单 → `4403`；漏 `idempotency_key` → 服务端拒绝；`session.update` 用只读设备 token → `forbidden`。
- 客户端误调 loopback 内部路由 → 断言不发生（代码评审 + 抓包核对）。

**自动化**

- `rc-client` 纯逻辑（帧解析、去重、退避、未读计数）：Node 单测，无浏览器依赖。
- 服务端新增方法：pytest（沿用 `tests/` 现有远控测试风格），覆盖 scope、幂等重放、参数校验、搜索结果结构。

---

## 18. 默认假设与遗留项

**L1 面板级对齐范围（默认假设）**：D7 的"全量对齐"指**消息流渲染**；主 UI 的**独立面板**（详情栏文件树、Goal 面板、待办计划面板、子代理目录面板）**本期不做**——它们需要 HTTP 内部路由或额外协议方法。若确认要做，优先补 `session.todo_plan` 与 `subagent.list` 两个只读方法。

**L2 附件口径切换（默认假设）**：按 D12 的 A 口径实现并在代码注释写明前提；未来需要多设备隔离时再切 B（上传时以 `Bearer device_token` 把 ref 授权给设备）。

**L3 未读与服务端 unread_result 的关系（默认假设）**：侧栏未读为**客户端本地**状态；不与服务端 `unread_result`/主 UI 徽标联动，避免两端互相清零造成困惑。

**L4 上下文长度**：默认 8000 字符（可调 2000–20000），上线后按实际 token 消耗复核。

**L5 会话搜索默认范围**：默认仅当前会话；"全部会话"为显式切换，且限制结果条数与总耗时（超出即截断并提示）。

**待实测（实现第一步验证，不阻塞设计）**

1. 扩展页发起 WS 是否携带 `Origin: chrome-extension://<id>` → 决定白名单是否必须（无论结论都建议保留）。
2. 扩展页/SW 连 `ws://127.0.0.1:8192` 是否被 CSP 或 host 权限拦截（预期不拦）。
3. 扩展页拉取 `/api/workspace-image` 等只读资源是否受 Origin 校验影响（预期不受；附件上传/读取类接口才校验）。

**已评估并否决的备选方案：以 SugarAgent 插件形式交付（D20）**

- **备选内容**：把整个项目做成内置插件 `plugins/browser-sidebar/`——`capabilities.web` 提供"安装与配对向导"页（并可用 `capabilities.ui.navigation` 在主 UI 加导航入口），向导页调用本机接口完成启用与配对；MV3 扩展放进该插件的 `extension/` 子目录，用户"加载已解压的扩展程序"直接指向它。
- **当时确认可行的证据**：`plugins/execution-dashboard/.myagent-plugin/plugin.json` 已是"纯 Web 页面 + 导航入口"形态；插件页由 `app/webui.py:8280` 提供且与主 UI 同源（CSP `connect-src 'self'`）；`POST /api/env` 接受任意合法键名并写入 dotenv（`app/webui.py:8000-8036`），因此向导页能自动写 `MYAGENT_REMOTE_CONTROL_ENABLED` 与 `MYAGENT_REMOTE_CONTROL_ALLOWED_ORIGINS`；`POST /api/remote/v1/pairings` 只要求 loopback 直连（`app/remote_control/gateway.py:136+`），向导页可直接生成配对码；D18 的固定扩展 ID 让白名单可预填。
- **否决理由（用户决定）**：扩展保持独立演进与独立版本节奏，不把它绑到应用内置插件的生命周期上；代价是启用流程保留手工两步（D18）。
- **同时澄清（避免后人误判能力）**：插件 **worker** 不具备写 `.env`、发起 HTTP、创建配对码的能力——其服务面仅 `sessions.run_many`、`session_state.{get,compare_and_set,set_latest,patch}`、`session_events.append`（`app/plugin_host_services.py:298/445-476`）；"插件化"只能由插件**网页**完成，且写入配置后**必须重启**（远控配置在模块导入时读取，`app/webui.py:8191`）。
- **将来若反悔**：按上述证据链重做即可，改动集中在"新增一个纯 Web 插件包"，不触碰扩展本体与 §14 的 S2–S8。

---

## 19. 参考依据

- 协议与远控：`app/remote_control/gateway.py:48-59,99-106,136+,239-345`、`service.py`（`METHOD_SCOPES`/`IDEMPOTENT_METHODS`/`_session_send`/`_session_steer`/`_approval_*`）、`store.py:16-17`、`config.py`、`docs/remote_control.md`、`app/templates/remote_control.html`。
- 服务端接口：`app/webui.py:1862`（`/`）、`:237-242,4690-4712,5012-5050`（presence）、`:2504`（skills）、`:2543`（上传）、`:3509/3922`（模型档案）、`:4226`（审批分析）、`:5120`（`/chat`）、`:5258-5304,5340`（技能与附件 → `user_content`）、`:6631/6712/6719/6726/3981`（会话改名/归档/置顶/待办/删除）。
- 会话与检索：`app/agent_harness.py:6923/7158/7181/7209/7262`、`app/history_context.py:330-352,354,401`（`_search_session` 等）、`app/agent_loop.py:9475`（`astream_events` 含 `user_content`）。
- 附件：`app/attachments/access.py`（loopback→admin、Origin 白名单、`require_attachment`）。
- 前端参考：`frontend/src/app/modules/message-rendering.js:1735-1783`（presence）、`frontend/vite.config.js`、`app/templates/dist/assets/vendor/mermaid.min.js`（Mermaid 打包来源）。
- 外部：Chrome `sidePanel` API（`setPanelBehavior`/`setOptions`/`open`、`action` 必需、`side_panel.default_path`）、MV3 跨源访问（`host_permissions` 下扩展页/SW 的 fetch 不受 CORS 约束；content script 仍受限）、MV3 CSP（禁止远程脚本）、Page Assist 的 sidebar + chat history + Chat With Webpage 形态。
- 插件体系（本次评估、结论为不采用，见 §18 备选方案与 D20）：`docs/plugin_api_v1.md`、`plugins/execution-dashboard/.myagent-plugin/plugin.json`（`capabilities.web` + `ui.navigation` 形态）、`app/plugin_host_services.py:298/445-476`（worker 服务面）、`app/webui.py:8000-8036`（`/api/env` 可写配置）、`app/webui.py:8280`（插件页路由）、`app/plugin_web_gateway.py`（插件页与资源服务）。
