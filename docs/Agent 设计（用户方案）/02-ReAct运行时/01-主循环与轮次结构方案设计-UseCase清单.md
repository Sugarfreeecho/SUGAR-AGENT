# 主循环与轮次结构 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v4（覆盖至：当前工作区）
- 用途：逐条审查（触发 → 预期现象 → 规则与边界 → 依据）。
- 适用实现：`app/agent_loop.py`（`react_node / _react_node_once / _late_round_synthesis_reminder / finish / astream_events`）。
- 上级：`00-ReAct运行时整体设计.md`

---

## 1. 功能定位

一次任务的"心跳"：思考—行动—观察循环，直到产出最终答复。

## 2. UseCase

### UC-2A1 决策-行动-观察循环
- **触发**：用户消息进入（或恢复运行继续）。
- **预期现象**：模型先想（可能有思考计时提示）→ 若调工具则执行并回填 → 再想……循环推进；最终给出答复并结束 run。
- **规则与边界**：循环在**线程外**执行（不阻塞事件循环，界面保持响应）；"最终答复"前会推 `validate_final` 事件——当前实现**不再调用独立校验模型**，仅为 PASS 占位（见 05 写栅栏与提交链）。
- **依据**：`react_node / _react_node_once / validate_final / prepare_final_event`。

### UC-2A2 流式事件出口
- **触发**：运行中任意状态变化。
- **预期现象**：思考增量、工具状态、进度提示、最终答复按序到达界面（SSE 事件）；刷新页面可从历史回放。
- **规则与边界**：事件追加与 Runtime V2 提交共用顺序源（不出现"界面有、历史无"）。
- **依据**：`_push_stream_event`、`astream_events`。

### UC-2A3 运行收尾
- **触发**：正常结束 / 中断 / 失败。
- **预期现象**：三种结局都有明确终态（答复 / 中断文案 / 错误卡）；未读标记正确（切回会话能看到）。
- **依据**：`finish`、`_finalize_agent_run_lifecycle`、`_mark_run_terminal_unread`。

### UC-2A4 出站历史装配与工具链校验
- **触发**：每次模型请求完成本轮实际出站历史装配。
- **预期现象**：先规范化模型轮次并为缺失的 tool result 注入明确占位，再从实际出站消息中删除没有直属 assistant tool call、重复或 call ID 错配的 tool result，避免供应商以非法消息链拒绝请求。
- **规则与边界**：正常会话不在加载阶段扫描整份持久化历史，只校验本次真正发给模型的部分；只有出站校验发现脏数据时，才额外清理 `llm_history/work_messages` 并持久化一次。插话回滚产生的未闭合工具尾巴仍由独立回滚清理路径处理。
- **依据**：`messages_for_openai_turns / inject_missing_tool_messages / _drop_orphan_tool_messages / _persist_orphan_cleanup_after_outgoing_detection / _rollback_steer_partial_turn`。

### UC-2A5 长运行收敛检查点
- **触发**：单次 run 达到第 24 个 ReAct 轮次，或累计 48 次工具调用；达到第 32 轮或 72 次工具调用时进入强提醒档。
- **预期现象**：模型先判断现有证据是否足够；足够则停止继续探索并综合最终答复，不足则只执行路径与目的都明确的定向验证。
- **规则与边界**：这是软收敛而非硬截断，不会切断仍然必要的工具调用；阈值由 `LATE_SYNTHESIS_*` 环境变量调整。检查点作为请求尾部 system 消息临时注入，不写入会话历史，也不插到历史前缀中破坏供应商 Prompt Cache。
- **依据**：`_late_round_synthesis_reminder`、`_react_node_once` 的 `convergence_reminder` 装配。

## 3. 边界

- "一轮"的粒度 = 一次模型请求及其工具往返；多轮由循环驱动，并受 `max_react_iter`、上下文/预算约束及 UC-2A5 软收敛检查点共同控制。
- 循环期间的压缩触发见 ../09-横切能力/01。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-2A1 | `react_node`、`_react_node_once` |
| UC-2A2 | `_push_stream_event`、`astream_events` |
| UC-2A3 | `finish`、`_finalize_agent_run_lifecycle`、`_mark_run_terminal_unread` |
| UC-2A4 | `messages_for_openai_turns`、`inject_missing_tool_messages`、`_drop_orphan_tool_messages`、`_persist_orphan_cleanup_after_outgoing_detection` |
| UC-2A5 | `_late_round_synthesis_reminder`、请求消息尾部装配 |

## 5. 版本记录

- 2026-09-20 v4：将历史清洗改为实际出站消息校验；仅发现孤儿 tool 时修复并持久化底层历史，移除正常加载路径的全历史扫描。
- 2026-09-20 v3：新增长运行软收敛检查点；补充阈值、Prompt Cache 前缀保护和硬上限边界。
- 2026-09-14 v2：修正 agent_loop.py 行号漂移（+15）与 validate_final 描述；版本线更新至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-201/214 等）。
