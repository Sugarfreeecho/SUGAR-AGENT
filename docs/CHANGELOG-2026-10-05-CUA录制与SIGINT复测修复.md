# CUA 录制与 Windows SIGINT 复测修复

依据本次两份真机反馈，继续修复原任务。保留其他正在进行的仓库修改，没有重放用户的计算器/浏览器任务，没有修改 rec3/rec4 的契约来伪造历史坐标证据。

## 录制问题不是仅靠重载解决

复测使用的 MyAgent PID 20708 于 `2026-10-05T06:26:54Z` 启动；computer.py / computer_policy.py 的修改时间为 `04:01:13Z`。运行入口和 Python 路径也指向当前仓库。因此不能仅凭部分行为没有发生就判定 RecordingEvidence 未加载。

已经定位两个宿主问题：

1. **读取越过前面的控制/输入。** CUA 读取工具此前为 `early_stream_safe:true`，在模型流式输出时即可执行；start/stop/click 要等待完整调用批次。同批“start→get”可能实际先 get；“stop→start→get”可先 get 上一段状态。provider 的互斥锁只保证先到先执行，不能保证后来的读取不会先到。这也能解释“UIA 验证更新了、同批截图还是旧值”，现有证据不能直接把该现象判定为驱动渲染陈旧。
2. **重启后映射缓存丢失，写入条件静默短路。** 本轮最后一次带图窗口观察开始于 `06:25:29Z`，在上述重启之前。重启之后、rec3/rec4 录制期间仅有 tree-only 观察；新的 window_images 没有该窗口。原代码只有缓存命中才写契约，也没有提示缺少证据，所以 windows 保持空对象。这个现象不证明控制回执为空。

本次修复：

- Native/MCP 的所有 CUA 调用都关闭提前执行，并保持 `parallel_safe:false`。同一完整模型调用批次按顺序执行；独立 Agent 之间仍共享桌面。
- 活跃录制下，像素动作缺少宿主映射时先取精确窗口 image-only 截图，恢复固定驱动空间，再发一次输入并写合同。image-only 不更新 UIA token 缓存。取图失败则在输入前返回 `recording_coordinate_observation_failed`；不会默认把窗口置前。
- getter 检查 enabled、活跃目录、driver owner、已知动作后的 next_turn 下限；stop 后陈旧的 enabled 也检测。冲突返回 `recording_state_conflict` 和未知 live state，保留原读数与控制回执。
- 冲突检查覆盖整个 provider，映射也覆盖该驱动实际记录的其他 Agent 动作；录制启停仍由创建 Agent 控制。
- 状态 API 增加 `recording_evidence`，控制回执增加 `host_recording_evidence`，包含 `policy_revision:recording-evidence-v2`、control_tracked、acknowledged_enabled、owner 和 counter 下限。它们是本地控制证据，**不是缓存伪装的实时录制状态**。

正确顺序下，start 后即时 getter 正常返回当前 enabled/目录属于健康结果，不要求必定返回冲突码；只有实际读数矛盾才返回冲突。

## UIA 与截图的验证范围

`_verify` 明确输出 `evidence_scope:driver_predicates`、`visual_consistency:not_checked`。模型提示说明：关键显示值使用 `_verify` 加新截图，两通道不一致时继续观察；既不能自动相信 UIA，也不能把截图附件或截图 hash 当作 OCR/语义验证。`include_screenshot:true` 提供图像证据，并不自动比较图像中的数字。没有增加默认 OCR、自动输入重试或全局等待。

## Windows SIGINT

删除效果不可靠的 windows_interrupt.py 控制台辅助进程。新链路为：

1. 校验终端 shell 的 PID/创建时间，保存原有子进程目标；向该 PTY 写 Ctrl+C。
2. 最多等待两秒，检查新的私有 shell prompt 和前台就绪状态。
3. 若 shell 仍未就绪且有原有子进程，对这批受控子进程执行终止兜底，保留 PID/创建时间保护和错误证据。
4. 校验目标退出、shell 仍存活及新 prompt。回执用 `forced:true`、`pty_ctrl_c_then_terminate_owned_children` 区分强制终止，不能描述成程序处理了 SIGINT。

不会通过 signal 杀掉或重建 shell。无独立子进程的 PowerShell `Start-Sleep` 无法靠子进程终止链路取消：Ctrl+C 未确认时返回 `no_owned_child_processes`、`interruptVerified:false`，需要强制停止时显式 terminal_close。REPL 没有回到 shell 时，兜底可能结束该 REPL 程序；工具描述与模型提示已明确该语义。POSIX 路径保留原行为。

测试没有把 `interruptVerified:true` 弱化成“调用没报错”。持久终端隔离测试使用可独立终止的外部命令继续断言 shell 复用；另加真实 in-process 场景校验未知回执及 shell 保留。外部命令测试另有丢弃 Ctrl+C 的故障注入，只阻断控制字节，子进程、终止、退出等待和 shell 复用仍走真实 Windows PTY。

反馈中的 pywinpty teardown WinError 5 暂未在本次套件复现，未据此修改关闭逻辑。

## 验证与生效

- 主套件：**123 passed, 1 skipped**，涵盖 CUA、MCP/调用层、执行集成/API、真实 PTY、工具状态及工具检索策略。
- 最终 CUA 聚焦：**62 passed, 1 skipped**，包括真实 MCP CallToolResult 形状、重启后无缓存、跨 Agent 映射、取图失败不输入、旧目录/owner/counter 冲突和禁止读取抢跑。
- 终端/执行集成/前端聚焦：**34 passed**。外部 SIGINT 测试随后增加强制 Ctrl+C 丢弃用例，原路径与强制兜底路径单独复验 **2 passed**；均断言没有尾部完成标记，同一 shell PID 保持可复用。
- 实际 MCP 集成探针（独立进程、当前仓库代码）：Native/MCP 互斥选择 MCP，start→get→stop 正常，控制回执确实被保存，输出 recording-evidence-v2。探针未发桌面输入、未开启视频，结束后停止自身录制并关闭连接。映射写入的窗口输入仍用受控模拟结果验证，未宣称重新完成了计算器实机回放。

这些套件有重叠，数字不直接相加。

部署前检查包含归档的 400 个会话：运行 Agent 为 0、运行 job/terminal 为 0、读取错误为 0。通过现有托盘重载服务，监听 PID 从 20708 更新为 2656。实际 HTTP 返回 MCP ready、57 个工具，`recording_evidence.policy_revision=recording-evidence-v2`；重启后 control_tracked=false 是尚未开始新录制的正常初始值。所有本次实现文件的修改时间均早于新进程启动时间。浏览器授权仍为 allow_existing_profile=false；终端面板 HTTP 脚本与工作区哈希一致。

后续计算器实机复验可检查：新 start 回执 control_tracked=true；录制中做一次像素点击，合同 windows 中出现当前 pid:window_id；getter 正常返回当前录制，或在实际冲突时明确 unknown；同批 start/get 与 click/截图不再抢跑。Windows 外部命令的强制兜底应返回 forced=true 并保留原 shell；无子进程命令不能把 delivered 当成中断证明。
