# 2026-10-14 批次归档：桌面壳通知启动链 + 自动追问执行计时

- 归档：2026-10-14；本批 3 个提交（`ac76218`、`84885d5` + 本 docs 提交）；其前另有未推送的空行裁剪修复 `889ca64`。
- 结论：桌面壳三组增强（通知启动器静默转交、双 exe 品牌与旧快捷方式清理、窗口隐藏状态上报）+ 自动追问执行过程轮次计时修复；全量回归全绿。按用户要求**暂缓打包**（版本保持 1.5.4，待打包）。

## 一、提交清单

| # | 提交 | 主题 |
|---|---|---|
| 1 | `ac76218` | feat(desktop)：通知启动器静默转交、双 exe 品牌、窗口隐藏状态上报与旧 Electron 快捷方式清理 |
| 2 | `84885d5` | fix(webui)：自动追问执行过程轮次计时 + dist 重建（main-D7ns97ey.js） |
| 3 | 本提交 | docs：05/07 v7（UC-5G8/UC-5G9）、05/02 v24（UC-5B15）、00-总览 v50、本 changelog、现场文档 |

## 二、主题一：桌面壳通知启动链（`ac76218`）

- **通知启动器静默转交**：`StartupLauncher.cs` 识别合法 `sugaragent-desktop://open-ui` 调用（`--launcher-smoke` 除外）时直接转交 `SugarAgentRuntime.exe`——不建 Form、不建启动管道、不请求系统忙碌光标；`--launcher-report` 记录 `{nativeSplashShown:false, protocolForwarded:true}`。普通双击保留完整启动反馈；旧安装器协议仍指向 `SugarAgent.exe` 时同样有效。
- **双 exe 品牌**：`afterPack` 换入启动器后，对 `SugarAgentRuntime.exe` 显式应用图标/产品名/版本/版权（`signAndEditResources`），钩子等待品牌化完成再编译启动器。
- **稳定通知身份**：安装器写入 `HKCU\Software\Classes\AppUserModelId\com.sugaragent.desktop`（DisplayName=SugarAgent、IconUri=tray.ico），卸载清理。
- **旧快捷方式清理**：新增 `desktop-shortcuts.js`——仅删除目标指向本安装目录（桌面/开始菜单、绝对路径、大小写不敏感）的旧 `Electron.lnk`；其它 Electron 应用不受影响。
- **窗口隐藏状态上报**：主进程 show/hide 经每次启动令牌 `POST /api/ui-desktop-window`（串行队列，迟到 hide 不覆盖新 show）；`webui` 记录 `_desktop_ui_hidden`，隐藏视同“无打开页面”（驻留渲染器心跳不再冒领抑制），关闭到托盘按宽限发“仍在后台运行”，重新显示取消待发；具体完成/待处理通知优先；失败记日志。`sendUiPresence` 携带 `desktop` 标记。

## 三、主题二：自动追问执行过程计时（`84885d5`）

- 根因与修复见 `performance/自动追问执行过程计时-2026-10-14.md`：自动追问沿用同一 run，过程框原用 run 总起点计算；重连与定期对账又会被 run 总起点覆盖。
- 后端：提交用户轮次时保存时间戳，随事实序号以 `created_at` 随实时 `user` 事件下发。
- 前端：分组经 `turn:<seq>`（未编号时按当前用户消息位置）锚定 user 消息取 `created_at` → `procTurnStartedAt`；`applyRunStartedAtToProcessGroup` 优先分组自身起点；已封存未恢复运行的分组不重启计时；无锚点分组回退 run 起点。
- dist 重建（`main-D7ns97ey.js`；戳 v5.20261014）。

## 四、验证

- 全量 pytest：**2459 passed / 6 skipped / 0 failed**（619.9s）。
- node：**39/39**（含新增 `desktop_shortcuts.cjs`）。
- 定向：attention 通知 5 例新增 + enablement 契约 + 桌面外壳 + 启动器套件 = **53 passed / 1 skipped**；`Frontend dist is in sync.`。
- 提交钩子：运行时戳一致（v5.20261014）、dist 同步通过。

## 五、状态与遗留

- 打包（桌面版 1.5.4 安装包）按用户要求**暂缓**；版本号保持 1.5.4。
- 本地未推送提交：`889ca64` + 本批 3 个（远端停在 `a07d67e`）。
- 未跟踪遗留：`patches/`、`tools/ffmpeg-8.1-essentials_build/`。
