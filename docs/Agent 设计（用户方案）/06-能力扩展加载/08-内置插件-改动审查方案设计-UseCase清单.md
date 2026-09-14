# 改动审查 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：commit `3dfada4` 的撤销+恢复能力，及未提交的"临时写入全程隐身"修复）
- 用途：**逐条审查功能与现象是否符合需求**。每条用例给出「触发 → 预期现象 → 规则与边界 → 依据」。审查时按编号逐条勾选；如有不符，反馈编号即可。
- 适用插件：`plugins/change-review`（store.py / host.py / runtime.py / web/change-review.js）
- 所属：能力扩展加载模块 → 插件子系统 → 内置插件实例（本文件夹 08；配套通则见 01–07）

---

## 0. 阅读指南

每条 UseCase 的固定结构：

| 字段 | 含义 |
|---|---|
| **触发** | 谁做了什么操作（用户 / 模型 / 系统） |
| **预期现象** | 界面上应该看到什么（这是审查验收的核心） |
| **规则与边界** | 为什么是这个现象；什么情况下会不同 |
| **依据** | 代码位置或测试名（可复核） |

---

## 1. 功能定位与范围

**一句话**：以「执行过程（run）」为账本单位，对工作区改动做**净变更统计 + 安全撤销/恢复**。

**目标**：
1. 每轮执行过程内，谁（哪个工具）改了什么、改了多少行——可信、可对账；
2. 改动可以安全撤销（并可恢复），有冲突保护，不会误删文件。

**明确的非目标 / 已知边界**（详见 §9）：
- 非 Git 工作根下、经 shell/脚本/MCP 的改动不在观测面（全量扫描方案已撤除）；
- 不做跨 run 的自动累计（各轮各自结算，用户此前拍板的边界）；
- 不跟踪 `temporary=True` 文件（全程隐身，见 UC-107）。

**能力总览**：

| 能力 | 状态 |
|---|---|
| 变动行统计（真实增删口径） | ✅ |
| 单文件 / 整批撤销 | ✅ |
| 单文件 / 整批恢复（redo） | ✅ |
| 冲突保护（再修改即整批中止） | ✅ |
| 幂等重放 / 事务回滚 | ✅ |
| 二进制 / 大文件"未统计"如实展示 | ✅ |
| 快照留存与历史修剪联动 | ✅ |

---

## 2. 核心概念与数据模型

| 概念 | 含义 |
|---|---|
| **run（执行过程）** | 一次任务执行；统计与撤销的结算边界。同一 run 内同文件的多次修改**合并**为一条记录 |
| **快照（snapshot / record）** | 一条文件级记录：`before`（本轮起点状态）+ `after`（当前状态）+ diff + ± 行数 |
| **revision** | 记录被合并更新的次数（同 run 内每改一次 +1） |
| **effective** | 相对本轮起点是否还有净变化；改回原样 = `false`（界面上整条消失） |
| **reverted** | 已被撤销；界面上显示"已撤销"并可恢复 |
| **dropped** | 历史被修剪、永远不可再操作；其快照字节可被回收 |
| **temporaries（登记表）** | `temporary=True` 写入时登记"隐身路径"，三处采集源（Git 扫描 / 声明路径 / 删除）一律静默（见 UC-107） |
| **diff_omitted_reason** | 行数未统计的原因：`binary` / `too_large_bytes` / `too_many_lines` / `too_complex` / `directory` |
| **存储** | 会话目录下 `change_reviews/index.json` + `blobs/`（sha256 压缩块） |

---

## 3. 观测面：捕获类用例（UC-1xx）

### UC-101 Git 仓库 · tracked / 未忽略文件 · 任意工具修改
- **触发**：run 内任何工具（含 run_shell、脚本、MCP、Plugin）改动 Git 仓库里 tracked 或未忽略的未跟踪文件。
- **预期现象**：文件出现在审查列表，`+x −y` 与 `git diff --numstat` 一致；该行也可撤销。
- **规则与边界**：每 run 首次采集时用 `git ls-files -co --exclude-standard` 建立基线，结束时比对。
- **依据**：`store.py::_git_inventory / _ensure_workspace_baseline / finish_capture`；探针 A / C / J 场景。

