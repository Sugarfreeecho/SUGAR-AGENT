# 电源模式（power-modes）

Windows 专属插件。三种**互斥**模式，从 Agent 托盘图标右键 →「电源模式」子菜单切换，当前模式带勾。

## 三种模式

| 模式 | 屏幕 | 系统 | 适合 |
|---|---|---|---|
| 护屏模式 | 全屏纯黑遮罩，OLED 像素不发光 | 挂住唤醒锁，CPU 满速、Wi-Fi 不断 | 挂机跑任务，又不想屏幕一直亮着 |
| 常亮模式 | 持续常亮，不熄屏 | 挂住显示器 + 系统唤醒锁，不进待机 | 看长文档、演示、盯进度 |
| 任务完成后睡眠 | 保持原样，直到触发 | Agent 全部任务结束后等待 N 秒，关屏并睡眠，**不关机** | 睡前丢一个任务，跑完自动睡 |
| 退出模式 | — | 释放所有唤醒锁，回到系统默认 | — |

勾选状态来自 `%LOCALAPPDATA%\SugarAgent\state\power-mode.json`，每次弹出托盘菜单都会重新读取。

## 为什么不用系统自带的"关闭显示器"

本机（HUAWEI DRC-WXX）没有 S1/S2/S3，只有 S0 低电量待机；`powercfg /a` 显示 S0 待机"连接的网络：不支持"。系统关屏会直接进入 Modern Standby：断网、降频、风扇停，后台任务会断。

护屏模式换成"看起来黑但系统仍在跑"：纯黑遮罩 + 唤醒锁，网络与 CPU 不受影响。

## 实现

`scripts/power_modes.py` 是一个单实例守护进程（命名互斥体 `SugarAgentPowerModes`）：

- **护屏**：拉起 `scripts/shield.ps1` 全屏遮罩；遮罩被任意按键/鼠标移动或点击关闭后，守护进程把模式回落为 `none`，托盘勾选随之消失
- **常亮**：`SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)`
- **任务完成后睡眠**：每 5 秒查询 `http://127.0.0.1:<port>/api/runtime-status` 的 `active_run_count`；连续 `idle_seconds`（默认 180）为 0 后调用 `powrprof.SetSuspendState(False, False, False)` 进入睡眠。后端不可达时视为"状态未知"，**不睡眠**
- 触发睡眠后模式自动回落 `none`，避免唤醒后又立刻睡

## 状态与日志

| 文件 | 用途 |
|---|---|
| `%LOCALAPPDATA%\SugarAgent\state\power-mode.json` | 当前模式、`idle_seconds`、遮罩 pid、上次睡眠时间 |
| `%LOCALAPPDATA%\SugarAgent\state\power-modes.log` | 守护进程日志（上限 512 KB 自动轮转） |

## 手动命令

```powershell
# 切换模式
.\python\pythonw.exe plugins\power-modes\scripts\power_modes.py set shield
.\python\pythonw.exe plugins\power-modes\scripts\power_modes.py set awake
.\python\pythonw.exe plugins\power-modes\scripts\power_modes.py set autosleep --idle-seconds 300
.\python\pythonw.exe plugins\power-modes\scripts\power_modes.py set none

# 查看当前状态
.\python\python.exe plugins\power-modes\scripts\power_modes.py status
```

## 边界

- 只在本机 Windows 上验证；遮罩依赖 System.Windows.Forms，需要可交互桌面会话
- 合盖仍按电源计划进入睡眠，模式不拦截硬件事件
- 「任务完成后睡眠」只看 Agent 的运行中任务数，不判断你本人是否还在用电脑；不想要就提前切回「退出模式」

## 与 `app/runtime_power.py` 的分工

两者都调用 Windows 电源 API，但**不能合并**，职责与生命周期完全不同：

| | `app/runtime_power.py` | 本插件 |
|---|---|---|
| 触发 | 每次 agent run 自动开始/结束 | 用户从托盘显式选择 |
| 锁范围 | 仅 `ES_SYSTEM_REQUIRED`（不碰显示器） | 护屏/常亮按模式决定，含 `ES_DISPLAY_REQUIRED` |
| 生命周期 | 与 run 同生共死，进程退出自动释放 | 常驻守护进程，跨 run、跨进程 |
| 附加能力 | `RuntimeSuspensionMonitor`：检测睡眠后恢复，供 agent 续跑 | 无 |
| 依赖方向 | 核心运行时，插件停用也必须生效 | 可选插件，可被用户在设置里关掉 |

「任务完成后睡眠」正是靠这个分工工作：run 期间 `runtime_power` 持有系统锁让电脑别睡，run 结束后锁释放，本插件才发现 `active_run_count == 0` 并开始倒计时。合并会破坏这条链。
