# CHANGELOG — 2026-08-12

## Goal Judge 对话上下文增强

- Judge 现在收到**完整的 Goal 生命周期对话**（不裁剪）与裁剪后的辅助执行证据（`build_judge_prompt` 支持结构化 evidence）。
- 内存中对话不可用时，从 `events.jsonl` 重建（`_load_goal_judge_dialogue_for_goal`），保证跨进程/重启后 Judge 依据完整。
- Goal 元数据新增 `completion_requested_run_id` / `origin_run_id`，将"申请完成"精确关联到发起轮次。

## 工具审查携带对话上下文

- 捕获工具审查附近的 assistant 推理/回复（`_capture_tool_review_assistant_context`），从会话事件重建审查对话（`_tool_review_conversation_from_events`）。
- 构建 `review_context` 并经 `webui.py` 传入审批流程，使"替我分析/审批"的审查建议具备证据依据。

## 网络出口控制（Egress Guard）

### 安全层（新）

- `app/security/egress_guard.py`：出口守卫，通过 HMAC 会话密钥、健康检查缓存与 helper 发现（`SUGAR_AGENT_EGRESS_HELPER` → `app/native/` → PATH）执行应用策略的网络决策。
- `app/security/shell_analysis.py`：Shell 命令的出口意图分析（数据发送 upload / 网络读取 read / 未知/交互）。
- `models.py` / `policy.py` / `runtime.py` / `store.py`：新增 `SandboxHealth`、restriction 与 `enforcement_level`（strong / partial / degraded）模型与持久化。
- `docs/egress_helper_protocol.md`：helper 协议 v1——`health --json` 握手，`strong`/`partial` 级别，后端 `windows-appcontainer`、`linux-network-namespace`、`macos-sandbox-profile`。

### 原生 helper 与构建（新）

- `app/native/`：Windows C# 实现（`SugarAgentEgressHelper.cs`）、Python 实现（`sugaragent-egress-helper.py`）、无扩展启动器；`.exe` 由 C# 源码可复现构建（已加入 `.gitignore`）。
- `scripts/build_egress_helper_windows.ps1`（Windows 构建）、`scripts/verify_egress_helper.py`（协议验证）。

### 审批与前端

- 审批卡片展示 egress 意图（数据发送/网络读取/未知网络操作）与目标主机列表（`human-interactions.js`）。
- 出站防护降级/部分降级时顶部提示（`permissions.js`），说明当前无系统级网络隔离。
- 工具层：`agent_tools.py` 集成 `prepare_egress_launch` 与 `egress_helper_enabled`；`agent_loop.py` 按 egress 意图定制审批标题。
- CI/启动脚本更新（`.github/workflows/platform-tests.yml`、`RUN.bat`、`scripts/install_unix.sh`）。

### 相关提交

- `5f07db7` feat(goal): full dialogue evidence for Judge and completion tracking
- `6ecd6d3` feat(security): carry conversation context into tool review
- `961d647` docs: add changelog for 2026-08-12 changes
- （本批 egress 提交见 git log）
