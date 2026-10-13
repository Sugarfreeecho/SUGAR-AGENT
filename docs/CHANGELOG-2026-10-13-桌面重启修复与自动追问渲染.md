# 2026-10-13 批次归档：桌面后端重启修复 + 自动追问残留执行过程

- 归档：2026-10-13；本批 4 个提交（基线 `c4f4dc6`，含此前未推送的 22 个提交一并推送）。
- 结论：两处用户报告的缺陷修复（桌面“重启内置服务”报错；自动追问后残留“正在思考中”执行框）+ 配套渲染/进程卫生增强。按指示**未构建安装包**；分发物为 `20261013.zip` 迁移包（内附以 20261012.zip 为基线的补丁）。

## 一、提交清单

| # | 提交 | 主题 |
|---|---|---|
| 1 | `fd60aa7` | fix(desktop)：重启内置服务生命周期收敛与崩溃上报（`packaging/electron/main.js`、README、`tests/js/desktop_shell_runtime.cjs` +13 项回归） |
| 2 | `aa35f94` | fix(webui)：自动追问轮次分组与临时状态框清理；工具/进度流平滑揭示与快照替换；dist 重建 v5.20261013 |
| 3 | `bae7ebf` | chore(desktop)：版本号升至 1.5.4（package.json/lock 自身 2 处 + README/HOWTO 引用） |
| 4 | 本提交 | docs：设计稿 5 处（09/06 v3·UC-9E5、05/01 v8、05/02 v23·UC-5B14、05/03 v11、00-总览 v49）+ 本 changelog + 现场文档 ×2 |

## 二、主题一：桌面“重启内置服务”报错修复（`fd60aa7`）

- 根因：`stopBackend()` 主动终止进程未登记“预期退出”，旧进程 `exit` 回调随后仍走崩溃恢复分支；该回调直接改全局 `backend`/日志流/状态文件，迟到事件可清空新后端引用、写入新后端日志、覆盖其就绪状态。
- 修复：`WeakSet` 按 child 对象登记预期退出（避免 PID 复用误判）；事件闭包自持 child 与日志流；日志流在 `close` 后收束（含同步启动失败）；托盘/IPC/崩溃恢复共用重启互斥；退出取消待启动定时器、启动与等待检查退出态；健康检查绑定 child 并二次确认；恢复对话框去重、迟到旧框不能操作已恢复后端；重启期通知跳转排队。详见 `desktop-backend-restart-fix-2026-10-13.md`。
- 生效方式：主进程源码，需重新构建安装包/覆盖安装（本批未打包）。

## 三、主题二：自动追问残留执行框（`aa35f94`）

- 现场 `36497ba7-5683-4215-b3fd-3a7559b8a90d`；根因五条与修复见 `performance/自动追问残留执行过程-2026-10-13.md`：实时 `user` 事件缺事实序号 → 消息位置被当序号 → 临时错误分组插入“正在思考中” → 正式记录换组后旧框无法清理。
- 后端：`agent_loop` 保存用户提交序号，自动追问实时事件携带 `runtime_seq` 与 `process_group_id=turn:<seq>`；轮内 `user_steer` 维持原边界。
- 前端：先封存后编号；无序号保留未编号分组（兼容旧后端）；清理按已跟踪节点跨分组进行、空临时框连观察器/布局回调一并移除、封存先清临时状态；工具调用增量的平滑揭示（名称/参数两流）；压缩/要点进度流逐帧揭示；重放快照按累计值替换（不重放打字动画）；`setUiRuntimeText` 增量文本节点改写。
- 配套测试修复：`execution_display_compat_runtime.cjs` 桩补 `stream.contains`/`.process-aggregate-body`；`frontend_session_stream_runtime.cjs` 与 `session_loading_runtime.cjs` 补 seal 侧新钩子桩（原会话未运行相关套件，本批补跑全绿）。

## 四、验证

- 全量 pytest：**2440 passed / 6 skipped / 0 failed**（607s；修复前 2439/6/1，唯一失败为该 fixture 缺桩，已修复复跑）。
- node：**38/38**（含 desktop_shell_runtime / execution_display_compat / execution_smooth_stream 等）。
- dist：`Frontend dist is in sync.`；运行时戳 **v5.20261013**。
- 补丁重放：对 20261012.zip 解压样张（临时 git 仓库内应用）——full 版 320/320 逐字节全等（bad=0，被替换的旧 dist 资源已正确移除）；source 版 318/320（dist 两项按设计保持不变）。
- 注意：`git apply` 在非 git 仓库目录下会静默跳过全部补丁（rc=0），补丁应用前需 `git init` 一次（详见包内应用说明）。

## 五、交付物（本批外发）

- `20261013.zip`：app + plugins + packaging（净版），**323 文件 / 8.3 MB**，sha256 `16a8084721cd1c73f7268efa95b7d2529d9e47703e37cb919be3d134983c1fc3`。
- 包内 `patch_from_20261012/`：
  - `app_plugins_packaging_since_20261012_full_20261013.patch`（9 项，4,395,409 字节，sha256 `67dcd902…7840`）
  - `app_plugins_packaging_since_20261012_source_20261013.patch`（6 项，17,725 字节，sha256 `ea5bcabb…a254`）
  - `应用说明.md`
- 版本号 1.5.4 已就位：下一台机器重构建即出 `SugarAgent-Setup-1.5.4-x64.exe`；本机未执行打包。

## 六、遗留

- dist 内旧安装包（1.5.1/1.5.2/1.5.3）未清理；`tools/ffmpeg-8.1-essentials_build/` 仍未跟踪。
