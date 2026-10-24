# 设置页插件接口

2026-10-22：独立业务页面统一在主页面右侧详情栏打开。设置浮层通过已校验的宿主消息转交；直接访问 `/settings` 时使用 `/?open_plugin=<id>` 深链返回主页面。已有 `embedded: true` 的设置贡献仍在设置分区中打开，未保存设置继续使用现有离开检查。右栏业务页面声明和桥接见 [Plugin API v1](plugin_api_v1.md#右侧详情栏页面2026-10-22)。

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

需要账号登录、模型选择等完整交互时，可在该声明上增加 `"embedded": true`。
宿主会直接在对应设置页签内加载 `/plugins/{plugin_id}?embedded=1`，不再显示跳转按钮。
普通表单和未声明内嵌的插件保持原有行为；仅接受布尔值 `true`，页面地址仍由宿主生成。

内嵌页面可使用同源 `postMessage` 与设置外壳交互：

- 页面发送 `myagent:plugin-settings-ready`，宿主返回 `myagent:plugin-settings-context`，
  包含 `theme`（`theme-light` / `theme-purple` / `theme-dark`）、`lang` 和 `fontPx`。
- 页面用 `myagent:plugin-settings-resize` 发送数字 `height`，宿主在 320–20000px 内调整高度，
  让外壳承担页面滚动。建议通过 `ResizeObserver` 仅在内容高度变化时发送。
- `myagent:plugin-settings-navigate` 配合 `section: "models"` 可切到模型设置；
  `myagent:plugin-settings-close` 可请求关闭设置窗口，并沿用宿主的未保存检查。

双方必须同时验证 `event.origin` 与 `event.source`。宿主只接受当前内嵌 frame 的消息，
不允许指定任意导航 URL。页面可复用 `/static/settings/settings.css` 的 `--st-*` 主题变量；
账号和模型业务、接口及资源仍由插件自己提供。

随应用发布的内置系统插件还可以声明 `target: "renderer"` 和 `renderer: {"module": "settings.js", "style": "settings.css"}`，直接贡献一个设置分区，与模型、插件等现有设置项并列；不额外增加设置容器或导航层级。分区标识同样为 `plugin:<plugin_id>:<id>`。宿主沿用聊天渲染器的物理目录、系统插件与资源路径校验，只发布宿主生成的资源地址。模块导出 `mountSettings({root, settings})`，返回清理函数；切换设置分区时宿主调用清理。禁用的内置插件仍保留该设置入口和静态资源，供用户重新启用，其聊天贡献和运行接口保持禁用。

技能和插件的安装区支持选择本地路径，也支持拖入一个目录或 ZIP/TAR 压缩包。
拖放使用内容上传接口 `/api/skills/install-upload` 和 `/api/plugins/install-upload`，
不依赖浏览器提供绝对路径。一次最多 5000 个文件、200 MB，拒绝非法路径和特殊文件；
临时目录在安装结束或失败后清理。

模型推理强度在会话中独立保存，提供 `low`、`medium`、`high`、`xhigh`、`max`。
聊天输入框旁显示模型与当前强度；菜单先显示「模型」和「推理强度」，点入后选择具体值。
当前选项带勾，保存成功后关闭菜单；方向键可移动，Escape 返回上一层，再按一次关闭。
请求协议分别转换：Responses 使用原生 reasoning 字段，兼容接口保留 thinking 参数，
Anthropic 依据模型使用自适应思考或受输出上限约束的思考预算；旧模型不支持的强度会映射到支持值。
相关协议依据见 [Anthropic effort 文档](https://platform.claude.com/docs/en/build-with-claude/effort)
和 [thinking 文档](https://platform.claude.com/docs/en/build-with-claude/thinking)。
