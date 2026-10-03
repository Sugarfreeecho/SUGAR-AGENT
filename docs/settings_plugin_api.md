# 设置页插件接口

插件通过 manifest 的 `capabilities.ui.settings.section` 声明设置页签。宿主从
`GET /api/extensions` 获取已启用插件的声明，自动注册到设置页左侧导航。
安装、启停或热重载后会同步入口；较旧的异步响应不会覆盖新注册结果。

以下声明可放在 `.myagent-plugin/plugin.json` 中：

```json
{
  "schema_version": 1,
  "id": "example.settings",
  "name": "示例插件",
  "version": "1.0.0",
  "settings_schema": {
    "type": "object",
    "title": "示例插件设置",
    "properties": {
      "working_folder": {
        "type": "string",
        "format": "directory",
        "title": "工作目录"
      },
      "config_file": {
        "type": "string",
        "format": "file",
        "title": "配置文件"
      },
      "enabled": { "type": "boolean", "title": "启用功能", "default": true }
    }
  },
  "capabilities": {
    "ui": {
      "settings.section": [
        {
          "id": "main",
          "title": "示例插件设置",
          "description": "配置工作目录与功能开关",
          "target": "settings",
          "order": 100
        }
      ]
    }
  }
}
```

页签标识为 `plugin:example.settings:main`，也可使用 `/settings#plugin:example.settings:main`
直接打开。已有 `settings_schema` 的插件即使没有显式声明，也会获得默认设置入口；
显式声明空数组可关闭默认入口。

`target: "settings"` 使用宿主表单，读写接口为
`GET /api/plugins/{plugin_id}/settings` 与 `PATCH /api/plugins/{plugin_id}/settings`。
保存请求体为 `{"values":{"working_folder":"D:\\data"}}`。空值按现有插件配置规则恢复默认。
页面保留未保存更改提醒，后端按 schema 校验后写入插件配置。

字符串字段支持 `text`、`multiline`、`file`、`directory`、`secret`。
`file` 和 `directory` 自动附带文件或目录选择按钮；枚举、布尔、数字字段使用对应控件。
必填与选填都有标记；`secret` 只显示配置状态，继续使用已有密钥引用权限规则。

`target: "plugin-page"` 为提供 Web 入口的插件注册独立页面入口。
宿主构造 `/plugins/{plugin_id}` 地址，不接受 manifest 自定义跳转到任意站点。
设置页面将名称作为文本渲染。普通插件通过声明和 schema 扩展设置页。

技能和插件的安装区支持选择本地路径，也支持拖入一个目录或 ZIP/TAR 压缩包。
拖放使用内容上传接口 `/api/skills/install-upload` 和 `/api/plugins/install-upload`，
不依赖浏览器提供绝对路径。一次最多 5000 个文件、200 MB，拒绝非法路径和特殊文件；
临时目录在安装结束或失败后清理。

模型推理强度在会话中独立保存，提供 `low`、`medium`、`high`、`xhigh`、`max`。
请求协议分别转换：Responses 使用原生 reasoning 字段，兼容接口保留 thinking 参数，
Anthropic 依据模型使用自适应思考或受输出上限约束的思考预算；旧模型不支持的强度会映射到支持值。
相关协议依据见 [Anthropic effort 文档](https://platform.claude.com/docs/en/build-with-claude/effort)
和 [thinking 文档](https://platform.claude.com/docs/en/build-with-claude/thinking)。
