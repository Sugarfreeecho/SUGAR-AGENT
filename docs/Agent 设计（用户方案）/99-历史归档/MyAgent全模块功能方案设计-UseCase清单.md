# MyAgent · 全模块功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf` + 工作区未提交改动——含告警分级、网络恢复、模型档案刷新等）
- 用途：**逐条审查功能与现象是否符合需求**。每条用例给出「触发 → 预期现象 → 规则与边界 → 依据」。审查时按编号逐条勾选；如有不符，反馈编号即可。
- 适用：MyAgent 全量模块——LLM 接入 / ReAct 运行时 / 工具系统 / 工作区 / WebUI / 能力扩展 / 权限审批 / 会话存储 Runtime V2 / 横切能力（压缩、识图、告警、观测）。
- 配套资料（同目录）：8 份《能力清单》Markdown；架构 HTML 与交付回执位于 `workspace/archify_study/`。

---

## 0. 阅读指南

每条 UseCase 的固定结构：

| 字段 | 含义 |
|---|---|
| **触发** | 谁做了什么操作（用户 / 模型 / 系统） |
| **预期现象** | 界面上应该看到什么（这是审查验收的核心） |
| **规则与边界** | 为什么是这个现象；什么情况下会不同 |
| **依据** | 代码位置或交付回执（可复核） |

状态标记：✅ 已实现 · 🟡 规范/规划中（尚未落地，不应作为验收目标） · ⚪ 已知取舍（不是故障）。

---

## 1. 功能定位与范围

**一句话**：MyAgent 是一个本地运行的通用 Agent 应用——对话界面（WebUI）+ ReAct 执行内核 + 完整工具链（文件/Shell/Web/任务）+ 可扩展体系（插件/技能/MCP/Hooks）+ 安全审批 + 事件溯源式会话存储（Runtime V2）。

**目标**：
1. 任意 OpenAI 兼容 / OpenAI Responses / Anthropic 三类端点皆可接入，模型可自动或手动切换；
2. 执行过程透明可追溯（事件流、告警、变更可回放）；
3. 危险操作有分级授权（完全访问 / 请求批准 / 替我审批）；
4. 一切能力可扩展、可热更新、可审计。

**明确的非目标 / 已知边界**（详见 §12）：
- 不做云端多租户；凭证与卷宗均在本机；
- 部分告警（LLM-HEDGE、LLM-BUDGET、CTX-FULL 等）仍处于规范阶段 🟡；
- WebUI 架构图为"骨架版"，全要素展开为可选迭代。

**模块地图**：

| 模块 | 用例编号段 | 架构交付（workspace/archify_study/） | 清单（docs/Agent 设计（用户方案）/） |
|---|---|---|---|
| LLM 接入 | UC-1xx | `llm_provider_api/`（v3，12 节点） | LLMProviderAPI能力清单.md |
| ReAct 运行时 | UC-2xx | `react_loop/`（10 节点） | ReAct循环能力清单.md |
| 工具系统 | UC-3xx | `tools/`（10 节点） | 工具系统能力清单.md |
| 工作区 | UC-4xx | `workspace/`（10 节点） | 工作区能力清单.md |
| WebUI | UC-5xx | `webui/`（7 节点骨架） | WebUI能力清单.md |
| 能力扩展 | UC-6xx | `extensions/`（10 节点） | 能力扩展加载能力清单.md |
| 权限审批 | UC-7xx | `approval/`（11 节点） | 权限审批能力清单.md |
| 会话存储 Runtime V2 | UC-8xx | `runtime_v2/`（10 节点） | 会话存储RuntimeV2能力清单.md |
| 横切能力 | UC-9xx | 散布于上述各图 | 各清单交叉章节 |

---

## 2. 核心概念

| 概念 | 含义 |
|---|---|
| **session / run** | 会话；一次任务执行（告警与统计的结算边界） |
| **turn** | 一轮"用户发送 → 模型响应（含工具往返）" |
| **purpose** | 请求用途：main / goal_judge / title / summary / security_review / diagnostic |
| **候选链（fallback chain）** | 由模型档案排序决定的备用模型序列，自动切换按此执行 |
| **权限三档** | 完全访问 / 请求批准 / 替我审批（全局默认 + 会话覆盖） |
| **key_context** | 单一「## 上下文摘要」小节；压缩产物写入其中 |
| **Runtime V2** | events.jsonl 唯一真源 + 投影/快照/迁移；流式续看以游标读取 |
| **审批闸口** | 工具执行前的等待点：人工卡片 / 自动复核 / 规则直通 |

---

## 3. LLM 接入（UC-1xx）

### UC-101 三协议自动判别（auto）
- **触发**：选择任一模型档案发起对话。
- **预期现象**：官方 OpenAI / Anthropic host 走原生协议；其余端点一律走 Chat Completions 兼容协议；界面无感知差异。
- **规则与边界**：可用 `EXECUTOR_LLM_TYPE=openai` 强制 Responses 代理；协议选择不影响消息形态。
- **依据**：`app/llm/transport.py::detect_provider / resolve_provider`。

### UC-102 Responses 状态模式
- **触发**：使用官方 OpenAI（或强制 Responses）时。
- **预期现象**：`stateful`（previous_response_id 续接）/ `stateless`（重放）/ `auto` 自动判定；续接失败自动回退重放，不打断对话。
- **规则与边界**：加密推理块失效、previous 无效等错误有独立分类与自愈路径。
- **依据**：`llm/responses/state.py`、`llm/responses/capabilities.py`。

