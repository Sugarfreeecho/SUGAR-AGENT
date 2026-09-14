# 会话、档案与技能面板 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
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
- **依据**：`session-management.js`、sessions API、`recover_sessions`。

### UC-5F2 模型档案管理
- **触发**：新增/编辑/删除/排序/启停档案；发起探测。
- **预期现象**：保存立即生效（无需重启）；**排序 = 候选链优先级**（提示用户）；启停改变可用性；探测给出结论/原因。
- **依据**：`model-profiles.js`、`get/save/reorder/delete_model_profile`、`discover/probe`。

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

## 3. 边界

- 档案的**业务语义**（协议/能力/切换）见 ../01-LLM接入；
- 技能装载细节见 ../06-能力扩展加载/05。

## 4. 依据映射

见上表（webui 路由 + frontend 模块）。

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-509/506 与设置面板条目）。
