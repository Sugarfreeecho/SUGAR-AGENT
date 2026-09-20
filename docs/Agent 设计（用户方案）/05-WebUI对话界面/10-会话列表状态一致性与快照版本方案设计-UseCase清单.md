# 会话列表状态一致性与快照版本 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v1（覆盖至：HEAD `1d9e1b0`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`modules/session-management.js`、`state/session-store.js`、`state/session-actions.js`、`app/webui.py`（`/sessions/state` 快照与其写接口）、`app/agent_harness.py`（SessionManager 摘要写入与状态广播）。
- 上级：`00-WebUI对话界面整体设计.md`
- 关联：`06-会话档案与技能面板方案设计-UseCase清单.md`（UC-5F1 会话管理操作面）；`03-SSE管道与断线续看方案设计-UseCase清单.md`（事件流、重连与对账）。

---

## 1. 功能定位

侧栏会话列表的**状态一致性契约**：改名 / 归档 / 置顶 / 设为待办这类"元数据编辑"，一旦服务端确认，就不能被随后到达的轮询快照回滚。为此约定两条：**服务端快照带版本**（`state_revision`），**客户端只接受不早于已提交写入的快照**。

## 2. 问题与设计

### 2.1 现象（用户反馈）

在侧栏对会话执行改名 / 归档 / 置顶 / 设为待办后：

1. 操作立即生效（名称、分组、徽标、排序都正确）；
2. 数秒后**自行回退**为操作前的样子（旧名称、归档项重新出现在普通列表、置顶/待办消失），并伴随排序位置跳动；
3. 再过一段时间**自行恢复**为新值并保持稳定；
4. 全程无报错、无 toast；磁盘与内存索引里始终是新值（刷新或重启后即为新值）。

### 2.2 根因（代码结论）

1. **服务端"失效但继续发旧值"**：`/sessions/state` 为压低轮询开销设有 5 s TTL 的 stale-while-revalidate 缓存（`_SESSIONS_STATE_TTL_SEC`）。元数据写接口调用 `_invalidate_sessions_state_cache()` 时只把 `ts` 置 0、**保留 `payload`**，于是变更后的第一次请求收到的仍是变更前构建的快照，只由后台线程去重建。
2. **重建结果可被丢弃**：重建结果带 generation 校验；若期间又发生一次失效（`run_started / final / run_finished` 等生命周期事件同样会失效），这次重建被丢弃，旧快照继续对外发，抖动被拉长。
3. **客户端全量覆盖**：`applySessionSnapshot → sessionStore.applySnapshot` 用 `Object.assign({}, s)` 整条替换并立即重排，对 `name / pinned / pinned_at / todo / archived` 没有任何本地优先逻辑；既有保护只覆盖"新建会话"（`snapshotProtectedSessions`）与"已删除"（`deletedSessionTombstones`）。
4. **新旧请求竞态**：客户端此前只用 `client_request_seq` 比较先后，没有"这份数据是否比本地新"的概念——变更前已发出、变更后才落地的快照同样会把新值盖回旧值。
5. **旁路写入不失效**：自动命名（Agent 生成标题）、远程控制改名、自动归档扫描等不经过菜单的写入，此前不通知快照缓存，存在最长 5 s 的陈旧窗口。

### 2.3 设计（本次修复）

