# Runtime V2 correctness and performance supplement (2026-07-17)

- `events.jsonl` is the Runtime V2 fact source. Malformed, undecodable, or unsupported-version rows must raise a repair-required error; readers must never skip them and continue with a shorter projection.
- Every event carries `schema_version`; snapshots and projection indexes carry projector/index versions. Version mismatches invalidate only derived caches and rebuild from facts.
- V2 model, context, subagent, pending-result, and persistence failures are fail-closed. A projection error is never equivalent to an empty session.
- Normal append updates projections incrementally. Full message reprojection is reserved for delete, rewrite, truncate, model-window replacement, compaction, and equivalent semantic history operations.
- Snapshot disk writes may be coalesced because snapshots are rebuildable. Published in-memory projections use copy-on-write, and restart recovery replays a bounded tail (default checkpoint interval: 32 events).
- Runtime seq reads use a versioned sparse byte-offset index. Reconnect polling must not scan from byte zero when the cursor is near the tail.
- UI indexes store final-visible runtime seq mappings. Recent-turn reads may use the seq index when older history operations are outside the requested window; operations inside the window require full deterministic projection.
- Live reattach may do one UI-index catch-up and then advances by durable Runtime V2 seq. Semantic history operations explicitly request reprojection.
- Legacy UI migration commits a batch and materializes one snapshot, uses bounded-memory disk rollback, prioritizes on-open/manual work over startup scanning, and must migrate 10,000 local rows in under 10 seconds.
- Content-addressed blobs are atomic and SHA-256 verified.
- A stale provider token checkpoint keeps the prior provider-scale value with `pending_recalculation=true`; projection errors are explicit and never trigger a silent local-scale switch.
- `history_snapshot.timing` includes `read_page`, `count`, `user_turns`, `context_tokens`, `todo_plan`, and `total`; retain `open_session_timing` and `pre_api_timing` diagnostics.

# General Agent 工程规格说明

版本日期：2026-06-07

## 1. 项目定位

General Agent 是一个本地运行的 AI Agent 开发与使用平台。系统通过浏览器 Web UI 提供会话式交互，由 Python FastAPI 后端驱动 ReAct 推理循环、工具调用、子 Agent 编排、上下文压缩、MCP 扩展和会话持久化。

本工程的目标是让用户在本机完成代码开发、文件处理、联网检索、研究分析、文档生成和多步骤自动化任务，同时保留可审计的会话记录、工具过程和运行日志。

### 1.1 层级术语（全仓注释与文档统一使用）

- 会话：侧边栏一条 = 一个会话（session）。
- 轮：会话内一次对话 = 一轮（一条用户提问到最终回复完成；分页、TOC、`/user_turns` 中的「轮次」均指此，不用于 API 计数）。
- 步：每次 API 发送 = 一步（对应 `react_iter`，执行过程面板统计中的「N 步」）。
- 条：每一步期间产生的一条思考/回复/工具/状态记录（feed item，过程面板的行单位）。

## 2. 运行形态

### 2.1 生产运行

- Windows 入口脚本：`RUN.bat`
- Ubuntu/macOS 入口脚本：`RUN.sh`
- Unix 运维接口：`scripts/agentctl start|stop|restart|status|logs|update|tray`
- Python 入口：`app/main.py`
- 默认服务地址：`http://127.0.0.1:8192/`
- 后端应用对象：`app/webui.py` 中的 `fastapi_app`
- 前端产物目录：`app/templates/dist/`

启动流程：

1. Windows 由 `RUN.bat` 设置 UTF-8 输出和内置 Python 路径，并启动 `app/tray_launcher.py`。
2. Ubuntu/macOS 由 `RUN.sh` 检查 `.venv`，首次运行调用 `scripts/install_unix.sh`。
3. Ubuntu 后端由用户级 systemd 服务监管；macOS 后端由用户级 LaunchAgent 监管。
4. 后端最终通过 `app/main.py` 启动 FastAPI/uvicorn。
5. `app/main.py` 调用 `refresh_executor_client_from_env()` 刷新 LLM 配置。
6. 服务监听后自动打开浏览器，除非 `OPEN_BROWSER=0/false/no/off`。

Windows、Ubuntu 和 macOS 的常驻图标（Windows 任务栏右下角 / macOS 菜单栏 / Ubuntu 顶部栏）均提供 WebUI、设置、MCP、日志、重启、更新和退出入口。重启与更新操作默认隐藏，由 `MYAGENT_TRAY_SHOW_UPDATE_RESTART` 启用。更新操作由独立进程执行 `git pull --ff-only`，仅在 `app/requirements.txt` 变化时同步 Python 依赖，完成后通过对应生命周期后端恢复服务。更新不得强制覆盖本地修改；失败时必须恢复启动并记录到 `logs/agent_update.log`。

WebUI 必须继续只监听 `127.0.0.1:8192`。Ubuntu Server 的远程访问通过 SSH 本地端口转发完成，不得因平台适配默认开放局域网或公网监听。

### 2.2 工具安全运行形态