### UC-103 Responses 原生压缩
- **触发**：长会话在原生协议下达到压缩点。
- **预期现象**：走服务端压缩检查点（checkpoint），本地不重复做同规模压缩；检查点可续接。
- **依据**：`llm/responses/compact.py`、`agent_openai.py::compact_responses_history`。

### UC-104 传输重试
- **触发**：瞬时传输错误（429/5xx/连接抖动）。
- **预期现象**：同模型自动重试（≤4 次、1s 起步的退避），不换模型；界面只有轻量状态提示。
- **依据**：`agent_openai.py`（OPENAI_MAX_RETRIES、重试分类）。

### UC-105 首 token 对流（hedge）
- **触发**：主请求首 token 超过 30s 未达。
- **预期现象**：并发出备请求竞速，胜者出内容，败者被取消；用户只看到"更慢但成功"的一次回答。
- **规则与边界**：对冲请求计入共享预算；可配置关闭。
- **依据**：`agent_openai.py`（first-token hedge 逻辑）。

### UC-106 共享请求预算
- **触发**：一次逻辑请求内同时对冲 + 重试 + 后续。
- **预期现象**：物理请求总量不超过 6（默认）；超限即进入受控终止路径，不无限重试。
- **依据**：`agent_openai.py::_LogicalRequestBudget`。

### UC-107 截止与并发
- **触发**：模型长时间无响应或并发升高。
- **预期现象**：总截止 600s 到点终止；同 Provider in-flight ≤3，排队而不夯死。
- **依据**：`agent_openai.py`（OPENAI_TOTAL_DEADLINE_SEC / OPENAI_MAX_INFLIGHT_REQUESTS）。

### UC-108 思考字段与流式增量
- **触发**：模型返回 reasoning / tool_call 增量。
- **预期现象**：思考内容按目标模型格式转换（deepseek=reasoning_content 等）且多轮回传不丢；工具名跨增量合并无碎片。
- **依据**：`agent_openai.py::messages_to_openai_params`、`agent_reasoning.py`、`llm/transport.py::merge_streamed_tool_name`。

### UC-109 自动候选切换
- **触发**：当前模型失败（且非纯重试类）。
- **预期现象**：状态区出现「【模型自动切换】」提示，按档案候选链切换并继续任务；切换历史可见。
- **规则与边界**：切换是"续跑"而非重开；提示有去重（同 run 内不刷屏）。
- **依据**：`agent_harness.py::_FallbackCompletions / _emit_model_switch_status`。

### UC-110 预算不足阻断切换（LLM-BLOCKED-SWITCH）✅
- **触发**：想切换但共享预算已耗尽。
- **预期现象**：L2 告警「切换被预算阻断」，任务以明确错误结束；绝不"假装在切换"。
- **依据**：`agent_harness.py::_emit_blocked_switch_status`、`app/alert_spec` 实施记录。

### UC-111 手动模型切换
- **触发**：用户在界面上切换模型 / 子代理 `switch_model`。
- **预期现象**：正在运行的会话中断并恢复（保留上下文），以新档案继续；子代理切换只影响该子代理。
- **依据**：`agent_harness.py`（模型切换机制）、`agent_subagent.py`。

### UC-112 媒体能力降级
- **触发**：候选模型不支持图片输入 / 端点拒绝媒体。
- **预期现象**：纯文本降级 + 注入委托指令（"让支持视觉的模型看"）；被拒模态回写档案，后续不再踩坑。
- **依据**：`agent_openai.py`（_strip_media/_inject_non_image_fallback）、`model_profiles.mark_profile_modalities_failed`。

### UC-113 端点兼容性降级
- **触发**：端点不支持 `stream_options` 等参数。
- **预期现象**：识别错误 → 自动降级重发，用户无感；降级过程不触发误报。
- **依据**：`agent_openai.py::_is_stream_options_error`。

### UC-114 DSML 工具调用救援
- **触发**：模型把工具调用"写在文本里"（DeepSeek 系 DSML 形态）。
- **预期现象**：从文本解析/修复工具调用并正常执行；流式场景有过滤器兜底；界面表现与常规工具调用一致。
- **依据**：`agent_openai.py::_parse_dsml_invokes / _DsmlStreamFilter`。

### UC-115 用量采集
- **触发**：每次模型响应。
- **预期现象**：token 用量进入运行看板与执行指标；不影响对话速度。
- **依据**：`extract_usage_dict`、`runtime_observability.record_usage`。

### UC-116 网络重连
- **触发**：请求因本机断网失败。
- **预期现象**：界面提示"网络连接失败，正在重连（第 n 次，x 秒后重试）"；恢复后自动续跑；上限 5 次后进入常规失败路径。
- **依据**：`agent_loop.py`（NETWORK_RECONNECT_MAX_ATTEMPTS / _wait_for_local_network_recovery）。

### UC-117 SSL 直达
- **触发**：内网/自签证书环境下访问模型端点。
- **预期现象**：默认不因证书校验失败而连不上；可用 `SSL_BYPASS_ENABLED=0` 关闭（外网环境）。
- **依据**：`app/ssl_bypass.py`。

### UC-118 端点探测与诊断
- **触发**：配置新模型档案。
- **预期现象**：wire 协议探测（哪种协议可用）+ 上下文窗口探测（3M token 探针，从报错提取真实窗口）；探测失败有明确原因。
- **依据**：`model_profiles.detect_wire_protocol / probe_model_context`。

