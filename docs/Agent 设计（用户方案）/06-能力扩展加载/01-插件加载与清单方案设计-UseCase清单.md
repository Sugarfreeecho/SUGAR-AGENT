# 插件加载与清单 · 功能方案设计（UseCase 清单）

- 版本：2026-10-25 v9（插件可用性体检与体检会话）
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
- **预期现象**：仅已是canonical拼写的路径可以复用规范化名称。每次以lstat的device/inode/ctime/type及父目录身份校验；最多32项LRU，未变化时减少Path.resolve调用。10-21起文件检查与resolve位于锁外，独立短锁仅保护LRU读取/更新/淘汰，避免一个慢路径阻塞其他路径的检查。
- **规则与边界**：创建、替换、父目录替换或环境配置变化重新解析；别名、reparse、未知身份、缺父目录、访问错误保持实时解析。默认路径发现与迁移检查仍执行，启停状态/信任/实际调用授权保持实时；不缓存跨请求授权，不延长UC-6A5的状态scope。名称缓存失败不能隐藏原解析错误。首次构造与失效有额外守卫成本，不能承诺所有配置均获收益。
- **依据**：`plugins.manager._canonical_manager_path / _manager_path_identity / get_plugin_manager`、`tests/test_plugin_manager_path_cache.py`；局部正常配置60次resolve由180降至0，原P50 1.378ms、新0.811ms；Windows 8.3别名按设计不命中，真实收益尚待自然重启后的样本，见[多会话复核](../../performance/agent-current-sessions-2026-10-19.md)。

### UC-6A8 默认manager路径准备与并发发布