### UC-102 Git 仓库 · 未忽略新文件 · shell/脚本创建
- **触发**：run_shell 或脚本在 Git 仓库新建未忽略文件。
- **预期现象**：记录为 `create +N −0`。
- **依据**：`finish_capture` 工作区扫描；探针 C 场景。

### UC-103 Git 仓库 · 被忽略文件 · 原生文件工具
- **触发**：`write_file` / `edit_file` / `apply_patch` / `delete_file` 直接修改被 `.gitignore` 忽略的文件（如 `logs/x.log`）。
- **预期现象**：**可见**（走"声明路径"采集），修改/删除都能显示、可撤销。
- **规则与边界**：与 UC-104 对照——同一个忽略文件，用 shell 改不可见、用原生工具改可见（双轨，属已知边界）。
- **依据**：`begin_capture::_target_specs`；探针 K 场景。

### UC-104 Git 仓库 · 被忽略文件 · shell/MCP 修改
- **触发**：shell/脚本/MCP 修改被忽略文件。
- **预期现象**：**不可见**（Git 策略面之外，也无声明路径）。
- **规则与边界**：设计保留项（尊重 `.gitignore` 策略）。
- **依据**：探针 B 场景。

### UC-105 非 Git 工作根 · 原生文件工具
- **触发**：在不是 Git 仓库的工作根（含默认 `workspace/`）用 `write_file` 等原生文件工具改文件。
- **预期现象**：可见（声明路径兜底：创建/修改/删除均可显示、可撤销）。
- **依据**：`begin_capture` 声明路径分支；探针 E 场景、`test_non_git_workspace_observes_declared_file_tools_only`。

### UC-106 非 Git 工作根 · shell / 脚本 / MCP
- **触发**：非 Git 根下经 shell/脚本/MCP 的改动。
- **预期现象**：**不可见**（当前最大盲区）。
- **规则与边界**：全量扫描方案曾填补此缺口、后按决策撤除（成本约 2s/步 + 复杂度）。**这是取舍，不是故障**。
- **依据**：探针 D 场景。

### UC-107 temporary=True 写入
- **触发**：模型用 `write_file(temporary=True)` 写中间产物。
- **预期现象**：**全程隐身**——后续无论被 `delete_file` 删除、被 shell 删除、还是回合末自动清理，审查里都不出现任何行。
- **规则与边界**：
  - 写前登记"最初起点"；若该路径**后来被正常写**（不带 temporary），则"毕业"为正常记录——显示从最初起点起的累计 diff（撤销可回到最初内容）；
  - 首次登记为 missing 的路径毕业后显示为 `create`（含全部内容）。
- **依据**：`store.py::_register_temporary / begin_capture / finish_capture`；测试 `test_temporary_write_and_delete_stay_invisible_even_in_git` 等 4 例。

### UC-108 目录删除（delete_file 作用于目录）
- **触发**：`delete_file` 删除一个目录（含文件与空子目录）。
- **预期现象**：目录内**每个文件一行**（`delete −N`）；纯空目录显示一行"目录结构"（±0，标注 directory）。撤销后文件与空目录都恢复。
- **依据**：`_target_specs` 目录展开 + `groups`；`test_directory_delete_restores_files_and_empty_directories`、`test_directory_delete_restore_round_trip`。

### UC-109 同 run 同文件多次修改
- **触发**：同一执行过程中多次改同一文件。
- **预期现象**：审查列表里**只保持一行**，数字是相对**本轮起点**的累计净额；内部 revision 递增。
- **依据**：`active_key = run_id + "\0" + path_key` 合并逻辑；`test_same_round_same_file_is_cumulative`。

### UC-110 净零（改回原样）
- **触发**：同一 run 内先改、又改回完全一致的内容。
- **预期现象**：该行**整条消失**（不参与汇总）。
- **规则与边界**：与"未统计"不同——是"确实没有净变化"。
- **依据**：`effective=false` 过滤；`test_same_round_return_to_baseline_is_not_undoable`。

### UC-111 跨 run
- **触发**：run1 改 +2，run2 又改 +3。
- **预期现象**：各轮各自结算；run2 的桶显示相对 run2 起点的 +3，**没有跨轮累计**；撤销也只回各自 run 的起点。
- **规则与边界**：口径决策（按 run 为边界）。会话级合计未实现（可选后续项）。
- **依据**：探针 F 场景；`probe_cross_run_undo.py`。

