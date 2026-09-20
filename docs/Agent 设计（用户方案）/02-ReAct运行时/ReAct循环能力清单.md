# Agent 运行时 ReAct 循环 · 能力清单（代码证据版）

> 对象：MyAgent Agent 运行时（ReAct 主循环及配套运行时能力）
> 代码版本：当前工作区（2026-09-20；补充历史性能优化 3.1~3.19、运行生命周期防风暴、跨进程恢复租约与后台子代理任务托管）
> 图例：【图】见 `react-loop.architecture.html`（10 节点）；【卡】图中卡片；【单】仅本清单

## 1. 主循环与轮次结构
| 能力 | 位置 | 状态 |
|---|---|---|
| ReAct 主循环 `react_node` / `_react_node_once`（决策-行动-观察），线程外执行避免阻塞事件循环 | `agent_loop.py` | 【图】 |
| 长运行软收敛：24轮/48工具调用开始综合提醒，32轮/72工具调用升级；请求尾部注入以保护前缀缓存 | `_late_round_synthesis_reminder`、`convergence_reminder` | 【单】 |
| 每轮静态 system 多段重建：进程级缓存 + 修订漂移后台重建（最多一次请求陈旧） | `agent_loop.py` `_build_static_segments_for_session`、`_schedule_static_segments_rebuild` | 【图】 |
| 兜底与收尾：`validate_final`（现为 PASS 占位事件，不调用独立校验模型）/ `prepare_final_event` / `finish`、事件流 `astream_events` / `…_continuation` | `agent_loop.py` | 【单】 |
| 会话标题后台生成（诊断 + 兜底、worker 队列） | `agent_loop.py` `_session_title_worker` 等 | 【卡】 |

## 2. 提示与上下文装配
| 能力 | 位置 | 状态 |
|---|---|---|
| key_context 读取（会话摘要 / 恢复） | `_load_key_context_for_run`、`_load_runtime_v2_context_summary` | 【图】 |
| 分词与缓存：对象身份最长前缀、扁平文本最长前缀、精确命中、工具指纹、prompt-usage 基线 | `agent_tokenizer.py`（≈30 函数） | 【图】 |
| tokenizer 启动后台预热；加载锁避免与首请求并发重复解析，失败维持字符/4回退 | `warm_tokenizer`、`_TOKENIZER_LOAD_LOCK`、`webui.start_webui_lifecycle` | 【单】 |
| 本地 token 估算诊断旁路（只用于归因，禁止作为生产默认） | `CONTEXT_TOKEN_SKIP_LOCAL_ESTIMATE`、`estimate_full_input_tokens_for_messages` | 【单】 |
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
| 工作流回调 registry 2 秒 TTL 缓存；显式失效后重建 | `_WORKFLOW_CALLBACKS_CACHE`、`_invalidate_workflow_callbacks_cache` | 【单】 |
| Todo `before_round` 从同步内存态判断活跃计划，初始化/更新/压缩边界回源刷新 | `TodoManager.has_active_plan`、`initialize_state` | 【单】 |
| 停止钩子与执行前授权钩子（hook 决定 allow/ask/deny 理由） | `_apply_stop_hooks`、`_authorize_hook_before_execute`、`_dispatch_state_hook` | 【卡】 |
| 工具审查上下文（review 会话回放） | `_build_tool_review_context` 等 | 【单】 |

