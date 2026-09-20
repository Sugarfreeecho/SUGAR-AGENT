# API 识图与多模态投影 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v3（覆盖至：当前工作区）
- 用途：按「触发 → 预期现象 → 规则与边界 → 依据」逐条审查图片从接入、存储、模型请求到结果和生命周期的完整链路。
- 适用实现：`app/attachments/**`、`app/vision_api.py`、`app/agent_openai.py`、`app/llm/transport.py`、`app/agent_harness.py`、`app/agent_loop.py`、`app/agent_mcp.py`、`app/agent_subagent.py`、`app/runtime_v2/**`、`app/webui.py`、`frontend/src/app/modules/{workspace-media,sse-handling,event-dispatch,message-rendering}.js`。
- 上级：`00-横切能力整体设计.md`
- 详细技术契约：[API识图功能设计方案](../../API识图功能设计方案.md)。本篇按用户可观察场景组织，详细文档按数据模型、协议和模块组织；两者描述同一实现。

---

## 1. 功能定位

API 识图把上传、粘贴、拖拽、本地路径、远程图片链接和工具截图统一变成耐久图片引用，再依据实际模型能力与预算生成一次性请求图片。它同时提供不创建 Agent 对话的独立识图 API，并负责身份授权、幂等、流式结果、取消、配额、回收与备份。

核心承诺：

1. 会话、事件、队列和常规日志保存 `sha256` 引用，不长期保存图片 base64。
2. 用户上传的图片内容一经准入便冻结；原文件或远程 URL 后续变化不会修改历史事实。
3. 只有实际送入具备 image 能力模型的图片才标记为 `sent`；纯文字回答不能冒充识图成功。
4. 图片是否可发送、如何缩放和超预算省略，以实际候选 model profile 为准。
5. 图片失败可解释、批次失败可回滚、请求可查询，取消请求与实际结束状态分开表达。

## 2. 用户入口与统一准入

### UC-9B1 上传、粘贴与拖拽图片

- **触发**：用户选择图片文件、把图片拖进输入区，或直接粘贴截图。
- **预期现象**：界面显示图片附件；服务端完成格式、大小、像素与完整解码校验，返回包含 `attachmentId/mediaType/bytes/width/height` 的引用；消息和队列中没有 base64 或临时 blob 地址。
- **规则与边界**：严格支持 PNG/JPEG/WebP/GIF；本地兼容 BMP 在严格准入前转成 PNG。单图默认 20 MiB、单消息最多 20 张、源图片合计最多 200 MiB、单图最多 64,000,000 像素且最大边 8192。失败时删除本次上传暂存文件，不留下半个对象。
- **依据**：`webui.upload_chat_files`、`attachments/local.py::save_images_sync`、`attachments/normalization.py`、`frontend/src/vendor/myagent_path_picker.js`。

### UC-9B2 用户文本中的本地图片路径

- **触发**：本机用户在消息中写入带引号或可识别的 `.png/.jpg/.jpeg/.gif/.webp/.bmp` 路径。
- **预期现象**：入口在发送前把可读图片归一化入库，Core 消息保存图片引用；原文件随后修改或删除不影响已提交图片。
- **规则与边界**：文本路径扫描默认开启，可用 `MULTIMODAL_TEXT_PATH_SCAN=off` 关闭；关闭后不影响显式上传和已有引用。本能力按 Agent 进程的文件权限读取，不额外构成文件系统沙箱。
- **依据**：`attachments/admission.py::admit_content`、`attachments/content.py::IMAGE_PATH_RE`、`agent_loop.py` 用户入口、`agent_openai.py` 兼容序列化边界。

### UC-9B3 整条消息的原子准入

- **触发**：一条消息或嵌套工具结果同时包含多张原始图片、data URL、旧格式图片块和已有附件引用。
- **预期现象**：系统先遍历整棵内容树，汇总数量与字节，再一次性归一化、提交并按原位置回填；任一图片失败时 strict 调用整体失败，兼容调用保留普通文字并把本批图片统一替换为错误占位。
- **规则与边界**：写入前完成整批图片校验；写入异常回滚本批新建文件，既有内容寻址对象不动。文件系统原子替换与回滚不承诺进程被强杀时具备跨文件数据库事务语义，遗留未引用对象由宽限 GC 处理。
- **依据**：`attachments/admission.py::AdmissionContext/admit_content`、`attachments/local.py::atomic_write/save_images_sync`、`tests/test_dsh_attachments.py`、`tests/test_vision_api.py`。