### UC-112 二进制 / 超大 / 超行数 / 过于复杂
- **触发**：文件为二进制、>1 MiB、>20,000 行或差异匹配超预算。
- **预期现象**：文件**计数存在**、行数显示"未统计"，tooltip 给出原因（二进制 / 超过 1 MiB / 超 20,000 行 / 改动过于复杂）；撤销仍可用（快照字节保留）。
- **依据**：`_diff / _text_info`；`test_binary_and_large_file_omit_line_diff`。

### UC-113 行尾（CRLF/LF）
- **触发**：文件换行风格差异（如整文件 CRLF 重写）。
- **预期现象**：审阅 diff 归一展示（不因换行风格炸出全文件 diff）；字节级快照保留，撤销还原原始字节。纯换行风格变化行数统计约 0。
- **依据**：`_text_info` 注释与实现；`test_text_diff_normalizes_line_endings_...`、`test_same_round_text_return_to_baseline_...`。

### UC-114 工具失败 / 部分写入
- **触发**：工具执行失败但文件实际被部分改动。
- **预期现象**：按**实际落盘状态**记录（不虚构成功）；无实际变化则无行。
- **依据**：`test_noop_has_no_change_but_failed_tool_reports_actual_partial_write`。

### UC-115 MCP / Plugin 工具（observe_workspace）
- **触发**：MCP/插件工具执行（带 `observe_workspace=True`）。
- **预期现象**：与 shell 同级——Git 仓库可见、非 Git 不可见。
- **依据**：`agent_loop.py` 采集挂接；`test_runtime_callback_can_observe_an_unknown_external_tool`。

---

## 4. 统计口径用例（UC-2xx）

### UC-201 行数 = 真实增删（最小差异）
- **触发**：任意记录生成。
- **预期现象**：`+added −removed` 只统计**真实新增/删除行**（不包含上下文行）；与 `git diff --numstat` 口径一致。
- **依据**：`_diff`（difflib opcodes 统计）；探针 A 与 git numstat 对账一致。

### UC-202 与 apply_patch 工具输出对账（预期差异）
- **触发**：拿单次 `apply_patch` 结果文本的 `(+N −M)` 对比面板。
- **预期现象**：**净增必然一致**；两侧数字可能不同——工具数的是**补丁文本**的 ± 行（含"重写但未变化"的行），面板数的是**内容最小差异**。
  - 例 1（2 行原样保留、顺序不变）：工具 `+7 −2`，面板 `+5 −0`；
  - 例 2（同样 2 行顺序颠倒）：工具 `+7 −2`，面板 `+6 −1`；
  - 例 3（7 行全不同）：工具 `+7 −2`，面板 `+7 −2`（完全一致）。
- **规则与边界**：每有一条"重写未变化"的行对，面板两侧比工具各少 1。**这是口径差，不是错误**。
- **依据**：`agent_tools.py::apply_patch`（计数实现）；`workspace/.../run_patch_identity_probe.py` 实测。

### UC-203 汇总与口径提示
- **触发**：查看列表头部/徽标的汇总。
- **预期现象**：显示"N 个文件 · +x −y（· M 个文件未统计行数）（· K 已撤销）"；悬停 tooltip 说明"本轮净变更、同文件合并、已还原不计入"，并逐项列出未统计原因与数量。
- **依据**：`change-review.js::setSummary / statsTitle`。

### UC-204 流程聚合徽标
- **触发**：展开某个执行过程。
- **预期现象**：过程标题旁徽标显示该轮的 `+x −y`；全部撤销后徽标消失；存在已撤销行时附加"· K 已撤销"。
- **依据**：`updateBadge`。

---

## 5. 撤销用例（UC-3xx）

### UC-301 单文件撤销
- **触发**：某行点"撤销 → 确认"。
- **预期现象**：文件内容恢复为本轮起点状态（创建→文件删除；修改→内容还原；删除→文件恢复）；该行变为"已撤销"样式并出现"恢复"按钮。
- **依据**：`store.py::undo`；`host.py` undo 路由；`test_create_modify_delete_and_undo`。

