# 出口守卫与 Shell 沙箱 · 功能方案设计（UseCase 清单）

- 版本：2026-10-21 v3（Windows票据标记长路径与失败分类）
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

### UC-7F5 Windows票据标记保持独占领取并支持长文件名

- **触发**：受控run_shell为每次执行签发新票据，helper在该run的TEMP内创建nonce标记；完整标记名可超过260字符。
- **预期现象**：签名、有效期和命令digest通过后，Windows helper以扩展Win32路径和`CreateFileW(CREATE_NEW)`原子创建标记；与原`FileMode.CreateNew`一样，只有一个执行能领取同一nonce。只有ERROR_FILE_EXISTS/ERROR_ALREADY_EXISTS报“已使用”，其他I/O错误明确失败并拒绝启动命令。
- **规则与边界**：不关闭出口隔离，不转为full access，不复用或删除生产nonce来重试。父目录不能创建时同样拒绝。受控临时目录清理先做原有归属/链接/存活租约检查，再以Windows扩展路径删除已确认归属的目录，支持原生子进程创建的长文件名；不扩大可删除根，持有lease的后台进程仍先结算。原AppContainer和网络规则保持。
- **依据**：`app/native/windows/SugarAgentEgressHelper.cs::ClaimNonce`、`runtime_files._remove_owned`；新增3项原生helper集成及2项长文件名/lease清理回归。原304字符标记首次误报已使用；修复候选在304/257字符路径上首次成功、重放仍拒绝。失败保留及性能补验见[10-21报告§8](../../performance/agent-subagent-interround-2026-10-21.md#8-完成审查追加写shell与持续巡检负载)。

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

- 2026-10-21 v3：新增UC-7F5；用扩展Win32路径保持nonce独占创建，区分真正重放与I/O失败，补齐已核验归属的临时目录长文件名清理。

- 2026-09-14 v2：补充 `enforce_leaf` 行号（runtime.py L981）并更新版本线至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-710 与出口守卫条目）。
