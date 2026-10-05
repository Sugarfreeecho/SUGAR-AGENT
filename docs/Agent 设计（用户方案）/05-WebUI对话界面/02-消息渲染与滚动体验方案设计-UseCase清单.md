# 消息渲染与滚动体验 · 功能方案设计（UseCase 清单）

- 版本：2026-10-05 v12（覆盖至：当前工作区；上下文补取缓存归属）
- 用途：逐条审查（四字段格式）。
- 适用实现：`modules/message-rendering.js`、`modules/smooth-stream.js`、`modules/session-scroll-history.js`、`modules/toc-todo.js`、`modules/workspace-media.js`、`modules/ui-performance.js`。
- 上级：`00-WebUI对话界面整体设计.md`

---

## 1. 功能定位

"文字怎么出现"的体验层：平滑流式、Markdown/代码/工具轨迹渲染、滚动与目录。

## 2. UseCase

### UC-5B1 平滑流式输出
- **触发**：模型流式返回。
- **预期现象**：文字平滑滚动（非大段跳变）；长回答顺滑不卡顿；流结束后与最终文本一致（不失真）；内容停顿（等工具/思考间隙）时跟随自然收尾（数百毫秒级）、无长尾拖尾。
- **规则与边界**：平滑是**渲染节流**，不改动真实内容顺序；极端高速流下允许"快进"。跟随运动为**固定刚度临界阻尼软弹簧**（DeepSeek 同款，速度连续、按实际帧长精确积分）：响应 ω = √180 ≈ 13.42/s 为常数、不随落后距离增强（慢启动、长收尾——19px 折行首帧 ≈0.4px、约 480ms 收敛）；底部目标变化时保留当前速度平滑续接（不重启动画），单帧写入上限 20px 仅在大位移时防爆冲；折行与整行插入/折叠共用同一规则、无速度地板与通道差异；到位阈值 0.25px，到位即清零速度。**稳态跟随滞后 ≈ 2v/ω**（v 为内容增长速率）：常规流式（1–4 行/s）<1.5 行，高速长段（>10 行/s）4–5 行为软弹簧物理特性（可上调 `followStiffness` 收紧）。文本揭示层（`revealDivisor`）保留，与跟随解耦：揭示只决定内容何时写入，跟随器只观察高度变化。
- **依据**：`smooth-stream.js`（跟随/揭示原语）、`session-scroll-history.js`（揭示调度）。

### UC-5B2 消息渲染（Markdown / 代码 / 工具轨迹）
- **触发**：任意消息上屏。
- **预期现象**：Markdown 正确（含表格/列表/代码块高亮）；工具调用显示为可折叠轨迹（命令/结果/状态）；mermaid 图按需加载渲染；运行中输出实时刷入工具行（见 UC-5B8）。
- **规则与边界**：执行过程框高度上限 = min(原 CSS `min(72vh, 41.6rem)`, 工作区可视高度 − 8px)——框高不得超出工作区可视区域，原上限保持不变；展开 / 滚动 / 窗口尺寸变化时重算（`message-rendering.js::applyProcessBodyViewportClamp` / `scheduleProcessViewportClampSweep`）。度量取“可视高度”而非“底边 − 框顶”（跟随钉底时后者会自我收缩）。
- **依据**：`message-rendering.js`、`app/index.js`（mermaid 懒加载）。

### UC-5B3 滚动历史锚点
- **触发**：长会话中滚动/跳转。
- **预期现象**：向上回看历史稳定（不被新内容顶飞）；"回到最新"入口可用；加载历史段时不闪屏。
- **依据**：`session-scroll-history.js`。

### UC-5B4 TOC 与 Todo
- **触发**：打开目录/Todo 面板。
- **预期现象**：TOC 定位准确（点击跳到对应消息）；Todo 面板实时反映任务计划（含状态变化）。
- **依据**：`toc-todo.js`、`update_todo` 事件投影。

