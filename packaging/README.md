# SugarAgent 桌面版打包工程

把 SugarAgent（Python 后端 + Vite 前端）打包成 **Windows x64 一键安装的桌面应用**：内置便携 Python 运行时与全部必需依赖，用户下载安装包双击安装即可使用，无需自行安装 Python、pip 或联网装依赖。

## 产物

| 产物 | 路径 | 体积 |
|---|---|---|
| 安装包（向导式，默认） | `packaging/build/dist/SugarAgent-Setup-<版本>-x64.exe` | ≈ 202 MB |
| 安装包差分块 | `packaging/build/dist/SugarAgent-Setup-<版本>-x64.exe.blockmap` | ≈ 200 KB |
| 未打包目录版 | `packaging/build/dist/win-unpacked/`（3487 文件 / ≈ 641 MB） | 调试用 |
| 运行时载荷 | `packaging/build/payload/`（3413 文件 / ≈ 273 MB） | 中间产物 |

安装后：程序在 `%LOCALAPPDATA%\Programs\sugaragent`（**按用户安装，不需要管理员权限**），用户数据在工作目录 `%USERPROFILE%\Documents\SugarAgent\workspace`，桌面/开始菜单都有 `SugarAgent` 快捷方式，并注册标准卸载项。

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
│  ├─ make-icons.py              # PNG → 多尺寸 ICO（应用图标 / 托盘图标）
│  ├─ build.mjs                  # 一键构建：图标 → 载荷 → electron-builder
│  ├─ smoke-payload.mjs          # 载荷自检：用内置 Python 真启动后端并探活
│  └─ smoke-desktop.ps1          # 端到端自检：启动打包产物，校验窗口目标与后端健康
└─ build/                        # 构建输出（已 gitignore）
```

## 构建

前置：Windows x64、Node.js ≥ 22（本机 v24）、仓库内 `python\python.exe` 可用；首次构建需要联网拉取 pip wheel。

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
$env:SUGARAGENT_MAX_COMPRESSION='1'; node scripts\build.mjs   # 极限压缩（安装包更小、构建更慢）
$env:SUGARAGENT_PIP_INDEX='https://pypi.tuna.tsinghua.edu.cn/simple'  # 国内镜像装依赖
```

自检：

```powershell
node scripts\smoke-payload.mjs --port 8399        # 载荷级：启动内置后端并探活
powershell -File scripts\smoke-desktop.ps1        # 端到端：启动 win-unpacked 并校验窗口
powershell -File scripts\smoke-desktop.ps1 -AppDir "$env:LOCALAPPDATA\Programs\sugaragent"   # 校验已安装版本
```

## 载荷内容

```
resources/runtime/
├─ app/                  # 应用代码（含 templates/dist 前端产物、tools、native 的 egress helper）
├─ plugins/              # 10 个内置插件
├─ python/               # 便携 CPython 3.10.11 基座 + 干净安装的 site-packages（85 个依赖）
│  └─ Scripts/rg.exe     # 文件搜索用的 ripgrep
├─ workspace-template/   # 首次启动铺到工作目录的技能模板（18 个技能，含 docx/pdf/pptx/xlsx）
└─ runtime-manifest.json # 版本、依赖清单、体积、排除项
```

**不会打进安装包**：`app/.env`（含真实密钥）、`python/Lib/site-packages` 里的历史环境、`workspace/`、`logs/`、`version/`（备份包）、`__pycache__`、开发机 `Scripts/` 里的历史 shim。审计脚本可复核（见下）。

## 内置依赖策略

保留应用本体运行需要的库（fastapi/uvicorn/openai/httpx/mcp/lark-oapi/pillow/openpyxl/pdfplumber/tokenizers/tiktoken/psutil/pywin32…）。
**有意排除**重依赖：`playwright`、`matplotlib`、`pandas`、`pymupdf`、`markitdown`、`sentry-sdk`、`coverage`、`pytest*`、`python-magic` —— 桌面版因此少了浏览器自动化、图表绘制、重型数据分析等能力，但安装包小了 300 MB 以上。

用户后续需要时，可用**随包自带的 pip** 补装到内置运行时（无需再装 Python）：

```powershell
"%LOCALAPPDATA%\Programs\sugaragent\resources\runtime\python\python.exe" -m pip install pandas matplotlib
```

（安装目录保持程序原地更新不变；补装的包在卸载时随安装目录一起移除。）

## 运行期设计要点

| 主题 | 行为 |
|---|---|
| 后端托管 | Electron 主进程用内置 `python\python.exe` 起 `app\main.py`，日志写 `%APPDATA%\SugarAgent\logs\backend-<日期>.log` |
| 端口 | 默认 8192，被占用时自动顺延到 8199；同时通过 `MYAGENT_SERVER_PORT` 告知后端与内部链接 |
| 环境变量 | 只继承系统变量，模型/搜索/云厂商密钥一类变量被显式过滤，保证新装用户一定是"未配置"状态 |
| 首启向导 | 未检测到可用模型配置时，窗口直接打开应用自带的 `/setup` 配置向导 |
| 技能模板 | 首次启动把 `workspace-template/skills` 铺到 `Documents\SugarAgent\workspace\skills`（已存在则不动） |
| 托盘 | 关闭窗口＝最小化到托盘；托盘菜单：打开主界面 / 配置向导 / 浏览器打开 / 重启内置服务 / 打开日志 / 打开工作目录 / 退出 |
| 退出 | 退出时按进程树结束内置 Python（`taskkill /T /F`）；后端异常退出会弹恢复对话框 |
| 数据保留 | 工作目录在"文档"下，卸载/重装不影响会话与技能；`%APPDATA%\SugarAgent` 保留 |
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

版本号在 `packaging/package.json` 的 `version`（当前 `1.0.0`），会体现在安装包文件名、卸载项显示名与窗口标题中；发新版时改这里并重新构建。
