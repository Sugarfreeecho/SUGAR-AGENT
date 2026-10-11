# 2026-10-09 ~ 10-11 批次归档

- 归档时间：2026-10-11（本地提交；推送另步）
- 基线：`f746a3b6`（10-10 23:33，"chore: refresh models_table.md from OpenRouter snapshot"）
- 范围：10-09、10-10、10-11 三天并行开发成果的首次分组提交，另含更早遗留的 `.config` 配置路径迁移与 10-09 流式排查材料。
- 提交清单：`git log --oneline f746a3b6..HEAD`（下方表格）。

## 一、提交清单（按落地顺序）

| # | 提交 | 主题 |
|---|------|------|
| 1 | `bcd5379` | feat(workspace): 会话有效根贯通（子代理/worktree/提示/终端/浏览/扩展/桌面入口）+ `.config` 路径体系 |
| 2 | `05eef2a` | fix(memory): 压缩思考可见性 v2（候选失效重置、结束事件、执行器流边界） |
| 3 | `c2c9426` | fix(session): 睡眠恢复旧临时帧过滤（后端：事件总线 + 订阅恢复竞态） |
| 4 | `dd5c831` | fix(tools): run_shell 输出解码（1/3 判据）与 PowerShell UTF-8 前置 |
| 5 | `bbb1657` | feat(tools): 工具按需披露 v2（pinned_tools、配置语义收口） |
| 6 | `20a15c8` | feat(settings): 技能管理、安装冲突三选一、会话导出/导入 |
| 7 | `096160d` | fix(models): 模型档案兼容（`:batch` 变体降权、能力标签随表刷新） |
| 8 | `aa25a9b` | feat(webui): 前端批次（会话列表/流式/右键菜单/媒体预览/i18n）+ dist 重建（v5.20261011） |
| 9 | `f5fbf71` | feat(desktop): 壳协议、原生右键菜单、NSIS 工作区保留与载荷脚本 |
| 10 | `27bd80e` | feat(tools): 会话重放工具 1.0.5 与卡顿排查脚本 |
| 11 | `020b638` | test(stream): 全文本用例接替、导入修正与 js 恢复桩补齐 |
| 12 | `c656e5f` | chore(plugins): 移除 hello-python 示例 |
| 13 | 本归档 | docs: 用户方案 v48、本 changelog、审查与性能证据、示意图 |

## 二、主题明细

### 1. 会话有效根 v2（`bcd5379`）
- 路径链路统一到会话有效根（`subagent_work_dir → git_worktree_path → work_dir → WORK_DIR`）：子代理创建继承父根、旧子代理按父链补齐；worktree 按所属项目仓库定位/合并/清理；提示（Environment/fork）、用户终端、权限兜底、Hook（`project_root` + `app_root`/`shared_root`）同根；`temporary` 清理按实际路径、超长结果全局保存但返回绝对路径。
- 新增 `app/workspace_paths.py`（无副作用解析）与 `app/config_paths.py`（`.sugaragent→.config` 一次性合并、冲突保留）；MCP/插件/vision/history-media/远程控制/桌面壳/维护脚本接入；`webui` 浏览/文本/媒体/HTML 预览支持会话身份，`/api/workspace-info`；选择器 v2。
- 测试：`test_session_workspace_paths`（新）、`tests/js/session_workspace_paths.cjs`（新）、`test_config_paths`（新）、`test_webui_paths`、`test_sugaragent_state_paths`、`test_workspace_media_snapshots`、`test_agent_harness_executor_session`、`test_tool_result_truncation`。
- 文档：04/01 v5·UC-4A8/4A9、04/00 v5、04/02 v5、04/05 v2·UC-4E6、04/06 v4、《工作区能力清单》、`docs/workspace-path-audit-2026-10-11.md`。

### 2. 压缩思考 v2（`05eef2a`）
- `agent_memory` 在无答案候选结束时发 `context_summary_reasoning_end`、实时预览仅限当前轮；`agent_openai` 候选失败重置 reasoning 缓冲；`agent_harness` 执行器流补齐 `on_reasoning_end`/`reasoning_end` 边界。
- 测试：`test_agent_memory_compress_parse`（+3.7K）、`test_cpu_pressure`、`test_compression_reasoning_browser`。
- 文档：09/01 v6、05/02 v21、05/03 v9。

