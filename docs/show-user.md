# show_user / ask_user：展示与询问

`show_user` 是与 `ask_user` 配套的内置 Host Tool，常驻工具目录。前者在执行中向用户展示内容并立即返回，后者暂停当前运行并等待用户回答。`ASK_USER_ENABLED=0` 不禁用展示能力。

实时收到当前可见会话的新展示时，前端打开对应详情标签、顶部提示或设置页签。生成继续进行；用户可以关闭或稍后从工具行重新打开。历史重放和重复 SSE 不重复触发展示，后台会话不抢占当前页面。窄屏沿用详情栏的全屏模式。系统通知由后端发送，不依赖浏览器在线。

## 支持的内容

| kind | 必要内容 | 展示方式 |
|---|---|---|
| `webpage` | `url` | 现有详情栏浏览器；支持 HTTP(S) 和本地开发服务 |
| `text` | `text`，可选 `format=text/markdown` | 只读文本或 Markdown 页面，最多 65,536 字符 |
| `image` | `attachment_id` 或 `data_url`，另需 `alt` | 持久图片附件，支持放大、加载失败重试；可选 `caption` |
| `file` | `path` | 当前会话工作区内文件，复用已有文档、HTML、媒体和图片预览 |
| `plugin` | 可选 `plugin_id`、`page_id` | 已启用插件声明的详情页/控制台；不传 ID 时打开插件目录 |
| `notice` | `text`，可选 `level`、`duration_ms` | 顶部可关闭提示，最多 4,000 字符；默认显示 8 秒 |
| `settings` | 可选 `section` | 打开指定设置页签，默认 `general`；保护未保存内容 |
| `notification` | `text` | 原生系统通知，最多 2,000 字符；返回发送请求状态 |

每次调用都需要 `title`，最多 100 字符。每次展示一个目标，可在后续调用中展示其他内容。重复打开同一展示会聚焦已有标签；插件页面保留现有挂载状态和未提交内容。

```json
{"kind":"webpage","title":"运行中的页面","url":"http://127.0.0.1:3000/"}
```

```json
{"kind":"text","title":"实现说明","format":"markdown","text":"## 当前结果\n\n已接通展示工具，接下来继续验证。"}
```

```json
{"kind":"file","title":"生成的报告","path":"reports/result.html"}
```

```json
{"kind":"plugin","title":"插件控制台","plugin_id":"sugar-bili-scroll","page_id":"main"}
```

插件 ID 和页面 ID 应以实际启用插件的声明为准，不能任意拼 URL。图片来源沿用 ask 卡片的附件准入：本地图片先 `read_file`，然后复用返回的 `attachmentId`；真实截图工具返回的 PNG/JPEG/WebP/GIF Base64 可作为 `data_url`，最多 2 MiB，不要编造图片字节。扫码图片可先 `show_user` 展示，再单独 `ask_user` 收集“已扫码 / 失效 / 取消”等选择；登录是否成功仍需实际核验。

## 顶部提示、设置与系统通知

```json
{"kind":"notice","title":"准备完成","text":"页面已启动，可以开始预览。","level":"success","duration_ms":8000}
```

`level` 支持 `info`、`success`、`warning`、`error`。`duration_ms` 为 1,000–30,000，或 `0`（直到关闭）。悬停、键盘聚焦或页面隐藏时暂停计时；新提示替换当前提示，原内容保留在会话工具卡片中，可手动重新显示。提示和卡片均按纯文本渲染。

```json
{"kind":"settings","title":"配置模型","section":"models"}
```

内置页签：`general`、`models`、`skills`、`plugins`、`hooks`、`mcp`、`usage`、`security`、`env`、`paths`。插件设置使用实际声明的 `plugin:<plugin_id>:<section_id>`。工具只打开页面，不修改配置；已打开的相同页签直接保留表单，切换页签或会话上下文时沿用未保存更改确认，取消后保留原内容。用户已确认丢弃的表单再次打开时会刷新。

```json
{"kind":"notification","title":"报告已生成","text":"结果保存在 reports/result.html，可以回来查看。"}
```

系统通知只调用已注册的 `desktop-notifications` 提供者，不启用停用的插件，也不转发给其他通知渠道。工具仍返回 `display_requested`，并附带 `notification_status`：

- `requested`：已向桌面通知通道发出请求，不代表系统实际显示或用户已阅读。
- `unavailable`：桌面通知通道未启用，正文保留在工具卡片。
- `failed`：通道调用失败，正文仍保留。
- `unknown`：上次请求的最终状态无法确认，为避免重复提醒不自动重发。

每次调用先保存展示事实，在会话目录 `presentations/notification-<presentation_id>.json` 中排他创建并刷盘通知凭据，再发送并记录结果。同一会话/运行/工具调用 ID 至多发送一次；即使服务在发送前后崩溃、工具调用被重试或 SSE/历史重放，也不会自动补发不确定的通知。新的工具调用 ID 可用于有意发起的新通知。通知卡片没有重发按钮；前端只显示结果。

## 保存、恢复与边界

- 请求先提交到现有 Runtime V2 UI 事实，再发布实时事件。图片保存为附件引用，参与现有导出和垃圾回收扫描。
- 工具结果为 `display_requested`，不代表网页加载成功或用户已阅读。浏览器不在线时，展示记录仍保留供稍后查看。
- 文件展示走 `fs.read` 授权，并限制在当前会话工作区。Web 页面复用现有浏览器隔离和地址检查，不直接导航主应用。
- Markdown 由解析器 token 构建 DOM；不执行原始 HTML，不自动请求 Markdown 图片。需要图片时使用 `kind=image`。
- 图片接口绑定具体会话和展示记录，执行访问认证，并使用 `no-store`。不能传任意文件地址给该接口。
- 本轮没有新增插件页面能力；没有声明 Web 详情页的插件不会因 `show_user` 自动获得控制台。网页受对方嵌入限制时，沿用浏览器中的系统浏览器打开入口。
- 服务端不替用户确认、点击授权或完成登录。`show_user` 也不创建待回答状态，不改变 `ask_user` 的确认流程。

主要实现：`app/user_presentations.py`、`frontend/src/app/modules/user-presentations.js`，工具注册在 `app/builtin_host_tools.py`，模型定义在 `app/agent_tools.py`。

完整重启应用并刷新页面后生效。本次不重启正在运行的用户实例，不构建或安装 Electron 发行包。

## 验证记录

- `show_user`、通知提供者及浏览器目标检查共 66 项，全部通过：覆盖详情栏原有五种目标、顶部提示、设置导航、未保存内容保护、通知断连/失败/未启用、并发和崩溃凭据去重，以及历史静默和通知状态更新。
- 相关 Python/浏览器回归共 242 项通过，包含上述检查及设置中心、插件导航、人工交互、图片、工具注册和会话通知。插件导航旧测试补齐 `/api/plugins/catalog` 模拟数据后通过。测试结束时已有 GitHub MCP 后台连接出现线程池关闭日志，pytest 退出码为 0。
- 前端生产构建、产物与源码一致性检查通过；现有大包体积提示仍存在。
- 使用真实浏览器检查了深色 Markdown、浅色 320px 图片详情页，以及深色和浅色窄屏顶部提示，预览位于 `.analysis/show-user/`。系统通知测试使用隔离的模拟提供者，未向用户桌面发送实际通知。
