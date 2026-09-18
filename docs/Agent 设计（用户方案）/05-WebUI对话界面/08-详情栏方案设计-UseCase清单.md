# 详情栏 · 功能方案设计（UseCase 清单）

- 版本：2026-09-14 v6（覆盖至：HEAD `d022831` + 详情栏三轮反馈与开文件策略更新）
- 用途：逐条审查（四字段格式）。
- 适用实现：`frontend/src/app/modules/dock/**`（engine 8 件 / renderer 5 件：icons、gesture、measure、dock-surface、float-layer / embedder 3 件：surface-store、tab-registry、right-column）、`frontend/src/styles/dock.css`、`frontend/src/app/index.js`（`?raw` 登记）、后端 `GET /api/workspace-file-text`、测试 `frontend/tests/dock-engine.test.mjs`（24 项）、冒烟 `workspace/分屏功能需求/dock_verify/dock_smoke.py`（30 项）。
- 上级：`00-WebUI对话界面整体设计.md`；技术细节与序列化格式见 [`../../frontend-dock.md`](../../frontend-dock.md)；诊断脚本 `dock_verify/turn_scope_probe.py`、`dock_verify/scope_probe_browser.py`。
- 参照实现：dsh 新版 `packages/client/ui-dockkit`（引擎/组件/契约、`SplitGlyph`）、`ui-sidebar-right`（右栏产品化、`ExpandButton` 角落按钮、`PanelChrome` 条尾控件）、`ui-sidebar-files` / `ui-sidebar-documentpreview`（文件树与文件预览类型）。

---

## 1. 功能定位

按 dsh 的三段式布局，WebUI 从"会话栏 + 工作区"扩为：最左会话列表、中间会话、右侧一个**可开合的详情栏**（dockkit 的唯一挂载点）。详情栏推挤工作区、按会话记忆状态，内含「开始（guide）/ 工作区文件 / 文件内容 / 修改历史」四类页面；打开入口是会话标题右上角（header corner）的图标按钮，与 dsh 的 `ExpandButton` 相同——28px 圆形按钮、15px 面板图标（左侧栏图标镜像，分隔线在右），图标路径逐字取自 dsh 源码，**仅在收起时显示**（展开后隐去，[hidden] 带 `display:none` 兜底）。

> 历史说明：早期版本曾同时在主内容区挂一套"会话分屏 + conversation 标签 + 只读镜像"。v2 按用户要求**整体移除**（分屏按钮、conversation 类型、镜像管线全部删除），主内容区回到应用原有形态；引擎、渲染器与注册表只保留详情栏实际使用的部分，引擎层保留了全方向/4 面板等能力（产品层收紧为水平两面板）。

## 2. UseCase

### UC-5H7 详情栏开合、推挤、过渡与宽度
- **触发**：点击会话标题右上角的图标按钮（`#dock-rightbar-toggle-btn`）。
- **预期现象**：右侧出现第三列（默认 460px），工作区平滑让位（实测 1220→760px）；左缘 8px 可拖宽（320–960px，双击复位，宽度按浏览器记忆）；窄屏（<768px）打开自动全屏；收起即完全不占位。
- **规则与边界**：角标**只在收起时显示**（展开后隐去；样式层显式 `[hidden]{display:none}`，防止 `display:inline-flex` 覆盖默认行为——此前"展开后按钮还在"的根因）；开合有 **180ms 宽度+透明度过渡**；同一列自身的 tab 条右端也有全屏/收起控件（`PanelChrome`）；每会话各自保留开合状态与布局；⚪ 默认不落盘（与 dsh memory-only 一致）。
- **依据**：`dock/embedder/right-column.js`（`dockRightToggle` / `dockRightEnsureButton` / `dockRightStartResize` / `dockRightRender` / `dockRightBuildChrome`）、`dock.css`（`.dock-rightbar` / `.dock-expand-btn[hidden]` / `.dock-rightbar-sash`）、`surface-store.js`（区域 `right`）。

### UC-5H8 详情栏 · 开始页（guide，默认页与兜底页）
- **触发**：详情栏首次打开；`+` 新建窗口；关闭页签后由 settle 回填；`MyAgentDock.openDetailsTab('guide')`。
- **预期现象**：居中展示指南针图示与两张引导卡（工作区文件 / 修改历史），点卡片即打开对应页。
- **规则与边界**：关闭**最后一个页签**时由 settle 自动重播种开始页（栏不随之收起）；**当栏内只剩这一个开始页时，关闭它 = 收起详情栏**（用户口径）；`+` 在目标面板新建一个开始页（"空窗口"），一个面板至多一个；分栏产生的新面板也以开始页落座（不再复制同一窗口）。
- **依据**：`right-column.js`（`dockRightGuideBody` / `dockRightSeed` / `dockRightOpenPageKind`）、`surface-store.js`（`dockActionCloseTab` 的"孤零开始页=收栏"分支）。