### UC-119 前缀缓存与会话身份
- **触发**：多轮对话。
- **预期现象**：会话级 prompt_cache_key 稳定命中（更快 + 更省钱）；不同用途的请求互不污染缓存。
- **依据**：`llm/types.py::prompt_cache_key`（purpose/issuer/model 哈希）。

### UC-120 隐私旗标
- **触发**：档案配置了"禁用服务端存储"。
- **预期现象**：Responses 线的服务端存储被关闭（server_storage_allowed=false 语义）；界面不额外打扰。
- **依据**：`llm/types.py`、`model_profiles.responses_store_disabled`。

---

## 4. ReAct 运行时（UC-2xx）

### UC-201 主循环
- **触发**：用户发送消息。
- **预期现象**：模型思考 → 调工具 → 看结果 → 再思考，直到给出最终答复；每轮有进度感（思考计时、工具状态）。
- **依据**：`agent_loop.py::react_node / _react_node_once`。

### UC-202 提示静态段缓存
- **触发**：连续多轮对话。
- **预期现象**：系统提示不随轮次频繁重算；技能/插件/工具变更最多滞后一次请求生效。
- **依据**：`_build_static_segments_for_session`、`_schedule_static_segments_rebuild`。

### UC-203 key_context 装配
- **触发**：每轮构建输入。
- **预期现象**：会话摘要（含压缩产物）稳定注入；恢复中的会话能接上旧摘要。
- **依据**：`_load_key_context_for_run`、`_load_runtime_v2_context_summary`。

### UC-204 钩子介入
- **触发**：`before_round` / 停止钩子 / 授权钩子配置存在时。
- **预期现象**：钩子可在轮次前注入提醒、在停止时做收尾；钩子失败按 fail-closed 策略阻断（见 UC-611）。
- **依据**：`_workflow_callbacks / _apply_stop_hooks / _authorize_hook_before_execute`。

### UC-205 插话（Steer）
- **触发**：任务运行中用户追加指令。
- **预期现象**：指令在安全点被吸收（"插话已受理"类反馈），任务按新指令调整；不需要重新开会话。
- **依据**：`enqueue_session_steer / _claim_session_steers / _consume_steer_messages`。

### UC-206 插话回滚
- **触发**：插话在工具执行中途到达。
- **预期现象**：部分轮次被干净回滚（未完成的工具调用不残留半成品），随后完整重跑当前轮。
- **依据**：`_rollback_steer_partial_turn`、`_runtime_v2_delete_unfinished_tool_events_after_marker`。

### UC-207 写栅栏
- **触发**：会话被中断/恢复时。
- **预期现象**：已提交的用户轮与答复不丢失、不重复；未提交的半截状态不写入历史。
- **依据**：`_state_run_has_write_fence`、`_RuntimeV2RunLifecycle`。

### UC-208 自动压缩触发
- **触发**：输入估算逼近上下文窗口（或达到压缩比例阈值）。
- **预期现象**：后台执行压缩（有进度提示），完成后继续对话；用户不需要手动操作。
- **依据**：`agent_loop.py` L4909 起（context policy 段）、`agent_memory.run_context_policy`。

### UC-209 超限强制恢复
- **触发**：模型返回上下文超限错误（CTX）。
- **预期现象**：自动进入"强制压缩 → 重试一次"的恢复路径；仍不行则明确报错（不静默死循环）。
- **依据**：`forced_context_limit_compress`、`_context_limit_recovery_window`。

### UC-210 错误分类（含原因链）
- **触发**：任意模型/网络错误。
- **预期现象**：错误卡分类为 NET / CTX / BUDGET / 429 / 5xx / 其他；文案给出可操作指引，不落"未知错误"。
- **依据**：`_classify_api_error / _classify_api_error_leaf`（保留 raise...from 原因链）。

### UC-211 断网等待
- **触发**：本机离线时发起请求。
- **预期现象**：不疯狂发请求；等待网络恢复后继续（与 UC-116 联动）；全程有状态提示。
- **依据**：`machine_network_available`、`_wait_for_local_network_recovery`。

### UC-212 会话标题生成
- **触发**：新会话首条消息后。
- **预期现象**：后台生成短标题（失败有兜底、不阻塞对话）；标题不出现本地路径/思考标签等脏内容。
- **依据**：`_generate_session_title_with_diagnostics / _fallback_session_title`。

### UC-213 计时与度量埋点
- **触发**：每轮 pre-API 与流式过程。
- **预期现象**：TTFT 与各阶段耗时进入日志/看板；对用户无可见打扰。
- **依据**：`_pre_api_timing_mark`、`_llm_stream_timing_log`。

### UC-214 恢复运行历史清理
- **触发**：加载含未闭合工具调用的历史（上次异常退出）。
- **预期现象**：不合法尾部被安全修剪；新 run 不被旧半截状态污染。
- **依据**：`_sanitize_loaded_histories_for_new_run`、`_truncate_unclosed_tool_call_tail`。

---

## 5. 工具系统（UC-3xx）

### UC-301 统一工具注册表
- **触发**：发起模型请求前。
- **预期现象**：内置 + 宿主 + 插件 + MCP 工具合并为一张表，"名字冲突"被拦截；插件/技能变更后工具表自动刷新。
- **依据**：`tool_registry.ToolRegistry`、`build_combined_tool_registry_for_session`。

### UC-302 工具行为旗标
- **触发**：工具执行调度。
- **预期现象**：只读工具可并行、写类工具串行；压力受限/可交互工具走特殊通道；与界面行为一致。
- **依据**：`ToolDescriptor`（parallel_safe / pressure_limited / interactive / 可中断性）。