### 3. 睡眠/断线恢复过滤（`c2c9426` + 前端部分在 `aa25a9b`）
- `session_event_bus`：工具状态按执行 ID 最新化、完成清理；压缩等待只保留当前一条；睡眠恢复只通知在线订阅者、不进重放缓存。
- `webui`：订阅恢复按 `after_runtime_seq` 过滤，追赶完成后再次过滤队列（覆盖竞态）；前端 `shouldSkipRecoveredEphemeralEvent`/`seedEphemeralRecoveryScope` 跳过不新于游标的临时帧。
- 证据：`docs/performance/睡眠恢复重复执行过程-2026-10-11.md`；文档 05/03 v10·UC-5C10。

### 4. run_shell 解码链（`dd5c831`）
- `_decode_byte_line` 改"非 ASCII 字节里 ≥1/3 不是合法 UTF-8 才按 GBK"；PowerShell 执行加统一 UTF-8 I/O 前置（`RUN_SHELL_PS_UTF8=0` 可关）。
- 测试：`test_decode_cli_subprocess_bytes`、`test_run_shell_ps_utf8_prelude`（新）。

### 5. 工具按需披露 v2（`bbb1657`）
- `pinned_tools`/MCP `tools.pin` 追加常驻；`defer_plugin_tools` 弃用；配置缺失/损坏回退内置默认（on）且不删工具；文件 off 不被环境变量重开。
- 测试：`test_tool_search`、`test_tool_registry`；文档 09/08 v2、`docs/tool-disclosure.md`。

### 6. 设置中心 v2（`20a15c8`）
- 技能：本机移除、同名安装三选一（取消/覆盖/改名导入）；来源字段批量 textarea + 浏览按钮 `data-browse-kind`；目录拖拽保留相对路径。
- 会话包：`export_session`（+290 行）与导入（沿用原 id；冲突换 id 并改写包内引用）。
- 协作修复的真 bug：`sections_basic.js` 解构缺 `closeDialog`（完成后对话框不关）；`package_import.js` 目录批上传 sink 丢失（上传体无文件）。
- 测试：`test_session_import`（新）、`test_skills_admin`（新）、`test_settings_center_browser`；文档 05/14 v3·UC-5N7/5N8。

### 7. 模型档案兼容（`096160d`）
- 归一化模糊匹配遇同分不再取字符串更大的 `:batch` 变体（仅显式含限定词才命中）；能力标签随 10-10 表刷新收口（glm-5.2 输出价、gpt-5.4 intel）。
- 测试：`test_model_profiles` 43 passed。

### 8. 前端批次 + dist（`aa25a9b`）
- 会话列表/滚动历史、消息渲染保真（部分更新不覆盖元数据）、右键菜单模块与样式（UC-5Q1~5Q6 前端半）、路径选择器 v2（vendor）、workspace-media 原图细节、dock/浮窗/插件面板、i18n、app.css 主题与字重降档。
- dist 重建：`main-CY3E_0xp.js` / `main-Cbkpc6ct.css`；版本戳 `v5.20261011`（三处一致）；`Frontend dist is in sync.`。
- 契约测试更新：typography、context-menus（新 23KB）、image-preview（新）、execution-trace、llm-collapse、enablement、plugin-ui。

### 9. 桌面壳批次（`f5fbf71`）
- `sugaragent-desktop://` 协议与未决激活；布局解析保留 workspace 相邻关系；`installNativeContextMenu`（frame 感知原生回退）；`notify_ui_closed.ps1` 协议/AUMID 选择；NSIS 覆盖/卸载保留工作区；载荷脚本更新。
- 测试：`test_desktop_shell`（新）、`test_desktop_context_menu`（新，真 Electron 冒烟）、`test_nsis_workspace_preservation`（新）、`tests/js/desktop_shell_runtime.cjs`（新）、`tests/js/desktop_context_menu_electron.cjs`（新）。

