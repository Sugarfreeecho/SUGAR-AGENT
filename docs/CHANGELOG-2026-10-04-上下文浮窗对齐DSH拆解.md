# 2026-10-04 右上角上下文用量浮窗对齐 DSH 拆解

涉及改动：本轮工作区改动（未提交），仅限上下文用量浮窗与它的三段构成数据；工作区里其它未提交改动（execution services、steering、设置中心等）不在本次范围。

## 一、浮窗内容与样式（学 DSH `ContextMeter`）

参考 `Deepseek Harness/deepseek-harness`：`packages/client/ui-conversation/src/client/skeleton/ContextMeter.{tsx,module.css}` 与 `packages/llm/token-meter/src/breakdown-projection.ts`。右上角触发器外观保持不变（仍是「24.5k / 128k + 细条 + 百分比」），只有 hover 浮窗换成 DSH 式拆解卡：

- 标题行：「上下文已用 8.1%」+ 右对齐「~41.2k / 512k」；
- 一条 4px 占比条，按构成分三色（系统提示词=中性蓝灰、工具定义=紫 `#a78bfa`/浅色 `#7c3aed`、对话消息=主题蓝），1px 间隙、每段最小 2px、占比条总长严格等于精确百分比（与 DSH 一致：条长用精确值，分段只按启发式构成分配宽度，占比为 0 的段直接丢弃）；
- 三行图例：8px 色块 + 名称 + `~token`；
- 12px 字号、264px 宽（窄窗收敛到 `100vw - 1.5rem`）、`--floating-surface` 浮层、8px 圆角，随三套主题（默认紫黑 / theme-dark 中性深色 / theme-light）自动取色。
- 与 DSH 的差异：卡片贴在右上角触发器右缘向下展开，落点本就在视口内，因此不引入 DSH 的测量式锚定；另加一行灰色的「分母为压缩摘要阈值；构成按本地估算」说明（DSH 无此行），因为本地分母是压缩阈值而非原始上下文窗口。

## 二、功能与数据来源

- 交互：指针停在该用量上 180ms 后展开卡片；指针离开整块（卡片是触发器子节点，移入卡片不会收起）即收起；Escape 收起。有构成数据时该元素不再挂纯文字提示（避免两种浮窗叠加）；没有构成数据时保留原来的纯文字提示、卡片不出现。
- 数据：`build_context_breakdown`（`app/agent_tokenizer.py`）给出三条泳道——系统提示词本地计价、工具定义用既有 schema 计价、对话消息取整包估值的余量，因此三行之和恒等于右上角显示的整包数字（DSH 同语义，故行值带 `~`）。系统段按内容缓存，热路径上同一段提示词只付一次分词；不额外分词对话历史。
- 接入点：`compute_context_tokens_for_session` 返回值、主循环 pre-request 的 `context_tokens` 事件、压缩后检查点、`/sessions/{id}/context_tokens`；后者的快照若来自旧检查点（只有总量、没有构成），端点会用 `backfill_context_breakdown_for_session` 只补构成、不改总量与口径，失败则原样返回。
- 前端透传：SSE 事件 → `session-event-reducer` → `context-store`（新一轮若不带构成则保留已存构成，避免快照竞态抹掉泳道）→ `session-scroll-history` 渲染；`/history_snapshot` 同样透传。
- 中英文案：`上下文已用 / 系统提示词 / 工具定义 / 对话消息 / 分母说明`。

## 验证

- `npm run build` 后 `npm run verify:dist`：`Frontend dist is in sync.`（dist 随源码重建）。
- 新增 `tests/test_context_breakdown.py`（11 passed，含三段之和等于总量、总量偏小时的收敛、只计开头连续 system 段、端点补齐与既有构成直出、补齐失败不抛、双外壳标记、前端透传契约、node 卡片用例）；新增 `tests/js/context_breakdown_card_runtime.cjs`（分段宽度与总量一致、0 宽度段丢弃、无构成时的单色兜底、超阈值收敛到满条、脏数据拒绝）。
- 修正两处旧断言：`tests/test_agent_loop_runtime_v2.py`（结果字典新增 `breakdown`）、`tests/test_webui_messages.py`（总量口径测试不再触碰真实补齐路径）。
- 定向 pytest：`test_context_breakdown.py` 11 passed；`test_webui_messages.py` 56 passed；runtime_v2 与前端运行时套件合计 276 passed；前端契约类套件 130 passed。
- 全量 `pytest -q`：2085 passed / 5 skipped / 4 failed。4 项失败与本次改动无关且可归因：`test_feature_flags.py` 两项（`session_manager.append_ui_event(` 被工作区未提交改动移入 Runtime V2 提交路径、`max_react_iter` 计数由 4 变 7；已用 `git show HEAD:app/agent_loop.py` 对照确认 HEAD 满足断言、失败区域不含本次改动）；`test_settings_modal_sections.py` 与 `test_settings_center_browser.py` 各一项（设置中心 `settings.js` 与静态设置页，`function applyFontLevel(` 在 HEAD 的工作区版本里同样缺失，本次未触碰这些文件）。
- 真实浏览器（Playwright，stub 掉 `/sessions/**`，不动用户在线会话）：悬停展开、移出收起、Escape 收起、theme-dark / theme-light 两套取色、无构成时的兜底均已实测；截图见工作区 `ctx拆解浮窗_dsh对齐/card-theme-{dark,light}-hover.png`。实测数字：`41.2k / 512k → 8.1%`，三段宽度 `0.814% + 1.782% + 5.504% = 8.1%`，行值 `~4.1k / ~9.1k / ~28k`；`486.4k / 512k → 95%` 时 `2.422% + 1.777% + 90.801% = 95%`。

## 文件

- 后端：`app/agent_tokenizer.py`（`build_context_breakdown`）、`app/agent_loop.py`（`_leading_system_messages`、`compute_context_breakdown_for_llm_history`、`backfill_context_breakdown_for_session`，以及端点返回值 / pre-request 事件 / 压缩后检查点三处载荷）、`app/webui.py`（`/sessions/{id}/context_tokens` 快照补齐）；
- 前端：`frontend/src/app/modules/session-scroll-history.js`、`frontend/src/app/state/context-store.js`、`frontend/src/app/state/session-event-reducer.js`、`frontend/src/app/modules/session-management.js`、`frontend/src/app/modules/i18n.js`、`frontend/src/styles/app.css`、`frontend/index.html`、`frontend/src/shell-body.html`、`app/templates/dist/**`（重建产物）；
- 测试：`tests/test_context_breakdown.py`、`tests/js/context_breakdown_card_runtime.cjs`、`tests/test_agent_loop_runtime_v2.py`、`tests/test_webui_messages.py`。
