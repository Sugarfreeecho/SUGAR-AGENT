# 2026-10-05 批次归档、二阶消融与增量补丁

## 一、本批范围

10-05 全天批次（约 106 个路径）在**先同步设计稿**后，按主题拆分为 6 个提交；连同 10-04 晚批 4 个提交一并推送（`ff56ab2`→`b8bd2b7`，共 10 个提交）。

## 二、设计稿落点（提交前先改）

- 新建 `09-横切能力/08《工具按需披露》`（UC-9G1~9G4）；
- `09/07 v2`（UC-9F6 执行回执与证据链）；`09/06 v2`（UC-9E4 活动时间口径与面板初始化幂等）；`02/09 v4`（UC-2I13 Goal 失败即停）；`05/01 v6`（UC-5A9 排队消息连续运行）；
- 补记：`05/02 v12`、`05/04 v8`、`05/05 v4`、`05/14 v2`、`06/06 v3`、`06/08`、`04/02 v3`、`09/00 v9`；`00-总览 v31`（专项 72→73）；`WebUI 能力清单 v27`。

## 三、分组提交

| 提交 | 主题 | 规模 |
|---|---|---|
| `3c95350` | feat(tools)：工具按需披露 + MCP 服务器级筛选 | 28 文件 +2123/−584 |
| `294f1d2` | fix(execution)：CUA 证据链 / SIGINT 三级回执 / 终端与后台任务修复 | 24 文件 +2603/−90 |
| `b69196a` | fix(runtime)：排队追问连续运行 / Goal 失败即停 / 活动时间 | 27 文件 +1999/−550 |
| `bb3c7de` | fix(webui)：交互与状态保存 / 权限与终端 cwd 边界 / 拆解卡补取 | 19 文件 +633/−163 |
| `fc1bd4b` | chore：二阶孤儿消融 | 9 文件 +123/−159 |
| `b8bd2b7` | docs：用户方案同步 | 15 文件 +99/−16 |

（`ea1f056`..`31c7b11` 为 10-04 晚批 4 个提交，随本批一并推送。）

## 四、二阶孤儿消融

- 删除 6 个全仓零引用符号及 2 条死导入（均 `git grep` 零引用核验）：`dockActionStep`、`branchFinalTextMatches`、`splitUserMessageVisualLines`、`executor_text_and_usage`、`_openai_sdk_base_url`、`single_turn_text_completion`；
- 保留待判定：`session_authorized_dirs` 三函数、`is_preapproved_host`（安全语义，不盲删）；口径见 [dead-code-2026-10-05.md](dead-code-2026-10-05.md)。

## 五、验证与推送

- 消融后全量 `pytest`：**2258 passed / 5 skipped / 0 failed**；node 30/30；每个含前端的提交均通过 "Frontend dist is in sync." 钩子；
- 推送：`ff56ab2..b8bd2b7`，`ls-remote` 与本地一致，ahead 0。

## 六、增量补丁（另一台电脑）

- `workspace/patch_20261005/`：
  - `app_plugins_since_20260930_full_20261005.patch`（完整版 1,587,129 B，含 dist 重建产物）；
  - `app_plugins_since_20260930_source_20261005.patch`（源码版 444,582 B，不含 dist）；
  - `应用说明.md`（含 sha256 与应用命令）。
- 基线 `ff56ab2` / 目标 `b8bd2b7`（范围 `app/` + `plugins/`）；以 `ff56ab2` 重放校验：full 版 281/281、source 版 274/274 文件与目标逐一相等（source 版不改动 dist）。
