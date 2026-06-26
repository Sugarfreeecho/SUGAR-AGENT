# SugarAgent

> **Self-Upgrading General Agent Runtime**
>
> 一款本地运行的可自优化代码通用智能平台。在本机完成代码开发、文件处理、联网检索、研究分析、文档生成和多步骤自动化任务，同时保留可审计的会话记录与运行日志。

---

## 项目概览

SugarAgent 是一个**本地运行**的 AI Agent 开发与使用平台。它通过浏览器 Web UI 提供会话式交互，由 Python FastAPI 后端驱动 **ReAct 推理循环**、**工具调用**、**子 Agent 编排**、**上下文压缩**、**MCP 扩展**和**会话持久化**。

系统支持连接 OpenAI 兼容接口的任意 LLM 后端（DeepSeek、Mimo 等），无需依赖外部云服务即可在本地完成复杂的多步骤任务。

---

## 核心能力

| 能力 | 说明 |
|------|------|
| 🧠 **ReAct 推理循环** | 基于 ReAct 模式的 LLM 调度，支持工具调用链、流式输出和中断恢复 |
| 🔧 **内置工具系统** | 文件读写编辑、目录搜索、Shell 命令、Web 搜索/抓取/下载、上下文管理等 20+ 工具 |
| 🤖 **子 Agent 编排** | 通过 `task` 工具将复杂任务拆分为隔离子 Agent，支持 best-of-n 多路并行策略 |
| 🗜️ **上下文压缩** | 渐进式压缩、微压缩、摘要合并和应急裁剪，保障长会话稳定运行 |
| 🔌 **MCP 扩展** | 支持 stdio / SSE / Streamable HTTP 三种 MCP transport，可热重载配置 |
| 💾 **会话持久化** | 完整会话状态落盘（元数据、事件流、LLM 历史、对话历史、Todo 计划） |
| 🛡️ **安全边界** | 工作区路径限制、Shell 危险命令拦截、SSRF 防护、敏感信息脱敏、工具审批机制 |
| 🖥️ **系统托盘** | Windows 原生托盘集成，支持一键打开 WebUI、查看日志、退出 Agent |

---

## 技术栈

### 后端

- **Python 3.10**（工程内置运行时，无需系统安装）
- **FastAPI** + **uvicorn** — Web 框架与 ASGI 服务器
- **OpenAI 兼容 API 客户端** — 连接任意 OpenAI 兼容 LLM
- **SSE (Server-Sent Events)** — 实时事件流推送
- **MCP Python SDK (v1.6)** — Model Context Protocol 扩展
- **python-dotenv** — 环境变量管理
- **loguru** — 结构化日志

### 前端

- **Vite 6** — 构建工具
- **原生 JavaScript ES Module** — 无框架依赖
- **原生 CSS** — 自研样式系统

### 主要依赖

| 分类 | 依赖 |
|------|------|
| LLM 交互 | `openai`, `tiktoken`, `tokenizers` |
| 文档处理 | `pdfplumber`, `pymupdf`, `pypdf`, `openpyxl`, `markitdown[pptx]` |
| 网络工具 | `aiohttp`, `httpx`, `ddgs` (DuckDuckGo Search) |
| 数据分析 | `pandas`, `matplotlib`, `pillow` |
| 可观测性 | `prometheus-client`, `sentry-sdk` |

完整依赖列表见 [app/requirements.txt](app/requirements.txt)。

---

## 目录结构