### 10. 会话重放工具与排查脚本（`27bd80e`）
- `tools/session-replay` 1.0.5：便携重放服务 + 浏览器查看器，21 个开关（1007/1004 对照）、会话导入、实验运行器、自带测试与 README（覆盖边界以 README 为准）。
- `scripts/performance`：归档流/真实会话回放器与引导；控制台闪烁捕获脚本；证据 `docs/performance/**`（15 件）与 `docs/CHANGELOG-2026-10-09-流式间歇卡顿排查.md`。

### 11. 流式测试接替与桩补齐（`020b638`）
- `test_llm_stream_full_text_browser.py` 接替 `test_llm_stream_window_geometry.py`；4 处浏览器用例 import 更新；5 个 js 运行时套件补新全局（`streamHistoryRecoveryBySession`、`shouldSkipRecoveredEphemeralEvent`、`seedEphemeralRecoveryScope`、`executionRecordsBySession`、`appendLog`）；`benchmark_frontend_performance.py` 适配重构后的 llm 窗口。

### 12. 清理与文档归档（`c656e5f` + 本归档）
- 移除 `examples/plugins/hello-python`（目录整体删除）。
- 用户方案 v48：04 模块 v5 系列、新增 05/16《桌面壳右键菜单》、05/03 v10、05/14 v3、09/08 v2、00-总览（专项 74→75）、05/02 v22（用量表 10px）、05/13 v9.5（进行中图标）、WebUI 能力清单 v41、05/00 v32、05/06 v15；README 与技能参考跟进 `.config` 布局。

## 三、修复记录（本批收尾）

- 收集错误 ×4：被删用例引用 → 指向 `tests.test_llm_stream_full_text_browser`。
- js 桩 ×4：恢复过滤新全局缺失（含 tool_pending 深链 `seedEphemeralRecoveryScope`/`executionRecordsBySession`/`appendLog`）。
- 契约红 ×10（全量基线 2394/5/10 诊断后全部修复）：
  1. enablement：悬浮浮出契约（静止隐藏 + hover/focus 恢复）→ 成对断言；
  2. 全站字重降档 500→400（feed-chunk-scroller）；
  3. `.ctx-wrap` 10px（`0.625 × 1rem`）新基准 → 期望更新 + 设计稿 05/02 v22；
  4. 压缩思考移出 `createProcessFeedRow` → 断言改命名变量（语义等价）；
  5. 进行中图标改"右半实心圆" → 新 path 断言 + 三角转负断言 + 设计稿 05/13 v9.5；
  6. `:batch` 变体降权（源码修复）；
  7. glm-5.2 / gpt-5.4 能力标签随表刷新（期望修正）；
  8. 技能安装 `data-browse-kind` 契约 + `closeDialog` 解构真 bug（源码修复）；
  9. 目录批上传 sink 真 bug（源码修复）；
  10. dock 变更 diff 用例缺 `config.js` 共享作用域注入 → 按同类测试约定补加载（export-strip）。

## 四、验证

- 全量 pytest：2404 passed / 5 skipped / 0 failed（收尾复跑；基线 2394/5/10 的 10 红全部转绿）。
- node 运行时（tests/js，除 Electron 冒烟件）：36/36 通过。
- Electron 桌面冒烟：6 passed（desktop 批次）。
- dist 同步：`Frontend dist is in sync.`；版本戳 `v5.20261011`（`frontend/index.html`、`frontend/src/shell-body.html`、`app/templates/dist/index.html` 三处一致）。
- 提交后工作区：仅余 `tools/ffmpeg-8.1-essentials_build/`（未跟踪，310MB）与工作区临时物。

## 五、遗留与注意

- `tools/ffmpeg-8.1-essentials_build/`（310MB 下载物）未忽略、未提交：建议加 `.gitignore` 或移出仓库。
- 流式上滚卡顿为已知未决问题：见 `docs/流式自动上滚卡顿-反馈与排查结论-2026-10-09.md`。
- 本批 13 个提交均为本地；推送前核对 `git log --oneline origin/master..HEAD`（避免落后/领先混淆）。
- 设计稿覆盖度审查（S3）遗留的可选补充项（05/02 图像预览原图细节、上滚卡顿"已知未决"条目、09/09 桌面壳）见会话记录，未在本批处理。
