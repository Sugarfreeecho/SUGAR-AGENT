# 插件热重载工具 `reload_plugin`

日期：2026-11-17。范围：新增一个核心内置 host 工具，对**单个插件**做热重载；不改动插件加载策略、不重启后端。

## 行为

模型调用 `reload_plugin(plugin_id, reason?)` 后，宿主按顺序执行：

1. 校验插件命名空间，未安装则返回 `unknown_plugin`，此时不做任何缓存失效。
2. `PluginManager.reload_changed()` 重新扫描磁盘，更新定义基线并得出 added/changed/removed。
3. `invalidate_extension_caches(plugin_id=…)`：只释放该插件的 host-service 租约、只丢弃该插件的 runtime worker、清除 hook 管理器与技能缓存；其他插件的 worker 保持存活。
4. `start_plugin_background_services(loaded=…)`：按内容签名重新拉起该插件的后台服务；签名未变的插件不会重启。
5. 有 FastAPI 应用时，重装 bundled host 适配器（路由与生命周期回调），并按需 `agent_mcp.force_reload()`（仅当插件声明了 MCP server）。
6. 返回结构化 JSON：`changed`、`signature_before/after`、`changes`、`components`（skills 为实际 `SKILL.md` 数）、`background_services`、`routes_reinstalled`、`mcp_refreshed`、`errors`、`warnings`、`elapsed_ms`。

`signature_before` 取自上一次装载记录的基线（`PluginManager.loaded_signature()`），不是入口时的即时扫描——插件文件通常已经改完才调用本工具，即时扫描会把前后签名算成同一个。

## 文件

| 文件 | 变更 |
|---|---|
| `app/plugin_hot_reload.py` | 新增：定向重载流程与 `reload_plugin` 调用器 |
| `app/builtin_host_tools.py` | 注册 `reload_plugin`（owner `core.services`，`effect=control`） |
| `app/agent_tools.py` | 新增工具 Schema，`plugin_id` 必填 |
| `app/security/runtime.py` | 分类为 `tool.call` / `effect=control`（声明式，不经 workspace 写入路径） |
| `app/tool_search.py` | 加入 `RESIDENT_TOOLS`，常驻工具数组，无需先 `tool_search` |
| `app/plugins/manager.py` | 新增 `loaded_signature()`，供变更报告读取装载基线 |
| `tests/test_plugin_hot_reload.py` | 新增 10 个用例 |

## 边界

- 不安装依赖、不启用被禁用的插件；插件处于禁用或装载失败时只清理缓存并返回 `active=false`。
- 插件 worker 被替换时，正在执行的该插件调用会失败，结果里体现为调用错误，不是静默重试。
- bundled host 适配器若自身不做路由去重，重复 `install()` 可能留下旧路由；工具会在 `warnings` 中提示核对 `/api` 路径。
- MCP 重新发现是全局操作，只在插件声明 MCP server 时触发。
- 工具本身是新增 Python 代码，当前运行中的后端需重启一次才会出现该工具。

## 验证

- `pytest tests/test_plugin_hot_reload.py`：10 项通过（注册/常量、未知插件不触发失效、定向失效、无变更、禁用、装载错误过滤、路由与 MCP、重装失败降级、JSON 结果、装载基线）。
- `pytest tests/test_plugins_core.py tests/test_plugin_host_services.py tests/test_tool_registry.py`：与插件加载、host service、工具注册相关用例通过（本机既有失败项见下）。
- 真实端到端（临时目录 + 真实 `PluginManager`）：首次重载 `changed=false`、`skills=1`；新增一个 `SKILL.md` 后重载得到 `changed=true`、`skills=2`，签名 `2da60926→6d53fad0`；无 FastAPI 应用的进程返回 `routes_reinstalled=false` 与相应 warning。
- 本机既有失败与本改动无关：`scheduled_tasks`/`manage_scheduled_task` 的 `additionalProperties`、`agent_loop._execute_one_impl` 缺失、ripgrep 用例、`delete.review` 规则断言、`test_history_context` 临时目录创建失败。
- 未重启正在运行的后端实例，未对用户插件目录做写操作。
