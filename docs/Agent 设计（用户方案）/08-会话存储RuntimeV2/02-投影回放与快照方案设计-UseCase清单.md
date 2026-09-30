# 投影、回放与快照 · 功能方案设计（UseCase 清单）

- 版本：2026-09-30 v3（覆盖至：当前工作区；Goal 读取的复制范围）
- 用途：逐条审查（四字段格式）。
- 适用实现：`runtime_v2/projector.py`（1270 行）、`ui_projection.py`（1304 行）、`model_projection.py`、`snapshot_store.py`（580 行）、`blob_store.py`。
- 上级：`00-会话存储RuntimeV2整体设计.md`

---

## 1. 功能定位

从事件到"可用状态"的三层派生：状态投影（内部）、UI 投影（界面）、模型投影（请求），以及加速它们的快照。

## 2. UseCase

### UC-8B1 状态投影
- **触发**：读取会话状态。
- **预期现象**：由事件增量投影出会话状态（消息、运行、计划、上下文水位等）；投影结果与事件序列一致；token 过期标记触发按需重算。
- **依据**：`RuntimeProjector`、`_mark_context_tokens_stale`。

### UC-8B2 UI 投影与回放
- **触发**：界面打开/刷新/续看。
- **预期现象**：产出与界面一致的 SSE payload 序列；回放严格只读、不产生副作用；有序不重复。
- **依据**：`ui_projection.py`、`webui._runtime_v2_chat_sse_payload`。

### UC-8B3 模型历史投影
- **触发**：构建下一轮模型请求。
- **预期现象**：输出干净的消息序列（Responses 续接信息、内部标记被剥离）；不含 UI 专用事件。
- **依据**：`model_projection.py`（strip_responses_continuation_from_message）。

### UC-8B4 快照加速
- **触发**：长会话读取。
- **预期现象**：快照命中 → 快速返回；未命中/失效 → 从事件重建并写新快照；快照永不与真源"唱反调"。
- **依据**：`SnapshotStore`、`blob_store`。

### UC-8B5 一致性检查
- **触发**：诊断/修复入口。
- **预期现象**：经修复服务可对比"事件重放 vs 快照/镜像"并报告差异（`root_log_repair._verify_repaired_state` 与迁移校验）；通用的一键一致性诊断入口 🟡 规划中（不作为当前验收目标）。
- **依据**：`projector` 校验段 + `repair.py` 联动。

### UC-8B6 按需复制 Goal 子状态

- **触发**：Goal 查询仅需扩展状态，而不需要消息、UI、模型等完整投影的可修改副本。
- **预期现象**：复用既有 `read_consistent_view()` 的一致只读视图，保留事件日志新鲜度核对和必要重建；GoalManager 只复制提取出的 Goal。没有 Goal 时不复制其他字段。
- **规则与边界**：view 是共享只读对象，读取方不能就地改写；需要给外部调用方修改的 Goal 必须 deepcopy 后返回。本批调整调用方，未把 `SnapshotStore.read_consistent()` 的完整隔离副本语义改成共享引用，也未跳过快照恢复。
- **依据**：`app/agent_goal.py::GoalManager.get`、`runtime_v2/snapshot_store.py::read_consistent_view / read_consistent`；[02/09 · UC-2I12](../02-ReAct运行时/09-运行生命周期与Goal续跑防风暴方案设计-UseCase清单.md)。真实快照复制步骤 A/B 见 [09/05](../09-横切能力/05-性能优化基线与已完成项方案设计-UseCase清单.md)。

## 3. 边界

- 投影缓存失效规则由事件类型驱动（提交/替换/修剪等）；
- 快照是**加速器**而非事实：删除后系统仍能工作（只是慢）。

## 4. 依据映射

见上表。

## 5. 版本记录

- 2026-09-30 v3：新增 UC-8B6，明确 Goal 一致读取只复制所需子状态、共享 view 只读与返回值隔离，保留完整快照 API 的原语义。
- 2026-09-14 v2：收紧一致性检查表述（现为修复/迁移校验入口）；版本线更新至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-803/804/807/808）。
