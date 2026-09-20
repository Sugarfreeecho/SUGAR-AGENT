# 审批卡片锚点与流恢复稳定性 · 功能方案设计（UseCase 清单）

- 版本：2026-09-17 v2（覆盖至：`4083cbc` 起的审批卡锚点修复，含兜底落点收口）
- 用途：逐条审查（四字段格式）。
- 适用实现：`modules/human-interactions.js`、`modules/sse-handling.js`、`modules/message-rendering.js`、后端 `agent_loop.py`（工具行占位事件）。
- 上级：`00-WebUI对话界面整体设计.md`
- 关联：`05-审批与交互卡片方案设计-UseCase清单.md`（卡片自身的呈现与决议流程）；`03-SSE管道与断线续看方案设计-UseCase清单.md`（重连与回放）。

---

## 1. 功能定位

保证"需要人拍板"的卡片（审批卡 / ask_user 问答卡）**在任意时刻都属于它那条工具调用**：正常流式、页面刷新、SSE 重连、历史重建、执行中断——卡片都应出现在对应工具行内，而不是掉在聊天流末尾（"执行过程"块外面）。

## 2. 问题与设计

### 2.1 现象（用户反馈）

Agent 执行不稳定后（断线重连、运行中刷新、历史恢复、执行中断），待审批卡片会"跑到外面"：不再挂在对应工具条目内，而是单独落在聊天流末尾；若该工具后来执行完成，卡片有时又会跳回工具行内，若执行被中断则长期留在外面。

### 2.2 根因（代码结论）

1. 审批卡是**持久化**的（审批存储 + `approval_requested`），恢复时靠 `tool_call_id` 寻找"锚点行" `.feed-item.feed--tool[data-tool-call-id]`。
2. 锚点行来自 `tool_pending` 事件，而该事件 `ephemeral=true`、**不落 ui_events**（`agent_loop.py::_emit_tool_pending_sse` L3751；`agent_subagent_events.py::should_persist_ui_event` L42 对 ephemeral 直接拒绝）。任何流重建（`loadSessionMessages` 清流回放）都会丢行。
3. 找不到锚点时前端兜底 `(slot || stream).appendChild(card)`，卡片落到流末尾——即"外面"。
4. `ensurePendingQuestionToolRow` 只服务问答卡（开头即 `record.kind === 'approval' → return false`），**审批卡被显式排除**，所以跑外面的总是审批卡。
5. 断线重连触发的历史恢复路径（`attachSessionEventStream`）在重建流后没有刷新持久交互，卡片能否归位只能靠零散的 attach 兜底。

### 2.3 设计（本次修复）

- **A. 补行对称化（核心）**：`ensurePendingHumanInteractionToolRow`（由 `ensurePendingQuestionToolRow` 泛化，`human-interactions.js` L426）对 `status=pending` 的审批与问答一视同仁——找不到锚点行时，按 `tool_call_id` 补一根占位 `tool_pending` 行（审批用 `record.tool` 作行预览，问答维持 `ask_user` 预览）；ctx/stream 缺失时回退到可见聊天流。占位行与后续真实 `tool_pending` / `tool_call` 行按 `tool_call_id` 合并（`message-rendering.js::appendToolPendingRow` L4084），不产生重复条目。
- **B. 恢复后刷新（兜底）**：`attachSessionEventStream` 的历史恢复分支在 `loadSessionMessages` 完成后、清理恢复标记之后调用 `refreshHumanInteractions(runSessionId)`（`sse-handling.js` L1089-1094），重新渲染持久卡片并全量 attach（`renderPendingHumanInteractions` 末尾 `attachAllHumanInteractionCards`），避免"行在但卡不在 / 卡在外"。
- **C. 兜底落点收口（本次补充）**：卡片找不到（且永远不会有）工具行时，`placeHumanInteractionCardFallback`（`human-interactions.js` L410）不再直挂聊天流，而是放入**最新"执行过程"框**的聚合体（`.process-aggregate-body`，取最后一个）；会话尚无任何框时按常规路径创建一个（`getProcessBody(newDomContext(stream))`），保证外观与实时一致。Hook 审批的伪 id（`hook:` 前缀）不再生成占位工具行，直接走兜底落框；已处理（resolved）卡片同样适用。待处理卡片若落在折叠框内会自动展开该框；卡片被真实行收编后，空兜底容器由 `removeEmptyHumanInteractionFallbackSlots`（L368）自动移除。
- **D. 复用既有框（本次补充）**：补行与落框都优先复用最后一个既有"执行过程"框（`ctx.currentProcessGroup = boxes[boxes.length - 1]`），不再新开空框；补行/落框后若所在框（或工具行）处于折叠态，`revealHumanInteractionCardContainer`（L392）会自动展开。
- **不改后端**：`tool_pending` 保持 ephemeral，不新增持久事件类型，回放与测试面不受影响。

### 2.4 明确边界

- 无 `tool_call_id` 的存量记录与 Hook 审批（`hook:<id>` 伪 id）：不补假行，卡片直接落进"执行过程"框；
- 已处理（resolved）卡片若有真实工具行则归位；无行时同样落进"执行过程"框，不伪造执行结果；
- 占位行与 `ask_user` 采用同一策略：恢复期短暂显示"工具名 + 执行中…"，真实行到达后由真实命令预览覆盖/合并；
- 卡片所在框被折叠时，**待处理**卡片会自动展开该框以保证可见；已处理卡片保持框的折叠状态。

