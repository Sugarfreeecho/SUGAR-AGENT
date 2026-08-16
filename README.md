# SugarAgent

> **Self-Upgrading General Agent Runtime**
>
> 一款本地运行的可自优化代码通用智能平台。在本机完成代码开发、文件处理、联网检索、研究分析、文档生成和多步骤自动化任务，同时保留可审计的会话记录与运行日志。

---

## 项目概览

SugarAgent 是一个**本地运行**的 AI Agent 开发与使用平台。它通过浏览器 Web UI 提供会话式交互，由 Python FastAPI 后端驱动 **ReAct 推理循环**、**工具调用**、**子 Agent 编排**、**上下文压缩**、**MCP/插件扩展**、**持久 Goal** 和**会话持久化**。

系统支持连接 OpenAI 兼容接口的任意 LLM 后端（DeepSeek、Mimo 等），无需依赖外部云服务即可在本地完成复杂的多步骤任务。服务端调度器可在浏览器关闭后继续执行持久 Goal，并具备 CPU 压力自适应、首 token 竞速重试等稳定性机制。

---

## 核心能力

| 能力 | 说明 |
|------|------|
| 🧠 **ReAct 推理循环** | 基于 ReAct 模式的 LLM 调度，支持工具调用链、流式输出和中断恢复 |
| 🔧 **内置工具系统** | 文件读写编辑、目录搜索、Shell 命令、Web 搜索/抓取/下载、上下文管理等 20+ 工具 |
| 🤖 **子 Agent 编排** | 通过 `task` 工具将复杂任务拆分为隔离子 Agent，支持 best-of-n 多路并行、运行中 steer 与**运行中模型切换** |
| 🎯 **持久 Goal 模式** | 服务端调度器自动续跑未完成的 Goal，不依赖浏览器保持打开；双阶段完成流程由独立 Judge 裁决 |
| 🗜️ **上下文压缩** | 渐进式压缩、微压缩、摘要合并和应急裁剪，保障长会话稳定运行 |
| 🔌 **MCP 扩展** | 支持 stdio / SSE / Streamable HTTP 三种 MCP transport；专用后台事件循环避免跨循环绑定错误 |
| 🧩 **插件生态** | Plugin API v1 支持 Python/Node 工具、Hook、Slash Command，可在插件包中携带 Skill/MCP/Agent |
| ⚡ **稳定性自适应** | CPU 压力监测下自动降级为非流式输出；首 token 超时自动发起并行重试；可观测性防抖写盘 |
| 🛡️ **安全边界** | 工作区路径限制、Shell 危险命令拦截、SSRF 防护、敏感信息脱敏、工具审批、**网络出口控制（egress）** |
| 🖥️ **前端体验** | 深色/紫色主题、执行轨迹 V2（可折叠/展开高度）、工作区媒体渲染（GIF/图片/视频/音频）、会话自动恢复 |
| 💾 **会话持久化** | 完整会话状态落盘（元数据、事件流、LLM 历史、对话历史、Todo 计划） |
| 🖥️ **常驻图标** | Windows 任务栏右下角 / macOS 顶部菜单栏 / Ubuntu 顶部栏图标，集成开关菜单与更新/重启 |

### 工具权限与应用层限制

MyAgent 全局统一使用一套持久权限模式，主界面提供三档固定权限。新任务、子 Agent、
后台任务、切换工作区和应用重启都会立即使用当前全局模式；只有用户主动切换才会改变：

| 模式 | 执行边界 | 审批 |
|------|------|------|
| 请求批准 | `app_restricted` | 普通只读（含工作区外）与 `delete_file` 软删除自动放行；敏感文件读取、工作区外写入/Shell、网络、不可恢复删除或未知副作用需审批 |
| 替我审批 | 与“请求批准”完全相同 | 独立只读审查 Agent 决定是否批准 |
| 完全访问权限 | `no_restriction` | 不审批；以当前宿主用户权限执行 |

`app_restricted` 使用当前操作系统用户运行，通过中央能力策略、工作区路径校验、敏感环境过滤、危险操作检查和摘要绑定审批限制工具。它是应用层防护，不是硬沙箱；不会因为缺少原生 OS 沙箱而降级只读。普通读取（含工作区外）自动允许，凭据/信息安全类文件读取需审批；工作区内普通写入和 Shell 自动允许；动态代码为普通审批（不可沉淀“始终允许”规则），破坏性命令为红色强制审批，凭据导出与安全策略篡改默认拒绝。安全策略、全局权限档位、审批记录、插件信任和 MCP 注册记录保存在工作区外。审批 grant 仍绑定具体会话与请求摘要；权限模式本身不做会话隔离。

