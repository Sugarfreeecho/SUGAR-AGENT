# 上下文压缩全链路 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v2（覆盖至：当前工作区）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_memory.py`（本地压缩）、`app/history_context.py`（压缩归档与检索）、`app/agent_harness.py`（后台模型候选与流处理）、`app/agent_loop.py`（触发/调度与发送前校验）、`agent_openai.compact_responses_history`（原生线）。
- 上级：`00-横切能力整体设计.md`

---

## 1. 功能定位

"对话不爆"的完整机制：何时压、怎么压（分阶）、压出来的摘要去哪、失败了怎么办。

## 2. UseCase

### UC-9A1 自动触发
- **触发**：输入估算逼近上下文窗口，或达到压缩比例阈值（`_compress_ratio_reached`）。
- **预期现象**：无感后台压缩；界面出现阶段性进度提示（context_summary_progress）；完成后对话继续。
- **规则与边界**：与请求构建**互斥**（会话级 context policy 锁，30s 空闲超时）；跳过标记（`_compress_skip_next`）防止同轮反复压。
- **依据**：`agent_loop.py` L4909+、`_run_context_policy_serialized / _wait_context_policy_idle`。

### UC-9A2 分阶执行
- **触发**：压缩启动。
- **预期现象**：先轻后重逐阶执行——微收缩（micro shrink：工具消息成对保护）→ Phase D/E 分级收缩（保留近期、压缩远期）→ 摘要轮；任何一步达标即停。按用户轮切不出前缀时继续尝试按完整 ReAct 步切分，再无法切分才进入半窗截尾。
- **规则与边界**：截断点必须位于完整消息步边界，工具调用与结果的**成对完整性**受保护（不会压出"孤儿结果"）；未完成轮次不参与压缩；不得在 assistant tool call 与对应 tool result 之间落刀。
- **依据**：`_compress_unified_in_place / _compress_entry_state / _apply_phase_d / _apply_phase_e / _micro_shrink_*`。

### UC-9A3 摘要生成与 key_context 更新
- **触发**：需要摘要轮。
- **预期现象**：待压缩原文先写入不可变归档；执行端模型产出 `<recap>`+`<summary>`；通过结构及草稿态校验后写入 key_context 单一「## 上下文摘要」小节（更新制），并附归档引用。
- **规则与边界**：包含“草稿”“再想想”等未完成规划痕迹的结果不可提交为持久摘要；一次摘要轮的多个候选/重试复用同一份原文归档，不重复落盘。
- **依据**：`archive_messages / _compress_summary_round / _run_compress_executor_dialogue / _parse_compress_dialogue_output / _compress_dialogue_output_quality_error / _upsert_compress_summary_key_context`。

### UC-9A4 失败兜底
- **触发**：摘要模型格式无效/调用失败。
- **预期现象**：格式或质量无效时整体重试一次；连续两次仍无效，或所有候选调用均失败时，使用活跃摘录兜底；压缩仍完成且原文可按引用取回，对话不中断。
- **规则与边界**：活跃摘录完整保留可容纳的用户正文和助手正文；reasoning、工具调用、工具结果及系统消息改为稳定引用占位符。若仅正文已超过预算，整条正文改为引用，不从消息中间截出误导片段。
- **依据**：`history_context.active_excerpt / _compress_executor_excerpt_fallback / compress_tail_fallback`。

### UC-9A5 强制压缩（CTX 恢复联动）
- **触发**：模型返回上下文超限错误。
- **预期现象**：进入"强制压缩 → 重试一次"路径（与 ../02/07 UC-2G2 同一机制）；仍失败则明确报错。
- **依据**：`forced_context_limit_compress` 段。

### UC-9A6 手动压缩与编辑指令
- **触发**：`context_manage(mode="compact")` / 编辑 key_context 指令。
- **预期现象**：按需压缩/修改摘要；完成回执清晰；与自动路径同锁互斥。
- **依据**：`context_manage`、`run_edit_key_context_instruction`。

### UC-9A7 原生压缩优先（Responses 线）
- **触发**：原生线且端点支持。
- **预期现象**：走服务端 checkpoint（见 ../01-LLM接入/02）；本地压缩作为兜底不重复做同规模工作。
- **依据**：`compact_responses_history`、`_runtime_v2_commit_responses_compaction`。