### UC-5B5 媒体展示
- **触发**：消息含图片/文件引用。
- **预期现象**：用户消息图片以等高缩略图在气泡下方横向排列，空间不足时整张缩略图自动换行；文件链接按打开协议工作；加载失败显示稳定占位。同一附件 ID 同时出现在历史消息、工具轨迹和待发送队列时，共享一次 fetch 和一个 blob URL。
- **规则与边界**：缩略图使用固定尺寸和居中等比例完整缩放，保持每行视觉高度一致。共享项维护节点集合；最后一个节点移除时取消未完成 fetch 并撤销 blob URL。失败项不保留无效共享状态，后续重新出现可以重试。附件读取携带同源凭据，由服务端鉴权。
- **依据**：`workspace-media.js::renderDurableAttachmentImages/durableImagePreviews`、`GET /api/attachments/{id}`。

### UC-5B6 长会话性能
- **触发**：数百条消息的会话。
- **预期现象**：滚动/输入不卡；历史段懒渲染；内存不持续膨胀。
- **依据**：`message-rendering.js`、`session-scroll-history.js`（懒渲染/裁剪）；`ui-performance.js` 仅做采样与直方图诊断（非渲染层优化）。

### UC-5B7 长用户消息折叠预览（10 行）
- **触发**：用户消息较长（超过 10 行）进入折叠态；点击 / 键盘操作折叠控件。
- **预期现象**：只显示前 10 行、底部渐隐；**没有摘要副本**（直接裁剪原文，不重复内容）；下缘半胶囊切换控件（chevron + 文案）随状态变化——"展开全部 · 还有 N 行" ⇄ "收起"；展开/收起带 max-height 过渡。
- **规则与边界**：控件可点击也可 Enter/Space；带 `aria-expanded` / `aria-label` / `title`，语言切换时整体重刷；隐藏行数按实测行高计算（`USER_MESSAGE_COLLAPSE_LINES = 10`）；浅色主题使用专用渐隐遮罩。
- **依据**：`shared-state-and-dialogs.js::buildUserMessageCollapseToggle / renderUserMessageContent`（`user-msg-chevron`、`user-msg-expanded`、`--user-msg-full-h`）、`app.css`、`i18n.js`。

### UC-5B8 工具行实时输出与增量渲染
- **触发**：`run_shell` 执行中产生 stdout/stderr；或模型流式给出工具调用参数增量。
- **预期现象**：运行中输出以节流增量直接刷进对应工具行（首段带"实时输出" / `STDERR:` 前缀；超过 64 KiB 显示截断说明）；工具调用参数增量（`tool_call_delta`）按动画帧合并后渲染，无逐字符抖动。
- **规则与边界**：实时输出是 **ephemeral**（不落盘、不参与回放，断线不续）；最终结果仍按工具结束后的限长投影（`tool_detail_ui`）提供，UI 以最终结果收口。
- **依据**：`message-rendering.js`（工具行按帧渲染）、`agent_loop.py::_emit_run_shell_output / _ThreadToAsyncQueue`（`tool_command_delta` 合帧）、`agent_tools.py::_RunShellProgressPublisher`（≈40ms / 8 KiB 节流、64 KiB 上限）。

### UC-5B9 上下文用量浮窗拆解卡（对齐 DSH）
- **触发**：指针停留右上角上下文用量（约 180ms）或键盘聚焦；Escape / 移出收起。
- **预期现象**：浮窗为拆解卡——标题行「上下文已用 x%」+「~y / 阈值」、4px 三色占比条（系统提示词=蓝灰 / 工具定义=紫 / 对话消息=主题蓝）、三行图例（色块 + 名称 + `~token`）；占比条总长按精确百分比、分段按构成分配、0 宽度段丢弃、每段最小 2px；三行之和恒等于整包数字（行值带 `~`）；随三套主题自动取色；宽 264px（窄窗收敛 `100vw - 1.5rem`）。
- **规则与边界**：分母为压缩摘要阈值（非原始窗口），卡底保留一行灰色口径说明；有构成数据时不叠加纯文字提示，无构成时保留旧提示且不出现卡片；卡片贴在触发器右缘向下展开（不引入测量式锚定）；构成由 `build_context_breakdown` 本地估算（系统段按内容缓存计价、工具定义按 schema 余量、对话消息取整包估值余量），快照缺构成时端点只补构成不改总量。
- **依据**：`agent_tokenizer.py::build_context_breakdown`、`agent_loop.py`（pre-request 事件 / 压缩检查点 / 端点载荷）、`webui.py::get_session_context_tokens`、`session-scroll-history.js`（渲染）、`context-store.js`、`session-event-reducer.js`、`i18n.js`；回归 `tests/test_context_breakdown.py`、`tests/js/context_breakdown_card_runtime.cjs`。