审批卡片提供**“替我分析”**：复用审查模型给出风险等级、分析理由与允许/拒绝建议，但不代行审批；工作区外操作与工具执行**分开审批**——先审批工作区处理，之后仍需单独审批工具操作。审查上下文携带待审批请求与用户意图，仅在审批期间保留于内存。

`EXTENSION_REGISTRATION_APPROVAL_ENABLED=0`（默认）时，MCP 与可执行 Plugin 能力直接注册；设为 `1` 后，可执行 Plugin 首次启用或内容摘要变化、MCP 首次注册或配置摘要变化都必须由用户确认。注册确认只授权加载、连接和能力发现，具体工具调用仍按当前全局权限模式执行中央 `allow/ask/deny`。Plugin 与 MCP 均以当前操作系统用户权限运行，能力声明不构成硬隔离。

**网络出口控制（Egress Guard）**：可选的系统级网络隔离助手。`EGRESS_HELPER_ENABLED=1` 时，Agent 通过健康握手发现原生助手（`SUGAR_AGENT_EGRESS_HELPER` → `app/native/` → `PATH`），依据策略对命令执行**网络放行/隔离**；helper 报告 `strong`（可按目标约束网络）或 `partial`（仅可整体拒绝）。助手缺失或未启用时，出站防护处于 `degraded` 状态，前端会提示"当前没有系统级网络隔离"，命令仍按应用层规则审批。协议见 [docs/egress_helper_protocol.md](docs/egress_helper_protocol.md)，Windows 助手由 C# 源码可复现构建（`scripts/build_egress_helper_windows.ps1`）。

原生 OS 沙箱仅作为未来可选的高级安全功能，不是正常运行的前置条件。本项目不安装、检测或调用容器运行时。

---

## 技术栈

### 后端

- **Python 3.10+**（Windows 可使用工程内置运行时，Linux/macOS 使用项目 `.venv`）
- **FastAPI** + **uvicorn** — Web 框架与 ASGI 服务器
- **OpenAI 兼容 API 客户端** — 连接任意 OpenAI 兼容 LLM
- **SSE (Server-Sent Events)** — 实时事件流推送
- **MCP Python SDK (v1.28)** — Model Context Protocol 扩展
- **psutil** — CPU/内存压力监测
- **python-dotenv** — 环境变量管理
- **loguru** — 结构化日志

### 前端

- **Vite 6** — 构建工具（Mermaid 预构建为本地 vendor，构建耗时约 2s）
- **原生 JavaScript ES Module** — 无框架依赖
- **原生 CSS** — 自研样式系统（深色/紫色/浅色主题）

### 主要依赖

| 分类 | 依赖 |
|------|------|
| LLM 交互 | `openai`, `tiktoken`, `tokenizers` |
| 文档处理 | `pdfplumber`, `pymupdf`, `pypdf`, `openpyxl`, `markitdown[pptx]` |
| 网络工具 | `aiohttp`, `httpx`, `ddgs` (DuckDuckGo Search) |
| 数据分析 | `pandas`, `matplotlib`, `pillow` |
| 系统监控 | `psutil` |
| 可观测性 | `prometheus-client`, `sentry-sdk` |

完整依赖列表见 [app/requirements.txt](app/requirements.txt)。

---

## 目录结构

