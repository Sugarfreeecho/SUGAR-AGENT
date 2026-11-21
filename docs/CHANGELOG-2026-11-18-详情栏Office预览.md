# 详情栏 Office / PDF / CSV 内嵌预览

日期：2026-11-18。

## 目标

详情栏的文件内容页此前只内嵌文本、图片和音视频；PDF、Word、PowerPoint、Excel、CSV 一律显示"在系统应用中打开"卡片或纯文本，浏览办公文件要离开应用/自己数逗号。本次把这些文件放进详情栏直接看，不引入前端大依赖，也不调用本机 Office。

## 文件内容页

- **PDF**：`/api/workspace-assets/<rel>` 以 `application/pdf; inline` 返回，交给浏览器内置查看器；支持其自带缩放、文字选择与链接。
- **Word（.docx）**：标题、段落、粗/斜/下划线/颜色/字号、对齐、项目符号与编号列表（含样式里的 numPr）、表格（含合并单元格）、内嵌图片、外链；HTML 全部由后端转义生成。
- **PowerPoint（.pptx）**：960px 逻辑画布按栏宽等比缩放；占位符几何从 slide → layout → master 继承，字号/颜色/项目符号从 `txStyles` 逐级回退；支持图片、表格、组合形状；图表与 SmartArt 显示占位框（不解析内部数据）。
- **Excel（.xlsx/.xlsm）**：工作表页签、合并单元格、字体/填充/换行/对齐、日期与百分比格式、冻结首行/首列吸顶；单表 400 行 × 64 列、最多 24 表、全局 3 万单元格。
- **CSV / TSV**：首行吸顶的表格；自动识别 `, ; TAB |` 分隔符，编码按 BOM → UTF-8 → GB18030 回退；工具条显示 `CSV · 行 × 列 · 编码`，一键切"查看源码 / 预览表格"（源码走既有 `/api/workspace-file-text`）；上限 20 MB / 500 行 / 60 列。
- 页脚统一标注"简化还原"与超限原因（文档过长 / 幻灯片过多 / 表格较大 / 图片过大），避免把截断误认为文件损坏。
- 头带保留刷新、打开目录、在系统应用中打开；刷新会重新请求预览并重放大图。

## 后端解析与安全

- 新增 `app/workspace_doc_preview.py`：只用标准库 `zipfile` + `defusedxml` + `csv` 解析 OOXML/分隔文本，Excel 复用已随桌面版分发的 `openpyxl`；桌面打包不需要新增依赖。
- 新增 `GET /api/workspace-doc-preview`（结构化载荷）与 `GET /api/workspace-doc-media`（按部件取图）。媒体接口只允许 `word/media`、`ppt/media`、`xl/media` 下的常见位图，其它部件返回 400。
- 路径复用既有 `_workspace_request_root` / `_resolve_workspace_view_path` 校验；只读、不写文件。
- 限额：原件 60 MB、解压总量 240 MB、单 XML 24 MB、单图 12 MB、Word 6000 块、幻灯片 60 页；预览结果按 (路径, mtime, 大小) 做 6 条 LRU 缓存，保存后自动失效。
- 旧版 `.doc/.xls/.ppt`、压缩包、可执行文件、字体仍走"系统打开"卡片。

## 打开策略

`MyAgentDock.openPathSmart` 从"文本 → 详情栏，其余 → 系统应用"扩展为"文本与 PDF/Office/CSV → 详情栏，其余 → 系统应用"；文件树、会话文件链接、`show_user` 的文件展示共用同一判定（新增 `isPreviewPath` 查询）。

## 验证

- 后端 `tests/test_workspace_doc_preview.py`：8 项（docx 结构/转义、媒体部件校验、xlsx 样式/合并/冻结、csv 引号/GBK/分号/行列上限、pptx 占位符继承与表格、拒绝非 Office/损坏/超大文件、缓存随 mtime 失效、路由路径与状态码）。
- 前端 `tests/test_details_office_preview_browser.py`：5 项（幻灯片翻页与缩放、工作表页签与限额提示、CSV 表格/源码切换、Word 图片按部件加载、PDF 使用浏览器查看器）。
- 既有详情栏回归（页面/拖拽/会话切换/插件目录/设置导航）与 `test_show_user_browser.py` 通过；长批次运行时设置导航用例一次 iframe 点击超时，单跑复验通过。`npm run build` 后 `npm run verify:dist` 通过。

## 注意

`/api/workspace-doc-preview`、`/api/workspace-doc-media` 是新增后端路由，**需重启一次服务**才生效；生效前 Office 页显示"预览接口尚不可用（可在系统应用中打开）"。