- 权限模式是工作区外持久化的单一全局状态；新任务、子 Agent、后台任务、切换工作区和应用重启都使用当前全局模式，且不得自动降级。初次安装默认 `ask_for_approval = (app_restricted, on_request, user)`。
- `approve_for_me = (app_restricted, on_request, auto_review)`，只替换审批者，不改变文件、网络或进程边界。
- `full_access = (no_restriction, never, none)`，普通文件、工作区内删除、Shell 与网络操作不执行应用层审批；格式化、磁盘写入、关机等非删除高危命令的一次性人工审批以及 Agent 自保/控制器完整性硬拒绝不受该档位影响。
- `app_restricted` 使用当前操作系统用户运行，依靠中央策略、工作区路径限制、敏感环境过滤和危险操作检查；UI 必须明确标为“应用层受限”，不得称为硬沙箱。
- 普通读取（含工作区外）默认放行，凭据/信息安全类文件（`.env`、`.ssh`、密钥、凭据库等）读取需审批；工作区内普通写入和 Shell 自动允许；工作区内删除（含 `delete_file`、补丁删除及 `rm`/`Remove-Item` 等 Shell 删除）与动态代码为普通黄色审批，可由“替我审批”自动审查，也可“本次/本任务”放行，不得强制人工弹窗；工作区外写入、Shell 外部路径、网络、不可恢复删除及未知副作用请求审批；格式化、磁盘写入、关机等非删除高危命令在所有权限模式下均为红色强制审批；`delete_file` 仍为移入 `WORK_DIR/.trash/` 的可恢复软删除；凭据导出、安全策略篡改和 Agent 控制器终止在所有权限模式下默认拒绝。
- 原生 OS 沙箱是未来可选高级功能，不是正常运行、写文件或执行工作区 Shell 的前置条件。
- MCP 与 Plugin 按声明的 `read/workspace_write/external_write`、网络、Shell 和未知副作用能力执行 `allow/ask/deny`，不得因其类型一律拒绝。
- `run_shell` 的旧范围参数只保留调用兼容，不能由模型用于开启或关闭权限；新 schema 和提示不得暴露该参数。
- 策略、全局权限档位、审批摘要、授权消费状态、插件信任、MCP 注册确认和审计记录必须保存在工作区外；审批 grant 仍按会话和请求摘要隔离。
- 完全访问无需设置页预先启用；用户切换时必须看到强警告，并明确提示该全局状态会跨任务、工作区和应用重启保持，同时说明工作区内删除不再询问、非删除高危系统命令仍需一次性确认、Agent 自保红线仍会硬拒绝。
- Hook 命令在启动前必须按 Hook ID、事件、命令、cwd、环境、配置摘要和策略版本鉴权；没有交互通道或鉴权异常时不得启动。
- 可执行 Plugin 在 `describe` 前必须核对用户建立的内容摘要信任。MCP 在第一次 `start/connect` 前必须取得一次人工注册确认，并绑定完整配置摘要；摘要变化后重新确认。确认后可以连接、发现并注册工具，但每次 MCP 工具调用仍必须经过当前全局权限模式对应的中央审批。
- 不得提供容器沙箱实现、依赖、探测、配置或备用路径。

### 2.3 前端开发运行

后端开发服务：

```bash
cd app
python -m uvicorn webui:fastapi_app --reload --port 8000
```

前端开发服务：

```bash
cd frontend
npm install
npm run dev
```

Vite 开发服务器默认端口为 `5173`，并代理：

- `/sessions` -> `http://127.0.0.1:8000`
- `/api` -> `http://127.0.0.1:8000`

### 2.4 前端构建

```bash
cd frontend
npm run build
```

构建输出必须写入 `app/templates/dist/`。后端主页优先服务该目录中的 `index.html`。如果构建产物缺失，后端应显示构建提示页，而不是回退到过期 UI。

## 3. 技术栈

### 3.1 后端

- Python 3.10，工程内置运行时位于 `python/`
- FastAPI + uvicorn
- OpenAI 兼容 API 客户端
- SSE 事件流
- MCP Python SDK
- python-dotenv 环境变量加载
- 文件、网络、PDF、Office、数据分析相关依赖见 `app/requirements.txt`

### 3.2 前端

- Vite
- 原生 JavaScript ES Module
- 原生 CSS
- 构建入口：`frontend/index.html`
- 运行入口：`frontend/src/main.js`
- UI 引导器：`frontend/src/app/index.js`

前端当前采用“按功能拆模块，但共享全局状态”的迁移形态。模块加载顺序仍然重要，后续重构必须保持旧执行顺序或显式声明模块依赖。

## 4. 目录职责

| 路径 | 职责 |
| --- | --- |
| `app/` | Python 后端、Agent 核心、路由、工具、配置页模板 |
| `app/templates/` | 后端 HTML 模板和 Vite 生产构建产物 |
| `app/tools/` | 工具辅助资源，例如 tokenizer |
| `frontend/` | Vite 前端源码 |
| `frontend/src/app/modules/` | 前端会话、SSE、消息渲染、子 Agent、设置、TOC/Todo 等功能模块 |
| `python/` | 内置 Python 运行时与依赖 |
| `workspace/` | 默认工作区、会话数据、技能目录、用户产物和临时分析文件 |
| `logs/` | 运行/对话日志 |

## 5. 核心后端模块

### 5.1 `app/webui.py`

系统的 HTTP/SSE 边界层，负责：

- 服务 Web UI 首页和静态资源。
- 创建、读取、删除、重命名、归档、置顶会话。
- 接收用户聊天请求。
- 建立会话 SSE 事件流。
- 暴露历史消息、用户轮次、Todo、上下文 token 估算。
- 处理工具审批。
- 管理子 Agent 列表、输出、停止和删除。
- 提供首次配置、高级环境变量配置和 MCP 配置页面。
- 对未配置状态进行中间件拦截，引导用户进入 `/setup`。
- 扫描并后台恢复所有未归档的中断会话（`react-recovery-*` 恢复 run，失败按 `REACT_RECOVERY_RETRY_SECONDS` 重试）。
- 处理审批卡片的“替我分析”请求（只返回审查建议，不执行授权）。
- 存在 pending 提问/审批时禁止自动恢复、Goal 续跑与删除会话。

### 5.2 `app/agent.py`

对外轻量入口，导出：

- `astream_events`
- `astream_events_continuation`
- `session_manager`

其他模块或脚本应优先从这里导入 Agent 流式能力，而不是直接耦合内部实现。

### 5.3 `app/agent_harness.py`

Agent 调度与持久化核心，负责：

- 加载 `app/.env`。
- 解析 prompt 模板。
- 创建和刷新 OpenAI 兼容客户端。
- 管理 executor 模型调用、流式调用和 usage。
- 序列化/反序列化消息。
- 从 UI 事件重建核心消息。
- 管理 `llm_history`、`dialogue_history`、`key_context`、`metadata` 等会话文件。
- 估算 token。
- 支持历史截断、分支、压缩摘要和 key context 合并。
- 处理模型 reasoning/thinking 相关兼容逻辑。

### 5.4 `app/agent_loop.py`

ReAct 执行循环，负责：

- 调用 LLM。
- 解析 assistant tool calls。
- 执行内置工具和 MCP 工具。
- 将工具 pending、工具结果、LLM delta、进度提示、最终回答等事件推送到 SSE。
- 支持工具审批等待。
- 支持中断检查。
- 清理临时写入文件。
- 处理 API 错误分类和最终输出校验。
- 提供普通运行和 continuation 运行。
- 维护进程级 CPU 压力策略：严重压力下切为非流式输出、限制本地只读工具并发。
- 流式文本增量按帧合并（`LLM_STREAM_COALESCE_MS`），首 token 立即推送。
- 目标：Goal 完成申请当轮立即执行 Judge，并把完整 Goal 对话证据注入下一轮上下文。
- 集成请求恢复预算（`_LogicalRequestBudget`）与工具审查上下文构建。

### 5.5 `app/agent_tools.py`

内置工具层，提供：