### UC-9B4 纯消息对象与旧历史迁移

- **触发**：构造 `UserMessage`、`ToolMessage`、`RuntimeEvent`，或读取包含旧 data URL/原始图片块的会话事件。
- **预期现象**：单纯构造值对象不读取文件、不下载网络图片、不写附件库；旧图片只在明确入口或事件仓库读写边界迁移成引用，再执行脱敏。
- **规则与边界**：迁移采用懒迁移，不破坏性批量改写全部旧 JSONL。`RuntimeEvent.to_dict` 只做内存脱敏，唯一历史图片数据不能在准入前被直接丢弃。
- **依据**：`agent_messages.py`、`runtime_v2/event_schema.py`、`runtime_v2/attachment_migration.py`、`runtime_v2/event_log.py`。

## 3. 图片规范化、身份和存储

### UC-9B5 图片归一化与内容寻址

- **触发**：新图片通过任一准入入口。
- **预期现象**：应用 EXIF 方向，转换为 8 位 sRGB RGB/RGBA，移除 EXIF/ICC 等元数据，按面积和边长等比缩放；有透明通道保存 WebP，否则保存 JPEG；对最终规范字节计算 `sha256:<64 位小写摘要>`。
- **规则与边界**：编码按 90/80/70/60/50/40 质量阶梯选择第一个满足软大小目标的结果，全部超限时保留实际最小版本，再由请求总预算决定是否发送。归一化副本是识图输入，不是原图档案；动画只取首帧。
- **依据**：`attachments/normalization.py`、`attachments/encoding.py`、`attachments/local.py::digest`。

### UC-9B6 内容去重与完整性复验

- **触发**：相同图片重复上传，或通过附件 ID 再次读取图片。
- **预期现象**：相同规范字节只保存一份；读取时校验引用字段、字节数、SHA-256、格式、尺寸、色彩模式和单帧要求，损坏对象不会发给模型。
- **规则与边界**：存储去重不等于请求次数、图片数量或模型计费去重；同一图片在消息中出现两次，仍按两次计算请求预算。最多 1024 项的内存验证缓存复用解码结论，但每次磁盘读取仍检查实际字节摘要。
- **依据**：`attachments/local.py::ref_by_id/read_image_sync`、`attachments/validation.py`。

### UC-9B7 图片请求版本与缓存

- **触发**：模型候选准备发送附件图片。
- **预期现象**：按候选 profile 的 `maxPixels/maxBytes` 生成请求版本；同附件、同策略复用缓存；缓存缺失、旧版或损坏时从规范对象重建。
- **规则与边界**：缓存键包含变换版本、Pillow 版本、附件 ID、请求策略和质量阶梯。缓存命中发生在缩放前；请求版本是可重建缓存，不是新的会话附件身份。
- **依据**：`attachments/request_image.py`、`attachments/__init__.py::request_policy`。

### UC-9B8 并发与磁盘配额

- **触发**：多个线程或进程并发准备同一请求图片，或对象库/缓存接近容量上限。
- **预期现象**：同一版本只生成一次，不同版本可并行；对象提交、授权 pin 和 GC 通过 catalog 锁协调。对象库超限拒绝新提交；请求缓存超限按旧到新淘汰可重建版本，不删除锁文件或源对象。
- **规则与边界**：对象库默认 10 GiB，缓存默认 512 MiB。锁等待默认 30 秒，超时给出 `ATTACHMENT_BUSY`。规范对象不能像缓存一样直接淘汰，必须经过可达性 GC。
- **依据**：`attachments/locking.py`、`attachments/local.py::occupied_bytes`、`attachments/request_image.py::_trim_cache`。

### UC-9B26 附件序列化热路径缓存

