# 2026-10-17 新建会话默认目录入口 + 欢迎页「选择」拆分 + 目录选择器单窗口修复

## 现象（用户反馈）

1. 「新建会话」右侧箭头菜单里缺少"在默认工作目录新建"的入口：草稿选了自定义目录后，只能靠主按钮（当前目录）或"新工作目录"（每次都要重选系统目录）绕回去。
2. 新会话草稿的欢迎页只有一个「选择 >」按钮：既不能直接挑"已经创建过的工作目录"，也不直观表示"下一步是系统文件夹对话框"。
3. 点击「选择」弹出"选择文件夹"窗口后，**有时会出现另一种样式的选择文件夹窗口、选择无效要在第二个窗口里重选一次，甚至第三种样式的窗口**（一开始被当成"错误提示弹窗"）。

## 根因（复现与定位）

### 3.1 三种样式的窗口来自后端的兜底级联

`pick_native_path` 在 Windows 上的兜底链是 `windows-ifiledialog → tkinter → windows-powershell`：

- `IFileDialog` 必须在 STA 套间创建，但 Web 侧是 `run_in_threadpool(pick_native_path, …)` 调用。线程池线程一旦被其它库初始化成 MTA，`ole32.CoInitializeEx(None, 0x2)` 会返回 `RPC_E_CHANGED_MODE`（`ctypes.OleDLL` 直接抛 `OSError`），于是"新版对话框"这一档直接算失败 → 继续兜底。
- 本机运行时装的是精简 Python：`import tkinter` → `ModuleNotFoundError`（实测 `python\python.exe` 与系统 `python` 都没有 tcl/tk），所以第二档不会弹窗。
- 第三档 PowerShell `System.Windows.Forms.FolderBrowserDialog` 是另一种样式（旧式树形选择框）——这就是"另一种形式的窗口，要在里面重新选一次"。
- 结果读取失败（`GetResult` 失败 / 选择项读不出文件系统路径）此前也按"兜底链"处理（旧文档 UC-4F4 明确如此），用户已经选过的窗口被关掉、再弹一个新样式的窗口。

用真实 COM 绑定做的探针（`workspace/目录选择器诊断_20261017/evidence/probe_picker.py`，脚本自动按 OK/关闭，不需要人工点击）证实了这一点：

| 场景 | 修复前 | 修复后 |
| --- | --- | --- |
| 普通线程调用 | 返回确认目录 | 返回确认目录 |
| 调用线程**已是 MTA** | `OSError: [WinError -2147417850]` → 级联到旧样式窗口 | 仍然只弹一次新版窗口并返回确认目录 |

对运行中的服务（`:8192`）连续 6 次 `POST /api/pick-path` 全部落在"干净"的线程池线程上，所以现象是**时有时无**（`workspace/目录选择器诊断_20261017/evidence/probe_app_picker.py`：每次只出现一个 `DUIViewWndClassName` 新版窗口）。这也解释了为什么手动测试很难稳定复现。

### 3.2 "选择无效"还有一条独立成因：客户端 50 s 超时

`myagent_path_picker.js::pickPath` 用 `AbortController` + 50 s 定时器兜底。在系统窗口里翻目录超过 50 s（很常见）时请求已被前端 abort，用户随后点"选择文件夹"没有任何反应；紧随其后的是 `promptNewSessionWorkDirFallback` 的手填路径模态框——同一件事的第二、第三种窗口。

## 变更

### 前端

- `frontend/index.html`、`frontend/src/shell-body.html`（两份外壳同步）：`#new-session-menu` 增加第三项，顺序为
  `在当前工作目录新建会话` → **`在默认工作目录新建对话`** → `在新工作目录新建会话`；菜单与箭头的 `aria-label` 同步为三项描述。
- `session-management.js`
  - 新增 `startNewSessionInDefaultDir()`：`startNewSessionInDir('')`，即 `POST /sessions` 不带 `work_dir`（服务端全局默认目录）。**主按钮 `startNewSessionInCurrentDir` 与既有会话创建链路未改动**，`bindNewSessionMenuOnce` 只是按 `data-new-session-scope` 多分一支。
  - 欢迎页卡片改为两个按钮：
    - `renderWelcomeSessionDirectoryMenu()`：下拉列出"已经创建过的工作目录"——默认工作目录（`''` = 服务端默认）+ 各会话的 `work_dir`（`work_dir_label` 优先、否则取末级目录名），默认组固定第一、其余按最近活动倒序，当前生效项打勾（`aria-checked`/`is-active`）。
    - `bindWelcomeSessionDirectoryCard()`：卡片每次重建后重新接线（通用 `.sidebar-popup` 弹出层：Esc 关闭并归还焦点、↑↓/Home/End 走查、点外部关闭）。
    - 文件夹图标按钮沿用原「选择 >」的系统对话框链路（`pickNewSessionWorkDir`），点击期间禁用，失败时把原因带进手填兜底文案。
  - i18n 词条与动态兜底文案的英文映射。
- `message-rendering.js`：`WELCOME_HTML` 里「选择 >」拆成「选择 ▾」+ 文件夹图标两个按钮，`syncWelcomeSessionDirectory` 末尾调用 `bindWelcomeSessionDirectoryCard`。
- `styles/app.css`：`.welcome-session-directory-actions / -browse` 与下拉条目（两行：目录名 + 绝对路径，当前项打勾）样式，沿用浮层主题令牌。
- `vendor/myagent_path_picker.js`（+ `app/templates/static/` 同款副本）：`pickPath` 的客户端超时 50 s → 15 min，只保留安全网，取消由用户关闭系统窗口表达。

