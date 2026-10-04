# 公共左侧栏（会话扩展面板）· 功能方案设计（UseCase 清单）

- 版本：2026-10-04 v3（覆盖至：当前工作区；统一悬停说明与自适应面板宽度）
- 用途：逐条审查（四字段格式）；核对聊天区左缘「会话扩展面板」是否统一为**一条公共栏（页签式，方案 B）**——一套外壳、一套页签显隐、一套避让/降级逻辑，而不是多套卡片与多套规则并存。
- 适用实现（拟落点）：新增 `frontend/src/app/modules/public-sidebar.js`；改造 `frontend/src/app/plugin-ui-slots.js`、`frontend/src/app/modules/layout-panels.js`、`frontend/src/app/modules/toc-todo.js`、`frontend/src/styles/app.css`、`frontend/src/shell-body.html`、`frontend/index.html`；插件侧 `plugins/session-todo/**`、`plugins/agent-goal/**`、`plugins/change-review/web/change-review.{js,css}`；后端 `app/plugins/ui.py`（`session.panel` 透传 `group`）；词条 `frontend/src/app/modules/i18n.js`。
- 上级：`00-WebUI对话界面整体设计.md`｜相关：`11-工作区双侧面板视觉系统方案设计-UseCase清单.md`（视觉原语继承、本条收口“多栏共生”）、`../06-能力扩展加载/08-内置插件-改动审查方案设计-UseCase清单.md`（改动审查内容）、`../../plugin_api_v1.md`（拟增 `group` 字段，实现后同步）。

---

## 1. 功能定位

聊天区左缘现为“一主一邻 + 分散逻辑”：（主）会话扩展面板承载 Todo / Goal / 声明式插件面板；（邻）改动审查左缘卡片占同一槽位、两列并排、空间不足退化为输入框上方条（现状分析见 [`../../../workspace/左侧栏统一_分析/左侧栏现状分析_v2.md`](../../../workspace/左侧栏统一_分析/左侧栏现状分析_v2.md)）。

本方案把它收敛为**一条公共左侧栏（方案 B · 页签）**：

```
#chat-todo-plan（唯一挂点，几何不变）
└─ .chat-todo-plan-inner（整条 = 一个玻璃面）
   ├─ 头部：会话扩展 + 收起
   ├─ 页签：计划 ｜ 目标 ｜ 插件 ｜ 改动(N)
   └─ 内容：一次显示一类，共用一条滚动
```

- 形态依据：原型 v1（两形态同页对比：A 分节 / B 页签；评审选定 B）——[`../../../workspace/左侧栏统一_分析/公共左侧栏_原型_v1.html`](../../../workspace/左侧栏统一_分析/公共左侧栏_原型_v1.html)（截图：`原型v1_对比_浅色.png`、`原型v1_方案B_改动页签.png`、`原型v1_对比_深色.png`）。
- 不涉及会话列表主侧栏；不改插件权限、状态协议与会话切换机制。

## 2. UseCase（规划中，逐条转正）

> 说明：本文实现已落地（v2，2026-10-02）：以下 UC 逐条按实现核对；提交后补提交号。

### UC-5M1 一条栏单出口
- **触发**：任一有内容的会话（Todo / Goal / 插件面板 / 改动审查出现）。
- **预期现象**：左缘只出现**一条**“会话扩展”栏——头部（标题）→ 页签条 → 内容区（开合仅经右缘把手，头部不设折叠按钮）；不再出现多张各自带壳的卡片堆叠，也不再出现“主栏 + 改动邻栏”两列并排。
- **规则与边界**：几何保持现状——宽 9.5rem、垂直居中、右缘把手、≤760px 为 7rem、`--panel-edge-slide-width` 语义不变；会话列表主侧栏不参与。
- **依据**：现状挂点 `#chat-todo-plan`（`frontend/src/shell-body.html` / `frontend/index.html`）与 `.change-review-drawer` 同槽位并排（`plugins/change-review/web/change-review.css`）；现状分析 v2 §0/§4；拟落点见 §3。