### UC-302 整批撤销（全部撤销）
- **触发**：面板底部"全部撤销"。
- **预期现象**：本轮所有活动行一起还原；**全有或全无**——任一文件冲突则整批取消（一个都不动），并列出冲突文件路径。
- **依据**：`undo(snapshot_ids=[...])` 批次语义；`test_batch_conflict_aborts_without_restoring_any_file`。

### UC-303 冲突保护（再修改）
- **触发**：改动之后、撤销之前，文件被再次修改（任何来源）。
- **预期现象**：撤销被拒绝，提示"文件已再次修改，撤销已中止"，并列出路径；文件保持现状。
- **依据**：`undo` 的前置校验（current == record.after）；同上测试。

### UC-304 幂等重放
- **触发**：同一撤销请求（同 operation_id）重复发送。
- **预期现象**：不重复执行，返回 `idempotent_replay: true` 与首次结果。
- **依据**：`operations` 日志；`test_create_modify_delete_and_undo` 尾部断言。

### UC-305 事件持久化失败时回滚（事务）
- **触发**：撤销后写 UI 事件 / 通知失败（内部异常）。
- **预期现象**：文件内容**放回撤销后状态**，记录恢复为活动；不留下半吊子状态。
- **依据**：`rollback_undo`；`test_prepared_undo_can_roll_back_when_event_commit_fails`。

### UC-306 撤销边界 = run
- **触发**：跨 run 的场景（run1 +2，run2 +3）。
- **预期现象**：只能按各 run 的记录撤销；撤回 run2 到 run2 起点（仍是 run1 之后的状态），再撤 run1 才回到最初始。
- **规则与边界**：先撤 run1 会被冲突保护拒绝（文件当前状态 ≠ run1 记录的后态）。
- **依据**：`probe_cross_run_undo.py` 实测。

### UC-307 任务运行中禁用
- **触发**：会话（含子代理、同工作区）正在运行时点击撤销。
- **预期现象**：按钮禁用；API 返回 409 `task_running`；工作区锁与二次检查防止竞态。
- **依据**：`host.py` 双重检查 + 工作区互斥；`change-review.js::isRunning`。

### UC-308 各类操作的撤销效果
- **触发**：分别撤销 create / modify / delete(含目录) 记录。
- **预期现象**：创建→删除文件；修改→还原内容；删除→恢复文件（含空目录结构，目录全批选中时修复目录树）。
- **依据**：`_restore_record` + `groups` 目录修复；`test_directory_delete_restores_files_and_empty_directories`。

### UC-309 历史截断后不可撤销
- **触发**：会话历史被编辑/截断，记录失去引用被修剪（dropped）。
- **预期现象**：对应行不再展示；陈旧视图中的撤销尝试会失败（快照已不可用）。
- **依据**：`prune_unreferenced`（标记 dropped）；`test_branch_copy_and_truncation_cleanup_...`。

---

## 6. 恢复（redo）用例（UC-4xx）

### UC-401 单文件恢复
- **触发**：对"已撤销"行点"恢复 → 确认"。
- **预期现象**：改动被**重新应用**（文件回到工具修改后的内容）；行恢复为活动样式（可再撤销）。
- **依据**：`store.py::restore`；`test_undo_then_restore_round_trip`。

### UC-402 整批恢复（全部恢复）
- **触发**：面板底部"全部恢复"。
- **预期现象**：所有已撤销行一起重新应用；仍为**全有或全无**。
- **依据**：`restore` 批次语义；`test_restore_api_reapplies_and_persists_ui_event`。

### UC-403 恢复冲突保护
- **触发**：撤销之后、恢复之前，文件被再次修改。
- **预期现象**：恢复被拒绝，提示"文件已再次修改，恢复已中止"并列出路径；不做部分应用。
- **依据**：`restore` 校验（current == record.before）；`test_restore_conflict_aborts_without_touching_files`。

### UC-404 恢复的幂等重放
- **触发**：同 operation_id 重复恢复请求。
- **预期现象**：返回 `idempotent_replay: true`，不重复执行。
- **依据**：journal 键 `restore:<opid>`；`test_undo_then_restore_round_trip`。