- 文件工具：`read_file`、`write_file`、`edit_file`、`delete_file`
- 目录和搜索：`ls`、`glob`、`grep`
- 命令执行：`run_shell`
- 网络工具：`web_search`、`web_fetch`、`web_download`
- 技能系统：`discover_skills`、`get_skills_catalog`、`activate_skill`
- 任务管理：`update_todo`
- 上下文管理：`context_manage`
- 子 Agent 入口：`task`
- Goal 工具：`create_goal`、`get_goal`、`update_goal`

工具层必须继续承担路径限制、敏感信息脱敏、输出截断、SSRF 防护、危险命令判断和 shell 超时控制。
`ls` 行为约定：

- 仅对已识别的文本/源码文件统计行数（白名单后缀与文件名）。
- 压缩包（zip/7z/rar/tar/gz 等）不显示大小与行数（均为 `—`）。
- 单文件行数统计上限 `LS_LINE_COUNT_MAX_BYTES`（默认 5 MiB），超限显示 `— (>5.0 MiB)`。
- 执行层保留 `list_dir` → `ls` 兼容映射，LLM 工具定义只暴露 `ls`。

### 5.6 `app/agent_subagent.py`

子 Agent 编排层，负责：

- 过滤子 Agent 可用工具。
- 构造子 Agent 用户消息和附件上下文。
- 启动单个子 Agent。
- 支持 `best-of-n` 多路并行策略。
- 维护父子会话关系。
- 汇总子任务结果。
- 支持中断和清理。
- 在需要时创建/清理 git worktree 隔离环境。

### 5.7 `app/agent_memory.py`

上下文策略层，负责：

- 估算完整上下文包大小。
- 判断是否触发压缩。
- 执行渐进式压缩、微压缩、摘要合并和应急裁剪。
- 维护 `key_context` 中的压缩摘要。
- 尽量保留近期真实用户轮次和任务关键状态。

### 5.8 `app/agent_mcp.py`

MCP 扩展层，负责：

- 读取 MCP 配置。
- 启动 stdio、SSE、streamable-http MCP server。
- 将 MCP tool schema 转为 OpenAI tool definition。
- 调用 MCP 工具。
- 格式化 MCP 工具返回结果。
- 支持强制重载和统一关闭。
- 所有 MCP 异步操作（`force_reload`/`ensure_started`/工具调用）固定运行在专用长期事件循环（`_run_on_mcp_loop`），避免 asyncio 原语跨循环绑定错误，并正确传播取消。

### 5.9 会话生命周期模块

`app/session_lifecycle.py` 负责：

- 标记会话删除状态。
- 注册运行任务。
- 判断会话是否正在运行。
- 取消指定会话或会话树的运行任务。

`app/session_event_bus.py` 负责：

- 发布会话事件。
- 订阅会话事件。
- 剪裁短期事件缓存。
- 关闭指定会话的流。

## 6. 前端模块规格
### 5.10 `app/cpu_pressure.py`

进程级 CPU/内存/事件循环延迟复合监测（psutil）：

- 采样间隔 `CPU_PRESSURE_SAMPLE_SECONDS`（默认 10s），滑动窗口均值。
- 阈值：`CPU_PRESSURE_HIGH_PERCENT`（默认 85）进入繁忙、`CPU_PRESSURE_SEVERE_PERCENT`（默认 90）进入严重、`CPU_PRESSURE_RECOVERY_PERCENT`（默认 65）恢复；连续 12 次升档确认 + 120s 恢复稳定期防抖。
- 严重压力下 LLM 输出切换为非流式，本地资源型只读工具并发降为 `CPU_PRESSURE_TOOL_CONCURRENCY`（默认 2）；繁忙状态保持流式。

### 5.11 `app/agent_goal.py` / `agent_goal_judge.py`

持久 Goal 生命周期与完成裁决：

- 双阶段完成流程：`update_goal(completed)` 只登记申请，独立 Judge 裁决 `done/continue`。
- Judge 证据 = 完整 Goal 生命周期对话（不裁剪）+ 裁剪后近期辅助证据；可从 `events.jsonl` 重建。
- Goal 元数据跟踪 `completion_requested_run_id`/`origin_run_id`；GoalManager 单例缓存；活动 Goal 会话状态可订阅。

### 5.12 `app/security/`（权限、审批、egress）

- `policy.py`/`runtime.py`/`store.py`：权限模式、能力策略、审批记录持久化。
- `reviewer.py`：审查模型（“替我分析/替我审批”），审查上下文携带请求与用户意图。
- `egress_guard.py` + `shell_analysis.py`：网络出口守卫——发现并健康检查系统 helper（`SUGAR_AGENT_EGRESS_HELPER` → `app/native/` → `PATH`），按策略对命令执行网络放行/隔离；helper 报告 `strong`/`partial`，缺失时 `degraded`。协议见 `docs/egress_helper_protocol.md`。
- `extensions.py`：插件/MCP 注册信任与审批门（`EXTENSION_REGISTRATION_APPROVAL_ENABLED`）。

### 5.13 `app/runtime_observability.py` / `execution_metrics.py`

- Runtime V2 可观测性：内存缓存 + 防抖整文件写盘（`RUNTIME_OBSERVABILITY_FLUSH_DELAY_MS`/`EXECUTION_METRICS_FLUSH_DELAY_MS`，默认 200ms）、终端状态立即落盘、`atexit` 兜底、60s 全量扫描上限。
- 执行指标看板：运行/工具耗时、心跳、挂起恢复时长（`runtime_power.py` 共享挂起监视器）。

### 5.14 `app/agent_team/`

Agent 团队调度：活动团队会话跟踪 + 事件驱动调度器（状态变化唤醒，避免轮询自我唤醒）。


### 6.1 页面结构

- `frontend/index.html` 是页面 shell。
- `frontend/src/shell-body.html` 承载主体 HTML 片段。
- `frontend/src/main.js` 引入 CSS、路径选择器和 UI 入口。
- `frontend/src/app/index.js` 负责按既有顺序初始化 UI 模块。

### 6.2 功能模块

| 模块 | 职责 |
| --- | --- |
| `config.js` | 读取运行时配置 |
| `shared-state-and-dialogs.js` | 共享状态、弹窗、提示 |
| `settings.js` | 设置面板与配置交互 |
| `session-management.js` | 会话列表、切换、发送、中断、重发、归档、置顶、删除 |
| `sse-handling.js` | 建立和处理 SSE 流 |
| `message-rendering.js` | 渲染用户、assistant、工具、进度、最终回答等消息 |
| `session-scroll-history.js` | 历史分页、滚动跟随、上下文 token 标签、流式 DOM 状态 |
| `subagent.js` | 子 Agent 面板、卡片、增量同步、展开折叠、停止和删除 |
| `toc-todo.js` | 会话目录、Todo 面板、hover tooltip |
| `layout-panels.js` | 布局面板状态 |
| `event-dispatch.js` | 前端事件分发协调 |

