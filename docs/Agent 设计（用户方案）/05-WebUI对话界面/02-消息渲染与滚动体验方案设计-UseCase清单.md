# 消息渲染与滚动体验 · 功能方案设计（UseCase 清单）

- 版本：2026-09-14 v3（覆盖至：HEAD `d022831` + API 识图工作区改动）
- 用途：逐条审查（四字段格式）。
- 适用实现：`modules/message-rendering.js`、`modules/smooth-stream.js`、`modules/session-scroll-history.js`、`modules/toc-todo.js`、`modules/workspace-media.js`、`modules/ui-performance.js`。
- 上级：`00-WebUI对话界面整体设计.md`

---

## 1. 功能定位

"文字怎么出现"的体验层：平滑流式、Markdown/代码/工具轨迹渲染、滚动与目录。

## 2. UseCase

### UC-5B1 平滑流式输出
- **触发**：模型流式返回。
- **预期现象**：文字平滑滚动（非大段跳变）；长回答顺滑不卡顿；流结束后与最终文本一致（不失真）。
- **规则与边界**：平滑是**渲染节流**，不改动真实内容顺序；极端高速流下允许"快进"。
- **依据**：`smooth-stream.js`。

### UC-5B2 消息渲染（Markdown / 代码 / 工具轨迹）
- **触发**：任意消息上屏。
- **预期现象**：Markdown 正确（含表格/列表/代码块高亮）；工具调用显示为可折叠轨迹（命令/结果/状态）；mermaid 图按需加载渲染。
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

## 3. 边界

- 渲染层不修改事件数据——所见即事件流投影。
- 主题（明暗）规范属设置面板（06）。

## 4. 依据映射

见上表（均为 frontend/src/app/modules/ 下文件）。

## 5. 版本记录

- 2026-09-14 v3：修正性能实现归属（`ui-performance.js` 为诊断采样；懒渲染在 `message-rendering.js`/`session-scroll-history.js`）并更新版本线至 `d022831`。
- 2026-09-14 v2：补齐跨容器共享附件 fetch/blob、节点释放与失败重试语义；用户消息图片改为等高横排缩略图。
- 2026-09-13 v1：拆分首版（承接 UC-503/504/511）。
