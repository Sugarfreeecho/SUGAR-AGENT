# MyAgent 浏览器侧栏 · 现状对齐版（v3）

- 版本：**v3**（2026-11-11）｜取代 [browser_extension_sidebar_design_v2.md](browser_extension_sidebar_design_v2.md)（v2.1，作为"设计意图"保留）
- 为什么有这一版：v2.1 是在**假定仓库里还没有扩展**的前提下写的（当时要求"新建 `browser-extension/`、走 Remote Control `/api/remote/v1/ws`"）。实际情况是仓库里**早就有**一个可用的扩展（v0.6.36）与配套后端插件 `plugins/browser-use`，协议是 `/api/browser/v1/*`。本文以现有实现为准，纠正 v2.1 中被现实推翻的假设。

---

## 1. 现状事实（实测）

| 项 | 事实 | 依据 |
|---|---|---|
| 扩展本体 | `browser-extension/`，v0.6.36，React + TypeScript + Vite；加载目录为 `browser-extension/dist` | `public/manifest.json`、`src/App.tsx`（73 KB）、`package.json`（`build = tsc --noEmit && vite build`） |
| 扩展 ID | **`mdiicfkdpohkiccgjiomnlmokamaafbo`**（由 manifest `key` 推导，`public/` 与 `dist/` 一致） | manifest `key` + SHA-256 前 32 hex 映射 a–p |
| 权限 | `sidePanel, storage, tabs, debugger, scripting, contextMenus, alarms, activeTab, downloads`；`host_permissions: http://*/*, https://*/*`；`minimum_chrome_version: 125` | manifest |
| 侧栏入口 | `side_panel.default_path = sidepanel.html`；`options_page = sidepanel.html#settings`；快捷键 `Ctrl+Shift+Y` | manifest |
| 后端插件 | `plugins/browser-use`（id `browser-use`，v0.6.36，`capabilities.trusted_host.entry = host.py`，另有 `web` 设置页与 `settings.section` 渲染器） | `plugins/browser-use/.myagent-plugin/plugin.json` |
| 后端路由 | 前缀 `/api/browser/v1`，由插件 host 注册（**不是** `webui.py` 内的路由） | `plugins/browser-use/host.py:163` |
| Playwright 中继 | 插件自带 Node 进程 `plugins/browser-use/node/server.mjs`，本次实例监听 `127.0.0.1:6030`（`/extension?token=…`） | 进程 22900（父进程为 `app/main.py`）、`/setup` 返回 `runtime_installed: true` |
| 扩展就绪度 | `GET /api/browser/v1/setup` → `extension_ready: true`、`extension_directory: …\browser-extension\dist`、`version: 0.6.36`、`node_available: true`、`protocol: 1` | 实测 2026-11-11 |
| 设备状态 | 5 条 `browser_connections`：**4 条已撤销**，仅 `a201b0c6…` 有效（`default_browser`），其 `runtime = {connected:false, initialized:false, paused:false, port:6030, generation:5}` | `GET /api/browser/v1/status` |
| 远控（另一套） | `app/.env` 未设 `MYAGENT_REMOTE_CONTROL_*` → `/api/remote/v1/status` **404**，与本扩展无关 | 实测 |

> 结论：**服务端与中继都在运行且健康**；连不上属于客户端侧（配对身份 / 浏览器权限 / 载入副本）问题。

---

## 2. 真实连接协议

### 2.1 时序

```
① 主界面 → 设置「浏览器连接」（插件设置页）→ 生成一次性配对码
   POST /api/browser/v1/pairings   （loopback + Origin: http://127.0.0.1）

② 侧栏「配对并连接」：POST /api/browser/v1/claim
   Header Origin: chrome-extension://mdiicfkdpohkiccgjiomnlmokamaafbo
   body  { code }  → 返回该浏览器设备的凭据（token）

③ 长连接：ws://127.0.0.1:8192/api/browser/v1/ws
   客户端 → {"type":"hello","token":…,"browser_id":…}
   服务端 → {"type":"ready","relay_url":"ws://127.0.0.1:6030/extension?token=…"}

④ 浏览器桥：扩展连 relay_url，随后 attach 普通标签页（需 debugger 权限），
   向服务端上报 runtime {connected, initialized, paused, port, generation}
```

