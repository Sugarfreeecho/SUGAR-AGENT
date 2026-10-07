# 消息渲染与滚动体验 · 功能方案设计（UseCase 清单）

- 版本：2026-10-07 v19（覆盖至：当前工作区；图片附件卡片与原有过程行距）
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
- **规则与边界**：执行过程框高度上限 = min(原 CSS `min(72vh, 41.6rem)`, 工作区可视高度 − 8px)——框高不得超出工作区可视区域，原上限保持不变；展开 / 滚动 / 窗口尺寸变化时重算（`message-rendering.js::applyProcessBodyViewportClamp` / `scheduleProcessViewportClampSweep`）。度量取“可视高度”而非“底边 − 框顶”（跟随钉底时后者会自我收缩）。执行过程框、轨迹条目和长用户消息的展开/收起共用动效令牌，详见 15·UC-5P1~5P3。
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
- **预期现象**：用户气泡与执行过程中的图片以紧凑附件卡片显示缩略图、名称和大小，卡片可点开放大；最终回答卡片中的图片也可点开，但沿用原有正文排版。文件链接按打开协议工作；加载失败显示稳定占位。同一附件 ID 同时出现在历史消息、工具轨迹和待发送队列时，共享一次读取和一个 blob URL。
- **规则与边界**：缩略图等比例完整显示并保持卡片尺寸稳定。共享项维护节点集合；最后一个节点移除时取消未完成读取并撤销 blob URL。失败项不保留无效共享状态，后续重新出现可以重试。附件读取携带同源凭据，由服务端鉴权。图片卡片只调整图片自身布局；执行过程图片条容器不额外保留下边距，图片行与下一条沿用原有过程条目间距。
- **依据**：workspace-media.js 的 renderDurableAttachmentImages/durableImagePreviews、GET /api/attachments/{id}。

### UC-5B6 长会话性能
- **触发**：数百条消息的会话。
- **预期现象**：滚动/输入不卡；历史段懒渲染；内存不持续膨胀。
- **依据**：`message-rendering.js`、`session-scroll-history.js`（懒渲染/裁剪）；`ui-performance.js` 仅做采样与直方图诊断（非渲染层优化）。

### UC-5B7 长用户消息折叠预览（10 行）
- **触发**：用户消息较长（超过 10 行）进入折叠态；点击 / 键盘操作折叠控件。
- **预期现象**：只显示前 10 行、底部渐隐；**没有摘要副本**（直接裁剪原文，不重复内容）；下缘半胶囊切换控件（chevron + 文案）随状态变化——"展开全部 · 还有 N 行" ⇄ "收起"；展开/收起带 max-height 过渡。
- **规则与边界**：控件可点击也可 Enter/Space；带 `aria-expanded` / `aria-label` / `title`，语言切换时整体重刷；隐藏行数按实测行高计算（`USER_MESSAGE_COLLAPSE_LINES = 10`）；浅色主题使用专用渐隐遮罩。
- **依据**：`shared-state-and-dialogs.js::buildUserMessageCollapseToggle / renderUserMessageContent`（`user-msg-chevron`、`user-msg-expanded`、`--user-msg-full-h`）、`app.css`、`i18n.js`。

> 执行过程与消息内容的统一折叠时长、缓动、减少动态效果及浏览器兼容边界见 [15《展开/收起统一过渡动效》](15-展开收起统一过渡动效方案设计-UseCase清单.md)。

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

### UC-5B10 上下文压缩思考实时行
- **触发**：本地上下文压缩摘要模型以 `context_summary_reasoning_delta` 流式返回 reasoning，或运行中活动流续接后收到当前思考的聚合快照。
- **预期现象**：在执行过程区域中追加独立“压缩思考”行，实时显示模型已输出内容；压缩摘要正文继续进入自己的正文行。思考行开始时展开，摘要正文开始后自动收起，用户可再次点开查看。
- **规则与边界**：思考内容以纯文本安全插入，不解析为 Markdown/HTML；临时运行态不进入用户/助手消息历史。候选重试形成新行；收到 `context_summary_reasoning_end`、失败、取消或中断时只收束对应活动行。活动流续接收到累计快照时替换本地草稿而非追加，避免重复；主对话 reasoning 与压缩 reasoning 相互独立。
- **依据**：`message-rendering.js`、`event-dispatch.js`、`sse-handling.js`、`session-event-reducer.js`、`i18n.js`；后端投影见 `session_event_bus.py`。事件续接见 05/03·UC-5C9；压缩生产端见 09/01·UC-9A11。

