# 自动安全复核（替我审批） · 功能方案设计（UseCase 清单）

- 版本：2026-10-23 v2（审批材料按需构建）
- 用途：逐条审查（四字段格式）。
- 适用实现：`security/reviewer.py`（296 行）、`security/runtime.py`（auto_review 开关）、`tool_approval_gate`（合流）。
- 上级：`00-权限审批整体设计.md`

---

## 1. 功能定位

"替我审批"档的核心：让一个**安全复核模型**在用户不盯着屏幕时先看一遍。

## 2. UseCase

### UC-7D1 复核触发
- **触发**：替我审批模式下出现需授权操作。
- **预期现象**：复核自动进行（用户可见"复核中/已复核"状态）；无需用户操作。
- **依据**：`reviewer.py`、`security_settings()`（auto_review_enabled）。

### UC-7D2 复核结论三态
- **触发**：复核完成。
- **预期现象**：放行（直接执行）/ 拒绝（操作收尾并说明）/ **仍转人工**（弹卡，理由传递）；三态边界清晰。
- **规则与边界**：模型输出无法解析/超时 → 保守（转人工或拒绝）；复核是**建议**，最终审计同时记录复核与人工结论。
- **依据**：`reviewer` 结论合流（runtime + gate）。

### UC-7D3 复核上下文
- **触发**：复核需要背景。
- **预期现象**：复核能看到必要上下文（工具、参数、声明路径/域名、当前模式）；不看无关隐私内容（最小化）。
- **规则与边界**：每次工具仍先执行 `authorize_tool`。只有 ASK 或有效 Hook 审批才在 pending 之前重建/冻结材料；ALLOW 无审批时不读历史，DENY 直接返回。full_access 沿用既有规则忽略 Hook 审批要求。自动审查、转人工、人工覆盖和目录授权重试共用同一份材料，批准后仍重新绑定最终请求。主代理和子代理共用执行路径；没有跨调用复用可能过期的授权或审批上下文。
- **依据**：`agent_loop._build_tool_review_context / _execute_one_core`；`tests/test_tool_review_preparation.py`；[本地准备对照](../../performance/grep-queue-and-tool-preparation-2026-10-23.md)。

### UC-7D4 复核设置
- **触发**：开关"替我审批"相关的复核行为（auto_review_enabled 等）。
- **预期现象**：开关即时生效；关闭后该档回落到"全部人工或全部拒绝"的既定语义（以设置为准）。
- **依据**：`security_settings / update_security_settings`。

## 3. 边界

- 复核模型调用计入正常用量（属 ../01-LLM接入）；
- 复核**不改变**模式本身的含义（请求批准档不会触发复核）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-7D1/7D2 | `security/reviewer.py`、`tool_approval_gate.resolve_tool_approval_decision` |
| UC-7D3 | `agent_loop._build_tool_review_context` |
| UC-7D4 | `runtime.py` L1024–1041 |

## 5. 版本记录

- 2026-10-23 v2：仅在实际审批分支准备材料，去掉已允许/拒绝工具的无用历史读取；保留冻结时点、自动/人工/Hook审批及最终请求绑定。

- 2026-09-13 v1：拆分首版（承接 UC-705）。
