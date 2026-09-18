# LLM Provider API 接入层 · 能力清单（代码证据版）

> 对象：MyAgent（本机 `D:\AI\AI Agent\MyAgent Developer`）的 LLM Provider API 接入子系统
> 代码版本：HEAD `1fd80ca` + 运行中切换修复（2026-09-18 复核）
> 图例：【图】已画入 v3 全景图节点 / 【卡】在图上卡片中 / 【单】仅本清单（超出 12 主节点容量）

## 1. 请求生命周期与身份
| 能力 | 位置 | 状态 |
|---|---|---|
| 请求用途分类：`main / goal_judge / title / summary / security_review / diagnostic` | `llm/types.py` `LLMRequestPurpose` | 【单】 |
| 会话级 `prompt_cache_key`（含 lineage/purpose/issuer/model 哈希，服务前缀缓存） | `llm/types.py` `prompt_cache_key()` | 【单】 |
| 请求上下文身份：`session_id / lineage_id / history_generation` | `llm/types.py` `LLMRequestContext` | 【单】 |
| 服务端存储开关：`server_storage_allowed`（隐私旗标，Responses 服务端存储可关） | `llm/types.py`、`model_profiles.responses_store_disabled` | 【单】 |
| 事件流中立契约：`TransportEvent`（含 `is_first_token`、tool_call 增量、usage、finish_reason） | `llm/types.py` | 【单】 |

## 2. 可靠性（调用层内核）
| 能力 | 位置 | 状态 |
|---|---|---|
| 重试：4 次、退避 1s 起；错误可重试性分类 | `agent_openai.py` `OPENAI_MAX_RETRIES`、`_classify_candidate_failure` | 【卡】 |
| 首 token 竞速对冲（hedge）：30s 未达即并发布备请求、可关、胜者胜出 | `agent_openai.py` hedge 常量与 `run_*` 逻辑 | 【卡】 |
| 共享逻辑请求预算：单请求预算 6 次物理请求（hedge/重试/fallback 共摊） | `agent_openai.py` `_LogicalRequestBudget` | 【卡】 |
| 时限与并发：总截止 600s、in-flight 上限 3 | `agent_openai.py` | 【卡】 |
| 流式降级：流式失败降为整段（buffered-via-stream）；非流式路径经流式缓冲实现，保留对冲/取消能力 | `agent_openai.py` `_buffered_chat_completion_via_stream` | 【卡】 |
| 用户中断/取消：steer/cancel 贯穿 hedge 与流 | `agent_loop.py`、`agent_openai.py` | 【单】 |
| 网络连通性分类：断网≠普通错误（`LocalNetworkUnavailableError`） | `agent_harness.py` | 【图·网络节点】 |
| 网络重连循环：断网等待恢复 + 最多 5 次重连（NET-RETRY 式提示） | `agent_loop.py` `NETWORK_RECONNECT_MAX_ATTEMPTS=5` | 【图·网络节点】 |
| 流观察者重连（SSE `streamReconnect`） | `webui.py` `MYAGENT_ENABLE_STREAM_RECONNECT` | 【单】 |
| 上下文超限恢复（Bounded context-recovery）：CTX 错误→压缩→继续 | `agent_loop.py`、`tests/test_context_limit_recovery.py` | 【单】 |

## 3. 端点、协议与状态（llm/ 包）
| 能力 | 位置 | 状态 |
|---|---|---|
| 三条线协议：OpenAI Responses / Chat Completions 兼容 / Anthropic Messages | `llm/transport.py` 三个 Transport 类 | 【图·三端点】 |
| `auto` 协议判定：官方 host 走原生、其余按兼容；强制 Responses 用档案 `llm_type:openai-responses`（legacy `openai` 归一为 auto） | `llm/transport.py` `detect_provider/resolve_provider` | 【图·边标签】 |
| Responses 状态模式：`stateful`（previous_response_id）/`stateless`（重放）/`auto` | `llm/transport.py` `ResponsesStateMode`；续接判定 `llm/responses/state.py` `ContinuationAnchor`、`evaluate_continuation` | 【卡】 |
| WebSocket 模式协商：`auto/enabled/disabled`（仅官方 host 探测） | `llm/transport.py` `_responses_websocket_mode` | 【卡】 |
| Responses 原生压缩：checkpoint 与匹配、可续接 | `llm/responses/compact.py` | 【单】 |
| 结构化错误分类：rate_limit/transient/invalid_previous/encrypted_reasoning/unsupported_compact… | `llm/responses/capabilities.py` | 【单】 |
| 端点能力缓存（探测结果缓存） | `llm/responses/capabilities.py` `responses_capability_cache` | 【单】 |
| Provider 注册表（fail-closed、语义版本 v2、discover/probe 诊断钩子） | `llm/provider_registry.py` | 【单】 |
| 流式工具名跨增量合并 | `llm/transport.py` `merge_streamed_tool_name` | 【单】 |