### 2.2 关闭码与故障语义（服务端精确位置）

| 码/状态 | 触发条件（服务端） | 扩展侧文案 | 含义 |
|---|---|---|---|
| **403**（握手前拒绝） | `host.py:687` 三条件之一不满足，`close(4403)` 在 `accept()` 之前 → Starlette 回落 HTTP 403 | —（连接直接失败） | 非直连 loopback（走了代理）/ Origin 不符 / 插件未启用 |
| **4403** | 同上（已进入 WS 层时触发） | **"浏览器连接插件暂不可用，恢复后将自动重连"** | 同上，最常见是 **Origin 不符**（载入了另一份副本，ID 变了）或**插件被禁用** |
| **4401** | `hello` 非法、`browser_connections` 记录缺失/已撤销、`browser_id` 与记录不匹配、或运行时授权失败（`host.py:722`、`:881`） | "配对授权已被撤销或已到期，请重新配对" | 需要重新配对 |
| **404** | 请求了当前后端不存在的路由（如 `/api/browser/v1/messages`） | "请重启 SugarAgent 后端以启用自动页面关联" | 后端是旧进程 |
| 连不上 | 端口关闭 / 后端未起 | "无法连接本机 SugarAgent，配对已保留" | 服务未运行 |
| relay 失败 | `relay_url` 握手失败（debugger 未授权、端口被占等） | "浏览器桥接连接失败" | 浏览器权限或中继问题 |

### 2.3 客户端重连与状态

- 退避：1s → 2s → … → 30s；另注册 `chrome.alarms`（`sugar-reconnect`，0.5 min）兜底。
- 状态集合：`unpaired / connecting / connected / disconnected / auth-required / error`，同时写入 `chrome.storage.session['sugar.status']` 并广播给侧栏；工具栏角标 `!`（出错）/`Ⅱ`（暂停）。
- 4401 时会额外调 `verifyPairing` 复核：确认无效才落到"重新配对"，避免一次抖动就清凭据。

---

## 3. 服务端 API 全表（`/api/browser/v1/*`，均在插件 host 内）

| 方法 | 用途 |
|---|---|
| `GET /setup`、`POST /setup/install`、`GET /setup/download`、`POST /setup/reveal` | 扩展安装态与安装包（`extension_directory` 指向 `browser-extension/dist`） |
| `GET /status` | 插件开关、`extension_origin`、设备列表与 `runtime`、`default_browser` |
| `POST /pairings`、`POST /claim` | 生成/兑换一次性配对码（claim 要求扩展 Origin） |
| `GET /connection`、`POST /devices/{id}/revoke`、`POST /default` | 连接信息、撤销设备、设默认浏览器 |
| `GET /models`、`POST /session-state`、`GET /workspaces`、`POST /workspaces/pick`、`POST /workspaces/validate` | 会话上下文：模型、会话状态、工作区 |
| `GET /plugins`、`GET /skills` | 插件/技能列表（侧栏选择器） |
| `POST /messages`、`POST /steers`、`POST /permissions` | 发消息（含页面上下文引用）、追加/打断、权限设置 |
| `POST /approvals/analyze` | 审批卡"AI 分析" |
| `POST /uploads`、`GET /files`、`GET /media` | 附件上传与工作区文件/媒体读取 |
| `WS /ws` | 长连接（hello/ready、会话事件、relay 地址） |

**鉴权要点**：写请求必须带扩展 Origin（`host.py:139-150`）；`GET/HEAD` 允许缺 Origin（Chromium 扩展 worker 的既有行为）；配对凭据以 Bearer 形式传递；设备记录在 `browser_connections`，撤销后 hello 即 4401。

---

## 4. 与 v2.1 的差异（被现实推翻的假设）

