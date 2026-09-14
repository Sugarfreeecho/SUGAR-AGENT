# Agent 运行时 ReAct 循环 · 能力清单（代码证据版）

> 对象：MyAgent Agent 运行时（ReAct 主循环及配套运行时能力）
> 代码版本：HEAD `6acc6bf` + API 识图工作区改动（2026-09-14 扫描）
> 图例：【图】见 `react-loop.architecture.html`（10 节点）；【卡】图中卡片；【单】仅本清单

## 1. 主循环与轮次结构
| 能力 | 位置 | 状态 |
|---|---|---|
| ReAct 主循环 `react_node` / `_react_node_once`（决策-行动-观察），线程外执行避免阻塞事件循环 | `agent_loop.py`（L2853/L4509/L8534） | 【图】 |
| 每轮静态 system 多段重建：进程级缓存 + 修订漂移后台重建（最多一次请求陈旧） | `agent_loop.py` `_build_static_segments_for_session`、`_schedule_static_segments_rebuild` | 【图】 |
| 兜底与收尾：`validate_final` / `prepare_final_event` / `finish`、事件流 `astream_events` / `…_continuation` | `agent_loop.py` | 【单】 |
| 会话标题后台生成（诊断 + 兜底、worker 队列） | `agent_loop.py` `_session_title_worker` 等 | 【卡】 |

## 2. 提示与上下文装配
| 能力 | 位置 | 状态 |
|---|---|---|
| key_context 读取（会话摘要 / 恢复） | `_load_key_context_for_run`、`_load_runtime_v2_context_summary` | 【图】 |
| 分词与缓存：消息哈希、工具指纹、prompt-usage 基线、精确命中缓存 | `agent_tokenizer.py`（≈30 函数） | 【图】 |
| 上下文 token 计算与会话级模式（含压缩后估算） | `compute_context_tokens_for_session`、`get_context_token_mode` | 【卡】 |
| 未闭合工具调用清理 / 历史 sanitize（新运行前） | `_first_unclosed_tool_call_index`、`_sanitize_loaded_histories_for_new_run` | 【单】 |

## 3. 模型交互与工具链路
| 能力 | 位置 | 状态 |
|---|---|---|
| 模型调用（流式）与 AssistantTurn 解析（思考/工具增量） | `agent_loop.py` + `agent_openai.py` | 【图】 |
| 工具注册表构建（会话级、修订号、重校验调度） | `build_combined_tool_registry_for_session`、`_schedule_tool_registry_revalidate` | 【图】 |
| 工具执行 SSE：pending → 审批 → 调用 → 结果（含失败判定与状态分级） | `_emit_tool_pending_sse`、`_emit_tool_call_sse`、`_tool_result_status` | 【卡】 |
| 工具产物转存临时文件（大结果处理） | `_save_result_to_tempfile`、`_cleanup_temporary_write_files` | 【单】 |

## 4. 钩子与工作流
| 能力 | 位置 | 状态 |
|---|---|---|
| before_round / after 钩子回调注入提醒（workflow callbacks） | `_workflow_callbacks()`、`agent_loop.py` 主循环 | 【图】 |
| 停止钩子与执行前授权钩子（hook 决定 allow/ask/deny 理由） | `_apply_stop_hooks`、`_authorize_hook_before_execute`、`_dispatch_state_hook` | 【卡】 |
| 工具审查上下文（review 会话回放） | `_build_tool_review_context` 等 | 【单】 |

## 5. Steer 与中断
| 能力 | 位置 | 状态 |
|---|---|---|
| 插话队列（enqueue/claim/transition/remove，多模式 normalize） | `enqueue_session_steer`、`_claim_session_steers` | 【图】 |
| 运行中止与部分轮回滚（保护状态一致） | `abort_session_steer_run`、`_rollback_steer_partial_turn` | 【卡】 |
| steer 请求唤醒（`_raise_if_steer_requested`、`_await_steerable`） | `agent_loop.py` | 【单】 |

## 6. 错误分类与恢复
| 能力 | 位置 | 状态 |
|---|---|---|
| 链式分类器：NET / CTX / BUDGET / 具体码 / OTHER（保留 cause 链） | `_classify_api_error`、`_classify_api_error_leaf` | 【图】 |
| 上下文超限恢复窗口计算 | `_context_limit_error_info`、`_context_limit_recovery_window` | 【卡】 |
| 断网等待 + 重连（≤5 次），未闭合工具事件清理 | `_wait_for_local_network_recovery`、`_runtime_v2_delete_unfinished_tool_events_after_marker` | 【卡】 |
| CPU 压力事件（本地过载降级提示） | `_cpu_pressure_transition_event` | 【单】 |

## 7. Runtime V2 提交与生命周期
| 能力 | 位置 | 状态 |
|---|---|---|
| 用户轮 / 最终答复 / 模型消息提交、历史替换、摘要提交 | `_runtime_v2_commit_user_turn`、`_runtime_v2_commit_assistant_final` 等 | 【图】 |
| 上下文 token 检查点、Responses 压缩提交 | `_runtime_v2_checkpoint_context_tokens`、`_runtime_v2_commit_responses_compaction` | 【卡】 |
| 运行生命周期（开始/结束/unread 标记、写栅栏） | `_RuntimeV2RunLifecycle`、`_mark_run_terminal_unread`、`_state_run_has_write_fence` | 【单】 |

## 8. 观测与度量
| 能力 | 位置 | 状态 |
|---|---|---|
| pre-API 计时标点与日志、管道步骤计时 | `_pre_api_timing_mark`、`_pipeline_step_timing_log` | 【图】 |
| 流式首包/总时长日志、实时度量推送、GC 探查 | `_llm_stream_timing_log`、`_emit_live_metrics`、`_gc_probe_extras` | 【卡】 |

## 9. 并发与执行模型
| 能力 | 位置 | 状态 |
|---|---|---|
| 线程→异步桥（队列泵、SSE 保活等待） | `_ThreadToAsyncQueue`、`_await_thread_with_sse_keepalive` | 【单】 |
| 上下文策略串行化锁（防止并发策略冲突） | `_run_context_policy_serialized`、`_wait_context_policy_idle` | 【单】 |
| 用户内容在占用运行位前统一准入为耐久图片引用；每个实际模型候选发送前从 Core 历史重新投影能力、缩放与总预算 | `agent_loop.py`、`attachments/admission.py`、`attachments/content.py` | 【单】 |

## 10. 边界说明
- 工具系统内部实现（注册表细节、各工具、审批闸口策略）归"工具系统"与"权限审批"模块清单。
- 会话持久化细节（Runtime V2 存储格式、迁移）归"会话存储 Runtime V2"模块清单。
- 图片准入、模型候选投影和独立 API 的完整契约见 [识图与多模态投影](../09-横切能力/02-识图与多模态投影方案设计-UseCase清单.md)。