### UC-5B11 标题栏用量表基准与标题区留白/⋯ 光心微调
- **触发**：打开会话页，观察右上角上下文用量表、会话标题区与标题行末尾的 ⋯ 菜单按钮。
- **预期现象**：用量表按参考基线（zip 源机）渲染，16px 档实测——条内文字 10.08px / 最小宽 112px / 行间距 6.4px / 百分比 9.28px / 进度条上边距 3.2px；会话标题上方留白 6.19px，与「标题→副标题」间距 5.39px 接近；⋯ 点位中心与标题文字视觉中心对齐（相对大写/CJK 光心与全墨迹中心偏差均 ≤ 0.5px）；子代理寻址视图的返回胶囊（`.breadcrumb-back-chip`）与「· N 个子代理」目录触发器（`.subagent-catalog-trigger`）同款处理——两胶囊中心与 ⋯ 一致（16px 档实测 17.09px）。
- **规则与边界**：移除用量表的 `--ctx-unit: 0.875rem` 缩放，改回基准值（`0.63rem / 7rem / 0.4rem / 0.58rem / 0.2rem`）；hover 拆解卡（UC-5B9）样式不动。`.titlebar` 顶部内边距 `0.4 → 0.2rem`（其余三边不变），用于平衡上下留白；⋯ 光心对齐用 `transform: translateY(1px)`，只作用于顶栏实例（`.breadcrumb-session-actions .session-more-btn`），侧栏会话行按钮与弹出菜单定位不受影响；返回胶囊与目录触发器同样 `transform: translateY(1px)`（仅顶栏实例），标题行内「文字 / ⋯ / 胶囊」光心一致。
- **依据**：`frontend/src/styles/app.css`；实测与截图见 `../../../workspace/桌面版打包_20261006/`（`顶栏对比分析.md` §八~§十、`titlebar_measure.json`、`ctx_meter_after.json`、`dots_vs_text_metrics.json`、`dots_alignment_after_fix.json`）。

### UC-5B12 全区域图片预览浮窗与居中缩放
- **触发**：点击输入框附件、用户气泡、执行过程条目或最终回答卡片中的图片；在预览窗口滚动鼠标滚轮。
- **预期现象**：图片统一在设置窗口同类的居中浮窗内打开，背景为半透明模糊遮罩；标题和关闭按钮在标题栏内垂直居中，标题字号使用设置字号令牌。打开时图片按窗口可视区域等比例完整适配；滚轮可在 0.2× 至 8× 间缩放，图片始终围绕视口中心保持居中。所有图片入口共用预览浮窗，最终回答卡片原有图片排版不变。
- **规则与边界**：图片解码完成后再显示，窗口尺寸变化时重算适配尺寸。滚轮事件按动画帧合并；缩放只更新已适配图片的合成变换，不在每个滚轮事件中重复读取布局或改写尺寸，避免打开和连续缩放卡顿。标题字号跟随设置字号令牌 --ui-text-lg。遮罩点击或关闭按钮可关闭浮窗。
- **依据**：workspace-media.js 的 ensureDurableAttachmentPreviewDialog、scheduleDurableAttachmentPreviewFit 与 applyDurableAttachmentPreviewScale；styles/app.css 的 attachment-image-viewer 样式；tests/js/image_preview_runtime.cjs、tests/test_workspace_media_runtime.py。

## 3. 边界

- 渲染层不修改事件数据——所见即事件流投影。
- 主题（明暗）规范属设置面板（06）。

## 4. 依据映射

见上表（均为 frontend/src/app/modules/ 下文件）。


## 5. 版本记录

- 2026-10-07 v19：修正 UC-5B5 的执行过程图片卡片间距——图片容器不再额外添加下边距，图片条目与下一条的距离恢复到原有过程行间距；非图片条目规则保持不变。
- 2026-10-07 v18：UC-5B11 补记——子代理返回胶囊（`.breadcrumb-back-chip`）与目录触发器（`.subagent-catalog-trigger`）同款 `translateY(1px)` 光心对齐；两胶囊中心 16.09→17.09px，与 ⋯ 及标题文字光心一致。前后实测与 3x 对比见 `workspace/桌面版打包_20261006/`（`subagent_chip_metrics_before.json`、`subagent_chip_metrics_after3.json`、`subagent_chip_before_3x.png`、`subagent_chip_after_3x.png`）。
- 2026-10-07 v17：新增 UC-5B12《全区域图片预览浮窗与居中缩放》并扩展 UC-5B5——输入框、用户气泡、执行过程和最终回答图片复用居中预览；标题/关闭控件垂直居中且标题字号跟随设置；滚轮缩放按帧合并并保持视口居中，图片布局变更不影响非图片执行条目及最终回答的原排版。
- 2026-10-07 v16：补齐 UC-5B10 的事件契约名称（`context_summary_reasoning_delta/end`）与 05/03 活动快照续接边界，保持与 09/01·UC-9A11 一致。
- 2026-10-07 v15：新增 UC-5B11《标题栏用量表基准与标题区留白/⋯ 光心微调》——用量表移除 `--ctx-unit` 缩放、恢复参考基线值（0.63rem / 7rem / 0.4rem / 0.58rem / 0.2rem，浮窗不动）；`.titlebar` 顶部内边距 0.4→0.2rem（标题上方留白 9.4→6.2px，与中部 5.4px 接近）；⋯ 按钮 `translateY(1px)` 光心对齐（偏差 ≤ 0.5px，仅顶栏实例）。实机数据与 3x 放大截图见 `workspace/桌面版打包_20261006/`。
- 2026-10-07 v14：新增 UC-5B10——本地摘要 reasoning 独立实时行，安全纯文本展示、正文到达后默认收起、重试分行、终态清理；活动流重连用累计快照替换草稿以免重复。
- 2026-10-07 v13：同步 15《展开/收起统一过渡动效》——执行过程主体、轨迹行长内容及长用户消息使用共享折叠时长与缓动；减少动态效果时缩短过渡。
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
