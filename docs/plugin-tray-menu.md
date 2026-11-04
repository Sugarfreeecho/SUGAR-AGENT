# 插件托盘菜单（`capabilities.ui.tray`）

插件在宿主托盘图标右键菜单里增加条目的唯一契约。实现分三层，共用同一个解析器：

| 文件 | 职责 |
|---|---|
| `app/tray_slot.py` | 纯标准库解析 + 校验，唯一事实来源 |
| `app/plugins/loader.py` | 调用校验，把问题写进插件 warning（设置页可见） |
| `app/plugins/ui.py` | 投影成 `slot: "tray"` 的 UI 贡献，供设置页展示 |
| `app/tray_plugins.py` | 托盘进程侧：解析占位符、解析路径、启动子进程 |
| `app/tray_launcher.py`（Windows）<br>`app/platform_tray_linux.py`<br>`app/platform_tray_macos.py` | 各自的菜单渲染与命令分发 |

## 清单写法

```json
"capabilities": {
  "ui": {
    "tray": [
      {
        "id": "shield",
        "label": "护屏模式",
        "description": "可选，设置页展示用",
        "command": ["{pythonw}", "scripts/mode.py", "set", "shield"],
        "windowless": true,
        "check": {"file": "{state}/power-mode.json", "key": "mode", "equals": "shield"}
      },
      {
        "id": "power",
        "label": "电源模式",
        "items": [
          {"id": "awake", "label": "常亮模式", "command": ["{pythonw}", "scripts/mode.py", "set", "awake"]}
        ]
      }
    ]
  }
}
```

`ui.tray` 也可以是单个对象而不是数组。带 `items` 的条目渲染成子菜单，层级只允许一层。

## 字段

| 字段 | 必填 | 约束 |
|---|---|---|
| `id` | 是 | `[A-Za-z0-9][A-Za-z0-9_.-]{0,63}`，同一插件内唯一 |
| `label` | 是 | 1–40 字符 |
| `description` | 否 | ≤200 字符 |
| `command` | 动作项必填 | 1–16 个非空字符串，**不经过 shell** |
| `windowless` | 否 | 默认 `true`，Windows 下用 `CREATE_NO_WINDOW` |
| `check` | 否 | 见下 |
| `items` | 分组项必填 | 1–8 个动作项，不允许嵌套分组 |

上限：每个插件最多 8 条（分组按子项数计算），全局最多 8 条。

## 占位符

| 占位符 | 展开为 |
|---|---|
| `{python}` | 项目内置 `python.exe` |
| `{pythonw}` | 项目内置 `pythonw.exe`（无控制台，推荐给 GUI/后台脚本） |
| `{powershell}` | `%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe` |
| `{plugin}` | 插件根目录绝对路径 |
| `{root}` | 项目根目录 |
| `{state}` | `%LOCALAPPDATA%\SugarAgent\state` |

## 执行语义

- **无 shell**：`command` 是 argv 数组，`shell=False`，不做 `cmd /c` 或 PowerShell 拼接
- **路径收敛**：看起来像路径的相对 token 会相对插件根解析，解析后逃出插件根的条目会被整条丢弃
- **可执行文件必须存在**：首个 token 解析后必须存在且为绝对路径，否则该条不显示
- **脱离父进程**：子进程 `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`，标准流接 `DEVNULL`，托盘退出不影响它
- **失败不致命**：清单损坏、脚本缺失、导入失败都只会让对应条目消失，菜单照常打开

## 勾选状态

`check` 让菜单项显示勾选，用于"当前模式"这类状态：

```json
"check": {"file": "{state}/power-mode.json", "key": "mode", "equals": "shield"}
```

- `file`：状态文件路径，支持占位符
- `key`：JSON 的顶层键；省略则对整个值求值
- `equals`：省略时按真值判断，否则与字符串化后的值比较

状态文件由插件自己维护，宿主只读不写。**每次弹出菜单都会重新读取**，所以插件改完状态，下一次右键即可见。

## 校验与报错

写错不会静默失败：`loader` 会把问题写进插件的 `compatibility.warnings`，在插件列表里能看到，例如：

```
Tray entry 'broken': command must be a list of 1-16 tokens
Tray entry 'bad id': id is invalid in tray
Tray entry 'group': nested tray groups are not supported
```

## 平台支持

| 平台 | 菜单渲染 | 勾选状态 | 子菜单 |
|---|---|---|---|
| Windows (`tray_launcher.py`) | Win32 PopupMenu | 支持 | 支持 |
| Linux (`platform_tray_linux.py`) | Gtk Menu | 暂不支持 | 支持 |
| macOS (`platform_tray_macos.py`) | NSMenu | 暂不支持 | 支持 |

非 Windows 适配器在构建插件菜单时整段包在 `try/except` 里：插件出问题不会影响托盘的其余菜单。

## 与插件启停的关系

- 插件的启用状态按 `PLUGIN_<ID>_ENABLED` 环境变量 → `.config/plugins-state.json` → tier 默认值（`standalone` 默认停用）判定
- 菜单每次弹出都重新扫描插件目录，所以在设置里停用插件后，下一次右键就不再出现它的条目，**不需要重启托盘**