- **触发**：长历史中的每条消息通过 `durable_content()` 解析附件存储与远程图片策略。
- **预期现象**：附件根目录只读取单一 `WORK_DIR` 并记忆化已解析路径，远程图片策略复用缓存，避免对每条历史消息重复读取多组环境变量和执行 Windows `Path.resolve()`。
- **规则与边界**：显式设置或变化的 `WORK_DIR` 仍必须被尊重；配置更新通过 `invalidate_attachment_env_cache()` 清除缓存。缓存只消除环境/路径解析开销，不跳过附件身份、权限或完整性校验。
- **依据**：`attachments.__init__.get_attachment_store / invalidate_attachment_env_cache`、`RemoteImagePolicy` 缓存调用点。

## 4. 远程图片链接

### UC-9B9 自动识别图片链接

- **触发**：消息包含带常见图片扩展名的 HTTP(S) 裸链接，或 Markdown 图片 `![说明](URL)`。
- **预期现象**：默认 `ingest` 模式先下载、校验、归一化并保存为附件；同一已提交消息后续重放不再请求源 URL。无扩展名裸链接仍是普通文本，用 Markdown 图片语法可显式标记。
- **规则与边界**：`MULTIMODAL_REMOTE_IMAGE_MODE=passthrough` 保留供应商直接读取 URL 的旧行为；`disabled` 保留文字链接而不下载。选择 ingest 后下载失败不会静默改走 passthrough。
- **依据**：`attachments/admission.py::REMOTE_IMAGE_RE/remote_part`、`attachments/remote.py::RemoteImagePolicy`。

### UC-9B10 远程下载安全边界

- **触发**：默认模式需要下载初始 URL，或响应发生重定向。
- **预期现象**：每一跳解析并检查 DNS，连接固定到已检查的地址；HTTPS 继续使用原始主机名校验证书；私网、loopback、链路本地和混合公网/私网解析默认拒绝。
- **规则与边界**：仅 HTTP(S)，拒绝 URL 用户名/密码；默认总期限 20 秒、最多 3 次重定向，同时检查 Content-Length 和实际流式字节、响应 MIME 和完整图片解码。不继承浏览器 Cookie、供应商 API Key 或环境代理凭证。管理员可用 `ATTACHMENT_REMOTE_ALLOWED_HOSTS` 精确允许必要的内网主机。
- **依据**：`attachments/remote.py::resolve_target/_open/download_image`、`tests/test_vision_api.py` 远程下载用例。

### UC-9B11 显式 URL 入库 API

- **触发**：调用方执行 `POST /api/attachments/ingest`，请求 `{"urls":[...]}`。
- **预期现象**：服务端对整个 URL 数组执行 ingest，成功返回规范图片引用；调用方随后可把这些 ID 交给 `/chat` 或 `/api/vision/analyze`。
- **规则与边界**：需要 write scope，最多使用单消息图片数量上限；显式 ingest 在 passthrough 配置下仍入库，在 disabled 配置下拒绝。来源回执只记录 `kind=remote` 和 host，不保存查询参数、签名或 URL 凭证。
- **依据**：`attachments/api.py::register_attachment_api`、`attachments/remote.py`、`attachments/registry.py`。

## 5. 模型能力、预算与三协议投影

### UC-9B12 模型能力门控

- **触发**：候选 profile 声明支持或不支持 `image`，或供应商端点实际拒绝媒体。
- **预期现象**：支持 image 才准备请求图；不支持时图片转成含身份和只读路径的确定性文字占位，不读取或生成请求图缓存。端点实际拒绝媒体时记录被拒模态并回写 profile，后续避免重复失败。
- **规则与边界**：不再自动注入“交给 task 子代理识图”的强制委托文案；显式 task 传图仍支持。图片被省略不删除 Core 历史。音频/视频仍按原兼容降级规则处理。
- **依据**：`attachments/content.py::project_request_images`、`agent_openai.py::_media_error_modalities`、`model_profiles.mark_profile_modalities_failed`。

### UC-9B13 请求总预算与确定性省略