- **触发**：ReAct目录版本检查、Hook或WebUI等线程并发取得默认manager；10-21真实3bf iter2观察到manager锁1066.775ms，另一次默认路径包络749.407ms。
- **预期现象**：默认路径/迁移检查及canonical守卫在manager发布锁外执行；已有同配置manager立即返回。首次私有构造也在锁外，可以重复构造无发现/写盘副作用的候选，锁内双重检查后只发布一个，同配置并发调用取得同一已发布实例。一个慢调用不再把自己的路径I/O作为其他调用的全局屏障。
- **规则与边界**：准备前取得仅含环境配置与实现入口的内存token；进入发布锁及候选发布前复核。插件目录/状态路径或home/data-root环境变化时重做准备，慢旧配置请求不能覆盖新配置。旧配置调用可在线性化检查后正常返回，未承诺锁外环境永不变化。文件/父目录替换、alias/reparse与访问错误仍依UC-6A7实时守卫；路径读取失败不替换已有实例。启停状态、信任及实际调用授权仍实时，未缓存跨请求授权。
- **迁移边界**：发现legacy源时用独立迁移锁再次检查并执行原move，正常不存在legacy源时不取得该锁；复制期间目标已出现但源尚在的第二个调用必须等迁移完成。迁移失败仍选旧路径，不在manager发布锁或LRU锁里移动文件。该互斥只覆盖本进程，不新增跨进程迁移协议。
- **依据**：`get_plugin_manager / _manager_configuration_token / _canonical_manager_path / _migrate_legacy_path / _user_plugins_dir`；新增9项定向用例，共20项通过；原代码对照的6项并发场景按预期失败。相关插件、状态、host目录及主/前后台子入口组合214 passed、1系统符号链接跳过，源码前后无漂移。350ms受控阻塞下第二调用P50约355–360→0.5–0.6ms，仅证明消除锁放大，不等价于完整轮间收益。持续负载及生产加载状态见[10-21报告§10](../../performance/agent-subagent-interround-2026-10-21.md#10-插件manager发布锁隔离补修)。

#### UC-6A8 补充：同次默认路径复用源根

`default_state_path`未显式配置状态路径时只解析一次本模块所属项目根，再用于新配置和legacy迁移路径；受控检查两条结果路径相同，源文件resolve调用从2次变1次。不增加跨调用缓存，不免除每次配置/目录/源身份检查或迁移互斥。显式路径分支和实时信任语义保持；不能将减少一次解析称为目录revision全部免I/O。完整关联实现、回归与待生产加载范围见[报告§13](../../performance/agent-subagent-interround-2026-10-21.md#13-事实提交与hook准备的事件循环隔离补修)。

### UC-6A9 后台Hook准备保留目录陈旧命中

- **触发**：Hook准备已在线程执行，同键插件目录超过原30秒TTL。
- **预期现象**：返回已有目录，显式使用原owner loop安排一次后台刷新。future注册和去重在该loop，扫描在worker并沿用原扫描锁；目录准备线程不因缺少running loop退回同步扫描。
- **规则与边界**：排队回调和刷新发布均核对catalog generation，失效后旧回调不能扫描/回填；排队期间目录已更新或切换键时，旧请求不再扫描。force、冷缓存、无可用或已关闭loop仍等待真实加载，不放宽实际调用时的实时信任/启停检查。executor提交失败清理in-flight和活动计数，后续仍可刷新。
- **依据**：`load_plugins(refresh_loop=...) / _schedule_plugin_cache_refresh / _prepare_hook_dispatch`；最初6项目录新增用例所在39项组合通过；补同键/新鲜度2例后，最终冻结定向27项通过、源码无漂移，包含当前8项目录例及相关Hook/失效/取消。23:22自然运行暴露了线程化初版的同步扫描回退，补修与未加载限制见[报告§14](../../performance/agent-subagent-interround-2026-10-21.md#14-2322自然重启与hook目录刷新回退补修)。

### UC-6A10 插件四级分层与逐插件环境开关

- **触发**：插件发现、设置页目录、工具目录构建、桌面打包。
- **预期现象**：`app/plugins/tiers.json` 把插件分为 `system`（设置页隐藏、工具常驻）、`system-external`（可见可开关、工具常驻）、`extension`（可见可开关、工具延迟）、`standalone`（不随包分发、默认停用、工具延迟）。每插件可用 `PLUGIN_<ID>_ENABLED` 强制开关，优先级高于界面状态与分级默认值；环境变量生效时设置页开关置灰并显示变量名。
- **规则与边界**：分级表是运行期与桌面打包的唯一口径；`system_builtin` 只保留“原生渲染/信任”语义，不再决定设置页可见性。未登记插件沿用“可见、默认启用、不打包”，未登记的老式内置插件仍隐藏。环境变量不落盘，界面开关仍写 `.config/plugins-state.json`；`standalone` 仅影响打包与默认值，用户手动启用后照常加载。
- **依据**：`plugins/tiers.json`、`plugins/tiers.py`、`plugins/manager.is_enabled`、`plugins/host.bundled_host_plugin_enabled`、`agent_extensions._plugin_catalog_data`、`packaging/scripts/prepare-payload.mjs`。

### UC-6A11 插件可用性体检与体检会话

- **触发**：设置页插件行点击「检查可用性」；插件刚由未启用打开，或已启用但 `loaded=false`（启用失败）时按钮高亮。
- **预期现象**：`GET /api/plugins/{id}/availability` 返回 `state`（ready / degraded / unavailable）和逐项 `checks`：全局开关、启用状态、清单兼容性、trusted_host 信任路径、`requirements.txt` 声明的依赖、必填配置、Web 入口、runtime 入口。`POST /api/plugins/{id}/diagnose` 新建会话并把报告写进首条提示词；主界面用一次性 localStorage 键接收提示词并自动发送，由 Agent 实际调用工具/页面复核，再按阻塞项逐步引导。
- **规则与边界**：体检只做静态检查，不导入插件代码；真实可用性以会话内调用结果为准。报告只用于引导，不改变启停或配置；安装依赖、改配置等动作需用户确认后执行。自动发送读取即删除，避免刷新重复发送；弹窗被拦截时退回当前标签打开。
- **依据**：`app/plugin_availability.py`、`app/webui.py`（`/api/plugins/{id}/availability`、`/api/plugins/{id}/diagnose`）、`app/templates/static/settings/sections_ext.js`、`frontend/src/app/modules/session-management.js`、`tests/test_plugin_availability.py`。

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
| UC-6A8 | `_manager_configuration_token`、`get_plugin_manager`、`_migrate_legacy_path`、`_user_plugins_dir` |
| UC-6A9 | `load_plugins(refresh_loop=...)`、`_schedule_plugin_cache_refresh`、`tests/test_hook_worker_plugin_cache.py` |
| UC-6A10 | `plugins/tiers.py`、`plugins/manager.py`、`agent_extensions.py`、`packaging/scripts/prepare-payload.mjs` |
| UC-6A11 | `plugin_availability.py`、`webui.py`、`sections_ext.js`、`session-management.js` |

## 5. 版本记录

- 2026-10-25 v9：新增插件可用性体检接口与体检会话；设置页按钮在刚启用/启用失败时高亮，会话内由 Agent 实际复核并分步引导。

- 2026-10-25 v8：新增四级分层（system / system-external / extension / standalone）、逐插件 `PLUGIN_<ID>_ENABLED` 与环境变量优先级；打包范围改由同一张分级表派生。

- 2026-10-21 v7：修复Hook目录读取移到worker后丢失陈旧命中后台刷新的回退；显式回原loop调度并保留generation、force、冷缓存和失败清理。

- 2026-10-21 v6：默认状态路径在同次调用复用一次源根解析，新旧目标一致；没有扩大名称缓存或省略身份、迁移和权限守卫。

- 2026-10-21 v5：默认路径I/O与候选构造移出manager发布锁，LRU只锁内存；新增配置token双重校验与独立迁移互斥，保留实时权限及失效检查，记录214项组合与受控机制对照，完整收益另验。

- 2026-10-19 v4：按当前多会话963.780ms直接子段证据，增加仅名称的有界缓存、逐次身份守卫与别名降级；状态和权限不跨请求缓存。

- 2026-10-18 v3：完整host构建复用单次状态读取并在线程执行；所属loop预取插件tuple保留陈旧命中的后台刷新，worker不重复加载；修复读失败后的enabled提前发布，保留调用时实时启停与原信任检查。

- 2026-10-17 v2：新增 UC-6A5，限定启用状态快照只在单次目录检查内共享，保留实际执行时的实时检查。
- 2026-09-13 v1：拆分首版（承接 UC-601）。
