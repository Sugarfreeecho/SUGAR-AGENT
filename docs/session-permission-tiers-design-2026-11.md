# 会话权限分级规范（草案 v0.4，2026-11）

> **已被精简版取代**：[session-permission-levels.md](session-permission-levels.md)。本文保留作调研与证据附录（身份、控制面、缺口），不再作为方案正文。

> 主轴改为你定的那条：**直接或间接会超出本机的才受限；本机能直接操作的视为同一档。**
> 同时区分两件事：**操作者是否可信** 与 **内容是否可信**——本机操作者的指令可信，但从网页/评论/文档读进来的内容仍按不可信数据处理。
> v0.1 把浏览器扩展压到 L1 是错的，v0.2 已改正。标注 `现状` 的是代码事实，`建议` 的是待确认设计。

**已定决策**：R1 本轮权限模式保持全局，只把 `read_only`/`limits` 做成会话级；R2 本机渠道同等对待（WebUI/桌面/本机 CLI/本机扩展）；R3 跨出本机的渠道允许建会话，但限目录 + L1 工具档。
**R4 关键澄清**：三档权限模式与"可操作范围"是两套正交机制，本规范管后者，靠**入口场景 + 白名单**实现。
**R5**：本机 UI 接口新增本地令牌/CSRF 头，本机 ≠ 无门槛。
**R6**：白名单由**各插件自行维护**，宿主只提供契约与夹取；非白名单调用默认受限。
**R7**：白名单最高封顶 L3，改配置/删会话/跨目录仍需本机操作者。

---

## 〇、三个易混概念

| 概念 | 是什么 | 不是什么 |
|---|---|---|
| 权限模式（三档） | `ask_for_approval` 请求批准 / `approve_for_me` 替我审批 / `full_access` 完全访问权限。控制沙箱档（`app_restricted`↔`no_restriction`）、审批策略（`on_request`↔`never`）、审批者（用户/自动复核/无） | 不管会话可见范围、不管目录授权、不管工具集；且**现状是全局一个值**（`mode_scope=global`），会话级接口未真正生效 |
| 控制服务能力 | `session.create/send/steer/interrupt/config.update/...` 字符串能力表 | 不是 UI 上的开关，由 Principal 的 policy 决定 |
| 作用域 scope | `self` / `tree` / `sessions` / `workspace` / `workspaces` / `all` | 不是会话标签，是调用方视图 |

---

## 一、身份清单

### 1.1 边界维度（本次主轴）

| 边界 | 定义 | 例子 |
|---|---|---|
| **B0 本机** | 只有本机操作者能驱动，进程/浏览器都在同一台机器 | WebUI、桌面壳、本机 CLI、本机浏览器扩展 |
| **B1 跨设备** | 本机用户但通过另一台设备操作 | 手机/平板配对远程控制 |
| **B2 公网陌生人** | 消息来自不受你控制的人 | 飞书群成员、B站评论者、外部 ACP Agent |

### 1.2 系统身份

| 代号 | 身份 | 认证 | 边界 | 当前作用域 | 现状能力 |
|---|---|---|---|---|---|
| S1 | 本机 Web UI | 无令牌，loopback 同源 | B0 | 不适用（直连 manager） | 等同管理员：建/删会话、改目录、改权限模式、批审批 |
| S1b | 桌面壳 / 托盘 | Electron 主进程，本机 | B0 | 同上 | 同上（含托盘菜单入口） |
| S1c | 本机浏览器扩展 | 插件内配对记录 | B0（本机浏览器） | `workspace` / `sessions` | 建会话、发消息、审批；**当前低于 WebUI，需提升** |
| S2 | 本机 CLI 个人登录 | bootstrap/配对码换 `sc1_` Bearer | B0 | `all` 或自定义 | 按 grant 的能力 |
| S3 | 配对设备 | 设备令牌 / cookie，`/api/remote/v1` | B1 | `all` | `read` + `create/send/steer/interrupt`；不含配置与自动化 |
| S4 | 插件宿主 | 进程内 `host_client()` | B0 | `workspace` 或 `sessions` | `read` + 显式能力，默认含 `create/fork/send/notice` |
| S5 | 运行时子代理 | `@runtime/subagents`，`kind=runtime` | B0 | `tree` | `read/create/send/notice`，受 `runtime_ceiling` 收窄 |
| S6 | ACP 入站客户端 | Bearer（个人或宿主令牌） | B0/B1 视来源 | 同令牌 | 新建/恢复/发送/取消/改模型，按会话挂 MCP |
| S7 | 外部 Agent（ACP 出站） | 子进程，默认 `permission=reject` | B2 | 无 | 仅宿主代管下执行 |
| S8 | 定时/事件自动化 | 任务内 `_automation_id` | B0 | 按任务 policy | `read/create/send` |
| S9 | Hook | OS 用户跑 shell | B0 | 无 | 无直接能力；**可读凭据文件 → 能调 CLI**（风险点） |
| S10 | 未认证外部 | 无 | B2 | 无 | 控制面拒绝；UI 接口仅 loopback |