- **触发**：本次请求图片的 base64 表示长度或出现次数超过候选 profile 的预算。
- **预期现象**：按消息与内容顺序从最旧图片开始省略，生成可恢复文字引用；同样输入和策略得到同样结果，不修改会话历史。
- **规则与边界**：默认 base64 总预算 20 MiB，图片数量默认不另设上限；按 DSH byte/count quantum 取整，byte quantum 大于 1 时必须严格超过目标才停止省略。模型 profile 可覆盖 `maxInlineRequestImageBytes/maxImagesPerRequest/byteQuantum/countQuantum`。
- **依据**：`attachments/request_budget.py::offloaded_image_prefix_count/offload_request_images_with_policy`、`attachments/__init__.py::budget_policy`。

### UC-9B14 工具与 MCP 图片

- **触发**：MCP 或内置工具返回文字和一张或多张图片。
- **预期现象**：图片先进入统一准入，保留文字与图片顺序；Chat Completions 把连续 tool 结果的图片集中放到紧随其后的 user 消息，Responses 放入 `function_call_output.output`，Anthropic 放入 `tool_result.content`。
- **规则与边界**：工具消息不再统一 `str(content)`，MCP 图片不再直接写成 `[image content omitted]`。日志先去图片 payload 再序列化/截断，避免 base64 先进入日志。模型无 image 能力时明确省略且不写入 MCP 图片库。
- **依据**：`agent_mcp.py`、`attachments/content.py::chat_tool_images`、`llm/transport.py` 三个 Transport、`attachments/logging.py`。

### UC-9B15 主 Agent、备用模型与子代理一致投影

- **触发**：主模型调用、候选自动切换，或 task 子代理接收路径/附件引用。
- **预期现象**：每个实际候选从未裁剪的 Core 历史按自己的能力与预算重新投影；子代理在占用运行位前统一准入图片，向模型传引用并向执行环境提供规范只读路径。
- **规则与边界**：不能复用前一个候选已经省略过的 wire 请求作为历史事实。子代理坏图准入失败时不启动模型；非图片附件沿用原文件附件行为。
- **依据**：`agent_harness.py` 候选投影、`agent_subagent.py`、`agent_loop.py`。

## 6. 独立识图 API

### UC-9B16 创建持久识图请求

- **触发**：已上传/入库图片后，调用 `POST /api/vision/analyze`，提供稳定 `requestId`、`modelProfileId`、prompt、非空图片引用数组和 output。
- **预期现象**：服务端校验调用方附件权限和整条消息预算，解析现有模型 profile，后台运行不带工具的单轮识图。非流式连接等待终态；客户端断开时返回/保留 running，可稍后查询，不自动取消已发起的供应商调用。
- **规则与边界**：JSON 请求体最多 256 KiB；requestId 为 1–128 个字母、数字、点、下划线或连字符。所有图片都因能力/预算省略时返回 `VISION_NO_IMAGES` 且不调用模型。最大并发默认 4，历史记录默认最多 10000 条。
- **依据**：`vision_api.py::VisionJobs.start/_run/register_vision_api`、`webui.py::_vision_candidate`。

### UC-9B17 请求幂等与所有者隔离

- **触发**：相同设备重复提交 requestId，或另一设备尝试读取/取消该请求。
- **预期现象**：owner + requestId + 相同输入复用原作业与结果，不重新解析模型或调用供应商；同 ID 不同输入返回 409。其他设备看到 404，不能枚举结果。
- **规则与边界**：`stream` 不参与业务输入指纹，因此可用相同 ID 从非流式切换到流式观察。只有显式删除已结束的请求历史后，ID 才能作为新调用重新使用。
- **依据**：`vision_api.py::VisionJobs.start/get/cancel/prune`、SQLite `jobs/events` 表、`tests/test_vision_api.py` 并发幂等与设备隔离用例。

### UC-9B18 流式事件、状态查询与断线续接

- **触发**：`stream=true`，或调用 `GET /api/vision/requests/{id}`、`GET /api/vision/requests/{id}/events?after=N`。
- **预期现象**：SSE 依次报告 `accepted`、`image_prepared/image_omitted`、`answer_delta`，最后以 `completed/failed/cancelled` 收口；事件带递增 ID，断线后可从 N 继续。状态和最终事件在同一 SQLite 事务完成，查询不会先看到终态却读不到终态事件。
- **规则与边界**：每图状态至少为 `prepared/sent/omitted_budget/omitted_capability`；`sent` 表示供应商流已返回事件且图片在请求中，不证明模型已正确理解图片。运行中心跳每 10 秒更新；超过 180 秒的遗留作业标记 `VISION_INTERRUPTED`，不会自动重发导致重复计费。
- **依据**：`vision_api.py::publish/finish/events/get/stream_response`。

