# HOWTO · 在另一台电脑上打包 SugarAgent 桌面版

> 面向：**同样一份工程**的第二台 Windows x64 电脑（干净环境或已有源码均可）。
> 读完你能理解打包流水线，并独立完成「首次构建」与「日常更新」。
> 设计细节见同目录 [README.md](README.md)。

---

## 0. 先建立心智模型：一条流水线、三层拷贝

```
仓库代码(app/ plugins/ frontend/ packaging/)
   + python/ 便携运行时（不在 git）
   + workspace/skills 技能模板（不在 git）
        │
        ▼  ① node scripts\prepare-payload.mjs   ← 组装"载荷"（≈365MB）
build/payload/{app, plugins, python, workspace-template, runtime-manifest.json}
        │
        ▼  ② node scripts\build.mjs             ← electron-builder 套壳+签名（≈2min）
build/dist/win-unpacked/  （Electron 壳 + 内嵌载荷，≈682MB，可直接运行）
        │
        ▼  ③ 同上命令的后半段                   ← NSIS 固实压缩（≈9.5min，最耗时）
build/dist/SugarAgent-Setup-<版本>-x64.exe  （≈251MB，可分发）
```

- 每层都是**全量拷贝**，所以 build/ 目录会到 ~1.3GB（正常）。
- 耗时大头 = ③ NSIS 压包；只想快速验证时用 `--dir` 跳过 ③。

## 1. 前置条件（第二台电脑）

| 项 | 要求 | 从哪来 |
|---|---|---|
| 系统 | Windows x64 | — |
| Node.js | **≥ 22**（本机 v24） | nodejs.org 或镜像安装 |
| 工程代码 | 与打包机同版本 | `git clone https://github.com/Sugarfreeecho/SUGAR-AGENT.git`；或整目录拷贝 |
| **python/ 运行时** | 仓库根必须存在 `python\python.exe` | **不在 git**！从打包机拷 `python\` 整个目录（≈1.2GB） |
| **workspace/skills** | 技能模板目录（≈108MB，全部技能） | **不在 git**！从打包机拷 `workspace\skills\`（只拷这一层） |
| 网络（首次） | npm 拉 electron/electron-builder；pip 装 85 个依赖 | 可配镜像（见 §6） |

> 只拷 `workspace\skills\`，**不要**整拷 `workspace\`（里面还有会话/回收站等在本机数据）。

## 2. 首次打包（一次性，约 30–60 分钟，含下载）

```powershell
# 0) 自检运行时
.\python\python.exe --version          # 应为 Python 3.10.x

# 1) 装桌面壳工具链（仅一次；下载 electron 44 + electron-builder）
cd packaging
npm install

# 2) 一键构建：图标 → 载荷（含 pip 装依赖）→ NSIS 安装包
node scripts\build.mjs

