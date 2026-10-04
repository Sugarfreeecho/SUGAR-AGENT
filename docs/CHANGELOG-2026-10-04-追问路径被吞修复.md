# 2026-10-04 追问路径被吞修复（@基名 胶囊映射丢失）

## 现象

追问里带文件路径时，"撤回再发 / 刷新后再发 / 会话忙回填后再发"这几种情况下，发出去的正文里路径变成 `@文件名`：Agent 上下文里也只剩标签，拿不到真实路径。

## 根因

输入框每次 `input` 都把绝对路径改写成 `@基名` 胶囊标签（`rewriteInputWorkspacePaths`），**真实路径只存在内存映射 `inputPathTokenMap` 里，不落盘**；而入队/发送时会 `clearInputPathTokens()` 把映射清空。于是任何"把 display 文本（标签形式）当作正文"的链路，都会在下一次发送时真的发出 `@文件名`：

| # | 链路 | 位置 | 说明 |
| --- | --- | --- | --- |
| ① | 撤回 / steer 失败 / watcher 取消回填 | `returnFollowupToInput` 用 `item.display` | 三条调用方全部走这里；映射已清空 → 标签成死文本 |
| ② | 草稿落盘 + 恢复 | `persistInputDraft` 只存标签文本 | 刷新（映射从零开始）、切会话、新会话草稿移交后同样成死文本 |
| ③ | `/chat` 返回 409（会话忙）回填 | `messageInput.value = visibleMessage` | `visibleMessage` 是标签形式，且此处映射已被清空 |
| ④ | 改写重发 | `fromInlineRewrite` 分支跳过展开 | 编辑器沿用的标签会被原样发出 |

需要区分的是：**模型主链路一直是正确的**——`/steer` 提交 `message: item.text`、队列 `/chat` 提交 `message: item.text`、`ui_message`/`event.content`(ui) 才走 display。所以"追问在对话/队列里显示成 @基名"是既有显示设计（本次刻意保持），真正的缺陷是上面 4 条把标签当正文再发的链路。

## 变更

- `frontend/src/app/modules/sse-handling.js`
  - `returnFollowupToInput`：回填正文改为 `item.text || item.display`（发送原文，含展开后的真实路径）；回填后仍走 `rewriteInputWorkspacePaths()`，因此**显示形态不变**（仍是 `@基名` 胶囊），但映射被重建，再发一次不会丢路径。
  - `sendMessage`：`rawMessage` 只在 `fromQueue` 时沿用（入队时已展开），`fromInlineRewrite` 恢复做标签展开。
  - 409 忙回填：改为写回 `rawMessage` + `rewriteInputWorkspacePaths()`，并把重写后的输入框文本落进草稿（连同映射）。
- `frontend/src/app/modules/session-scroll-history.js`
  - 新增 `inputDraftPathTokenStorageKey / collectDraftPathTokens / persistDraftPathTokens / restoreDraftPathTokens`：草稿落盘时同步持久化"文本里确实出现的"标签→真实路径映射（会话级隔离，键由草稿键派生），恢复草稿前先重建映射，再做胶囊重写。
  - `persistInputDraft`：写/清草稿时同步写/清映射；`removeStoredInputDraft`：一并清映射键，避免陈旧映射串到后续输入。
- `app/templates/dist/`：`npm run build` 重新生成（构建后为 `main-BrGUZQZY.js` / `main-BgbtHP-e.css`；若并行还有其它前端改动再构建，哈希文件名会随之变化，以 `npm run verify:dist` 结论为准）。
  - 说明：工作区里原有未提交的前端改动（`frontend/index.html`、`frontend/src/app/modules/model-profiles.js`、`frontend/src/shell-body.html`、`frontend/src/styles/app.css`）按 `verify:dist` 的"dist 必须等于源码构建产物"约定一并进入了这次构建产物，未做任何改动或回退。

## 测试与验证

- 新增 `tests/js/input_path_token_roundtrip_runtime.cjs`：从真实源码抽出相关函数在 `vm` 沙箱里跑往返（仓库既有 `tests/js/*_runtime.cjs` 风格），断言
  - 草稿落盘 → 清空内存映射（模拟刷新）→ 恢复后提交文本 = `帮我看看 "D:\work\报告\report.md" 里的结论`；
  - 撤回回填（映射已清空）→ 重新发送同样是完整真实路径，且映射被重建；
  - **负向对照**两组：删掉映射/沿用 display 回填时确实只剩 `@report.md`（复现修复前行为，证明断言有效）；
  - 模型侧与显示侧分路：`sendSteerMessage(sid, item.text, …)`、队列 `/chat` 三处 `message: item.text`、`ui_message` 仍走 display、`fromInlineRewrite` 必须展开。
- 新增 `tests/test_input_path_token_followup.py`（pytest 源码接线断言，进 CI）：7 项，覆盖上述 4 条链路的接线不变式（背景会话回填不得碰当前输入框等既有契约由原测试保持）。
- 定向回归：`tests/test_input_path_token_followup.py tests/test_session_draft_badge.py tests/test_feature_flags.py tests/test_input_actions_runtime.py` → **71 passed**。
- 全量 `pytest -q`：**1994 passed, 4 skipped, 3 failed**；3 项失败为既有环境问题，与本次改动无关，已在把两个被改文件回退到 HEAD 的基线上原样复现：
  - `tests/test_llm_stream_window_geometry.py::test_streaming_omission_note_follows_language_without_translating_output[characters|lines]`（注入 i18n 串落成乱码，英文文案未生效）；
  - `tests/test_model_reasoning_menu_browser.py::test_draft_effort_uses_two_level_menu_and_updates_caption`（同一编码问题导致的乱码断言，单独跑基线时通过，属不稳定项）。
- `node` 遍历 `tests/js/*.cjs|*.mjs`：**26/26 通过**（含新增用例）。
- `npm run verify:dist`：dist 与源码同步。

## 文件

- `frontend/src/app/modules/sse-handling.js`、`frontend/src/app/modules/session-scroll-history.js`
- `tests/js/input_path_token_roundtrip_runtime.cjs`、`tests/test_input_path_token_followup.py`
- `app/templates/dist/`（构建产物）

## 未修（本次范围外，需产品决策）

Agent 侧派生上下文仍优先取 `ui_content`（= 标签形式）：`app/agent_loop.py` 的 `_tool_review_conversation_from_events`（工具/安全审查对话）、`capture_dialogue(kind="followup")` → `plugins/agent-goal/runtime.py` 的 Goal Judge 提示词。即"目标判定 / 安全审查"看到的追问仍是 `@文件名`。按用户选择（只修真丢路径的分支、显示保持 @ 胶囊），本次未改动这些位置。
