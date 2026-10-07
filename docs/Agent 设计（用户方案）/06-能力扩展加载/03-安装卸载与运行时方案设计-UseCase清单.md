# 安装、卸载与运行时 · 功能方案设计（UseCase 清单）

- 版本：2026-10-07 v3（覆盖至：当前工作区；延迟结果过期清理）
- 用途：逐条审查（四字段格式）。
- 适用实现：`plugins/installer.py`、`plugins/runtime.py`、`plugins/worker.py`、`worker_node.cjs`、`agent_extensions.install_plugin*`。
- 上级：`00-能力扩展加载整体设计.md`

---

## 1. 功能定位

插件的"生命周期后半段"：安装/依赖/卸载/回滚，以及安装后的运行承载（worker/后台服务）。

## 2. UseCase

### UC-6C1 安装与校验
- **触发**：安装本地插件包。
- **预期现象**：安装前校验清单/结构；不合法即拒绝并说明；合法则登记到插件目录。
- **依据**：`plugins/installer.py`、`install_plugin`。

### UC-6C2 依赖安装
- **触发**：插件声明依赖（如 Node 依赖）。
- **预期现象**：按需安装并汇报进度/结果；失败不影响其他插件与主程序。
- **依据**：`install_plugin_dependencies`。

### UC-6C3 卸载与回滚区
- **触发**：卸载插件 / 安装冲突回滚。
- **预期现象**：文件移入插件目录下独立 `.myagent-trash`（可找回）；卸载即从列表消失；无残留引用报错。
- **依据**：`uninstall_plugin`、`installer.py` L219/307。

### UC-6C4 运行时承载
- **触发**：插件工具调用 / 后台服务启动。
- **预期现象**：Node worker 按需启动（`worker_node.cjs`）；后台服务随启用状态启停；进程异常不拖垮主进程（隔离）。
- **依据**：`plugins/runtime.py / worker.py`、`start_plugin_background_services / stop_plugin_runtime`。

### UC-6C5 延迟工具结果过期时仍执行清理

- **触发**：插件工具返回延迟结果；宿主检查截止时间后，线程边界上的下一次轮询恰好遇到令牌过期；或调用被取消。
- **预期现象**：真实过期按 `timeout` 调用插件取消清理，插件能释放仍等待的资源并收到原调用的会话与取消上下文；正常取消按 `cancelled` 清理。清理后撤销租约，正常完成结果不向界面或模型暴露宿主延迟标记。
- **规则与边界**：令牌必须先通过工具身份、插件签名及 `session_id / run_id / cancellation_id` 校验，再判断期限。轮询过期使用专门的 `DeferredTokenExpiredError`，保留租约直到 `cancel_deferred` 清理完成；清理允许令牌过期但仍要求原身份。未知、已消费、错工具或未授权令牌继续报协议/授权错误，不因错误文本含 `expired` 被吞成超时。插件清理失败时由宿主记录错误并给超时/取消兜底结果。
- **依据**：`plugins/runtime.py::DeferredTokenExpiredError / PluginRuntimeRegistry._deferred_binding / poll_deferred / cancel_deferred`、`agent_extensions.py::invoke_plugin_tool`；`tests/test_plugin_deferred_results.py::test_deferred_expiry_during_poll_still_calls_cleanup / test_deferred_protocol_error_is_not_treated_as_timeout`，以及正常完成/取消/权限绑定用例。

## 3. 边界

- 安装不授予信任——首次使用仍需信任流程（见 07）；
- 插件工具的权限与审批走统一体系（../03、../07）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-6C1~6C3 | `agent_extensions.py` L1150–1187、`plugins/installer.py` |
| UC-6C4 | `plugins/runtime.py`、`worker_node.cjs`；后台服务启停 `agent_extensions.py` L599–621 |
| UC-6C5 | `plugins/runtime.py` 的租约身份与期限检查、`agent_extensions.invoke_plugin_tool` 的超时清理；`tests/test_plugin_deferred_results.py` |

## 5. 版本记录

- 2026-10-07 v3：新增 UC-6C5，记录跨线程轮询遇到期限过期、身份先验、保留租约直到取消清理，以及未知/已消费令牌不吞成超时。

- 2026-09-14 v2：澄清 L599–621 归属（`agent_extensions.py` 插件后台服务启停）；版本线更新至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-603/604）。
