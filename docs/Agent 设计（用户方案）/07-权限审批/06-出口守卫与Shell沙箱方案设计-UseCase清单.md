# 出口守卫与 Shell 沙箱 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `d022831`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`security/egress_guard.py`（172 行）、`security/shell_analysis.py`（403 行）、`security/policy.py`、`security/models.py`（SandboxProfile / SandboxHealth）。
- 上级：`00-权限审批整体设计.md`

---

## 1. 功能定位

两类"形状更复杂"的授权对象：**网络出口**（去哪）与 **Shell 命令**（做什么）——先分析、再决策。

## 2. UseCase

### UC-7F1 出口意图分析
- **触发**：外联类工具（web_fetch 等）进入授权。
- **预期现象**：目标被解析为结构化出口意图（EgressIntent/约束），据此匹配预批准清单/模式；内网目标始终拒绝（SSRF 联动 ../03-工具系统/05）。
- **依据**：`egress_guard.py`、`models.EgressIntent / EgressConstraint`。

### UC-7F2 命令分段分析
- **触发**：run_shell 进入授权。
- **预期现象**：命令被切分为片段并分类（读/写/网络/高危），产出 ShellAnalysis；决策据此而非"整串字符串"。
- **规则与边界**：无法解析的片段保守处理；分析结果进入审计。
- **依据**：`shell_analysis.py`、`models.CommandSegment / ShellAnalysis`。

### UC-7F3 沙箱画像与健康
- **触发**：查看安全状态 / 启动时自检。
- **预期现象**：展示沙箱画像（SandboxProfile）与健康状态（SandboxHealth）；不健康时给出建议。
- **依据**：`models.SandboxProfile / SandboxHealth`、`execution_scope`。

### UC-7F4 执行边界强制
- **触发**：执行路径上的最后一道校验。
- **预期现象**：`enforce_leaf` 在叶子动作上落实边界（路径/资源）；违规即拒绝（带原因）。
- **依据**：`enforce_leaf`。

## 3. 边界

- 命令"危险模式"识别（文本层）在 ../03-工具系统/02；本篇是其**结构化升级版**：两者叠加生效。
- 策略库（policy.py）是规则数据的家——新增规则不需要改代码路径。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-7F1 | `egress_guard.py`、`web_preapproved.py` |
| UC-7F2 | `shell_analysis.py`、`policy.py` |
| UC-7F3/7F4 | `models.py` L26–155、`runtime.py` L900–960（`enforce_leaf` 见 L981） |

## 5. 版本记录

- 2026-09-14 v2：补充 `enforce_leaf` 行号（runtime.py L981）并更新版本线至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-710 与出口守卫条目）。
