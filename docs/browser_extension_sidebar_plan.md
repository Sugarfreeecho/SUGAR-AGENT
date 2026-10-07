# 浏览器侧栏插件（Page Assist 形态）实现方案

> 结论先行：本仓库**不需要新增一套聊天后端**。Agent 本体已经是"本机 FastAPI 服务 + 薄客户端 + 事件流"结构，
> 且已经存在一个**专为外部客户端设计**的正式通道（Remote Control v1：WebSocket + 设备配对 + 权限分级 + 审计）。
> 侧栏插件应作为 Remote Control 的**原生客户端**接入，而不是复用（或新造）WebUI 内部接口。
> 落地代价：扩展侧纯新增（`browser-extension/`），服务端只需 2 个环境变量 + 固定扩展 ID。

---

## 1. 现状分析（关键事实与依据）

| # | 事实 | 依据（文件:行/函数） |
|---|---|---|
| 1 | 服务端是 FastAPI + uvicorn，只监听 `127.0.0.1:8192`，启动后自动打开系统浏览器指向 `http://127.0.0.1:8192/` | `app/main.py`（`_listen_host`/`_listen_port`/`uvicorn.run`） |
| 2 | 主界面 `GET /` 返回内嵌 HTML（`get_index_html()`），**未设置** `X-Frame-Options` / CSP `frame-ancestors` → 允许被扩展页 iframe 嵌入 | `app/webui.py:1862 get_index` |
| 3 | 前端是 Vite 项目，构建产物输出到 `app/templates/dist`；dev 模式把 `/sessions`、`/api` 代理到 8192 | `frontend/vite.config.js` |
| 4 | 前端不是组件框架：`src/app/index.js` 把所有模块以 `?raw` 字符串拼成一个脚本，用 `Function(...)()` 在全局作用域执行，DOM 依赖 `shell-body.html` 的三栏结构，接口全部是**相对路径** `fetch('/sessions/...')` | `frontend/src/app/index.js`、`frontend/src/app/modules/*` |
| 5 | 聊天主接口 `POST /chat`：multipart 表单 + SSE 流（`stream_protocol=runtime_v2`），需要单会话 start-token 预约，忙时返回 409 `busy` | `app/webui.py:5120 chat` |
| 6 | 另有两路 SSE：`GET /sessions/{id}/stream`（UI 投影 + `after_index` 游标）与 `GET /runtime-v2/sessions/{id}/stream` | `app/webui.py:5444`、`app/webui.py:2916` |
| 7 | 服务端**没有 CORS 中间件**（全仓 `CORSMiddleware/allow_origins` 无命中）→ 任何非 `127.0.0.1:8192` 源的 HTTP 客户端都过不了浏览器同源策略 | `app/` 全目录检索 |
| 8 | 存在正式的远控通道 **Remote Control v1**：默认关闭（`MYAGENT_REMOTE_CONTROL_ENABLED=0`），WS 路径 `/api/remote/v1/ws`，握手 `connect.challenge` → `connect{nonce, device_token\|pairing_code}` | `app/remote_control/gateway.py:99-106,279-345`、`app/.env.example:176` |
| 9 | 远控方法集与权限分级（scope）：读 `session.list/get/history/system.health`；写 `session.create/send/steer/interrupt`；审批 `approval.list/resolve`；管理 `device.*/audit.list`；写方法**强制** `idempotency_key` | `app/remote_control/service.py`（`METHOD_SCOPES`/`IDEMPOTENT_METHODS`） |
| 10 | 设备默认 scope 为 `read/write/approvals`（不含 `admin`），配对码本机创建、一次性、默认 10 分钟过期 | `app/remote_control/store.py:16-17`、`app/remote_control/gateway.py:136+` |
| 11 | WS 有 Origin 校验：无 `Origin` 头按原生客户端处理（仍校验凭据），浏览器源必须同 Host 或列在 `MYAGENT_REMOTE_CONTROL_ALLOWED_ORIGINS` | `app/remote_control/gateway.py:48-59`、`app/remote_control/config.py` |
| 12 | 已有**可工作的参考客户端**：手机版网页客户端（会话列表 / 历史补拉 / `event_bus_seq` 去重 / 审批卡片 / 忙时转 `session.steer` / 断线重连） | `app/templates/remote_control.html`（配对弹层、`selectSession`、`handleEvent`、`renderApproval`、`send`） |
| 13 | 协议语义：`session.subscribe{session_id, after_seq}` 收事件，`session.history{session_id, turns}` 补历史，事件用 `event_bus_seq` 去重；`session.send` 返回 `session_busy` 时应降级为 `session.steer{mode:"append"}` | `docs/remote_control.md`、`app/templates/remote_control.html:144-197` |
| 14 | 已有 UI 在线状态登记机制（最后一个 UI 关闭后才发"后台仍在运行"通知） | `app/webui.py:5012 /api/ui-presence` |