### 6.3 前端行为要求

- 正在运行的会话切换回来时，应能恢复或同步流式状态。
- 历史消息应支持按需加载，避免一次性渲染超大 DOM。
- 子 Agent 详情应懒加载，并支持卡片级增量同步。
- 工具调用应区分 pending、streaming、done、error 和 approval required。
- Todo 和 TOC 应随会话切换清理并重新加载，不能显示上一会话残留状态。
- 前端对长文本、工具输出和流式块应做折叠、溢出处理和复制支持。

## 7. API 规格

### 7.1 页面与静态资源

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/` | Web UI 首页 |
| GET | `/static/myagent_path_picker.js` | 路径选择器脚本 |
| GET | `/setup` | 首次配置页 |
| GET | `/setup/env` | 高级环境变量配置页 |
| GET | `/setup/mcp` | MCP 配置页 |

### 7.2 会话

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/sessions?include_archived=false` | 获取会话列表 |
| POST | `/sessions` | 创建会话 |
| GET | `/sessions/{session_id}` | 获取会话详情 |
| DELETE | `/sessions/{session_id}` | 删除会话 |
| PUT | `/sessions/{session_id}/name` | 重命名会话 |
| PUT | `/sessions/{session_id}/archive` | 归档/取消归档 |
| PUT | `/sessions/{session_id}/pin` | 置顶/取消置顶 |
| POST | `/sessions/{session_id}/interrupt` | 中断会话运行 |
| POST | `/sessions/{session_id}/truncate` | 截断会话事件 |
| POST | `/sessions/{session_id}/branch` | 从指定位置创建分支会话 |
| POST | `/sessions/{session_id}/append_ui_events` | 追加 UI 事件 |

### 7.3 聊天与流

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/chat` | 提交用户消息并启动 Agent 运行 |
| GET | `/sessions/{session_id}/stream` | 订阅会话 SSE 事件 |
| POST | `/sessions/{session_id}/continue` | 继续 ReAct 会话 |
| POST | `/sessions/{session_id}/continue-subagents` | 子 Agent 完成后继续父会话 |
| POST | `/sessions/{session_id}/continue-subagents/dismiss` | 忽略继续提示 |

### 7.4 消息与状态

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/sessions/{session_id}/messages` | 获取会话消息，支持分页/轮次参数 |
| GET | `/sessions/{session_id}/messages/count` | 获取消息数量 |
| GET | `/sessions/{session_id}/user_turns` | 获取用户轮次 |
| GET | `/sessions/{session_id}/todo_plan` | 获取 Todo 计划 |
| DELETE | `/sessions/{session_id}/todo_plan` | 清空 Todo 计划 |
| GET | `/sessions/{session_id}/context_tokens` | 获取上下文 token 估算 |

### 7.5 子 Agent

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/sessions/{session_id}/subagents` | 获取子 Agent 树/列表 |
| GET | `/sessions/{parent_id}/subagents/{task_id}/output` | 获取子 Agent 输出 |
| POST | `/sessions/{parent_id}/subagents/{child_id}/interrupt` | 中断子 Agent |
| DELETE | `/sessions/{parent_id}/subagents/{child_id}` | 删除子 Agent |
| POST | `/sessions/{parent_id}/subagents/{child_id}/model-profile` | 运行时切换子 Agent 模型 profile（保留 child ID/历史/worktree） |

### 7.6 配置

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/env` | 获取环境变量快照 |
| POST | `/api/env` | 保存环境变量更新 |
| POST | `/api/save_config` | 保存首次配置 |
| GET | `/api/mcp_config` | 获取 MCP 配置 |
| POST | `/api/mcp_config` | 保存 MCP 配置 |
| POST | `/api/pick-path` | 调用本机路径选择 |
| GET/POST | `/api/security/settings` | 读取/更新安全设置（含工作区外许可撤销） |
| GET | `/api/open-workspace-file` | 打开 workspace 文件 |

