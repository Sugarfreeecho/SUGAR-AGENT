# 错误分类与恢复路径 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v2（覆盖至：当前工作区）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_loop.py`（分类器 L4251–4509、恢复段 L7317+）。
- 上级：`00-ReAct运行时整体设计.md`

---

## 1. 功能定位

失败的"翻译层"：把异常翻译成可行动的分类（NET / CTX / BUDGET / 具体码），并驱动对应的恢复动作。

## 2. UseCase

### UC-2G1 链式分类（含原因链）
- **触发**：任意模型/网络/授权异常冒泡。
- **预期现象**：错误卡分类明确（NET / CTX / BUDGET / 429 / 5xx / OTHER）；文案给"下一步"；不落"未知错误"。
- **规则与边界**：沿 `raise ... from` 原因链逐层判定（叶子优先）；分类结果与告警联动（见 ../09-横切能力/03）。
- **依据**：`_classify_api_error / _classify_api_error_leaf / _iter_exception_chain / _format_exception_chain`。

### UC-2G2 上下文超限恢复
- **触发**：CTX 类错误（或预判超窗）。
- **预期现象**：强制压缩 → 重试一次；恢复窗口按报错中给出的真实窗口与配置取合理值；仍失败则明确报错。
- **规则与边界**：`_skip_compress` 防连跳（同一错误不无限压缩）；恢复只做一轮（bounded）。
- **依据**：`_context_limit_error_info / _context_limit_recovery_window`、agent_loop L4909+（forced_context_limit_compress）。

### UC-2G3 断网等待与重连
- **触发**：连通性失败。
- **预期现象**：与 LLM 模块 UC-1G1 联动——等待/重连提示；本机离线时不空转。
- **依据**：`machine_network_available / LocalNetworkUnavailableError`、`_wait_for_local_network_recovery`。

### UC-2G4 CPU 压力提示
- **触发**：本机 CPU 高压（如并行重任务）。
- **预期现象**：产生压力事件（本地过载提示），帮助解释"变慢"；不改变任务语义。
- **依据**：`_cpu_pressure_transition_event / _cpu_pressure_metrics_text`。

### UC-2G5 运行时辅助线程耗尽
- **触发**：心跳、观测刷盘、power guard 或生命周期异步追加遇到 `RuntimeError: can't start new thread`。
- **预期现象**：指标/观测后台能力非致命降级；生命周期事件改为同步追加，已经开始的 run 仍必须进入唯一终态。
- **规则与边界**：不能把诊断线程创建失败当作业务 run 的失败前置；若同步终态追加也失败，记录明确错误并完成其余指标/注册清理后再上抛。
- **依据**：`_RuntimeV2RunLifecycle.commit`、`execution_metrics._ensure_heartbeat_thread`、`runtime_observability._schedule_write`、`runtime_power.AgentRunPowerGuard`。

## 3. 边界

- 分类器**只分类不决策**：决策在各自的恢复路径（重试/压缩/等待/切换）。
- 部分告警级联（如 LLM-RETRY）以状态事件形式出现，不额外弹窗。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-2G1 | `agent_loop.py` L4251–4509 |
| UC-2G2 | L4305–4336、L4900+ |
| UC-2G3 | L3351、L7462+ |
| UC-2G4 | L237–327 |
| UC-2G5 | `_RuntimeV2RunLifecycle`、`execution_metrics.py`、`runtime_observability.py`、`runtime_power.py` |

## 5. 版本记录

- 2026-09-20 v2：新增 UC-2G5，辅助线程耗尽时观测降级但 run 终态必须收敛。
- 2026-09-13 v1：拆分首版（承接 UC-209/210/211）。
