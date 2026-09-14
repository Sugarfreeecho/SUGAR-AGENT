# 插件加载与清单 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
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

## 3. 边界

- 加载失败≠崩溃：失败信息进入运行错误列表（`plugin_runtime_errors`）。
- 清单能力声明不授予权限本身（权限仍走工具/审批体系）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-6A1/6A2 | `agent_extensions.py` L62–165、`plugins/loader.py` |
| UC-6A3 | L1085–1097、`plugins/state.py` |
| UC-6A4 | L1463–1545 |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-601）。
