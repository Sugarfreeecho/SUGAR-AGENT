# 2026-10-12 桌面版卸载清理与残留收敛

- 目标：让「卸载」除用户工作目录外不留残留；同时保证「覆盖安装升级」不误删用户数据与状态。
- 范围：`packaging/electron-builder.config.cjs`、`packaging/nsis/installer.nsh`、`tests/test_nsis_workspace_preservation.py`、`packaging/README.md`、根 `README.md`。
- 基线：`c283814`（10-12 14:59）。

## 一、问题

按 `Uninstall SugarAgent.exe`（1.5.1，2026-10-07 构建）卸载后，除安装目录被删外仍会留下：

| 残留 | 大小（本机实测） | 原设计保持的原因 |
|---|---|---|
| `%APPDATA%\SugarAgent`（Electron userData：缓存/日志/Local Storage/状态） | 84.3 MB | `nsis.deleteAppDataOnUninstall: false` |
| `%LOCALAPPDATA%\SugarAgent\security\security.sqlite3`（安全库）、`plugins\` | 33.6 MB | 由应用写盘，卸载器未处理 |
| `%TEMP%\sugaragent-*`（插件运行时/出网校验临时目录） | 2626 个目录 / 15.9 MB | 卸载器未处理 |
| `HKCU\Software\Classes\sugaragent-desktop`（协议）、`…\Notifications\Settings\com.sugaragent.desktop` | — | Windows 侧无自动注销（electron-builder 只为 mac/Linux/Appx 生成协议注册） |
| 工作目录（本机为 `…\OneDrive\文档\SugarAgent\workspace`） | 480.2 MB | 用户数据，**按需求保留** |

## 二、改动

### 1. `packaging/electron-builder.config.cjs`
- `nsis.deleteAppDataOnUninstall: false → true`：卸载（非升级）时删除 `%APPDATA%\SugarAgent`（`APP_FILENAME`=`SugarAgent`；模板同时覆盖 `APP_PRODUCT_FILENAME`/`APP_PACKAGE_NAME`）。
- 顶部注释新增「卸载策略」：程序文件、userData、应用状态、临时目录、协议/通知键各自由哪一层负责清理；升级路径不受影响。

### 2. `packaging/nsis/installer.nsh`
- 新增 `Var sugarUpgradeMode` / `Var sugarDeleteAppData`，在 `customUnInstall` 里用 `${StdUtils.TestParameter}` 判定 `--updated` / `--delete-app-data`（与 electron-builder 生成的 `_isUpdated` 同一机制；StdUtils 在生成脚本里先于本 include 引入）：
  - **用户主动卸载**（无 `--updated`，含显式 `--delete-app-data`）：`RMDir /r` 清 `%LOCALAPPDATA%\SugarAgent`、`%LOCALAPPDATA%\sugaragent-updater`、`%LOCALAPPDATA%\sugaragent-desktop-updater`，调用新函数清 `%TEMP%\sugaragent-*`，`DeleteRegKey` 清 `HKCU\Software\Classes\sugaragent-desktop` 与通知设置键 `${APP_ID}`。
  - **覆盖安装升级**（`--updated`）：只清历史包名遗留的 `sugaragent-desktop-updater`；用户状态、协议注册一律保留（本包 installer store 由正在运行的安装器随后覆盖为新包）。
- 新增 `Function un.SugarAgentRemoveTempDirs`：`FindFirst/FindNext "$TEMP\sugaragent-*"` 逐个 `RMDir /r`，只删目录不删同名文件，删不掉的忽略错误。
- 仍保留既有策略：`un.SugarAgentRemoveFiles` 与 `patch-nsis.mjs` 对 `un.atomicRMDir` 的补丁共同保留 `$INSTDIR\resources\runtime\{workspace,.config,.sugaragent}` 与安装目录骨架；工作目录本身（哪怕被配置到别处）永不动。

### 3. `tests/test_nsis_workspace_preservation.py`
- 新增 `test_uninstall_configuration_removes_app_state_and_gates_on_update`：校验 `deleteAppDataOnUninstall=true` 与 `installer.nsh` 里的分流条件、各清理目标。
- 新增 `test_uninstall_macro_expands_with_cached_toolchain`：用缓存 NSIS 编译器 + `nsis-resources` 插件目录真编译 `Section "un.Validate"`（展开 `customUnInstall`），确保 `${StdUtils.TestParameter}`、`Call un.…`、`DeleteRegKey … ${APP_ID}` 可编译。
- 预处理用例补充 `un.SugarAgentRemoveTempDirs` 断言。
- 修正 `test_workspace_patch_preserves_atomic_rollback_and_is_idempotent[previous_patch=True]`：模板已被 10-12 的补丁写成「完整三行跳过」，旧模拟会重复注入 `workspace` 导致 `count==1` 断言失败；现改为先回退 `.config`/`.sugaragent` 两行再跑补丁，恢复该用例原本的「旧补丁→新补丁」升级语义。

### 4. 文档
- `packaging/README.md`：安装路径大小写修正（`%LOCALAPPDATA%\Programs\SugarAgent`）；「数据保留」「卸载清理」两行说明。
- 根 `README.md`：桌面版覆盖安装/卸载的数据范围说明。

### 5. `packaging/scripts/patch-nsis.mjs` —— 安装器仓库改为条件生成
- electron-builder 默认在**安装阶段**把安装器自身复制成 `%LOCALAPPDATA%\sugaragent-updater\installer.exe`（模板 `include/installer.nsh:93` 的 `copyFile "$EXEPATH" …`；目录名来自 `appInfo.updaterCacheDirName = ${sanitizedName}-updater`，`appInfo.js:126`）。该副本只在“本包带更新渠道”时有意义（更新器用 `--package-file` 复用本地包做差分下载/无网修复）；本项目未接 electron-updater，`app-builder-lib` 内部也只有写入、没有读取方，等于每装一次多复制 ≈250 MB。
- 新增第 5 条补丁（`required: true`、幂等）：用 `IfFileExists "$INSTDIR\resources\app-update.yml" 0 sugar_skip_installer_store` 包住那行复制。判据来源：`resources\app-update.yml` 只在配置了 `publish` 时由 `PublishManager.js:89` 写入，正好表示“这个包带更新渠道”。
- 卸载/升级里对 `%LOCALAPPDATA%\sugaragent*-updater` 的回收逻辑保留（对老版本安装留下的目录仍有作用）。

## 三、行为矩阵（改动后）

### 用户主动卸载
| 路径 | 结果 |
|---|---|
| 安装目录 `$INSTDIR` 内程序文件（SugarAgent.exe、app.asar、runtime/app、runtime/python、plugins、workspace-template…） | 删除 |
| `$INSTDIR\resources\runtime\{workspace,.config,.sugaragent}` 与目录骨架 | 保留 |
| `%APPDATA%\SugarAgent` | 删除（`deleteAppDataOnUninstall`） |
| `%LOCALAPPDATA%\SugarAgent`（安全库/插件） | 删除 |
| `%LOCALAPPDATA%\sugaragent-updater`、`sugaragent-desktop-updater` | 删除 |
| `%TEMP%\sugaragent-*` | 删除 |
| 桌面/开始菜单快捷方式、`HKCU\…\Uninstall\<GUID>`、`HKCU\Software\<GUID>` | 删除（electron-builder 模板） |
| `HKCU\Software\Classes\sugaragent-desktop`、`…\Notifications\Settings\<APP_ID>` | 删除 |
| 用户工作目录（可被配置到任意位置，本机为 OneDrive 下） | 不动 |

### 覆盖安装升级（安装器带 `--updated` 调用旧卸载器）
| 项 | 结果 |
|---|---|
| 旧程序文件 | 由旧卸载器移出并删除，新安装包重新解包 |
| `%APPDATA%\SugarAgent`、`%LOCALAPPDATA%\SugarAgent`、`%TEMP%\sugaragent-*`、协议/通知键 | 保留 |
| 快捷方式 | `--keep-shortcuts`（旧注册表 `KeepShortcuts=true` 且旧 exe 存在时）保留，否则由新安装器重建 |
| `$INSTDIR\resources\runtime\{workspace,.config,.sugaragent}` | 取决于**执行卸载的旧卸载器**是否带保留补丁：本版及以后保留；无补丁的旧包（如 1.5.1）会连它们一起清掉 |
| `%LOCALAPPDATA%\sugaragent-updater` | 旧卸载器（1.5.1 起）升级时会清；本版起不再清（安装器随后覆盖为新包） |

## 四、实测证据（NSIS 语义探针，一次性）

用缓存编译器 `nsis-3.0.4.1` 编译最小脚本验证 `Rename`（`un.atomicRMDir` 的搬运原语）：

| 场景 | 结果 |
|---|---|
| 跨卷（D: → `$PLUGINSDIR`，C:）重命名**文件** | OK |
| 跨卷重命名**空目录** | **FAILED**（源目录保持完好） |
| 同卷重命名空目录 | OK |

推论：升级路径 `un.atomicRMDir` 只对**文件**做 `Rename`（目录是 `CreateDirectory` + 递归），所以跨卷升级可行；但安装目录内若存在**空目录**，会走 `Rename` 文件分支 → 跨卷失败 → `un.restoreFiles` 回滚 + `Abort`，安装器进入重试/取消对话框。本机 1.5.1 安装目录实测**空目录 0 个**（45598 文件 / 684.5 MB），因此本次覆盖安装不会触发该问题。

## 五、验证

```powershell
.\python\python.exe -m pytest tests/test_nsis_workspace_preservation.py tests/test_sugaragent_state_paths.py -q
# 20 passed
```

### 真机验收（2026-10-12 22:25–22:55，`SugarAgent-Setup-1.5.3-x64.exe`）

流程：备份现网数据 → 静默安装到 `D:\AI\AI Agent\_sugaragent-uninstall-test`（此步先由 1.5.1 旧卸载器处理现有安装）→ 跑一次应用生成用户状态 → 再装一次（升级分支）→ 静默卸载 → 核对。
可复现脚本与日志：`workspace/SugarAgent卸载分析/verify-uninstall.ps1`、`workspace/SugarAgent卸载分析/验收结果-20261012.log`。

| 时点 | 检查项 | 结果 |
|---|---|---|
| 安装后 | 旧安装目录 `D:\AI\AI Agent\SugarAgent Desktop` | 被整体清空（旧卸载器无保留补丁，含 `runtime\.sugaragent`） |
| 安装后 | 新目录 / 卸载项 / installer store | `…\_sugaragent-uninstall-test`；DisplayVersion=1.5.3、InstallLocation=测试目录；store `installer.exe` 264456263 B = 新包同尺寸 |
| 升级分支 | `%APPDATA%\SugarAgent`（Preferences、app-logs） | 保留 ✔ |
| 升级分支 | `%LOCALAPPDATA%\SugarAgent\security` | 保留 ✔ |
| 升级分支 | `%TEMP%\sugaragent-*`（含自建 marker 目录） | 保留 ✔ |
| 升级分支 | 协议键 / 通知键 / 两个快捷方式 / `runtime\workspace` | 全部保留 ✔ |
| 卸载分支 | `%APPDATA%\SugarAgent`、`%LOCALAPPDATA%\SugarAgent`、`%LOCALAPPDATA%\sugaragent-updater` | 全部删除 ✔ |
| 卸载分支 | `%TEMP%\sugaragent-*`（2622 个历史目录 + marker） | 删除；仅剩 1 个由当时在跑的源码实例即时新建的 `sugaragent-runtime-v2-snapshot-locks` |
| 卸载分支 | 协议键 / 通知键 / 卸载项 / InstallLocation 键 / 两个快捷方式 | 全部删除 ✔；开发版协议键 `HKCU\Software\Classes\sugaragent` 保留（非本安装包注册） |
| 卸载分支 | 测试安装目录 | 只剩 `resources\runtime\workspace\`（首次启动铺设的技能模板 2150 个文件）与目录骨架 ✔ |
| 全程 | 工作目录 `…\OneDrive\文档\SugarAgent\workspace` | 13509 文件 / 12 会话，卸载前后一致 ✔ |
| 全程 | 系统管理项 | `%LOCALAPPDATA%\CrashDumps`（10 个开发版转储）、Recent（13 个 `.lnk`）仍在，卸载器按设计不处理 |

验收后清理：测试安装目录（85.9 MB）与临时构建目录 `build\dist-uninstall-test`（937.4 MB）已删除；`build\dist` 保留 1.5.1 / 1.5.2 / **1.5.3**；用户数据备份保留在 `D:\AI\AI Agent\_sugaragent-卸载验收-20261012\`（118 MB）。

### 安装器仓库（`%LOCALAPPDATA%\sugaragent-updater`）条件生成的验证

| 验证方式 | 结果 |
|---|---|
| NSIS 守卫探针（真实执行同样语句；`workspace/SugarAgent卸载分析/_guard-probe.nsi`） | 无 `resources\app-update.yml` → `A_no_channel=SKIPPED`；有 → `B_with_channel=COPIED`，并在 store 路径生成 `installer.exe`（38,715 B = 探针自身）✔ |
| 端到端（重建的 `SugarAgent-Setup-1.5.3-x64.exe`，无 `publish`） | 安装后 `resources/app-update.yml=False`、`store_after_install=False`（不再生成该目录）；卸载后 `%APPDATA%\SugarAgent`、商店目录、卸载项、快捷方式与测试安装目录全部消失 ✔ |

日志：`workspace/SugarAgent卸载分析/安装器仓库验收-20261012.log`。说明：该轮脚本末尾几行因会话被平台中断未写入日志，最终状态由独立检查复核（store / 测试目录 / 卸载项 / 快捷方式均为 False，仅剩源码实例即时重建的 `%LOCALAPPDATA%\SugarAgent\security`）。

## 六、已知限制与注意

1. **旧包升级仍会丢安装目录内配置**：1.5.1（及更早）卸载器没有保留补丁，被新安装包调用时会清空整个安装目录（含 `resources\runtime\.sugaragent\model_profiles.json`，其中含明文 API Key）。升级前请备份该目录；本版起的后续升级不再有该问题。
2. **`%LOCALAPPDATA%\SugarAgent` 与源码运行共用**（`app/security/store.py` 在 Windows 固定用该路径）：卸载会清掉源码版共用的安全库（审批/信任/审计）。这是「除工作目录外都清」的既定取舍，需要保留时请先备份。
3. **跨卷升级成本**：旧文件会先复制到 `%TEMP%`（C:）再由卸载器退出时删除，需要 C: 上约等于安装体积的空闲空间。
4. Windows「最近使用」`.lnk`、`%LOCALAPPDATA%\CrashDumps\*.dmp` 属系统管理项，卸载器不处理。

## 七、验收过程中的自我误伤（教训，待办未实施）

- 现象：本批次两轮真机验收的「真卸载」各删掉一次 `%LOCALAPPDATA%\SugarAgent`（22:55、00:2x），而当时**正在运行的源码/dev 实例**用的就是这个目录里的安全库（`app/security/store.py`：Windows 固定路径，可用 `MYAGENT_SECURITY_HOME` 覆盖）。库被删后该实例每次工具执行都报 SQLite `unable to open database file`，运行与自动续跑连续失败，会话停滞（22:55–23:31 无任何运行）。
- 结论：这是「卸载要干净」叠加「安装版与源码版共用状态目录」的必然结果；宿主重启（`host_restarted`）是失败链的终点，不是原因。旧库已备份在 `D:\AI\AI Agent\_sugaragent-卸载验收-20261012\Local-SugarAgent\security\security.sqlite3`（33.7 MiB），当前运行的是重建后的空库（72 KiB）。
- 待办（尚未实施，需单独决策）：
  1. 验收脚本加「dev 实例未运行」守卫，并在卸载前备份、事后恢复 `security` 目录；
  2. dev 实例用 `MYAGENT_SECURITY_HOME` 指向独立目录，与安装版状态隔离；
  3. 产品级选项：安装版后端改用独立状态目录（随卸载只清自己那份），或在 README 显著位置警告「真卸载会删掉与源码版共用的安全库（审批/MCP 注册/审计）」。
