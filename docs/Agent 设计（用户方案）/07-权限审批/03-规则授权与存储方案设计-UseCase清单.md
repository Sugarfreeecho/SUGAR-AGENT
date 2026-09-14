# 规则、授权与存储 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `d022831`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`security/store.py`（680 行）、`security/runtime.py`（规则 L819–960）、`security/web_preapproved.py`。
- 上级：`00-权限审批整体设计.md`

---

## 1. 功能定位

"记住你的决定"：权限规则、授权目录引用、审批记忆（grants）与全局设置。

## 2. UseCase

### UC-7C1 权限规则管理
- **触发**：添加/查看/删除规则（如"总是允许 web_fetch 到 X"）。
- **预期现象**：规则即刻参与决策；会话级规则可一键清空；列表可查（含创建时间）。
- **依据**：`add_permission_rule / list_permission_rules / delete_permission_rule / clear_session_permission_rules`。

### UC-7C2 审批记忆（grants）
- **触发**：用户批准某类操作后（模式允许"记住"时）。
- **预期现象**：同类操作不再重复弹卡（在有效范围内）；记忆在会话内生效；可被规则/清空操作覆盖。
- **依据**：`add_approval_grant`。

### UC-7C3 会话级存储隔离
- **触发**：跨会话。
- **预期现象**：会话级规则/记忆不跨会话（安全默认）；全局设置（模式）另行存放。
- **依据**：`store.py`（settings 与 per-session 划分）。

### UC-7C4 预批准域名清单
- **触发**：维护 web_fetch 预批准域名。
- **预期现象**：清单内域名按模式放行/少打扰；保存即时生效；格式错误被拒（域名归一）。
- **依据**：`web_fetch_preapproved_domains / set_web_fetch_preapproved_domains`、`web_preapproved.py`。

### UC-7C5 敏感数据安全
- **触发**：存储/读取决策数据。
- **预期现象**：存储原子写入、不外泄；导出/查看不包含密钥类信息。
- **依据**：`store.py`（原子 JSON/SQLite 写入段）。

## 3. 边界

- 工作区目录授权（authorized_dirs）的写入在 ../04-工作区/02，本篇只讲它与决策的**合并消费**。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-7C1/7C2 | `runtime.py` L819–960 |
| UC-7C3/7C5 | `store.py`（全） |
| UC-7C4 | `runtime.py` L877–900、`web_preapproved.py` |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-704/709 的清单部分）。
