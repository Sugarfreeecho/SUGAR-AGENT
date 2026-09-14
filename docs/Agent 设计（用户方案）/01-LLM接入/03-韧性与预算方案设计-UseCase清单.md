# 韧性与预算（重试 / 对冲 / 预算 / 时限） · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_openai.py`（主战场）、`app/agent_harness.py`（分类联动）。
- 上级：`00-LLM接入整体设计.md`

---

## 1. 功能定位

单次"逻辑请求"内部的工程韧性：同模型重试 → 首 token 对冲 → 共享预算与时限护栏，确保**要么拿到结果，要么明确失败**。

## 2. UseCase

### UC-1C1 同模型重试
- **触发**：瞬时错误（429/5xx/连接抖动/流中断）。
- **预期现象**：自动重试（≤4 次、1s 起的退避）；界面仅见轻量状态（LLM-RETRY 提示，见 ../09-横切能力/03）；模型不切换。
- **规则与边界**：认证失败/参数错误等**不可重试**类不做重试；重试耗尽才进入候选切换（见 04）。
- **依据**：`agent_openai.py`（OPENAI_MAX_RETRIES、`_is_retriable_openai_error`）、`_emit_retry_status`。

### UC-1C2 首 token 对冲（hedge）
- **触发**：主请求发出后 30s 未达首 token。
- **预期现象**：并行发起备用请求竞速，先出内容者胜出，败者取消；用户只感知"更慢但成功的一次回答"。
- **规则与边界**：对冲仅在"无任何首 token"时触发；已开始输出的流不会被替换；对冲请求**计入**共享预算；可配置关闭/调参。
- **依据**：`agent_openai.py`（OPENAI_FIRST_TOKEN_HEDGE_TIMEOUT_SEC=30.0、hedge 逻辑、loser cancel）。

### UC-1C3 共享逻辑请求预算
- **触发**：一次逻辑请求内发生 重试+对冲+后续 的组合。
- **预期现象**：物理请求总数 ≤ 6（默认）；到顶后受控终止（错误文案明确），绝不无限重试。
- **规则与边界**：预算被 **hedge/重试/fallback 三路共摊**；预算不足时的切换尝试会变成 `LLM-BLOCKED-SWITCH`（见 04）。
- **依据**：`agent_openai.py::_LogicalRequestBudget`、`agent_harness._raise_budget_exhausted_before_fallback`。

### UC-1C4 截止与并发上限
- **触发**：模型长时间无响应 / 并发会话增多。
- **预期现象**：总截止 600s 到点终止；同 Provider in-flight ≤3（排队而非夯死）；取消（用户停止）即时传播到对冲/流。
- **依据**：`agent_openai.py`（OPENAI_TOTAL_DEADLINE_SEC=600.0、OPENAI_MAX_INFLIGHT_REQUESTS=3、取消链）。

## 3. 边界

- 调参：重试次数/对冲阈值/预算/截止均可环境变量调整（BX-06）；调小省时、调大容错。
- 对冲存在极端浪费（两个请求都收费的窗口）——属成本换取稳定性的取舍，默认开启且可关。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-1C1 | `agent_openai.py` L234–311 |
| UC-1C2/1C3/1C4 | `agent_openai.py`（run_nonstream/run_stream worker 段） |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-104~107）。
