# 2026-10-19/20 批次归档：能力命名与 Hooks、压缩加固、桌面前台激活、运行时与 WebUI 增量

- 归档：2026-10-20；覆盖 10-17 ~ 10-20 的工作区批次（此前 10-16 批已提交，本次一并推送）。
- 版本：桌面安装包版本保持 1.5.4（未升包版本）；前端运行戳由提交钩子刷新为 v5.20261020。

## 一、提交清单

| # | 提交 | 主题 |
|---|---|---|
| 1 | `27ee6fb` | feat(naming)：工具/资源/Hook 短名分配（身份不变） |
| 2 | `618f101` | feat(plugins)：插件宿主/运行时/执行服务刷新 |
| 3 | `b08b34d` | fix(compression)：压缩目标统一为当前会话窗口 60%，取消与截断元数据 |
| 4 | `05df771` | feat(runtime)：RuntimeV2 写入/事件日志/快照 + 本地计时与请求执行器隔离 |
| 5 | `948c49f` | feat(loop)：轮次计时、断流恢复与 STREAM_WORKER_IDLE_TIMEOUT_SEC |
| 6 | `8d14a16` | feat(webui)：会话结果提示、上下文菜单、SSE 恢复、子代理 UI + dist 重建 |
| 7 | `3550054` | feat(desktop)：前台激活与本地路径桥 |
| 8 | `0c37419` | feat(subagent)：父子同步与子会话生命周期 |
| 9 | 本提交 | docs：设计稿更新（25 份）+ 本 changelog + 性能/缺陷记录 |
| 10 | 随后一提交 | chore：`.gitignore` 忽略本机工具链；`patches/` 归档入库 |

## 二、主题要点

### 1. 能力命名（naming）

- 新增 `tool_naming.py` / `resource_naming.py` / `hooks/naming.py`：按来源身份分配模型可见短名，截断改为“最短无歧义名”，执行身份（工具调用、hook id、资源路径）保持不变。
- registry / tool_search / MCP 目录 / 扩展目录 / hooks 执行器统一走分配器；`security/runtime.py` 跟随新命名契约。

### 2. 插件与执行服务

- 插件宿主、管理器、运行时接入命名契约与路径缓存；hook 执行统一经 `host_hooks`。
- 执行服务保持跨插件重载的作业归属；execution-tools 宿主与 agent-goal 插件同一生命周期。
- 记录：`docs/bugs/plugin-refresh-execution-stop-2026-10-20.md`、`plugin-toggle-latency-2026-10-20.md`。

### 3. 上下文压缩加固

- 达标判定改为「整包 token ≤ 当前会话窗口 × 60%」（`CONTEXT_COMPRESS_TARGET_RATIO`），不再用压缩前基线；长窗口会话压一次、短窗口保尾窗。
- 摘要轮可取消（`should_stop` 贯穿 `_compress_summary_round` / `_run_compress_executor_dialogue`）；`completion_info`（finish_reason/usage/model）穿透封装；截断重试按半输出预算收敛并要求闭合标签。
- `history_ops` / `versions` / `projector` 记录归档/版本/投影；设计稿 09/01 v7；分析记录 `docs/bugs/session-compression-6db32422-2026-10-19.md`（含 zen-gate `max` 档映射与 120s 总时限删除）。

### 4. RuntimeV2 与本地计时

- 写入侧：拥有式追加尾（seq cache 绑定路径身份）、后缀游标、增量源边界；快照预热分相位；派生缓存/扩展镜像只更新变化部分。
- 新增本地计时（跨 worker/hedge 的请求跨度、UI 投递与收尾共享的无载荷跨度）、阻塞请求独立执行器、快速 JSON 编码回退、工具结果状态适配、流事件桥与会话事件。
- 新增读写探针与追加/快照回归测试；`scripts/benchmark_agent_interround.py`。

### 5. 主循环与断流恢复

- 每轮本地相位计时；排队追问可恢复；阻塞模型调用隔离出事件循环执行器。
- 传输层区分首字停滞与中途静默：`STREAM_WORKER_IDLE_TIMEOUT_SEC`（默认 60）在已收到进度时保留进度并重连；README 与 `.env.example` 同步。
- 执行指标/观测/电源接口扩展；goal 预算停止标记为失败。

### 6. WebUI + 前端

- 会话结果提示、上下文菜单、灵活侧栏（dock/右栏）、技能面板、会话管理刷新、SSE 冻结/超时恢复、子代理目录与帧、路径选择器。
- `webui.py` 随附会话与设置 API；dist 由 `frontend/src` 逐字节重建（与新构建一致）。

### 7. 桌面壳

- 协议启动转交运行中实例、原生前台激活 + preload 桥、回环本地路径桥（`local-paths.js`）；启动器报告保持准确。

### 8. 子代理

- 子会话与父任务在重启后保持连接；子代理事件携带谱系；`subagent_store` 持久化关系。

## 三、验证

- `python -m compileall -q app` 通过。
- 快速子集：`tests/test_tool_naming.py tests/test_extension_resource_naming.py tests/test_agent_memory_compress_parse.py` → **48 passed**。
- 前端：dist 与一次全新 Vite 构建逐字节一致（`check_frontend_dist_sync.py` 通过）；运行戳 v5.20261020。
- 未跑全量套件（历史静机基线 2509 passed / 7 failed / 7 skipped，7 项均为负载型）；建议静机复跑。

## 四、交付与归档

- 补丁链（worktree 快照）：`patch_20261014_from_20261013` → `patch_20261019_from_20261014_v2` → `patch_20261020_from_20261019_v2`（均在 `patches/`，本次入库）。
- 迁移包：`20261016_worktree.zip`（工作区快照，7.1 MB）；已提交态包为 `20261016.zip`。
- 本机工具链目录 `tools/`（ffmpeg 等，约 890 MB）加入 `.gitignore`，不入库。

## 五、遗留

- 桌面安装包未重打（版本仍 1.5.4；如需出新包可升 1.5.5 并构建）。
- `patches/` 随仓库增长（本次 25.6 MB）；如不希望入库可改为忽略。