### 7.7 工具审批

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/sessions/{session_id}/tool-approval` | 提交用户对待审批工具调用的允许/拒绝决定 |

### 7.8 Session List and UI Loading Rules

- `/sessions` and `/sessions/state` are sidebar/navigation endpoints. They must stay lightweight and should return from in-memory/session-index data plus local active-run evidence only.
- Sidebar refresh must not scan every session's full Runtime V2 snapshot, rebuild projections, read large `ui_events.json`, traverse subagent dialogue, or perform orphan cleanup. Deep Runtime V2 cleanup belongs in explicit single-session actions, debug endpoints, or background maintenance.
- Session list refresh must not block current conversation rendering. Page startup should be able to open `lastSessionId` even when sidebar refresh is slow or temporarily unavailable.
- Global/sidebar errors must not be appended to the active chat stream, `ui_events.json`, process aggregates, or replayable history. They should render in the owning UI surface only.
- Frontend session-list fetches must be coalesced while one request is in flight. On refresh failure, keep the last usable sidebar state instead of clearing the list or blocking message history loading.
- Manual user actions may show scoped errors. Background refresh, polling, reconnect, and lifecycle reconciliation should prefer silent degradation plus cached state.

## 8. SSE 事件规格

SSE 是后端向前端展示 Agent 过程的主通道。事件至少应覆盖以下语义：

- LLM 文本 delta
- LLM reasoning/thinking delta
- 工具调用开始
- 工具命令/参数展示
- 工具执行 pending
- 工具审批 required
- 工具执行结果
- 进度提示
- Todo 更新
- 子 Agent 开始/更新/完成
- 最终回答
- 错误
- 会话关闭/中断

所有 SSE 事件必须包含足够信息让前端在以下场景恢复 UI：

- 当前会话实时运行。
- 用户切走后切回。
- 页面刷新后从持久化消息重建。
- 子 Agent 卡片懒加载详情。

## 9. 数据持久化规格

默认会话根目录位于 `workspace/sessions/`。每个会话目录通常包含：

| 文件 | 说明 |
| --- | --- |
| `metadata.json` | 会话名称、归档、置顶、更新时间等元数据 |
| `ui_events.json` | 前端可重放事件流 |
| `work_messages.json` | Agent 工作消息 |
| `llm_history.json` | 发送给模型或可重建模型上下文的历史 |
| `dialogue_history.json` | 面向对话显示/压缩的历史 |
| `key_context.md` | 压缩后的关键上下文 |
| `todo_plan.md` | Todo 计划 |
| `pending_subagent_results.json` | 子 Agent 待处理结果 |
| `subagent_tasks.json` | 子 Agent 任务索引 |
| `truncate_backups/` | 截断前备份 |

子 Agent 会话存放在父会话的 `subagents/{child_id}/` 下，结构尽量与主会话一致，并可额外包含 `output.md`。

全局会话索引：

- `workspace/sessions/sessions.json`
- `workspace/sessions/subagent_index.json`

持久化要求：

- 写入 JSON 时必须保证可恢复，避免半写入破坏会话。
- 历史截断、分支、压缩前应保留必要备份或边界标记。
- 子 Agent 输出必须可从父会话索引追溯。
- UI 事件和 LLM 历史可以不同步，但必须能通过修复/重建逻辑恢复到可显示状态。

## 10. 消息模型

后端轻量消息类型定义在 `app/agent_messages.py`：

- `UserMessage`
- `SystemMessage`
- `AssistantMessage`
- `ToolMessage`

要求：

- 消息类型命名必须与历史落盘结构兼容，不应随意重命名。
- `UserMessage.content` 支持字符串和多模态数组。
- `AssistantMessage` 支持 `tool_calls`、`metadata` 和 `additional_kwargs`。
- `ToolMessage` 必须带 `tool_call_id`，用于对应 assistant 的工具调用。
- 序列化和反序列化逻辑由 `agent_harness.py` 统一维护。

## 11. 配置规格

主要配置文件：`model_profiles.json`（模型）与 `app/.env`（非模型运行设置）。

### 11.1 LLM 配置

模型名称、类型、API 连接、密钥、窗口限制、推理模式、temperature、extra body 与多模态输入模式必须保存在 model profile 中。多模态输入模式支持 `auto`、`enabled`、`disabled`；只有有效状态支持多模态的 profile 才能展开并发送媒体内容，接口明确拒绝后必须持久化为 `disabled`。旧 `.env` 模型字段仅允许在启动时执行一次性、幂等导入：等价 profile 不得重复创建，导入完成后不得持续覆盖 profile，也不得作为运行时回退。

要求：

- 修改 LLM 配置后必须刷新 executor client。
- API key 等敏感字段在 UI、日志和工具输出中必须脱敏。
- OpenAI 兼容接口差异应在 `agent_harness.py` 或 `agent_openai.py` 中适配，避免散落到业务层。
- 媒体序列化只由目标 model profile 的有效输入模态决定：支持图片时将 prompt 或附件中的图片引用转为 `image_url` content；仅文本时保留路径/URL 文本并注入多模态 `task` 委派指引。主 Agent 和 subagent 必须共用此规则。
- 配置向导入口只检查是否存在可用 model profile。
- 检查配置向导入口前必须先完成旧 `.env` 模型配置的自动注册。

### 11.2 工作区配置

典型字段：

- `WORK_DIR`
- `LOG_DIR`

要求：

- 相对路径应相对工程根目录解析。
- 工作区变化可能需要重启才能完全生效。
- 文件工具默认限制在工作区内，越界操作必须经过限制或审批。

### 11.3 搜索与网络配置

典型字段：

- `WEB_SEARCH_PROVIDER`
- `TAVILY_API_KEY`
- Brave/SearXNG/Jina 等 provider 相关配置

要求：

- 网络搜索 provider 不可用时应有明确错误。
- `web_fetch` 和 `web_download` 必须保留 SSRF 防护和下载大小限制。

### 11.4 MCP 配置

示例文件：`app/mcp_servers.json.example`

支持 transport：

- `stdio`
- `sse`
- `streamable-http`

要求：

- MCP 配置保存后应支持重新加载。
- MCP 工具名必须经过安全映射，避免函数名冲突或非法字符。
- MCP 工具是否需要 UI 审批由 `agent_mcp.py` 和审批层共同决定。

### 11.5 稳定性与安全配置

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `OPENAI_HTTP_TIMEOUT` | `300` | LLM 请求超时（秒） |
| `OPENAI_MAX_RETRIES` | `4` | LLM 最大重试次数 |
| `OPENAI_FIRST_TOKEN_HEDGE_TIMEOUT_SEC` | `30` | 首 token 竞速阈值（0=关闭） |
| `OPENAI_FIRST_TOKEN_HEDGE_MAX_RETRIES` | `2` | 每次调用最多竞速次数 |
| `CPU_PRESSURE_*` | 见 5.10 | CPU 压力监测参数 |
| `LLM_STREAM_COALESCE_MS` | `12` | 流式增量合并窗口 |
| `SECURITY_ENABLED` | `1` | 普通安全审批总开关（`0` 进入完全访问，但不关闭破坏性审批与 Agent 自保红线） |
| `EXTENSION_REGISTRATION_APPROVAL_ENABLED` | `0` | 插件/MCP 注册人工确认 |
| `EGRESS_HELPER_ENABLED` | `1` | 系统级网络出口助手（`0` 关闭） |
| `SUGAR_AGENT_EGRESS_HELPER` | 自动发现 | 指定 helper 路径 |
| `REACT_RECOVERY_RETRY_SECONDS` | `30` | 后台会话恢复重试间隔 |
| `MYAGENT_FRONTEND_VERSION` | `v1` | 前端版本标识 |
| `LS_INCLUDE_LINE_COUNTS` / `LS_LINE_COUNT_MAX_BYTES` | `1` / `5242880` | `ls` 行数统计开关与上限 |

## 12. 安全规格

### 12.1 文件系统

- 默认文件操作必须限制在 `WORK_DIR`。
- 删除文件应采用软删除或受控删除策略。
- 凭据文件（`.env`、密钥文件等）读取一律要求审批，且每次都要确认（不支持“始终允许/本会话允许”）；写入/修改仍拒绝，凭据导出（上传、复制到外部、网络发送）无条件拒绝。
- MyAgent 自身敏感资源（`app/.env`、`config.bin`、`secret_loader`、安全策略与授权库）不允许被工具读取或写入，工具结果不得泄露。
- 路径解析必须处理 Windows/Posix 差异、引号、重定向和 shell token。

### 12.2 Shell

- `run_shell` 必须支持超时、中断、输出截断和二进制输出摘要。
- 危险命令必须被识别或要求用户审批。
- 工作区外路径访问必须受限。
- Windows 下 Bash、PowerShell、CMD 的执行差异必须集中在工具层处理。

### 12.3 网络

- `web_fetch` 和 `web_download` 必须阻止访问本机、内网、保留地址等 SSRF 风险目标。
- 重定向目标必须重新校验。
- 下载必须有最大字节数限制。

### 12.4 敏感信息

- 日志、工具输出、UI 预览和模型上下文中应尽量脱敏 API key、token、secret 等字段。
- 环境变量高级配置页应标记敏感字段，并避免明文回显不必要内容。

### 12.5 审批

- 工具审批通过 `/sessions/{session_id}/tool-approval` 完成。
- 审批状态必须绑定具体 session 和 tool call，避免跨会话串扰。
- 用户拒绝时，Agent 应收到结构化的拒绝结果，而不是静默失败。

### 12.6 网络出口控制（egress）

- `EGRESS_HELPER_ENABLED=1` 时，命令执行前通过 helper 健康握手（`health --json`）获取强制级别；`strong` 可按目标约束网络，`partial` 仅可整体拒绝，缺失/未启用为 `degraded`。
- helper 通过 `SUGAR_AGENT_EGRESS_HELPER` → `app/native/` → `PATH` 顺序发现；Windows 助手由 C# 源码可复现构建，`.exe` 不入库。
- 降级时前端必须提示“当前没有系统级网络隔离”，命令仍按应用层审批执行。
- 协议细节与后端命名见 `docs/egress_helper_protocol.md`。

### 12.7 注册审批与恢复门禁

- `EXTENSION_REGISTRATION_APPROVAL_ENABLED=1` 时：可执行 Plugin 首次启用/内容摘要变化、MCP 首次注册/配置摘要变化必须人工确认；确认只授权加载/连接/能力发现，工具调用仍走中央审批。
- 存在 pending 提问或审批的会话不得被通用恢复、Goal 续跑或 HTTP continuation 启动；仅回答/取消交互的专用恢复链可继续（发现与执行阶段双门禁）。

### 12.8 审批卡片

- 手动审批卡提供“替我分析”（复用审查模型，返回风险等级与建议，不执行授权；上下文仅存于待审批期间）。
- 拒绝审批时，已有自动审批或“替我分析”的拒绝结论应自动携带其理由；没有可用结论时由用户填写拒绝原因。拒绝原因随审批记录持久化，并返回给 Agent 作为后续调整依据。
- 工作区外操作与工具执行分开审批：先批准工作区处理（始终允许/本次允许），之后仍需单独审批工具操作。

## 13. 上下文管理规格

系统必须支持长会话运行，核心策略：

1. 保留近期用户轮次。
2. 对较旧工具结果和长文本进行微压缩。
3. 将早期对话压缩进 `key_context.md`。
4. 在上下文压力过高时进行应急裁剪。

要求：

- 压缩不得丢失当前任务目标、用户明确约束、未完成 Todo 和关键文件路径。
- 压缩边界必须在历史中可识别。
- 压缩后的 `key_context` 不应混入 Todo 计划正文，二者应可分离解析。
- 前端应能显示当前上下文 token 估算。

## 14. 子 Agent 规格

子 Agent 用于把复杂任务拆成隔离运行单元。

要求：

- 子 Agent 必须拥有独立 session id。
- 子 Agent 的事件和输出必须能在父会话中追踪。
- 父会话应能知道子 Agent running/completed/failed/interrupted 状态。
- `best-of-n` 运行必须能汇总多个候选结果。
- 子 Agent 默认不得污染父 Agent 的核心历史，除非结果被显式汇总。
- 中断父会话树时应能取消相关子 Agent 任务。

## 15. 技能系统规格

技能位于 `workspace/skills/` 或其他配置路径下，每个技能至少包含 `SKILL.md`。

要求：

- `discover_skills` 应能扫描技能目录。
- `activate_skill` 应按需加载技能说明。
- 技能加载结果应进入 Agent 可见上下文，但避免一次性加载大量无关引用。
- 技能脚本和资源路径必须相对技能目录解析。

## 16. 日志与可观测性

日志目录：`logs/`

要求：

- 每次会话/用户输入应能生成可追踪日志。
- 日志中应包含必要的模型、工具、错误和运行过程信息。
- 日志中必须脱敏敏感配置。
- 前端显示的工具过程与后端日志应能互相辅助排查。

## 17. 性能规格

### 17.1 后端

- SSE 事件推送不得因长工具调用完全静默，应有 keepalive 或进度事件。
- 大工具输出必须截断或写临时文件后摘要返回。
- 上下文 token 估算和压缩应避免阻塞 UI 主流程过久。
- 会话删除、中断和子 Agent 停止必须及时释放运行任务。

### 17.2 前端

- 历史消息应分页/懒加载。
- 归档目录首次显性展示 20 条并预取但隐藏后续 20 条；每次点击“加载更多”新增展示 20 条，同时继续预取下一批。
- 子 Agent 详情应懒加载，避免大量卡片一次性渲染完整过程。
- 流式文本应批量 flush，避免每个 token 都触发布局。
- TOC/Todo/上下文 token 刷新应异步调度，避免切换会话卡顿。

### 17.3 自适应与可观测性性能

- CPU 严重压力下 LLM 请求整体切换为非流式，减少逐 token 解析/持久化开销；恢复后自动还原。
- 流式正文累积使用 list + join，避免字符串平方级复制；增量按 12ms 帧合并后再渲染。
- 可观测性文件采用防抖整文件重写（默认 200ms），终端状态与显式快照立即落盘。
- 前端构建将 Mermaid 预构建为本地 vendor，生产构建从约 5 分钟降至约 2 秒。
- Provider token 缓存加入工具指纹，工具启停后不会误用旧缓存；发送前估算计入工具 Schema，避免首步 token 突跳。

## 18. 验收标准

### 18.1 启动验收

- Windows 运行 `RUN.bat`、Ubuntu/macOS 运行 `RUN.sh` 后，服务可访问 `http://127.0.0.1:8192/`。
- 缺少前端构建产物时显示明确构建提示。
- 已配置 `.env` 时不应误跳首次配置页。
- 修改 LLM 配置后重启或刷新配置可生效。

