# 会话、档案与技能面板 · 功能方案设计（UseCase 清单）

- 版本：2026-10-03 v7（覆盖至：当前工作区；会话级推理强度与模型绑定跟随）
- 用途：逐条审查（四字段格式）。
- 适用实现：`modules/session-management.js`、`modules/model-profiles.js`、`modules/settings.js`、`modules/skill-picker.js`、`modules/i18n.js`、对应后端 API。
- 上级：`00-WebUI对话界面整体设计.md`

---

## 1. 功能定位

围绕对话的三个"管理面"：会话列表、模型档案、技能与设置（含 i18n/主题）。

## 2. UseCase

### UC-5F1 会话管理
- **触发**：新建/切换/归档/删除会话。
- **预期现象**：列表即时更新（含运行中标记/未读标记）；删除有确认且安全中断其运行；归档可恢复。
- **规则与边界**：改名/归档/置顶/待办的"提交后不回退"由快照版本协议保证——独立成篇，见 10·UC-5J1~5J6。
- **依据**：`session-management.js`、sessions API、`recover_sessions`。

### UC-5F2 模型档案管理
- **触发**：新增/编辑/删除/排序/启停档案；发起探测。
- **预期现象**：保存立即生效（无需重启）；**排序 = 候选链优先级**（提示用户）；启停改变可用性；探测给出结论/原因；高级配置可选择 system prompt 的 `auto / merge / preserve` 兼容策略。
- **规则与边界**：`auto` 对 Qwen Chat Completions 自动使用开头唯一 system；该选项只改变请求副本，不改写会话历史。完整语义见 `../01-LLM接入/09-SystemPrompt能力投影与Qwen兼容方案设计-UseCase清单.md`。
- **依据**：`model-profiles.js`、`app/templates/static/settings/sections_basic.js`、`get/save/reorder/delete_model_profile`、`discover/probe`。

### UC-5F3 技能面板
- **触发**：查看/开关技能。
- **预期现象**：技能列表与工作区 skills 目录同步（新技能自动出现）；开关状态持久（重启保持）；坏技能有提示。
- **依据**：`list_registered_skills / set_registered_skill_enabled`。

### UC-5F4 设置：i18n 与主题
- **触发**：切换语言 / 明暗主题。
- **预期现象**：界面文案与主题即时切换；设置持久化（下次启动保持）。
- **依据**：`i18n.js / settings.js`、前端样式变量。

### UC-5F5 扩展相关设置
- **触发**：查看扩展信任/启用状态（与 ../06 联动）。
- **预期现象**：设置页可看到扩展项与信任状态；变更即时反映到工具/面板可见性。
- **依据**：`get_security_extensions / trust_security_extension`。

### UC-5F6 对话区模型选择器（切换使用）
- **触发**：在右下角模型选择器点选档案。
- **预期现象**：选择器跟随**当前打开的会话**（含经寻址打开的子代理会话）；切换立即写会话绑定与选择纪元——**主会话**：清空本 run 熔断记录（同 run 内失败过的目标档案立即重试）、不打断当前请求、下一次模型调用生效；**子代理会话**：走子代理切换链路（数据动作全保留、不打断）。成功后选择器即时刷新；失败给出可见错误。
- **规则与边界**：连续切换以后者为准（选择纪元守卫）；档案排序仍是候选链优先级（见 UC-5F2）。语义细则见 ../01-LLM接入/05·UC-1E1/1E2/1E4。
- **依据**：`model-profiles.js`（`setCurrentSessionModelProfile` / `refreshModelProfileSelector`）、`session-management.js`（切会话刷新选择器）、`webui.set_session_model_profile`。

### UC-5F7 新会话预取与隐藏草稿
- **触发**：在无会话态点击"新会话"（含刷新后重新进入草稿态）。
- **预期现象**：点击即启动后台预取——服务端创建**隐藏草稿会话**（目录、元数据与索引照常落盘，但首条 user 事件落盘前不出现在会话列表）；发送首条消息时直接复用该草稿（预取失败或未完成则回退为发送时即时创建，路径永远可用）；首条真实 user 事件落盘即"转正"进入列表并广播状态；刷新后按**本标签页 `sessionStorage`** 记录复用同一草稿（旧版 `localStorage` 记录读取时自动迁移，避免多标签页把独立消息发给同一草稿）。
- **规则与边界**：草稿不进入侧栏、远程控制列表与导出；页面内重复点击"新会话"复用同一份预取；后台物化（目录预创建 + 元数据 + 索引）在用户输入首条消息之前完成，不占用发送等待；启动重建时若发现草稿已有已提交的首条 user 消息，自动修复元数据并转正（覆盖提交与转正之间的进程退出窗口）。
- **依据**：`session-management.js::ensurePrefetchedNewSession / prefetchNewSessionInner`（`PENDING_NEW_SESSION_KEY`，`sessionStorage` + 旧记录迁移）、`webui.py::create_session`（`prefetch=true`，不失效 `/sessions/state`）、`agent_harness.py::get_or_create_session(draft=…)` / `_first_committed_draft_user_event`（`metadata.draft`、首条 user 事件转正、列表过滤、启动重建修复）。