### UC-5M2 页签分组与归属
- **触发**：插件通过 `session.panel` 注入会话面板；改动审查产生当轮改动。
- **预期现象**：内容按四类进入页签——计划（session-todo）、目标（agent-goal）、插件（其余会话面板）、改动（change-review）；页签顺序：计划 → 目标 → 插件 → 改动。
- **规则与边界**：分组由 manifest `session.panel` 新增可选 `group`（`id / label / order`）声明，缺省为「插件」组；核心前端不硬编码任何插件 id 或专有类名（延续“专用 UI 归插件”约束）；「改动」不属于 `session.panel` 体系，由 change-review 直接注册。
- **依据**：`app/plugins/ui.py::plugin_ui_contributions / project_plugin_session_ui`（拟透传 `group`）；`plugins/session-todo/.myagent-plugin/plugin.json`、`plugins/agent-goal/.myagent-plugin/plugin.json`；`tests/test_plugin_ui_frontend.py::test_goal_and_todo_specialized_ui_remains_owned_by_plugins`。

### UC-5M3 内容驱动显隐
- **触发**：扩展数据刷新（会话切换、状态变化、Todo/Goal/改动增删）。
- **预期现象**：只出现“有内容”的页签；仅 1 类内容时不显示页签条（直接展示该内容）；全部为空 → 整条收起、把手隐藏。
- **规则与边界**：显隐由数据驱动、不由用户操作驱动；“有内容” = 页签宿主内无可见子元素即为空；空态切换不闪烁、不残留上一会话内容。
- **依据**：现状语义 `layout-panels.js::syncTodoPanelContentVisibility / updatePanelToggles`、`toc-todo.js::syncExtensionPanelVisibility`；`myagent:plugin-session-ui-rendered` 事件；拟收口到 `MyAgentPubar.hasContent()`。

### UC-5M4 活动页签、记忆与切换
- **触发**：用户点击页签 / ←→ / Home·End；或切换会话后重新出现内容。
- **预期现象**：默认激活第一个有内容页签（按组 order）；记忆最近活动页签（跨会话全局）；切会话时记忆页签仍有内容则保留，否则回落第一个有内容页签；隐藏页签不可激活；切换页签不改变栏的开合状态。
- **规则与边界**：记忆键独立于会话（`pubar-active-tab`）；页签语义为 tablist / tab / tabpanel，roving tabindex；键盘与鼠标等价。
- **依据**：拟落点 §3（`public-sidebar.js`）。

### UC-5M5 徽标与提示
- **触发**：改动文件数变化；插件面板数量变化；非活动页签出现新内容。
- **预期现象**：「改动」页签显示文件数；「插件」页签在 >1 时显示面板数；非活动页签出现新内容时**自动切换到该页签**（见 UC-5M14）；会话切换抑制期内回退为脉冲提示。
- **规则与边界**：徽标只表达“数量 / 有新内容”，不承担状态色；数字随数据刷新增减；活动页签显示时脉冲即清除；自动跟切与抑制规则以 UC-5M14 为准。
- **依据**：`plugins/change-review/web/change-review.js`（当轮文件行来源）；拟落点 §3。

### UC-5M6 开合、把手与自动折叠保持不变
- **触发**：点击右缘把手；正文与栏重叠；空间恢复；用户手动开合。
- **预期现象**：与现状完全一致——把手贴在栏右缘、有内容才显示；用户开合被记忆；与正文冲突自动收起、空间恢复自动展开；冷却与手动覆盖语义不变。
- **规则与边界**：本条约只把“是否有内容”的判定收口到公共栏统一入口；不改变 `panelUserCollapsedTodo / panelAutoCollapsedTodo / runPanelAutoCollapseCheck` 既有规则。
- **依据**：`layout-panels.js::toggleTodoPlanPanel / updatePanelToggles / runPanelAutoCollapseCheck / layoutPanelEdgeTabs`；`tests/test_side_panel_content_overlap.py`。

### UC-5M7 改动审查入栏
- **触发**：当前轮产生文件改动且过程框展开。
- **预期现象**：文件行（路径 + 增删计数 + 查看 / 已撤销）+ 汇总（N 文件 +x −y）显示在「改动」页签内；「查看」仍打开右侧详情栏；过程框行徽标与轮徽标不变。
- **规则与边界**：旧左缘抽屉只在公共栏不可用时回退（防御路径），默认不再出现；改动页签不再与主栏并排占两个槽位。
- **依据**：`change-review.js::mount / render / updatePlacement / openDetails`；`plugins/change-review/web/change-review.css`；`tests/js/change_review_visibility_runtime.mjs`、`tests/js/change_review_stats_runtime.mjs`。

### UC-5M8 输入框兜底条
- **触发**：改动有内容，但公共栏处于收起 / 不可用状态。
- **预期现象**：输入框上方出现紧凑条（改动审查 + 汇总 + 查看）；公共栏内可取改动时**不再同时显示**。
- **规则与边界**：兜底条与页签互斥，避免同信息双显；旧的“空间不足”几何判断随两列并排形态退役（实现后记录差异）。
- **依据**：`change-review.js::hasRoom / updatePlacement`（现状：“空间不足 → 条”）；`.change-review-bar` 样式（`change-review.css`）。