### 1.3 用户身份

| 代号 | 身份 | 入口 | 边界 |
|---|---|---|---|
| U1 | 本机管理员 | bootstrap、设置页 | B0 |
| U2 | 本机用户 | WebUI、桌面壳、本机 CLI、本机扩展 | B0 |
| U3 | 本机用户的另一台设备 | 远程控制配对 | B1 |
| U4 | 公网陌生人 | 飞书群、B站评论/弹幕、外部 ACP | B2 |
| U5 | 未配对访客 | 任何外部渠道 | B2（应拒绝） |

### 1.4 信任级

- **T3 本机可信**：B0 全部（S1/S1b/S1c/S2/S4/S5/S8/S9 的操作者侧）+ U1/U2 —— 能力不降级
- **T2 本机派生**：子代理、自动化、插件 —— 继承本机能力但作用域收窄
- **T1 跨设备**：B1（U3/S3）—— 需配对，能力等同 L2，不能改全局配置
- **T0 外来回源**：B2（U4/U5/S7）—— 最小能力，默认不得新建会话

**内容侧规则（建议）**：即使操作者是 T3，凡来自网页/评论/文档/外部 Agent 的文本，按"不可信内容"处理——涉及写盘、删文件、外发数据、改权限的动作一律走人工审批，不因身份是 T3 而自动放行。

---

## 二、会话控制面盘点

### 2.1 Agent 本体（12 处）

| # | 位置 | 能做什么 |
|---|---|---|
| 1 | `webui.py` `POST /sessions` | 建会话：`work_dir`、`model_profile_id`、`reasoning_effort`、`system_context(_mode)`、`permission_mode`、`prefetch` |
| 2 | `webui.py` `/sessions/{id}/*` | 改目录、改系统上下文、改权限模式、切模型、打断、审批、追问队列、steer、continue、删会话 |
| 3 | `webui.py` `/sessions/{parent}/subagents/*` | 看子代理、打断、换模型、删子会话 |
| 4 | 控制服务 RPC | `session.create/list/get/history/search/attach/detach/send/send_batch/steer/steer.cancel/notice/interrupt/continue/recover/fork/update/archive/delete/export/import/config.*` |
| 5 | `operations` 队列 | 幂等准入、排队、取消、跨重启续跑 |
| 6 | CLI `agent-session-control.py` | 上述 RPC 的命令行映射 |
| 7 | 模型工具 `task` | 创建子代理会话 |
| 8 | 模型工具 `scheduled_tasks` / `manage_scheduled_task` | 建改定时任务，运行时 `session.create` |
| 9 | `automation.py` | 定时/事件触发 → `session.create` + `session.send` |
| 10 | ACP 入站 `acp_stdio.py` | `session new/list/resume/prompt/cancel/close`、`set_config_option`、按会话挂 MCP |
| 11 | 通知/回送 | `session.notice`、完成汇总投递 |
| 12 | Hooks | 生命周期 shell，间接可执行 CLI |

### 2.2 插件（7 个涉及会话）

| 插件 | 接入方式 | 能力 | 作用域 | 建会话 | 发消息 | 边界 |
|---|---|---|---|---|---|---|
| acp-agents | `host_client("acp-agents", session_ids=[origin])` | `send`、`notice` | 单会话 | 否 | 是 | B0→B2（回送原会话） |
| agent-goal | `host_client` | `continue/recover` | 单会话 | 否 | 是 | B0 |
| feishu-transport | `transport_service("feishu-transport")` | `create/send` | workspace（强制项目 `WORK_DIR`） | 是 | 是 | **B2** |
| browser-use | 自建 `authorize` + `transport_service` | `create/send/update`、`approval.resolve` | workspace / 配对会话 | 是 | 是 | **B0（本机扩展）** |
| sugar-bili-scroll | `ensure_host_session` + `host_client` | `send`、`steer` | 单会话 | 是 | 是 | **B2**（评论/弹幕） |
| agent-team | 少量引用 | — | — | 否 | 否 | B0 |
| web-search-providers | 仅工具 | — | — | 否 | 否 | — |

### 2.3 对外通讯接口

