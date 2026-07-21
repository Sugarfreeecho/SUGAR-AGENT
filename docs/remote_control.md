# Remote Control v1

Remote Control v1 是 SugarAgent 的正式远控入口。它复用现有会话与 Agent Runtime，不另起一套执行逻辑；当前提供经过设备认证的 WebSocket 控制协议和手机浏览器客户端。飞书等聊天入口后续应作为适配器调用同一个 `SessionControlService`。

## 安全模型

- 默认关闭；未设置 `MYAGENT_REMOTE_CONTROL_ENABLED=1` 时不注册 Remote Control 路由、不创建状态文件，也不接受连接。修改开关后必须重启 SugarAgent。
- SugarAgent 继续只监听 `127.0.0.1:8192`。不要为了手机访问把整个现有 Web UI 绑定到 `0.0.0.0`，因为普通 Web UI 路由尚未全部纳入 Remote Control 鉴权。
- 推荐用 Tailscale Serve 将本机端口作为 tailnet 内的 HTTPS 服务提供。不要使用公网 Funnel。
- 配对必须先在电脑本机创建一次性配对码；配对码默认 10 分钟过期，使用一次立即失效。
- 手机浏览器得到的是 `HttpOnly`、`SameSite=Strict` Cookie，页面 JavaScript 读不到设备令牌。原生客户端可在 WebSocket 配对响应中取得一次性的明文令牌；服务端只保存 SHA-256 哈希。
- 设备权限分为 `read`、`write`、`approvals`、`admin`。手机默认获得前三项，不获得设备管理权限。
- 所有改变状态的方法要求 `idempotency_key`；成功结果持久化 24 小时，重试不会重复创建会话或重复发送消息。
- 配对、连接、写操作、拒绝和设备撤销均写入 SQLite 审计日志。

状态数据库默认位于 `.myagent/remote-control/remote-control.sqlite3`，已被 `.gitignore` 排除。可用 `MYAGENT_REMOTE_CONTROL_STATE_DIR` 改到其他目录。

## 正式启用

在 `app/.env` 中加入：

```dotenv
MYAGENT_REMOTE_CONTROL_ENABLED=1
```

重启 SugarAgent。然后在电脑上安装并登录 Tailscale，手机登录同一个 tailnet。在电脑终端运行：

```powershell
tailscale serve --bg 8192
tailscale serve status
```

当前 Tailscale CLI 支持把本机端口作为 Serve target，并由 tailnet 内的 HTTPS 地址反向代理到 `127.0.0.1`。若本机版本不接受上述简写，先执行 `tailscale serve --help`，使用它显示的等价 `localhost:8192` target 形式。

## 配对手机

1. 保持 SugarAgent 运行，在电脑本机 PowerShell 创建配对码：

```powershell
$body = @{ label = "My phone" } | ConvertTo-Json
$pairing = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8192/api/remote/v1/pairings `
  -ContentType application/json `
  -Body $body
$pairing
```

2. 在手机打开 `tailscale serve status` 显示的 HTTPS 地址，并追加：

```text
/api/remote/v1/client
```

3. 输入电脑显示的配对码。成功后即可选择会话、补拉历史、订阅实时事件、发送消息、steer、停止运行和处理工具审批。

手机断线后会自动重连。客户端先建立实时订阅，再补拉持久化历史，并用 `event_bus_seq` 去重；这样历史加载期间到达的新事件不会丢失。

## 管理与撤销设备

设备管理 HTTP 接口只接受来自电脑的直接 loopback 请求；带 `Forwarded`、`X-Forwarded-*` 或 Tailscale identity headers 的代理请求即使后端看到的 socket 来源是 `127.0.0.1` 也会被拒绝。

列出设备：

```powershell
Invoke-RestMethod http://127.0.0.1:8192/api/remote/v1/devices
```

撤销设备：

```powershell
Invoke-RestMethod `
  -Method Delete `
  -Uri http://127.0.0.1:8192/api/remote/v1/devices/<device_id>
```

浏览器里的“退出设备”只清除该浏览器 Cookie；如果手机丢失，应从电脑执行撤销。撤销后，该设备下一次请求或重连会认证失败。

## WebSocket v1 协议

连接地址：`/api/remote/v1/ws`。

服务端首先发送 `connect.challenge`，客户端必须在 15 秒内回传 nonce：

```json
{
  "type": "req",
  "id": "connect-1",
  "method": "connect",
  "params": {
    "nonce": "<challenge nonce>",
    "device_token": "<native client token>"
  }
}
```

普通请求、响应和事件：

```json
{"type":"req","id":"42","method":"session.send","params":{"session_id":"...","message":"继续"},"idempotency_key":"..."}
{"v":1,"type":"res","id":"42","ok":true,"result":{"accepted":true,"run_id":"..."}}
{"v":1,"type":"event","event":"session.event","session_id":"...","event_id":"...","payload":{"type":"status","content":"..."}}
```

已实现的方法：

- 读取：`system.health`、`session.list`、`session.get`、`session.history`
- 实时：`session.subscribe`、`session.unsubscribe`
- 写入：`session.create`、`session.send`、`session.steer`、`session.interrupt`
- 审批：`approval.list`、`approval.resolve`
- 管理：`device.list`、`device.revoke`、`audit.list`

单帧默认上限 256 KiB；单连接默认每分钟最多 120 个请求；慢客户端的出站队列溢出时服务端主动断开，客户端应从历史与最近事件恢复。

## 配置项

| 环境变量 | 默认值 | 说明 |
|---|---:|---|
| `MYAGENT_REMOTE_CONTROL_ENABLED` | `0` | 启用 Remote Control；修改后需重启 |
| `MYAGENT_REMOTE_CONTROL_STATE_DIR` | `.myagent/remote-control` | 设备、幂等和审计数据库目录 |
| `MYAGENT_REMOTE_CONTROL_PAIRING_TTL_SEC` | `600` | 配对码有效期，限制为 60–3600 秒 |
| `MYAGENT_REMOTE_CONTROL_IDEMPOTENCY_TTL_SEC` | `86400` | 幂等结果保留时间 |
| `MYAGENT_REMOTE_CONTROL_MAX_FRAME_BYTES` | `262144` | WebSocket 单帧上限 |
| `MYAGENT_REMOTE_CONTROL_OUTBOUND_QUEUE` | `1000` | 每连接出站事件队列上限 |
| `MYAGENT_REMOTE_CONTROL_ALLOWED_ORIGINS` | 空 | 额外允许的浏览器 Origin，逗号分隔；同 Host Origin 自动允许 |
| `MYAGENT_REMOTE_CONTROL_BOOTSTRAP_TOKEN` | 空 | 可选的管理员 bootstrap token；只建议临时用于原生运维客户端 |

## 飞书适配

飞书长连接适配器已经实现，并与 Direct WebSocket 共享 `SessionControlService`；未启用 Direct Remote Control 时，飞书会创建独立的本地控制服务，仍然不会调用未鉴权的 `/chat`。配置、权限和命令参见 [飞书机器人接入](feishu.md)。
