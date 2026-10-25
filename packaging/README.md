# SugarAgent 桌面版打包工程

把 SugarAgent（Python 后端 + Vite 前端）打包成 **Windows x64 一键安装的桌面应用**：内置便携 Python 运行时与全部必需依赖，用户下载安装包双击安装即可使用，无需自行安装 Python、pip 或联网装依赖。

## 产物

| 产物 | 路径 | 体积 |
|---|---|---|
| 安装包（向导式，默认） | `packaging/build/dist/SugarAgent-Setup-<版本>-x64.exe` | ≈ 251 MB |
| 安装包差分块 | `packaging/build/dist/SugarAgent-Setup-<版本>-x64.exe.blockmap` | ≈ 200 KB |
| 未打包目录版 | `packaging/build/dist/win-unpacked/` | 调试用；现有产物尚未应用资源归档优化 |
| 运行时载荷 | `packaging/build/payload/` | 中间产物；下次准备时自动合并飞书 SDK 与 PPT 图标 |

2026-10-14 的 1.5.4 优化包位于 `build/dist-1.5.4/SugarAgent-Setup-1.5.4-x64.exe`（224.5 MiB）；载荷 8,130 个文件、应用 8,152 个文件、松散字节码为 0。构建与验证记录见 `docs/desktop-release-1.5.4-2026-10-14.md`。

安装后：程序在 `%LOCALAPPDATA%\Programs\SugarAgent`（**按用户安装，不需要管理员权限**），默认工作目录在安装目录的 `resources/runtime/workspace`，与 `app/`、`python/` 保持源码版的相对位置。安装目录不可写时使用 `%APPDATA%\SugarAgent\workspace`。桌面/开始菜单都有 `SugarAgent` 快捷方式，并注册标准卸载项。卸载只保留工作目录与 `runtime` 内的用户数据，程序文件、Electron userData（`%APPDATA%\SugarAgent`）、应用状态（`%LOCALAPPDATA%\SugarAgent`）与临时目录都会被清掉。

### 安装器形态

默认是**向导式（assisted）**，页面顺序：`安装选项（当前用户/所有用户）→ 选择安装位置 → 安装进度 → 完成页（可勾选"运行 SugarAgent"）`，界面为简体中文，支持自选安装目录。

需要"双击即装、只有进度条"的一键式（one-click）时：

```powershell
$env:SUGARAGENT_INSTALLER_STYLE='oneclick'; node scripts\build.mjs --skip-payload
# 产物改名为 SugarAgent-Setup-<版本>-x64-oneclick.exe
```

两种形态都支持静默安装（`/S`）与指定目录（`/D=<绝对路径>`，需放在最后一个参数）。

## 目录结构

```
packaging/
├─ package.json                  # 桌面壳工程（electron 44.5.1 / electron-builder 26.15.3）
├─ electron-builder.config.cjs   # NSIS 一键安装配置（按用户、快捷方式、卸载器）
├─ requirements.desktop.txt      # 精简后的内置依赖（派生自 app/requirements.txt）
├─ electron/
│  ├─ main.js                    # 主进程：后端托管 / 动态端口 / 托盘 / 单实例 / 退出清理
│  └─ preload.js                 # 最小渲染进程桥接
├─ scripts/
│  ├─ prepare-payload.mjs        # 组装运行时载荷（拷贝 + 裁剪 + pip 安装 + 自检 + 清单）
│  ├─ archive-runtime.py         # 合并飞书 SDK / PPT 图标，并适配载荷中的图标读取脚本
│  ├─ runtime-archives.cjs       # 拒绝未优化或已展开图标的旧载荷
│  ├─ make-icons.py              # PNG → 多尺寸 ICO（应用图标 / 托盘图标）
│  ├─ build.mjs                  # 一键构建：图标 → 载荷 → electron-builder
│  ├─ smoke-payload.mjs          # 载荷自检：用内置 Python 真启动后端并探活
│  └─ smoke-desktop.ps1          # 端到端自检：启动打包产物，校验窗口目标与后端健康
└─ build/                        # 构建输出（已 gitignore）
```

## 构建