### UC-5M9 插件渲染契约不变
- **触发**：Todo / Goal / 插件面板渲染与清理。
- **预期现象**：Todo、Goal 仍由插件自绘内容；其余面板仍由宿主声明式渲染；渲染器只被要求“放进页签”，不被要求重写业务。
- **规则与边界**：`renderSessionPanel(context)`、cleanup（返回 false 保留）、action（`/api/extensions/session-action`）协议不变；插件专有类名（`chat-todo-plan-panel`、`chat-goal-card` 等）留在插件侧，核心不引用；插件 CSS 收敛为“透明节”，不再自建卡壳。
- **依据**：`plugin-ui-slots.js::renderSessionPanels`；`plugins/{session-todo,agent-goal}/web/session-panel.{js,css}`；`tests/test_plugin_ui_frontend.py`。

### UC-5M10 视觉规格（继承 05/11）
- **触发**：在 light / dark / neutral dark 主题与中英文间切换。
- **预期现象**：整条栏一个玻璃面；页签条（小字号、活动 = accent 底 + 描边、数字徽标）；节 = 标题 / 计数 / 操作位 + 条目；四类内容同级同规格。
- **规则与边界**：继续消费 `--workspace-side-panel-*` 令牌族与 `:root.theme-*`；不新增第二套皮肤；插件只保留业务语义差异（完成态、状态、操作按钮）。
- **依据**：`11-工作区双侧面板视觉系统方案设计-UseCase清单.md`（UC-5K1~5K7）；`frontend/src/styles/app.css`；拟落点 §3。

### UC-5M11 响应式与可访问性
- **触发**：窗口 ≤760px；键盘操作页签。
- **预期现象**：窄宽下页签压缩（字号 / 内边距收紧、隐藏数字徽标），栏宽 7rem 不变形；键盘 ←→ / Home·End 可切换，焦点可见。
- **规则与边界**：压缩只影响页签条内部排版，不影响栏宽 / 避让几何；`aria-selected`、`role=tab/tabpanel` 齐备；`prefers-reduced-motion` 下禁用过渡。
- **依据**：`app.css` 现有 `--panel-edge-slide-width: 7rem` 媒体规则；拟落点 §3。

### UC-5M12 会话切换与清理
- **触发**：切换会话 / 新建会话。
- **预期现象**：公共栏清空上一会话动态内容并按新会话数据重算页签；无残留、无跨会话串扰；栏的开合记忆保持既有语义。
- **规则与边界**：沿用 cleanup 协议与 `clearOptionalPanelsForSessionLoad`；公共栏增加 `resetForSession()` 作为结构级清理；改动页签内容跟随当前挂载会话。
- **依据**：`toc-todo.js::clearOptionalPanelsForSessionLoad`；`plugin-ui-slots.js` 的 cleanups；`change-review.js::resetForSession`。

### UC-5M13 节内容细则（终稿 · 实机确认）
- **触发**：在浅色 / 深色主题下查看四类页签内容；窗口 ≤720px；悬停改动行路径。
- **预期现象**：四类内容统一为「节」= **单行节头（标题 + 计数/统计 + 操作位）＋ 条目/字段**：
  - 计划：节头 `当前计划 · N / M 已完成 · ×`；条目 = 圆角行卡 + **状态图标**（已完成 = 绿色圆勾、正文删除线；进行中 = 强调色缺口弧环（加载环）；待处理 = 中性空环；图标与首行文字中线对齐；语义文字在 `aria-label` / 悬停提示）+ 正文（**最多 3 行**，被截断的条目在统一悬停浮框中完整呈现全文）。
  - 改动：节头 `改动审查 · +x −y · 查看`（栏内为紧凑净增删，完整统计口径保留在悬停提示）；文件行 = 圆角行卡，路径**尾部优先省略**（省略前面、保留文件名段；悬停 `title` 显示完整路径）。
  - 目标：节头 `GOAL · 状态胶囊`（进行中 · 时长 / 已暂停 / 已完成）；目标正文；`已用 X · 剩余 Y` 摘要行（无预算时仅「已用 X」）；操作按钮行（统计 / 暂停-开始 / 编辑 / 删除，完成后加「结果审核」）固定于卡片底部。
