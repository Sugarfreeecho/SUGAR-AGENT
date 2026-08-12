# CHANGELOG — 2026-08-11

本批次改动来自 2026-08-11 的 Codex 会话记录（`~/.codex/sessions/2026/08/11`），覆盖 **MCP 事件循环、Goal Judge、审批卡片、会话恢复、媒体渲染与 CPU 压力监控**。改动已按主题分类提交。

## 一、可靠性修复

### 1. MCP 专用长期事件循环（17:17）
- 根因：`agent_mcp.py` 中 MCP 桥持有的 asyncio 原语（`_start_lock`、`_queue`、`_ready`、`_restart_lock`）绑定到首次 await 时的事件循环，ReAct 临时循环切换后跨循环操作出错。
- 修复：新增长期存活的 MCP 后台事件循环，`_run_on_mcp_loop()` 统一桥接所有 MCP 异步操作并正确传播取消；`force_reload()`、`ensure_started()`、工具重连与实际调用均固定在该循环执行，无需侵入 `agent_loop.py`。

### 2. Goal Judge 结果同轮生效（17:38）
- 根因：Judge 判定结果会延后一轮——新轮次收到的是前一轮的 verdict。
- 修复：Judge 改为在完成申请当轮立即执行并把结果注入下一轮上下文（`_run_pending_goal_judge` + `_goal_judge_context_message`），包含"已完成待人工审核 / 验证证据后重新申请 / Judge 无效"等明确指引；after-turn Judge 保留为兜底。

### 3. 全会话后台自动恢复（23:03）
- 根因：页面刷新/启动只恢复当前显示的会话，其他会话需切换后刷新才恢复。
- 修复：服务端后台接管恢复（`webui.py` 扫描所有非归档中断会话并启动 `react-recovery-*` 恢复 run），Web UI 初始化触发全会话扫描（`layout-panels.js`）；带运行预留避免与当前会话重复启动；失败按 `REACT_RECOVERY_RETRY_SECONDS`（默认 30s）重试。

## 二、审批卡片重构（22:29）

- 按钮语义统一：审批卡片只保留一个"始终允许"——能生成长期规则时保存规则，无法生成时仅当前任务内允许相同请求（原"始终允许"与"本任务内允许相同请求"合并）。
- "替我分析"按钮与其他按钮分开，靠左对齐；其余按钮靠右。
- **工作区审批与工具审批分离**：涉及工作区外操作时先审批工作区处理，之后仍需单独审批工具操作。
- 移动端适配：验证 360px / 390px 布局，按钮自动换行；危险强制审批只显示"替我分析 / 拒绝执行 / 本次允许"。

## 三、工作区媒体渲染（23:08）

新增 `frontend/src/app/modules/workspace-media.js` 完善渲染链路：

- `![说明](path.gif)` 正常显示并播放 GIF；图片按原始像素显示，超出消息区/视口才等比缩小。
- 独占一行的 `[视频](path.mp4)`、`[音频](path.mp3)` 渲染为播放器；裸媒体路径仅保留为可点击链接。
- 媒体序列化只由目标 model profile 的有效输入模态决定：图片模型收到 `image_url` content，纯文本模型只收到可恢复的文本引用与多模态委派提示（`agent_tools.py` 工具描述与 `SPEC.md` 同步更新，主 Agent 与 subagent 共用规则）。

## 四、CPU 压力监控升级与请求恢复预算

- `cpu_pressure.py` 升级为**主机 CPU、内存、Agent 进程 CPU、事件循环延迟**四级复合监控：CPU 5 次滑动均值，60% 繁忙 / 90% 严重 / 65% 恢复，10s 采样、连续 12 次升档确认、120s 恢复稳定期防抖。
- 繁忙状态保持流式输出并沿用无感优化；仅严重压力切换非流式；严重压力下仅本地资源型只读工具并发降为 2（网络型读取不受影响）。
- `agent_openai.py` / `agent_harness.py`：请求恢复引入逻辑预算（`_LogicalRequestBudget`），限制每轮物理请求数量，防止恢复风暴；配置项可热刷新。

## 五、其他前端优化

- **会话草稿徽章**：非当前会话存在未发送草稿时显示徽章（`session-management.js`）。
- **Followup 模式选项**：下拉选项显示"当前"选中徽章（`sse-handling.js`）。
- **执行过程块折叠**：收起后不再显示 `status` 状态行，无其他摘要时仅显示"本段过程已折叠"（`message-rendering.js`）。
- **子代理模型切换**：下拉选项带模型/思考强度/上下文元信息（`subagent-actions.js`）。

## 六、其他

- `ssl_bypass.py`：补丁块缩进整理。
- 新增配置（`app/.env.example`）：`REACT_RECOVERY_RETRY_SECONDS`、`CPU_PRESSURE_*` 新阈值等。
- 新增测试：MCP 跨循环重连、Judge 同轮生效、全会话恢复、媒体渲染运行时、过程块折叠、会话草稿徽章等。
- 前端 `dist` 已重建。