## 3. 边界

- 渲染层不修改事件数据——所见即事件流投影。
- 主题（明暗）规范属设置面板（06）。

## 4. 依据映射

见上表（均为 frontend/src/app/modules/ 下文件）。

## 5. 版本记录

- 2026-10-05 v12：上下文构成补取保存至所属聊天缓存（切聊天不覆盖当前界面）；获取后清除补取标记，返回聊天直接可用。
- 2026-10-04 v11：新增 UC-5B9《上下文用量浮窗拆解卡》——右上角用量 hover 拆解卡（三色占比条 + 三行图例，三行之和=整包；快照补齐只补构成）。

- 2026-10-03 v10：补记前端性能批次——流式重测分 6,000 字符批让出主线程（MessageChannel，单任务约 4ms）、每个流式窗口最多两种布局签名缓存、执行框一次测量不再清样式重读；公共侧栏窄态条目 DOM 复用、改动审查轮定位二分（详见 docs/CHANGELOG-2026-10-03-前端性能优化.md）。

- 2026-10-02 v9：**执行过程框高度上限新增“不超出工作区可视区域”条件**——上限 = min(原 `min(72vh, 41.6rem)`, `#chat-container` 可视高度 − 8px)；原上限保持不变；随展开 / 滚动 / 窗口尺寸变化重算（`applyProcessBodyViewportClamp`）。实机：420px 高窗口下框高由 302px 收至 284px（=可视高度−8）不再高过可视区；720px 窗口恢复原上限 518px。

- 2026-09-28 v8：跟随运动改为**固定刚度软弹簧**（`followStiffness: 180`，临界阻尼、ω=√180≈13.42/s 常数）——替代 v7 的距离增强（26+0.5×lag）与 230ms 到期期限，对齐 DeepSeek 手机端"软"观感：19px 折行首帧 0.41px、483ms 收敛；单帧 20px 上限保留为大位移安全阀；明确稳态滞后 2v/ω（常规流式 <1.5 行）。
- 2026-09-28 v7：跟随运动同步为**临界阻尼弹簧**（速度连续、响应 = 26 + 0.5×落后距离、230ms 期限、单帧 ≤20px）——替代 v6 的限时滑动；修正收尾口径：小残余一帧收口、大残余以 ≤1200px/s 连续收敛（不跳变、无拖尾）；重申文本揭示层保留、仅与跟随解耦（跟随器不读取揭示速率）。
- 2026-09-28 v6：UC-5B1 跟随运动改为**统一限时滑动**——折行与整行高度变化共用同一规则（160ms 段时长、单帧 ≤20px、easeOutCubic）；移除速度地板、通道差异与揭示速率反馈；内容停顿后 ≤250ms 收尾，不再有缓动拖尾。
- 2026-09-25 v5：新增 UC-5B7《长用户消息折叠预览》——折叠改为"原文裁剪 + 渐隐"（去掉摘要副本），10 行预览 + 半胶囊切换控件（隐藏行数、i18n/ARIA/键盘），浅色遮罩适配。
- 2026-09-21 v4：新增 UC-5B8《工具行实时输出与增量渲染》——`run_shell` 输出经 `tool_command_delta` 节流增量刷入工具行（ephemeral、64 KiB 上限），工具调用增量按帧合并渲染。
- 2026-09-14 v3：修正性能实现归属（`ui-performance.js` 为诊断采样；懒渲染在 `message-rendering.js`/`session-scroll-history.js`）并更新版本线至 `d022831`。
- 2026-09-14 v2：补齐跨容器共享附件 fetch/blob、节点释放与失败重试语义；用户消息图片改为等高横排缩略图。
- 2026-09-13 v1：拆分首版（承接 UC-503/504/511）。