### 18.2 会话验收

- 可创建新会话。
- 可发送消息并收到流式响应。
- 可切换会话并恢复历史。
- 可重命名、归档、置顶、删除会话。
- 删除运行中会话时应中断对应运行任务。

### 18.3 工具验收

- 文件读写编辑能在 `WORK_DIR` 内正常执行。
- 工作区外或高风险操作会被限制或触发审批。
- shell 命令支持超时、中断和输出截断。
- 网络抓取阻止内网/本机地址。
- 工具错误能清晰反馈给前端和 Agent。

### 18.4 子 Agent 验收

- 主 Agent 可通过 `task` 启动子 Agent。
- 子 Agent 状态在前端面板可见。
- 子 Agent 输出可展开查看。
- 可中断和删除子 Agent。
- 子 Agent 完成后父会话可继续处理结果。
- `task.prompt` 和 `task.file_attachments` 中的图片引用必须进入同一模态门控：图片模型收到 `image_url` content，纯文本模型只收到可恢复的文本引用与委派提示。

### 18.5 上下文验收

- 长会话达到阈值后可触发压缩。
- 压缩后仍能保留当前任务目标和近期对话。
- `key_context.md`、`todo_plan.md` 可分别读取。
- 前端上下文 token 显示不阻塞主交互。

