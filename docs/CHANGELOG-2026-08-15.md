# CHANGELOG — 2026-08-15

本批次来自 8/14 深夜与 8/15 凌晨的两个 Codex 会话：带引号路径解析修复（已由 `0052a52` 提交）、恢复门禁、执行轨迹 V2 UI。

## 一、带引号工作区路径解析修复（`0052a52`）

- 根因：正常 md 文件路径（如 `[说明]("D:\...\报告.md")`）会被剥离后括号导致无法识别。
- 修复：`message-rendering.js` 支持带引号的工作区路径解析；`workspace_media_runtime.cjs` 测试同步更新。
- 注：该提交由本地直接创建（8/15 00:21），本次一并推送。

## 二、恢复/续跑门禁（00:07 会话）

- 即使 Runtime V2 把运行标记为 `interrupted`，只要会话仍有 **pending 问题或审批**，通用 ReAct、Goal runner 与 HTTP continuation 都不会启动；只有回答/取消交互的专用恢复链可以继续。
- 双门禁：发现阶段与执行阶段各检查一次（`webui.py` `_session_pending_human_counts`）。
- 新增/更新测试：`test_react_recovery_runner.py`、`test_goal_runner.py`、`test_human_interaction.py`。

## 三、执行轨迹 V2 UI（23:51 会话）

- "执行过程"更名为"**执行轨迹**"；支持展开/收起轨迹高度按钮（`aria-expanded`），输入框增高时自动把聊天区/轨迹区重新钉到底部，避免与流式滚动互相拉扯。
- 未挂载 document 的片段（回放/"加载更早消息"预挂载）保留同一执行轨迹。
- 相关：`message-rendering.js`、`layout-panels.js`、`shared-state-and-dialogs.js`、`sse-handling.js`、`session-scroll-history.js`、`subagent.js`、`i18n.js`、`app.css`、`myagent_path_picker.js`。
- 新增 `MYAGENT_FRONTEND_VERSION=v1` 环境配置（`.env.example`）。
- 新测试：`test_workspace_file_picker_theme.py`；更新 `test_feature_flags.py`、`test_frontend_theme_variants.py`。

## 其他

- 清理历史 demo/公告页面：`agent-banner-style-gallery.html`、`codex-permission-mockup.html`、`external-ops-demo.html`、`update-announcement-2026-08.html`。
- `app/templates/dist` 已重建。
