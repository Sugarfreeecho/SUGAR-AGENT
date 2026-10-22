# 提交 / 推送 / 打包 · 标准作业流程（SOP）

本文把「提交、推送、打包」三件事固定下来：改完代码按本流程执行即可，不需要每次口头交代。
适用范围：本仓库（Windows x64 开发机，PowerShell；仓库内自带 `python\python.exe`）。

---

## 0. 前置检查（一次性）

```powershell
python\python.exe --version        # 仓库自带运行时
node --version                     # 需 ≥ 22（打包用）
git config core.quotepath          # 建议 false：中文路径不被转义
git status --porcelain             # 开工前确认没有别人的半成品混进来
```

- 钩子已就位：`.git/hooks/pre-commit`、`.git/hooks/pre-push`（见下文）。
- `python\`、`workspace\skills`、`tools\`、`*.zip`、`workspace\` 均不入库；打包/迁移要用它们时从本机取。

---

## 1. 提交（commit）

### 1.1 改动顺序

1. **先改设计稿**：`docs/Agent 设计（用户方案）/` 下对应 UseCase 清单，补/改条目并升版本行（如 `2026-10-19 v7`）。
2. 改代码与测试。
3. 写 **changelog**：`docs/CHANGELOG-<YYYY-MM-DD>-<主题>.md`，含提交清单、主题要点、验证、交付/遗留。

### 1.2 分组提交

- 按主题分组，一组一个提交；提交信息格式：`type(scope): subject` + 正文（英文 subject，正文说清「为什么」与影响面）。
- 一个文件混了多个主题时做 **hunk 级拆分**：
  - 交互式：`git add -p -- <path>`
  - 脚本化：把选定 hunk 写入临时 patch，`git apply --cached <hunks.patch>`（历次 `_split_*.py` 即此模式）
- 提交前确认暂存内容：`git diff --cached --stat`、`git diff --cached --check`

### 1.3 前端硬规则（钩子强制）

只要动到 `frontend/` 或 `app/templates/dist/`：

```powershell
cd frontend
npm run build            # 产物写回 app/templates/dist（可用 GENERAL_AGENT_DIST_DIR 指到临时目录做校验）
cd ..
```

- **源码与 dist 必须同一个提交**；只交源码或只交 dist 都会被拒。
- `pre-commit` 会先跑 `scripts/update_frontend_version.py`：把 `v5.YYYYMMDD` 戳刷成当天，并自动 `git add` 三个文件
  （`frontend/index.html`、`frontend/src/shell-body.html`、`app/templates/dist/index.html`）。
- 再跑 `scripts/check_frontend_commit_policy.py` → `scripts/check_frontend_dist_sync.py`：**在临时目录做一次全新 Vite 构建**，与 `app/templates/dist` 逐字节比对（`filecmp`）。不一致即拒绝提交。
- 常见被拒原因：手改了 dist；改了源码没重新 build；`dist/index.html` 与构建产物差空行；CRLF 混乱。
  处理：`cd frontend && npm run build`，然后 `git add -A -- frontend app/templates/dist` 再提交。
- 应急绕过：`$env:SKIP_FRONTEND_CHECK='1'`（仅限 CI/救火，正常流程不要用）。

### 1.4 版本号（只在发版时改）

- 只改两处**权威**位置：`packaging/package.json` 的 `version`、`packaging/package-lock.json` 里**自身 2 处**（顶层 + `packages[""]`）。
- `README.md` / `packaging/README.md` / `packaging/HOWTO-另一台电脑打包.md` 的「当前版本」引用随改；历史 `dist-1.5.4` 之类的记录保留。
- 版本号体现在：安装包文件名、卸载项显示名、窗口标题。前端 `v5.YYYYMMDD` 是运行戳，与包版本无关。

### 1.5 提交前自检

```powershell
python\python.exe -m compileall -q app
python\python.exe -m pytest tests\test_xxx.py -q -p no:cacheprovider    # 相关子集；全量约 27 分钟
git status --porcelain
```

- 统计未跟踪/修改时**别用** `Where-Object { $_ -like '??*' }`（PowerShell 的 `?` 是单字符通配符，会误判）；用 `git status --porcelain -z -uall` 交给 Python 解析。

### 1.6 收尾

`git status --porcelain` 必须为空。未跟踪内容二选一：**入库**（源码/测试/文档/`patches/`）或**写入 `.gitignore`**（`tools/`、探针目录、临时产物）。

---

## 2. 推送（push）

```powershell
git push origin master
```

- `pre-push` 运行 `scripts/check_frontend_commit_policy.py --pushed`：检查 **HEAD 提交**涉及的文件；不含前端时自动跳过；含前端时同样做「全新构建 + 逐字节比对」，不一致会**阻止推送**。
- 推送后核验：

```powershell
git ls-remote origin master                 # 与本地一致
git log --oneline origin/master..HEAD       # 必须为空
git status --porcelain                      # 必须为空
```

- 推送被拒时：按提示补构建/补提交，再 `git push`；不要 `--force`（历史仅快进）。

---

## 3. 打包（package）

三种产物，按需选择。

### 3.1 桌面安装包（Windows）

前置：Node ≥ 22、`packaging\node_modules` 已装（`npm install`）、`python\` 可用、首次联网拉 wheel。
**换机打包先读 `packaging/HOWTO-另一台电脑打包.md`**（`python\` 与 `workspace\skills` 两个不入库的必备输入）。

```powershell
# 发版先升版本号（见 1.4），再：
cd packaging
node scripts\build.mjs                   # 一键：图标 + 载荷 + NSIS 安装包（约 40 分钟）
```

常用变体：

```powershell
node scripts\build.mjs --dir             # 只出未打包目录（调试最快）
node scripts\build.mjs --skip-payload    # 复用现有载荷，只重打安装包
node scripts\prepare-payload.mjs --skip-deps   # 复用 site-packages，仅重刷 app 代码
node scripts\prepare-payload.mjs --build-frontend  # 构建前先跑 vite build
$env:SUGARAGENT_BUILD_OUTPUT='build\dist-1.5.5'; node scripts\build.mjs   # 指定输出目录
$env:SUGARAGENT_MAX_COMPRESSION='1'; node scripts\build.mjs               # 极限压缩
```

内部阶段（build.mjs 串联，失败会明确报出）：

1. `prepare-payload.mjs`：拷贝 app/plugins/skills，`pip install --no-compile`、全程 `-B`/`PYTHONDONTWRITEBYTECODE=1`；
   跑 `archive-runtime.py`（飞书 SDK → `lark_oapi.zip` + `.pth`；PPT 图标 → `icons.zip` + 索引）；`payload-bytecode.cjs` 清理并**拒绝**松散 `.pyc`。
2. `electron-builder`：`beforePack/afterPack` 断言 `runtime-archives.json` 布局；`afterPack` 调 `installStartupLauncher` 做双 exe 品牌化。
3. NSIS：`installer.nsh` 写 `HKCU\Software\Classes\AppUserModelId\<APP_ID>`，卸载清理。

产物：`packaging\build\dist\SugarAgent-Setup-<版本>-x64.exe`。
交付前核验：文件名含版本号、`Get-FileHash` 记 sha256、安装→启动→卸载残留检查（详见 `docs/desktop-release-1.5.4-2026-10-14.md`）。

### 3.2 迁移包（整目录 zip，拷到另一台机）

- **钉已提交状态**：`git ls-tree -r -z HEAD -- app plugins packaging` + `git cat-file blob HEAD:<path>`，未跟踪文件不入包（要含未提交现状则单独标注「worktree 快照」）。
- 范围：`app/`、`plugins/`、`packaging/`；`packaging` 只取白名单子目录（`electron scripts nsis native assets runtime` + 配置/README/HOWTO）。
- 排除：`__pycache__`、`*.pyc/pyo`、`.pytest_cache`、`.mypy_cache`、`node_modules`、`build`、`logs`、`.env*`、`.requirements.installed`。
- 压缩：`zipfile.ZIP_DEFLATED, compresslevel=6`，4 MB 分块，mtime=HEAD 提交时间，权限 0o644。
- 命名：`YYYYMMDD.zip`（含未提交时 `YYYYMMDD_worktree.zip`）；生成后报 **文件数 / 字节 / sha256**，并核 must-have（`app/main.py`、dist 两资产、`packaging/package.json`、`electron/main.js`、`startup.html`、`sugar-logo.png`、`StartupLauncher.cs`、`archive-runtime.py`、`payload-bytecode.cjs`、`runtime-archives.cjs`、`runtime/sugaragent_icon_archive.py`、`nsis/installer.nsh`）。

### 3.3 增量补丁包

- 目录：`patches/patch_<日期>_from_<基线日期>/`，含 `full`（含 dist）与 `source`（不含 dist）两个 `.patch`、`numstat_*.txt`、`应用说明.md`；并更新 `patches/README.md` 索引（含 sha256 表）。
- 生成：`git diff --cached -p --no-color --no-renames --binary`（rename 形式在外部目录不可用，故 `--no-renames`）。
- 应用：目标目录若**不是 git 仓库，`git apply` 会静默跳过全部补丁**（rc=0、Skipped）——必须先
  `git init -q && git add -A && git -c user.email=a@b -c user.name=t commit -qm base`，应用后可删 `.git`；CRLF 报错加 `--ignore-whitespace`。
- 校验：在临时仓库重放，逐字节 strict + EOL 宽容 tolerant 双计，`bad` 必须为 0；被替换的旧 dist 资源须确认移除。
- 基线重建规则：未改动文件取磁盘字节；已改动文件取基线提交 blob 并按该文件磁盘 EOL 风格转换（否则 CRLF 噪声会污染补丁）。

---

## 4. 一键清单（复制勾选）

```
[ ] 设计稿已更新（UseCase 版本行）
[ ] changelog 已写（docs/CHANGELOG-<日期>-<主题>.md）
[ ] 前端已 npm run build，src+dist 同提交
[ ] 版本号（发版时）package.json + lock 自身 2 处
[ ] compileall + 相关 pytest 通过
[ ] 分组提交完成，提交信息含 why
[ ] git status 为空（未跟踪已入库或忽略）
[ ] git push origin master
[ ] ls-remote / ahead=0 / status 空 三项核验
[ ] （打包）产物名含版本、sha256、安装与卸载冒烟
```

## 5. 常见故障

| 现象 | 原因 | 处理 |
|---|---|---|
| 提交被拒：dist 不同步 | 改源码没重 build / 手改 dist | `cd frontend && npm run build`，再 `git add -A -- frontend app/templates/dist` |
| 推送被拒：前端检查 | HEAD 提交里前端与 dist 不一致 | 同上，补一个修复提交后重推 |
| `git apply` 什么都没做 | 目标目录不是 git 仓库 | 先 `git init` 并提交 base |
| 补丁里全是 EOL 噪声 | 基线用 blob 直出（LF）对磁盘 CRLF | 按 3.3 的基线重建规则生成 |
| Windows 下中文路径显示乱码/被引号包裹 | `core.quotepath` 默认 true | `git config core.quotepath false`；脚本解析用 `-z` |
| PowerShell 统计未跟踪数量不对 | `-like '??*'` 的 `?` 是通配符 | 用 `git status --porcelain -z -uall` + Python 解析 |
| PowerShell 读 UTF-8 文件乱码 | PS 5.1 默认 ANSI | `$PSDefaultParameterValues['Get-Content:Encoding']='utf8'`（run_shell 前置已内置） |

---

相关文档：`packaging/README.md`（打包工程细节）、`packaging/HOWTO-另一台电脑打包.md`（换机打包）、`patches/README.md`（补丁索引）、`docs/CHANGELOG-*.md`（各批次记录）。