### UC-303 审批闸口接入
- **触发**：写类/外网类工具调用。
- **预期现象**：按当前权限档位决定"直通 / 弹卡 / 自动复核"（详见 UC-7xx）；工具先显示"等待中"再出结果。
- **依据**：`tool_execution_policy.py` + 权限审批链路。

### UC-304 危险命令识别
- **触发**：`run_shell` 执行看起来危险或纯删除的命令。
- **预期现象**：命中危险模式时被拦或加注可操作提示；纯删除建议改用软删除。
- **依据**：`agent_tools._is_dangerous / _has_non_delete_dangerous_pattern`。

### UC-305 Agent 自保护
- **触发**：命令试图结束 Agent 自身进程/端口/生命周期脚本。
- **预期现象**：明确拒绝 + 指引（"用托盘/agentctl 重启"），不误杀、不把 Agent 弄崩。
- **依据**：`_agent_self_protection_reason / _agent_lifecycle_guidance`。

### UC-306 Shell 执行器
- **触发**：任何 `run_shell`。
- **预期现象**：本机默认 PowerShell；安装了 Git Bash 则识别；Windows 用作业对象收拢进程，取消时整棵进程树被杀；不留下孤儿进程。
- **依据**：`run_shell`、`_assign_windows_run_shell_job`、`_kill_process_tree`。

### UC-307 长脚本自动物化
- **触发**：`python -c` 超长内联脚本。
- **预期现象**：自动落盘为临时脚本再执行（避免命令行长度/转义问题），结束后清理。
- **依据**：`_maybe_materialize_python_c_script / _unlink_run_shell_temp`。

### UC-308 文件工具矩阵
- **触发**：read/write/edit/apply_patch 使用。
- **预期现象**：read 超长行有"虚拟化"提示；write 原子落盘；edit 允许模糊定位；apply_patch 解析失败时整体失败、不落半成品。
- **依据**：`read_file / write_file / edit_file / apply_patch`（含原子校验）。

### UC-309 提速类工具
- **触发**：大仓库里 glob / grep。
- **预期现象**：有 ripgrep / Windows 搜索索引时显著提速，没有则回退；结果有行数/字节上限保护。
- **依据**：`_grep_with_ripgrep`、`_glob_with_windows_index`。

### UC-310 Web 抓取防护
- **触发**：web_fetch / Web 搜索。
- **预期现象**：内网/畸形目标被拒（SSRF 防护）；重定向有上限；超长内容截断保留；代理可用。
- **依据**：`_url_safe_for_fetch / _safe_redirect_target / web_fetch`。

### UC-311 Web 下载
- **触发**：web_download。
- **预期现象**：默认落在工作区；同名自动去重；有字节上限；回执给出保存路径。
- **依据**：`web_download / resolve_default_download_path`。

### UC-312 软删除与护栏
- **触发**：delete_file。
- **预期现象**：移入 `.trash`（可回收）；`sessions/skills/.trash` 拒删；超 500MB 整体拒绝并提示手动清理。
- **依据**：`delete_file / _delete_path_prohibited_reason`。

### UC-313 结果脱敏与截断
- **触发**：工具结果进入上下文。
- **预期现象**：敏感资源路径/密钥类文本被打码；超长结果截断或转存临时文件并给引用。
- **依据**：`redact_sensitive_tool_text / _save_result_to_tempfile / _truncate_output`。

### UC-314 工具失败的真实性
- **触发**：工具执行失败但文件已部分改动。
- **预期现象**：如实报告（不虚构成功）；界面状态与真实落盘一致。
- **依据**：`_tool_result_status / _tool_result_indicates_failure`。

---

## 6. 工作区（UC-4xx）

### UC-401 虚拟路径模型
- **触发**：任何写类工具使用相对路径。
- **预期现象**：统一按"`/` = 工作区根"解析；界面/回执中出现的是工作区相对语义。
- **依据**：`prepare_agent_workspace_path_literal`、系统提示路径模型段。

### UC-402 越界审批
- **触发**：写类工具访问工作区外绝对路径（受限模式）。
- **预期现象**：弹审批卡片；批准后执行**并记住该目录**；拒绝则明确报错。
- **依据**：`session_authorized_dirs.add_authorized_dir`、审批卡片链路。

### UC-403 授权目录复用
- **触发**：同会话再次访问已批准目录。
- **预期现象**：不再弹卡，直接放行；授权记录在会话元数据中可查。
- **依据**：`get_authorized_dirs_for_session / is_path_authorized_for_session`。

### UC-404 回收站命名与容量
- **触发**：多次软删除同名文件 / 批量删除。
- **预期现象**：`.trash` 内带时间戳前缀不重名；超限拒绝（不部分移动）。
- **依据**：`delete_file` 实现、`TRASH_SIZE_WARN_MB`。

### UC-405 受保护区域
- **触发**：试图删 `sessions/`、`skills/`、`.trash/`。
- **预期现象**：拒绝并给出原因；无任何移动发生。
- **依据**：`_delete_path_prohibited_reason`。

### UC-406 临时文件生命周期
- **触发**：模型声明 `temporary=true`。
- **预期现象**：turn 末自动回收（移入 `.trash` 并告知数量）；全程不打扰。
- **依据**：`_cleanup_temporary_write_files`、工具描述契约。

### UC-407 上传与命名
- **触发**：界面上传文件。
- **预期现象**：安全文件名过滤、同名自动递增；超限给出明确错误；文件出现在工作区可见面。
- **依据**：`_safe_upload_filename / _dedupe_upload_path / _ChatUploadLimitError`。