### 18.6 前端验收

- 生产构建成功写入 `app/templates/dist/`。
- 会话切换不残留上一会话的 TOC/Todo/子 Agent 状态。
- SSE 流式输出、工具过程、最终回答均能正确渲染。
- 长消息、长工具输出、子 Agent 历史不会造成明显卡顿。

### 18.7 新功能验收

- CPU 压力升至严重阈值后输出切为非流式，恢复后还原；阈值可通过环境变量调整。
- 首 token 超过竞速阈值时发起并行请求，先到者胜出，另一路被关闭且不产生重复副作用。
- Goal 申请完成当轮即执行 Judge；Judge 证据包含完整 Goal 对话（可从 `events.jsonl` 重建）。
- 存在 pending 提问/审批时，通用恢复、Goal 续跑与删除会话均被拒绝。
- egress helper 缺失时显示降级提示；helper 健康检查通过时按策略放行/隔离网络。
- 深色主题、执行过程折叠/展开高度、工作区 GIF/图片/音视频渲染在 360px 与桌面宽度下均可正常使用。
- 中断会话在页面刷新/重启后由服务端后台自动恢复（无 pending 交互时）。

## 19. 变更约束

- 修改前端源码后必须运行 `npm run build`，确保生产 UI 更新到 `app/templates/dist/`。
- 修改路由时必须同步更新本 spec 的 API 表。
- 修改会话落盘结构时必须考虑旧会话兼容和迁移。
- 修改消息类型名称或序列化字段属于高风险变更，必须提供兼容层。
- 修改工具安全策略时必须补充越界路径、危险命令、敏感信息和 SSRF 测试。
- 修改上下文压缩策略时必须用长会话样例验证任务目标不丢失。

## Runtime V2 收敛补充规范

- API 返回的 `prompt_tokens` 必须可作为下一步 API 前 token 估算的基线；当前缀请求包一致时，只允许估算新增尾部，禁止每步重新扫描完整长历史。
- Runtime V2 下 `/messages`、`/messages/count`、`/user_turns`、TOC/Todo/context snapshot 等 UI 读取必须优先来自 Runtime V2 projection/snapshot；不得因 TOC 或滚动恢复自动读取 legacy UI 历史。
- Runtime V2 下 `/todo_plan` 必须只读 Runtime V2 context snapshot；snapshot 无 Todo 时返回空 Todo 快照，不得回退读取 legacy `todo_plan.md` 或 `key_context.md`。
- Runtime V2 下 `/context_tokens` 必须优先读 Runtime V2 snapshot；snapshot 无缓存时只能用 Runtime V2 model projection 与 context summary 估算，不得调用 legacy session history 合并路径。
- Runtime V2 下 `/subagents` 普通展示必须只读 Runtime V2 subagent store / parent snapshot；V2 无 task/subagent 数据时返回空列表，不得回退扫描 legacy subagent 会话目录或 legacy task index。
- Runtime V2 下 subagent output 与 pending/continue 状态必须只读写 Runtime V2 subagent store 与 V2 UI projection；output 缺失或 pending 为空时返回 V2 结果，不得回退读取或反写 legacy output、pending results、task index 或 `ui_events.json`。
- Runtime V2 下 subagent task index 与虚拟 task output 写入必须只写 Runtime V2 subagent store；不得为了兼容同时反写 legacy `subagent_tasks.json` 或 `subagent_outputs/`。
- Runtime V2 下普通 ReAct continue 可用性判断必须读取 Runtime V2 UI projection；不得为了判断最后一步是否已有 final 而读取 legacy `ui_events.json`。
- `RUNTIME_SYNC_ON_MESSAGES_OPEN` 不得在 Runtime V2 primary 正常打开会话时同步读取 legacy；检测到 legacy-only 会话时，可由独立后台 migration coordinator 按需排队执行可验证迁移。迁移未完成前快照返回 `migration_pending`，前端自动重试，不得把旧会话显示为空 V2 会话。为避免批量 JSON 解析阻塞主进程，启动全量扫描默认关闭，仅可通过 `RUNTIME_V2_AUTO_MIGRATE_STARTUP=1` 显式启用。
- 显式 runtime sync/migration 可以导出 Runtime V2 UI projection 与 model projection 到 legacy 文件，用于备份、兼容和人工迁移；该导出不得出现在普通打开、发送、刷新、TOC 或滚动恢复路径。
- legacy migration/export 必须集中在 Runtime V2 migration service；允许 startup/on-open coordinator 只做文件指纹检查、排队和状态查询，普通 webui/messages/agent_loop/projection read path 不得直接加载、合并或反写 legacy 历史。
- 会话加载期间 TOC 可以提前启动，但后续被 suppress 的 `rebuildToc()` 必须是 no-op，不能再次清空 TOC、递增 TOC epoch 或作废已经发出的 `/user_turns` 请求。
- Runtime V2 打开会话应优先使用 session history snapshot，一次返回首屏正文分页、消息总数和 TOC 用户轮次，减少 `/messages`、`/messages/count`、`/user_turns` 多请求竞争；snapshot 失败时才回退旧分页接口。
- Runtime V2 session history snapshot 必须返回 `timing` 分段，至少包含 `read_page`、`count`、`user_turns`、`total`，慢日志也必须带同样分段，方便定位打开会话慢在正文分页、计数还是 TOC 索引。
- 前端打开会话必须保留 `open_session_timing` 诊断日志，至少包含前端总耗时、消息数、数据来源和后端 snapshot timing；日志只能用于慢请求诊断，不能改变滚动/TOC/渲染时序。
- 首次加载且没有保存滚动位置/anchor 时，应保持 V1 体验的平滑滚到底部；存在保存位置/anchor 时必须立即恢复，避免历史分页和 TOC active 更新打断用户位置。
- Runtime V2 的 TOC 用户轮次必须优先来自 projection index/cache；`/user_turns` 和 session history snapshot 不得为了 TOC 预览重新物化完整 UI events。
- Runtime V2 UI projection 的 `ui_index`、`runtime_seq` 映射必须基于最终可见 UI 投影，而不是原始 runtime seq 列表；删除、改写、截断、visible range 等历史操作必须先作用到投影后再生成 count/user_turns/index。
- Runtime V2 recent-turn tail 快路径遇到删除、改写、截断等 history ops 时必须回退到完整 projection，不能用原始尾窗绕过可见历史规则。
- `user_steer` 只表示 UI 展示类型差异：模型上下文仍按普通 user message 处理，UI projection 必须恢复为执行过程块中的“追问”，且不得进入 TOC 用户轮次。
- 运行中输入的追问先进入本地待发送队列；入队、刷新及普通服务端同步本身均不得发送 `pending` 条目。用户可点击任意 pending 条目的“立即发送”；若未点击，则上一轮对话正常结束后必须先完成服务端对账，并仅在本地 run、服务端 stream、发送管线锁和会话 dispatcher 全部空闲时按 FIFO 自动续发队首一条；用户主动停止及其抑制窗口不得自动续发。`consumed` 事件只能唤醒同一套空闲门禁，不得绕过活跃 run 直接续发。新 run 启动后其余条目继续等待该 run 的终止边界。手动与自动发送共用同一 per-session dispatcher，重复终止事件必须合并为一个 drain；每个终止边界最多尝试一条，失败时保留队列项且不得形成自动重试环。
- `interrupt` 追问必须用 `client_id/steer_id` 原位提交同一乐观行，并在追问处封口旧 process group；新运行即使从 `react_iter=1` 重新计数，也只能在新 process group 内查找/upsert reasoning 与 response 行，不得覆盖旧运行中编号相同的行。
- “立即发送”steer 返回 409（服务端认为旧 run 已结束）后降级 `/chat`，降级前必须等待发送锁释放；若锁迟迟未释放或 `/chat` 未真正开跑，必须将队列项恢复为 `pending` 保留，不得静默返回或定时无条件删除。
- 追问队列项必须持久化所有非终态状态（含 `clientId`、`steerId`、`status`、`mode`、`replacementRunId`），包括 `submitting/sending/accepted/restarting`；只有收到 `consumed/cancelled` 或 `/chat` 明确成功开跑后才删除。刷新恢复时 `submitting/sending` 回退为 `pending`（服务端按 `client_id` 幂等去重），`accepted/restarting` 保留由 watcher/server sync 继续追踪。
- 实时 `user_steer` SSE、轮询与历史回放必须携带并通过 `client_id/steer_id/steer_mode` 提交同一乐观行，不得 `appendLog` 新增重复行；`append` 模式先乐观追加 pending 行，SSE 到达时通过 operation-id 提交该行而非再追加一条；预留的乐观 UI event index 必须被持久化事件原位占用，不能使后续事件整体偏移。
- watcher 必须覆盖 `submitting/sending/accepted/restarting` 全部非终态状态，不能只监控后两种；SSE 丢失、轮询查到 consumed/cancelled 时必须相应提交或回退乐观行。
- 前端 context token/cache stats 显示必须以事件所属 session 为准；后台运行、切走会话或重连事件不得刷新当前可见会话的右上角 token 标签。

