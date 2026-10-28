# Feishu Remote Transport（feishu-transport）

把飞书当成 SugarAgent 的远程入口：飞书单聊 / 群聊 / 话题对应到宿主会话，消息进来起 run，结果回飞书。

- 配置全部来自 `.env`：`FEISHU_ENABLED`、应用凭据、`FEISHU_SESSION_SCOPE`（`chat` / `thread`）、`FEISHU_ALLOWED_OPEN_IDS`、`FEISHU_ALLOWED_CHAT_IDS`。逐步填写与发布应用的完整步骤见 [飞书对接启用指南](飞书对接启用指南.md)。
- 生命周期：`start()` 用 `FeishuRuntimeManager` 建立长连接并注册传输，`stop()` 关闭；插件停用后不导入飞书 SDK、不建连接、不创建状态目录。
- 实现放在本目录 `feishu_transport/`，宿主在没有本插件时不 import 任何飞书代码。飞书 SDK（`lark-oapi`）由 `requirements.txt` 单独安装，清单里标为可选依赖。
- 状态：`standalone` 级，默认停用。

会话接入使用宿主公共控制服务，独立于手机远控开关。来信按飞书 message ID 提交持久 queue；插件保存 operation、事件游标和待发送回复。SDK 断线后恢复观察原操作并重试投递，沿用相同回复去重标识；最终结果来自该 operation 的完成回执。插件停用会撤销来源授权，正常应用退出保留尚未执行输入和投递记录。会话范围默认宿主工作区，飞书白名单校验仍在渠道入口执行。

## 热重载

- 改本目录里的代码（含 `feishu_transport/`）→ 设置页「重新发现 / 热重载」即生效，不必重启：适配器导入前会清掉 `feishu_transport.*` 的旧模块，`stop()` 关旧连接、`start()` 用新代码重连。
- 改 `.env` → **必须重启**：环境变量只在进程启动时读取一次。
- 判定口径见 [插件热重载](../../docs/plugin_hot_reload.md)。