### UC-9B19 协作取消与超时

- **触发**：调用 `DELETE /api/vision/requests/{id}`，或请求超过执行期限。
- **预期现象**：接口先返回 `cancellationRequested=true` 和当前真实状态；工作线程在准备边界、流事件边界和结束前检查取消，关闭本次 transport 流，真正结束后才保存 `cancelled`。超时以 `VISION_TIMEOUT` 失败。
- **规则与边界**：取消不能撤回已产生的供应商费用，也不能保证第三方 SDK 的阻塞调用立即返回。供应商 I/O timeout 最多 30 秒；独立作业默认 120 秒执行预算在事件边界检查。HTTP/SSE 断线本身不等于取消。
- **依据**：`vision_api.py::cancel/_run`、`llm/transport.py::_managed_stream` 与各协议上下文关闭、`VISION_REQUEST_TIMEOUT_SECONDS`。

### UC-9B20 JSON Schema 结构化输出

- **触发**：请求使用 `output={"format":"json_schema","schema":{...}}`。
- **预期现象**：服务端先校验 Draft 2020-12 schema，再要求模型仅返回 JSON；最终文本解析并通过 schema 后写入 `structured`，否则返回 `VISION_OUTPUT_INVALID`。
- **规则与边界**：只允许本地 `$ref/$dynamicRef`，拒绝外部引用。流式 `answer_delta` 是尚未校验的中间文本，必须等待 completed 后使用 structured。这是服务端结果校验，不宣称所有供应商启用了原生 constrained decoding；结构正确也不等于视觉事实正确。
- **依据**：`vision_api.py::VisionJobs.start/_run`、依赖 `jsonschema>=4.18,<5`。

## 7. 权限、前端与生命周期

### UC-9B21 附件和识图请求授权

- **触发**：本机或远程设备上传、读取、引用、识图、导入导出或 GC。
- **预期现象**：本机直接 loopback 使用本地管理员身份；远程请求复用已配对设备的 Bearer/cookie 和 read/write/admin scopes。上传/URL 入库授予当前设备附件 grant；非管理员只能读自己的附件和识图请求，未授权统一返回 404。
- **规则与边界**：校验 Origin；带转发身份头的请求不因来源地址是 loopback 自动获得管理员。grant、导入导出和 GC 分别按所需 scope 限制。本隔离覆盖新附件/识图端点和 `/chat` 结构化图片引用，不把整个共享工作区 Agent 宣称为不可信租户沙箱。
- **依据**：`attachments/access.py`、`attachments/registry.py`、`remote_control/store.py::DevicePrincipal`、`webui.py` 附件路由。

### UC-9B22 前端耐久预览与队列保护

- **触发**：历史、工具行或待发送队列中展示同一个附件，节点被移除，或页面恢复队列。
- **预期现象**：用户消息中的图片在气泡下方以等高缩略图横向排列并按空间换行；同一附件 ID 跨容器共享一次 fetch 和 blob URL；最后一个节点离开时取消未完成下载并释放 URL。队列只保存附件引用，恢复/变更时向服务端同步 queue pin，保证未发送图片不会被 GC。
- **规则与边界**：同 scope 的 pin 更新串行发送，旧请求不能覆盖新状态；清空队列发送空引用集。离线时 localStorage 仍保留队列，重新加载时重试；尚未同步到服务端的离线引用只能依靠上传租约保护。
- **依据**：`workspace-media.js::renderDurableAttachmentImages`、`sse-handling.js::syncFollowupAttachmentPins/persistFollowupQueue`、`POST /api/attachments/references`。

### UC-9B23 可达性 GC 与请求历史清理