**由此得出的判断：**

- 侧栏插件需要的全部能力（列会话、拉历史、订阅实时事件、发消息、停止、审批）**已经被 Remote Control v1 覆盖**，且该通道的定位就是"给远程/外部客户端用"（手机、飞书适配器共用同一个 `SessionControlService`），会话数据与主 UI 完全同源。
- 反过来，直接复用 WebUI 的 `/chat` + `/sessions/*`（无鉴权、无 CORS、非对外契约）会把新客户端绑死在内部实现上，并需要额外绕过 CORS，不推荐作为主通道。

---

## 2. 目标形态（对齐 Page Assist 的 sidebar 范式）

1. 任意网页右侧栏常驻对话（Chrome/Edge `sidePanel`，工具栏图标一键开合）。
2. **页面上下文问答**（Chat with Webpage）：按需提取当前页正文/选区，作为消息上下文发给 Agent。
3. 复用 Agent 的会话与历史，与主 WebUI **并行可用**（同一会话两端订阅不冲突）。
4. 流式输出、停止、工具审批卡片（与手机端同款交互）。
5. 快捷键 / 右键菜单（"就选中内容提问"）作为增强项。
6. 可选：多标签上下文、图片/截图附件、远程（Tailscale）模式。

---

## 3. 三条实现路线

| 路线 | 做法 | 优点 | 代价/风险 | 结论 |
|---|---|---|---|---|
| **A. iframe 壳** | 侧栏页里 `<iframe src="http://127.0.0.1:8192/">` | 0 协议编码，半天可跑通；`/` 未设 `frame-ancestors`，可嵌入；`127.0.0.1` 属可信源，扩展页加载 http iframe 不触发混合内容拦截 | 侧栏宽约 320–480px，主 UI 是三栏 dock 布局，窄宽下折叠严重、体验差；拿不到页面上下文；无法做快捷键/右键等浏览器侧增强 | 仅作"最小可见效果"验证，不作交付形态 |
| **B. 原生侧栏 + Remote Control WS**（推荐） | MV3 扩展自带侧栏 UI，`WebSocket → /api/remote/v1/ws`，content script 提页面正文 | 走正式鉴权通道；与手机端同一协议；历史/事件/审批/停止全部现成；天然支持断线重连与幂等；未来接 Tailscale 地址即可远程复用；WebSocket **不受 CORS 限制** | 需要：启用远控 + 扩展 ID 白名单 + 一次性配对；侧栏 UI 需自写（可直接移植 `remote_control.html` 的逻辑与视觉语言） | ✅ 主推 |
| **C. 原生侧栏 + WebUI 内部 HTTP/SSE** | 直接 `fetch('http://127.0.0.1:8192/chat')`、`EventSource('/sessions/{id}/stream')` | 事件形状与主 UI 完全一致 | 服务端无 CORS → 必须让扩展 SW 中转或改服务端；接口无鉴权、非对外契约；等同把内部实现当 API | ❌ 不建议 |

---

## 4. 推荐架构（路线 B）

```
┌────────────────────────── 浏览器扩展（MV3） ──────────────────────────┐
│  sidepanel.html / sidepanel.js（聊天流、会话列表、审批卡片、配对弹层）│
│      │ chrome.runtime Port                     │ WebSocket             │
│      ▼                                         ▼                       │
│  content/extract.js                     ws://127.0.0.1:8192            │
│  （activeTab 注入，提取正文/选区）        /api/remote/v1/ws               │
│  background.js（setPanelBehavior / 右键菜单 / 快捷键 / 注入）           │
└────────────────────────────────────────────────────────────────────────┘
                                   │ Remote Control v1（device_token，scope=read/write/approvals）
                                   ▼
                    SessionControlService → 同一 Agent Runtime / 同一会话数据
                    （与主 WebUI、手机端、飞书适配器共享）
```

关键工程约定：