- **A. 服务端硬失效 + 单飞重建**（`app/webui.py`）：失效时把两个变体（`include_archived=true/false`）的 `payload` 直接置 `None`（仅保留 `ts=0`），下一个读者在 per-variant 构建锁内**同步重建**；冷路径改为循环——若这次扫描跨越了一次新失效，则按新版本重扫，**绝不把跨变更的响应发出去**。
- **B. 快照版本协议**（`state_revision`）：进程内单调计数器（`_sessions_state_cache_generation`，初值 `int(time.time()*1000)`，每次失效 +1）在构建快照时写入 `payload["state_revision"]`；六类写接口（新建、删除、改名、归档、置顶、待办）在响应体回传同一值。
- **C. 全路径失效广播**（`app/agent_harness.py`）：SessionManager 新增 `add_session_state_listener / _notify_session_state_changed`，在 `created / name / pinned(+pinned_at) / todo / archived（含自动归档扫描） / goal_review_pending` 的写入点广播；`webui` 在导入时注册失效回调。于是**不经过菜单的写入路径同样让快照失效**。
- **D. 客户端三道闸门**（`state/session-store.js`、`state/session-actions.js`）：`applySessionSnapshot` 入口先经 `shouldAcceptSnapshot` 判定——① **写入在途期间**拒收任何快照（乐观行不被覆盖）；② **客户端请求下界**：提交写入时把 `committedSnapshotRequestFloor` 抬到当前 `snapshotRequestSeq`，更早发出的请求一律丢弃；③ **版本下界**：`state_revision` 低于 `committedStateRevisionFloor` 的快照丢弃。
- **E. 写入流程与失败回滚**（`modules/session-management.js`）：四个菜单动作统一为"begin → 乐观更新 → PUT（12 s 超时）→ commit（携带响应 `state_revision`）→ 单行刷新"，同时 bump 列表/归档加载代次以作废在途加载；**仅当写入本身失败**才 cancel + 还原旧值（修复前失败与陈旧响应都会回滚，无法区分）。

### 2.4 明确边界与已知取舍

- ⚪ **代价**：变更后的第一次读取会同步重建（本机实测：默认视图 78 会话 ≈ 0.16 s；含归档 345 会话 ≈ 1.0 s，其中 `pending_counts` ≈ 0.69 s）。稳态轮询仍命中 5 s TTL 缓存，不受影响。
- ⚪ **在途写入期间所有快照都被拒收**（含 run-state 快照），上限为 PUT 的 12 s 超时；这是有意的保守取舍——宁可少刷新一次，也不要覆盖用户刚提交的结果。
- ⚪ **单行刷新未纳入闸门**：`refreshSingleSessionRow` 走 `applySessionPatch`（`GET /sessions/{id}`），不受版本约束；理论上一次"旧响应后到"仍可覆盖单行（窗口 ≈ 一次往返）。
- ⚪ **依赖服务端版本字段**：新前端 + 未重启的旧服务端时只剩"请求序号下界"这道闸门，仍可能出现一次回跳——发布需前后端同版本（`app/webui.py` 需重启生效）。
- 广播只在字段确实写入后触发（自动归档扫描仅在确有改动时广播），不会形成"重建→失效→重建"循环。

## 3. UseCase

### UC-5J1 元数据编辑即时且不回退
- **触发**：在侧栏对会话改名 / 归档 / 置顶 / 设为待办（含各自的取消）。
- **预期现象**：行内状态立即变化（名称、分组位置、徽标、排序）；此后任意次侧栏刷新都不再回退到旧值。
- **规则与边界**：只有**服务端确认后**才建立版本下界；失败路径不建立下界。
- **依据**：`session-management.js`（`toggleSessionPinnedFromMenu` L357 / `toggleSessionTodoFromMenu` L387 / `toggleSessionArchivedFromMenu` L417 / `renameSessionFromMenu` L450）。

### UC-5J2 轮询快照不得回滚已提交写入（核心）
- **触发**：写入确认后，侧栏因 15 s 对账、发送消息、切换会话、run 结束等触发 `/sessions/state` 轮询。
- **预期现象**：该次及其后的快照只反映新值；不再出现"生效 → 回退 → 再恢复"的三段抖动。
- **规则与边界**：变更前已发出、变更后才落地的快照被**请求下界**丢弃（即使它的 `client_request_seq` 比之前见过的都大）；`state_revision` 更小的快照被**版本下界**丢弃；两条闸门独立生效，任一成立即拒收。
- **依据**：`session-store.js::shouldAcceptSnapshot`（L59）、`session-actions.js::applySessionSnapshot`（L3）；回归 `tests/js/session_store_runtime.cjs`（ablation A/B/C 三组消融）。

