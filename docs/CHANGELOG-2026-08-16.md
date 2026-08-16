# CHANGELOG — 2026-08-16

## 首次配置页确认弹窗样式

- `first_time_config.html`：新增与设计系统一致的确认弹窗样式（`modal-overlay`/`modal-card`/`modal-icon`，毛玻璃背景、动效过渡）；移除旧的 `.model-context-warning` 样式。

## 前端版本号按提交日期自动刷新（新机制）

- 左下角 Runtime 版本号（`sidebar-runtime-version`）原为硬编码 `v4.YYYYMMDD`，现在由 **pre-commit hook 自动刷新**：
  - 新增 `scripts/update_frontend_version.py`：提交时把 `frontend/index.html`、`frontend/src/shell-body.html`、`app/templates/dist/index.html` 三处的日期部分更新为当天（`v4.20260816` 格式），幂等（同一天多次提交不产生噪音）。
  - `scripts/install_git_hooks.py` 的 pre-commit 模板先刷新版本号并重新暂存，再执行前端提交策略检查；pre-push 保持原检查。
  - 已重新安装本地 hook（`git commit` 即刻生效）。

## 相关提交

- `feat(webui): first-time config confirm dialog styles`
- `feat(build): auto-refresh frontend version stamp on commit`
