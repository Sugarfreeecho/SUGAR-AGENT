# 输入、发送与插话 · 功能方案设计（UseCase 清单）

- 版本：2026-10-07 v7（覆盖至：当前工作区；输入附件卡片与未发送副本清理）
- 用途：逐条审查（四字段格式）。
- 适用实现：`modules/sse-handling.js`（发送/插话主流程 `sendMessage`/`acquireSendPipelineLock`）、`modules/input-actions.js`（输入键助手）、`modules/skill-picker.js`、后端 steer API、`webui.py` 消息路径。
- 上级：`00-WebUI对话界面整体设计.md`

---

## 1. 功能定位

从键盘到运行的一切入口动作：发送、停止、插话、技能选取、上传。

## 2. UseCase

### UC-5A1 发送消息
- **触发**：输入并发送（含含技能/附件的情况）。
- **预期现象**：消息立即上屏（乐观渲染）；发送管道锁保证连点不重复提交；失败时有明确错误与"恢复"入口。
- **规则与边界**：空消息/纯空白不发；发送中再点发送不产生第二条 run。
- **依据**：`sse-handling.js::sendMessage`、`acquireSendPipelineLock`（`sse-handling.js` L47–53）。

### UC-5A2 停止与插话
- **触发**：运行中点"停止"或发送追加指令。
- **预期现象**：停止让当前轮安全收尾；插话被受理并注入（与 UC-2D1 联动）；插话失败可恢复（steer 状态可查）。
- **依据**：`post_session_steer`、`recover_session_steer`、UC-2D 段。

### UC-5A3 技能选取
- **触发**：在输入区选取一个/多个技能后发送。
- **预期现象**：已选技能随消息注入；选择器里看不到的技能名不会造成报错（被忽略）；发送后选择器状态合理重置。
- **依据**：`skill-picker.js`、`_build_agent_message_with_selected_skills`。

### UC-5A4 附件与路径输入
- **触发**：上传文件 / 通过选择器插入路径。
- **预期现象**：普通文件以安全工作区路径出现；图片先由服务端准入为耐久附件引用，再显示缩略图。服务端在占用会话运行位前重新校验结构化附件身份、grant 和整条消息限额；超限或越权整条拒绝。
- **规则与边界**：前端回执不是授权事实，不能仅凭客户端路径或 MIME 决定图片有效。图片 URL 可在消息中按配置自动入库，也可先调用 `POST /api/attachments/ingest`；显式入库契约见横切识图方案。
- **依据**：上传链路（[工作区 UC-4D](../04-工作区/04-上传与命名方案设计-UseCase清单.md)）、`api_pick_path`、`agent_loop.py` 统一准入入口。

### UC-5A5 输入体验细节
- **触发**：常用编辑操作（多行、快捷键、粘贴图片）。
- **预期现象**：多行输入与发送键行为符合习惯；粘贴/拖拽图片自动上传，回执只保存附件引用；无丢字、重复字符或长期保存的浏览器 blob URL。
- **依据**：`input-actions.js`（Enter/组合键助手）+ `sse-handling.js`（发送/粘贴管道）。

### UC-5A6 待发送队列中的图片

- **触发**：运行中把含图片的消息加入 follow-up 队列，刷新页面、离线后恢复、重排或移除队列项。
- **预期现象**：localStorage 队列只保存耐久附件引用；队列每次变化按浏览器/会话 scope 串行同步服务端 pin，旧同步请求不能覆盖新状态。清空队列发送空引用集。
- **规则与边界**：离线时本地队列仍可恢复，恢复后重试 pin；尚未同步的附件仅受上传宽限租约保护。发送队列项时沿用原附件引用并再次接受服务端授权校验。
- **依据**：`sse-handling.js::syncFollowupAttachmentPins/persistFollowupQueue`、`POST /api/attachments/references`。

### UC-5A7 待发送队列的手动排序

- **触发**：运行中用握把拖拽（鼠标/触摸）或键盘在待发送（follow-up）队列内调整顺序。
- **预期现象**：拖拽立即出现落点提示、松手换位；行间隙、面板内边距与在途行（`data-reorderable=false`）的落点吸附到最近的待发送行；长列表拖到边缘持续自动滚动；握把可聚焦（40×26 命中区、含序号徽标，`aria-label`/`aria-keyshortcuts`），↑/↓ 在待发送槽位间移动且焦点跟随条目；拖拽期间推迟 SSE 触发的重绘（`dragend` 后补齐），拖拽不被重绘打断。
- **规则与边界**：仅待发送（pending）槽位可换位，在途行保持固定槽位且不可拖；浏览器接管原生 HTML5 拖拽时的 `pointercancel` 不得结束拖拽（仅触摸/笔指针路径结束）；插入提示同时至多一个；拖拽不改变队列持久化与附件 pin 语义（见 UC-5A6）。
- **依据**：`sse-handling.js::onFollowupPointerCancel / resolveFollowupDropTarget / runFollowupAutoScroll / moveFollowupQueueItemByOffset / renderFollowupQueue`、`styles/app.css` 握把与提示样式、`modules/i18n.js`；回归 `tests/js/followup_dispatch_runtime.cjs`（5 例）、`tests/test_feature_flags.py`。