### UC-9A8 后台摘要流与候选切换
- **触发**：本地摘要请求通过流式模型执行。
- **预期现象**：持续收到 reasoning 视为连接和生成仍有进展，继续等待；真正无事件/无字节的连接由传输层静默读取超时处理；流正常结束但没有可消费正文时，当前候选结果判为不可用并尝试下一候选。
- **规则与边界**：没有“reasoning 持续 60 秒即空流”的判断，也不把长思考等同故障；整次请求如需总时限，应使用独立、较长且可配置的请求上限。候选切换表示“本次任务结果不可用”，不表示模型服务永久不可用，也不永久修改会话选模。
- **依据**：`ExecutorLLMClient.complete_text / ExecutorLLMClient.stream`、后台文本请求的 EOF 校验与 transport read timeout。

### UC-9A9 压缩历史检索
- **触发**：模型需要核对已被压缩的细节，或用户明确要求跨会话回溯。
- **预期现象**：优先调用 `history_context(action="search", scope="current")` 搜索当前会话；默认只返回 `ref` 和清洗后的正文片段，拿到引用后用 `action="read"` 分页读取可读文本。只有明确需要跨会话时才使用 `scope="global"`；确需检查原文件时再显式传 `include_source=true`。
- **规则与边界**：默认隐藏时间戳、序号、schema、索引和内部元数据，并对同会话相同语义结果去重；`read` 的当前会话作用域不得越权读取其他会话；单页最多返回 50,000 字符；搜索与读取均为只读宿主工具。活跃摘要只负责提示线索，归档和事件流才是细节证据。
- **依据**：`app/history_context.py`、`agent_tools.history_context`、`builtin_host_tools._invoke_history_context`、`prompt.md`。

## 3. 事故问题与处理方法

| 问题 | 处理方法 |
|---|---|
| 压缩目标较深且摘要轮串行，主候选多次只有 reasoning，导致长时间等待 | reasoning 到达即视为活跃进展，不设 60 秒正文首字超时；仅传输完全静默时使用读取超时，或在 EOF 后判定是否有可消费正文。 |
| 备用候选返回非空正文，但缺少 `<recap>/<summary>` | 将其判为格式无效，整体摘要请求最多再执行一次；第二次仍无效则生成带归档引用的活跃摘录。 |
| 摘要格式正确但正文仍是“草稿/再想想”等规划态 | 在提交前增加内容质量校验；草稿态不得污染 key_context，按格式无效路径重试并最终摘录兜底。 |
| 仅按“用户轮”寻找前缀，在超长单轮历史中直接退化成半窗截尾 | 用户轮口径失败后继续按完整 ReAct 步寻找切点；所有截断均按消息步边界对齐。 |
| 截断切开 assistant tool call 与 tool result，形成孤儿 tool 并被供应商 400 拒绝 | 压缩端保护工具对；模型发送前只扫描本次实际出站消息并删除孤儿、重复、错配结果；确实发现脏数据时再修复和持久化底层历史。 |
| 兜底摘录丢失工具细节或因预算从正文中间截断 | 压缩前写不可变 JSONL 归档；摘录完整保留可容纳的用户/助手正文，其余改为 `history:` 引用；超预算正文整条引用化。 |
| 摘要中的引用无法直接找回原文 | 新增 `history_context`，支持当前会话/全局会话搜索、稳定引用读取和分页；默认仅返回清洗后的语义内容，确需原文件兜底时才以 `include_source=true` 返回路径。 |

## 4. 边界

- 压缩**不改写已完成事件**：只替换"后续输入视图"；
- `history_context_archives/*.jsonl` 是压缩原文的独立不可变副本，不替换 Runtime V2 事件流，也不是新的会话真相源；
- 候选调用失败（传输异常、对象非法、EOF 后正文为空）会在同一逻辑请求内尝试下一候选；正文存在但格式/质量无效则重启一次完整摘要请求，候选顺序从首选模型重新开始；
- 进度/正文的 UI 呈现（context_summary_body/delta）见事件类型（../08/03）。

## 5. 依据映射

见各用例“依据”；检索与摘录专项测试见 `tests/test_history_context.py`，压缩解析与归档引用测试见 `tests/test_agent_memory_compress_parse.py`。

## 6. 版本记录

- 2026-09-20 v2：补齐“轮→步”降级、工具对完整性、出站孤儿清理、草稿态校验、reasoning/静默/EOF 三种流语义，以及“活跃摘录 + 可检索归档 + history_context”方案。
- 2026-09-13 v1：拆分首版（原 UC-901~905 合并成篇）。
