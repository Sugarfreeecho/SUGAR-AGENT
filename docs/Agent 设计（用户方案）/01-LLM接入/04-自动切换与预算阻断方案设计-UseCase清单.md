# 自动切换与预算阻断 · 功能方案设计（UseCase 清单）

- 版本：2026-09-18 v2（覆盖至：HEAD `1fd80ca` + 运行中切换修复）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_harness.py`（`_FallbackCompletions` 全链路）、`app/model_profiles.py`（候选链）。
- 上级：`00-LLM接入整体设计.md`

---

## 1. 功能定位

当前模型无法继续时，按**候选链**自动切换并**续跑**任务；当预算不足时，明确阻断而不是假装切换。

## 2. UseCase

### UC-1D1 自动候选切换（LLM-SWITCH）
- **触发**：当前模型重试耗尽（或不可重试类失败），候选链上还有备选档案。
- **预期现象**：状态区出现「【模型自动切换】…→（备选）」类提示；任务以新模型继续；同 run 内提示不刷屏；切换历史可查；接管成功后会话绑定改写为实际服务的档案（右下角选择器随事件流刷新）。
- **规则与边界**：切换是"续跑"——已完成轮次/工具结果不重放；候选链顺序 = 档案面板排序；同 run 内已失败的候选会被熔断跳过（"本轮运行跳过已失败模型"），**手动切换会清空该会话 live run 的熔断记录**使其立即重试（见 05·UC-1E1/1E4）；无备选时直接进入失败路径（错误分类见 UC-2xx）。
- **依据**：`agent_harness.py::_FallbackCompletions`（候选链驱动）、`_emit_model_switch_status`、`model_profiles.fallback_chain()`。

### UC-1D2 预算阻断（LLM-BLOCKED-SWITCH）
- **触发**：需要切换，但共享预算（UC-1C3）已耗尽。
- **预期现象**：L2 告警「切换被预算阻断」，任务以明确错误结束；不发送任何"切换后请求"。
- **规则与边界**：保留原因链（raise ... from last_error），错误卡正确分类（BUDGET 而非"未知"）；此为已实现告警（与 🟡 的 LLM-BUDGET 不同——后者是"预算将尽"的事前提醒，仍未实现）。
- **依据**：`_emit_blocked_switch_status`（coalesce_key=LLM-BLOCKED-SWITCH）、`_raise_budget_exhausted_before_fallback`、alert_spec 实施记录。

## 3. 边界

- 切换目标**媒体能力**可能与原模型不同 → 自动触发媒体降级（见 05 / ../09-横切能力/02）。
- 自动接管会把**会话档案绑定**改写为实际服务的档案（下次请求与右下角选择器都以它为准）；若期间发生更新的手动切换（选择纪元变化），接管不覆盖该选择，原失败档案仍留在候选链中可再次兜底（见 05·UC-1E1/1E4）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-1D1 | `agent_harness.py` `_FallbackCompletions` / `_emit_model_switch_status` |
| UC-1D2 | `agent_harness.py` L1433 附近（LLM-BLOCKED-SWITCH） |

## 5. 版本记录

- 2026-09-13 v1：拆分为独立功能（原在切换大类中，与手动切换分离）。
- 2026-09-18 v2：对齐运行中切换修复——补熔断跳过与"手动切换清熔断"、fallback 接管改写绑定及其选择纪元守卫（见 05·UC-1E1/1E4）。
