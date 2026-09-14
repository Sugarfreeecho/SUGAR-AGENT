# 三档模式与预设 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `d022831`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`security/models.py`（PermissionMode 等）、`security/runtime.py`（presets）、`security/store.py`（全局持久化）。
- 上级：`00-权限审批整体设计.md`

---

## 1. 功能定位

"约束强度"的三个档位及其默认值管理：完全访问 / 请求批准 / 替我审批。

## 2. UseCase

### UC-7A1 三档模式行为
- **触发**：切换模式后执行写类/外网类操作。
- **预期现象**：
  - 请求批准（ask_for_approval）：可写工作区、网络需审批；外网/越界操作弹卡；
  - 替我审批（auto_review）：LLM 复核后自动放行/拒绝/转人工（见 04）；
  - 完全访问（full_access）：直通（保留危险识别与自保护底线）。
- **依据**：`PermissionMode`、`PERMISSION_PRESETS`、`permission_context_for_mode`。

### UC-7A2 全局默认与会话覆盖
- **触发**：设置全局模式；对某会话单独改模式。
- **预期现象**：新会话继承全局；会话覆盖只影响该会话；界面显示当前生效值。
- **依据**：`get/set_global_permission_mode`、`session_permission_mode / set_session_permission_mode`。

### UC-7A3 全局保留与恢复
- **触发**：重启应用。
- **预期现象**：上次全局模式被保留并恢复（带时间戳）；无记录时回落到默认（请求批准）。
- **依据**：`store.py`（permission_mode 键 + updated_at）。

### UC-7A4 SECURITY_ENABLED=0 强制完全访问
- **触发**：环境变量显式关闭安全体系。
- **预期现象**：强制完全访问、隐藏前端模式选择器；保存后立即生效（页面刷新后界面更新）。
- **规则与边界**：该开关用于特殊部署；关闭后审批/复核链路不再产生卡片。
- **依据**：`security_enabled()`、配置说明（webui config docs L6787）。

## 3. 边界

- 模式的"视觉效果"（徽标/选择器）见 ../05-WebUI对话界面/05；
- 工具级"总是询问"列表与模式叠加（见 02）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-7A1 | `security/models.py` L46–196、`runtime.py` L142 |
| UC-7A2 | `runtime.py` L166–201 |
| UC-7A3 | `store.py` L160–513 |
| UC-7A4 | `runtime.py` L129、webui 配置 |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-701/702）。
