# WebUI 对话界面 · 能力清单（代码证据版）

> 对象：MyAgent WebUI（前端 SPA + FastAPI Web 服务）
> 代码版本：`4083cbc`（2026-09-16 扫描；子代理前端 dsh 式重建）
> 图例：【图·7节点骨架】见 `webui.architecture.html`；【卡】图中卡片；【单】仅本清单

## 1. 前端架构与状态
| 能力 | 位置 | 状态 |
|---|---|---|
| SPA 启动与模块汇聚（raw-source 打包技巧，全局挂载 marked / mermaid） | `frontend/src/app/index.js`、`main.js` | 【卡】 |
| 状态仓库：session-store / message-store / context-store + selectors/renderers | `frontend/src/app/state/*`（11 个模块，含 session-actions；子代理 3） | 【图】 |
| 子代理目录对象层（寻址/目录快照/已读/指标；单飞刷新 + 成员帧修补） | `state/subagent-catalog-store.js`、`state/subagent-addressing.js`、`state/subagent-ui-decisions.js` | 【单】 |
| 前端插槽注册表（声明即授权/单链座位/优先级选举/disposer 级联） | `modules/ui-slot-registry.js` | 【单】 |
| 事件派发与 reducer：SSE 事件 → 状态归约 → 渲染 | `modules/event-dispatch.js`、`state/session-event-reducer.js` | 【图】 |
| 布局面板与 Toast 容器 | `modules/layout-panels.js` | 【单】 |
| 插件 UI 插槽（插件可注入界面位） | `app/plugin-ui-slots.js` | 【卡】 |
| i18n 与主题（浅色/深色切换） | `modules/i18n.js`、`settings.js` | 【卡】 |

## 2. 消息与流式渲染
| 能力 | 位置 | 状态 |
|---|---|---|
| 消息渲染（Markdown、工具执行轨迹、附件图片） | `modules/message-rendering.js`、`state/message-renderers.js` | 【图】 |
| 耐久图片预览：同附件跨容器共享 fetch/blob，末节点移除时取消并释放 | `modules/workspace-media.js::renderDurableAttachmentImages` | 【单】 |
| 平滑流式输出（逐帧节流） | `modules/smooth-stream.js` | 【卡】 |
| 滚动历史锚点与回看 | `modules/session-scroll-history.js` | 【卡】 |
| TOC 与 Todo 面板 | `modules/toc-todo.js` | 【卡】 |
| 性能采样与诊断（直方图/计时；长会话懒渲染在 `message-rendering.js`、`session-scroll-history.js`） | `modules/ui-performance.js` | 【单】 |

## 3. 输入与交互
| 能力 | 位置 | 状态 |
|---|---|---|
| 发送流程与失败恢复（发送主流程在 `sse-handling.js`：`sendMessage`/管道锁；`input-actions.js` 为输入键助手） | `modules/sse-handling.js`、后端 `post_session_steer` | 【图】 |
| Steer 中断（运行中插入指令，失败可恢复 `recover_session_steer`） | 后端 `webui.py` steer API | 【单】 |
| 技能选取（skill-picker，随消息注入已选技能） | `modules/skill-picker.js`、`_build_agent_message_with_selected_skills` | 【卡】 |
| 路径选择器与打开协议（`sugaragent://`） | `vendor/myagent_path_picker.js`、后端 `api_pick_path` | 【单】 |
| 普通文件上传与图片统一准入（限额、规范化、内容寻址、批次回滚） | 后端 `upload_chat_files`、`attachments/admission.py` | 【卡】 |
| follow-up 队列保存耐久引用，并向服务端同步 queue pin | `modules/sse-handling.js`、`POST /api/attachments/references` | 【单】 |

## 4. SSE 与实时管道
| 能力 | 位置 | 状态 |
|---|---|---|
| SSE 事件流（live/观察者/回放游标 after_index） | 后端 `runtime_v2_session_stream` | 【图】 |
| 断线续看：空闲 120s 探测、重连 ≤10 次（0.5s→15s 退避）、耗尽提示 | `modules/sse-handling.js` 顶部常量 | 【卡】 |
| 发送管道锁（防重复提交） | `modules/sse-handling.js` `acquireSendPipelineLock` | 【卡】 |
| 观察者重连开关 | 后端 `MYAGENT_ENABLE_STREAM_RECONNECT`、`streamReconnect` | 【单】 |
| 服务端自主运行自动接管（心跳 `active_session_ids`→≤5s 挂接观察流） | `webui._runtime_status_payload`、`modules/session-management.js` 心跳接管 | 【单】 |
| 扩展状态控制事件（observer 流 `ephemeral+control_event`→前端刷新扩展面板） | `webui._observer_extension_control_event`、`modules/sse-handling.js::consumeExtensionControlEvent` | 【单】 |

