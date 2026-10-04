# 2026-10-04 界面排版、模型两级菜单与面板细节

涉及提交：`7c382a1`（系统字体与排版令牌）、`852e117`（模型与推理强度两级菜单）、`4618c3d`（统一悬停说明与自适应面板宽度）、`0fdce56`（用户方案同步）。

## 一、系统字体与排版令牌（7c382a1）

- 移除 Google Webfonts（Plus Jakarta Sans / JetBrains Mono / Space Grotesk）与 `preconnect`，全站改用系统字体栈（`-apple-system / Segoe UI / Microsoft YaHei / PingFang SC / Hiragino Sans GB / Helvetica Neue …`；等宽 `SF Mono / JetBrains Mono / Consolas …`）；Mermaid 渲染跟随 `body` 字体。
- 新增 `--ui-text-xs/sm/md/lg` 与 `--ui-line-*` 令牌，`app.css`、`dock.css`、设置中心 `settings.css`、配置向导内联页、远程控制页与插件页（agent-goal / agent-team / execution-dashboard / game-arena）把硬编码 rem 字号全量替换为令牌；根字号 14px → 16px，元信息等处按注释保留原 14px 设计尺度；强调字重收敛（600–800 → 500/600），玻璃模糊面简化（`backdrop-filter` 修剪）。
- 回归：`tests/test_frontend_typography_browser.py`（真实外壳渲染，检查字号缩放、裁切与输入框同宽碰撞）。

## 二、模型与推理强度两级菜单（852e117）

- 输入框旁「模型」触发器改为两级菜单：先展示「模型」「推理强度」两个入口，点入后选择具体值；当前项带勾（√）；方向键移动、Escape 返回上一层（再按一次关闭）、保存成功后关闭并恢复焦点；触发器原文案改为「模型 · 强度」。
- `aria-haspopup="menu"` / `role="menu"` 语义；菜单滚动条用 `stable both-edges`（两侧空隙对称），字号随界面偏好缩放（`--composer-model-font-size`）。
- 文档：`docs/settings_plugin_api.md` 同步两级菜单交互说明。
- 回归：`tests/test_model_reasoning_menu_browser.py`（真实聚焦与 API 写入）。

## 三、统一悬停说明与自适应面板宽度（4618c3d）

- 悬停说明统一走 `setUiHoverTip`（不再写原生 `title`）：文本在布局前绑定、条目可见期间实时更新、显示时翻译；计划条目被截断时的全文浮窗不再依赖"布局后补测内高"（隐藏页签/后续换宽都能有提示）；插件面板（`plugin-ui-slots`）、窄态条与弹层、计划/目标/改动审查各渲染器全部接入。
- 面板宽度变量化：`--todo-panel-width` / `--toc-panel-width` 由 `layout-panels.js` 分侧填充分配（有空间时向内填满、原始宽度为下限，先设 max-width 再测重叠，避免过渡期误折叠）；改动审查抽屉跟随同一变量。
- 改动审查文件条目与单行计划条目对齐（`font: inherit` + `line-height: normal`，避免表单线条盒拉高行高；去掉旧折叠箭头样式）。
- 回归：`tests/test_plugin_ui_frontend.py` 契约更新。

## 验证

- 四次前端构建全部通过（提交钩子 `Frontend dist is in sync.`，版本戳 v5.20261004）；
- 定向 pytest（含两个真实浏览器套件）52 passed；node 运行时套件 26/26；全量 pytest 2021 passed / 4 skipped。

## 文件

- 前端：`frontend/src/styles/app.css`、`dock.css`、`frontend/index.html`、`shell-body.html`、`modules/{model-profiles,message-rendering,layout-panels,public-sidebar,toc-todo}.js`、`plugin-ui-slots.js`；
- 后端/模板：`app/webui.py`（向导内联页字体）、`app/templates/{first_time_config,remote_control}.html`、`app/templates/static/settings/settings.css`；
- 插件页：`plugins/agent-goal/web/{style.css,session-panel.js}`、`plugins/session-todo/web/session-panel.js`、`plugins/change-review/web/{change-review.css,change-review.js}`、`plugins/agent-team/web/style.css`、`plugins/execution-dashboard/web/style.css`、`plugins/game-arena/web/index.html`。