## 3. UseCase

### UC-5I1 实时锚定（行先于卡）
- **触发**：工具调用进入审批（正常实时流）。
- **预期现象**：工具行先出现，审批卡直接渲染在该行内；不出现"底部生成 → 跳回工具行"。
- **依据**：`agent_loop.py` L5401（"Announce the tool row before any approval dialog…never renders at the bottom"）、`human-interactions.js::humanInteractionToolSlot`（L327）。

### UC-5I2 刷新/重连后审批卡重建锚点（本次修复）
- **触发**：待审批期间刷新页面 / SSE 重连 / 历史恢复。
- **预期现象**：卡片重新出现在对应工具行内（锚点行按 `tool_call_id` 重建），而不是落在执行过程块外。
- **规则与边界**：仅 `status=pending`；无 `tool_call_id` 不补行；补行落到既有执行过程框（无框才创建），折叠时自动展开。
- **依据**：`human-interactions.js::ensurePendingHumanInteractionToolRow`（L426）、`message-rendering.js::appendToolPendingRow`。

### UC-5I3 占位行与真实行合并
- **触发**：先由持久卡片补出占位行，随后真实 `tool_pending` / `tool_call` 事件到达。
- **预期现象**：同一 `tool_call_id` 只有一条工具行；真实命令预览/结果覆盖占位（`preferredToolPendingCommandPreview` 保留信息更多者），卡片始终挂在这一行内；`upsertToolCallResult` 后行转为已完成并自动收起。
- **依据**：`message-rendering.js::appendToolPendingRow`、`upsertToolCallResult`。

### UC-5I4 历史重建后的交互刷新（本次修复）
- **触发**：重连触发的历史重建（`streamHistoryRecoveryBySession`）完成。
- **预期现象**：持久交互（待审批/待回答）被重新渲染并归位；不产生重复卡片；恢复标记先清理、再刷新，不触发二次历史重建循环。
- **依据**：`sse-handling.js::attachSessionEventStream`（L1089-1094）。

### UC-5I5 问答卡行为不回退
- **触发**：ask_user 在任意恢复路径。
- **预期现象**：行为与修复前一致（同一 helper 的 kind 分支），卡片仍在工具行内。
- **依据**：`ensurePendingHumanInteractionToolRow`；既有回归 `tests/test_human_interaction.py::test_pending_question_tool_row_is_merged_by_stable_call_id`。

### UC-5I6 无工具条目的兜底落点（本次补充）
- **触发**：卡片渲染时找不到对应工具行、且（或）其 `tool_call_id` 永远不会与真实工具行合并（Hook 审批、存量无 id 记录、行已不可回放的已处理卡片）。
- **预期现象**：卡片落在**最新"执行过程"框内**；会话里一个框都没有时先创建框再放入——只要浏览器可创建框，就不允许直接挂在聊天流上。
- **规则与边界**：补行/落框都优先复用最后一个既有执行过程框（无框才创建）；待处理卡片若落在折叠框（或折叠行）内会自动展开；卡片被真实工具行收编后，空兜底容器自动移除。
- **依据**：`human-interactions.js::humanInteractionFallbackHost`（L375）、`placeHumanInteractionCardFallback`（L410）、`removeEmptyHumanInteractionFallbackSlots`（L368）；回归 `tests/test_human_interaction.py::test_card_fallback_lands_inside_process_aggregate`。

## 4. 边界

- 审批策略与模式语义见 ../07-权限审批/01–03；
- 断线重连次数、退避与回放游标见 03《SSE 管道与断线续看》；
- 不覆盖：执行过程框本身被历史剪裁移除的场景（此时退化为聊天流落点，浏览器侧无容器可建）。

## 5. 依据映射

| 用例 | 代码 |
|---|---|
| UC-5I1 | `agent_loop.py` L5401；`human-interactions.js` L327-341 |
| UC-5I2/5I3/5I5 | `human-interactions.js::ensurePendingHumanInteractionToolRow`（L426 起）；`message-rendering.js::appendToolPendingRow`（L4084 起） |
| UC-5I4 | `sse-handling.js` L1089-1094；`human-interactions.js::refreshHumanInteractions`（L1460） |
| UC-5I6 | `human-interactions.js::humanInteractionFallbackHost`（L375）、`placeHumanInteractionCardFallback`（L410）、`removeEmptyHumanInteractionFallbackSlots`（L368） |

## 6. 版本记录

- 2026-09-17 v3：补行/落框统一优先复用最后一个既有执行过程框（不再新开空框）；折叠框/折叠行自动展开（UC-5I2/5I6 补充）。
- 2026-09-17 v2：补录兜底落点收口（UC-5I6）——无工具条目的卡片（含 Hook 审批与存量无 id 记录）落进"执行过程"框、不再直挂聊天流；Hook 伪 id 不造假行；空兜底容器随真实行收编自动清理；`frontend/src` 与 `app/templates/dist` 已再次同步重建。
- 2026-09-17 v1：首版。记录问题（流恢复后审批卡落到执行过程外）与修复设计（A 审批补行 + B 恢复后刷新）；实现落于 `human-interactions.js` / `sse-handling.js`，`frontend/src` 与 `app/templates/dist` 已同步重建。