| 接口 | 鉴权 | 边界 |
|---|---|---|
| `POST /api/control/v1/rpc` | Bearer | B0–B2 取决于令牌 |
| `GET /api/control/v1/events`、`/operations/{id}/events` | Bearer | 同上 |
| `/api/control/v1/auth/claim|pairings|logout` | bootstrap / 配对码 | bootstrap 仅直接 loopback |
| `/api/acp/connections`、`/api/acp/mcp/{sid}`、`/api/acp/status` | Bearer | B0/B1 |
| `/api/remote/v1/{pairings,claim,client,ws}` | 设备/cookie | B1 |
| ACP 出站 stdio | 子进程 + `env_refs` | B2 |
| MCP Server | 配置 + 审批 | 只扩工具 |

### 2.4 结构性缺口

1. **权限模式实为全局**：`mode_scope="global"`，会话级读写不一致，无法做到"这个会话严格、那个会话宽松"。
2. **会话无归因字段**：元数据没有 `origin`/`created_by`/`tier`，只能从 `operations._source.id` 反推轮次，无法按来源配额或审计。
3. **本机渠道不同权**：WebUI 直通，浏览器扩展却是受限插件；同一台机器上两套标准。
4. **插件作用域偏宽**：`scope=workspace` 可在目录内任意新建会话。
5. **Hooks 可读凭据**：以 OS 用户运行，可读 `%LOCALAPPDATA%\SugarAgent\session-control\*.json` 后直接调 CLI，绕过所有分级。

---

## 三、分级矩阵（5 档，按边界）

### 3.1 等级定义

| 等级 | 面向对象 | 边界 | 作用域 | 目录 | 操作 | 工具档 | 模型档 | 审批 |
|---|---|---|---|---|---|---|---|---|
| **L0 观察** | 未配对访客、只读集成 | B2 | `session_ids` | 无写 | `list/get/history/search/attach` | 只读白名单 | 单一固定档 | 不适用 |
| **L1 外部受限** | 飞书群、B站评论、外部 ACP 回送 | B2 | `sessions`（绑定） | 仅会话既有目录 | **默认禁建**；`send(queue)`、`notice` | 只读 + 显式 allowlist，禁 `run_shell` 写 | 固定 1–2 档 | 每次问人，高危必问 |
| **L2 跨设备** | 远程控制配对设备 | B1 | `all` 或 `workspace` | 已授权目录 | `create/send/steer/interrupt` | 继承，可收窄 | 已启用档案 | 三档可选，红线必问 |
| **L3 本机派生** | 插件、子代理、定时/事件、Goal | B0 | `workspace` / `tree` | 任务目录 | L4 去掉 `delete/export/import/device.*` | 受 `runtime_ceiling` 强制收窄 | 会话配置指定 | 红线必问，非红线可自动 |
| **L4 本机直控** | WebUI、桌面壳、本机 CLI、**本机浏览器扩展** | B0 | `all` | 任意已存在目录 | 全部，含 `export/import`、改全局权限模式、`device.*` | 无限制 | 全部可切换 | 可切三档，红线仍不可绕过 |

**叠加规则**：`生效能力 = 身份等级 ∩ 会话等级 ∩ 单轮覆盖 ∩ runtime_ceiling`，取最小；单轮覆盖不得突破 ceiling。

**内容侧附加**：L4 的操作者指令可信，但网页/评论/文件内容作为数据，触发写盘、删除、外发、改权限时仍需人工确认——这条同时防住"本机浏览器扩展被恶意网页注入"。

### 3.2 会话内"每次对话"粒度

| 粒度点 | 字段/机制 | 说明 |
|---|---|---|
| 单轮模式 | `session.send.mode` = `queue/append/interrupt` | 后两者需 `steer`/`interrupt` 能力 |
| 单轮覆盖 | `runtime_override` | 仅 `queue`；可临时改工具/预算/只读 |
| 单轮预算 | `limits.timeout_seconds`、`limits.max_tool_calls` | 超限即止，外部渠道必备 |
| 单轮只读 | `read_only` | 会话常开或单轮覆盖 |
| 每次工具调用 | `allow_once` / `allow_always` / `deny` | `FORCED_APPROVAL_RULES` 禁止长期授权，只允许一次性 |
| 每轮工具集 | `tools.mode=custom` + `allow/deny/bindings` | 可锁参数、限根目录、限 host |
| 每轮模型 | `model_profile_id`、`reasoning_effort` | 运行中改动下一轮生效 |

### 3.3 入口场景与白名单（核心机制）

**入口决定默认档，白名单只做升级。** 同一个人从不同入口进来，能力可以不同。

