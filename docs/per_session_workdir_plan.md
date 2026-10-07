# 每会话工作目录 · 计划与实施状态

> 说明：本文件由 `01_per_session_workdir.patch` 的「实施状态」节移植而来（2026-10-06）。
> 原计划文档的正文（一~七节：背景、DSH 对照、方案取舍等）未随补丁包提供，故此处仅含实施状态部分；
> 表中行号为源机（生成补丁时的检出）行号，仅供定位参考。

---

## 八、实施状态（首版已落地）

### 已决策
- D1 会话库**保持全局**（索引里加一个 `work_dir` 字段）✅
- D2 附件 / Vision / 上传 / 历史媒体**继续留在默认工作目录** ✅
- D3 **创建后不可改**（与 DSH 一致）：想换目录就新建会话 ✅（因此不需要"变更失效链"）

### 后端（已实现 + 已验收）
| 改动 | 位置 |
|---|---|
| 会话工作目录工具函数族：`normalize_session_work_dir` / `session_work_dir_override` / `session_work_root_raw` / `session_work_root` / `session_work_dir` / `session_work_dir_projection` | `app/agent_harness.py`（工具函数区） |
| 创建会话接受 `work_dir`（校验：绝对路径 + 存在 + 是目录；非法直接 `ValueError`/422）；`authorized_dirs` 首值随会话目录；索引行写入 `work_dir` | `app/agent_harness.py` `get_or_create_session`、`app/webui.py` `POST /sessions` |
| 索引重建与侧栏投影：`/sessions`、`/sessions/state` 每条含 `work_dir` / `work_dir_label` / `work_dir_is_default`（读索引行，不额外做磁盘 I/O） | `app/agent_harness.py`（索引投影区） |
| **三根统一**：工具根（`worktree_root`）、安全策略根（`security_workspace`）、审计根（`audit_root`）、early-tool 预授权根全部走 `session_work_root()`，并去掉 `is_subagent` 守卫 | `app/agent_loop.py` `_react_node_once` 各分支 |
| hook 载荷与变更审计锁 key 跟随会话目录（默认目录/子代理行为不变） | `app/agent_loop.py` `_dispatch_state_hook`、`plugins/change-review/host.py` |
| 安全白名单兜底按会话目录 | `app/session_authorized_dirs.py` |

**验收脚本（源机可复跑；未随补丁包提供）**：
- `workspace\每会话工作目录\verify_backend.py` —— 22 项，全过（默认会话、自定义会话、索引、投影、非法输入、ContextVar、白名单、显式默认目录等价于未指定）
- `workspace\每会话工作目录\verify_api.py` —— 14 项，全过（隔离实例跑 `POST /sessions` 与 `GET /sessions/state`，含 422 分支）

### 前端（已实现 + 构建通过；子代理做了打桩浏览器验证）
- 分组切换：侧栏会话列表头部与「界面设置 → 会话目录」两处同步，键 `myagent-session-group-by`，**默认仍是时间分组**（老用户无感）
- 工作目录分组：组标题 = `work_dir_label`（默认目录显示"默认工作目录"），完整路径进悬停提示；默认组在前、其余按组内最近活动倒序；折叠状态按组 key 记忆
- 渲染 key：`computeSessionListRenderKey()` 已纳入 `groupBy` 与 `work_dir*` 三字段
- 路径根跟随当前会话：新增 `getActiveWorkDir()`（`frontend/src/app/config.js`），已替换 `message-rendering.js`（7 处）、`settings.js`、`permissions.js` 的路径根
- 新建会话：`▾` 菜单提供「在当前工作目录新建会话」/「在新工作目录新建会话」（第二项复用 `MyAgentPathPicker`，不可用时降级为手填路径）
- 空白会话草稿：欢迎内容下方展示当前目录，并允许发送首条消息前选择或更改会话目录；更改会重建隐藏草稿，保留输入内容，会话物化后目录固定
- 构建产物：`app/templates/dist/`（`npm run build` 通过）

> 本仓库落地补充（2026-10-06）：设置面板已由「设置中心」承接，「会话分组」控件落在 设置中心 → 界面；
> 桌面版打包工程已从源机补丁包引入（`packaging/`），载荷将包含以上全部后端/前端改动。

### 尚未完成（下一步候选）
1. **浏览器端到端**：真实后端 + 真界面的联合验收（子代理只做了打桩验证；后端契约已由 `verify_api.py` 覆盖）。
2. **工作区文件面板**（`vendor/myagent_path_picker.js`、`dock/embedder/right-column.js`、`workspace-media.js`）仍按全局根走：`/api/workspace-files`、`/api/open-workspace-file`、`/api/workspace-file-text` 的 `rel` 是服务端按 `WORK_DIR` 解析的，需要这些接口支持 `session_id` / `work_dir` 参数才能跟随（前端已加注释说明）。
3. **原生目录选择器初始目录**（`app/path_picker_util.py`）仍读全局 `WORK_DIR`，建议改为按当前会话目录起步。
4. **桌面版**：后端改了 `app/*.py`，桌面安装包需要重新 `prepare-payload` + 重打包才会带上这些改动。