- **规则与边界**：仅 1 类内容时隐藏页签条；徽标 = 改动文件数、插件 >1 面板数；输入框兜底条与栏内互斥；条目列表不预留滚动条槽（`scrollbar-gutter: auto`，左右内边距对称）；暂停/开始图标按状态**单显**（SVG 需 `toggleAttribute('hidden', …)`，`hidden` property 写法对 SVG 无效）；≤720px 页签字号 / 内边距收紧并隐藏数字徽标。
- **依据**：`plugins/session-todo/web/session-panel.{js,css}`、`plugins/agent-goal/web/session-panel.{js,css}`、`plugins/change-review/web/change-review.{js,css}`、`frontend/src/styles/app.css`（`.pubar-*` 与页签内覆盖）；实机留档 `workspace/左侧栏统一_分析/样例_*.png`、`实机_*.png`。

### UC-5M14 自动跟随最新生成/更新的页签
- **触发**：某页签出现新内容或数量增长（改动行新增、计划/目标实质更新、插件面板出现）；或插件渲染器调用 `MyAgentPubar.notifyActivity(el)` 上报实质更新。
- **预期现象**：该页签自动成为活动页签（栏收起时也完成切换记忆）；同一波更新以最后一个为准（150ms 合并）；若该页签已是活动页签则保持不动。
- **规则与边界**：会话切换后 4s 抑制期内不自动切换（回退为脉冲提示），避免加载期抢焦点；用户点击 / 键盘切换页签时取消待执行的自动切换；计划 / 目标渲染器各自维护“渲染签名”只上报实质变化，秒级计时与用量刷新不触发；目标卡只跟随状态 / 描述类变化；渲染器可能在内容提交前（未挂载片段）提前上报，核心延迟一拍（120ms）在提交后补解析归属。
- **依据**：`public-sidebar.js::pubarFollowActivity / pubarNotifyActivity / pubarResetForSession`；`plugins/{session-todo,agent-goal}/web/session-panel.js`（签名 + `notifyActivity`）；`tests/js/public_sidebar_runtime.mjs`（自动切换 / 抑制 / 显式通知用例）。

### UC-5M15 窄态条目区（输入框上方）+ 专用浮窗
- **触发**：左栏收起（窄态）且某页签有内容；或窄态下点击条目。
- **预期现象**：输入框上方出现单行玻璃胶囊条目（图标 + 标题 + 计数/摘要 +（可选，如 GOAL）状态胶囊 + 行内动作按钮 + 箭头），按页签 order 排序（堆叠顺序：追加队列（现有）→ 计划 → 目标 → 插件 → 改动，最贴近输入框）；左栏展开时条目区自动隐藏（与页签互斥）。点击条目**不展开左栏**，而是在条目上方弹出**专用浮窗**（形式对标输入框「＋」的 skill 选择浮窗）：标题 + 关闭按钮，内容即该页签宿主（宿主被就近搬运进浮窗，插件持续向同一宿主渲染，内容实时）；关闭（× / Esc / 点击外部 / 左栏展开 / 内容消失）后宿主搬回左栏原位。行内动作按钮直接复用页签内控件（GOAL 开始/暂停、编辑、删除；改动「查看」→ 右侧详情；均触发原逻辑）。
- **规则与边界**：条目外观由页签注册方经 `handle.setNarrow / MyAgentPubar.configureNarrow` 配置（icon / label / summary / summaryHtml / chip / actions）；未配置页签用缺省样式（默认图标 + 计数摘要）；浮窗内“节”与左栏内同款去壳；浮窗仅在窄态出现（宽态自动关闭并复位）；关闭时恢复页签 hidden 状态与 DOM 排序。
- **依据**：`public-sidebar.js::pubarRenderNarrowStrip / pubarBuildNarrowItem / pubarOpenNarrowPopover / pubarCloseNarrowPopover / pubarConfigureNarrow`；`plugins/{session-todo,agent-goal,change-review}/web/**`（configureNarrow / setNarrow 接线）；`app.css`（`.pubar-narrow-strip / .pni / .pubar-narrow-popover`）；双 shell 的 `#pubar-narrow-slot`。

