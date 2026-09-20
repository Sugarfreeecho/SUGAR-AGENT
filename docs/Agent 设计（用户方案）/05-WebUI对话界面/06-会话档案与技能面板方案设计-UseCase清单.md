# 会话、档案与技能面板 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v4（覆盖至：当前工作区；含快照版本与写入围栏交叉引用）
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
- **依据**：`model-profiles.js`、`advance_config.html`、`get/save/reorder/delete_model_profile`、`discover/probe`。

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

## 3. 边界

- 档案的**业务语义**（协议/能力/切换）见 ../01-LLM接入；
- 技能装载细节见 ../06-能力扩展加载/05。

## 4. 依据映射

见上表（webui 路由 + frontend 模块）。

## 5. 版本记录

- 2026-09-20 v4：UC-5F1 补交叉引用——会话列表状态一致性契约（快照 `state_revision`、写入围栏、仅失败才回滚）见 10《会话列表状态一致性与快照版本》。
- 2026-09-13 v1：拆分首版（承接 UC-509/506 与设置面板条目）。
- 2026-09-18 v2：新增 UC-5F6（对话区模型选择器）——选择器跟随当前会话；主会话清熔断即时重试、子代理会话按数据动作切换（不打断，见 04·UC-5D15）。
- 2026-09-20 v3：UC-5F2 补入 system prompt `auto/merge/preserve` 档案设置及其“只投影请求、不改写历史”边界。