| v2.1 的假设 | 现状 | 处理 |
|---|---|---|
| D2：通道用 Remote Control v1（`/api/remote/v1/ws` + `session.*` 方法） | 实际是 `/api/browser/v1/ws` + 插件 `browser-use`，方法名完全不同（`/messages`、`/steers`、`/session-state`…） | 以本文 §2/§3 为准；Remote Control 属另一套（当前未启用） |
| D9：无构建链（原生 ESM） | 实际是 React + TS + Vite，加载 `dist` | 构建/发布按 `browser-extension/package.json` 脚本 |
| D15：中英双语 + 跟随系统深浅色 | 现有实现为中文界面 + `ui.css` 的深色媒体查询（`prefers-color-scheme: dark`），未见 i18n 框架 | 改为"现状：中文单语 + 深色媒体查询"；双语属新增需求 |
| D18：手工改 `.env` 两行 | 实际只需主界面「浏览器连接」生成配对码；无需改 `.env`（插件随应用启用） | 启用流程改为"配对码"单步 |
| D16/D11：新增 `session.update`、`model.list`、`skill.list`、`approval.analyze` 等协议方法 | 这些能力**已由插件 API 提供**（`/models`、`/skills`、`/approvals/analyze`、会话操作走 `/session-state` 等） | 无需新增协议方法；改造点在扩展侧 UI |
| 目录 `browser-extension/`（新增） | 目录已存在，含 `src/ dist/ tests/ scripts/ artifacts/ design-review/` | 沿用现有目录与测试体系 |

---

## 5. 故障矩阵与处置

| 现象 | 先查 | 处置 |
|---|---|---|
| **「浏览器连接插件暂不可用」**（= 4403） | ① `chrome://extensions` 里该扩展卡片的 **ID 是否等于 `mdiicfkdpohkiccgjiomnlmokamaafbo`**；② 主界面是否把 `browser-use` 插件关掉；③ 是否走了代理（Tailscale/系统代理）导致非直连 | ① 若 ID 不符 → 卸载后改加载 `browser-extension\dist`（`public/`、`.build-0.6.31/`、`artifacts/` 里的旧副本 ID 不同）；② 重新启用插件并等 10s；③ 关掉该域名的代理 |
| 「配对授权已被撤销或已到期」 | `/api/browser/v1/status` 里该设备是否 `revoked: true` | 主界面「浏览器连接」生成新配对码 → 侧栏重新配对 |
| 「浏览器桥接连接失败」 | `chrome://extensions` 是否有"需重新授予权限"提示；`6030` 是否被别的进程占用 | 移除后重新加载 `dist` 并授予 `debugger`；必要时重启 Agent 以重启中继 |
| 「请重启 SugarAgent 后端…」 | 后端启动时间 vs `app/*.py` 修改时间 | 重启 Agent |
| 状态文案不变、也不重连 | Service Worker 是否休眠（`chrome://extensions` → 该扩展 → Service Worker 检查视图） | 点"重新加载"或关开侧栏；若仍不动，属 SW 侧缺陷（`initializing` 相关） |

**本次实测证据**：15:28 的日志里同时出现 `WebSocket /api/browser/v1/ws [accepted]` 与 `403`（后者为我无凭据探测），且 `/status` 显示 `plugin_enabled: true` → 说明**当时确有客户端通过了 Origin+loopback+启用 三重校验**；因此持续 4403 更可能来自"载入了 ID 不同的副本"或"插件被临时禁用后状态未刷新"。

---

## 6. 待办（文档层面，未改代码）

1. 若需要中英双语/浅色主题，属**新增需求**，需在现有 `ui.css`（媒体查询）之上引入语言包与主题切换。
2. 若需要"审批卡记住这类操作"，需在插件 `/permissions` 扩展能力（当前未见对应 UI）。
3. `design-review/`、`artifacts/`、`.build-0.6.31/` 属历史产物，建议在 README 里标注"勿作为加载目录"，避免误载入导致 Origin 不符（这正是 4403 的典型来源）。

---

## 7. 依据

- 扩展：`browser-extension/public/manifest.json`、`src/background.ts`（`connectApp`/`connectRelay`/`scheduleReconnect`/`chrome.alarms.onAlarm`）、`src/App.tsx`、`package.json`、`README.md`。
- 插件：`plugins/browser-use/.myagent-plugin/plugin.json`、`host.py:30/72/74/139-150/163/176-684/687-722`、`node/server.mjs`、`runtime.py`。
- 实测：`GET /api/browser/v1/setup`、`GET /api/browser/v1/status`、`logs/agent_terminal.log`（15:28 段）、进程 20348/22900、端口 6030。
- 上限行为参考：`app/remote_control/gateway.py:23-37`（`_is_loopback` 接受 `::1` 与 `localhost`，故 `localhost` 不是 4403 的成因）。