## 4. 多模态 / 识图
| 能力 | 位置 | 状态 |
|---|---|---|
| 请求图片→base64 data URL 投影（含文本 handle 提示） | `attachments/content.py` `project_request_images` | 【图·多模态节点】 |
| Core 消息只保存 sha256 附件引用；统一整消息准入、批次回滚和旧格式迁移 | `attachments/admission.py`、`runtime_v2/attachment_migration.py` | 【单】 |
| 图片规范化与内容寻址：EXIF、8 位 sRGB、元数据清理、JPEG/WebP、完整性复验 | `attachments/normalization.py`、`local.py` | 【单】 |
| 每候选请求版本缓存、按键线程/进程去重、损坏重建 | `attachments/request_image.py`、`locking.py`、`validation.py` | 【单】 |
| 超预算自动卸载为文本引用；按 base64 表示长度和 DSH quanta 从最旧图片确定性省略 | `attachments/request_budget.py` | 【卡】 |
| 工具结果图片并入后续消息（chat tool 限制规避） | `attachments/content.py` `chat_tool_images` | 【卡】 |
| Chat/Responses/Anthropic 分别映射工具图片，关闭流时释放底层资源 | `llm/transport.py` 三个 Transport、`_managed_stream` | 【单】 |
| 候选不支持图片→确定性文本句柄；不生成请求图缓存，不再强制注入视觉委托 | `attachments/content.py` `project_request_images` | 【卡】 |
| 端点拒绝媒体→识别被拒模态并回写档案（自动降级能力标记） | `agent_openai.py` `_media_error_modalities`、`model_profiles.mark_profile_modalities_failed` | 【单】 |
| 文本路径图片扫描开关 / 图片请求策略 | `MULTIMODAL_TEXT_PATH_SCAN`、`normalize_image_request_policy` | 【单】 |
| 远程图片 `ingest/passthrough/disabled` 三模式、逐跳 DNS/IP 安全校验 | `attachments/remote.py`、`admission.py` | 【单】 |
| 独立识图 API：profile 复用、持久幂等、SSE/查询/取消、JSON Schema 结果校验 | `vision_api.py` | 【单】 |
| 图片授权、对象/缓存配额、pins/租约、GC、ZIP 备份恢复和指标 | `attachments/{access,registry,lifecycle,api,metrics}.py` | 【单】 |

## 5. 模型档案与探测
| 能力 | 位置 | 状态 |
|---|---|---|
| 档案注册表：排序/启停/删除/`fallback_chain()` 候选链来源 | `model_profiles.py` | 【图·档案节点】 |
| 能力推断与评分门槛（低成本/高智能/编码/Agentic/长上下文；models_table 价格与窗口） | `model_profiles.py` `infer_model_task_capabilities`、`app/data/models_table.md` | 【单】 |
| 上下文窗口探测：最大 3M token 探针、8s 超时、从报错文本提取窗口 | `model_profiles.py` `probe_model_context`、`extract_context_window_from_error` | 【单】 |
| wire 协议探测：按端点试探可用协议（payload/headers/route-missing 判定） | `model_profiles.py` `detect_wire_protocol` | 【单】 |
| 模型列表发现：`GET /models` 拉取端点模型目录 | `model_profiles.py` `discover_models` | 【单】 |
| URL 构造：三个协议端点 + models 端点 | `model_profiles.py` `*_url_for_base` | 【单】 |
| 专用分支：华为云 API 域名特判 | `model_profiles.py` `is_huawei_api_domain` | 【单】 |
| 旧 .env 单档案导入迁移 | `model_profiles.py` `register_legacy_env_model_profile` | 【单】 |
| 会话级自定义请求头 | `model_profiles.py` `profile_with_session_request_headers` | 【单】 |