1. **WS 连接由侧栏页持有**（普通扩展页，无 Service Worker 空闲回收问题）；SW 只负责 `sidePanel.setPanelBehavior({openPanelOnActionClick:true})`、菜单/快捷键、脚本注入。若将来要"面板关着也收通知"，再引入 SW 持有连接（需 Chrome 116+，并自行处理保活与重连）。
2. **第一帧交互必须是 `connect`**：先收 `connect.challenge`，15 秒内回 `connect{nonce, pairing_code|device_token}`；配对成功后把返回的 `device_token` 存 `chrome.storage.local`（**不要**依赖 Cookie 路径：远控 Cookie 是 `HttpOnly + SameSite=Strict + path=/api/remote/v1`，扩展源属跨站，取不到也发不出）。
3. **写操作一律带 `idempotency_key`**（协议强制，`session.send/steer/interrupt/approval.resolve` 缺了会被拒）。
4. **先订阅、后补历史**：`session.subscribe{after_seq}` 建立实时管道，再 `session.history{turns:20}` 拉历史，用 `event_bus_seq` 去重（照抄参考客户端顺序，避免历史加载期间漏事件）。
5. **权限最小化**：配对时只用默认 scope（`read/write/approvals`），不要 `admin`。
6. **页面正文按需提取**：用 `activeTab`（用户点图标/菜单时才授权）+ `chrome.scripting.executeScript`，不做常驻全站注入；要"自动跟随页面"才需要 `<all_urls>`，属可选升级。

---

## 5. 服务端最小改动清单

| # | 改动 | 是否必须 | 说明 |
|---|---|---|---|
| 1 | `app/.env` 增 `MYAGENT_REMOTE_CONTROL_ENABLED=1`（改后重启） | ✅ | 否则远控路由不注册，WS 直接 `4404` |
| 2 | `app/.env` 增 `MYAGENT_REMOTE_CONTROL_ALLOWED_ORIGINS=chrome-extension://<扩展ID>` | ⚠️ 视实测 | 扩展页发起 WS 时 Chrome 通常带 `Origin: chrome-extension://<id>`，会被 `_origin_allowed` 拒绝（4403）；白名单加上即可。若由 SW 发起且不带 Origin，服务端按原生客户端处理，仍要凭据 |
| 3 | `manifest.json` 加 `"key"` 字段固定扩展 ID | ✅（工程建议） | 未打包扩展的 ID 由加载路径派生，不加 `key` 会导致白名单条目每次换机器/换目录就失效 |
| 4 | 可选：`/api/ui-presence` 注册 | 可选 | 让侧栏参与"最后一个 UI 关闭"的通知语义，避免与主 UI 状态互相打架 |
| 5 | 可选：扩展侧"本机一键配对"（SW 里 `POST /api/remote/v1/pairings` 再 claim） | 可选，默认关 | 会削弱"必须在本机确认一次"的语义，建议保持手工输码；如启用需在扩展设置里显式勾选 |
| 6 | 可选：图片/文档附件 | 可选 | REST 上传（`/api/upload-chat-files`）需由扩展 SW 中转（`host_permissions` 下 SW 的 fetch 不受 CORS 约束）；更干净的做法是后续在远控协议里加 attachment 字段 |

> 也就是说：**P0 阶段服务端只需 2 行配置**，不需要写新的 Python 代码。

---

## 6. 建议目录结构（新增）

```
browser-extension/                 # 无构建链，原生 ESM，可直接"加载已解压的扩展程序"
  manifest.json                    # MV3：sidePanel / scripting / storage / contextMenus + key
  sidepanel.html | sidepanel.js | styles.css
  background.js                    # setPanelBehavior、右键菜单、快捷键、activeTab 注入
  content/extract.js               # 正文/选区提取（readability 简化版）
  lib/rc-client.js                 # 协议客户端：握手、重连、RPC、事件去重、idempotency
  README.md                        # 安装、固定 ID、配对、白名单配置步骤
docs/browser_extension_sidebar_plan.md   # 本文件
```

manifest 骨架（要点）：

```json
{
  "manifest_version": 3,
  "name": "SugarAgent Sidebar",
  "key": "<固定扩展 ID 用的公钥>",
  "permissions": ["sidePanel", "scripting", "storage", "contextMenus", "activeTab"],
  "host_permissions": ["http://127.0.0.1:8192/*", "http://localhost:8192/*"],
  "action": { "default_title": "打开 SugarAgent 侧栏" },
  "side_panel": { "default_path": "sidepanel.html" },
  "background": { "service_worker": "background.js" },
  "minimum_chrome_version": "116"
}
```

侧栏与页面上下文的两种挂载方式（按需选一，不要同时开）：

- 全局侧栏：`side_panel.default_path` + `chrome.sidePanel.setPanelBehavior({openPanelOnActionClick:true})`。
- 每标签页实例：去掉 `default_path`，在 `chrome.action.onClicked` / 菜单回调里对当前 `tabId` 先 `setOptions({tabId, path, enabled:true})` 再 `open({tabId})`（后者必须在用户手势内调用）。

---

## 7. 分阶段计划