### UC-408 浏览与可见性
- **触发**：打开工作区文件面板。
- **预期现象**：目录/文件列表带体积与行数；内部目录（.trash 等）按规则隐藏；越界路径不可见。
- **依据**：`_list_workspace_dir / _is_workspace_visible_dir`。

### UC-409 媒体与图片
- **触发**：浏览图片/在工作区查看媒体。
- **预期现象**：缩略图/元数据（尺寸）正常；SVG 有尺寸解析；大图不卡界面。
- **依据**：`_workspace_media_response / _svg_image_dimensions`。

### UC-410 打开协议与选择器
- **触发**：点击文件打开 / 使用路径选择器。
- **预期现象**：`sugaragent://` 协议打开；选择器可用（本机/工作区）。
- **依据**：`open_workspace_file`、`myagent_path_picker.js`、`api_pick_path`。

---

## 7. WebUI 对话界面（UC-5xx）

### UC-501 发送消息
- **触发**：输入并发送。
- **预期现象**：消息即时上屏；有发送管道锁，连点不重复提交；失败有明确错误与恢复入口。
- **依据**：`input-actions.js`、`acquireSendPipelineLock`。

### UC-502 中断与插话
- **触发**：运行中点"停止"或发插话。
- **预期现象**：停止让当前轮安全收尾；插话受理后任务调整（见 UC-205/206）；失败可恢复（recover_session_steer）。
- **依据**：WebUI steer API 组、`_SteerRunControl`。

### UC-503 平滑流式渲染
- **触发**：模型流式输出。
- **预期现象**：文字平滑滚动（非一坨弹出）；长回答顺滑；渲染与状态解耦（切会话不崩）。
- **依据**：`smooth-stream.js / message-rendering.js`。

### UC-504 滚动与目录
- **触发**：长会话滚动 / 打开 TOC。
- **预期现象**：滚动锚点稳定（回看不跳）；TOC/Todo 面板定位准确。
- **依据**：`session-scroll-history.js / toc-todo.js`。

### UC-505 断线续看
- **触发**：SSE 中断（网络闪断/后台休眠）。
- **预期现象**：自动续看（≤10 次、0.5s→15s 退避）；空闲 120s 有探测；恢复后**不丢事件、不重复**；彻底失败时提示刷新。
- **依据**：`sse-handling.js`（常量组）、`streamReconnect`。

### UC-506 会话管理
- **触发**：新建/切换/归档/删除会话。
- **预期现象**：列表即时更新；删除有确认；被删除会话的运行被安全中断。
- **依据**：`session-management.js`、sessions API。

### UC-507 子代理 Dock
- **触发**：任务派生子代理。
- **预期现象**：Dock 中可见任务状态/输出/耗时；可中断、删除、查看产物；切换子代理模型只影响该子代理。
- **依据**：`subagent-*`（10 个状态模块）、subagent API。

### UC-508 审批与提问卡片
- **触发**：工具需要审批 / 模型发起 ask_user。
- **预期现象**：卡片出现（含命令预览/分析入口）；提交后即执行；可取消；多个待办逐一处理不卡死。
- **依据**：`human-interactions.js`、approvals/interactions API。

### UC-509 模型档案面板
- **触发**：增删改/排序/启停档案、探测。
- **预期现象**：即时生效；探测失败有原因；排序决定候选链优先级。
- **依据**：`model-profiles.js`、model-profile API。

### UC-510 技能选取
- **触发**：输入区选择技能后发消息。
- **预期现象**：技能随消息注入（已选技能有效时）；不存在的技能名被忽略。
- **依据**：`skill-picker.js`、`_build_agent_message_with_selected_skills`。

### UC-511 工作区媒体展示
- **触发**：消息里的图片/文件引用。
- **预期现象**：图片内联渲染（可点开）；文件链接走打开协议；加载失败有兜底。
- **依据**：`workspace-media.js`、媒体 API。

### UC-512 通知与存在性
- **触发**：页面失焦 / 运行结束 / 需要人处理。
- **预期现象**：桌面通知按配置触发；无焦点时也不丢事件（presence 上报）；同 run 不重复轰炸。
- **依据**：`ui-presence`、通知优先级逻辑。

### UC-513 插件 UI 插槽
- **触发**：安装了带 UI 的插件。
- **预期现象**：面板/按钮按插槽规则出现；未启用插件不显示。
- **依据**：`plugin-ui-slots.js`、`plugins/ui.py`。

### UC-514 主界面恢复
- **触发**：刷新页面 / 应用重启后打开。
- **预期现象**：历史会话完整回放（含中断续跑入口）；孤儿运行被清理或提示。
- **依据**：`recover_interrupted_react_sessions`、`_cleanup_orphan_runtime_v2_active_runs`。

---

## 8. 能力扩展加载（UC-6xx）

### UC-601 插件加载
- **触发**：启动 / 安装插件后。
- **预期现象**：插件清单出现在扩展面板；启停状态持久；内置系统插件与用户插件区分展示。
- **依据**：`plugins/manager.py`、`load_plugins`。

### UC-602 热更新
- **触发**：修改插件/技能文件。
- **预期现象**：无需重启——签名变化触发后台重建；最多一轮请求后生效；失败不破坏现状。
- **依据**：`plugin_registry_signature`、`_schedule_hook_manager_rebuild`、SWR 逻辑。

### UC-603 安装与卸载
- **触发**：安装/卸载/安装依赖。
- **预期现象**：安装前有校验；卸载有回收区（`.myagent-trash`）；失败可回滚。
- **依据**：`plugins/installer.py`、`install_plugin* / uninstall_plugin`。