# 3) 载荷级自检（真启动内置后端并探活）
node scripts\smoke-payload.mjs --port 8399
```

产物：`packaging\build\dist\SugarAgent-Setup-1.5.1-x64.exe`（当前版本以 `packaging/package.json` 为准）。

**离线/加速捷径（推荐给低网速机器）**：
1. 拷 `packaging\build\payload\`（≈365MB）→ 目标机后，用 `node scripts\build.mjs --skip-payload` 跳过 pip；
2. 再拷 `packaging\node_modules\`（≈450MB，同 Windows x64 通用）→ 连 `npm install` 都省；
3. electron-builder 首次会下工具（winCodeSign/nsis，几十 MB）；离线时连 `%LOCALAPPDATA%\electron-builder\Cache` 一起拷。

## 3. 日常更新（代码改动后重打包，≈13 分钟）

```powershell
cd packaging
node scripts\prepare-payload.mjs --skip-deps   # ① 只刷 app/plugins/技能模板（≈1.5min；复用已装依赖）
node scripts\build.mjs --skip-payload          # ② 重打安装包（≈11min；NSIS 压包是大头）
node scripts\smoke-payload.mjs --port 8399     # ③ 冒烟（≈0.5min）
```

更快的档位：

| 场景 | 命令 | 耗时 |
|---|---|---|
| 只验证功能，不出安装包 | `node scripts\build.mjs --dir` → 直接跑 `build\dist\win-unpacked\SugarAgent.exe` | ≈2–3 min |
| 跳过图标/载荷、只重压 | `node scripts\build.mjs --skip-payload --skip-icons` | ≈11 min |

## 4. 版本号与发布

- 版本号 = `packaging/package.json` 的 `version`（当前 **1.5.1**），连带 `package-lock.json` 里**自身 2 处**（顶层 + `packages[""]`；**不要**动依赖条目）。
- 改后安装包文件名、卸载项显示名、窗口标题自动跟随。
- 发布物：`build\dist\SugarAgent-Setup-<版本>-x64.exe` + `.blockmap`。

## 5. 验收清单

- [ ] `smoke-payload.mjs`：输出"健康检查通过：ok"
- [ ] `powershell -File scripts\smoke-desktop.ps1`：启动 win-unpacked，校验窗口目标与后端健康（需要桌面会话）
- [ ] 安装包大小 ≈251MB、时间戳为本次
- [ ] （可选）审计：载荷内无 `app\.env`、无 `sk-` 形态密钥——`Get-ChildItem build\payload\app -Recurse -Filter .env`

## 6. 常见问题

| 症状 | 处置 |
|---|---|
| `载荷不完整：缺少 …python.exe` | 仓库根 `python\` 没拷全 → 补齐后重跑 |
| pip 装依赖慢/失败 | `$env:SUGARAGENT_PIP_INDEX='https://pypi.tuna.tsinghua.edu.cn/simple'` 后再跑 |
| electron 下载慢 | `npm install` 前设 `$env:ELECTRON_MIRROR='https://npmmirror.com/mirrors/electron/'` |
| npm 慢 | `npm config set registry https://registry.npmmirror.com` |
| 重打时报文件被占用 | 关闭正在运行的 SugarAgent；杀软扫描期间稍等重试 |
| 前端改了没进包 | 打包只取 `app\templates\dist`：先在 `frontend\` 跑 `npm run build`（或 `prepare-payload --build-frontend`） |
| 技能模板没更新 | 模板拷自 `workspace\skills`（不是 app 内），确认该目录是最新 |
| 想要更小的包 | `$env:SUGARAGENT_MAX_COMPRESSION='1'`（更慢） |
| 想要"双击即装" | `$env:SUGARAGENT_INSTALLER_STYLE='oneclick'` 后重打 |

## 7. 关键文件速查

| 文件 | 作用 |
|---|---|
| `scripts\prepare-payload.mjs` | 组装载荷：拷 app/plugins/python、pip 装依赖、裁掉 `.env`/`__pycache__`/历史环境、生成 `runtime-manifest.json` |
| `scripts\build.mjs` | 一键：图标 → 载荷 → electron-builder；支持 `--dir/--skip-payload/--skip-icons/--build-frontend` |
| `scripts\make-icons.py` | PNG → 多尺寸 ICO（应用/托盘） |
| `scripts\patch-nsis.mjs` | NSIS 模板中文补丁（幂等） |
| `scripts\smoke-payload.mjs` / `smoke-desktop.ps1` | 载荷级 / 端到端自检 |
| `electron\main.js` | 桌面壳主进程：托管后端、动态端口、托盘、单实例、退出清理 |
| `electron-builder.config.cjs` | 安装器配置（按用户安装、快捷方式、压缩档、语言包裁剪） |
| `nsis\installer.nsh` | 安装向导定制（跳过"为谁安装"页） |
| `requirements.desktop.txt` | 内置依赖清单（派生自 app/requirements.txt，刻意排除 playwright/pandas 等重依赖） |

## 8. 这套方法是怎么被摸出来的（可复刻的"学习路径"）

1. **读设计**：先通读 `packaging/README.md`（产物清单、目录结构、变体命令全在里面）；
2. **读脚本**：`prepare-payload.mjs`（看拷贝/排除/自检逻辑）→ `build.mjs`（看编排顺序）→ `electron-builder.config.cjs`（看安装器形态与压缩档）；
3. **看现场**：检查 `packaging\node_modules`、`packaging\build\`、`python\python.exe` 是否齐——决定走"首次全量"还是"热更"；
4. **走热更**：`--skip-deps` 刷新载荷 → `--skip-payload` 重打 → `smoke-payload` 验收（本机实测 ≈13 分钟/轮）；
5. **对账**：载荷关键文件与仓库逐字节比对、`runtime-manifest.json` 看版本与依赖、安装包 sha256 留档。

> 一句话总结：**代码走 git，运行时走拷贝；更新只刷载荷、重压安装包；每次以 smoke 收尾。**
