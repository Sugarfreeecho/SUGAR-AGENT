# 打开协议与路径选择器 · 功能方案设计（UseCase 清单）

- 版本：2026-10-17 v5（覆盖至：当前工作区；选择器单窗口兜底规则、STA 线程与超时口径）
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
- **规则与边界**：`IFileDialog.Show` 成功后，文件与 `FOS_PICKFOLDERS` 两种模式均用 `GetResult()` 读取确认结果。`GetFolder()` 不能作为确认结果的优先值或失败兜底：此前这条分支会把仍为默认目录的浏览位置提前返回，前端即使正确传递路径也无法生效。COM 调用使用原始有符号 HRESULT，先显式判断用户取消/失败。结果项的文件系统路径读不到时再取 `SIGDN_DESKTOPABSOLUTEPARSING`（仍是被确认的那一项，不是浏览位置）；仍失败则报 `PathPickerDialogError`——**不再换下一个后端弹第二种样式的选择框**。
- **规则与边界（2026-10-17 增补）**：`IFileDialog` 固定跑在一条独立的 STA 线程里（`_run_in_sta_thread`）。原因是 Web 侧用 `run_in_threadpool` 调用，线程池线程可能已被其它库初始化成 MTA，此时 `CoInitializeEx(COINIT_APARTMENTTHREADED)` 会返回 `RPC_E_CHANGED_MODE`（ctypes 的 OleDLL 直接抛 OSError）——旧实现因此放弃新版对话框、继续走 tkinter / PowerShell 兜底，用户看到"先在新版窗口里选一次、没有生效、又要在另一种样式的窗口里重选一次"。线程套间状态与请求落在哪条线程池线程无关后，窗口样式才稳定为一种。
- **依据**：`path_picker_util.py::_run_in_sta_thread / _pick_windows_ifiledialog_impl / _pick_windows_ifiledialog / pick_native_path`；[Microsoft GetResult](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-ifiledialog-getresult)、[GetFolder](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-ifiledialog-getfolder)；`tests/test_path_picker_platforms.py::test_windows_dialog_returns_confirmed_selection / test_windows_dialog_result_failure_is_terminal / test_sta_thread_reports_mta_thread_as_unavailable`。

### UC-4F5 会话目录选择的 API、取消与手填兜底

- **触发**：新建菜单或欢迎页请求选择会话目录；系统选择器不可用，或用户取消选择。
- **预期现象**：前端向 `POST /api/pick-path` 提交 `kind=directory / initial / multiple=false`；成功取得 `path` 后交给新会话目录链路。取消返回 `cancelled=true` 并保留原状态；选择器不可用时提供填写绝对路径的模态框。
- **规则与边界**：选出路径与创建会话是两次独立请求；选择器返回值不替代 `POST /sessions` 的目录校验。取消不能当成默认目录确认，选择新目录也不改变全局 `WORK_DIR` 设置；原生选择器初始目录跟随当前会话/草稿目录（见 04/01 · UC-4A8），会话目录失效时保留配置身份、不回落默认根。后端模块修改后须重启服务加载，前端模块修改后须构建并核对 dist。
- **兜底与超时（2026-10-17 增补）**：`pick_native_path` 只在"窗口根本没弹出来"（`PathPickerUnavailable` / `ImportError` / `FileNotFoundError`）时才换下一个后端；对话框一旦弹出过（成功、取消或 `PathPickerDialogError`）本次就结束，绝不级联到另一种样式的窗口。已经成功弹过窗的后端会被记住并在后续调用里优先使用，同一进程内不出现样式来回切换。同一时刻只允许一个选择框（并发请求直接返回"已有一个文件选择窗口正在等待操作"）。超时口径以"人在浏览目录"为准：客户端 `pickPath` 的 AbortController 由 50 s 放宽到 15 min，PowerShell 后端默认 600 s、STA 选择线程默认 1800 s（`MYAGENT_PATH_PICKER_TIMEOUT` / `MYAGENT_PATH_DIALOG_TIMEOUT` 可覆盖）——此前的 50 s 会让用户在系统窗口里选完却没有任何反应（看起来就是"选择无效"），紧接着又弹出手填兜底框。
- **依据**：`webui.py::api_pick_path / create_session`、`vendor/myagent_path_picker.js::pickPath`、`session-management.js::pickNewSessionWorkDir / promptNewSessionWorkDirFallback`、`path_picker_util.py::pick_native_path / _ordered_backends / _remember_backend`；`tests/test_path_picker_platforms.py::test_dialog_error_does_not_fall_back_to_another_picker / test_unavailable_backend_falls_through / test_concurrent_pick_is_rejected`；界面语义见 [05/06 · UC-5F11~5F13](../05-WebUI对话界面/06-会话档案与技能面板方案设计-UseCase清单.md)。

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

- Windows COM 回归通过真实 ctypes 绑定接入测试 vtable，分别提供不同的浏览目录与确认目录，覆盖目录、文件、取消及结果读取失败四种情形；结果读取失败按 `PathPickerDialogError` 收口（不再落到兜底链），其余三种保持原返回值语义。测试不弹出系统对话框。兜底规则另由后端注入式用例覆盖：`PathPickerDialogError` 不级联、`PathPickerUnavailable/ImportError/FileNotFoundError` 继续下一个后端并记住成功后端、并发请求被拒。
- 2026-10-07 将同一回归应用于旧实现，复现返回 `D:\projects\default-workspace`；修复后返回 `D:\projects\selected-child`。因此验证同时覆盖旧问题复现和修复结果。
- 前端页面与真实会话 API 联测的选择器返回值为模拟；实际用户点击系统文件夹对话框的手工结果尚未记录。手工验收步骤与完整链路证据见 [05/06 · §4.1](../05-WebUI对话界面/06-会话档案与技能面板方案设计-UseCase清单.md)。

## 5. 版本记录

- 2026-10-17 v5：选择器"只出一次窗口"——`IFileDialog` 固定跑独立 STA 线程（避开线程池 MTA 导致的 `RPC_E_CHANGED_MODE` 级联）、结果读不到时改用同一项的其他显示形式再兜、弹过窗就不再换后端、成功后端记忆、并发单飞、超时放宽到"人在浏览目录"的量级；手填兜底文案带上失败原因。回归：`tests/test_path_picker_platforms.py` 15 passed（含新增的级联/记忆/单飞/STA 用例），真实对话框探针在"调用线程已是 MTA"时仍返回一次新版窗口的确认结果。
- 2026-10-11 v4：原生选择器初始目录跟随当前会话/草稿；会话目录失效不回落默认根（配合 04/01 · UC-4A8 与 04/05 · UC-4E6）。
- 2026-10-07 v3：新增 UC-4F4~4F5，记录 `GetFolder` 错取浏览目录的根因、改用 `GetResult` 的确认结果契约、HRESULT 取消/失败处理、会话目录选择 API 与手填兜底；补录 COM 回归和人工验收边界。

- 2026-09-14 v2：修正 `api_pick_path` 行号（L2459）并更新版本线至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-410）。