### UC-5F8 上下文探测失败原因透出

- **触发**：在「高级设置 → 模型配置」或首次配置向导点击「获取模型上下文」，探测未成功（鉴权被拒/模型不存在/端点不可达/400 无可解析窗口）。
- **预期现象**：状态栏显示真实原因——「上下文探测失败，已使用列表/默认窗口：HTTP 401 Unauthorized: {响应体片段}」；网络异常显示 `异常类名: 消息`；响应体折叠空白并截断 400 字符；响应非 JSON 时显示「HTTP <码>（响应无法解析为 JSON）」。服务端同落 `warning` 日志（`model=%s detail=%s`，不含 API Key）。成功或未发起探测时 `probe_error` 为空串，界面行为不变。
- **规则与边界**：只影响失败提示与日志，不改变探测本身（3M token 探针、8s 超时、从 400 报错提取窗口）与"探测结果只作建议、不自动改写档案"；原 `probe_context_window_from_error` 保留为兼容包装。
- **依据**：`model_profiles.py::probe_context_window_from_error_detail / probe_model_context（probe_error）`、`webui.py::probe_model_profile` 日志、`app/templates/static/settings/sections_basic.js / first_time_config.html` 状态栏（复用既有 i18n 规则）；回归 `tests/test_model_profiles.py`。

## 3. 边界
### UC-5F9 会话级推理强度与模型绑定跟随
- **触发**：在模型选择器调整推理强度（low/medium/high/xhigh/max）；或 fallback 接管改写了会话绑定。
- **预期现象**：强度随会话独立保存（新会话创建即带上、切换会话读取各自值）；请求按协议转换——Responses 原生 reasoning 字段、兼容接口保留 thinking 参数、Anthropic 自适应思考或受输出上限约束的思考预算（旧模型不支持的强度映射到支持值）。fallback 接管改写绑定后，服务端推送 `model_profile_bound`（ephemeral）轻量事件，选择器静默重取并跟随，不再依赖用户点开菜单才刷新。
- **规则与边界**：强度枚举以 `model_profiles.REASONING_EFFORTS` 为准；模型列表 30s TTL + 并发合并，打开菜单/改配置/发现新档案时强制更新；绑定通知只走当前事件流与重连快照、不进持久历史。
- **依据**：`model-profiles.js::noteModelBindingChanged`、`sse-handling.js`（model_profile_bound 分支）、`session-management.js`（新会话 reasoning_effort）、`agent_loop.py::_model_profile_bound_event`、`agent_harness.py`（reasoning extra body 语义）、`llm/transport.py::_apply_anthropic_reasoning`、`model_profiles.py::REASONING_EFFORTS`；回归 `tests/js/model_reasoning_effort_runtime.cjs`、`tests/test_anthropic_reasoning_controls.py`、`tests/test_model_settings_controls.py`。


- 档案的**业务语义**（协议/能力/切换）见 ../01-LLM接入；
- 技能装载细节见 ../06-能力扩展加载/05。

## 4. 依据映射

见上表（webui 路由 + frontend 模块）。

## 5. 版本记录

- 2026-10-03 v7：新增 UC-5F9《会话级推理强度与模型绑定跟随》——强度随会话独立保存并按三协议转换；fallback 接管后选择器即时跟随（`model_profile_bound`）；档案管理入口迁至设置中心 sections_basic。

- 2026-10-02 v6：新增 UC-5F8《上下文探测失败原因透出》——探测失败保留原始原因（HTTP 状态/响应体片段/异常文本），状态栏显示真实报错、服务端落 warning 日志；成功路径与探测语义不变。

- 2026-09-26 v5：新增 UC-5F7《新会话预取与隐藏草稿》——点"新会话"后台创建隐藏草稿（`metadata.draft`），发送时复用并在首条 user 事件"转正"；待用记录存每标签页 `sessionStorage`（旧 `localStorage` 迁移），失败回退即时创建；启动重建可修复已提交首条消息的草稿。
- 2026-09-20 v4：UC-5F1 补交叉引用——会话列表状态一致性契约（快照 `state_revision`、写入围栏、仅失败才回滚）见 10《会话列表状态一致性与快照版本》。
- 2026-09-13 v1：拆分首版（承接 UC-509/506 与设置面板条目）。
- 2026-09-18 v2：新增 UC-5F6（对话区模型选择器）——选择器跟随当前会话；主会话清熔断即时重试、子代理会话按数据动作切换（不打断，见 04·UC-5D15）。
- 2026-09-20 v3：UC-5F2 补入 system prompt `auto/merge/preserve` 档案设置及其“只投影请求、不改写历史”边界。