- **触发**：管理员调用 `POST /api/vision/gc`，或调用 `DELETE /api/vision/requests/{id}/history`。
- **预期现象**：GC 默认 dry-run，综合会话 JSON/JSONL/Markdown/文本中的附件 ID、队列/request pins、未过期租约和宽限期后列出候选；明确 `dryRun=false` 才删除。删除已结束请求历史同时释放它的附件 pin；运行中清理返回 409。
- **规则与边界**：默认宽限 7 天，HTTP 最低 1 天；任何引用文件读取错误会停止 GC。只删除经过身份和路径校验的规范图片与 metadata，不递归删除调用方目录。服务端无法枚举从未同步的浏览器 localStorage。
- **依据**：`attachments/lifecycle.py::collect_references/garbage_collect`、`attachments/registry.py`、`vision_api.py::gc/prune`。

### UC-9B24 会话/附件备份与恢复

- **触发**：导出含图片的会话，或调用管理员附件 `/export`、`/import`。
- **预期现象**：会话 ZIP 同时包含会话文件、`attachments/manifest.json` 和所引用的规范图片；独立导出按 ID 生成 ZIP。导入逐图验证并暂存，全部清单、固定路径、格式、尺寸、字节和摘要通过后才提交。
- **规则与边界**：拒绝 ZIP 路径穿越、重复 ID、损坏图片和配额超限；失败回滚新文件，已有对象保持不变。导入上限为 512 MiB 且受对象库配额限制。请求缓存可重建，不进入备份；恢复图片对象不等于自动导入会话历史。
- **依据**：`attachments/lifecycle.py::add_bundle/import_bundle`、`attachments/api.py`、`webui.py::_build_session_export_archive`。

### UC-9B25 图片指标和性能基准

- **触发**：执行图片准入、请求版本准备、远程下载、缓存淘汰或独立识图作业，或管理员读取 `/api/vision/metrics`。
- **预期现象**：返回当前进程的阶段计数与累计耗时，包括归一化、缓存命中/未命中/淘汰、远程下载字节、预算省略和作业完成/失败/取消；指标不含图片、完整 URL 或认证头。
- **规则与边界**：指标是进程内有界聚合，重启清零，不按 URL/用户/附件生成动态标签。`scripts/benchmark_attachments.py` 用 1/5/20 张合成图测量冷/热准备，不含供应商推理延迟，也不是生产 SLO。
- **依据**：`attachments/metrics.py`、`vision_api.py::metrics`、`scripts/benchmark_attachments.py`。

## 8. API 速查

| 方法与路径 | 最低权限 | 用途 |
|---|---|---|
| `POST /api/upload-chat-files` | write | 上传图片/文件，图片返回规范附件引用 |
| `GET /api/attachments/{attachmentId}` | read + grant | 校验后读取图片；支持 ETag/304 |
| `POST /api/attachments/ingest` | write | 把一组远程图片 URL 入库 |
| `POST /api/attachments/references` | write | 替换当前设备某个队列 scope 的 pins |
| `POST /api/attachments/grants` | admin | 向指定设备授予附件访问 |
| `POST /api/attachments/export` | admin | 按附件 ID 导出 ZIP |
| `POST /api/attachments/import` | admin | 完整校验后恢复附件 ZIP |
| `POST /api/vision/analyze` | write + 图片 grant | 创建/复用独立识图作业；可选 SSE |
| `GET /api/vision/requests/{id}` | owner | 查询持久状态和结果 |
| `GET /api/vision/requests/{id}/events?after=N` | owner | 按事件序号断线续接 |
| `DELETE /api/vision/requests/{id}` | owner + write | 请求协作取消 |
| `DELETE /api/vision/requests/{id}/history` | owner + write | 删除终态历史并释放 request pin |
| `GET /api/vision/metrics` | admin | 读取图片阶段指标 |
| `POST /api/vision/gc` | admin | dry-run 或执行附件可达性回收 |

独立识图最小请求：

```json
{
  "requestId": "image-check-001",
  "modelProfileId": "vision-profile-id",
  "prompt": "描述图片中的文字和主要对象",
  "images": [{"attachmentId": "sha256:<64位小写摘要>"}],
  "stream": false,
  "output": {"format": "text"}
}
```

终态响应示意：

