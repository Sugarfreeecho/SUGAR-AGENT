# 手动切换与兼容降级矩阵 · 功能方案设计（UseCase 清单）

- 版本：2026-09-18 v3（覆盖至：HEAD `1fd80ca` + 运行中切换一致性修复）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_harness.py`、`app/agent_subagent.py`、`app/agent_openai.py`（媒体/兼容降级）。
- 上级：`00-LLM接入整体设计.md`

---

## 1. 功能定位

用户主动换模型（含子代理），以及**降级矩阵**——媒体不支持、参数不支持时优雅退让。

## 2. UseCase

### UC-1E1 手动模型切换（主会话）
- **触发**：在右下角模型选择器切换到另一档案（运行中或空闲均可）。
- **预期现象**：会话绑定与「选择纪元」立即更新；**本 run 的模型熔断记录被清空**——同一 run 内曾失败过的目标档案会在下一次调用立即被重试（不再被"本轮运行跳过已失败模型"静默跳过）；进行中的请求不被打断，新档案自**下一次模型调用**起生效。
- **规则与边界**：不是"新建会话"；当前请求自然收尾（不重放已完成轮次与工具结果）；切换动作可连续操作，**以后者为准**（选择纪元守卫，见 UC-1E4）；选择器即时刷新，失败给出可见错误。
- **依据**：`webui.set_session_model_profile`、`agent_harness.reset_executor_failure_state_for_session`、`agent_harness.adopt_fallback_profile_for_session(expected_selection_id=…)`、`agent_loop`（每轮迭代解析 + 熔断跳过）。

### UC-1E2 子代理模型切换
- **触发**：① `task action=switch_model`；② 在子代理会话中操作右下角模型选择器（打开子代理会话 = 主对话区寻址，见 ../05-WebUI对话界面/04·UC-5D15）。
- **预期现象**：两条入口都只影响该子代理、主会话不变，并完整保留子代理身份（child ID、历史、worktree、任务归属）；切换记录写入 `model_switch_history`、父任务行同步、熔断清理、子代理收到状态事件：
  - ① **安全边界交接**（`handover=True`）：中断当前请求、保留持久断点，同一子代理以新档案续跑；任务行 `interrupting → continuation_queued`。
  - ② **下一次调用生效**（`handover=False`）：不打断当前请求，数据动作全保留，新档案自下一次模型调用起生效。
- **规则与边界**：**fork 冻结**——`resume=self` 引用式 fork 会冻结生成前缀时的请求配置（保证前缀回放格式一致、命中缓存）；显式切换时释放（`fork_model_runtime` 置空）使档案真正接管，不清则 fork 子代理会"切了不生效"；切换可连续操作，以后者为准（同 UC-1E1）。
- **依据**：`agent_subagent.py::switch_subagent_model_profile(handover=…)`、`webui.set_session_model_profile`（识别 `is_subagent` → 转交 `handover=False`）、`agent_harness.SessionManager.switch_subagent_model_profile`（记录 + 选择纪元 + 释放冻结）。

### UC-1E3 兼容与媒体降级矩阵
- **触发**：①端点不支持 `stream_options`；②模型不支持图片输入；③端点**拒绝**了媒体载荷。
- **预期现象**：
  - ①自动去参重发（用户无感）；
  - ②切换/起始前即识别，图片改为含附件 ID、规范尺寸和只读路径的确定性文字句柄，不生成请求图片缓存；
  - ③识别被拒模态并**回写档案**（后续不再踩），当轮按实际剩余模态降级。
- **规则与边界**：降级不静默丢弃用户内容；Core 历史中的图片引用不删除，换到支持图片的候选时会重新投影。不再自动注入“把图片交给 task”的强制委托，显式子代理传图仍支持。档案能力标记可在档案面板看到变化。
- **依据**：`agent_openai._is_stream_options_error`、`_strip_media_from_api_messages`、`_media_error_modalities`、`model_profiles.mark_profile_modalities_failed`、`attachments.content.project_request_images`。

### UC-1E4 运行中手动切换的一致性保护
- **触发**：运行中手动切换（主会话或子代理），与同 run 内的自动切换、迟到响应交错。
- **预期现象**：
  - **选择纪元**：每次手动切换写入新的 `model_profile_selection_id`；旧请求完成时的 fallback 接管若发现选择纪元已变化则放弃——不会把会话绑定改回旧档案；
  - **熔断代际**：切换清空本会话 live run 的熔断记录；切换前发起的请求即使随后失败，也不再把该档案写回熔断（失败代际校验）；
  - **scope 注册竞态**：清熔断与 run scope 注册在同一临界区结算，切换瞬间新注册的 run 不会被漏掉；
  - **配置缓存代际**：构建配置期间发生切换时不回写旧客户端（最多重试 3 次后走未缓存快照）。
- **规则与边界**：保护只作用于"手动切换立即生效"链路；自动 fallback 的熔断与粘性最近成功模型仍按 UC-1D1 工作（见 04）。
- **依据**：`agent_harness.py`（`model_profile_selection_id`、`_failure_state_generation`、`reset_executor_failure_state_for_session`、`_executor_config_generation`）、`tests/test_model_switch_circuit_reset.py`。

## 3. 边界

- "完全访问/请求批准"等权限模式与模型切换无关（属 ../07-权限审批）。
- 降级矩阵只处理**能力类**问题；网络类问题见 07。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-1E1 | `webui.set_session_model_profile`、`agent_harness`（选择纪元 / 熔断清理 / 配置缓存代际） |
| UC-1E2 | `agent_subagent.py::switch_subagent_model_profile(handover=…)`、`webui.py`（选择器路由） |
| UC-1E3 | `agent_openai.py` L1018–1424、`model_profiles.py` L1498+ |
| UC-1E4 | `agent_harness.py`（`model_profile_selection_id` / `_failure_state_generation` / `_executor_config_generation`）、`tests/test_model_switch_circuit_reset.py` |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（合并原媒体降级与兼容降级条目）。
- 2026-09-14 v2：按附件化实现修正图片降级语义，移除已删除的强制视觉委托描述。
- 2026-09-18 v3：运行中切换一致性修复。① UC-1E1 修正为"清熔断立即重试 + 下一次模型调用生效（不打断当前请求）"，并补选择纪元/失败代际/配置缓存代际保护；② UC-1E2 拆分为两条入口——`switch_model` 安全边界交接（`handover=True`）与选择器"下一次调用生效"（`handover=False`），补 fork 冻结释放与父任务行同步；③ 新增 UC-1E4。实现：`agent_harness.py`、`agent_subagent.py`、`webui.py`；回归 `tests/test_model_switch_circuit_reset.py` 等（全量 1623 passed）。
