# Agent：注册、自检、卸载

## 结构与安装位置

- 插件 manifest：`.myagent-plugin/plugin.json`；MCP 配置：`.mcp.json`；Skill：`skills/bili-scroll/SKILL.md`。
- MCP 使用宿主同进程的 Streamable HTTP，路径 `/api/sugar-bili-scroll/mcp/`。配置的 `host_path` 自动跟随 `MYAGENT_SERVER_PORT`，默认 8192，不另外启动后台进程。
- `host.py` 继续负责控制台、调度、入站队列和宿主 ASR；模型工具由 MCP 注册。调用使用宿主提供的一次性 `_meta` 身份票据，绑定服务、工具和参数。不要把会话 ID、run ID 或票据加入模型工具参数。
- 需要物理位于 SugarAgent 项目 `plugins/sugar-bili-scroll/`，宿主才允许 trusted_host。普通外部插件目录、ZIP 上传或仅复制 `.mcp.json` 不能获得该信任；不要用伪造 manifest 绕过位置检查。当前形态用于 SugarAgent 内部连接，其他 MCP 客户端不具有工具调用身份。

## 注册

1. 检查当前源码、宿主依赖、插件安装位置；全新安装应把完整目录放在上述 bundled 位置，避免出现重复 ID。manifest声明`mcp==1.28.1`、`bilibili-api-python==17.4.2`和`qrcode`，由宿主Python环境提供；本地Whisper为可选。依赖安装使用项目内置Python，不要装进其他Python环境。
2. 读取 `GET /api/plugins/catalog`和`GET /api/plugins/sugar-bili-scroll/availability`。可用性报告不能代替实际登录验证。`POST /api/plugins/sugar-bili-scroll/diagnose`会创建诊断会话，仅在用户要求创建诊断会话时使用；默认自检不调用它。
3. 如果用户要求启用，调用 `POST /api/plugins/sugar-bili-scroll/enabled`，JSON `{"enabled":true}`。服务随插件生命周期启动。首次部署本版本若包含宿主 Python 代码更新，需要由托盘重启 Agent；已有“暂不重启”约束时保留代码并报告。
4. 运行助手 `register`，或 `POST /api/mcp/servers/sugar-bili-scroll/bili/register`。检查响应 `registered=true`，再读 `GET /api/mcp/tools`：目标服务有 14 个工具，且已连接。注册审批不足时提示用户在宿主安全设置处理，不能手改审批状态。
5. 检查工具总开关/单工具开关是否启用。注册成功不等于账号登录或自动回复已开启。

## 自检与故障定位

先运行 `doctor`。它仅访问本地状态接口，不扫码、不运行值班、不向 B站发送消息。

| 表现 | 检查顺序 |
|---|---|
| 服务没有注册 | 插件启用状态 → MCP总开关/注册审批 → 服务连接错误 → 后端是否仍运行旧版 → `register`重试 |
| 工具可见但调用失败 | 当前设置/白名单/额度 → 会话运行身份 → 评论目标/收件人 → B站接口错误；不要根据目录可见推断有权限 |
| 私聊没回复 | 当前接收账号 UID 是否正确 → 登录是否过期 → `inbound_reply` → 渠道包含dm → 首次只记游标 → 冷却/每小时上限/待处理任务/模型错误 |
| @或回复没响应 | 渠道包含at或reply → 独立 `inbound_public_reply` → 是否能确定视频和评论楼层 → 去重/冷却/队列状态 |
| 白名单仍无工具 | 白名单填的是发信者UID，不是当前接收账号UID；查看最新设置；非白名单设计为零工具 |
| 转写失败 | `transcribe`开关 → 时长限制 → host引擎的语音输入服务/ffmpeg → local引擎模型依赖与下载状态 |
| 重复或不确定发信 | 查`GET /api/sugar-bili-scroll/inbound`中的队列/回执；unknown状态需核对B站实际结果，不能盲目重试 |

`GET /api/sugar-bili-scroll/status` 查看登录、当前UID、任务、繁忙和ASR状态；`GET /api/sugar-bili-scroll/accounts`仅返回账号摘要；`GET /api/sugar-bili-scroll/tasks`查任务；`GET /api/runtime-status`查宿主会话是否正在运行。不要读取或输出凭据原文。

## 停用与卸载

用户要求暂时停用时运行 `disable`。它请求宿主停用插件，停止调度和 MCP 服务并移除注册工具；数据保留。不要将“停用”报告为“卸载”。

用户明确要求卸载时：

1. 先检查运行态；活跃的B站任务先待其结束或按已授权范围中止。只卸载本插件，不中断其他会话。
2. 运行 `disable`，确认插件服务停止；默认保留 `workspace/.config/plugins/sugar-bili-scroll/data/`（以状态接口实际 home 为准）。其中包括账号登录态、SQLite回执、任务、提示词、表情和日报。
3. 运行 `uninstall`，它调用 `DELETE /api/plugins/sugar-bili-scroll`。可写安装目录下的插件由宿主移到可恢复的 `.myagent-trash`；以返回的 `trash_path/recoverable` 为准。
4. **当前 bundled 源码安装通常不在宿主可写安装目录，DELETE 会拒绝。** 如实报告“已停用，源码目录尚未移除”；不要绕过安装器静默删除。若用户明确要求移走 bundled 源码，可在确认解析路径恰好是当前项目 `plugins/sugar-bili-scroll/` 后，将该目录移到项目外的明确备份位置，再按用户已授权的时机重启宿主。保留运行数据目录，记录恢复路径。不得递归删除计算出来的目录。
5. 自检确认没有该服务注册工具；恢复时将源码还原到原位置，再启用/注册。删除运行数据或撤销B站设备登录均是另外的操作，需要明确授权。
