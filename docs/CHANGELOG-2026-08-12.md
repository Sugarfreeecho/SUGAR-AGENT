# CHANGELOG — 2026-08-12

## Goal Judge 对话上下文增强

- Judge 现在收到**完整的 Goal 生命周期对话**（不裁剪）与裁剪后的辅助执行证据（`build_judge_prompt` 支持结构化 evidence）。
- 内存中对话不可用时，从 `events.jsonl` 重建（`_load_goal_judge_dialogue_for_goal`），保证跨进程/重启后 Judge 依据完整。
- Goal 元数据新增 `completion_requested_run_id` / `origin_run_id`，将"申请完成"精确关联到发起轮次。

## 工具审查携带对话上下文

- 捕获工具审查附近的 assistant 推理/回复（`_capture_tool_review_assistant_context`），从会话事件重建审查对话（`_tool_review_conversation_from_events`）。
- 构建 `review_context` 并经 `webui.py` 传入审批流程，使"替我分析/审批"的审查建议具备证据依据。

## 相关提交

- `5f07db7` feat(goal): full dialogue evidence for Judge and completion tracking
- `6ecd6d3` feat(security): carry conversation context into tool review
