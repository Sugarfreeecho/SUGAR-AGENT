# 工具执行中收到 interrupt 追问：改为转入后台并立即续接新轮

日期：2026-11-10
涉及：`app/background_tools.py`（新增）、`app/agent_loop.py`、`app/runtime_v2/execution_journal.py`、`SPEC.md`、`tests/test_background_tools.py`（新增）、`tests/test_streamed_host_tool_execution.py`、`tests/test_agent_extensions_integration.py`、`tests/test_feature_flags.py`

## 1. 问题

`interrupt` 模式追问落在**工具执行阶段**时，原实现直接取消正在跑的工具：

- 只读工具（`read_file`/`grep`/`web_fetch` 等）在线程/HTTP 中途被取消，已收到的内容作废；
- 工具调用被写成「已被用户追问打断」，但外部副作用（请求、子进程、远端调用）是否停下并不确定；
- 用户的新问题必须等这一批工具收尾，无法真正“立即”开启下一轮。

## 2. 改后行为

工具**已开始执行且未完成**时收到 `interrupt` 追问：

1. 该调用转入后台继续执行，当前轮立即用追问开启下一轮模型请求（`_react_node_replanning` 原路径不变）；
2. 旧调用的模型侧收尾改为「已转入后台继续执行（用户追问优先开启新一轮）」，不再声称“已打断/已停止”；
3. 执行记录保持 `running`（abort 事件通过 `preserve_tool_call_ids` 跳过），后台完成时以同一 `tool_call_id`、同一 `process_group_id` 原位提交真实结果，UI 行从“执行中”变为“完成/失败”；
4. 结果同时写入会话目录的 `background_tool_results.json`，在**下一次模型请求前**以 `[后台工具已完成]` 系统条目回灌上下文（`claim_notes` → 注入 → 提交成功才消费）；
5. 会话空闲时完成的后台工具，等用户下一次发送时随首轮请求注入。

### 边界

| 情形 | 行为 |
|---|---|
| `ask_user` 等交互工具 | 保持原打断语义（不转后台，不能脱离前台等待回答） |
| `context_manage` / `request_restart` / `tool_call` | 保持原语义（历史/进程/桥接屏障） |
| `non_interruptible` 的串行写工具（`run_shell`、写文件等） | 保持原“延后到工具结束再应用追问”语义 |
| 模型正文/思考/参数仍在生成 | 完全不变，仍立即打断并以追问重启 |

### 隔离

后台执行使用 `ExecutionScope` 提供的开关式 `state`/`emit` 视图：未脱手前与正常运行完全一致；脱手后读写落到快照（`llm_history`/`work_messages`/`stream_events`/change-review 独立副本），且：

- 不再向新 run 的 SSE 推送事件；
- `_steer_requested` / `_state_interrupt_requested` 对后台状态恒为 False（新追问与“停止”都不会误杀旧工具）；
- 丢弃 `_steer_control` 引用，避免新 run 注册新控制后旧工具被判定为“陈旧运行”而自杀；
- 后台工具只跑完自身：不再审批、不再提问、不写模型历史。

## 3. 验证

- 新增 `tests/test_background_tools.py`（10 项）：作用域隔离、注记格式/截断、一次性领取与回滚、运行中调用不被领取清掉、abort 保留后台状态、`_await_steerable` 已开始→转后台、未开始→仍取消、后台状态忽略 steer/stop。
- `tests/test_execution_recovery.py`：52 项通过（1 项 `test_shell_timeout_keeps_stdout_and_stderr` 为本机 `python` 子进程输出捕获环境问题，与本次改动无关，改动前同样失败）。
- `tests/test_streamed_host_tool_execution.py`、`tests/test_agent_extensions_integration.py`（除既有 `"SessionEnd"` 引号断言）、`tests/test_human_interaction.py`（46 项）、`tests/test_feature_flags.py::test_tool_pending_switches_generated_draft_to_executing` 通过。
- `tests/test_agent_loop_runtime_v2.py` 58 项通过；同文件 4 项 `isolated_agent_loop_metrics` fixture 报 `runtime_observability` 写入已删除的临时目录，属既有测试隔离问题。