### UC-604 插件运行时
- **触发**：执行插件工具/命令/后台服务。
- **预期现象**：Node worker 运行；后台服务随开关启停；错误汇总可见、不拖垮主进程。
- **依据**：`plugins/runtime.py / worker_node.cjs`、`start_plugin_background_services`。

### UC-605 插件命令与 UI
- **触发**：使用插件声明的命令/按钮/面板。
- **预期现象**：命令目录可列举；声明式命令正确展开参数；UI 动作有反馈。
- **依据**：`dispatch_plugin_command / plugin_session_action`。

### UC-606 技能发现与启停
- **触发**：编辑 skills 目录 / 开关技能。
- **预期现象**：目录即发现（frontmatter 校验）；启停状态持久（skill_states.json）；坏技能被跳过并有提示。
- **依据**：`discover_skills / set_skill_enabled`。

### UC-607 技能激活
- **触发**：模型或用户激活某技能。
- **预期现象**：SKILL.md 正文与资源根注入当前对话；未启用技能不可激活。
- **依据**：`activate_skill`。

### UC-608 MCP 接入
- **触发**：配置 MCP 服务器（stdio / SSE / streamable-http）。
- **预期现象**：连接成功则工具入池；配置签名变化自动重连；断线有明确状态。
- **依据**：`agent_mcp.py`（三种连接器、_PersistentMcpServer）。

### UC-609 MCP 工具开关
- **触发**：对单个 MCP 工具启停。
- **预期现象**：即时生效（目录代际刷新）；禁用工具不再出现在模型工具表。
- **依据**：`set_mcp_tool_enabled / _bump_tool_catalog_generation`。

### UC-610 Hooks 装载
- **触发**：配置 hooks.json。
- **预期现象**：事件（如 PreToolUse）按 matcher 命中执行；windows/unix 命令按平台选择；超时生效。
- **依据**：`hooks.json.example`、`_build_hook_manager`。

### UC-611 钩子 fail-closed
- **触发**：命令型钩子失败/超时且 `failure_policy=block`。
- **预期现象**：操作被阻断（而不是放行）；审计里可见原因。
- **依据**：hooks 分发逻辑、`_audit_hook_dispatch_failure`。

### UC-612 扩展信任与审计
- **触发**：新插件/MCP 首次出现；信任/撤销操作。
- **预期现象**：未信任项有明确提示；信任后放行；撤销后回退；审计可查（开始/结果/失败）。
- **依据**：`security/extensions.py`、`_audit_hook_*`、`audit_plugin_inventory`。

---

## 9. 权限审批（UC-7xx）

### UC-701 三档模式
- **触发**：界面上切换"完全访问 / 请求批准 / 替我审批"。
- **预期现象**：切换即时生效并广播（permission_mode_changed）；不同模式的行为差异与文档一致（请求批准=弹卡，替我审批=LLM 复核后弹卡/放行，完全访问=直通）。
- **依据**：`security/models.py PermissionMode`、WebUI set_session_permissions。

### UC-702 全局默认与保留
- **触发**：重启应用。
- **预期现象**：上次的全局模式被保留恢复；`SECURITY_ENABLED=0` 时强制完全访问且隐藏选择器。
- **依据**：`security/store.py`、配置说明（webui config docs）。

### UC-703 工具能力分类
- **触发**：任意工具调用进入授权引擎前。
- **预期现象**：产出结构化 CapabilityRequest（effect/路径/域名等）；分类不改变工具本身行为。
- **依据**：`security/runtime.classify_tool`。

### UC-704 授权规则
- **触发**：用户添加"总是允许/拒绝"类规则。
- **预期现象**：规则即刻生效；会话级规则可清空；规则列表可查可删。
- **依据**：`add_permission_rule / list_permission_rules / clear_session_permission_rules`。

### UC-705 自动安全复核（替我审批）
- **触发**：该模式下有需授权操作。
- **预期现象**：LLM 复核给出结论（放行/拒绝/仍需人工）；复核过程与结论可见；复核失败时保守处理。
- **依据**：`security/reviewer.py`、`analyze_session_approval`。

### UC-706 审批等待与决议
- **触发**：弹卡后等待用户。
- **预期现象**：等待不占死资源（可被中断/批量拒绝）；决议落地即执行；同请求重复提交幂等。
- **依据**：`tool_approval_gate.py`。

### UC-707 审批卡片体验
- **触发**：待批列表。
- **预期现象**：卡片含命令预览、风险说明、分析入口；批准/拒绝后卡片状态更新；多个待办逐个处理不互相吞。
- **依据**：approvals API、`_tool_command_preview`。

### UC-708 ask_user 人工问答
- **触发**：模型发起 ask_user。
- **预期现象**：问题卡片出现（含选项）；回答回填后继续；长时间不答可取消；应用重启后未答问题可恢复。
- **依据**：`human_interaction/service.py`、interaction 恢复后台任务。

### UC-709 出口守卫
- **触发**：web_fetch 等外联工具。
- **预期现象**：目标域名不在预批准清单时按模式处理；预批准域名可在设置中维护；内网目标始终拒绝。
- **依据**：`security/egress_guard.py`、`web_preapproved.py`。

### UC-710 Shell 解析与沙箱
- **触发**：run_shell 经过授权引擎。
- **预期现象**：命令被分段分析（读/写/网络/危险），据此判定审批；沙箱画像健康状态可查。
- **依据**：`security/shell_analysis.py`、`SandboxProfile / SandboxHealth`。