### 后端

- `app/path_picker_util.py`
  - 新增 `_run_in_sta_thread()`：`IFileDialog` 固定跑在一条新 STA 线程里，与调用线程的套间状态解耦；`CoInitializeEx` 的 `RPC_E_CHANGED_MODE` 显式识别（`_is_com_mode_conflict`），隐藏宿主窗口在收尾时销毁。
  - 新增 `PathPickerUnavailable`（窗口没弹出来，可以换后端）与 `PathPickerDialogError`（弹过了，不能再换样式）两个语义化异常。
  - `pick_native_path` 只对"没弹过窗"的失败继续兜底；弹过的对话框（成功 / 取消 / 结果读取失败）就是最终结果。成功/取消过的后端会被记住（`_remember_backend` / `_ordered_backends`），同一进程内不再切换窗口样式；同一个时刻只允许一个选择框（`_pick_lock`，并发直接提示"已有一个文件选择窗口正在等待操作"）。
  - 结果读取：`SIGDN_FILESYSPATH` 失败时再取同一项的 `SIGDN_DESKTOPABSOLUTEPARSING`，仍然读不到才报 `PathPickerDialogError`。
  - 超时口径按"人在浏览目录"调整：PowerShell 后端 45 s → 600 s（`MYAGENT_PATH_PICKER_TIMEOUT`），STA 选择线程 1800 s（`MYAGENT_PATH_DIALOG_TIMEOUT`）。
- `app/templates/dist/`：`npm run build` 重新生成（`main-DehIH7H5.js` / `main-CsOwKjHJ.css`）。

## 测试与验证

- `tests/test_path_picker_platforms.py`：15 passed。新增/改写用例——结果读取失败 → `PathPickerDialogError` 且**不**再调用下一个后端；`PathPickerUnavailable / ImportError / FileNotFoundError` 继续兜底并记住成功后端（`_ordered_backends()` 把它排第一）；全部不可用时报安装提示；并发请求被拒且不残留锁；`_run_in_sta_thread` 正常回传值/异常，MTA 线程被判为 `PathPickerUnavailable`。
- `tests/js/new_session_lifecycle_runtime.cjs`：新增"欢迎页文件夹按钮"与"下拉选项"两条链路的断言（含切回默认目录后 `POST /sessions` 不再携带 `work_dir`），通过。
- 真实对话框探针（`workspace/目录选择器诊断_20261017/evidence/probe_picker2.py`）：普通线程与"调用线程已是 MTA"两种情形都只弹一次新版窗口并返回确认目录。
- Playwright 实机联测（`workspace/目录选择器诊断_20261017/evidence/ui_smoke.py`，headless Edge + 拦截 `POST /api/pick-path`，结束时删除测试产生的草稿会话）：菜单三项顺序与文案、卡片两个按钮、下拉条目（默认 + 已创建目录，当前项 `aria-checked=true`）、选中后卡片更新、文件夹按钮发出 `POST /api/pick-path` 并回填、菜单"在默认工作目录新建对话"把卡片切回默认目录，`pageerror` 为 0。
- `npm run build` 成功；`scripts/check_frontend_dist_sync.py`：dist 与源码同步。
- 定向后端回归：`test_path_picker_platforms / test_feature_flags / test_frontend_theme_variants / test_floating_surface_theme_contract / test_workspace_file_picker_theme / test_session_action_menu / test_frontend_session_stream_runtime / test_settings_center` → 除 `test_session_workspace_paths.py::test_normal_mcp_arguments_receive_custom_root`（`app/agent_mcp.py` 既有未提交改动导致，与本次无关）外全部通过。

## 行为边界

- 后端 `path_picker_util.py` 需要**重启服务**才生效；前端改动已构建进 `app/templates/dist`，刷新页面即可。
- 「在默认工作目录新建对话」只作用于新会话：不改写已有会话目录，也不改全局 `WORK_DIR` 设置。
- 欢迎页下拉里的"默认工作目录"等价于把目标目录置空（服务端默认），与主按钮/"当前工作目录"不是同一个入口；后者仍取当前打开会话的 `work_dir`。

## 文件

- 后端：`app/path_picker_util.py`
- 前端：`frontend/index.html`、`frontend/src/shell-body.html`、`frontend/src/app/modules/session-management.js`、`frontend/src/app/modules/message-rendering.js`、`frontend/src/app/modules/i18n.js`、`frontend/src/styles/app.css`、`frontend/src/vendor/myagent_path_picker.js`、`app/templates/static/myagent_path_picker.js`
- 测试：`tests/test_path_picker_platforms.py`、`tests/js/new_session_lifecycle_runtime.cjs`
- 构建产物：`app/templates/dist/`
- 文档：`docs/Agent 设计（用户方案）/04-工作区/06-打开协议与路径选择器方案设计-UseCase清单.md`（v5）、`docs/Agent 设计（用户方案）/05-WebUI对话界面/06-会话档案与技能面板方案设计-UseCase清单.md`（v16）、`docs/Agent 设计（用户方案）/05-WebUI对话界面/WebUI能力清单.md`（v42）
- 诊断与验证脚手架与截图：`workspace/目录选择器诊断_20261017/evidence/`（`probe_picker.py` COM 单例探针、`probe_picker2.py` 普通线程/MTA 对照、`probe_app_picker.py` 运行中服务的 `pick-path` 探针、`ui_smoke.py` Playwright 联测、`ui_shot.py` 截图脚本，`shot_*.png` 为界面截图）
