# 2026-10-01 追问 pending 队列拖拽排序可用性修复

## 现象

运行中把追问排进 pending 队列后，用握把拖拽改顺序"很困难"：拖起来没有插入提示，松手不换位；偶尔看到提示线也放不下去。列表一长就完全没法把条目拖到看不见的位置。

## 根因（浏览器实测）

用真实 `sse-handling.js` 源码 + 真实构建 CSS 搭了脚手架，在 Chromium 里跑真鼠标拖拽抓事件流（`workspace/追问队列拖拽优化/`）：

- Firefox/Chromium 在**原生 HTML5 拖拽接管指针时会补发 `pointercancel`**（鼠标指针同样如此）。原实现把它绑到 `endFollowupDrag`，于是 `dragstart` 刚建立的 `followupDragState` 立刻被清空：
  - 面板 `dragover` 处理器开头 `if (!followupDragState) return;` 全部提前返回 → 从不 `preventDefault()`；
  - 浏览器于是拒绝 drop，`drop` 事件一次都不触发 → `moveFollowupQueueItem` 从未被调用。
- 实测事件序列：`dragstart(state=true) → pointercancel(state=false) → dragover(不 preventDefault) → dragend`，全程 **0 个 drop**，队列顺序不变。把 `pointercancel` 拦住后同一路径立刻能换位——证明这是"拖不动"的主因。

次要缺陷（同一次实测量化）：

| 项 | 修复前 | 修复后 |
| --- | --- | --- |
| 握把命中区 | 17×11px（188px²，只有 ⠿ 字形大小） | 40×26px（1013px²，含序号徽标） |
| 行间 3.4px 间隙 / 面板内边距落点 | 显示插入提示但松手无效（死区） | 吸附到最近待发送行，提示在哪就落在哪 |
| 拖长列表（6 条已可滚动） | 无自动滚动（scrollTop 0→0） | 指针贴边持续滚动（0→51px） |
| 键盘排序 | 无 | 握把聚焦后 ↑/↓ 移动，焦点跟随条目 |
| 拖拽期重绘 | SSE 触发的重绘会换掉被拖节点、静默取消拖拽 | 拖拽期推迟重绘，`dragend` 后补齐 |

## 变更

- `frontend/src/app/modules/sse-handling.js`
  - 新增 `onFollowupPointerCancel`：只有 `mode === 'touch'` 且指针为 touch/pen 时才结束拖拽，鼠标 `pointercancel` 不再拆掉 HTML5 拖拽态。
  - 新增 `resolveFollowupDropTarget / resolveFollowupDropTargetAtPoint`：行间隙、面板内边距、在途行（`data-reorderable="false"`）一律按插入位吸附到最近的待发送行；`dragover` 提示与 `drop` 落点共用同一次解析。
  - 新增 `applyFollowupDropIndicator`（去重写入 + 单一插入点）、`focusFollowupQueueGrip / moveFollowupQueueItemByOffset`（键盘排序，只在 pending 槽位间移动）。
  - 新增 `followupEdgeScrollDelta / trackFollowupAutoScroll / runFollowupAutoScroll`：rAF 循环的边缘自动滚动，指针静止也持续滚动。
  - `startFollowupDrag`：`setDragImage(row, …)` 用整行做拖影（原来只有一个 ⠿ 字形），并在 `requestAnimationFrame` 后加变暗样式以免拖影也被打薄。
  - `renderFollowupQueue`：拖拽期间推迟重绘（`followupDragRenderPending`），`dragend` 后补齐。
  - 行结构：`⠿` 与序号徽标合并进可聚焦握把 `.followup-queue-grip`（`role=button`、`aria-label` 带位置、`aria-keyshortcuts`），在途行的握把 `aria-disabled` 且不可拖。
- `frontend/src/styles/app.css`：握把命中区、悬停/焦点态、拖拽期"可放置行提亮 + 在途行压暗"、插入提示改为 2px 发光横条 + 端点圆点（画在行间隙里）。
- `frontend/src/app/modules/i18n.js`：新增握把 `title`/`aria-label` 静态串与动态位置串（`第 N 条，共 M 条：…`）的英文。
- `app/templates/dist/`：`npm run build` 重新生成（`main-DhhktKki.js` / `main-ChE06VLS.css`）。

## 测试与验证

- `tests/js/followup_dispatch_runtime.cjs` 新增 5 组：`pointercancel` 不得拆掉 HTML5 拖拽（根因回归）、落点吸附（间隙/内边距/在途行/无同列可换）、边缘滚动方向与力度、键盘排序只在 pending 槽位间移动、插入提示唯一。
- `tests/test_feature_flags.py::test_followup_pending_queue_supports_manual_drag_reorder`：保留原有契约串，追加 `onFollowupPointerCancel`、握把命中区、落点解析、自动滚动、`setDragImage`、键盘与 i18n 断言。
- 定向回归 21 个套件（含 feature flags、主题契约、human interaction、stream resilience 等）：**200 passed**；`node tests/js/followup_dispatch_runtime.cjs` 通过；`npm run verify:dist`：dist 与源码同步。
- 浏览器实测（真实源码 + 真实构建 CSS）：原生拖拽换位成功（`q1→q3 之后`）、间隙落点生效、自动滚动 51px、键盘 ↑/↓ 生效且焦点留在原条目、混合状态队列中在途行保持固定槽位、触摸拖拽路径回归正常。

## 文件

- `frontend/src/app/modules/sse-handling.js`、`frontend/src/styles/app.css`、`frontend/src/app/modules/i18n.js`
- `tests/js/followup_dispatch_runtime.cjs`、`tests/test_feature_flags.py`
- `app/templates/dist/`（构建产物）
- 验证脚手架与截图：`workspace/追问队列拖拽优化/`
