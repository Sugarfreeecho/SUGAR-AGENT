# 写栅栏与 Runtime V2 提交 · 功能方案设计（UseCase 清单）

- 版本：2026-09-30 v3（覆盖至：当前工作区；性能优化的同步事实边界）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_loop.py`（提交点 L2113–2660）、`runtime_v2/history_ops.py`。
- 上级：`00-ReAct运行时整体设计.md`

---

## 1. 功能定位

运行内核与存储的**契约层**：什么时候写、写什么、失败怎么办——保证"事件流 = 唯一真源"。

## 2. UseCase

### UC-2E1 用户轮 / 答复提交
- **触发**：收到用户消息 / 产出最终答复。
- **预期现象**：两者都以事件形式原子提交；顺序稳定（用户轮在前）；失败不产生半截状态。
- **依据**：`_runtime_v2_commit_user_turn / _runtime_v2_commit_assistant_final`。

### UC-2E2 模型消息追加与历史替换
- **触发**：每轮模型/工具消息产生；或历史被压缩替换。
- **预期现象**：追加按序；"替换"以显式 reason 记录（可审计）；替换后模型投影立即反映。
- **依据**：`_runtime_v2_append_model_message / _runtime_v2_replace_model_history`。

### UC-2E3 写栅栏
- **触发**：同一会话内新 run 合法取得写栅栏，或旧 run 在检查点准备继续写入。
- **预期现象**：只有持有当前 `run_id` 栅栏的 run 可以继续提交业务事件；失去栅栏的旧 run 停止写入，但仍以 `run_interrupted(reason=superseded_by_new_run)` 写入自己的唯一终态。
- **规则与边界**：写栅栏用于隔离业务写，不等于省略旧 run 终态；中断判断也必须匹配 exact run，旧 run 的标记不得污染替代 run。
- **依据**：`_state_run_has_write_fence`、`_state_interrupt_requested`、`_RuntimeV2RunLifecycle`。

### UC-2E4 检查点
- **触发**：上下文 token 变化 / 压缩提交。
- **预期现象**：检查点记录 token 水位（供压缩判断与界面显示）；重启后水位可恢复。
- **依据**：`_runtime_v2_checkpoint_context_tokens`、`_runtime_v2_commit_context_summary`。

### UC-2E5 异步优化不得跨越事实提交边界

- **触发**：把观测写盘、UI 增量或派生索引维护移出重复热路径。
- **预期现象**：用户轮提交、助手消息/工具结果提交、压缩/摘要提交、子代理所有权转交这四类边界仍按原顺序完成；下一次 API 和取得执行权的子代理看到的事实完整。
- **规则与边界**：本批仅调整指标序列化/写盘的锁范围、临时 UI 增量交付、无新锚点的索引维护，以及只读查询的复制范围。事件日志追加、fsync、事务锁与耐久提交失败语义保留；临时 UI 增量入队不能替代事实提交。桥接 flush 表示先前交付队列已处理，耐久保证仍由 Runtime V2 提供。
- **依据**：`RuntimeHistoryOps` 的用户轮、模型消息、摘要提交；`agent_subagent.py::_commit_subagent_initial_turn`；[08/01 · UC-8A6](../08-会话存储RuntimeV2/01-事件日志与错误语义方案设计-UseCase清单.md)、[05/03 · UC-5C8](../05-WebUI对话界面/03-SSE管道与断线续看方案设计-UseCase清单.md)。

## 3. 边界

- 存储侧错误语义（Busy/损坏）见 ../08-会话存储RuntimeV2/01。
- 这里的"提交"只负责顺序与原子性；压缩算法本体见 ../09-横切能力/01。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-2E1 | `agent_loop.py` L2232–2352 |
| UC-2E2 | L2129–2379 |
| UC-2E3 | L1044/L2448 |
| UC-2E4 | L2421–2432 |
| UC-2E5 | `RuntimeHistoryOps`、`_commit_subagent_initial_turn`；异步 UI 与派生索引边界 |

## 5. 版本记录

- 2026-09-30 v3：明确本会话优化中必须同步完成的四类事实边界，区分指标/UI/索引派生工作与耐久提交。
- 2026-09-20 v2：修正写栅栏接管语义——旧 run 停止业务写但仍提交 `superseded_by_new_run` 唯一终态；控制边界收紧到 exact run。
- 2026-09-13 v1：拆分首版（原 UC-207 扩充成篇）。
