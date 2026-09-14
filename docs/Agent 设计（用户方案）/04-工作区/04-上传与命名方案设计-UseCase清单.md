# 上传、附件对象与命名 · 功能方案设计（UseCase 清单）

- 版本：2026-09-14 v2（覆盖至：HEAD `d022831` + API 识图工作区改动）
- 用途：逐条审查上传文件与图片附件在工作区侧的落点、授权、读取和备份边界。
- 适用实现：`app/webui.py`（`upload_chat_files / _safe_upload_filename / _dedupe_upload_path / read_attachment`）、`app/attachments/{local,registry,access,api,lifecycle}.py`。
- 上级：`00-工作区整体设计.md`
- 横切契约：[`../09-横切能力/02-识图与多模态投影方案设计-UseCase清单.md`](../09-横切能力/02-识图与多模态投影方案设计-UseCase清单.md)

---

## 1. 功能定位

该入口接收普通文件和图片。普通文件继续按安全文件名落入工作区；图片经过统一准入后进入内容寻址附件库，消息、会话和队列只保存耐久引用。

## 2. UseCase

### UC-4D1 普通文件上传与安全命名

- **触发**：界面上传一个或多个非图片文件。
- **预期现象**：文件名经过清理后落入默认上传目录；路径穿越、非法字符和冲突名称不会覆盖已有文件；回执包含可再次引用的工作区路径。
- **规则与边界**：同名文件自动追加序号。普通文件仍采用路径身份，不自动进入图片附件对象库。
- **依据**：`webui.upload_chat_files / _safe_upload_filename / _dedupe_upload_path`。

### UC-4D2 图片统一准入与内容寻址

- **触发**：上传、拖拽或粘贴 PNG/JPEG/WebP/GIF/BMP 图片。
- **预期现象**：服务端校验整批图片，应用方向与色彩归一化、移除元数据并按需缩放，再以 `sha256:<digest>` 保存规范对象；回执同时提供附件引用和 `/api/attachments/{id}` 读取地址。
- **规则与边界**：相同规范字节只存一份。BMP 在本地兼容入口先转 PNG；动画只取首帧。规范对象用于识图，不承担原始图片档案职责。
- **依据**：`webui.upload_chat_files`、`attachments/local.py`、`attachments/normalization.py`。

### UC-4D3 整批限额与失败回滚

- **触发**：一次上传超过图片数量、源字节、单图字节、像素或最大边长限制，或批次中任一图片损坏。
- **预期现象**：整批图片拒绝并返回可行动错误；本次暂存和新建对象回滚，不留下部分成功的消息状态。
- **规则与边界**：默认单图 20 MiB、单消息 20 张、源图合计 200 MiB、单图 64,000,000 像素、最大边 8192。单文件原子替换与可捕获异常回滚不等同于跨文件 ACID；强杀残留由宽限 GC 处理。
- **依据**：`_ChatUploadLimitError`、`attachments/admission.py::admit_content`、`attachments/local.py::save_images_sync`。

### UC-4D4 附件授权读取与缓存协商

- **触发**：前端或 API 调用方执行 `GET /api/attachments/{attachmentId}`。
- **预期现象**：服务端校验附件 ID、调用方身份和 grant 后返回规范图片；未授权或不存在统一返回 404；响应包含稳定 ETag，支持 `If-None-Match` 返回 304。
- **规则与边界**：loopback 本机身份按本地管理员处理；远程设备沿用已配对身份与 read scope。带转发身份头的请求不因来源是 loopback 自动提权。
- **依据**：`webui.read_attachment`、`attachments/access.py`、`attachments/registry.py`。

### UC-4D5 远程图片显式入库

- **触发**：有 write scope 的调用方执行 `POST /api/attachments/ingest`，提交图片 URL 数组。
- **预期现象**：服务端逐跳执行 DNS/IP 安全检查，限时下载并复用图片统一准入；成功后向当前设备授予附件 grant，只返回规范引用。
- **规则与边界**：仅 HTTP(S)，默认拒绝 loopback、私网、链路本地、凭证 URL 和混合公网/私网解析；不继承浏览器 Cookie、供应商密钥或环境代理凭证。来源记录不保存查询串和签名。
- **依据**：`attachments/api.py`、`attachments/remote.py`、`attachments/registry.py`。

### UC-4D6 附件引用保护与回收

- **触发**：浏览器队列同步 `POST /api/attachments/references`，识图请求创建/清理，或管理员执行附件 GC。
- **预期现象**：队列和识图作业通过 pin 保持附件可达；新上传 grant 同时提供宽限租约；GC 综合会话引用、pin、租约和宽限期后才列出或删除不可达对象。
- **规则与边界**：GC 默认 dry-run；任何引用根读取错误都停止删除。规范对象不能按普通缓存直接淘汰，请求缩放缓存才允许按容量清理。
- **依据**：`attachments/registry.py`、`attachments/lifecycle.py::garbage_collect`、`vision_api.py::gc/prune`。

### UC-4D7 附件备份与恢复

- **触发**：管理员调用 `POST /api/attachments/export` 或 `POST /api/attachments/import`，或导出包含图片的会话。
- **预期现象**：ZIP 包含 manifest、规范对象和 metadata；导入逐项校验路径、摘要、尺寸、格式与重复项，成功后向当前设备授予 grant。会话导出只打包该会话可达图片。
- **规则与边界**：导入拒绝绝对路径、`..`、符号链接、未知成员和超限压缩包；导出临时文件在响应结束后清理。附件包不包含设备授权、队列 pin 或模型请求缓存。
- **依据**：`attachments/api.py`、`attachments/lifecycle.py::add_bundle/import_bundle`、会话导出路径。

## 3. 边界

- 图片的模型能力判断、请求缩放、总预算、省略规则和独立识图 API 见[识图与多模态投影](../09-横切能力/02-识图与多模态投影方案设计-UseCase清单.md)。
- 普通文件的浏览、打开和路径授权继续属于工作区；附件对象的调用方 grant 不替代工作区文件系统授权。
- Runtime V2 只保存耐久附件引用，迁移和会话导出见 [`../08-会话存储RuntimeV2/05-迁移修复与日志压缩方案设计-UseCase清单.md`](../08-会话存储RuntimeV2/05-迁移修复与日志压缩方案设计-UseCase清单.md)。

## 4. 依据映射

| 用例 | 主要实现 |
|---|---|
| UC-4D1 | `webui.py` 普通上传分支 |
| UC-4D2~4D3 | `attachments/admission.py`、`local.py`、`normalization.py` |
| UC-4D4 | `webui.read_attachment`、`attachments/access.py` |
| UC-4D5 | `attachments/api.py`、`remote.py` |
| UC-4D6~4D7 | `attachments/registry.py`、`lifecycle.py`、`vision_api.py` |

## 5. 版本记录

- 2026-09-14 v2：区分普通文件与图片对象，补齐授权读取、URL 入库、引用保护、GC 和备份恢复。
- 2026-09-13 v1：拆分首版（承接 UC-407）。