### UC-5H9 详情栏 · 工作区文件页
- **触发**：开始页的"工作区文件"卡片，或点「工作区文件」页签。
- **预期现象**：逐层展开的工作区文件树；目录优先排序、目录可展开收起（▸/▾ + 文件夹图标）、文件显示分类图标与大小；点文件打开「文件内容」页；可刷新。
- **规则与边界**：数据来自既有 `GET /api/workspace-files?dir=`；资源地址形如 `myagent-resource://file/<rel>`，与 dsh 的 `dsh-resource://file/**` 同构；**滚动位置按页签记忆**，切换到其它页签再回来会恢复到原位置（浏览器会丢弃脱离文档的 scroller 位置，由 `__dockRestore` 在挂回时补写）；分类图标为按扩展名着色的内联 SVG（图片/代码/配置/文档/PDF/文件夹/通用文件）。
- **依据**：`right-column.js`（`dockRightFilesBody` / `dockRightLoadDir` / `dockRightFileRow` / `dockRightFileIcon` / `dockRightTrackScroll`）。

### UC-5H10 详情栏 · 文件内容页与统一开文件策略
- **触发**：在文件树点一个文件；`MyAgentDock.openDetailsFile(rel)` / `openResource('myagent-resource://file/…')` / **`openPathSmart(path)`**；或点击会话消息里的工作区文件链接（`a.msg-link-workspace-open`）。
- **预期现象**：图片走 `/api/workspace-image` 内嵌；音频/视频走 `/api/workspace-media`（带播放控件）；**文本类后缀**（md/txt/log/csv/json/yaml/py/js/ts/html/css/sql/sh/ps1/c/cpp/java/go/rs…白名单）显示为等宽正文，超过 200 KB 截断并提示；**其它类型**（pdf/office/压缩包/可执行/图片/音视频/无扩展名等）显示"此文件需在系统应用中打开"卡片并可一键系统打开；工具栏始终提供系统打开入口。
- **规则与边界**：会话文件链接与文件树点击**共用同一判定**（`MyAgentDock.isTextPath` / `openPathSmart`）：文本→详情栏，其余→系统应用；文本读取走**新增的最小只读接口** `GET /api/workspace-file-text?rel=&max_bytes=`（UTF-8、按上限截断并回传 `truncated`、路径经与媒体接口相同的允许根校验、绝不写文件）；读回内容替换字符占比 >2% 时自动降级为"系统打开"卡片（不再展示乱码）；⚠️ 该接口为后端路由，**需重启一次服务**才生效，生效前文本页显示"文本接口尚不可用"提示；内容区滚动位置同样按页签记忆。
- **依据**：`right-column.js`（`dockRightDocumentBody` / `dockRightLoadText` / `dockRightOpenPathSmart` / `dockRightIsTextPath` / `dockRightSystemCard`）、`session-scroll-history.js`（链接委托改走 `openPathSmart`）、`app/webui.py`（`workspace_file_text`）。

### UC-5H11 详情栏 · 修改历史页
- **触发**：`MyAgentDock.openDetailsTab('changes')`；开始页卡片；或点击 Change Review 插件的「查看」按钮（被捕获后改为打开本页）。
- **预期现象**：两个范围档位——**本轮**（默认）与 **本次会话**；每条列出路径、文件名、操作、+/− 行数与可展开的 ± 着色 diff，卡片式外观（整行底色、文件头、状态行，风格与改动审查一致）；每条带「撤销」（撤销后变「恢复」）；新的改动实时追加。
- **规则与边界**：数据源为会话历史里已持久化的 `ui.changes`（`path / operation / revision / snapshot_id / added / removed / diff / effective / reverted`），按路径去重取最新 revision；扫描走 `/sessions/{id}/history_snapshot`（limit 500 / turns 50 / event_budget 5000 / include_aux=false），并带**20s 超时、失败静默重试 ×2、2s 看门狗**（首次打开与会话切换并发时的一次扫描失败不再留下空页）；**"本轮"边界 = 最近一条用户消息**，并且**新的用户消息到达时即时推进边界**（此前只在首次扫描计算，导致"本轮"停留在上一轮）；撤销/恢复复用 Change Review 既有路由 `POST /sessions/{id}/change-reviews/undo|restore`（工作区有运行任务时服务端 409，界面显示原因）；页内监听 `myagent:ui-event`。
- **依据**：`right-column.js`（`dockRightChangesBody` / `dockRightChangeRow` / `dockRightChangeAction` / `dockRightFetchJSON` / 监听器的 user 分支）、`plugins/change-review/{web/change-review.js,host.py}`。