前置：Windows x64、Node.js ≥ 22（本机 v24）、仓库内 `python\python.exe` 可用；首次构建需要联网拉取 pip wheel。
**换机打包请先读 [HOWTO-另一台电脑打包.md](HOWTO-另一台电脑打包.md)**（含 `python\` 与 `workspace\skills` 两个「不在 git 的必备输入」清单）。

```powershell
cd packaging
npm install                      # 一次即可：装 electron / electron-builder
node scripts\build.mjs           # 一键：图标 + 载荷 + NSIS 安装包
```

常用变体：

```powershell
node scripts\build.mjs --dir             # 只出未打包目录（调试、最快）
node scripts\build.mjs --skip-payload    # 复用现有载荷，只重打安装包
node scripts\prepare-payload.mjs --skip-deps       # 复用已装好的 site-packages 重刷 app 代码
node scripts\prepare-payload.mjs --build-frontend  # 先跑 frontend 的 vite build
node scripts\prepare-payload.mjs --list-skills     # 只看白名单会打包/跳过哪些技能，不写载荷
node scripts\prepare-payload.mjs --list-plugins    # 只看按分级表会打包/跳过哪些插件，不写载荷
node scripts\build.mjs --all-skills                # 忽略白名单，全量打包技能
node scripts\build.mjs --all-plugins               # 连独立功能插件一起打包
$env:SUGARAGENT_MAX_COMPRESSION='1'; node scripts\build.mjs   # 极限压缩（安装包更小、构建更慢）
$env:SUGARAGENT_PIP_INDEX='https://pypi.tuna.tsinghua.edu.cn/simple'  # 国内镜像装依赖
```

### 技能模板只打包白名单里的技能

技能模板取自 `SKILLS_DIR`（默认 `workspace\skills`），但**不会整目录照搬**，只拷 `packaging\skills.allowlist.txt` 里列出的目录：

- 白名单是**打包侧的固定契约**：一行一个技能（写目录名或 `SKILL.md` 的 `name` 都行），`#` 之后是注释。与运行时的技能启停状态（`.config\skill_states.json`）**完全无关**——界面里以后开关了哪些技能，都不影响打包结果。
- 加技能就加一行、删技能就删一行；新增的白名单项如果对不上任何目录，构建会直接失败并列出名字，避免改名后静默漏打。
- 与运行期扫描规则一致：只认第一层目录且必须有 `SKILL.md`。因此 `workspace\skills\隐藏\`（运行期本来就不注册）和散落在技能根目录的 zip 永远不会进包。
- 真要发一个全量技能包（演示/排障）：`node scripts\prepare-payload.mjs --all-skills`，它只忽略白名单这一次。
- 打包结果写进 `runtime-manifest.json` 的 `skills` 字段（`mode` / `allowlistFile` / `packaged` / `skipped` / `missing`），便于事后审计。

### 插件范围由分级表决定

插件是否进包不在这里另列名单，而是读 `app/plugins/tiers.json`（运行期与打包共用的唯一分级表）：

| 分级 | 进包 | 设置页 | 默认状态 | 工具 |
|---|---|---|---|---|
| `system` | 是 | 隐藏 | 启用 | 常驻 |
| `system-external` | 是 | 可见可开关 | 启用 | 常驻 |
| `extension` | 是 | 可见可开关 | 启用 | 延迟加载 |
| `standalone` | **否** | 可见可开关 | **停用** | 延迟加载 |

- 当前 `standalone` 的 6 个（`voice-input`、`chatgpt-subscription`、`feishu-transport`、`game-arena`、`repo-engineering`、`sugar-bili-scroll`）不进安装包；源码运行时仍然可见，只是默认停用。
- 表里登记为前三档、但仓库里找不到对应目录时，构建直接失败，避免改名后静默漏打。
- 每插件都有独立环境变量开关：`PLUGIN_<ID>_ENABLED`（如 `PLUGIN_EXECUTION_TOOLS_ENABLED=0`）。环境变量优先级高于界面开关，设置页会把开关置灰并显示变量名。
- 兼容规则：未登记的老式内置插件（`system_builtin` + native + 位于 `plugins/`）仍按“隐藏”处理；未登记的新插件按“可见、默认启用、不打包”处理。

### SDK 与 PPT 图标归档

载荷准备默认执行资源合并，以减少安装和首次启动时的文件创建与复制：

- 飞书 SDK 的代码与预编译字节码放入 `python/Lib/site-packages/lark_oapi.zip`，通过随载荷写入的 `.pth` 文件直接导入；SDK 的 `.dist-info` 元数据与其它原生依赖保留在磁盘上，`RECORD` 同步记录归档和加载文件以兼容 pip 卸载/升级。归档使用同一便携 Python 生成字节码，载荷自检验证归档导入及消息、长连接入口。
- PPT 图标放入 `workspace-template/skills/ppt-master/templates/icons/icons.zip`，另有完整名称索引 `icon-archive.json`。源工作区技能不变；只适配载荷副本的图标同步、SVG 解析和预览读取，使用哪个 SVG 才提取哪个。首次启动复制的是归档，完整图标库保持离线可用。
- 搜索尚未使用的图标：在 `ppt-master` 技能目录运行 `python scripts/sugaragent_icon_archive.py list --library tabler-outline --query home`。文件夹列表只显示已经提取的图标。项目自定义图标优先保留。
- `runtime-archives.json` 与 `runtime-manifest.json` 记录归档路径、校验摘要和条目数。技能来源读取入口变化时，准备流程会明确失败，要求复核适配。
- 两处 pip 安装都使用 `--no-compile`，构建期 Python 子进程使用 `-B` / `PYTHONDONTWRITEBYTECODE=1`。所有依赖和版本探针结束后统一清理载荷中的松散字节码；复用依赖时也会清理历史缓存。SDK 和标准库 ZIP 内的字节码保留，运行期仍允许创建缓存。

归档不会在安装结束或首次启动时全量展开。安装器继续使用原有 7z 格式，用户数据保留规则不变。

旧载荷不能直接通过 `--skip-payload` 构建；构建前后都有归档布局校验。需要构建新版本时先执行 `npm run payload:fast`（复用依赖）或 `npm run payload`（重新安装依赖），再执行正常的构建命令。仅修改打包工程时无需执行载荷准备或构建命令。

需要保留已有目录版中的调试数据时，可设置 `SUGARAGENT_BUILD_OUTPUT=build/dist-<版本>`，将新产物构建到独立目录；默认仍为 `build/dist`。

自检：

```powershell
node scripts\smoke-payload.mjs --port 8399        # 载荷级：启动内置后端并探活
powershell -File scripts\smoke-desktop.ps1        # 端到端：启动 win-unpacked 并校验窗口
powershell -File scripts\smoke-desktop.ps1 -AppDir "$env:LOCALAPPDATA\Programs\SugarAgent"   # 校验已安装版本
```

## 载荷内容

```
resources/runtime/
├─ app/                  # 应用代码（含 templates/dist 前端产物、tools、native 的 egress helper）
├─ plugins/              # 按 tiers.json 收录的插件（当前 9 个，独立功能不进包）
├─ python/               # 便携 CPython 3.10.11 基座 + 干净安装的 site-packages（71 个依赖）
│  ├─ Scripts/rg.exe     # 文件搜索用的 ripgrep
│  └─ Lib/site-packages/lark_oapi.zip # 飞书 SDK，Python 直接从归档加载
├─ workspace-template/   # 首次启动铺到工作目录的技能模板（只含 skills.allowlist.txt 里的技能）
│  └─ skills/ppt-master/templates/icons/{icons.zip,icon-archive.json}
├─ runtime-archives.json # 资源归档布局 / 摘要 / 条目数
└─ runtime-manifest.json # 版本、依赖清单、体积、排除项
```

> 只打包激活技能后，若激活列表里没有 `ppt-master`，`workspace-template\skills\ppt-master` 与其图标归档都不存在，`runtime-archives.json` 的 `pptIcons` 记为 `null`；归档校验按“存在才校验”处理，不影响构建。

**不会打进安装包**：`app/.env`（含真实密钥）、`python/Lib/site-packages` 里的历史环境、`workspace/`、`logs/`、`version/`（备份包）、`__pycache__`、开发机 `Scripts/` 里的历史 shim。审计脚本可复核（见下）。

## 内置依赖策略

保留应用本体运行需要的库（fastapi/uvicorn/openai/httpx/mcp/lark-oapi/pillow/openpyxl/pdfplumber/pypdf/tokenizers/psutil/pywin32…）。
2026-10-25 清理：`aiohttp` 及其传递依赖只被不随包的 `sugar-bili-scroll` 使用；`aiofiles/cachetools/chardet/jinja2/loguru/tiktoken` 代码已无引用。`standalone` 插件（`voice-input`、`sugar-bili-scroll` 等）的依赖改为按需安装，清单与镜像地址见 `docs/standalone-plugin-dependencies.md`。
**有意排除**重依赖：`playwright`、`matplotlib`、`pandas`、`pymupdf`、`markitdown`、`sentry-sdk`、`coverage`、`pytest*`、`python-magic` —— 桌面版因此少了浏览器自动化、图表绘制、重型数据分析等能力，但安装包小了 300 MB 以上。

用户后续需要时，可用**随包自带的 pip** 补装到内置运行时（无需再装 Python）：

```powershell
"%LOCALAPPDATA%\Programs\SugarAgent\resources\runtime\python\python.exe" -m pip install pandas matplotlib
```

（安装目录保持程序原地更新不变；补装的包在卸载时随安装目录一起移除。）

## 运行期设计要点

| 主题 | 行为 |
|---|---|
| 后端托管 | Electron 主进程用内置 `python\python.exe` 起 `app\main.py`，日志写 `%APPDATA%\SugarAgent\logs\backend-<日期>.log` |
| 端口 | 默认 8192，被占用时自动顺延到 8199；同时通过 `MYAGENT_SERVER_PORT` 告知后端与内部链接 |
| 环境变量 | 只继承系统变量，模型/搜索/云厂商密钥一类变量被显式过滤，保证新装用户一定是"未配置"状态 |
| 首启向导 | 未检测到可用模型配置时，窗口直接打开应用自带的 `/setup` 配置向导 |
| 技能模板 | 首次启动把 `workspace-template/skills` 铺到默认 `workspace/skills`（已存在则不动） |
| 窗口尺寸 | 初始 1440×920；支持自由缩放和半屏停靠，不设应用级最小宽高 |
| 启动反馈 | `SugarAgent.exe` 是轻量 Windows 启动入口：先显示品牌 Logo 与原生等待提示，再以 `STARTF_FORCEONFEEDBACK` 拉起 `SugarAgentRuntime.exe` 请求系统启动光标；Electron 第一帧可见后通过当前用户专用命名管道收起原生提示。后端等待页同样使用 Logo、旋转动画和忙碌光标，任务栏显示等待进度；准备完成后自动进入主界面或首启向导 |
| 运行时品牌 | `afterPack` 替换启动入口后显式编辑 `SugarAgentRuntime.exe` 的图标、产品名、版本与版权资源，随后由构建器编辑启动器；两个 exe 都使用 SugarAgent 品牌。Electron 通知初始化按运行时产品名创建开始菜单快捷方式，不能只修改安装器的 `shortcutName` |
| 托盘 | 关闭窗口＝最小化到托盘；托盘菜单：打开主界面 / 浏览器打开 / 重启内置服务 / 打开后台日志 / 打开工作目录 / 退出；后台日志复用源码版实时彩色终端查看器 |
| 重启内置服务 | 重启内置 Python Agent 后端，保持 Electron 窗口、托盘及当前端口；重启期间禁用重复重启，就绪后重载界面并处理通知跳转。主动停止不弹崩溃框；启动失败与真正的等待超时分别提示。已安装桌面版需重新打包并覆盖安装才能更新外壳代码 |
| 通知跳转 | 使用独立的 `sugaragent-desktop://open-ui` 协议唤起桌面窗口；会话通知保留会话定位，使用当前后端端口 |
| 通知启动器 | 有效通知链接走静默转交路径，挂起创建 Electron 子进程、定向传递前台激活权限后再恢复执行，再由 Electron 单实例机制转交已有窗口；不显示原生启动小窗、不请求忙碌光标。普通双击保留完整启动反馈。启动时仅清理指向本安装的旧 `Electron.lnk`，其它 Electron 应用快捷方式保留 |
| 系统文件与目录 | 页面经 preload IPC 交给主进程，使用当前后端端口的 probe 接口保留路径与会话校验，再调用 `shell.openPath` 或 `shell.showItemInFolder`；不从后台 Python 唤起。打开失败返回界面，浏览器版保留原有后端入口。详见 `docs/desktop-foreground-activation.md` |
| 通知发送 | 后端通过带每次启动随机凭据的本机通道交给 Electron 主进程发送原生通知；窗口隐藏到托盘后仍可发送，失败记录在 `desktop.log` 并回退到系统通知助手 |
| 关闭窗口提示 | 主进程将窗口隐藏/显示状态同步到后端；关闭到托盘后提示后台运行，重新打开窗口取消待发提示，任务完成/待处理通知优先于通用提示 |
| 原生主题 | 页面浅色 / 深色 / 紫色同步到 Electron 原生主题，窗口边框和菜单随页面主题切换 |
| 退出 | 退出时按进程树结束内置 Python（`taskkill /T /F`）；后端异常退出会弹恢复对话框 |
| 配置目录 | 模型档案、MCP 与启停状态保存在 `resources/runtime/.config`；工作区内的附件、缓存也使用 `.config`，启动时自动迁移旧 `.sugaragent`，已有新配置优先，冲突旧文件保留；打包时排除载荷内的用户配置和工作区 |
| 数据保留 | 覆盖安装与卸载均保留 `resources/runtime/workspace`、`resources/runtime/.config` 和尚未迁移的 `.sugaragent`；此前在“文档”下的自定义工作目录既不迁移、也不受卸载影响 |
| 卸载清理 | 用户主动卸载会一并清掉 `%APPDATA%\SugarAgent`（`deleteAppDataOnUninstall`）、`%LOCALAPPDATA%\SugarAgent`（安全库/用户插件）、`%LOCALAPPDATA%\sugaragent*-updater`、`%TEMP%\sugaragent-*`，以及 `sugaragent-desktop` 协议和通知设置注册表键；覆盖安装（安装器用 `--updated` 调用旧卸载器）只换程序文件，这些用户数据与状态全部保留 |
| 安装器仓库 | 默认**不生成** `%LOCALAPPDATA%\sugaragent-updater\installer.exe`；electron-builder 原本会在这里复制一份 ≈250MB 的安装包，只有带更新渠道（`resources/app-update.yml`，即配置了 `publish`）时才需要它来做差分/修复。条件由 `scripts/patch-nsis.mjs` 第 5 条补丁注入，卸载/升级的回收逻辑保留 |
| 状态文件 | `%APPDATA%\SugarAgent\desktop-status.json` 记录端口、后端 PID、窗口目标，便于排查与自动化校验 |

