# 展开/收起统一过渡动效 · 功能方案设计（UseCase 清单）

- 版本：2026-10-07 v1（覆盖至：当前工作区；统一收放过渡）
- 用途：记录前端可折叠内容的共用动效规则及接入范围。
- 适用实现：`frontend/src/styles/collapse-transitions.css`、`frontend/src/app/modules/collapse-transitions.js`、`frontend/src/styles/app.css`、`frontend/src/styles/dock.css` 及对应前端模块。
- 上级：[00-WebUI对话界面整体设计.md](00-WebUI对话界面整体设计.md)

---

## 1. 设计目标

前端内已有多处展开/收起交互。它们共用一套持续时间、缓动、透明度和箭头反馈，使面板变化连贯且节奏相近；保留各区域自己的布局、滚动和状态语义。

## 2. UseCase

### UC-5P1 共用动效规则
- **触发**：任意已接入的折叠区域切换展开状态。
- **预期现象**：内容高度与透明度同步过渡，指示箭头随状态旋转；常规内容面板使用 220ms，详情栏使用 280ms，缓动使用统一的 ease-out 曲线。
- **规则与边界**：共用令牌为 `--ui-collapse-duration`、`--ui-panel-collapse-duration` 与 `--ui-collapse-easing`；高度从 `auto` 过渡依赖 CSS `interpolate-size: allow-keywords`。不支持该特性的浏览器仍按最终展开状态显示内容，但高度变化可能不做插值。系统设置 `prefers-reduced-motion: reduce` 时，共用时长缩至 1ms；既有明确禁用过渡的规则继续生效。
- **依据**：`styles/collapse-transitions.css`。

### UC-5P2 会话侧栏分区与分组
- **触发**：点击会话侧栏分区、时间分组或工作目录分组标题。
- **预期现象**：列表内容平滑展开/收起，标题箭头同步变化。
- **规则与边界**：折叠态内容不响应指针操作；容器仅在过渡期间裁切内容，结束后恢复溢出显示，避免会话操作菜单长期被裁掉。会话搜索框继续用原生 `hidden` 显隐，不加入高度过渡，避免隐藏时占据侧栏工具栏布局空间。
- **依据**：`.session-section-body`、`.session-group-body` 的共享样式；`session-management.js` 的会话搜索显隐逻辑。

### UC-5P3 消息区执行过程与长内容
- **触发**：展开或收起执行过程主体、执行轨迹条目，或长用户消息。
- **预期现象**：执行过程主体及轨迹长内容的高度/透明度平滑变化；长用户消息保留原有渐隐预览和“展开全部/收起”控件，最大高度过渡使用统一时长与缓动。
- **规则与边界**：执行过程主体仍保留自身可视高度上限和滚动行为；折叠内容在动效期间裁切，动画完成后恢复所需溢出行为，避免下拉菜单等浮层长期被父容器裁剪。消息文本、事件数据与折叠状态持久化规则不变。
- **依据**：`message-rendering.js`、`collapse-transitions.js`、`.process-aggregate-body` / `.feed-chunk-scroller` / `.user-msg-full` 样式。

### UC-5P4 技能、交互详情与工作区文件树
- **触发**：折叠技能分类组、只读人工交互卡片的摘要/详情，或详情栏文件树目录。
- **预期现象**：各区域共用内容折叠时长、缓动和箭头/切换反馈；状态切换与内容显隐同步。
- **规则与边界**：技能组、只读交互卡片和文件树折叠内容同步 `aria-hidden` / `inert`，折叠后不进入键盘焦点顺序；区域原有业务操作、滚动和数据状态不改变。
- **依据**：`skill-picker.js`、`human-interactions.js`、`dock/embedder/right-column.js`、`dock.css`、`collapse-transitions.css`。

### UC-5P5 详情栏收起
- **触发**：详情栏切换开合状态。
- **预期现象**：栏宽与面板内容位移平滑变化，整体时长为 280ms；和内容分组的折叠动效保持同一缓动风格。
- **规则与边界**：窄屏全屏/覆盖模式和既有面板状态判定不因动效改写；减少动态效果偏好生效。详情栏布局和菜单浮层行为沿用既有实现。
- **依据**：`dock/embedder/right-column.js`、`modules/collapse-transitions.js`、`styles/dock.css`。

## 3. 边界

- 统一的是动效令牌和视觉节奏，不合并各组件的开合状态管理。
- 会话搜索框特意保留 `hidden` 显隐，不做高度动画；上次尝试将其改为参与 flex 高度过渡时，收起状态侵占了侧栏工具栏空间，因此已回退。
- 高度自动插值依赖浏览器对 `interpolate-size: allow-keywords` 的支持；此兼容性只影响动画是否平滑，不影响最终开合状态。

## 4. 依据映射

| 范围 | 主要依据 |
|---|---|
| 共用时长、缓动、减少动态效果 | `frontend/src/styles/collapse-transitions.css` |
| 过渡期间的溢出处理 | `frontend/src/app/modules/collapse-transitions.js` |
| 会话侧栏分区/分组 | `frontend/src/styles/app.css`、`frontend/src/app/modules/session-management.js` |
| 执行过程、轨迹行、长用户消息 | `frontend/src/app/modules/message-rendering.js`、`frontend/src/styles/app.css` |
| 技能组、只读交互卡片 | `frontend/src/app/modules/skill-picker.js`、`frontend/src/app/modules/human-interactions.js` |
| 详情栏、文件树 | `frontend/src/app/modules/dock/embedder/right-column.js`、`frontend/src/styles/dock.css` |

## 5. 版本记录

- 2026-10-07 v1：首次整理统一展开/收起动效方案——常规内容 220ms、详情栏 280ms；覆盖会话侧栏、执行过程与消息、技能组、只读交互详情、详情栏文件树及右栏开合；补充减少动态效果、辅助技术状态和搜索框不参与动画的边界。