### UC-405 恢复失败回滚
- **触发**：恢复后事件/通知持久化失败。
- **预期现象**：字节放回撤销后状态、记录回到"已撤销"；不残留半状态。
- **依据**：`rollback_restore`；`test_prepared_restore_can_roll_back_when_event_commit_fails`。

### UC-406 撤销提交后仍可恢复（快照留存）
- **触发**：撤销完成后（事件已落库）再点恢复。
- **预期现象**：可以恢复——已撤销记录的 before/after 快照会**保留到历史修剪**为止；只有 dropped / 净零记录的快照会被回收。
- **依据**：`_gc_blobs` 保留策略；`test_undo_then_restore_round_trip`（含 commit 后恢复）。

### UC-407 记录彻底失效后恢复被拒
- **触发**：对已被修剪（dropped）的快照尝试恢复。
- **预期现象**：报"快照不可恢复"（410 `snapshot_gone`），不动文件。
- **依据**：`restore` 校验 + `test_pruned_records_cannot_be_restored`。

### UC-408 目录/空目录恢复闭环
- **触发**：删除目录 → 撤销（文件+空目录回来）→ 恢复（再次消失）。
- **预期现象**：目录、空目录、嵌套结构三者状态与操作顺序完全对称。
- **依据**：`test_directory_delete_restore_round_trip`。

---

## 7. 存储与生命周期用例（UC-5xx）

### UC-501 快照存储
- **触发**：记录创建/更新。
- **预期现象**：内容以 sha256 内容寻址的压缩块存于 `blobs/`；索引原子写入；内容损坏时按"快照丢失"处理而不是静默错误。
- **依据**：`_put_blob / _get_blob / _atomic_json`。

### UC-502 回收（GC）策略
- **触发**：撤销提交、run 结束、历史修剪等节点。
- **预期现象**：活动记录、已撤销待恢复记录、临时登记表的快照保留；dropped / 净零记录的快照回收。磁盘不随时间无界增长。
- **依据**：`_gc_blobs`。

### UC-503 会话分支复制
- **触发**：从某会话分支出新会话。
- **预期现象**：被引用的记录、快照**及临时登记表**一起复制，分支里撤销/恢复行为一致。
- **依据**：`copy_referenced_to`。

### UC-504 历史修剪
- **触发**：历史截断/编辑。
- **预期现象**：不再被引用的记录标记 dropped（不可再撤销/恢复），快照随 GC 回收。
- **依据**：`prune_unreferenced`；`runtime.py::history_truncated`。

### UC-505 基线清理
- **触发**：run 结束。
- **预期现象**：该 run 的工作区基线归档被清理；记录不受影响。
- **依据**：`finish_run`。

---

## 8. 前端呈现用例（UC-6xx）

### UC-601 列表与徽标
- **触发**：执行过程完成且有改动。
- **预期现象**：过程标题旁徽标显示 `+x −y`；展开后出现审查面板；无净变化则无徽标。
- **依据**：`updateBadge / activeRows`。

### UC-602 布局自适应
- **触发**：窗口宽窄变化 / 多个过程可见。
- **预期现象**：宽屏显示为侧栏（文件选择器），窄屏收起为底栏"改动审查 · 查看"；以视口内可见的过程优先展示；弹层展示完整列表与操作。
- **依据**：`hasRoom / updatePlacement / chooseVisibleChangeReviewIndex / viewportAggregate`。

### UC-603 行内 diff 展开
- **触发**：点击文件行。
- **预期现象**：懒加载展开统一 diff（+绿 −红、hunk 头、上下文行）；未展开的不构建 DOM（大历史不卡）。
- **依据**：`renderFile / renderDiff / body.dataset.rendered`。

### UC-604 已撤销行的展示
- **触发**：撤销成功后。
- **预期现象**：该行**保留在列表**、置灰、带"已撤销"标签，按钮由"撤销"变为"恢复"；汇总追加"· K 已撤销"。
- **依据**：`renderFile / splitReviewRows / setSummary`。

### UC-605 批量操作按钮
- **触发**：面板底部。
- **预期现象**："全部撤销"作用于活动行、"全部恢复"作用于已撤销行；两者都带确认弹窗与作用范围 tooltip；任务运行中禁用。
- **依据**：`renderReviewHost`。