| 入口类型 | 例子 | 触发者 | 默认档 | 建会话 | 工具 |
|---|---|---|---|---|---|
| 本机入口 | WebUI、桌面壳、本机 CLI、本机浏览器扩展 | 本机操作者 | L4 | 可 | 不限 |
| 受控私聊 / 点对点 | IM 私聊、ACP 入站、远程配对设备 | 指定对象 | L2 | 可（限目录） | 继承 + 收窄 |
| 多人频道 | 飞书群、团队频道 | 群成员 | L1 | 仅白名单 | 只读 + 少量安全工具 |
| 公共入口 | B站评论/弹幕、公开 webhook | 任何人 | L0 | 否 | 无工具或仅文本回复 |
| 宿主任派生 | 插件、子代理、定时/事件 | 本机程序 | L3 | 可 | 受 `runtime_ceiling` |

**白名单归属**：由插件自己维护（R6），宿主不集中存。宿主只做三件事：给 `host_client`/`ensure_host_session` 传入 `level`、把 `level` 夹取到合法区间、在 `session.create/send` 时写入 `tier` 元数据。原因很直接——插件最懂自己的渠道身份（B站是 UID、飞书是 open_id、ACP 是客户端名），集中建模只会变成一堆特例。

**现成范例**：`sugar-bili-scroll` 已经这么做了——`inbound_whitelist` 维护 `uid → 备注`，白名单用户拿到全套模型工具（`bili_reply`），非白名单用户**零模型工具**，只由宿主把一段普通回复投递回原楼层（`workflow.py:651`、`host.py:1401`）。新规范应把这个模式推广到 feishu、browser-use。

**白名单条目**（插件侧建议结构）

| 字段 | 含义 |
|---|---|
| `channel` | 渠道 id：`feishu` / `bili` / `acp` / `remote` / `browser` |
| `subject` | 外部用户标识：open_id、UID、设备 ID |
| `level` | 提升到的等级，最高 L4 |
| `workspaces` | 允许目录，空则用渠道默认目录 |
| `tools_mode` | `inherit` 或 `custom`（custom 时带 allow/deny） |
| `model_profiles` | 允许使用的模型档案 |
| `can_create` | 是否允许新建会话 |
| `expires_at` | 有效期，过期自动回落默认档 |

规则：白名单**只升不降**，多条命中取最高、且**不得超过 L3**（R7）；宿主对所有插件自报等级做 clamp（插件常驻默认 L1，声明 L2 需用户在插件设置里显式开启，L3 仅限本机派生来源）；命中写审计；撤销即时生效，与插件 `host_sources.epoch` 撤销同构。

**与三档权限模式的关系**：正交。三档模式 = 工具执行时的沙箱与审批策略（全局一个值）；本表 = 可操作范围与工具集上限。二者相乘，互不替代。

### 3.4 落地改动清单

1. **会话级只读与预算**：`read_only`、`limits` 已由 `runtime_config` 支持，本轮只补 UI 入口与按会话生效校验；三档模式保持全局（R1）。
2. **会话元数据三字段**：`origin`（ui/desktop/cli/extension/acp/plugin:<id>/automation）、`created_by`、`tier`，并进索引投影。
3. **本机渠道拉平**：`browser-use` 从 `host:` 插件档提升到 L4 等价，保留配对撤销与内容侧审批（R2）。
4. **插件能力按档生成**：`DEFAULT_CAPABILITIES` 不再固定拼 `fork/notice`，改为按 tier 计算。
5. **外部渠道可建会话但受控**：feishu/bili 建会话需目录白名单 + `tier=L1` 工具档 + 预算（R3）。
6. **白名单归属插件 + 宿主夹取**：插件在自己的 settings 存白名单（照 bili 的 `inbound_whitelist`），`host_client(..., level=)` 新增 `level` 参数并 clamp 到 ≤L3；命中写 `audit`，不新建中心化白名单表。
7. **Hooks 凭据隔离**：凭据 DPAPI/ACL 保护，或 Hook 进程剔除 `MYAGENT_CONTROL_TOKEN`。
8. **模型档白名单**：`model_profiles` 增加 `allowed_levels`。

---

## 四、决策状态

已定：R1 权限模式保持全局（只加会话级只读/预算）；R2 本机渠道同级；R3 外部渠道允许建会话但限目录 + L1 工具档。

已定补充：R5 本机接口加本地令牌/CSRF；R6 白名单由插件自维护、非白名单默认受限；R7 白名单封顶 L3。

待定：

- **D5**：多人频道（内部团队飞书群）归 L1 只读，还是按群配置成 L2 受限操作。
- **D6**：插件声明 L2 的开关放哪——插件设置页逐项勾选，还是集中一个"信任此插件的入站用户"总开关。
- **D7**：本地令牌的发放与存放——启动时生成注入 UI，还是复用现有个人登录凭据。范围见 §〇 与 R5。