### UC-5A8 追问与草稿的路径胶囊往返保真
- **触发**：把带本地文件路径的消息入队/发送后，经「撤回再发 / 刷新或切会话后从草稿再发 / 会话忙 409 回填 / 改写编辑器重发」任一链路再次发送。
- **预期现象**：再次发送的正文仍是完整真实路径（模型侧从不出现 `@基名`）；输入框显示形态不变（仍是 `@基名` 胶囊——回填后重跑标签重写、映射被重建）。
- **规则与边界**：标签→路径映射随草稿持久化（会话级隔离、随草稿清除）；回填用「实际提交原文」，`fromQueue` 沿用展开文本、`fromInlineRewrite` 重新展开；显示侧（`ui_message`/`event.content(ui)`）继续显示标签属有意设计。Agent 派生上下文（安全审查 / Goal Judge）仍取显示形式——记录为已知边界。
- **依据**：`sse-handling.js::returnFollowupToInput / sendMessage`、`session-scroll-history.js::persistDraftPathTokens / restoreDraftPathTokens / persistInputDraft / removeStoredInputDraft`；回归 `tests/js/input_path_token_roundtrip_runtime.cjs`、`tests/test_input_path_token_followup.py`。


- 输入层的"乐观渲染"会被服务端的真实事件校正（幂等）。
- ask_user 的回答入口在主界面卡片而非输入框（见 05）。

### UC-5A9 排队消息连续运行（同一 run 顺序续跑）
- **触发**：会话运行中提交多条普通排队消息（含刷新、排序、撤回、重复提交等操作后）。
- **预期现象**：当前回答完整保存后，同一 run 按队列顺序领取下一条继续处理；每条消息仍有独立用户轮次、最终回答与改动审查基线；队列清空后才结束本轮运行。
- **规则与边界**：只在回答完成边界领取，模型/工具执行中途不插入；排序同步服务端、撤回与领取互斥、重复提交/网络延迟/刷新不重建已处理操作；保留所选 Skill 与附件（服务端持久化，刷新可恢复）；手动停止、暂停与执行上限不领取后续；中途停止未开始消息会释放领取状态；赶上 run 已结束时仍可从普通聊天入口启动，但沿用原队列操作去重。
- **依据**：`agent_loop.py`（领取边界/生成阶段恢复）、`webui.py`（队列与 /chat）、`sse-handling.js`、`session-store`/`session-event-reducer`、projector；回归 `tests/test_queued_followup_continuation.py`、`tests/js/followup_dispatch_runtime.cjs`、`tests/js/session_store_runtime.cjs`。

### UC-5A10 输入附件卡片与未发送副本清理
- **触发**：在输入框上传图片或其他文件，移除附件、编辑正文后发送、发送失败或离开页面。
- **预期现象**：每个待发送文件只显示一个附件卡片，不再重复显示路径/文件标签；图片卡片展示缩略图，其他文件展示类型徽标，卡片均显示文件名、大小和移除入口。消息未被服务端接纳时，普通上传在工作区创建的副本会被清理。
- **规则与边界**：图片与普通文件使用同一张卡片布局；用户移除附件或正文中已不再引用该附件时清理普通文件副本。发送请求未被接纳、页面关闭时也清理待处理副本；发送被 409 回填或保留为待发送队列重试时保留附件副本。服务端确认接纳后保留文件。清理接口只允许删除受管理的 uploads/chat/YYYYMMDD 路径，已接纳文件不会被误删；耐久图片对象不走工作区副本清理接口。
- **依据**：vendor/myagent_path_picker.js 的 renderChatAttachmentTray、removeChatAttachment 与 cleanupChatUploads；sse-handling.js 的 sendMessage；webui.py 的 cleanup_unsent_chat_uploads/_managed_chat_upload_path；工作区 UC-4D8。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-5A1/5A2 | `webui.py` steer 段 + `sse-handling.js`（发送与管道锁）、`input-actions.js`（输入键） |
| UC-5A3 | `skill-picker.js`、`_build_*_with_selected_skills` |
| UC-5A4~5A5 | 上传 API、path picker、统一附件准入 |
| UC-5A6 | `sse-handling.js`、附件 references API |
| UC-5A7 | `sse-handling.js` 拖拽/键盘排序段、`styles/app.css`、`modules/i18n.js` |
| UC-5A10 | vendor/myagent_path_picker.js 附件卡片/清理、sse-handling.js、webui.py 上传清理 API |


## 5. 版本记录

- 2026-10-07 v7：新增 UC-5A10《输入附件卡片与未发送副本清理》——输入附件统一卡片呈现，移除重复文件标签；普通工作区上传副本在移除、未被发送接纳或页面离开时清理，409 回填/排队重试保留。
- 2026-10-05 v6：新增 UC-5A9《排队消息连续运行》——回答完成边界顺序领取、服务端持久化与去重、停止/暂停/上限不领取。
- 2026-10-04 v5：新增 UC-5A8《追问与草稿的路径胶囊往返保真》——撤回/草稿/忙回填/改写重发四条链路不再把 `@基名` 标签当正文发出；草稿随存标签→路径映射。

- 2026-10-02 v4：新增 UC-5A7《待发送队列的手动排序》——浏览器原生拖拽的 `pointercancel` 不再结束拖拽态；落点吸附（间隙/内边距/在途行）、边缘自动滚动、键盘 ↑/↓ 排序、拖拽期重绘推迟；握把命中区与 i18n 文案同步。

- 2026-09-14 v3：修正依据归属（发送主流程在 `sse-handling.js`；`input-actions.js` 仅为输入键助手）并更新版本线至 `d022831`。
- 2026-09-14 v2：补齐图片耐久引用、服务端准入校验和 follow-up 队列 pin。
- 2026-09-13 v1：拆分首版（承接 UC-501/502/510）。