### UC-5M15 统一悬停说明与自适应面板宽度
- **触发**：悬停/聚焦面板条目（计划/目标/插件/改动/窄态条）或舞台横向空间变化。
- **预期现象**：悬停说明统一走 `setUiHoverTip`（无原生 `title`）——文本在布局前绑定、可见内实时更新、显示时翻译；被截断条目悬停呈现全文。面板宽度走 `--todo-panel-width / --toc-panel-width`（有空间时向内填满、原宽度为下限），改动审查抽屉跟随该变量。
- **规则与边界**：宽度由 `layout-panels.js` 分侧独立填充、先设 max-width 再测重叠（避免过渡期误折叠）；窄态弹层关闭钮等也带统一提示。
- **依据**：`public-sidebar.js`、`toc-todo.js::setUiHoverTip`、`layout-panels.js`、`plugin-ui-slots.js`、`plugins/{session-todo,agent-goal,change-review}/web/*`；回归 `tests/test_plugin_ui_frontend.py`。

## 3. 实现落点与顺序（工程口径）

**文件清单**

| 区域 | 文件 | 改动 |
|---|---|---|
| 外壳 DOM | `frontend/index.html`、`frontend/src/shell-body.html` | `#chat-todo-plan` 内新增 头部 / 页签条 / 页签容器；保留 `id="plugin-session-panels"`（降级容器，恰好一次）；`index.html` 不出现 `change-review` 字样 |
| 核心模块 | `frontend/src/app/modules/public-sidebar.js`（新增） | 页签模型、显隐、徽标、记忆、键盘；`MyAgentPubar` API（`paneHostFor / registerPane / hasContent / activate / sync / resetForSession`）与 `myagent:public-sidebar-ready` 事件 |
| 装载 | `frontend/src/app/index.js` | `uiSources` 注册新模块（`tocTodoSource` 与 `layoutPanelsSource` 之间） |
| 渲染接线 | `frontend/src/app/plugin-ui-slots.js` | `normalizeProjectedItem` 透传并校验 `group`；`renderSessionPanels` 按组路由到页签宿主（缺失时回退 `#plugin-session-panels`） |
| 布局逻辑 | `frontend/src/app/modules/layout-panels.js`、`toc-todo.js` | `todoPanelHasVisibleContent` 与 `syncExtensionPanelVisibility` 优先 `MyAgentPubar.hasContent()`；`clearOptionalPanelsForSessionLoad` 追加 `resetForSession()` |
| 样式 | `frontend/src/styles/app.css` | 整条玻璃面、页签条、节规格（去卡壳）、响应式；几何与令牌契约不变 |
| 插件 | `plugins/session-todo/web/session-panel.css`、`plugins/agent-goal/web/session-panel.css` | 收敛为透明节（保留业务状态样式与弹窗） |
| 插件 | `plugins/change-review/web/change-review.{js,css}` | 注册「改动」页签并渲染入栏；兜底条规则更新；抽屉保留为回退 |
| 后端 | `app/plugins/ui.py` | `session.panel` 透传 `group`（id / label / order 校验；缺省不填） |
| 清单 | `plugins/{session-todo,agent-goal}/.myagent-plugin/plugin.json` | 分别声明 `group: {plan, 计划, 10}`、`group: {goal, 目标, 20}` |
| 词条 | `frontend/src/app/modules/i18n.js` | 新增 `会话扩展 / 计划 / 目标 / 插件 / 改动` 英文映射 |
| 文档 | `../../plugin_api_v1.md` | `session.panel` 增补 `group` 字段说明（实现后） |

**顺序**：P1 外壳与页签（双 shell + 新模块 + 基础 CSS）→ P2 分组接线（`ui.py` + manifest + 路由 + 词条）→ P3 面板换装（四类 CSS 收敛 + 改动入栏 + 徽标 / 脉冲）→ P4 测试与构建（`npm run build`、`verify:dist`）→ P5 收尾（能力清单 / 不变式转正、补证据）。

## 4. 测试与验证

- **更新**：`tests/test_frontend_theme_variants.py`（新契约字符串）、`tests/js/plugin_ui_slots_runtime.mjs`（`group` 透传 / 非法丢弃）。
- **新增**：`tests/test_public_sidebar.py`（双 shell 骨架与唯一 id、核心不引用插件专有类名）、`tests/js/public_sidebar_runtime.mjs`（页签显隐 / 激活 / 记忆 / 徽标）。
- **回归**：`tests/test_side_panel_content_overlap.py`、`tests/test_composer_side_control_alignment.py`、`tests/test_human_interaction.py`。
- **构建**：`cd frontend && npm run build` → `npm run verify:dist`（dist 为生成物，不手改）。
- **实机**：本机实例逐状态截图（仅计划 / 仅目标 / 插件 / 改动 / 全空收起 / 窄宽自动折叠 + 兜底条 / 浅色 / 深色 / 中英文）。

## 5. 风险与对策