```
SugarAgent/
├── app/                          # Python 后端核心
│   ├── main.py                   # FastAPI/uvicorn 启动入口
│   ├── webui.py                  # HTTP/SSE 路由层（含后台会话恢复与审批分析）
│   ├── agent.py                  # Agent 轻量对外入口
│   ├── agent_harness.py          # Agent 调度与持久化核心
│   ├── agent_loop.py             # ReAct 执行循环（流式合并、Goal Judge、CPU 策略）
│   ├── agent_tools.py            # 内置工具层（ls 文本行数统计、Goal 工具等）
│   ├── agent_subagent.py         # 子 Agent 编排层（运行中模型切换）
│   ├── agent_memory.py           # 上下文压缩策略
│   ├── agent_mcp.py              # MCP 扩展层（专用后台事件循环）
│   ├── agent_openai.py           # OpenAI 兼容适配层（首 token 竞速重试）
│   ├── agent_tokenizer.py        # Token 估算器（工具 Schema 感知）
│   ├── agent_goal.py             # 持久 Goal 生命周期
│   ├── agent_goal_judge.py       # Goal 完成独立裁决（Judge）
│   ├── cpu_pressure.py           # 进程级 CPU 压力监测（自适应降级）
│   ├── runtime_observability.py  # Runtime V2 可观测性（防抖写盘）
│   ├── execution_metrics.py      # 执行指标看板（防抖写盘）
│   ├── runtime_power.py          # 系统挂起/恢复监测
│   ├── agent_messages.py         # 消息类型定义
│   ├── session_lifecycle.py      # 会话生命周期管理
│   ├── session_event_bus.py      # 会话事件发布/订阅
│   ├── model_profiles.py         # 模型配置管理
│   ├── security/                 # 安全策略：权限、审批、egress 出口控制
│   │   ├── policy.py             # 权限模式与能力策略
│   │   ├── reviewer.py           # 审查模型（替我分析/替我审批）
│   │   ├── egress_guard.py       # 网络出口守卫
│   │   ├── shell_analysis.py     # Shell 命令出口意图分析
│   │   └── runtime.py / store.py # 安全状态持久化
│   ├── human_interaction/        # 人工交互（提问/审批）服务
│   ├── agent_team/               # Agent 团队调度
│   ├── plugins/                  # 插件运行时
│   ├── native/                   # egress 原生助手（C#/Python 源码）
│   ├── prompt.md                 # Agent System Prompt 模板
│   ├── tray_launcher.py          # Windows 系统托盘启动器
│   ├── desktop_notify.py         # Windows 桌面通知（Toast）
│   ├── notify_ui_closed.ps1      # UI 关闭通知助手
│   ├── platform_tray*.py         # Ubuntu/macOS 原生托盘与菜单栏适配
│   ├── agentctl.py               # Linux/macOS 统一运维入口
│   ├── tool_approval_gate.py     # 工具审批机制
│   ├── ssl_bypass.py             # SSL 证书绕过
│   ├── .env                      # 环境变量配置
│   ├── requirements.txt          # Python 依赖
│   ├── templates/                # 后端 HTML 模板与 Vite 构建产物
│   │   ├── first_time_config.html  # 首次配置向导
│   │   ├── advance_config.html     # 高级环境变量配置（安全与权限页签）
│   │   ├── mcp_config.html         # MCP 配置页面
│   │   └── dist/                   # Vite 生产构建输出
│   └── tools/                    # 工具辅助资源（tokenizer 等）
├── frontend/                     # Vite 前端源码
│   ├── index.html                # 页面 Shell
│   ├── vite.config.js            # Vite 配置（Mermaid vendor 预构建）
│   ├── package.json              # npm 依赖与脚本
│   └── src/
│       ├── main.js               # 前端入口
│       ├── shell-body.html       # 主体 HTML 片段
│       ├── app/
│       │   ├── index.js          # UI 模块初始化引导
│       │   ├── config.js         # 运行时配置读取
│       │   └── modules/          # 功能模块
│       │       ├── message-rendering.js      # 消息与执行轨迹渲染（媒体渲染）
│       │       ├── workspace-media.js        # 工作区 GIF/图片/音视频渲染
│       │       ├── sse-handling.js           # SSE 流处理与追问队列
│       │       ├── session-management.js     # 会话管理（三点菜单/导出）
│       │       ├── input-actions.js          # 输入框统一发送逻辑
│       │       ├── human-interactions.js     # 提问/审批卡片（egress 摘要）
│       │       ├── permissions.js            # 权限模式与降级提示
│       │       ├── subagent.js               # 子 Agent 面板（模型切换）
│       │       ├── toc-todo.js               # 目录与 Todo 面板
│       │       ├── settings.js               # 设置面板（MCP/Plugin 分类折叠）
│       │       ├── layout-panels.js          # 布局管理（防重叠）
│       │       ├── shared-state-and-dialogs.js # 全局状态与弹窗
│       │       ├── model-profiles.js         # 模型配置 UI
│       │       └── event-dispatch.js         # 事件分发协调
│       ├── styles/               # CSS 样式（深色/紫色/浅色主题）
│       └── vendor/               # 第三方脚本（Mermaid 预构建）
├── plugins/                      # 实际加载的插件（如 repo-engineering 示例）
├── examples/plugins/             # 插件开发示例（hello-python）
├── python/                       # 内置 Python 3.10 运行时（Windows）
├── workspace/                    # 默认工作区（会话数据、技能、用户产物）
│   ├── sessions/                 # 会话持久化数据
│   └── skills/                   # 技能目录
├── scripts/                      # 工程辅助脚本
│   ├── check_frontend_dist_sync.py     # 前端构建产物同步检查
│   ├── check_frontend_commit_policy.py # 前端提交策略检查
│   ├── install_git_hooks.py            # Git Hooks 安装
│   ├── install_unix.sh                  # Ubuntu/macOS 源码安装
│   ├── build_egress_helper_windows.ps1 # Windows egress 助手构建
│   ├── verify_egress_helper.py         # egress 助手协议验证
│   ├── agentctl                         # Unix 生命周期命令包装器
│   └── ...                              # 审计/基准/修复脚本
├── tests/                        # 测试套件（84+ Python 测试 + tests/js 运行时测试）
├── docs/                         # 设计文档与 CHANGELOG
├── logs/                         # 运行日志
├── RUN.bat                       # Windows 一键启动脚本
├── RUN.sh                        # Ubuntu/macOS 一键启动脚本
├── SPEC.md                       # 工程规格说明
└── .gitignore                    # Git 忽略规则
```