### UC-606 实时更新与跨会话隔离
- **触发**：工具完成、撤销/恢复事件、切换会话、历史加载。
- **预期现象**：数字即时更新（事件驱动，无需刷新）；撤销/恢复会同步至所有打开的视图与子代理视图；不同会话互不串扰。
- **依据**：`applyTool / markReverted / markRestored / onUiEvent / resetForSession / scanExisting`；事件 `file_changes_reverted / file_changes_restored`。

### UC-607 "未统计"显示
- **触发**：二进制/超限等记录。
- **预期现象**：单行显示"未统计"并可悬停看原因；汇总显示"· M 个文件未统计行数"；**不会**显示成 `+0 −0`。
- **依据**：`hasLineStats / omittedText / stats`；`tests/js/change_review_stats_runtime.mjs`。

### UC-608 历史回放
- **触发**：打开含历史的会话。
- **预期现象**：历史消息里的改动记录（含已撤销/已恢复状态）正确重建；懒渲染过程体，展开时才扫描。
- **依据**：`scanExisting / applyTool`；`file_changes_reverted/restored` 回放。

---

## 9. 已知边界与设计取舍（UC-7xx）

### UC-701 非 Git / 忽略文件的 shell 盲区
- **现象**：这类改动在审查中完全不可见（见 UC-104 / UC-106）。
- **定性**：**已知取舍**（全量扫描因成本与复杂度撤除；四家参考实现同样不做全量扫描）。不计入"故障"。
- **可选项**：后续若要覆盖，需按工具级捕获或影子快照方案重新设计。

### UC-702 大文件只"未统计行数"，不失去撤销
- **现象**：行数省略，但撤销/恢复可用（快照完整）。
- **例外**：仅历史遗留的 snapshot_missing 数据不可操作。
- **依据**：`_diff` 省略逻辑与 blob 留存。

### UC-703 temporary 毕业规则
- **现象**：临时文件永不出现；一旦被正常写保留，则从"最初起点"起一次性补全累计记录。
- **边界**：shell 删除临时路径后登记条目可能保留到该路径再次被正常使用（会话级、有界，不影响统计）。

### UC-704 与 `git numstat` 对账
- **做法**：Git 仓库内，把面板各行 ± 与 `git diff --numstat` 对比——应逐字一致（被忽略/临时路径除外）。
- **注意**：对账对象是"面板 vs numstat"，不是"面板 vs 工具文本"（后者见 UC-202）。

### UC-705 与工具文本对账
- **做法**：只对**净增**（added−removed）与工具文本比；两侧数字差异先看补丁里是否有"重写未变化"的行对（每对差 2）。

---

## 10. 测试覆盖映射（可复核）

| 用例 | 测试 / 探针 |
|---|---|
| UC-101/102/109/110/114 | `test_git_process_baseline_*`、`test_same_round_*`、`test_noop_has_no_change_*` |
| UC-103/105 | `test_gitignore_change_*`、`test_non_git_workspace_observes_declared_file_tools_only`、`probe K/E` |
| UC-104/106 | `probe B/D`（预期为空） |
| UC-107 | `test_temporary_write_and_delete_stay_invisible_even_in_git` 等 4 例、`run_temp_delete_probe(.4).py` |
| UC-108/308/408 | `test_directory_delete_restores_files_and_empty_directories`、`test_directory_delete_restore_round_trip` |
| UC-112/113 | `test_binary_and_large_file_omit_line_diff`、`test_text_diff_normalizes_line_endings_*` |
| UC-115 | `test_runtime_callback_can_observe_an_unknown_external_tool` |
| UC-201/202 | `probe_change_review_stats.py`、`run_patch_identity_probe.py` |
| UC-301~309 | `test_create_modify_delete_and_undo`、`test_batch_conflict_*`、`test_undo_api_*`、`probe_cross_run_undo.py` |
| UC-401~408 | `test_undo_then_restore_round_trip`、`test_restore_*`、`test_prepared_restore_*` |
| UC-502/503/504 | `test_branch_copy_and_truncation_cleanup_*`、`test_workspace_cache_*` |
| UC-601~608 | `tests/js/change_review_stats_runtime.mjs`、`change_review_visibility_runtime.mjs`、`test_plugin_ui_frontend.py` |
