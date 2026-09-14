# 扩展、子代理与运行注册 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `d022831`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`runtime_v2/extension_state.py`（432 行）、`subagent_store.py`、`subagent_repository.py`、`run_registry.py`。
- 上级：`00-会话存储RuntimeV2整体设计.md`

---

## 1. 功能定位

三类"附属账目"的存储语义：扩展命名空间状态、子代理账本、运行注册表（谁是活的）。

## 2. UseCase

### UC-8D1 扩展状态（命名空间）
- **触发**：插件写入会话级状态（如 change-review 的登记、其他插件数据）。
- **预期现象**：按插件+命名空间隔离读写；写入带 compare-and-set 语义——冲突抛明确错误（StateConflict），缺失抛 NotFound；重启保留。
- **依据**：`SessionExtensionStateStore / ExtensionStateConflict / ExtensionStateNotFound`。

### UC-8D2 子代理账本
- **触发**：子代理创建/更新/结束。
- **预期现象**：子代理状态、输出引用持久化；主会话可见子代理历史（关闭应用后仍可查）；分支复制时随会话走。
- **依据**：`RuntimeSubagentStore / SubagentRepository / SubagentState`。

### UC-8D3 运行注册表
- **触发**：run 开始/心跳/结束。
- **预期现象**：活跃 run 可被列举（含心跳时间）；超时/孤儿可识别；结束后注销。
- **依据**：`RunRegistry / RunState`。

### UC-8D4 孤儿清理
- **触发**：异常退出后重启。
- **预期现象**：孤儿 run 被清理（不再显示"运行中"）；未读标记与终态被补记；界面不出现僵尸状态。
- **依据**：`_cleanup_orphan_runtime_v2_active_runs`、`_runtime_v2_active_runs_are_recent`。

## 3. 边界

- 子代理的**界面呈现**见 ../05-WebUI对话界面/04；
- 扩展状态的**插件侧**使用方式由插件自定（宿主只提供语义）。

## 4. 依据映射

见上表（runtime_v2 + webui 清理段）。

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-809/810）。
