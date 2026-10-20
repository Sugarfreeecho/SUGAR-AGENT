# patches 目录索引（补丁归档）

本目录汇总历次对外补丁交付（工作区原件仍在 `workspace/` 对应目录，未删除）。
结构：`<patch 名>/` 下含 full / source（/ numstat / 应用说明.md）。

应用方式（在目标目录内；非 git 仓库目录下 `git apply` 会静默跳过，需先 `git init` 一次）：

```
git init -q && git add -A && git -c user.email=a@b -c user.name=t commit -qm base
git apply --check <patch 文件>
git apply         <patch 文件>
```

（每个含 `应用说明.md` 的补丁目录内有各自的基线、覆盖范围与重放核验记录。）

> 注意：
> - 推荐应用顺序（worktree 快照链）：`patch_20261014_from_20261013` → `patch_20261019_from_20261014_v2` → `patch_20261020_from_20261019_v2`。
> - `patch_20261019_from_20261014_v2/`：10-19 工作区快照（含压缩达标口径统一为当前会话窗口 60% 的最终编辑）。
> - `patch_20261020_from_20261019_v2/`：基线是上一条的目标态（10-19 15:55），覆盖 10-20 的命名重构/hooks/桌面壳增量。
> - 这几套（以及 worktree 快照包）的目标都是**含未提交改动的工作区快照**；其余各套均为已提交状态的增量。

## 归档清单

| 目录 | 内容 | 文件 |
|---|---|---|
| `patch_20260921/` | workspace_since_last_push（全量/源码） | workspace_since_last_push_full_20260921.patch、workspace_since_last_push_source_20260921.patch |
| `patch_20260922/` | app_plugins_since_20260922（全量/源码，另含 since_06c38cc 一项） | app_plugins_since_06c38cc_full_20260928.patch、app_plugins_since_20260922_full_20260928.patch、app_plugins_since_20260922_source_20260928.patch |
| `patch_20260930/` | app_plugins_since_20260928（全量/源码/应用说明） | app_plugins_since_20260928_full_20260930.patch、app_plugins_since_20260928_source_20260930.patch、应用说明.md |
| `patch_20261005/` | app_plugins_since_20260930（全量/源码/应用说明） | app_plugins_since_20260930_full_20261005.patch、app_plugins_since_20260930_source_20261005.patch、应用说明.md |
| `patch_20261005_bundle/` | app_frontend_plugins_since_20261004（全量/源码/应用说明） | app_frontend_plugins_since_20261004_full_20261005.patch、app_frontend_plugins_since_20261004_source_20261005.patch、应用说明.md |
| `patch_20261013_from_20261012/` | app_plugins_packaging_since_20261012（全量/源码/numstat/应用说明） | app_plugins_packaging_since_20261012_full_20261013.patch、app_plugins_packaging_since_20261012_source_20261013.patch、numstat_full.txt、numstat_source.txt、应用说明.md |
| `patch_20261014_from_20261013/` | app_plugins_packaging_since_20261013（全量/源码/numstat/应用说明） | app_plugins_packaging_since_20261013_full_20261014.patch、app_plugins_packaging_since_20261013_source_20261014.patch、numstat_full.txt、numstat_source.txt、应用说明.md |
| `patch_20261019_from_20261014_v2/` | app_plugins_packaging_since_20261014（10-19 工作区快照刷新版，含压缩口径统一；全量/源码/numstat/应用说明） | app_plugins_packaging_since_20261014_full_20261019_v2.patch、app_plugins_packaging_since_20261014_source_20261019_v2.patch、numstat_full.txt、numstat_source.txt、应用说明.md |
| `patch_20261020_from_20261019_v2/` | app_plugins_packaging_since_20261019_v2（基线 = 10-19 v2 目标态；含 10-20 命名重构/hooks/桌面壳增量；全量/源码/numstat/应用说明） | app_plugins_packaging_since_20261019_v2_full_20261020.patch、app_plugins_packaging_since_20261019_v2_source_20261020.patch、numstat_full.txt、numstat_source.txt、应用说明.md |

## SHA-256