1. 页签切换引起高度变化 → 自动折叠抖动：复用冷却机制抑制一次几何回调，或给内容区设最小高度。
2. Todo 完成自隐 / Goal 删除自隐与页签显隐联动：以“无可见子元素”为准则，在每次渲染事件后重算。
3. 改动信息双显（页签 + 兜底条）：见 UC-5M8 互斥规则。
4. 窄宽 4 页签拥挤：响应式压缩，极端情况下隐藏数字徽标。
5. 会话切换残留：`resetForSession()` + 现有 cleanup 双保险。

## 6. 实现采用的默认值（如与预期不符请指出）

1. 页签显示：**只有 1 类内容时不显示页签条**（备选：始终显示 4 个）。
2. 徽标：**仅「改动」= 文件数、「插件」>1 时 = 面板数**（备选：全加 / 全不加）。
3. 收起按钮：**头部按钮与边缘把手并存**（备选：仅留把手）。
4. 兜底条：**公共栏不可用时显示、栏内可取时不同显**；公共栏**收起**（窄态）时改由输入框上方「窄态条目区」承载（见 UC-5M15；备选：继续用旧兜底条）。
5. 新内容出现：**自动切换到最新生成/更新的页签**（会话切换后 4s 抑制期内回退为脉冲提示；用户点按页签即取消待切换）。

## 7. 版本记录

- 2026-10-04 v3：新增 UC-5M15《统一悬停说明与自适应面板宽度》——悬停说明全面走 `setUiHoverTip`（布局前绑定、实时更新）；面板宽度变量化并自适应填充（原宽下限）。

