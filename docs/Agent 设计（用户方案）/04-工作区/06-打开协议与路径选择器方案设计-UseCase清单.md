# 打开协议与路径选择器 · 功能方案设计（UseCase 清单）

- 版本：2026-10-07 v3（覆盖至：当前工作区；Windows 确认结果与会话目录选择）
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

### UC-4F4 Windows 返回确认选中的目录

- **触发**：Windows 原生文件夹选择器显示默认目录，用户单击一个子文件夹后直接确认；或导航到另一目录后确认。
- **预期现象**：返回用户确认选中的目录，而不是选择器的初始目录或浏览位置；用户取消则返回取消状态，已有草稿目录不变。
- **规则与边界**：`IFileDialog.Show` 成功后，文件与 `FOS_PICKFOLDERS` 两种模式均用 `GetResult()` 读取确认结果。`GetFolder()` 不能作为确认结果的优先值或失败兜底：此前这条分支会把仍为默认目录的浏览位置提前返回，前端即使正确传递路径也无法生效。COM 调用使用原始有符号 HRESULT，先显式判断用户取消/失败；取消不继续打开其他选择器，结果读取失败按后端兜底链处理。
- **依据**：`path_picker_util.py::_pick_windows_ifiledialog_impl / _pick_windows_ifiledialog / pick_native_path`；[Microsoft GetResult](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-ifiledialog-getresult)、[GetFolder](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-ifiledialog-getfolder)；`tests/test_path_picker_platforms.py::test_windows_dialog_returns_confirmed_selection`。

### UC-4F5 会话目录选择的 API、取消与手填兜底

- **触发**：新建菜单或欢迎页请求选择会话目录；系统选择器不可用，或用户取消选择。
- **预期现象**：前端向 `POST /api/pick-path` 提交 `kind=directory / initial / multiple=false`；成功取得 `path` 后交给新会话目录链路。取消返回 `cancelled=true` 并保留原状态；选择器不可用时提供填写绝对路径的模态框。
- **规则与边界**：选出路径与创建会话是两次独立请求；选择器返回值不替代 `POST /sessions` 的目录校验。取消不能当成默认目录确认，选择新目录也不改变全局 `WORK_DIR` 设置。后端模块修改后须重启服务加载，前端模块修改后须构建并核对 dist。
- **依据**：`webui.py::api_pick_path / create_session`、`vendor/myagent_path_picker.js::pickPath`、`session-management.js::pickNewSessionWorkDir / promptNewSessionWorkDirFallback`；界面语义见 [05/06 · UC-5F11~5F13](../05-WebUI对话界面/06-会话档案与技能面板方案设计-UseCase清单.md)。

## 3. 边界

- 打开协议**不绕过**权限体系：打开≠授权写权限。
- 选择器仅解决"输入"问题；授权仍由 ../07 与 02 决定。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-4F1 | `webui.py::open_workspace_file / _resolve_allowed_local_path` |
| UC-4F2 | 协议实现（webui/前端） |
| UC-4F3~4F5 | `webui.py::api_pick_path`、`vendor/myagent_path_picker.js::pickPath`、`path_picker_util.py::_pick_windows_ifiledialog_impl`、新会话目录选择入口 |

### 4.1 回归覆盖与验收边界

- Windows COM 回归通过真实 ctypes 绑定接入测试 vtable，分别提供不同的浏览目录与确认目录，覆盖目录、文件、取消及结果读取失败四种情形；测试不弹出系统对话框。
- 2026-10-07 将同一回归应用于旧实现，复现返回 `D:\projects\default-workspace`；修复后返回 `D:\projects\selected-child`。因此验证同时覆盖旧问题复现和修复结果。
- 前端页面与真实会话 API 联测的选择器返回值为模拟；实际用户点击系统文件夹对话框的手工结果尚未记录。手工验收步骤与完整链路证据见 [05/06 · §4.1](../05-WebUI对话界面/06-会话档案与技能面板方案设计-UseCase清单.md)。

## 5. 版本记录

- 2026-10-07 v3：新增 UC-4F4~4F5，记录 `GetFolder` 错取浏览目录的根因、改用 `GetResult` 的确认结果契约、HRESULT 取消/失败处理、会话目录选择 API 与手填兜底；补录 COM 回归和人工验收边界。

- 2026-09-14 v2：修正 `api_pick_path` 行号（L2459）并更新版本线至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-410）。
