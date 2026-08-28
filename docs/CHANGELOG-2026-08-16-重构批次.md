# CHANGELOG — 2026-08-16/17（架构重构批次）

本批次是一次大规模架构重构（约 120 个文件）：LLM 传输层 provider 化、内置功能插件化、工具注册表拆分、Runtime V2 扩展。

## 一、LLM 传输层重构（新增 `app/llm/`）

- 执行器通过 provider adapter 访问模型，主循环只处理统一 `TransportEvent`，不再解析 OpenAI/Anthropic 线协议。
- Provider 注册表（`provider_registry.py`）与传输抽象（`transport.py`/`types.py`），`EXECUTOR_LLM_TYPE` 选择 provider。
- 新增 **OpenAI Responses API** 传输（`app/llm/responses/`）：capabilities 能力探测、items/state 会话条目、compact 压缩、budget/planner/metrics/tool_results。
- `agent_openai.py`/`agent_harness.py` 适配 `LLMRequestContext`/`LLMRequestPurpose`/`TransportEvent`。
- 文档：`docs/llm-transport.md`、`docs/codex_responses_transport_refactor_plan.md`。

## 二、插件系统扩展 + 内置功能插件化

- 插件运行时新增 `host.py`（宿主）、`settings.py`、`storage.py`、`ui.py`、`web.py`；新增 `plugin_host_services.py`（后台服务）、`plugin_web_gateway.py`（Web 网关）、前端 `plugin-ui-slots.js`（UI 插槽）。
- **8 个内置功能迁移为插件**（`plugins/`）：`agent-goal`（持久 Goal）、`agent-team`（团队）、`execution-dashboard`（执行看板，原 `dashboard.js`/`execution-dashboard.html` 删除）、`desktop-notifications`（桌面通知）、`feishu-transport`（飞书）、`game-arena`（游戏竞技场）、`session-todo`（会话待办）、`web-search-providers`（搜索 provider，`web_search` 改由启用中的 Search Provider 插件执行）。
- `myagent_plugin_sdk.py`、`plugin_api_v1.md`、schema 同步更新；计划文档 `plugin-system-and-game-arena-optimization-plan.md`。

## 三、工具注册表与执行策略拆分

- `tool_registry.py`：模型面 JSON 定义与执行实现分离的注册契约。
- `host_tool_registry.py`/`builtin_host_tools.py`：宿主工具注册。
- `tool_execution_policy.py`/`workspace_lease_policy.py`：执行策略与工作区租约。
- `search_provider_registry.py`：搜索 provider 注册表。

## 四、Runtime V2 扩展与前端平滑流

- `runtime_v2/extension_state.py`（扩展状态）、`legacy_compat.py`（旧兼容）、`agent_team/projection.py`、`session_todo_extension.py`；runtime_v2 各模块适配。
- 前端 `smooth-stream.js`：平滑流渲染模块。

## 五、适配与杂项

- 后端各模块（goal/judge、mcp、subagent、tokenizer、updater、security、webui、tray、notify 等）与前端各模块（消息渲染、会话管理、设置、skill-picker、hover 等）适配新架构；README/SPEC/frontend README 同步。
- 大量测试新增/更新（`test_plugin_*`、`test_llm_transport`、`test_responses_*`、`test_tool_registry`、`test_provider_registry`、`test_game_arena_plugin`、`test_bundled_host_extensions`、`test_smooth_stream_runtime` 等 40+ 个）。
- `app/templates/dist` 已重建。

## 相关提交

- `feat(llm): provider-based transport with OpenAI Responses support`
- `feat(plugins): host services, web gateway and built-in feature plugins`
- `feat(tools): source-agnostic tool registry and execution policy`
- `feat(runtime_v2): extension state, legacy compat and smooth stream`
- `chore: backend and docs adaptation`
- `chore: frontend and tests adaptation`