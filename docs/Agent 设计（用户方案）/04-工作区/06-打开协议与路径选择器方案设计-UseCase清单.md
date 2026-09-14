# 打开协议与路径选择器 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `d022831`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/webui.py`（`open_workspace_file / _resolve_allowed_local_path / api_pick_path`）、`frontend/src/vendor/myagent_path_picker.js`、`app/path_picker_util.py`。
- 上级：`00-工作区整体设计.md`

---

## 1. 功能定位

从"聊天里的链接/路径"到"本机打开"的桥：受控的打开协议 + 路径选择器。

## 2. UseCase

### UC-4F1 工作区文件打开
- **触发**：点击回复里的工作区文件/图片引用。
- **预期现象**：文件被系统默认应用打开（或按类型预览）；非工作区目标被限制（按允许路径解析）。
- **规则与边界**：打开动作经过 `_resolve_allowed_local_path` 白名单解析——**不是**任意路径都能被打开；失败给出原因。
- **依据**：`open_workspace_file / _resolve_allowed_local_path`。

### UC-4F2 `sugaragent://` 打开协议
- **触发**：外部/界面使用 `sugaragent://` 链接。
- **预期现象**：协议被应用接管并解析为对应动作（打开文件/聚焦会话等，按协议实现）；非法参数被拒。
- **依据**：协议注册与解析实现（webui + 前端）。

### UC-4F3 路径选择器
- **触发**：界面上需要选路径（如选择目录）。
- **预期现象**：选择器可浏览本机并回填路径；与权限模型一致（选出的越界目录依旧按授权规则走）。
- **依据**：`myagent_path_picker.js`、`path_picker_util.py`、`api_pick_path`。

## 3. 边界

- 打开协议**不绕过**权限体系：打开≠授权写权限。
- 选择器仅解决"输入"问题；授权仍由 ../07 与 02 决定。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-4F1 | `webui.py` L1775–1862 |
| UC-4F2 | 协议实现（webui/前端） |
| UC-4F3 | `api_pick_path` L2459；vendor/path_picker_util |

## 5. 版本记录

- 2026-09-14 v2：修正 `api_pick_path` 行号（L2459）并更新版本线至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-410）。
