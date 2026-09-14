# key_context 与恢复装配 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `d022831`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_loop.py`（装载/提交）、`app/agent_memory.py`（写入端）、`runtime_v2/history_ops.py`（commit_context_summary）。
- 上级：`00-ReAct运行时整体设计.md`

---

## 1. 功能定位

会话的"压缩记忆"入口：key_context（单一「## 上下文摘要」小节）如何被装载、注入、更新、恢复。

## 2. UseCase

### UC-2C1 每轮装载并注入
- **触发**：构建任意轮次的输入。
- **预期现象**：摘要稳定注入到系统侧（模型可见）；摘要不存在时静默跳过（新会话不报错）。
- **依据**：`_load_key_context_for_run / _load_runtime_v2_context_summary`。

### UC-2C2 压缩产物更新（更新制）
- **触发**：压缩产生新摘要（自动或手动）。
- **预期现象**：写入 key_context 的**同一小节内更新**（不重复堆叠历史摘要）；更新后下一轮即生效。
- **规则与边界**：更新是"单节替换"语义（append 会炸上下文，已被设计排除）；旧摘要可追溯（事件流里有 body 记录）。
- **依据**：`agent_memory._upsert_compress_summary_key_context`、`_runtime_v2_commit_context_summary`。

### UC-2C3 会话恢复装配
- **触发**：应用重启 / 会话切换 / 中断续跑。
- **预期现象**：摘要与历史一起正确恢复；"继续运行"入口可用（未完成任务不丢）。
- **依据**：`agent_loop.py` L1879+（V2 摘要读取）、恢复 runner（见 ../05-WebUI对话界面/07）。

### UC-2C4 手动编辑指令
- **触发**：用户/模型发起"编辑 key_context"指令。
- **预期现象**：按指令修改摘要（如精简、补充要点）；修改结果可见且可再编辑；与自动压缩互斥（会话锁）。
- **依据**：`agent_memory.run_edit_key_context_instruction`、`context_manage(mode="edit_key_context")`。

## 3. 边界

- 摘要**不是**"全量记忆"：只承载压缩要点；完整历史仍在事件流（可回放）。
- 压缩算法本体见 ../09-横切能力/01。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-2C1 | `agent_loop.py` L1879–1903 |
| UC-2C2 | `agent_memory.py` L1183+；`history_ops.py` L423 |
| UC-2C3 | `agent_loop.py` L1791–1879 |
| UC-2C4 | `agent_memory.py` L1201 |

## 5. 版本记录

- 2026-09-13 v1：拆分首版。