> 说明：`skill_states.json` 为运行时状态文件（技能启停），仅存在于本地，不纳入版本库；克隆后所有技能默认启用。

---

## 快速开始

### 环境要求

- **操作系统**: Windows 10/11、Ubuntu 22.04/24.04 x86_64、macOS 13+
- **Python**: 3.10+（Windows 工程内置运行时，Linux/macOS 使用 `.venv`）
- **Node.js**: 16+（仅前端开发需要）
- **Git**: 版本管理

### 1. 克隆仓库

```bash
git clone <repository-url>
cd "MyAgent Developer"
```

### 2. 配置

首次启动后通过浏览器向导创建 model profile。模型名称、API 地址、密钥、上下文窗口和推理参数全部保存在 `model_profiles.json`，运行时不再从 `.env` 读取。

升级旧版本时，如果 `app/.env` 中存在一套完整的旧模型配置，启动过程会自动将其一次性注册为 model profile。已有等价 profile 时直接复用，不会重复创建；导入后的 profile 可独立编辑，后续启动不会再被 `.env` 覆盖。

`.env` 仅保留模型之外的运行配置，例如：

| 变量 | 说明 |
|------|------|
| `WORK_DIR` | 工作区目录 |
| `WEB_SEARCH_PROVIDER` | 搜索引擎 provider |