### UC-711 批量拒绝
- **触发**：会话被中断/清理时有多个待批。
- **预期现象**：全部被标记拒绝（不悬挂）；相关工具调用以"用户未批准"收尾。
- **依据**：`reject_pending_approvals_for_sessions`。

### UC-712 完全访问直通
- **触发**：完全访问模式下写类/外网操作。
- **预期现象**：无弹卡直接执行；仍保留危险命令识别与自保护（安全底线不解除）。
- **依据**：授权引擎 + 工具系统 §UC-304/305。

---

## 10. 会话存储 Runtime V2（UC-8xx）

### UC-801 事件真源
- **触发**：每轮对话/工具执行。
- **预期现象**：所有状态以 events.jsonl 顺序事件落盘（含 seq）；断电重启后按事件重建一致状态。
- **依据**：`runtime_v2/event_log.py`。

### UC-802 读写互斥与损坏语义
- **触发**：并发写入 / 文件损坏。
- **预期现象**：Busy 超时有明确错误（可重试）；损坏有 CorruptionError 且**拒绝静默覆盖**；修复工具可处理。
- **依据**：`RuntimeEventLogBusyError / CorruptionError`、`repair.py`。

### UC-803 游标读取与回放
- **触发**：界面打开历史 / SSE 续看。
- **预期现象**：按游标增量读取，不重复不缺失；断线续看从上次游标继续。
- **依据**：`event_log`（游标读取）、`runtime_v2_session_stream`。

### UC-804 投影一致性
- **触发**：读取会话状态。
- **预期现象**：投影结果与事件序列一致；token 标记过期后按需重算；不出现"界面有、事件无"的幽灵状态。
- **依据**：`projector.py / _mark_context_tokens_stale`。

### UC-805 历史提交事务
- **触发**：用户轮、模型答复、历史替换。
- **预期现象**：原子提交；失败不落半截；与 ReAct 写栅栏联动（UC-207）。
- **依据**：`history_ops.py`（事务与替换）。

### UC-806 压缩结果的持久化
- **触发**：压缩完成（自动/强制）。
- **预期现象**：`context_summary_committed` 事件落库；重启后摘要不丢；UI 回放可见压缩过程（body/delta/progress）。
- **依据**：`commit_context_summary`、事件类型登记。

### UC-807 模型历史投影
- **触发**：下一轮组装请求。
- **预期现象**：投影出干净的模型消息序列（Responses 续接信息被剥离、DSML 修复痕迹不泄漏）。
- **依据**：`model_projection.py`。

### UC-808 快照加速
- **触发**：长会话读取。
- **预期现象**：快照命中则快速返回；失效自动重建；与真源不产生分歧。
- **依据**：`snapshot_store.py`。

### UC-809 扩展状态
- **触发**：插件写入会话级命名空间状态。
- **预期现象**：冲突有明确错误（compare-and-set 语义）；缺失可查；重启后保留。
- **依据**：`extension_state.py`。

### UC-810 运行注册与孤儿清理
- **触发**：异常退出后重启。
- **预期现象**：孤儿 run 被识别并清理（或提示）；界面不显示"永远运行中"的假状态。
- **依据**：`run_registry.py`、`_cleanup_orphan_runtime_v2_active_runs`。

### UC-811 v1→v2 迁移
- **触发**：打开旧格式会话。
- **预期现象**：自动/手动迁移且**校验通过才切换**；迁移失败保留旧数据可回退；迁移清单可查。
- **依据**：`migration.py`（VerificationError）、runtime sync worker。

### UC-812 镜像与兼容
- **触发**：仍被旧路径读取的数据。
- **预期现象**：镜像/双向映射保持旧接口可用；不产生重复账。
- **依据**：`mirror.py / legacy_compat.py`。

### UC-813 修复与日志压缩
- **触发**：子代理日志/根日志异常，或日志膨胀。
- **预期现象**：修复服务可纠正引用/顺序问题；压缩后语义不变、文件变小。
- **依据**：`repair.py / root_log_repair.py / log_compaction.py`。

---

## 11. 横切能力（UC-9xx）

### UC-901 压缩触发（自动）
- **触发**：上下文占比达到阈值（默认比例/窗口估算）。
- **预期现象**：无感后台压缩；界面出现阶段性提示（context_summary_progress），完成后对话继续。
- **依据**：`agent_memory._compress_ratio_reached / run_context_policy`。

### UC-902 压缩分阶执行
- **触发**：压缩启动。
- **预期现象**：先轻后重（微收缩 → 分阶段收缩 Phase D/E → 摘要轮）；任何一步完成后若已达标即停止；工具消息成对完整性受保护。
- **依据**：`_compress_unified_in_place / _apply_phase_d / _apply_phase_e / _micro_shrink_*`。

### UC-903 摘要生成与 key_context 更新
- **触发**：需要摘要轮的压缩。
- **预期现象**：执行端模型产出 `<recap>`+`<summary>`；写入 key_context 单一「## 上下文摘要」小节（更新制，不重复堆叠）。
- **依据**：`_compress_summary_round / _run_compress_executor_dialogue / _upsert_compress_summary_key_context`。

### UC-904 压缩兜底
- **触发**：摘要模型格式无效/调用失败。
- **预期现象**：重试一次 → 摘录兜底（excerpt fallback）；压缩仍完成但保真度降低有日志记录；不影响对话继续。
- **依据**：`_compress_executor_excerpt_fallback / compress_tail_fallback`。

