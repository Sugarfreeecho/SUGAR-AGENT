# 自动安全复核（替我审批） · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `d022831`）
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
- **依据**：`_build_tool_review_context`（agent_loop L468）、review 会话回放。

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

- 2026-09-13 v1：拆分首版（承接 UC-705）。