### UC-5H12 详情栏的多标签、分栏与浮动
- **触发**：详情栏内继续打开内容；拖动 tab 条上的标签；点击标签条上的分栏图标（dsh `SplitGlyph`：面板框+居中竖线）；拖动标签到左/右半区。
- **预期现象**：同一栏可开多个标签（页面按 kind 唯一）；标签可在栏内重排、拖到左右半区分栏（受两面板上限与房间规则约束），标签可拖成浮动面板（380×300、级联 24px），再放回收起。
- **规则与边界**：产品限**水平方向、栏内至多两面板**；**到达两面板后分栏控件隐藏**（dsh `hideSplitWhenBlocked`，不留死按钮），栏宽不足时同样隐藏/禁用；分隔条两侧吸收全部变化，每侧最小 20%（引擎下限 12%）；条尾三个控件的图形均逐字取自 dsh（分栏=面板框+中线，全屏=四角括号/退出为两内收角，收起=面板图标镜像），28px 圆钮内 15px 图标、间距 4px；拦截与快捷键与 dsh 相同（指针捕获、焦点落 click、chip 键盘 ←/→/Home/End + Enter/Space）；胶囊（chip）38px 条内上下各 5px 真正居中，最小宽 96px / 最大 230px，浅色主题加底色与描边以保证可见。
- **依据**：`dock/engine/**`（operations / planner / constraints / geometry / sequence / controller）、`dock/renderer/**`（dock-surface / float-layer / gesture / measure / icons）、`dock.css`、`right-column.js`（`dockRightIntents` / `dockRightOpenResource` / `canSplitSurface` / `hideSplitWhenBlocked`）。

### UC-5H13 dockkit 扩展点（插件 / 脚本可用）
- **触发**：插件或页面脚本调用 `MyAgentDock` 公开 API。
- **预期现象**：`registerTabType({id, kind, patterns, priority, canOpen, title, body})` 注册新内容类型；`openResource(address)` 按 `extension > builtin > fallback` → 模式长度 → 注册顺序解析并落座；`openDetails()` / `toggleDetails()` / `closeDetails()` / `openDetailsTab(kind)` / `openDetailsFile(rel)` / **`openPathSmart(path)`** / **`isTextPath(path)`** / `detailsState()` 操作详情栏；`openSession(sessionId)` 切会话（其详情栏状态随动）；`sessionId()` 读当前会话；`myagent:dock-ready` 在就绪后派发。
- **规则与边界**：页面类型按 kind 打开且**每面板唯一**（同 kind 再开会聚焦而非重复）；资源类型 `canOpen` 一票否决；详情栏内置类型 id 为 `myagent.details.guide` / `.files` / `.document` / `.changes`。
- **依据**：`dock/embedder/tab-registry.js`（`DockTabRegistry` / `dockCompileGlob` / `dockPageAddress`）、`right-column.js` 末尾的 `MyAgentDock` 装配与事件派发。

## 3. 边界

- **不做**：主内容区的会话分屏（v2 已整体移除）；移动端专门适配（仅窄屏全屏策略）；分屏布局持久化（默认 memory-only，可后续按技术文档接入）；撤销/重做按钮 UI（引擎历史保留，当前无入口）。
- **"本轮"的口径**：指**最近一条用户消息之后**的改动（含正在进行的这一轮）；若需要"最近一次改动批次 / 最近一次工具调用组"为界，作为后续增强项，需另行确认口径。
- **改动审查的数据归属**：本页是"会话改动的只读聚合 + 撤销入口"；改动的捕获、统计与安全撤销语义属 06-能力扩展加载的 Change Review 插件，不在本篇。
- **文件访问安全**：四个页共用既有允许根校验；文本接口只读、限长。

## 4. 依据映射

