# 插件加载与清单 · 功能方案设计（UseCase 清单）

- 版本：2026-10-19 v4（受身份守卫的manager名称缓存）
- 用途：逐条审查（四字段格式）。
- 适用实现：`plugins/manager.py`、`plugins/loader.py`、`agent_extensions.load_plugins`、`plugins/models.py`。
- 上级：`00-能力扩展加载整体设计.md`

---

## 1. 功能定位

插件的"发现—校验—登记"：哪些插件存在、它们的清单长什么样、启停如何持久。

## 2. UseCase

### UC-6A1 插件清单解析
- **触发**：启动/刷新扩展列表。
- **预期现象**：`.myagent-plugin/plugin.json` 被解析（id/name/version/capabilities）；**内置系统插件**（`system_builtin: true`）与用户插件区分展示。
- **规则与边界**：清单不合法（缺 id/版本）的插件被跳过并记录原因；不影响其他插件。
- **依据**：`plugins/models.py`、`_is_bundled_system_plugin`。

### UC-6A2 插件加载结果
- **触发**：加载执行。
- **预期现象**：产出结构化加载结果（成功列表/失败原因）；启停状态持久化；重复加载幂等。
- **依据**：`load_plugins() -> PluginLoadResult`。

### UC-6A3 启用/停用
- **触发**：界面上开关插件。
- **预期现象**：即时生效——停用后其工具/命令/UI 消失；启用后恢复；状态写入持久存储。
- **依据**：`set_plugin_enabled`、`plugins/state.py`。

### UC-6A4 扩展快照
- **触发**：打开扩展面板/诊断。
- **预期现象**：快照含每个扩展的状态、能力、来源路径；供排查用。
- **依据**：`extensions_snapshot / plugin_session_ui_snapshot`。

### UC-6A5 工具目录检查期间共享一次插件状态读取

- **触发**：`HostToolInvokerRegistry.catalog_revision()` 遍历多个 bundled host 工具可用性回调。
- **预期现象**：使用仅覆盖本次同步检查的 ContextVar scope，首次 bundled 回调解析 manager 并读取插件状态，其余回调复用同一份状态；不为每个工具重复规范化路径和读取 JSON。无 bundled 回调时不读插件状态。
- **规则与边界**：scope 退出即释放；下一次目录检查重新读状态，环境总开关与各工具自己的额外开关仍参与可用性。实际工具执行在 scope 外按最新状态检查。读取失败时不启用工具，缓存不跨请求存活。
- **依据**：`plugins.host.bundled_host_availability_scope / bundled_host_plugin_enabled`、`host_tool_registry.HostToolInvokerRegistry.catalog_revision`；`tests/test_host_catalog_availability_scope.py`。

### UC-6A6 host目录构建在线程中执行一次状态pass

- **触发**：完整工具目录初建或后台重验，扫描多个host绑定及bundled host定义。
- **预期现象**：先在所属ReAct事件循环取得插件tuple，保持`load_plugins`陈旧命中的后台刷新调度，再将tuple交给to_thread中的同步host构建；worker不重复调用加载门面。ReAct事件循环在同步构建阻塞时仍能响应；同次同步pass只有一次manager/state读取，其后回调复用。host阶段单独记`host_tool_definitions`，不再全部留在registry未覆盖包络里。
- **规则与边界**：只共享本次pass，退出释放，下次重新读；MCP/插件异步生命周期仍在原loop，实际工具调用实时检查启停。state读取成功后才发布enabled，失败时本pass全部绑定禁用，不能第一次失败后默认启用其余工具。其他工具自己的额外开关及原host信任/源路径检查保留，不缓存跨请求授权。
- **依据**：`agent_loop._build_host_tool_catalog/build_combined_tool_registry_for_session`、`agent_extensions.bundled_host_tool_definitions(loaded_plugins=...)`、`plugins.host.bundled_host_plugin_enabled`；`tests/test_host_catalog_availability_scope.py`覆盖次数、下一次启停、调用时禁用、读失败全关闭、所属loop加载/worker不重载和构建不阻塞事件循环；真实失败及阶段基准见[d68报告](../../performance/agent-session-8533-run-d68-2026-10-18.md)。

### UC-6A7 默认manager配置名称的有界缓存

- **触发**：同一进程反复取得默认插件manager；真实95b的PostToolUse中canonical子段963.780ms，另一次186.716ms。
- **预期现象**：仅已是canonical拼写的路径可以复用规范化名称。持有原manager锁，每次先以lstat的device/inode/ctime/type及父目录身份校验；最多32项LRU，未变化时减少Path.resolve调用。
- **规则与边界**：创建、替换、父目录替换或环境配置变化重新解析；别名、reparse、未知身份、缺父目录、访问错误保持实时解析。默认路径发现与迁移检查仍执行，启停状态/信任/实际调用授权保持实时；不缓存跨请求授权，不延长UC-6A5的状态scope。名称缓存失败不能隐藏原解析错误。首次构造与失效有额外守卫成本，不能承诺所有配置均获收益。
- **依据**：`plugins.manager._canonical_manager_path / _manager_path_identity / get_plugin_manager`、`tests/test_plugin_manager_path_cache.py`；局部正常配置60次resolve由180降至0，原P50 1.378ms、新0.811ms；Windows 8.3别名按设计不命中，真实收益尚待自然重启后的样本，见[多会话复核](../../performance/agent-current-sessions-2026-10-19.md)。

## 3. 边界

- 加载失败≠崩溃：失败信息进入运行错误列表（`plugin_runtime_errors`）。
- 清单能力声明不授予权限本身（权限仍走工具/审批体系）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-6A1/6A2 | `agent_extensions.py` L62–165、`plugins/loader.py` |
| UC-6A3 | L1085–1097、`plugins/state.py` |
| UC-6A4 | L1463–1545 |
| UC-6A5 | `plugins.host.bundled_host_availability_scope`、`HostToolInvokerRegistry.catalog_revision` |
| UC-6A6 | `_build_host_tool_catalog`、`build_combined_tool_registry_for_session`、`bundled_host_plugin_enabled` |
| UC-6A7 | `_canonical_manager_path`、`_manager_path_identity`、`get_plugin_manager` |

## 5. 版本记录

- 2026-10-19 v4：按当前多会话963.780ms直接子段证据，增加仅名称的有界缓存、逐次身份守卫与别名降级；状态和权限不跨请求缓存。

- 2026-10-18 v3：完整host构建复用单次状态读取并在线程执行；所属loop预取插件tuple保留陈旧命中的后台刷新，worker不重复加载；修复读失败后的enabled提前发布，保留调用时实时启停与原信任检查。

- 2026-10-17 v2：新增 UC-6A5，限定启用状态快照只在单次目录检查内共享，保留实际执行时的实时检查。
- 2026-09-13 v1：拆分首版（承接 UC-601）。