```json
{
  "requestId": "image-check-001",
  "status": "completed",
  "modelProfileId": "vision-profile-id",
  "answer": "模型实际返回的分析",
  "images": [{
    "attachmentId": "sha256:<64位小写摘要>",
    "state": "sent",
    "requestWidth": 1600,
    "requestHeight": 900
  }],
  "usage": null
}
```

## 9. 配置速查

| 配置 | 默认值 | 作用 |
|---|---:|---|
| `MULTIMODAL_REMOTE_IMAGE_MODE` | `ingest` | `ingest/passthrough/disabled` |
| `ATTACHMENT_REMOTE_TIMEOUT_SECONDS` | `20` | 单张远程图片总下载期限 |
| `ATTACHMENT_REMOTE_MAX_REDIRECTS` | `3` | 远程图片最大重定向次数 |
| `ATTACHMENT_REMOTE_ALLOWED_HOSTS` | 空 | 显式允许的内网精确主机名 |
| `ATTACHMENT_STORE_MAX_BYTES` | `10737418240` | 规范对象与普通附件库配额 |
| `ATTACHMENT_CACHE_MAX_BYTES` | `536870912` | 可重建请求图片缓存配额 |
| `VISION_MAX_CONCURRENT_REQUESTS` | `4` | 全局运行识图作业上限 |
| `VISION_MAX_STORED_REQUESTS` | `10000` | 持久请求历史数量上限 |
| `VISION_REQUEST_TIMEOUT_SECONDS` | `120` | 独立作业事件边界执行期限 |

图片准入、规范化和请求预算的其余配置见 [API识图功能设计方案](../../API识图功能设计方案.md) 第 14、19 节。

## 10. 验收证据与边界

最终本地验证：Python **1587 passed，4 skipped**；识图/附件定向回归 **65 passed**；前端附件 **6 passed**；Vite 生产构建、dist 同步检查、Python compileall、文档 JSON 示例校验和 `git diff --check` 均通过。

验收覆盖整消息回滚、内容去重、缓存损坏恢复、线程/进程并发、实际本地 HTTP 重定向、私网/混合 DNS 阻断、幂等冲突、设备隔离、取消、SSE 续接、JSON Schema 成败、queue/request pins、GC、ZIP 恢复和前端 blob 生命周期。

三协议和独立 API 的模型调用使用本地协议转换与模拟 transport 验证。尚未用用户的真实模型额度逐家执行视觉效果测试，因此不能仅凭 HTTP 200 或有文字输出断言特定供应商真的理解了图片。真实验收应使用事实明确的文字、颜色和多图差异样本，并检查结果内容。

本方案不包含专业 OCR 引擎、图片生成、完整视频理解、供应商 Files API、原始图片档案保存、跨工作区全局去重或整个 Agent 的不可信租户隔离。

## 11. 跨模块边界

- 三种模型协议和能力失败回写：`../01-LLM接入/01-三协议与端点判定方案设计-UseCase清单.md`、`../01-LLM接入/05-手动切换与兼容降级矩阵方案设计-UseCase清单.md`。
- 图片上传和工作区文件：`../04-工作区/04-上传与命名方案设计-UseCase清单.md`。
- 输入、队列和图片渲染：`../05-WebUI对话界面/01-输入发送与插话方案设计-UseCase清单.md`、`../05-WebUI对话界面/02-消息渲染与滚动体验方案设计-UseCase清单.md`。
- 旧附件事件迁移：`../08-会话存储RuntimeV2/05-迁移修复与日志压缩方案设计-UseCase清单.md`。
- 通用运行指标：`04-观测与运行看板方案设计-UseCase清单.md`。

## 12. 版本记录

- 2026-09-20 v3：新增 UC-9B26，记录长历史附件序列化的环境读取与路径解析缓存，不改变附件校验语义。
- 2026-09-14 v2：按实际实现扩展为完整 API 识图方案，新增统一准入、远程图片三模式、独立 API、授权、幂等、SSE、取消、结构化输出、配额、GC、备份恢复、前端资源复用、指标和验收证据；删除旧的强制视觉委托描述。
- 2026-09-13 v1：拆分首版，覆盖请求投影、预算、工具图片、能力降级和附件存储。