```
SugarAgent/
├── app/                          # Python 后端核心
│   ├── main.py                   # FastAPI/uvicorn 启动入口
│   ├── webui.py                  # HTTP/SSE 路由层（~3100 行）
│   ├── agent.py                  # Agent 轻量对外入口
│   ├── agent_harness.py          # Agent 调度与持久化核心（~5200 行）
│   ├── agent_loop.py             # ReAct 执行循环（~3000 行）
│   ├── agent_tools.py            # 内置工具层（~3300 行）
│   ├── agent_subagent.py         # 子 Agent 编排层（~1280 行）
│   ├── agent_memory.py           # 上下文压缩策略（~1460 行）
│   ├── agent_mcp.py              # MCP 扩展层
│   ├── agent_openai.py           # OpenAI 兼容适配层
│   ├── agent_tokenizer.py        # Token 估算器
│   ├── agent_messages.py         # 消息类型定义
│   ├── session_lifecycle.py      # 会话生命周期管理
│   ├── session_event_bus.py      # 会话事件发布/订阅
│   ├── model_profiles.py         # 模型配置管理
│   ├── prompt.md                 # Agent System Prompt 模板
│   ├── tray_launcher.py          # Windows 系统托盘启动器
│   ├── tool_approval_gate.py     # 工具审批机制
│   ├── path_picker_util.py       # 本机路径选择器
│   ├── ssl_bypass.py             # SSL 证书绕过
│   ├── .env                      # 环境变量配置
│   ├── requirements.txt          # Python 依赖
│   ├── templates/                # 后端 HTML 模板与 Vite 构建产物
│   │   ├── frist_time_config.html  # 首次配置向导
│   │   ├── advance_config.html     # 高级环境变量配置
│   │   ├── mcp_config.html         # MCP 配置页面
│   │   └── dist/                   # Vite 生产构建输出
│   ├── tools/                    # 工具辅助资源（tokenizer 等）
│   └── assets/                   # 应用图标与 Logo
├── frontend/                     # Vite 前端源码
│   ├── index.html                # 页面 Shell
│   ├── vite.config.js            # Vite 配置（代理/构建输出）
│   ├── package.json              # npm 依赖与脚本
│   └── src/
│       ├── main.js               # 前端入口
│       ├── shell-body.html       # 主体 HTML 片段
│       ├── app/
│       │   ├── index.js          # UI 模块初始化引导
│       │   ├── config.js         # 运行时配置读取
│       │   └── modules/          # 功能模块
│       │       ├── message-rendering.js      # 消息渲染（~3100 行）
│       │       ├── sse-handling.js           # SSE 流处理（~1170 行）
│       │       ├── session-management.js     # 会话管理
│       │       ├── session-scroll-history.js # 历史分页与滚动
│       │       ├── subagent.js               # 子 Agent 面板
│       │       ├── toc-todo.js               # 目录与 Todo 面板
│       │       ├── settings.js               # 设置面板
│       │       ├── layout-panels.js          # 布局管理
│       │       ├── shared-state-and-dialogs.js # 全局状态与弹窗
│       │       ├── model-profiles.js         # 模型配置 UI
│       │       └── event-dispatch.js         # 事件分发协调
│       ├── styles/               # CSS 样式
│       └── vendor/               # 第三方脚本
├── python/                       # 内置 Python 3.10 运行时（Windows）
├── workspace/                    # 默认工作区（会话数据、技能、用户产物）
│   ├── sessions/                 # 会话持久化数据
│   └── skills/                   # 技能目录
├── scripts/                      # 工程辅助脚本
│   ├── audit_runtime_versions.py       # 运行时版本审计
│   ├── benchmark_runtime_versions.py   # 运行时性能基准
│   ├── check_frontend_dist_sync.py     # 前端构建产物同步检查
│   ├── check_frontend_commit_policy.py # 前端提交策略检查
│   ├── install_git_hooks.py            # Git Hooks 安装
│   └── compare_runtime_v2_session.py   # Runtime V2 会话对比
├── tests/                        # 测试套件
│   ├── test_model_profiles.py    # 模型配置测试
│   └── runtime_v2/               # Runtime V2 测试
├── docs/                         # 设计文档
│   ├── runtime_v2_design.md            # Runtime V2 架构设计
│   ├── runtime_v2_closure_status.md    # Runtime V2 状态闭包
│   └── runtime_v2_sidecar_invariants.md # Runtime V2 Sidecar 不变量
├── logs/                         # 运行日志
├── RUN.bat                       # Windows 一键启动脚本
├── SPEC.md                       # 工程规格说明（~625 行）
├── model_profiles.json           # 预置模型配置
└── .gitignore                    # Git 忽略规则
```

---

## 快速开始

### 环境要求

- **操作系统**: Windows 10/11
- **Python**: 3.10+（工程内置运行时，或系统已安装）
- **Node.js**: 16+（仅前端开发需要）
- **Git**: 版本管理

### 1. 克隆仓库

```bash
git clone <repository-url>
cd "MyAgent Developer"
```

### 2. 配置环境变量

复制并编辑配置文件，或在首次启动后通过浏览器向导配置。

关键配置项：

| 变量 | 说明 |
|------|------|
| `EXECUTOR_LLM` | 模型名称（如 `deepseek-v4-pro`） |
| `OPENAI_BASE_URL` | LLM API 地址 |
| `OPENAI_API_KEY` | API 密钥 |
| `CONTEXT_WINDOW` | 上下文窗口大小 |
| `MAX_OUTPUT_TOKENS` | 最大输出 Token 数 |
| `WORK_DIR` | 工作区目录 |
| `WEB_SEARCH_PROVIDER` | 搜索引擎 provider |

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

