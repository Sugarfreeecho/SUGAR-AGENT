# 插件 UI、命令与后台服务 · 功能方案设计（UseCase 清单）

- 版本：2026-09-14 v2（覆盖至：HEAD `d022831`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`plugins/ui.py`（914 行）、`plugins/web.py`、`agent_extensions`（命令目录/派发）、前端 `plugin-ui-slots.js`。
- 上级：`00-能力扩展加载整体设计.md`

---

## 1. 功能定位

插件从"后台能力"到"前台面孔"的三种出口：命令（可述）、UI 插槽（可视）、后台服务（可持）。

## 2. UseCase

### UC-6D1 命令目录与派发
- **触发**：插件声明命令（含声明式模板）。
- **预期现象**：命令出现在可列举的目录中（含描述/参数）；执行时参数正确展开；未知命令明确报错。
- **依据**：`plugin_command_descriptions / _plugin_command_catalog / _expand_declarative_command / dispatch_plugin_command`。

### UC-6D2 UI 插槽注入
- **触发**：插件声明 UI（chat.extension 等插槽）。
- **预期现象**：对应面板/按钮按插槽规则出现（如 change-review 的改动审查面板）；未启用/未信任插件不注入任何 UI。会话级扩展面板（如 session-todo/agent-goal）的实时刷新：live 流内经 `extension_state_changed`；观察者流经 `ephemeral+control_event` 旁路转发，前端消费后刷新（见 ../05-WebUI对话界面/03 UC-5C3）。
- **依据**：`plugin-ui-slots.js`、`plugins/ui.py`、清单 `ui.chat.extension`、`webui._observer_extension_control_event`。

### UC-6D3 会话级 UI 动作
- **触发**：插件要求与当前会话相关的动作（打开面板/查询状态）。
- **预期现象**：动作以会话上下文执行并返回结果；越权动作被拒。
- **依据**：`plugin_session_action / plugin_session_ui_snapshot`。

### UC-6D4 Web 路由
- **触发**：插件声明 web assets。
- **预期现象**：插件的静态资源/路由可被界面加载；路径隔离（插件间不串）。
- **依据**：`plugins/web.py`、清单 `web.assets`。

## 3. 边界

- 插件的**工具**类出口走工具系统（../03-工具系统/01）；
- change-review 是 UI 插槽的现成样例（其专项设计见本文件夹 `08-内置插件-改动审查方案设计-UseCase清单.md`）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-6D1 | `agent_extensions.py` L589–750 |
| UC-6D2/6D3 | L1522–1554、`plugins/ui.py` |
| UC-6D4 | `plugins/web.py` |

## 5. 版本记录

- 2026-09-14 v2：补录扩展状态控制事件旁路（observer 流）；版本线更新至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-605）。