## 20. 已知工程特征

- 工程包含内置 Python，因此可在未安装系统 Python 的 Windows 环境运行。
- `workspace/` 同时承载默认工作区、会话、技能和用户产物，后续如要分离，需要迁移配置和历史路径。
- 当前前端模块化仍处于渐进迁移状态，存在共享全局状态，重构时要特别注意加载顺序。
- 旧文档中存在编码显示异常的内容，后续文档建议统一保存为 UTF-8。

## Runtime V2 与 API 前热路径修改规范

- Runtime V2 正常运行路径不得为了兼容旧文件而直接读取、重建或反写 legacy `work_messages.json` / legacy `llm_history.json`。旧数据迁移必须走隔离的 migration service；自动迁移仅可后台串行执行，要求 active-run 互斥、文件指纹幂等、UI/model/context/todo 全量预读、事务回滚和 manifest 校验。V2 为 legacy 精确前缀时可安全补齐 legacy 尾部，真实分叉必须记录 blocked manifest 并拒绝自动覆盖。
- 会话历史的工具执行过程以 Runtime V2 event log / projection 为准。任何 `replace_model_history` 都必须保留 assistant tool call 与 tool result 的配对关系，禁止用 `user/final` 可见主链重建模型历史。
- 修复历史错位、TOC、滚动、final 展示等前端问题时，优先修事件协议和 projection 边界，不得通过“重新拉全量历史并反写模型历史”兜底。
- 发送 API 前的热路径不得重复读取大历史、重复解析 `work_messages`、重复扫描完整历史或重复解析模型配置。新增逻辑必须观察 `pre_api_timing`，并说明主要耗时项是否变化。
- 模型配置、token 估算、中断状态等热路径允许使用短 TTL 或显式失效缓存；缓存必须在模型配置变更、会话模型 profile 变更、interrupt request/clear 等写路径同步失效或更新。
- 新增优化必须配套回归测试，至少覆盖：V2 不 fallback legacy、工具过程不被 user/final 主链覆盖、API 前热路径不会重复读盘或重复计算。
- SSE 结束、`run_finished`、`final` 三条路径必须共用同一套前端 run-state 收口逻辑，避免一条路径清理运行态而另一条路径仍保持生成中。
- SSE 读取必须支持 keepalive 和空闲超时；超时只能触发重连/恢复，不得直接追加错误执行块或把后台会话状态写入当前可见会话。
- 修复 live LLM delta 拆行或重复时，应优先保持同一 `react_iter` 的 live row 可跨 process group 重建继续 upsert；不得通过全量刷新正文或重建会话历史兜底。
- 同一 ReAct 运行的过程消息必须按 `(react_iter, phase, tool_call_index)` 展示，其中 `phase` 的唯一顺序为 `llm_reasoning -> llm_response -> tool_call/tool_result`。闭合参数的工具允许在模型流结束前提前执行，但完成事件的持久化与 SSE 发布必须等待本步 LLM reasoning/response 提交；steer 打断保存 partial assistant 时也必须遵守同一提交屏障。Runtime V2 UI projection 必须稳定修复旧日志中按完成时间形成的倒序，并同步重建 projection index，且不得跨 `user/final/interrupt steer` 边界混排。