# 或手动启动
python app/main.py
```

服务启动后自动打开浏览器，访问地址：**http://127.0.0.1:8192/**

> 首次启动时，若未检测到配置文件，系统会自动跳转到 `/setup` 引导完成初始配置。

### 5. 托盘启动器（可选）

`RUN.bat` 默认通过 `tray_launcher.py` 启动，提供 Windows 系统托盘集成：

- 🖱️ 右键托盘图标：打开 WebUI / 高级设置 / MCP 配置 / 查看日志 / 退出
- 📋 终端窗口自动隐藏，减少桌面干扰
- 🔒 单实例运行，重复启动自动打开已有实例

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

构建产物输出到 `app/templates/dist/`，后端会优先服务此目录中的静态文件。

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
│              HTTP / SSE 路由层                        │
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
                              ┌──────────────┐
                              │agent_         │
                              │subagent.py    │
                              │子Agent编排层   │
                              └──────────────┘
```

### 会话生命周期

1. **创建会话** — 生成唯一 session ID，建立持久化目录
2. **用户输入** — 通过 `/chat` 提交消息，启动 ReAct 循环
3. **ReAct 循环** — LLM 推理 → 工具调用 → 结果反馈 → 继续推理
4. **SSE 推送** — 实时向前端推送 LLM delta、工具状态、进度提示等事件
5. **上下文压缩** — 达到阈值时自动压缩历史，保留关键上下文
6. **会话持久化** — 全部状态落盘，支持页面刷新后恢复

### 持久化结构

每个会话目录包含：

| 文件 | 说明 |
|------|------|
| `metadata.json` | 会话元数据（名称、归档、置顶状态） |
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
| `ls` / `list_dir` | 列出目录内容 |
| `glob` | 文件名模式匹配搜索 |
| `grep` | 文件内容正则搜索 |
| `run_shell` | 执行 Shell 命令（支持超时、截断、路径限制） |
| `web_search` | 网络搜索 |
| `web_fetch` | 抓取网页文本（SSRF 防护） |
| `web_download` | 下载文件（大小限制） |
| `activate_skill` | 加载技能说明 |
| `update_todo` | 更新 Todo 计划 |
| `context_manage` | 上下文压缩与编辑 |
| `task` | 启动子 Agent（支持 best-of-n 并行） |

---

## 配置说明

### LLM 配置

支持通过环境变量或 `model_profiles.json` 配置多个模型，运行时可切换：

- `EXECUTOR_LLM` / `EXECUTOR_LLM_TYPE` — 模型名称与类型
- `OPENAI_BASE_URL` / `OPENAI_API_KEY` — API 连接信息
- `CONTEXT_WINDOW` / `MAX_OUTPUT_TOKENS` — 上下文与输出限制
- `LLM_THINKING_MODE` / `LLM_REASONING_EFFORT` — 推理模式

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
      "url": "http://localhost:3002/mcp"
    }
  }
}
```

### Web 搜索配置

| 变量 | 说明 |
|------|------|
| `WEB_SEARCH_PROVIDER` | 搜索引擎（`duckduckgo` / `tavily` / `brave` / `searxng`） |
| `TAVILY_API_KEY` | Tavily 搜索 API Key |
| `BRAVE_API_KEY` | Brave Search API Key |

---

## 安全机制

- **文件系统隔离** — 工具默认限制在 `WORK_DIR` 内操作
- **Shell 命令过滤** — 识别危险命令，支持用户审批
- **SSRF 防护** — `web_fetch` / `web_download` 阻止访问内网和保留地址
- **敏感信息脱敏** — 日志和工具输出中的 API Key 自动脱敏
- **工具审批** — 高风险工具调用可通过 Web UI 进行人工审批
- **软删除** — 文件删除先进入 `.trash` 回收站，可恢复

---

## 工程规格

完整的工程规格说明（API 列表、SSE 事件定义、验收标准、变更约束等）见：

📄 **[SPEC.md](SPEC.md)**

---

## 更新日志

- [更新日志 2026年5月](更新日志%20202605.md)
- [更新日志 2026年6月](更新日志%20202606.md)

---

## 反馈与支持

如果你在使用中遇到问题，欢迎直接到 GitHub 提交 Issue 反馈。