## 6. 模型响应特性适配
| 能力 | 位置 | 状态 |
|---|---|---|
| 思考字段格式矩阵：deepseek=reasoning_content / reasoning / think_blocks / none；多轮回传 | `agent_openai.py` `messages_to_openai_params`、`agent_reasoning.py` | 【卡】 |
| 思考字段在 fallback 候选间重映射 | `agent_harness.py` `_remap_serialized_reasoning_format` | 【单】 |
| DSML 工具调用救援：从文本中解析/修复 DSML invoke（含流式过滤器） | `agent_openai.py` `_parse_dsml_invokes`、`_DsmlStreamFilter` | 【单】 |
| 原生边界 token 过滤 | `agent_openai.py` `_NativeBoundaryStreamFilter` | 【单】 |
| GLM 模型专项分支 | `agent_openai.py` `_is_glm_model` | 【单】 |
| `stream_options` 不兼容错误识别与降级 | `agent_openai.py` `_is_stream_options_error` | 【单】 |

## 7. 切换与降级（自动 / 手动）
| 能力 | 位置 | 状态 |
|---|---|---|
| 自动：候选链切换（【模型自动切换】状态事件）、同模型重试、媒体降级、adopt 备选档案（受选择纪元守卫，不覆盖更新的手动选择） | `agent_harness.py` `_FallbackCompletions` | 【图·切换节点】 |
| 预算阻断：想切换但预算不足 → `LLM-BLOCKED-SWITCH` | `agent_harness.py` `_emit_blocked_switch_status` | 【卡】 |
| 手动：模型选择器（主会话/子代理会话均可用；清熔断立即重试、下一次模型调用生效） | `webui.py`、`agent_harness.py` | 【卡】 |
| 手动：子代理 `switch_model`（安全边界中断并恢复）/ 选择器路径（数据动作、不打断） | `agent_subagent.py::switch_subagent_model_profile(handover=…)` | 【卡】 |
| 手动切换一致性：选择纪元（旧请求接管不改写新选择）、熔断代际（重置后不重新污染）、配置缓存代际 | `agent_harness.py` | 【单】 |
| 切换历史记录：`model_switch_history` / `last_model_switch`（自动与手动；含子代理切换状态） | `agent_harness.py` | 【单】 |

## 8. 网络与安全
| 能力 | 位置 | 状态 |
|---|---|---|
| 本机离线检测（OS 提示 + 主动探测，离线时不发散 fallback） | `agent_harness.py` `machine_network_available` | 【图·网络节点】 |
| SSL bypass（requests/httpx 全局 `verify=False` 补丁，默认开、可关） | `app/ssl_bypass.py`、`SSL_BYPASS_ENABLED=0` | 【图·网络节点(副标题)】 |
| 密钥脱敏：日志/状态文案统一 `_redact_runtime_log_text` | `agent_openai.py`、`agent_harness.py` | 【单】 |

## 9. 观测与告警（AlertSpec）
| 能力 | 位置 | 状态 |
|---|---|---|
| Token 用量采集（`record_usage` → runtime_observability / execution_metrics） | `agent_openai.py` `extract_usage_dict`、`runtime_observability.py` | 【卡】 |
| 已实现告警：`LLM-RETRY`(L1)、`LLM-BLOCKED-SWITCH`(L2)、模型自动切换状态、错误卡分类 NET/BUDGET/CTX/429/5xx + retry 字段 | `agent_harness.py`、`agent_loop.py` | 【图·告警节点】 |
| 告警目录中的规划项：`LLM-HEDGE`、`LLM-DEGRADE`、`LLM-BUDGET`、`LLM-RECOVERED`、`LLM-FAILED`、`NET-OFFLINE`、`NET-RESTORED` 等（分级 L0–L3、ephemeral/持久化、恢复配平） | `workspace/alert_spec_myagent/ALERT_SPEC.md` | 【单·规划中】 |
| 错误原因链保留（`raise ... from`）保证分类器不落"未知错误" | `agent_harness.py` `_raise_budget_exhausted_before_fallback` | 【单】 |

## 10. 边界说明
- 本清单由代码扫描整理（含 grep 函数清单 + 关键实现片段核对），未覆盖 UI 前端细节（如模型选择器交互）与测试文件内部实现。
- `graph TD/API` 12 主节点容量仅能承载"主干"，其余能力以卡片与本文档形式记录；如需要，可另出"机制时序图（sequence）"渲染自动切换与告警全过程。
- API 识图完整用户用例见 `../09-横切能力/02-识图与多模态投影方案设计-UseCase清单.md`；真实供应商视觉效果尚未逐家使用实际额度验证。
