# 启动与进程卫生 · 功能方案设计（UseCase 清单）

- 版本：2026-10-05 v2（覆盖至：当前工作区；活动时间口径与执行面板初始化幂等）
- 用途：逐条审查（四字段格式）；核对"启动依赖自检、子进程控制台窗口统一收敛、根目录状态文件迁移"三类进程/启动卫生机制的对外行为与边界。
- 适用实现：`app/check_requirements.py`、`RUN.bat` / `RUN.sh`、`app/proc_flags.py`、`scripts/audit_subprocess_flags.py`、`app/platform_lifecycle.py`、`app/tray_launcher.py` 及全仓派生点（`agent_tools` / `agent_subagent` / `runtime_observability` / `agent_updater` / `desktop_notify` / `path_picker_util` / `hooks/executor` / `security/egress_guard` / `plugins/installer` / `plugins/runtime` / `plugins/change-review/store`）、`.gitignore`、`pytest.ini`。
- 上级：`00-横切能力整体设计.md`｜相关：`05-WebUI对话界面/07-通知存在性与恢复方案设计-UseCase清单.md`（托盘启动链）、`06-能力扩展加载/05-Skills发现与激活方案设计-UseCase清单.md`（技能状态路径）、`../06-能力扩展加载/06-MCP接入与工具池方案设计-UseCase清单.md`（MCP 工具状态路径）。

---

## 1. 功能定位

三条"启动前后不打扰"的横切约定：**依赖自检**（每次启动真实校验解释器环境，不再依赖会随拷贝传播的标记文件）、**进程卫生**（无控制台形态下派生子进程不再闪出黑框，统一经一套 helper）、**状态目录**（运行时状态与临时产物统一收进 `.sugaragent/`，根目录只留源码/配置/脚本）。

## 2. UseCase

### UC-9E1 启动依赖自检与补装
- **触发**：通过 `RUN.bat` / `RUN.sh` 启动 Agent（含新电脑、整包拷贝到其他目录/机器）。
- **预期现象**：每次启动**真实校验当前解释器环境**（不再用 `app/.requirements.installed` 标记文件做字节比对跳过）——`check_requirements.py` 以 `importlib.metadata` 单进程快检（PEP 503 归一化名称 + 完整版本约束，含上下界/排除/兼容约束），成功静默（实测约 2.3s）；缺失或版本不满足即 `pip install -r requirements.txt` 并在安装后复核一次；复核仍缺则明确报错退出（exit 1）。`.requirements.installed` 仅在安装成功后写回作记录，不再具备跳过效力。
- **规则与边界**：缺少 `packaging` 的全新环境给出明确提示；旧实现（每包一个 `pip show` 子进程，>300s 超时）弃用。附注：`pymupdf/orjson/pandas/tokenizers/matplotlib/tiktoken` 的固定版本在 Python 3.13/3.14 无 wheel，新电脑建议 3.10–3.12。
- **依据**：`app/check_requirements.py`、`RUN.bat`、`RUN.sh`；回归 `tests/test_check_requirements.py`（14 例）。

### UC-9E2 隐藏子进程控制台窗口（统一收敛）
- **触发**：后端运行在无控制台形态（`pythonw` / `DETACHED_PROCESS` / 托盘静默启动）下派生子进程（`git`/`cmd`/`powershell`/`taskkill`/`pip` 等）。
- **预期现象**：不再新建可见控制台窗口（实测：无标志会新建终端宿主窗口，加标志为 0）。全仓派生点统一经 `app/proc_flags.py`：`NO_WINDOW` / `NEW_PROCESS_GROUP` 常量、`hidden_flags()`、`console_attached()`、`inherit_or_hide_flags()`；非 Windows 全部取 0 可无脑使用。`platform_lifecycle.py` 启动 `RUN.bat` 改为**自适应**：调用方有控制台则继承（照旧可见），无控制台才隐藏并把输出追加到 `logs/launcher_console.log`、stdin 指向 `DEVNULL`（避免隐藏后 `pause`/`input` 挂住进程）。
- **规则与边界**：`scripts/audit_subprocess_flags.py` AST 巡检 `app/`、`plugins/` 派生点是否声明 `creationflags`（豁免项集中在 `ALLOWED` 表并注明原因：macOS/Linux 分支、`**kwargs` 构造、自带可见控制台、有意 `CREATE_NEW_CONSOLE` 等）；未覆盖点非零即退出 1。托盘正常启动的会话里多数派生点本是空转，真实收益在"无控制台调用方"（托盘/更新/`agentctl`/WebUI 重启链路）。改动需**重启 Agent** 生效。
- **依据**：`app/proc_flags.py`、`scripts/audit_subprocess_flags.py`、各派生点（见适用实现）；回归 `tests/test_proc_flags.py`（含巡检脚本回归）、`tests/test_change_review_plugin.py`（`.git` 祖先探测快路径）。