## 对应用本体做的小改动

为了让桌面版能与开发实例共存、并支持自动避让端口，改了 4 个文件（默认行为不变）：

- `app/main.py`：监听端口支持 `MYAGENT_SERVER_PORT` 覆盖（默认仍 8192）
- `app/platform_lifecycle.py`、`app/tray_launcher.py`、`app/agent_updater.py`：同上，保持内部链接端口一致

## 已知限制与后续建议

1. **未做代码签名**：安装包没有证书，Windows SmartScreen 会提示"未知发布者"。对外分发建议购买 OV/EV 代码签名证书，在 `electron-builder.config.cjs` 的 `win.signtoolOptions` 里配置后重打。
2. **无内置自动更新**：目前靠重新下载安装包覆盖安装（同目录升级会保留用户数据）。需要自动更新可加 `electron-updater` + 固定更新源。
3. **仅 Windows x64**：macOS/Linux 需要另做托盘适配与签名公证（`app/platform_tray_macos.py`、`platform_tray_linux.py` 已存在）。
4. **应用内自更新（git pull 那套）不适用于桌面版**：`app/agent_updater.py` 针对源码运行方式，桌面版更新走安装包。
5. **审计脚本**：可在打包后复查载荷是否混入密钥/用户数据（检查 `app/.env`、`model_profiles.json`、`sk-` 形态字符串）。

## 版本号

版本号在 `packaging/package.json` 的 `version`（当前 `1.5.5`），会体现在安装包文件名、卸载项显示名与窗口标题中；发新版时改这里（连带 `package-lock.json` 中自身 2 处）并重新构建。
