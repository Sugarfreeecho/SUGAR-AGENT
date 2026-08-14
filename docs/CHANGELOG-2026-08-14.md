# CHANGELOG — 2026-08-14

延续 8/13 深色主题与 UI 优化批次（会话 `rollout-2026-08-14T00-20-47`）。

## 深色主题配色微调

- 深色版正文区域（文字、表格等）紫色元素统一调整为蓝色强调；文字色按截图参考校准，避免偏深。
- 保留紫色作为原"紫色版本"主题。

## Composer 侧控对齐修复

- `layout-panels.js`：侧控布局始终对照 **68cqi 自然列宽**计算（即使实际列被展开），修复展开态下权限/模型栏与输入框错位；补充 `main-center` 缺失保护。

## 相关提交

- `feat(webui): dark theme accent polish and composer side control alignment`
- `build: sync frontend distribution`