## 5. 面板能力
| 能力 | 位置 | 状态 |
|---|---|---|
| 子代理会话（标题栏谱系目录 + 主区寻址；四色状态点=进行中/完成未读/完成已读/错误；打开即已读，localStorage 持久化） | `modules/subagent-catalog-ui.js`、`state/subagent-catalog-store.js`、`state/subagent-addressing.js` | 【图】 |
| 子代理成员帧桥接（SSE `agent_id` → 目录增量；无专属事件流，后端零改动） | `modules/subagent-frames.js`、`modules/sse-handling.js` | 【单】 |
| 子代理编辑器三态（可写/锁定-保留 Stop/只读占位；slot chain 选举接管）与续接提示（结果未纳入父回答 → `/continue-subagents`） | `modules/subagent-composer-ui.js`、`state/subagent-ui-decisions.js` | 【单】 |
| 审批与 ask_user 交互卡片（含分析、取消、恢复） | `modules/human-interactions.js`、后端 interactions/approvals API | 【图】 |
| 权限与安全设置（会话级/全局权限、规则、预批准域名） | `modules/permissions.js`、后端 security API | 【图】 |
| 模型档案管理（增删改、排序、启用、发现、探测） | `modules/model-profiles.js`、后端 model-profile API | 【图】 |
| 工作区文件与媒体（目录浏览、图片元数据/预览、上传） | `modules/workspace-media.js`、后端 workspace API | 【卡】 |
| 通知与 UI 存在性（presence 上报驱动桌面提醒策略） | 后端 `ui-presence`、`_ui_presence_has_active` | 【卡】 |
| 右侧详情栏（dockkit 三层：引擎/渲染/嵌入；dsh 式第三列 + 开始/文件/内容/修改历史四类页；角落按钮与条尾控件图形同 dsh 源码） | `frontend/src/app/modules/dock/**`（engine 8 / renderer 5 / embedder 3）、`styles/dock.css`、`app/index.js` 登记 | 【单】 |
| 统一开文件策略（文本→详情栏，其余→系统应用；`MyAgentDock.openPathSmart` / `isTextPath`，会话文件链接与文件树共用） | `modules/dock/embedder/right-column.js`、`modules/session-scroll-history.js`（链接委托） | 【单】 |
| 修改历史双档（本轮/本次会话，默认本轮；边界随用户消息即时推进；扫描带超时/重试/看门狗；撤销/恢复走 Change Review 路由） | `modules/dock/embedder/right-column.js`、`plugins/change-review/host.py` | 【单】 |

## 6. 会话管理
| 能力 | 位置 | 状态 |
|---|---|---|
| 会话列表/归档/删除/恢复（recover_sessions） | `modules/session-management.js`、后端 sessions API | 【图】 |
| 会话状态快照缓存（增量失效） | 后端 `_build_sessions_state_snapshot_cached` | 【单】 |
| 中断与运行状态（缺省字段轻量版） | 后端 `interrupt_session`、`_session_run_state_fields_light` | 【单】 |

## 7. 后端服务面（webui.py，>60 路由分组）
| 能力 | 说明 | 状态 |
|---|---|---|
| 页面与静态资源（index.html、dist 资源、路径选择器 JS、setup i18n） | 由 Vite 构建产物驱动 | 【单】 |
| Runtime V2：state / events / runs / stream / subagents | 事件与快照读取、游标、SSE | 【图】 |
| 工作区：文件列表、目录浏览、图片元数据、媒体响应、打开文件 | 含路径越界防护 `_resolve_allowed_local_path` | 【单】 |
| 工作区：文本只读接口（`GET /api/workspace-file-text`，UTF-8 截断 + `truncated` 标记，供详情栏文件内容页） | `webui.py::workspace_file_text`；需重启服务生效 | 【单】 |
| 附件：授权读取、queue pin、grant、URL 入库、ZIP 导入/导出 | `webui.py`、`attachments/api.py` | 【单】 |
| 独立识图：创建/查询/SSE 续接/取消/清理/GC/指标 | `vision_api.py` 的 `/api/vision/*` 路由 | 【单】 |
| 运行恢复：interrupted ReAct 会话自动恢复、human interaction 恢复 | 后台 runner（`start_react_recovery_runner`） | 【单】 |
| 客户端计时上报（client_timing） | 前端性能数据回传 | 【单】 |

## 8. 边界说明
- 后端另含 Runtime V2 同步/迁移（legacy→V2）与孤儿运行清理逻辑，归属"会话存储 Runtime V2"模块清单详述。
- 图片准入、三协议投影、独立识图 API 和生命周期的横切契约见 [识图与多模态投影](../09-横切能力/02-识图与多模态投影方案设计-UseCase清单.md)。
- 主题/样式细节（`styles/*.css`）、构建工具链（Vite）不在本次清单范围。

## 9. 版本记录

- 2026-09-16（v5）：子代理前端 dsh 式重建——前端状态仓库计数修正为 11；「子代理 Dock」条目替换为「子代理会话」三行（目录树/成员帧桥接/编辑器三态与续接提示，新模块 5 个：catalog-ui/composer-ui/frames/slot-registry/address+store+decisions），UI 模块总数 22；旧 10 个 subagent-* 模块已删除，后端 API 组未变。
- 2026-09-14（v4）：详情栏三轮反馈收编——开始引导页、统一开文件策略（`openPathSmart`）、修改历史双档与扫描健壮性；renderer 计 5 件（新增 `icons.js`）；说明见 05/08 专项设计。
- 2026-09-14（v3）：补录右侧详情栏（`modules/dock/**` 三层与 `styles/dock.css`）及工作区文本只读接口；说明见 05/08 专项设计。主区会话分屏随后按用户要求移除。
- 2026-09-14（v2）：补录服务端自主运行自动接管与扩展状态控制事件；修正状态模块计数（17）、`ui-performance.js`/`input-actions.js` 职责描述；版本线更新至 `d022831`。