### UC-5J3 快照版本协议
- **触发**：任何 `/sessions/state` 读取，或任一元数据写接口。
- **预期现象**：快照携带 `state_revision`（整数、进程内单调）；写接口响应携带同一字段；失效之后**第一次读取直接返回重建结果**，而不是变更前的旧值。
- **规则与边界**：版本是"失效计数"而非内容哈希——同版本不代表内容相同（TTL 内复用属正常）；重建若跨越了新失效则按新版本重扫（单飞循环）。
- **依据**：`webui.py::_invalidate_sessions_state_cache`（L1693）、`_refresh_sessions_state_cache`（L1727）、`_build_sessions_state_snapshot_cached`（L1749）、写接口 L3426 / 3968 / 6591 / 6669 / 6676 / 6683；回归 `tests/test_webui_messages.py`（`…invalidation_discards_stale_value_and_rejects_older_refresh`、`…first_read_after_invalidation_rebuilds_instead_of_serving_stale`）。

### UC-5J4 非菜单写入同样失效
- **触发**：Agent 自动命名、远程控制改名、自动归档扫描、Goal 复核徽标变更。
- **预期现象**：这些写入同样让快照失效，下一次轮询即为新值（不再有最长 5 s 的陈旧窗口）。
- **依据**：`agent_harness.py::add_session_state_listener`（L3432）、`_notify_session_state_changed`（L3441）与 7 处广播点（L6720 / 7026 / 7080 / 7108 / 7131 / 7161 / 7177）；`webui.py::_on_session_manager_state_changed`（L1715）；回归 `tests/test_session_activity_sorting.py::test_session_summary_writes_notify_registered_state_listeners`。

### UC-5J5 写入失败与在途窗口
- **触发**：PUT 失败或超时；或写入在途期间发生侧栏刷新。
- **预期现象**：失败时乐观值回退到操作前并在控制台给出错误（不建立版本下界）；在途期间快照被拒收，界面保持乐观值，写入结束后的下一次轮询再对齐。
- **依据**：`session-management.js`（`beginSidebarMetadataMutation` L334 / `commitSidebarMetadataMutation` L342 / `cancelSidebarMetadataMutation` L351，各动作 `catch` 段）。

### UC-5J6 归档与取消归档的列表一致性
- **触发**：归档 / 取消归档。
- **预期现象**：行立即移入/移出归档分组，归档计数同步；取消归档时额外刷新归档分页，且在途分页不会把已取消的行塞回。
- **依据**：`session-management.js::toggleSessionArchivedFromMenu`、`loadArchivedSessions`（代次 `archivedSessionsLoadEpoch`）、`applyOptimisticSessionUpdate` 的归档列表增删与计数分支。

## 4. 边界

- 会话列表的排序与时间分组规则见 06·UC-5F1；
- 运行状态（run/stream）的对账与终态单调契约见 03 与《WebUI 能力清单》第 4 节；
- 不覆盖：不经侧栏的批量/脚本改动（无前端乐观状态，仅依赖服务端硬失效与下一次轮询）。

## 5. 依据映射

| 用例 | 代码 |
|---|---|
| UC-5J1 / 5J5 / 5J6 | `modules/session-management.js` L334-500 |
| UC-5J2 | `state/session-store.js::shouldAcceptSnapshot`（L59）、`state/session-actions.js`（L3） |
| UC-5J3 | `app/webui.py` L1681（TTL）、L1693（硬失效）、L1727-1795（重建与版本戳）、写接口 6 处 |
| UC-5J4 | `app/agent_harness.py` L3432 / L3441 + 7 处广播；`app/webui.py` L1715-1724 |
| 回归 | `tests/js/session_store_runtime.cjs`；`tests/test_webui_messages.py`；`tests/test_session_activity_sorting.py`；`tests/test_session_export.py` |

## 6. 版本记录

- 2026-09-20 v1：首版。记录"侧栏编辑被轮询快照回滚"的现象、根因（失效仍发旧值 / 重建被丢弃 / 客户端全量覆盖 / 请求竞态 / 旁路写入不失效）与修复设计（硬失效 + 单飞重建、`state_revision` 协议、SessionManager 状态广播、客户端请求与版本双下界、仅失败才回滚）；落于 `1d9e1b0`。
