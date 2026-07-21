# 飞书机器人接入

SugarAgent 使用飞书自建应用机器人和官方 Python SDK 的 WebSocket 长连接接收消息。连接由 SugarAgent 主动发起，不需要公网回调地址，也不要求启用 Direct Remote Control。

当前版本支持：

- 飞书单聊和群聊文本消息
- 群聊默认必须 @ 机器人
- 用户与群聊 allowlist
- 飞书会话到 SugarAgent 会话的持久化绑定
- 飞书 `message_id` 持久化去重
- 自动创建会话、发送消息和运行中 append steer
- 新建会话、查看会话、停止运行
- 通过文字命令允许或拒绝工具审批
- Agent final、失败、中断和审批通知回传飞书

暂不支持图片、文件、语音、交互式审批卡片和流式编辑同一条消息。

## 1. 创建飞书应用

在飞书开放平台创建“企业自建应用”，然后：

1. 在“应用能力”中启用机器人。
2. 在“权限管理”中至少开通：
   - `im:message.p2p_msg:readonly`：读取用户发给机器人的单聊消息。
   - `im:message.group_at_msg:readonly`：接收群聊中 @ 机器人的消息。
   - `im:message:send_as_bot`：以应用身份发送消息。
3. 在“事件与回调”中选择“使用长连接接收事件”。
4. 添加应用身份事件 `im.message.receive_v1`。
5. 发布应用版本，并确保目标用户处于应用可用范围内。
6. 从“凭证与基础信息”复制 App ID 和 App Secret。

如果只需要单聊，可以不申请群聊消息权限。机器人必须被加入目标群聊，才能在群内接收和回复消息。

## 2. 配置 SugarAgent

编辑 `app/.env`：

```dotenv
FEISHU_ENABLED=1
FEISHU_APP_ID=cli_xxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxx

# 强烈建议正式使用时至少配置一个 allowlist。
FEISHU_ALLOWED_OPEN_IDS=ou_xxxxxxxxxxxxx
FEISHU_ALLOWED_CHAT_IDS=

FEISHU_GROUP_REQUIRE_MENTION=1
FEISHU_SESSION_SCOPE=chat
```

重启 SugarAgent。日志中出现 `Feishu transport adapter started`，且飞书 SDK 显示 WebSocket connected 后即可使用。

`FEISHU_ENABLED=0` 或未配置时不会导入飞书 SDK、创建飞书状态数据库或建立网络连接。修改开关或凭证后需要重启。

## 3. 对话方式

直接向机器人发送文本即可。首次消息会自动创建 SugarAgent 会话并绑定：

- 单聊默认按飞书用户绑定。
- 群聊默认整个群共享一个 SugarAgent 会话。
- 设置 `FEISHU_SESSION_SCOPE=thread` 后，带 `thread_id` 的话题各自使用独立会话；普通群消息仍按群绑定。

群聊默认只有 @ 机器人时才处理。消息被接受后机器人先回复“已收到，正在处理”，完成后再回复最终结果。

支持以下命令：

```text
/new [会话名称]
/session
/whoami
/stop
/approve <审批ID>
/reject <审批ID>
/help
```

也支持中文的 `新会话`、`会话`、`停止` 和 `帮助`。

首次配置 allowlist 时，可以暂时留空，在可信单聊中发送 `/whoami` 获取 `open_id` 和 `chat_id`，写入 `.env` 后立即重启并启用 allowlist。

## 4. 环境变量

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `FEISHU_ENABLED` | `0` | 飞书入口总开关，修改后需重启 |
| `FEISHU_APP_ID` | 空 | 飞书自建应用 App ID |
| `FEISHU_APP_SECRET` | 空 | 飞书自建应用 App Secret，只应保存在 `.env` |
| `FEISHU_ALLOWED_OPEN_IDS` | 空 | 允许使用机器人的 open_id/union_id，逗号分隔 |
| `FEISHU_ALLOWED_CHAT_IDS` | 空 | 允许接入的 chat_id，逗号分隔 |
| `FEISHU_GROUP_REQUIRE_MENTION` | `1` | 群聊是否必须 @ 机器人 |
| `FEISHU_SESSION_SCOPE` | `chat` | `chat` 或 `thread` |
| `FEISHU_RESPONSE_TIMEOUT_SEC` | `7200` | 等待 Agent 最终事件的最长时间 |
| `FEISHU_MAX_REPLY_CHARS` | `3500` | 单条回复分段长度 |
| `FEISHU_STATE_DIR` | `.myagent/feishu` | 会话绑定与消息去重数据库目录 |

## 5. 状态与安全

状态默认保存在 `.myagent/feishu/feishu.sqlite3`。当 Direct Remote Control 未启用时，飞书会在同一目录下创建独立 control-plane 数据库，用于命令幂等和审计；两项功能同时启用时会复用现有 `SessionControlService`。

建议：

- 正式环境必须配置用户或群 allowlist。
- 不要把 App Secret 发到聊天中或提交到 Git。
- 群聊保持 `FEISHU_GROUP_REQUIRE_MENTION=1`。
- 工具审批包含高风险操作时，只允许可信用户使用机器人。
- 手机或账号丢失后，应及时从飞书应用可用范围和 SugarAgent allowlist 中移除对应用户。

## 6. 故障排查

- 启动时报缺少 `lark-oapi`：重新运行项目依赖安装流程。
- 没有收到消息：确认应用已发布、用户在可用范围内、事件使用长连接且订阅了 `im.message.receive_v1`。
- 单聊可用但群聊无响应：确认机器人已入群，消息中 @ 机器人，并已申请群 @ 消息权限。
- 能接收但不能回复：确认已申请 `im:message:send_as_bot`。
- 日志提示配置缺失：检查 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`，修改后重启。