### UC-9E3 根目录状态/临时文件迁移（.sugaragent）
- **触发**：技能启停、MCP 工具启停、pytest 运行、Playwright MCP 输出等状态读写；MCP 服务器配置与模型档案读写。
- **预期现象**：默认路径统一为 `.sugaragent/` 下——`skill_states.json`、`mcp_tools_state.json`、`pytest_cache`（含 frontend 的 `pytest_cache_frontend`）、`playwright-mcp`、`tmp-change-review-dist`；读取时若发现旧根目录文件且新路径不存在，**自动移动迁移**。技能状态迁移失败（文件占用等）记录警告并继续读旧文件、保留禁用状态；旧文件也无法读取/解析时显式报错（不按全部启用处理）。MCP 状态读取/解析失败保留内存状态且不锁存成功、后续可重试；未完成加载时工具暂不可用。`.gitignore` 补充忽略 `.sugaragent/` 与旧 `mcp_tools_state.json`（旧版遗留保护）。
- **规则与边界**：正在运行的实例需重启后使用新路径；重启前若旧实例写回根目录文件，新版本不覆盖 `.sugaragent/` 中状态，可手动删除残留。配置文件（`mcp_servers.json`、`model_profiles.json`）自 2026-10-06 起同样默认落 `.sugaragent/`（`agent_mcp._config_path`、`model_profiles.profile_store_path`），首次读取自动迁移根目录旧文件（模型档案还包括更早的 `app/model_profiles.json`）；配置内的相对路径仍相对进程工作目录解析，不随配置文件位置改变。
- **依据**：`agent_tools.py`（SKILL_STATE_PATH）、`agent_mcp.py`（_MCP_TOOLS_STATE_PATH）、`pytest.ini`、`.sugaragent/mcp_servers.json`、`.sugaragent/model_profiles.json`、`.gitignore`；回归 `tests/test_sugaragent_state_paths.py`、`tests/test_mcp_state_read_failures.py`。

### UC-9E4 会话活动时间口径与执行面板初始化幂等（2026-10-05 补）
- **触发**：宿主启动扫描；会话索引重建（mtime 提示有新增时）。
- **预期现象**：执行面板初始化幂等（已有状态不再改写、revision 不随重启递增；`recover()` 仍每次执行）；活动时间回填为"最后一条非控制事件"时间（控制类事件显式列举：扩展命名空间状态、插件清单/重载等不计入）；日志不可解析时退回 mtime 口径；尾部仅控制事件时保留已存活动时间。
- **规则与边界**：错误口径的索引无需手工修复（按新口径重算自愈）；全量重建约 0.5s（仅 mtime 新于已存活动时间的会话触发尾扫）。
- **依据**：`execution_services/notifications.py`、`session_lifecycle.py`、`agent_harness.py::refresh_sessions_index_from_disk`；回归 `tests/test_session_index_startup_rebuild.py`、`tests/test_execution_panel_bootstrap.py`。

## 3. 边界

- 三条机制都保持"非 Windows / 常规环境零额外行为"：helper 在非 Windows 返回 0；自检只影响启动路径；状态目录只改默认路径与迁移。
- 明细 changelog：`../CHANGELOG-2026-10-03-依赖启动自检修复.md`、`../CHANGELOG-2026-10-03-子进程控制台窗口统一收敛.md`、`../CHANGELOG-2026-10-03-根目录状态文件迁移.md`。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-9E1 | `check_requirements.py`、`RUN.bat`、`RUN.sh` |
| UC-9E2 | `proc_flags.py`、`audit_subprocess_flags.py`、`platform_lifecycle.py`、全仓派生点 |
| UC-9E3 | `agent_tools.py`、`agent_mcp.py`、`pytest.ini`、`.gitignore` |

## 5. 版本记录

- 2026-10-05 v2：新增 UC-9E4——启动扫描幂等（不污染活动时间）、活动时间改事件感知（控制事件显式排除）、索引自愈。
- 2026-10-03 v1：拆分首版——启动依赖自检（每次真实校验 + 缺失补装、~2.3s 快检）、隐藏子进程控制台统一收敛（`proc_flags` + 全仓巡检 + RUN 自适应隐藏）、根目录状态/临时文件迁入 `.sugaragent`（自动迁移与失败降级）。待提交后补提交号。
