# 上下文压缩全链路 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_memory.py`（主实现，`run_context_policy` L1677）、`agent_loop.py`（触发/调度 L4909–5217）、`agent_openai.compact_responses_history`（原生线）。
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
- **预期现象**：先轻后重逐阶执行——微收缩（micro shrink：工具消息成对保护）→ Phase D/E 分级收缩（保留近期、压缩远期）→ 摘要轮；任何一步达标即停。
- **规则与边界**：工具调用与结果的**成对完整性**受保护（不会压出"孤儿结果"）；未完成轮次不参与压缩。
- **依据**：`_compress_unified_in_place / _compress_entry_state / _apply_phase_d / _apply_phase_e / _micro_shrink_*`。

### UC-9A3 摘要生成与 key_context 更新
- **触发**：需要摘要轮。
- **预期现象**：执行端模型产出 `<recap>`+`<summary>`；写入 key_context 单一「## 上下文摘要」小节（更新制）。
- **依据**：`_compress_summary_round / _run_compress_executor_dialogue / _parse_compress_dialogue_output / _upsert_compress_summary_key_context`。

### UC-9A4 失败兜底
- **触发**：摘要模型格式无效/调用失败。
- **预期现象**：重试一次 → 摘录兜底（excerpt fallback）；压缩仍完成但保真度降低（有日志）；对话不中断。
- **依据**：`_compress_executor_excerpt_fallback / compress_tail_fallback`。

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

## 3. 边界

- 压缩**不改写已完成事件**：只替换"后续输入视图"；
- 进度/正文的 UI 呈现（context_summary_body/delta）见事件类型（../08/03）。

## 4. 依据映射

见上表（agent_memory.py 全函数清单已核对 60+ 函数）。

## 5. 版本记录

- 2026-09-13 v1：拆分首版（原 UC-901~905 合并成篇）。