### UC-905 手动压缩
- **触发**：用户或模型调用 `context_manage(mode="compact")` / 编辑 key_context 指令。
- **预期现象**：按需压缩或修改摘要；完成回执清晰；与自动压缩互斥（会话锁保护）。
- **依据**：`context_manage`、`run_edit_key_context_instruction`、`_run_context_policy_serialized`。

### UC-906 压缩告警（规范）
- **触发**：压缩启动/上下文满载。
- **预期现象**：🟡 按 AlertSpec 为 `CTX-COMPRESS / CTX-FULL`（含级别与合并键）；实现状态以实施记录为准。
- **依据**：`workspace/alert_spec_myagent/ALERT_SPEC.md`。

### UC-907 识图：请求投影
- **触发**：消息含图片（上传/工具截图）。
- **预期现象**：图片按需转 base64 data URL 发给支持视觉的模型；界面无感。
- **依据**：`attachments/content.py::project_request_images`。

### UC-908 识图：超预算卸载
- **触发**：图片体积/数量超请求预算。
- **预期现象**：自动卸载为文本引用（保留路径与说明），对话不因此失败。
- **依据**：`offload_request_images_with_policy`。

### UC-909 识图：工具图片并入
- **触发**：工具结果包含图片（如截图工具）。
- **预期现象**：并入后续消息（chat_tool_images 规则），模型可见；超限时同样有卸载策略。
- **依据**：`chat_tool_images`、`attachments` 投影链。

### UC-910 告警分级与合并
- **触发**：发生已实现告警（LLM-RETRY / LLM-BLOCKED-SWITCH / 网络恢复等）。
- **预期现象**：按 L0–L3 分级出现；同类告警按 coalesce_key **原地更新**而非刷屏；ephemeral 类不写历史。
- **依据**：`ALERT_SPEC.md`、`_emit_*_status` 系列、实施记录。

### UC-911 错误卡分类
- **触发**：任务失败。
- **预期现象**：错误卡给 NET / BUDGET / CTX / 429 / 502 / OTHER 分类与"下一步"建议；与告警配对（recovered 配平）。
- **依据**：错误分类器（agent_loop）+ WebUI 错误卡渲染。

### UC-912 观测与看板
- **触发**：任意运行。
- **预期现象**：TTFT/耗时/用量/心跳进入运行看板与日志；对对话零打扰；数据可导出（如需要）。
- **依据**：`runtime_observability.py / execution_metrics.py`。

---

## 12. 已知边界与设计取舍（BX 系列）

### BX-01 告警规范中的未实现项 🟡
- `LLM-HEDGE`（对冲提示）、`LLM-BUDGET`（预算将尽）、`CTX-FULL` 等仍在 `ALERT_SPEC.md` 规范阶段；当前不出现**不属于缺陷**。审查时请勿按"应有"验收。

### BX-02 WebUI 架构图为骨架版 ⚪
- 为满足 showcase 布局门禁，WebUI 图采用"7 节点主链骨架 + 卡片承载细节"；全要素展开版可作为迭代项。

### BX-03 非 Git 工作根的 shell 盲区 ⚪（改动审查插件）
- 详见《改动审查方案设计-UseCase清单.md》UC-104/106——是决策取舍，不是故障。

### BX-04 Responses 加密推理/压缩的兼容降级
- 加密推理块失效、compact 不被支持时走重放/降级路径；极端情况下多一次完整重发（表现为略慢）。

### BX-05 流式路径的已知限制
- 部分状态类消息（如缓冲态工具结果）在流式完成后以最终形态呈现；中间态文案不会全部单独出条。

### BX-06 预算/对冲参数可调 ⚪
- 重试次数、对冲阈值、预算与截止均可用环境变量调整；默认值见 UC-104~107；调小可省钱、调大可容错。

### BX-07 插件生态的行为边界
- 插件能力受宿主安全边界约束（工具执行策略 + 审批 + 审计）；未信任插件不发工具。

---

## 13. 审查指引与映射

**怎么审**：按编号逐条过——对每条确认「触发是不是这么做、现象是不是这样」。不符合的，把编号 + 实际现象反馈即可；我会逐条核对代码并修正（修正后在本文件标注版本）。

**证据映射（抽查用）**：

| 用例范围 | 首选核查点 |
|---|---|
| UC-1xx | `app/llm/`、`app/agent_openai.py`、`model_profiles.py`；清单 §1–§6 |
| UC-2xx | `agent_loop.py`（函数清单）、`agent_harness.py`；清单 §1–§9 |
| UC-3xx | `tool_registry.py`、`agent_tools.py`（函数清单）；清单 §1–§8 |
| UC-4xx | `session_authorized_dirs.py`、`agent_tools` 回收站段；清单 §1–§9 |
| UC-5xx | `frontend/src/**`、`webui.py` 路由段；清单 §1–§8 |
| UC-6xx | `agent_extensions.py`、`agent_mcp.py`、`plugins/**`、`hooks.json.example`；清单 §1–§8 |
| UC-7xx | `security/**`、`tool_approval_gate.py`；清单 §1–§11 |
| UC-8xx | `runtime_v2/**`（26 文件）、`webui.py`（V2 段）；清单 §1–§10 |
| UC-9xx | `agent_memory.py`（压缩）、`attachments/**`（识图）、`ALERT_SPEC.md`（告警） |
| 交付回执 | `workspace/archify_study/*/*.visual-check.json`、各模块 HTML（sha256 见总索引） |

**版本记录**：
- 2026-09-13 v1：首版（8 模块 + 横切；覆盖 HEAD `6acc6bf` + 未提交改动）。
