# 前端改动问题检查单

本文档用于排查近期围绕事件协议、DOM 渲染目标、运行状态生命周期、历史操作等改动可能引入的问题。

## A. 事件协议检查

- [ ] SSE 收到的事件都能被 `normalizeSsePayload()` 正确解析。
- [ ] Runtime V2 envelope 里的 `ui_event` 没有被误丢。
- [ ] `skip_ui` 只跳过真正不该渲染的事件。
- [ ] `seq`、`runtime_seq`、`_sseDedupeSeq` 没有混用。
- [ ] `session_id` 始终能落到正确会话。
- [ ] `final` 只渲染一次。
- [ ] `tool_call`、`tool_done`、`tool_command_delta` 没有被 final 后过滤逻辑吞掉。
- [ ] `run_started`、`run_finished`、`run_interrupted` 仍然会更新前端状态。
- [ ] 历史回放和实时 SSE 使用一致的 `eventIndex` 语义。
- [ ] 子 agent 事件不会被主 agent 的去重或过滤逻辑误处理。

## B. DOM 渲染目标检查

- [ ] 当前会话的消息只渲染到当前会话 chat stream。
- [ ] 切换会话后，旧请求返回不会继续写入当前会话 DOM。
- [ ] `ctx.stream` detached 后会被正确替换为当前可见 stream。
- [ ] DocumentFragment 回放时不会被强制改到可见 stream。
- [ ] 子 agent 的过程日志仍然进入子 agent 区域。
- [ ] 主 agent 的过程日志不会进入子 agent 区域。
- [ ] `process-aggregate` 不会空残留。
- [ ] `removeTemporaryStatus()` 不会删掉错误 process body 里的状态。
- [ ] `appendMessage()` 不会把消息 append 到错误容器。
- [ ] 历史加载 prepend/insert 时不会破坏滚动锚点。

## C. 运行状态生命周期检查

- [ ] `runCtx.runId` 每轮发送都会设置。
- [ ] `clearSessionRunStateIfMatch()` 不会因为 `runId` 缺失导致状态清不掉。
- [ ] 旧 run 的 `run_finished` 不会清掉新 run。
- [ ] 后端 `_state_run_is_current()` 不会误杀当前 run。
- [ ] 追问 restart 后，旧 stream 真的关闭。
- [ ] 新 run 能正常开始并显示用户消息。
- [ ] 发送按钮能在 `final` / `run_finished` 后恢复。
- [ ] 会话列表运行中状态能清掉。
- [ ] 断线重连不会重复 attach SSE。
- [ ] `stream_active` / `run_active` / 前端 run state 一致。

## D. 历史操作检查

- [ ] 删除 user 消息会从正确位置截断。
- [ ] 删除 assistant final 会截断到对应 user 前。
- [ ] 重写 user 消息会保留正确前文。
- [ ] 分支只能从 final 后创建。
- [ ] Runtime V2 历史带 `runtime_seq` 时，前端 `before_seq` / `after_seq` 传递正确。
- [ ] legacy 历史没有 `runtime_seq` 时仍可用旧下标逻辑。
- [ ] 加载更早历史后，已有消息不会重复。
- [ ] 历史裁剪后 token 估算、TOC、todo 会同步刷新。

## E. 会话加载与切换检查

- [ ] `/sessions/state` 失败时会保留当前会话列表。
- [ ] fallback `/sessions` 失败时不会把列表清空成空数组。
- [ ] 会话列表错误提示能在后续成功加载后清除。
- [ ] `loadSessionMessages()` 的旧请求不会覆盖新会话内容。
- [ ] 运行中切换会话再切回来，消息区、运行状态、按钮状态一致。
- [ ] 后台运行会话切回来后，final 和过程日志仍能补齐。

## F. 滚动与历史加载检查

- [ ] `saved-or-bottom` 模式会优先恢复保存的滚动位置。
- [ ] 加载更早历史时，滚动锚点不会跳动。
- [ ] 加载更早历史期间切换会话，不会把旧历史插入新会话。
- [ ] 缓存会话 stream 不会清理正在运行的会话。
- [ ] 离屏缓存数量超过限制时，能正常回收非运行会话。

## G. TOC / Todo / Token 检查

- [ ] 会话加载期间延迟 rebuild TOC 后，加载完成能补建。
- [ ] 切换会话后 TOC 不显示旧会话内容。
- [ ] todo plan 在 run 结束后刷新到当前会话。
- [ ] 运行中 token label 不会频繁请求服务端。
- [ ] run 结束后 token 估算能刷新为 Runtime V2 model projection 的结果。

## H. 工作区路径链接检查

- [ ] 自动识别的工作区路径可以正常打开。
- [ ] Markdown 工作区链接可以正常打开。
- [ ] 工作区图片链接仍能正常预览。
- [ ] tooltip 显示真实路径，不影响点击行为。
- [ ] 链接文本不会重复拼接尾部路径片段。

## I. 最小复现场景

- [ ] 普通新会话一问一答：用户消息、过程、final、按钮状态都正常。
- [ ] 带工具调用的一问一答：工具 pending、delta、done、final 都正常。
- [ ] 运行中切换会话：旧会话事件不会渲染到新会话。
- [ ] 运行中追问：旧 run 中断，新 run 启动，final 正常显示。
- [ ] 运行中断线或刷新：能恢复运行状态或正确清理。
- [ ] 删除消息：UI、Runtime V2 投影、上下文 token 一致。
- [ ] 重写消息：截断位置正确，新消息正常发送。
- [ ] 分支会话：从 assistant final 后分支，分支内容正确。
- [ ] 加载更早历史：消息不重复，滚动不跳。
- [ ] 子 agent 场景：主 agent 和子 agent 的过程区不串。

