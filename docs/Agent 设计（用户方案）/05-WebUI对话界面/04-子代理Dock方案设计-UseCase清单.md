# 子代理 Dock · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`frontend/src/app/state/subagent-*`（10 个模块）、`modules/subagent.js`、后端 subagent API 组。
- 上级：`00-WebUI对话界面整体设计.md`

---

## 1. 功能定位

把子代理任务"放进一个抽屉"：状态、输出、动作（中断/删除/切模型/继续）一站可见。

## 2. UseCase

### UC-5D1 Dock 数据同步
- **触发**：主任务派生子代理。
- **预期现象**：Dock 里即出现该子代理（名称/状态/耗时）；状态与主会话事件同源更新（无需刷新）。
- **依据**：`subagent-store/loader/sync`、`_build_session_subagents_response`。

### UC-5D2 查看输出
- **触发**：点击某子代理。
- **预期现象**：可查看其完整输出（含流式时的增量）；大输出截断合理。
- **依据**：`get_subagent_output`、`subagent-renderers`。

### UC-5D3 动作：中断 / 删除 / 继续
- **触发**：对子代理执行中断、删除、继续。
- **预期现象**：中断即时生效（状态转为已中断）；删除后从 Dock 消失且不影响主任务；"继续"以追加指令恢复同一子代理。
- **依据**：`interrupt_subagent / delete_subagent`、`subagent-continue.js`。

### UC-5D4 切换子代理模型
- **触发**：对运行中/等待中的子代理 set 模型档案。
- **预期现象**：只影响该子代理（主会话不变）；切换后输出继续；状态机不损坏。
- **依据**：`switch_subagent_model_profile_api`、`subagent-event-state.js`。

### UC-5D5 子代理视图隔离
- **触发**：主会话与子代理视图并存。
- **预期现象**：两者的渲染/滚动互不串扰；子代理的审批/问答不弹到主视图外（按归属显示）。
- **依据**：`subagent-dock.js / subagent-cache.js`。

## 3. 边界

- 子代理的**定义与调度**（如何被创建）属工具系统 task 工具与 ReAct 的协作，不在本篇；
- 子代理的存储细节见 ../08-会话存储RuntimeV2/05。

## 4. 依据映射

见上表（frontend state/subagent-* + webui subagent API）。

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-507 与 UC-1E2 的界面部分）。