| 阶段 | 交付 | 验收 |
|---|---|---|
| **P0 骨架** | `rc-client.js`（握手/重连/RPC/去重）+ 侧栏最简 UI（配对、会话列表、历史、发消息、停止） | 侧栏里能完成一整轮对话，主 WebUI 同步看到同一会话内容 |
| **P1 页面上下文** | content script 提取正文/选区 + "把当前页作为上下文" + 右键菜单 + 快捷键 | 对任意文章页提问，回答引用了页面内容；不点按钮不注入 |
| **P2 生产化** | 审批卡片、断线补拉、presence 注册、多标签、主题跟随、错误提示、i18n | 杀进程/重启 Agent 后自动恢复；审批可在侧栏完成；与主 UI 并存无重复事件 |
| **P3 增强** | 图片/截图附件、会话搜索、Tailscale 远程地址复用、`.crx` 打包分发 | 远程模式下同一扩展可用 |

---

## 8. 风险与边界

- **CORS**：服务端没有 CORS 中间件是"有意为之"的隐式保护（本机其他网页拿不到 Agent 接口）。方案不改这一点：主通道用 WebSocket（不受 CORS 约束），HTTP 仅在确有需要时由扩展 SW 中转，不新增服务端全量 `Access-Control-Allow-Origin`。
- **本机信任边界**：扩展 SW 拥有 `host_permissions` 后可以绕过 CORS 直连 `127.0.0.1:8192` 的**未鉴权** WebUI 路由，这是本机任意进程/扩展都能做到的事实。本方案不改动这些路由，但新客户端**不**使用它们，避免把内部实现升格为对外契约。
- **窄宽度**：主 UI 的三栏 dock 布局与 320–480px 侧栏不兼容，侧栏 UI 必须独立实现（可移植 `app/templates/remote_control.html` 的样式语言与交互逻辑，它本身就是"窄屏客户端"）。
- **MV3 生命周期**：WS 放侧栏页最稳；放 SW 需 Chrome 116+ 并处理保活（活动期间 SW 才不被回收）与重连风暴。
- **浏览器差异**：Edge 用 `edge-extension://<id>`（白名单/Origin 同理）；Firefox 是 `sidebar_action` + MV2/3 差异，不在本次范围。
- **待实测确认的两个细节**（实现第一步就用最小 demo 验证，别先写 UI）：
  1. 扩展页 WS 握手是否带 `Origin`（决定是否必须加白名单条目）；
  2. 从扩展页/SW 连 `ws://127.0.0.1:8192` 是否被 `host_permissions` 或页面 CSP `connect-src` 拦截（MV3 默认 CSP 不限制 `connect-src`，预期不拦）。

---

## 9. 验证方法（可执行）

1. **协议自检**：加载未打包扩展 → 打开侧栏 → 输入配对码 → `system.health` / `session.list` 有返回。
2. **端到端**：发一条消息，观察 `session.event` 流式事件；点"停止"触发 `session.interrupt`。
3. **并发一致性**：主 WebUI 与侧栏同时打开同一会话，两端消息顺序一致、无重复（`event_bus_seq` 去重）。
4. **重连**：杀掉 Agent → 侧栏显示离线；重启后可重连并补拉历史（断言无丢帧）。
5. **负向验证**：把 `chrome-extension://<id>` 从白名单移除 → 连接应被 `4403 origin not allowed` 拒绝（证明白名单真的在生效，而不是"碰巧没走校验"）。

---

## 10. 参考依据汇总

- `app/main.py`：监听地址与自动开浏览器。
- `app/webui.py:1862`（`GET /`）、`:5120`（`POST /chat`）、`:5444`（`/sessions/{id}/stream`）、`:2916`（`/runtime-v2/.../stream`）、`:5012`（`/api/ui-presence`）。
- `app/remote_control/gateway.py:48-59`（Origin 校验）、`:99-106`（路由注册）、`:136+`（配对创建/认领）、`:239-345`（握手与鉴权）。
- `app/remote_control/service.py`（方法↔scope、幂等要求）、`app/remote_control/store.py:16-17`（默认 scope）、`app/remote_control/config.py`（`MYAGENT_REMOTE_CONTROL_*` 环境变量）。
- `app/templates/remote_control.html`：可工作的参考客户端（配对、订阅、历史去重、审批、忙时 steer）。
- `docs/remote_control.md`：协议帧格式、方法清单、配置表、安全模型。
- `frontend/vite.config.js`、`frontend/src/app/index.js`：前端构建与"单脚本全局作用域"结构（决定侧栏 UI 不适合复用主前端代码）。
- 外部依据：Chrome 扩展 `sidePanel` API 与 MV3 跨源访问（`host_permissions` 下 SW/扩展页 fetch 不受 CORS 约束；content script 仍受限）；Page Assist 的 sidebar + "Chat With Webpage" 形态。
