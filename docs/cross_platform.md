# Linux 与 macOS 安装和运维

SugarAgent 的 WebUI 始终只监听 `127.0.0.1:8192`。Linux 服务器不应将该端口直接暴露到公网。

## 支持范围

- Windows 10/11：继续使用 `RUN.bat` 和 Win32 托盘。
- Ubuntu 22.04/24.04 x86_64：支持桌面模式和无桌面的 server 模式。
- macOS 13+：支持 Apple Silicon 和 Intel 的桌面源码安装。

其他 Linux 发行版、Linux ARM、签名/公证的 macOS `.app` 暂不在支持范围内。

## Ubuntu

安装器会创建 `.venv`、安装 Python 依赖，并生成用户级
`~/.config/systemd/user/sugaragent.service`。

桌面安装：

```bash
bash scripts/install_unix.sh --mode desktop
bash RUN.sh
```

Server 安装：

```bash
bash scripts/install_unix.sh --mode server
bash RUN.sh --server
```

Server 模式会通过 `loginctl enable-linger` 允许用户服务在 SSH 退出后继续运行。
该步骤需要 sudo。安装系统依赖已由管理员完成时，可传入
`--skip-system-packages`。

远程访问使用 SSH 本地端口转发：

```bash
ssh -L 8192:127.0.0.1:8192 user@server
```

随后在本机浏览器打开 `http://127.0.0.1:8192/`。

## macOS

先安装 Python 3.10 或更高版本，推荐 python.org 的 Python 3.12 universal2。
安装器不会自动安装 Homebrew，也不会创建或签名 `.app`。

```bash
bash scripts/install_unix.sh --mode desktop
bash RUN.sh
```

安装器会在 `~/Library/LaunchAgents` 中创建后台服务和菜单栏进程的
LaunchAgent。后台输出保存在 `logs/agent_terminal.log`。

## 统一管理命令

Linux/macOS 均使用：

```bash
scripts/agentctl start
scripts/agentctl stop
scripts/agentctl restart
scripts/agentctl status
scripts/agentctl logs
scripts/agentctl update
scripts/agentctl tray
```

托盘中的“重启”和“更新”默认隐藏，与 Windows 一样可在高级设置中通过
`MYAGENT_TRAY_SHOW_UPDATE_RESTART=1` 启用。

## 卸载

```bash
bash scripts/uninstall_unix.sh
```

卸载只移除用户服务、托盘自启动和 `.venv`，保留 `workspace/`、模型配置、
插件和日志。传入 `--keep-venv` 可保留虚拟环境。

## 故障排查

- Linux 服务状态：`systemctl --user status sugaragent.service`
- Linux 日志：`journalctl --user -u sugaragent.service -n 200 -f`
- macOS 服务状态：`launchctl print gui/$(id -u)/com.sugaragent.server`
- 端口检查：`curl -I http://127.0.0.1:8192/`
- Linux 托盘缺失：确认已安装 `python3-gi`、`gir1.2-gtk-3.0` 和
  `gir1.2-ayatanaappindicator3-0.1`，并从 GNOME 图形会话启动。
- Headless 模式没有原生文件选择器；请在 WebUI 中手动输入工作区路径。