| UseCase | 主要依据 |
|---|---|
| UC-5H7–5H12 | `frontend/src/app/modules/dock/**`、`styles/dock.css` |
| UC-5H10 文本接口 / 统一策略 | `app/webui.py::workspace_file_text`、`right-column.js`（`openPathSmart` / `isTextPath`）、`session-scroll-history.js` |
| UC-5H11 撤销/恢复 | `plugins/change-review/{web/change-review.js,host.py}`（`change-reviews/undo\|restore`、「查看」捕获） |
| 验证 | `frontend/tests/dock-engine.test.mjs`（24 项）、`workspace/分屏功能需求/dock_verify/dock_smoke.py`（30 项：角落按钮（含计算样式隐藏）/ 推挤 / 开始页 / 文件树与分类图标 / 分栏与上限隐藏 / 孤零开始页收栏 / 拖宽 / 文件内容 / 文本链接 / 滚动记忆 / 修改历史双档与"新用户轮次重置" / 撤销按钮 / 会话随动 / 收起与重开 / 无页面错误） |

## 5. 版本记录

- 2026-09-15 v9：**HTML 可直接渲染到详情栏**——文件内容页对 `.html/.htm` 默认以**沙箱 iframe 网页预览**呈现（`sandbox="allow-scripts"`，独立源、不可访问宿主 DOM/登录态），头带提供"查看源码/预览网页"一键切换与刷新；新增只读路由 `GET /api/workspace-assets/<rel>` 供页面内相对资源（css/js/图片）解析，与其它工作区读取同样经允许根校验、`no-store`；冒烟 42 项全绿。⚠️ 新路由需重启服务一次生效。
- 2026-09-15 v8：学习 dsh 文件页——工作区文件页新增**路径栏**（左侧工作区根路径、右侧 dsh 同款刷新图标，贴右 10px）；**修改历史页与文件内容页头部的刷新也统一为同一枚图标按钮**（内容页刷新=重读文本/重载图片与音视频，二进制类型禁用）；三页头部统一为**同一条 44px 工具带**，且**刷新固定在最右上角**（此前文件内容页三个元素 space-between 且标题无弹性，刷新被挤到中间）；修改历史页说明同步为**轮次下拉 + 会话总览**实际形态（改动审查「查看」经 `openChangeReview` 聚焦批次）；冒烟 39 项全绿（含三条头带高度断言与三条"刷新贴最右"断言）。
- 2026-09-15 v7（回退）：**"查看"按钮恢复为 Change Review 插件的原生浮窗**——撤销本模块对 `.change-review-view` 的捕获劫持与"按批次对齐"实验（捕获、批次过滤、焦点胶囊全部删除）；详情栏其余功能不变。冒烟回到 30 项全绿。
- 2026-09-14 v6：正文按最终行为重写——角标"仅收起时显示（含 [hidden] 显示修复）"；新增 UC-5H8 开始页（兜底/空窗口/孤零关闭=收栏）；修改历史补"本轮/本次会话"双档与扫描健壮性（超时/重试/看门狗、新用户消息即时推进边界）；文件内容补统一开文件策略（`openPathSmart`）与乱码降级；UC-5H12 补条尾三控件为 dsh 原始图形与分栏控件到顶隐藏；UC 编号顺延（原 5H12 → 5H13）。
- 2026-09-14 v5：统一开文件策略——会话内工作区文件链接走 `MyAgentDock.openPathSmart`（文本→详情栏，其余→系统应用，判定与文件树一致）；同步 `isTextPath` 查询接口。"本轮"边界跟随新的用户消息**即时推进**（此前只在首次扫描时计算，发新消息后仍显示上一轮改动）。
- 2026-09-14 v4：三轮反馈——角标 `[hidden]` 显示修复；改动审查「查看」改开详情栏；修改历史双档（本轮/本次会话，默认本轮）并借用改动审查卡片样式；孤零"开始"页关闭=收起详情栏；浅色主题胶囊加底色/描边。
- 2026-09-14 v3：二轮反馈落地——角落按钮恢复"展开即隐藏"；开合加 180ms 宽/透明过渡；关闭最后一个页签不再收栏（settle 重播种"开始"页），`+` 新建空窗口；新增"开始"引导页；文件树分类图标；非文本自动转"系统打开"卡片；树/内容/改动滚动位置按页签记忆；分栏新面板落"开始"页、两面板后分栏控件隐藏；胶囊垂直居中并加宽。
- 2026-09-14 v2：按用户要求裁剪为主区**单挂载点**——移除主区分屏、conversation 标签与只读镜像管线；角落按钮改为 dsh `ExpandButton` 同款（图标、悬停、展开隐去）；UC-5H1~5H6（主区分屏系列）随功能作废，编号保留不再复用；本文件更名与内容以详情栏为准。
- 2026-09-14 v1：首版（主区分屏 + 右侧详情栏双挂载点）。