| 文件 | 字节 | sha256 |
|---|---:|---|
| `patch_20260921/workspace_since_last_push_full_20260921.patch` | 480659 | `9bf670dd6946af764eb50de3c2afb2a79e5f25490354b8eda2689a89de07b1cf` |
| `patch_20260921/workspace_since_last_push_source_20260921.patch` | 74220 | `f0a0aa04612663c094f38290ad1d8136d28c7cf196e09fe734301a9d17db1575` |
| `patch_20260922/app_plugins_since_06c38cc_full_20260928.patch` | 704274 | `4159ab29e2d7d88e923c67befe0155cb7d086fa53fbf5884b2b640c3d463d027` |
| `patch_20260922/app_plugins_since_20260922_full_20260928.patch` | 681827 | `42af28caf668be9eac1baa9fd3d84cd4bc975cf7e8ed636cd8703591567880a0` |
| `patch_20260922/app_plugins_since_20260922_source_20260928.patch` | 42708 | `b74deb93a7dea1f695b643cf9cba5940cb1cfec447055b8ffbea06cb4b135c6f` |
| `patch_20260930/app_plugins_since_20260928_full_20260930.patch` | 414583 | `28b33d56cf9c0434e989f8576450a357c1126124785dc86944fa0dfa58c17d68` |
| `patch_20260930/app_plugins_since_20260928_source_20260930.patch` | 211870 | `bea851ee9d8bb2cec0c719928f9fc5ae854fef57b54dc0e603dfc825a9a73eac` |
| `patch_20261005/app_plugins_since_20260930_full_20261005.patch` | 1587129 | `b43a581fe20a4c4563d6ce6d097903b4abdfcee3ad228c7f0156aebb7128833a` |
| `patch_20261005/app_plugins_since_20260930_source_20261005.patch` | 444582 | `62eab2cde617749d63328b8c770a104a8c45a276a083106489df9ec4dca15da3` |
| `patch_20261005_bundle/app_frontend_plugins_since_20261004_full_20261005.patch` | 372527 | `39c5b732697e2fc208042c1e0e418fba50b107602dc04cc60752fecdbe749884` |
| `patch_20261005_bundle/app_frontend_plugins_since_20261004_source_20261005.patch` | 282631 | `293be544f95adbdb39c48a04383edbc5dbf866632de36f79933f965d8d2ad20c` |
| `patch_20261013_from_20261012/app_plugins_packaging_since_20261012_full_20261013.patch` | 4395409 | `67dcd902e3031d63272553ba34b4f4bc72cb46d9a68c1bcad5d2cc9ba9ea7840` |
| `patch_20261013_from_20261012/app_plugins_packaging_since_20261012_source_20261013.patch` | 17725 | `ea5bcabbee31ae737cf110bf3295e61d17bbc8f2a4aa28ab74f176a5d5e0a254` |
| `patch_20261014_from_20261013/app_plugins_packaging_since_20261013_full_20261014.patch` | 5000121 | `f9a6ca81a93aece09c5efef3da99575dcc36770130888401ecce34c4a5c5f36e` |
| `patch_20261014_from_20261013/app_plugins_packaging_since_20261013_source_20261014.patch` | 111124 | `1c9c52be0a6ecae964d3ac0bb32b7416ad0562887e1addc8c51ca5b848ad4d97` |
| `patch_20261019_from_20261014_v2/app_plugins_packaging_since_20261014_full_20261019_v2.patch` | 5251759 | `20a5f163bad7ee9a2eb5a077caf7dd0b55da4a1893b05c73c917ba2e0a94f709` |
| `patch_20261019_from_20261014_v2/app_plugins_packaging_since_20261014_source_20261019_v2.patch` | 332809 | `ad4646488348db427778c594c286f2b5c0d0aca7c21765a670d946d2a19db1d0` |
| `patch_20261020_from_20261019_v2/app_plugins_packaging_since_20261019_v2_full_20261020.patch` | 5036723 | `2788d1078c4fb1d5d9322fe56d0d83a3885cfef051bdd3ef86a9aa85f93208a2` |
| `patch_20261020_from_20261019_v2/app_plugins_packaging_since_20261019_v2_source_20261020.patch` | 93754 | `a4079b0f5d023ee5539ef419c60030abada3896b665b5ef849b4aba8aadbfd13` |

## 未归档说明

- `workspace/patch_20261006/`：中间工作集（备份、split 补丁、rejects、tmp 重放），非交付物，未复制。
- `workspace/模型配置Patch升级/`：设计方案文档，非补丁文件。
- 迁移包内嵌的补丁（如 20261013.zip 内 `patch_from_20261012/`）与本目录 `patch_20261013_from_20261012/` 内容一致。
- 2026-10-20：`patch_20261019_from_20261014`（v1，已被 v2 取代）与 `fix-llm-reply-blank-lines.patch` 已由外部清理，不在本目录。

