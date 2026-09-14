# 告警分级与错误卡 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `d022831` + 未提交告警改动）
- 用途：逐条审查（四字段格式）。**注意：本功能含 🟡 规划项，审查时勿按"应有"验收规划项。**
- 适用实现：`workspace/alert_spec_myagent/ALERT_SPEC.md`（v1.0，286 行）、`IMPLEMENTATION_20260912.md`、`agent_harness.py / agent_loop.py`（发出点）。
- 上级：`00-横切能力整体设计.md`

---

## 1. 功能定位

异常的"通知体系"：分级（L0–L3）、合并去噪、ephemeral/持久化区分，以及用户面前的错误卡。

## 2. UseCase

### UC-9C1 告警分级与目录 ✅
- **触发**：各类异常/状态发生。
- **预期现象**：告警按规范分级出现；目录涵盖 LLM-RETRY / LLM-DEGRADE / LLM-SWITCH / LLM-BUDGET / LLM-BLOCKED-SWITCH / LLM-RECOVERED / LLM-FAILED / NET-RETRY / NET-OFFLINE / NET-RESTORED / CTX-COMPRESS / CTX-FULL。
- **规则与边界**：`ephemeral` 类不写历史；持久化类参与回放。
- **依据**：`ALERT_SPEC.md` 目录章节。

### UC-9C2 合并去噪（coalesce）✅
- **触发**：同类告警连续发生（如多次重试）。
- **预期现象**：按 `coalesce_key` **原地更新**（计数/时间），不刷屏；run 结束有配平（recovered）。
- **依据**：`_emit_retry_status / _emit_blocked_switch_status`（coalesce_key 用法）。

### UC-9C3 已实现告警（现状）✅
- **触发**：重试 / 自动切换 / 预算阻断 / 网络重连。
- **预期现象**：LLM-RETRY（L1 轻提示）、模型自动切换状态、LLM-BLOCKED-SWITCH（L2）、NET-RETRY 依次正确出现并有对应恢复配平。
- **依据**：`agent_harness.py` L1173/L1384/L1433、`agent_loop.py` 重连段；`IMPLEMENTATION_20260912.md`（含测试与性能记录）。

### UC-9C4 规划中的告警 🟡
- **触发**：对冲（HEDGE）/ 预算将尽（BUDGET）/ CTX 满载（FULL）等场景。
- **预期现象**：**当前不会出现对应告警**（属规范待实现）；审查时按"无"预期。
- **规则与边界**：实现时机以 ALERT_SPEC 与实施记录为准；禁止把缺省当故障。
- **依据**：`ALERT_SPEC.md` §状态；`IMPLEMENTATION` 记录中的"后续项"。

### UC-9C5 错误卡分类 ✅
- **触发**：任务失败。
- **预期现象**：错误卡给出分类（NET / BUDGET / CTX / 429 / 5xx / OTHER）+ 下一步建议；与告警配对（如 NET-RETRY→NET-RESTORED 或最终失败）。
- **依据**：`_classify_api_error`（../02/07）+ WebUI 错误卡渲染。

### UC-9C6 与系统通知合并 ✅
- **触发**：run 结束时恰好有 LLM-FAILED 与 run_failed。
- **预期现象**：同 run 只产生**一次**桌面通知，文案取更具体者。
- **依据**：`ALERT_SPEC.md` §通知合并。

## 3. 边界

- 告警文案与级别细节以 ALERT_SPEC 原文为准（本节仅给审查坐标）；
- 告警变更需重启进程生效（历史实施备注）。

## 4. 依据映射

见上表。

## 5. 版本记录

- 2026-09-13 v1：拆分首版（原 UC-910/911 合并，明确 ✅/🟡 区分）。
