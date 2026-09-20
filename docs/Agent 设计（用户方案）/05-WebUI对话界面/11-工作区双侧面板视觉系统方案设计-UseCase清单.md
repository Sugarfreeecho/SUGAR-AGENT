# 工作区双侧面板视觉系统 · 功能方案设计（UseCase 清单）

- 版本：2026-09-21 v1（覆盖至：当前工作区）
- 用途：审查工作区左右两侧面板是否使用同一套视觉语言，而不是只核对某一个颜色值。
- 适用实现：`frontend/src/styles/app.css`、`frontend/src/shell-body.html`、`frontend/index.html`、`frontend/src/app/modules/toc-todo.js`、`frontend/src/app/plugin-ui-slots.js`、`plugins/session-todo/web/session-panel.{js,css}`、`plugins/agent-goal/web/session-panel.{js,css}`、`frontend/src/app/modules/i18n.js`。
- 上级：`00-WebUI对话界面整体设计.md`

---

## 1. 功能定位

工作区左右两侧面板共享同一套“外壳—标题—元信息—列表—条目”视觉原语。历史记录、Todo、Goal 与声明式插件面板在浅色/深色主题下应像同一产品中的同级区域；业务状态、操作按钮和内容结构仍按各自语义表达。

## 2. UseCase

### UC-5K1 左右面板外壳一致
- **触发**：同时打开左侧 Todo/Goal 插件面板与右侧历史记录面板。
- **预期现象**：面板背景、圆角、阴影、内边距、模糊效果、前景色和字体族一致；左右位置不同，但视觉层级相同。
- **规则与边界**：共享外壳由 `.workspace-side-panel` 和 `--workspace-side-panel-*` 令牌定义。插件自定义宿主只负责清除重复外壳，不得再声明一套独立背景、阴影或排版体系。
- **依据**：`app.css` 的 workspace side panel 令牌与 `.workspace-side-panel`；`shell-body.html` / `frontend/index.html` 的历史面板；session-todo、agent-goal 的 `session-panel.js`。

### UC-5K2 标题、元信息与正文层级一致
- **触发**：查看历史记录数量、Todo 进度、Goal 状态与各面板正文。
- **预期现象**：标题使用同一字号、字重、行高、字距与大写风格；统计/进度使用同一元信息层级；历史项、Todo 项和 Goal 目标使用同一正文尺度与条目容器。
- **规则与边界**：共享类分别为 `.workspace-side-panel-title`、`.workspace-side-panel-meta`、`.workspace-side-panel-list`、`.workspace-side-panel-item`。业务 CSS 可以控制完成态、危险态、按钮布局和文本截断，不得覆盖基础字号、背景与间距来形成第二套设计。
- **依据**：`app.css` 的共享原语；`toc-todo.js`、session-todo 与 agent-goal 的类名接线。

### UC-5K3 列表密度与交互反馈一致
- **触发**：滚动历史/Todo 列表，悬停历史项，切换当前历史项，勾选 Todo。
- **预期现象**：列表间距、条目内边距、边框和圆角保持一致；可点击历史项复用统一 hover/active 反馈；Todo 完成态仍通过勾选、删除线和透明度表达。
- **规则与边界**：视觉一致不等于交互一致。只有可点击条目使用 `.workspace-side-panel-item--interactive`；不可点击的 Goal 目标不伪造 hover，Todo 的复选框和状态色由插件保留。
- **依据**：`app.css` 的 item/interactive/active 规则；`toc-todo.js`；`plugins/session-todo/web/session-panel.css`。

### UC-5K4 浅色与深色主题同步切换
- **触发**：在 light、dark 与 neutral dark 主题间切换。
- **预期现象**：左右面板同时切换背景、阴影、标题色、分隔线、条目底色和交互反馈，不出现某一侧仍使用另一主题的“拼接感”。
- **规则与边界**：主题差异只在 `--workspace-side-panel-*` 令牌层定义；组件规则消费令牌，不按面板名称复制主题色。neutral dark 可复用默认值，但必须保持令牌契约完整。
- **依据**：`app.css` 的 `:root`、`:root.theme-light`、`:root.theme-neutral-dark`。

### UC-5K5 历史统计与空态同步
- **触发**：历史记录建立、增加、清空或切换会话。
- **预期现象**：标题下显示“n 条记录”；没有历史时统计同步清空，不保留上一会话数量；英文界面显示 `n items`。
- **规则与边界**：统计是当前 TOC 数据的派生值，不写入会话状态，不独立缓存；会话清理路径必须同时清理列表与统计。
- **依据**：`shell-body.html` / `frontend/index.html` 的 `#chat-toc-stats`；`toc-todo.js`；`i18n.js` 的“条记录”词条。

### UC-5K6 插件面板遵守宿主视觉契约
- **触发**：插件通过 `session.panel` 注入声明式或自定义会话面板。
- **预期现象**：声明式面板默认使用共享外壳、标题和列表条目令牌；自定义面板（Todo/Goal）显式组合共享类，只在插件 CSS 中保留业务语义和控件细节。
- **规则与边界**：宿主掌握基础视觉系统，插件掌握信息结构和语义状态。插件若确有品牌化需求，必须新增明确变体，而不是覆盖共享基础类。
- **依据**：`app.css` 的 `.plugin-session-panel*`；`plugin-ui-slots.js`；session-todo、agent-goal 的前端资源。

### UC-5K7 回归与构建产物一致
- **触发**：修改共享令牌、类名或任一侧面板结构。
- **预期现象**：主题契约测试能发现共享类断接或插件重新声明独立表面；Vite 构建成功，`app/templates/dist` 与源码同步。
- **规则与边界**：视觉测试至少覆盖 light token、共享外壳/标题/条目、历史/Todo/Goal 类名接线，以及 Todo/Goal 不再自建外壳背景。
- **依据**：`tests/test_frontend_theme_variants.py::test_workspace_side_panels_share_visual_system`；`frontend` 构建与 dist 同步检查。

## 3. 视觉原语映射

| 层级 | 历史记录 | Todo | Goal | 声明式插件 |
|---|---|---|---|---|
| 外壳 | `.chat-toc-panel` + `.workspace-side-panel` | `.chat-todo-plan-panel` + `.workspace-side-panel` | `.chat-goal-card` + `.workspace-side-panel` | `.plugin-session-panel` 消费同一令牌 |
| 标题 | `.chat-toc-title` + `.workspace-side-panel-title` | `.chat-todo-plan-title` + `.workspace-side-panel-title` | `.chat-goal-heading` + `.workspace-side-panel-title` | `.plugin-session-panel-title` 对齐共享规格 |
| 元信息 | `#chat-toc-stats` | `.chat-todo-plan-stats` | 标题内状态 | description / fields |
| 内容条目 | 历史链接 | Todo 行 | Goal objective | list row |
| 业务差异 | 当前项、加载态 | pending/in-progress/completed | 状态与动作按钮 | info/success/warning/danger |

## 4. 边界

- 本设计只约束工作区侧面板的视觉骨架，不改变 Todo/Goal 的服务端状态、会话切换协议或插件权限。
- 详情栏第三列的文件树、编辑器和修改历史属于 `08-详情栏`；若其中出现同级浮层，可消费共享令牌，但不强制套用窄侧栏结构。
- 响应式显隐、折叠把手和侧栏宽度仍由现有布局逻辑负责。

## 5. 版本记录

- 2026-09-21 v1：建立左右侧面板共享视觉系统；覆盖历史、Todo、Goal 与声明式插件面板，统一主题令牌、外壳、排版、列表密度和条目反馈，并保留业务语义差异。
