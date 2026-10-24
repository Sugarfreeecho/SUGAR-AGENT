# Workspace Context 示例插件

把本目录作为本地原生插件安装并启用。在当前会话的工作目录创建 `AGENT_CONTEXT.md`，写入希望模型获知的简短业务资料；下一次主任务步骤会采集它。文件不存在或为空时撤销本插件的贡献。

提供器只读取当前会话工作目录根部的这个文件，最多 16384 个字符；宿主再按 800 个估算 token 的提供器预算及总预算裁剪。文件内容不变时不重复追加，改变或删除后在下一步骤更新。启用插件或修改文件不会自动唤醒空闲模型。

Python 使用 `@plugin.context(id=..., title=..., max_tokens=..., timeout_seconds=...)`。manifest 的 `capabilities.context` 必须为 `true`；代码仍经过既有的插件信任与签名校验。

返回字符串、`{text, revision?}` 或 `None`。`revision` 表达插件自己的版本，宿主仍按实际文本判重；`None` 是明确清除，抛出错误则按采集失败处理。详见 [Plugin API](../../../docs/plugin_api_v1.md)。
