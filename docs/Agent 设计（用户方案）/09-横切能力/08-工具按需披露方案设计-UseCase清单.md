# 工具按需披露 · 功能方案设计（UseCase 清单）

- 版本：2026-10-05 v1（覆盖至：当前工作区；tool_search 桥接与计量）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/tool_search.py`、`app/tool_registry.py`、`app/builtin_host_tools.py`、`app/agent_mcp.py`、`app/agent_loop.py`、`frontend/src/app/modules/session-scroll-history.js`、设置中心 MCP 页。
- 上级：`00-横切能力整体设计.md`；对接：`../02-ReAct运行时`（工具循环/审批/Hook）、`../06-能力扩展加载`（MCP/插件）、`../05-WebUI对话界面`（设置与浮窗计量）。

---

## 1. 功能定位

把"模型看到的工具定义"与"会话获准执行的目录"分开：内置/会话管理/后台任务/终端常驻，MCP 与 Computer Use 经 `tool_search / tool_describe / tool_call` 按需取用。

## 2. UseCase

### UC-9G1 披露策略与开关
- **触发**：请求组装（每次按 generation 失效判断）。
- **预期现象**：`on`（有可延迟工具即启用）/`auto`（延迟定义本地估算 token ≥ 窗口 `threshold_pct%` 或 `threshold_tokens`）/`off`（完整目录）。
- **规则与边界**：配置缺失/删除/损坏 = 关闭披露，不删除任何工具；`pinned_tools` 常驻豁免、`defer_plugin_tools` 默认关闭；`MYAGENT_TOOL_SEARCH` 只能覆盖已开启配置（文件 off/缺失不能被环境变量重新开启）；设置中心 MCP 页提供开关。
- **依据**：`tool_search.py`、设置中心 `sections_ext.js`；回归 `tests/test_tool_search.py`。

### UC-9G2 桥接调用与执行边界
- **触发**：模型调用 `tool_search`（query 或 `select:`/`+term`）、`tool_describe`、`tool_call`。
- **预期现象**：搜索只读本会话过滤后的延迟目录；describe 返回完整 schema；call 走既有 Hook/审批/审计/流式/执行记录管线（真实工具名）。
- **规则与边界**：不接受桥接嵌套/常驻工具借道/未知名称/非对象参数；桥接 invoker 不直接执行目标工具；等待完整模型轮次、不在参数流未完成时抢跑；调用原件保留（函数名与 tool_call ID 配对），执行副本在 Hook 前解包；子代理 profile/fork 授权目录同样生效。
- **依据**：`tool_search.py`、`agent_loop.py`、`tool_registry.py`、`builtin_host_tools.py`。

### UC-9G3 MCP 服务器级筛选
- **触发**：`.sugaragent/mcp_servers.json` 服务器 `tools.include/exclude/pin` 增量设置。
- **预期现象**：include 空=不限、exclude 优先、pin 不复活被禁用/排除工具；旧 `tools.<name>` 执行契约继续兼容；设置中心支持按服务器批量启停与常驻按钮。
- **依据**：`agent_mcp.py`、`mcp_servers.json.example`；回归 `tests/test_mcp_tool_selection.py`。

### UC-9G4 计量与失效重建
- **触发**：上下文浮窗显示；模型配置 generation / 子代理类型 / MCP 目录 / 配置文件变化。
- **预期现象**：浮窗显示延迟工具数量与净节省估算（`deferred_tools_tokens` / `saved_tools_tokens` 已扣除桥接开销），不计入本轮上下文总量；已激活目录遇 revision 变化重建；冷启动先提供已就绪工具。
- **依据**：`session-scroll-history.js`、`agent_tokenizer.py`；回归 `tests/js/context_breakdown_card_runtime.cjs`、`tests/test_context_breakdown.py`。

## 3. 边界

- 披露只影响模型可见目录，不影响授权/审计；被隐藏工具的调用需经桥接且同样受权限约束；
- 搜索/描述结果进入对话历史与上下文计量。

## 4. 版本记录

- 2026-10-05 v1：初版——UC-9G1 策略与开关、UC-9G2 桥接边界、UC-9G3 MCP 筛选、UC-9G4 计量与失效。