- 2026-10-03 v9.4：**计划「进行中」图标改为描边播放三角（参考 DSH/ZCode）**——原 3/4 缺口弧环辨识度差、已退役。参考口径：DSH（`packages/client/ui-tool/.../ToolDetails.tsx`）进行中 = `IconPlayOutlineRegular` 14px、完成 = 对勾、待办 = 10×10 描边方块，且无动画（该包无 `@keyframes`）；ZCode（`apps/zcode-cli/packages/tui/src/app-sidebar.tsx`）侧栏标记 = `[x] / [>] / [ ]`，进行中取 `palette.accent` 强调色。本实现采用描边播放三角（沿用 `.todo-plan-status-icon` 的 stroke 家族 + 既有 `--accent` 高亮，未加动画），path 由 `M12 3.8A8.2 8.2 0 1 1 3.8 12` 改为 `M8.6 6.6 17.6 12 8.6 17.4Z`；待办圆环与完成「圆环+对勾」保持不变。验证：pytest（新增 `test_todo_in_progress_icon_uses_play_glyph_like_dsh_and_zcode`，断言新 path 存在且旧弧环已移除）+ 实机 DOM 探针（进行中 path 生效）+ 截图（`workspace/左侧栏统一_分析/浮窗截图/计划图标_进行中_播放三角_特写.png`、`计划图标_进行中_播放三角_左栏.png`）。
- 2026-10-03 v9.3：**「改动审查」节内文字规格对齐计划节**——节头行改与 `.workspace-side-panel-title` 同规格（`min-height 1.05rem`、`margin 0 0 0.3rem`、`padding 0 0.15rem`、`gap 0.32rem`），标题字 `650 0.62rem/1.3` + `--workspace-side-panel-title` token + `0.05em` 字距 + uppercase；节头右上统计 `500 0.56rem/1.3` + 等宽数字；列表改 flex 列向 `gap 0.22rem`（对齐 `.workspace-side-panel-list`）；条目内边距对齐 `.workspace-side-panel-item` 的 `0.38rem 0.4rem`（去掉 `.change-review-file-head` 的叠加内边距）；路径文字改 `400 0.68rem/1.45`（字号/字重/行高对齐计划条目文字，仍保留等宽字体便于读路径）；行内统计 `500 0.56rem/1.3`；「已撤销」标记补 `0.4rem` 右内缩。验证：pytest 21 passed（新增 `test_change_review_section_typography_matches_the_plan_section`）+ 实机截图（`workspace/左侧栏统一_分析/浮窗截图/风格对齐_计划节参照_左栏.png`、`风格对齐_改动节_浮窗.png`、`风格对齐_改动节_左栏.png`）。
- 2026-10-02 v9.2：**改动审查关联跟随「正在查看的轮次」**——修复“切到别的轮次后改动审查不收起”：`viewportAggregate` 新增查看轮判定（`viewedTurnRange`：贴近底部 = 最新轮，否则取视口中线以上最近一条用户消息所在轮），候选过程框仅取正在查看的那一轮；“过程框收起也关联显示”的兜底仅在查看最新轮时生效（`viewportFallbackAllowed`），切到别的轮次 → 返回空 → 页签/窄态条目随之收起。验证：node 运行时（新增 `pickReviewedTurnKey` / `viewportFallbackAllowed` 断言）+ pytest 28 passed + 实机（停在旧轮：收起；滚回底部：恢复）。
- 2026-10-02 v9.1：**窄态条目箭头右缘对齐（微调）**——展开箭头从 `main` 内部移到条目 DOM 末尾（动作按钮**之后**）、`pointer-events:none` 并给条目本体补点击兜底，保证含动作按钮的条目（GOAL / 改动）与其余条目箭头在同一条右缘线上；四种条目浮窗（计划/目标/插件/改动）实机截图归档（`workspace/左侧栏统一_分析/浮窗截图/`）。
- 2026-10-02 v9：**窄态条目区（输入框上方）+ 专用浮窗落地**——① 样式整体对齐原型：单行玻璃胶囊（图标 + 标题 + 计数/摘要 + 可选状态胶囊 + 行内动作 + 箭头，37px 高，深浅两态）；② 交互按钮出面：GOAL 条目带开始/暂停、编辑、删除（复用页签内按钮点击），改动条目带「查看」（开右侧详情），计划条目带 `N / M 已完成` 摘要；③ 点击条目改为打开**专用浮窗**（对标 skill 选择弹窗；不再展开左栏）：页签宿主就近搬运进浮窗、插件持续实时渲染，关闭（× / Esc / 点外部 / 栏展开）后复位；左栏在窄态视同不存在（互斥）。核心 API：`handle.setNarrow` / `MyAgentPubar.configureNarrow`。验证：pytest 26 passed（含穷尽接线断言）+ `npm run build` + `verify:dist` + 实机（条目区 / 浮窗开合 / 宿主复位 / GOAL 动作点击 / 四类条目数据探针；截图 `workspace/左侧栏统一_分析/样例_窄态条目区_实测.png`、`样例_窄态浮窗_实测.png`）。
- 2026-10-02 v8：**命名调整为「会话状态」+ 计划条目 3 行截断**——①对用户的名称由「会话扩展」调整为「会话状态」（栏头标题 / 面板与页签 aria / 把手 aria「折叠会话状态面板」/ i18n 英文词条同步；文档沿革保留旧称）；②计划条目正文最多 3 行（`-webkit-line-clamp:3`），超出的条目在统一悬停浮框（`#ui-hover-tooltip`）中完整呈现——核心新增 `globalThis.bindUiHoverTip` 桥接（插件为 ES 模块，裸标识符取不到核心函数），插件仅对实际被截断的条目挂 `data-ui-tip` 并绑定，且带延迟补测覆盖“面板尚不可见”的渲染时机。
- 2026-10-02 v7：**计划状态图标打磨**——进行中改为缺口弧环（加载环形态，替代半环实心）；条目改 flex 行、图标按行高换算与首行文字**中线对齐**（实机偏差 3.3px → 0）。

- 2026-10-02 v7：**头部折叠箭头移除**——「会话扩展」标题栏不再设折叠按钮，开合统一走右缘把手（`#todo-edge-tab`，`aria-label` 语义保留）；把手 / 自动折叠 / 记忆逻辑未动。

- 2026-10-02 v6：**计划条目状态胶囊 → 状态图标**——已完成 = 绿色圆勾（正文仍删除线）、进行中 = 强调色半环、待处理 = 中性空环；语义文字移入 `aria-label` / 悬停提示；行卡与节头排版不变。

- 2026-10-02 v5：**自动跟随规则修订（新增 UC-5M14）**——把“新内容只脉冲、不抢焦点”改为“**自动切换到最新生成/更新的页签**”：`pubarTrackNewContent` 对页签出现（hidden→visible）与数量增长执行跟切（150ms 合并、末次为准）；新增 `MyAgentPubar.notifyActivity(el)`，计划/目标渲染器以渲染签名上报实质更新（秒级计时/用量刷新不触发）；会话切换后 4s 抑制期内回退脉冲提示；用户点按页签即取消待切换。UC-5M5 与 §6 第 5 条同步修订。验证：node 运行时（自动切换 / 抑制回退 / 显式通知 / 未挂载延迟补发用例）+ pytest 59 passed；`npm run build` 与 `verify:dist` 通过；实机验证：文件改动 +1 → 自动切到「改动」、计划更新 → 自动切到「计划」（探针确认延迟补发解析 pane=plan）。