## 5. Steer 与中断
| 能力 | 位置 | 状态 |
|---|---|---|
| 插话队列（enqueue/claim/transition/remove，多模式 normalize） | `enqueue_session_steer`、`_claim_session_steers` | 【图】 |
| 运行中止与部分轮回滚（保护状态一致） | `abort_session_steer_run`、`_rollback_steer_partial_turn` | 【卡】 |
| steer 请求唤醒（`_raise_if_steer_requested`、`_await_steerable`） | `agent_loop.py` | 【单】 |
| exact run 中断：请求、原因与检查点均匹配 `(session_id, run_id)`；写栅栏被接管时原因为 `superseded_by_new_run` | `agent_harness.py`、`_state_interrupt_requested`、运行收尾分支 | 【单】 |

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
| 终态强收敛：生命周期唯一终态、幂等 operation id、有限重试；`can't start new thread` 时同步追加兜底，指标收尾不因持久化失败被跳过 | `_RuntimeV2RunLifecycle.commit`、`_finalize_agent_run_lifecycle` | 【单】 |
| Goal continuation 单租约、遗留 run 对账、interrupted 退避与默认三连败暂停 | `agent_goal.py`、`plugins/agent-goal/runner.py` | 【单】 |
| 跨进程恢复租约：本地任务表为空时，联合 Runtime V2 最近活动与未缓存的共享 exact-run 心跳判活；新鲜租约禁止 `no_local_activity` 清理/恢复 | `webui._discover_recoverable_react_sessions`、`_runtime_observability_active_runs_are_recent` | 【单】 |
| UI 验证服务隔离：一次性 `WORK_DIR` + dotenv 覆盖禁用，仅清理自身测试会话/目录 | `agent_harness.load_app_dotenv`、`scripts/subagent_ui_verify.py` | 【单】 |

## 8. 观测与度量
| 能力 | 位置 | 状态 |
|---|---|---|
| pre-API 计时标点与日志、管道步骤计时 | `_pre_api_timing_mark`、`_pipeline_step_timing_log` | 【图】 |
| 严格轮间分段：tool_result_post / tool_to_next_api / round_gap / pre_api / pre_api_tail / request_start；嵌套诊断段不重复计入总计 | `_pre_api_timing_total`、`execution_metrics.py` | 【单】 |
| 流式首包/总时长日志、实时度量推送、GC 探查 | `_llm_stream_timing_log`、`_emit_live_metrics`、`_gc_probe_extras` | 【卡】 |
| 进程级共享心跳；观测刷盘/计时线程启动失败时同步或非致命降级 | `execution_metrics._heartbeat_pump`、`runtime_observability._schedule_write`、`runtime_power.py` | 【单】 |

## 9. 并发与执行模型
| 能力 | 位置 | 状态 |
|---|---|---|
| 线程→异步桥（队列泵、SSE 保活等待） | `_ThreadToAsyncQueue`、`_await_thread_with_sse_keepalive` | 【单】 |
| 上下文策略串行化锁（防止并发策略冲突） | `_run_context_policy_serialized`、`_wait_context_policy_idle` | 【单】 |
| 用户内容在占用运行位前统一准入为耐久图片引用；每个实际模型候选发送前从 Core 历史重新投影能力、缩放与总预算 | `agent_loop.py`、`attachments/admission.py`、`attachments/content.py` | 【单】 |
| 后台子代理任务托管于进程级持久事件循环（守护线程 `subagent-background-loop`）；创建/注册原子交接，父轮临时循环关闭不中断 | `agent_subagent._BackgroundSubagentLoop`、`SubagentTaskRegistry.start_background` | 【单】 |
| 跨事件循环等待/取消桥接：等待超时不取消 owner 任务；取消经 owner 循环执行并等待结算（≤8s） | `SubagentTaskRegistry.wait/cancel` | 【单】 |

## 10. 边界说明
- 工具系统内部实现（注册表细节、各工具、审批闸口策略）归"工具系统"与"权限审批"模块清单。
- 会话持久化细节（Runtime V2 存储格式、迁移）归"会话存储 Runtime V2"模块清单。
- 图片准入、模型候选投影和独立 API 的完整契约见 [识图与多模态投影](../09-横切能力/02-识图与多模态投影方案设计-UseCase清单.md)。

## 11. 版本记录

- 2026-09-20：补录后台子代理任务的持久循环托管与跨循环等待/取消桥接；任务生命周期与调用方循环解耦。
- 2026-09-20：补充跨进程 exact-run 租约、共享心跳直接读盘、孤儿宽限保护与 UI 验证服务工作区隔离。
- 2026-09-20：补充 exact run 中断、写栅栏接管原因、终态线程耗尽兜底、共享心跳与 Goal continuation 租约/熔断。
- 2026-09-20：同步长运行收敛检查点、增量精确分词、tokenizer 后台预热与严格轮间计时口径。
- 2026-09-20：补齐工作流回调 TTL 缓存、Todo 内存态 lookup 与本地 token 估算诊断旁路。