完整配置项见下文 [配置说明](#配置说明)。

### 3. 安装依赖

```bash
# 使用内置 Python
python/python.exe -m pip install -r app/requirements.txt

# 或使用系统 Python
pip install -r app/requirements.txt
```

### 4. 启动服务

```bash
# Windows 一键启动（推荐）
RUN.bat

# Ubuntu/macOS 首次安装
bash scripts/install_unix.sh --mode desktop

# Ubuntu/macOS 启动
bash RUN.sh

# 或手动启动
python app/main.py
```

服务启动后自动打开浏览器，访问地址：**http://127.0.0.1:8192/**

> 首次启动时，若未检测到配置文件，系统会自动跳转到 `/setup` 引导完成初始配置。

Ubuntu Server 使用 `bash scripts/install_unix.sh --mode server` 安装，并通过
SSH 隧道访问 WebUI；macOS 使用 LaunchAgent 和原生菜单栏。完整安装、运维、
卸载与故障排查见 [Linux 与 macOS 安装和运维](docs/cross_platform.md)。

### 5. 常驻图标启动器（可选）

`RUN.bat` 默认通过 `tray_launcher.py` 启动，提供系统常驻图标（Windows 任务栏右下角 / macOS 菜单栏 / Ubuntu 顶部栏）集成：

- 🖱️ 右键常驻图标：打开 WebUI / 高级设置 / MCP 配置 / 查看日志 / 重启 / 更新 / 退出
- 🔄 “重启 Agent”会停止并重新拉起后端；“更新 Agent”会执行安全的 Git 快进更新，按需同步 Python 依赖，然后自动重启
- 🛡️ 更新不会强制覆盖本地修改；更新冲突或失败时会保留现场、恢复启动 Agent，并将详情写入 `logs/agent_update.log`
- 📋 终端窗口自动隐藏，减少桌面干扰
- 🔒 单实例运行，重复启动自动打开已有实例

Ubuntu Desktop 使用 Ayatana AppIndicator，macOS 使用原生菜单栏；两者由
`platform_tray.py` 调用 systemd/launchd 生命周期后端，菜单能力与 Windows
保持一致。Headless Ubuntu 不启动常驻图标，改用 `scripts/agentctl` 管理服务。

---

## 前端开发

### 开发模式

```bash
cd frontend
npm install
npm run dev
```

Vite 开发服务器运行在 `http://localhost:5173/`，自动代理 `/sessions` 和 `/api` 到后端 `http://127.0.0.1:8000`。

### 构建生产版本

```bash
npm run build
```

构建产物输出到 `app/templates/dist/`，后端会优先服务此目录中的静态文件。Mermaid 以预构建 vendor 形式内联，构建可在数秒内完成且支持离线使用。

### 工程检查脚本

```bash
# 检查前端构建产物是否与源码同步
npm run verify:dist

# 检查前端提交策略
npm run verify:commit

# 安装 Git Hooks
npm run install:hooks
```

---

## 架构概览

### 后端核心模块

```
┌─────────────────────────────────────────────────────┐
│                    webui.py                          │
│         HTTP / SSE 路由层 · 后台恢复 · 审批分析       │
└──────────┬──────────────────────────┬───────────────┘
           │                          │
     ┌─────▼──────┐           ┌──────▼──────┐
     │ agent.py   │           │ session_     │
     │ 对外入口    │           │ lifecycle.py │
     └─────┬──────┘           │ event_bus.py │
           │                  └──────────────┘
     ┌─────▼──────────────────────────────────┐
     │         agent_harness.py                │
     │    调度核心 · 持久化 · 消息管理          │
     └─────┬──────┬──────┬──────┬─────────────┘
           │      │      │      │
    ┌──────▼─┐ ┌──▼───┐ ┌▼────┐ ┌▼──────────┐
    │agent_  │ │agent_│ │agent│ │agent_      │
    │loop.py │ │tools │ │_mcp │ │memory.py   │
    │ReAct   │ │内置   │ │MCP  │ │上下文压缩  │
    │执行循环 │ │工具层 │ │扩展 │ │策略层      │
    └────────┘ └──────┘ └─────┘ └────────────┘
        │            │           │
   ┌────▼────┐  ┌────▼────┐  ┌───▼─────────┐
   │cpu_     │  │agent_   │  │agent_        │
   │pressure │  │goal.py  │  │subagent.py   │
   │CPU自适应 │  │Goal+    │  │子Agent编排    │
   │         │  │Judge    │  │(模型切换)     │
   └─────────┘  └─────────┘  └─────────────┘
        ┌──────────────────────────────┐
        │ security/ (权限/审批/egress)  │
        │ human_interaction/ (交互)    │
        └──────────────────────────────┘
```

### 会话生命周期

1. **创建会话** — 生成唯一 session ID，建立持久化目录
2. **用户输入** — 通过 `/chat` 提交消息，启动 ReAct 循环
3. **ReAct 循环** — LLM 推理 → 工具调用 → 结果反馈 → 继续推理（首 token 竞速、CPU 自适应、流式合并）
4. **SSE 推送** — 实时向前端推送 LLM delta、工具状态、进度提示等事件
5. **上下文压缩** — 达到阈值时自动压缩历史，保留关键上下文
6. **会话持久化** — 全部状态落盘，支持页面刷新后恢复
7. **后台恢复** — 中断的会话由服务端后台自动恢复（pending 问题/审批存在时不恢复）

### 持久化结构

每个会话目录包含：

| 文件 | 说明 |
|------|------|
| `metadata.json` | 会话元数据（名称、归档、置顶、模型切换历史） |
| `ui_events.json` | 前端可重放事件流 |
| `work_messages.json` | Agent 工作消息 |
| `llm_history.json` | 发送给模型的上下文历史 |
| `dialogue_history.json` | 面向对话显示/压缩的历史 |
| `key_context.md` | 压缩后的关键上下文摘要 |
| `todo_plan.md` | Todo 计划 |

---

## 内置工具一览

| 工具 | 说明 |
|------|------|
| `read_file` | 读取文件内容（支持行范围） |
| `write_file` | 写入文件（支持临时文件标记） |
| `edit_file` | 查找替换编辑（支持正则） |
| `delete_file` | 软删除到回收站 |
| `ls` | 列出目录内容（仅文本/源码文件统计行数，压缩包显示 `—`，单文件上限 5 MiB） |
| `glob` | 文件名模式匹配搜索 |
| `grep` | 文件内容正则搜索 |
| `run_shell` | 执行 Shell 命令（超时、截断、路径限制、egress 出口控制） |
| `web_search` | 网络搜索 |
| `web_fetch` | 抓取网页文本（SSRF 防护） |
| `web_download` | 下载文件（大小限制） |
| `activate_skill` | 加载技能说明 |
| `update_todo` | 更新 Todo 计划 |
| `context_manage` | 上下文压缩与编辑 |
| `create_goal` / `get_goal` / `update_goal` | 持久 Goal 的创建、查询与结束 |
| `task` | 启动/管理子 Agent（引用式 fork、best-of-n、运行中 steer、运行中模型切换、托管 worktree） |

> `list_dir` 已合并为 `ls`；执行层保留 `list_dir` 兼容映射。

---

## 插件生态

MyAgent Plugin API v1 支持在独立持久 Worker 中注册 Python/Node Tool、Hook、
Slash Command 和生命周期回调，也可在同一插件包中携带 Skill、MCP、Agent、Prompt
等声明式资源。扩展管理页 `/setup/extensions` 支持从本地目录、压缩包或 Git URL
安装/更新插件、准备私有 Python/Node 依赖、启停、热重载和可恢复卸载。

仓库自带两个插件参考：

- `examples/plugins/hello-python` — **可执行插件示例**：展示用 `myagent_plugin_sdk` 编写 Python 插件（生命周期钩子 + 工具注册），仅供学习，不会被实际加载
- `plugins/repo-engineering` — **声明式 Skill 插件示例**：Codex 格式插件，携带仓库工程化工作流 Skill（代码审查/测试/changelog/发布检查），启动时会被真实发现

当前还提供 Claude Code、Codex、Hermes Agent 与 OpenCode 的兼容发现/适配诊断。
原生 SDK、Manifest Schema、effect/worktree 契约和兼容边界见
[Plugin API v1](docs/plugin_api_v1.md) 与 [Hooks / Plugins](docs/hooks_plugins.md)。

---

## 配置说明

### LLM 配置

仅通过 `model_profiles.json` 配置模型，运行时可切换并按优先级故障转移。每个 profile 包含：

- 模型名称与类型
- API Base URL 与 API Key
- 上下文窗口与输出限制
- 思考模式、reasoning effort、temperature 和额外请求体
- 多模态输入模式：`auto`、`enabled` 或 `disabled`；接口拒绝多模态后自动持久化为仅文本
- 媒体序列化只由目标 profile 的有效输入模态决定：图片模型收到 `image_url` content，纯文本模型只收到可恢复的文本引用与多模态委派指引（主 Agent 与子 Agent 共用规则）

首页是否进入配置向导，只取决于自动导入完成后是否存在可用的 model profile；`.env` 中的旧模型字段只用于一次性迁移，不参与运行时回退。

### MCP 配置

参考 `app/mcp_servers.json.example`，支持三种 transport：

```json
{
  "mcpServers": {
    "example-stdio": {
      "transport": "stdio",
      "command": "node",
      "args": ["mcp-server.js"]
    },
    "example-sse": {
      "transport": "sse",
      "url": "http://localhost:3001/sse"
    },
    "example-http": {
      "transport": "streamable-http",
      "url": "http://localhost:3002/mcp",
      "headers": {
        "Authorization": "Bearer ${EXAMPLE_MCP_TOKEN}"
      }
    }
  }
}
```

请求头中的 `${ENV_VAR}` 会在建立连接时从进程环境解析，配置文件中无需保存密钥；缺失变量只会阻止对应服务器启动，并在错误中报告变量名。

### Web 搜索配置

| 变量 | 说明 |
|------|------|
| `WEB_SEARCH_PROVIDER` | 搜索引擎（`duckduckgo` / `tavily` / `brave` / `searxng`） |
| `TAVILY_API_KEY` | Tavily 搜索 API Key |
| `BRAVE_API_KEY` | Brave Search API Key |

### 稳定性与性能配置

| 变量 | 默认 | 说明 |
|------|------|------|
| `OPENAI_HTTP_TIMEOUT` | `300` | LLM 请求超时（秒） |
| `OPENAI_MAX_RETRIES` | `4` | LLM 请求最大重试次数 |
| `OPENAI_FIRST_TOKEN_HEDGE_TIMEOUT_SEC` | `30` | 首 token 竞速阈值；设为 `0` 关闭 |
| `OPENAI_FIRST_TOKEN_HEDGE_MAX_RETRIES` | `2` | 每次模型调用最多触发的并行竞速次数 |
| `CPU_PRESSURE_ENABLED` | `true` | CPU 压力监测总开关 |
| `CPU_PRESSURE_HIGH_PERCENT` | `85` | 进入"繁忙"的 CPU 阈值（%） |
| `CPU_PRESSURE_SEVERE_PERCENT` | `90` | 进入"严重"（切换非流式）的阈值 |
| `CPU_PRESSURE_RECOVERY_PERCENT` | `65` | 恢复阈值（低于此值并稳定 120s 才恢复） |
| `CPU_PRESSURE_SAMPLE_SECONDS` | `10` | 采样间隔（秒） |
| `CPU_PRESSURE_TOOL_CONCURRENCY` | `2` | 严重压力下本地只读工具并发上限 |
| `LLM_STREAM_COALESCE_MS` | `12` | 流式文本增量合并窗口（首 token 立即推送） |
| `EXECUTION_METRICS_FLUSH_DELAY_MS` | `200` | 执行指标防抖写盘延迟 |
| `RUNTIME_OBSERVABILITY_FLUSH_DELAY_MS` | `200` | 可观测性防抖写盘延迟 |
| `LLM_FULL_CALL_TRACE` | `0` | 调试用完整请求/响应日志 |

### 安全与恢复配置

| 变量 | 默认 | 说明 |
|------|------|------|
| `SECURITY_ENABLED` | `1` | 安全审批总开关（`0` 关闭） |
| `EXTENSION_REGISTRATION_APPROVAL_ENABLED` | `0` | 插件/MCP 注册人工确认（`1` 开启） |
| `EGRESS_HELPER_ENABLED` | `1` | 系统级网络出口助手（`0` 关闭，仅保留应用层审批） |
| `SUGAR_AGENT_EGRESS_HELPER` | 自动发现 | 指定 egress helper 路径 |
| `REACT_RECOVERY_RETRY_SECONDS` | `30` | 后台会话恢复失败重试间隔 |
| `MYAGENT_UI_CLOSED_NOTIFY` | `1` | UI 关闭时发送桌面通知（测试建议设 `0`） |

### 其他配置

| 变量 | 说明 |
|------|------|
| `ASK_USER_ENABLED` | 提问工具开关（默认开） |
| `GOAL_ENABLED` | 持久 Goal 开关（默认开，`0` 禁用） |
| `MYAGENT_FRONTEND_VERSION` | 前端版本标识（`v1`） |
| `LS_INCLUDE_LINE_COUNTS` | `ls` 是否统计文本行数（默认开） |
| `LS_LINE_COUNT_MAX_BYTES` | `ls` 单文件行数统计上限（默认 5 MiB） |

---

## 安全机制

- **文件系统隔离** — 工具默认限制在 `WORK_DIR` 内操作
- **Shell 命令过滤** — 识别危险命令，支持用户审批
- **SSRF 防护** — `web_fetch` / `web_download` 阻止访问内网和保留地址
- **敏感信息脱敏** — 日志和工具输出中的 API Key 自动脱敏
- **工具审批** — 高风险工具调用可通过 Web UI 进行人工审批；"替我分析"给出建议不代行审批
- **工作区外审批** — 写入/删除/Shell 越出工作区时逐次审批，可授权持续放行并随时撤销
- **网络出口控制** — 可选的系统级 egress helper 强制执行策略的网络决策（strong/partial/degraded）
- **注册确认** — 可执行插件与 MCP 首次注册/摘要变化可按配置要求人工确认
- **恢复门禁** — 存在 pending 提问/审批时禁止自动恢复、Goal 续跑与删除会话
- **软删除** — 文件删除先进入 `.trash` 回收站，可恢复

---

## 工程规格

完整的工程规格说明（API 列表、SSE 事件定义、验收标准、变更约束等）见：

📄 **[SPEC.md](SPEC.md)**

---

## 更新日志

- [变更说明 2026-08](docs/CHANGELOG-2026-08-15.md)
- [变更说明 2026-08-10](docs/CHANGELOG-2026-08-10.md)
- [变更说明 2026-08-11](docs/CHANGELOG-2026-08-11.md)
- [变更说明 2026-08-12](docs/CHANGELOG-2026-08-12.md)
- [变更说明 2026-08-13](docs/CHANGELOG-2026-08-13.md)
- [变更说明 2026-08-14](docs/CHANGELOG-2026-08-14.md)

---

## 反馈与支持

如果你在使用中遇到问题，欢迎直接到 GitHub 提交 Issue 反馈。

# 持久 Goal 模式 / Durable Goal mode

MyAgent 每个会话支持一个持久 Goal。模型通过 `create_goal`、`get_goal` 和 `update_goal` 创建、查询及结束
Goal；服务端调度器会在本轮结束后继续执行 active Goal，不依赖浏览器保持打开。Goal 状态、每次模型调用的
Token 用量、活动时长、续跑次数和最终状态都会写入 Runtime V2 事件日志及快照。Web UI 提供暂停、恢复、
追加预算并恢复以及取消操作。Token 预算耗尽后必须追加正数预算才能恢复；连续运行失败默认达到 3 次会自动
暂停，以避免无限重试。

MyAgent supports one durable Goal per session. The model creates, inspects, and finishes it with `create_goal`,
`get_goal`, and `update_goal`. A server-side scheduler continues active Goals after a run ends, without requiring
an open browser. Goal state, per-call token usage, active time, continuation count, and terminal status are stored
in the Runtime V2 event log and snapshot. The web UI provides pause, resume, add-budget-and-resume, and cancel
controls. An exhausted token budget requires a positive budget increase before resuming. By default, three
consecutive run failures pause the Goal to prevent an infinite retry loop.

Goal 使用固定的双阶段完成流程。执行模型自主推进任务，仅在认为整个目标已经达成时调用
`update_goal(status=completed)`；该调用不会直接完成 Goal，而是发起一次无工具的独立 Judge 裁决。
Judge 返回 `continue` 时，反馈会注入下一轮供执行模型修正；返回 `done` 时，Goal 才进入人工审核。
Judge 调用本身的 Token 计入 Goal 预算。单次 Judge 失败会继续执行，连续解析失败 3 次或调用失败 5 次
则暂停 Goal。Judge 证据包含**完整的 Goal 生命周期对话**（不裁剪）与近期辅助证据，并在申请完成的当轮
立即执行（不再延后一轮）。

Goal uses one fixed two-stage completion flow. The worker advances the task autonomously and calls
`update_goal(status=completed)` only when it believes the entire objective is achieved. That call requests an
independent, tool-free Judge verdict instead of completing the Goal directly. `continue` feeds the Judge's
feedback into the next worker run; `done` moves the Goal to human review. Judge usage counts toward the Goal
budget. A single Judge failure fails open, while repeated parse or transport failures pause the Goal. The Judge
evidence includes the full Goal lifecycle dialogue (unclipped) plus recent auxiliary evidence, and runs in the
same round the completion is requested.

完成后的 Goal 会保留在侧栏并显示“已完成”，右侧操作替换为“结果审核”。审核弹窗允许修改 Goal 描述和
Judge 结论：“保存修改”保留弹窗与待审核状态；“继续 Goal 任务”重新激活 Goal，并把人工意见注入下一轮；
“审核通过”确认目标达成、保留审计事件并从侧栏移除 Goal。

After completion, the Goal remains visible with a Result Review action. The review dialog can edit both the
objective and Judge result. Save keeps the review pending, Continue reactivates the Goal and injects the human
feedback into the next run, and Approve finalizes the review while removing the card without deleting audit
events.

`GOAL_ENABLED=0`（也接受 `false`、`no` 或 `off`）会禁用整个功能；默认启用。禁用后模型工具列表不会
暴露 Goal 工具，服务端不会自动续跑，Goal 控制接口也会拒绝变更。`GOAL_RUNNER_POLL_SECONDS` 控制服务端
扫描间隔（默认 `2` 秒，最小 `0.5` 秒），`GOAL_MAX_CONSECUTIVE_FAILURES` 控制连续失败暂停阈值（默认 `3`）。
Judge 可通过 `GOAL_JUDGE_MAX_OUTPUT_TOKENS`、`GOAL_JUDGE_EVIDENCE_MAX_CHARS`、
`GOAL_JUDGE_MAX_PARSE_FAILURES` 和 `GOAL_JUDGE_MAX_TRANSPORT_FAILURES` 调整。
修改这些环境变量后需要重启 MyAgent。

Set `GOAL_ENABLED=0` (also accepts `false`, `no`, or `off`) to disable the entire feature; it is enabled by
default. When disabled, Goal tools are omitted, server-side continuation stops, and Goal control mutations are
rejected. `GOAL_RUNNER_POLL_SECONDS` controls the server scan interval (default `2`, minimum `0.5` seconds), and
`GOAL_MAX_CONSECUTIVE_FAILURES` controls the automatic pause threshold (default `3`). Restart MyAgent after
changing these environment variables.