- 2026-10-02 v4：**细节设计点入册**——新增《UC-5M13 节内容细则（终稿 · 实机确认）》：节头单行（标题 + 计数/统计 + 操作位）、计划条目内联胶囊与「完成划线仅正文」、改动节头紧凑净增删 + 路径尾部优先省略（悬停显示完整路径）、目标「已用/剩余」摘要与底部按钮行、页签显隐与徽标规则、响应式压缩等固化为规范。同轮修正：① 暂停/开始图标单显（SVG 的 `hidden` 须用 `toggleAttribute`，property 写法无效）；② 计划条目列表不预留滚动条槽（`scrollbar-gutter:auto`，条目左右内边距对称——修复「右空隙比左宽 10px」）。

- 2026-10-02 v3：**页签内容按原型「节」规格重排**（工作区，待提交）——① 计划：节头并为单行（标题 + `N / M 已完成` + 清除 ×），条目改为「内联状态胶囊 + 正文」，完成态删除线只作用于正文、胶囊保留绿色；② 改动：节头并为单行（标题 + `+x −y` 净增删 + 查看），文件行改为圆角行卡（路径省略 + 彩色增删），卡内 footer 退役（查看移至节头）；③ 目标：新增「已用 X · 剩余 Y」摘要行（操作按钮行与结果审核保持卡片底部原位，与旧版一致）；④ i18n 增「已用 / 剩余」；⑤ 修复改动列表 grid 撑宽（`minmax(0, 1fr)` + `min-width: 0`，长路径不再撑破 9.5rem 栏宽）；⑥ 改动行路径改为**尾部优先省略**（省略前面、保留文件名段——同质前缀 `D:\AI\AI Agent\…` 不再占位；`direction: rtl` + 左侧省略号，悬停 `title` 显示完整路径）。验证：全量 pytest 1781 passed（另有 1 项附件导出用例为本机既有环境问题、与本改动无交集）、`npm run build` + `verify:dist`、node 运行时（change-review 可见性 / 统计）、实机核对（计划 / 改动两态截图已更新；目标因本会话无 Goal 未做实机截图，结构由静态测试覆盖）。

- 2026-10-02 v2：**实现落地（工作区，待提交）**——① 新增 `frontend/src/app/modules/public-sidebar.js`（`MyAgentPubar`：`paneHostFor / registerPane / hasContent / activate / sync / resetForSession`；页签显隐、徽标、活动页签记忆、键盘切换）；② `plugin-ui-slots.js` 按 `group` 路由渲染（缺失时回退 `#plugin-session-panels`），`normalizeProjectedItem` 透传并校验 `group`；③ `app/plugins/ui.py` 投影 `group`，session-todo / agent-goal manifest 声明 `plan` / `goal`；④ change-review 注册「改动」页签（栏内可取时不显示输入框条，栏收起 / 不可用时兜底条显示）；⑤ `layout-panels.js` / `toc-todo.js` 统一以 `MyAgentPubar.hasContent()` 判定“是否有内容”；⑥ i18n 增「会话扩展 / 计划 / 目标 / 插件 / 改动」。验证：pytest（101 + 135 passed）、node 运行时（public_sidebar / plugin_ui_slots / change_review）、`npm run build` 与 `verify:dist` 全绿；实机核对（本机 8192 实例）：展开 / 收起、页签切换与徽标、兜底条互斥、切会话自动展开、控制台零错误——截图见 `workspace/左侧栏统一_分析/实机_*.png`。

- 2026-10-02 v1：建立《公共左侧栏（会话扩展面板）》——把聊天区左缘 Todo / Goal / 插件面板 / 改动审查收敛为一条页签式公共栏（方案 B）：单一外壳与页签、内容驱动显隐、改动审查入栏（兜底条保留）、插件渲染契约不变；附实现落点、测试与风险清单。状态：🟡 规划中（待评审；实现后转 ✅ 并补证据）。

---

*依据来源：仓库源码（`frontend/src/app/{index.js,plugin-ui-slots.js}`、`modules/{layout-panels,toc-todo,i18n}.js`、`styles/app.css`、两份 shell、`plugins/{session-todo,agent-goal,change-review}/**`、`app/plugins/ui.py`）、既有测试与脚本（`tests/**`、`scripts/**`）、以及 [`../../../workspace/左侧栏统一_分析/`](../../../workspace/左侧栏统一_分析/)（现状分析 v2、原型 v1 与截图）。*
