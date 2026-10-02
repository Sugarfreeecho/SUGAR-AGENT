# 2026-09-29 read_file 透明读图（并入原工具）

## 能力：`read_file` 直接查看图片

- 命中 `.png/.jpg/.jpeg/.gif/.webp/.bmp` 时，`read_file` 忽略行范围参数，返回 `[文本信封, image 块]`：图片经既有附件准入（字节/像素/边长上限、BMP→PNG、EXIF 修正、8-bit sRGB 归一化、内容寻址去重）落库，随后由请求投影按当前候选模型能力决定作为视觉输入下发，或降级为确定性省略文案；模型不支持图片输入时不丢历史、不报错。
- 信封给出 `<path>/<type>/<content>`、媒体类型、显示尺寸与字节数；归一化缩过图时附"坐标乘数"提示，便于按原图像素定位（对齐 DSH `read_image` 信封与 ZCode `Read` 的透明读图行为）。
- 文本路径行为不变（行范围、行数缓存、二进制嗅探、范围读上限）；扩展名非图片但内容确为 JPEG/PNG/GIF/WebP 时，嗅探回执改为"改名/复制后重读"，不再指向不存在的 image tool。
- 审批与执行语义不变：`read_file` 仍按 `fs.read` 分类、并行安全，子代理白名单自动继承（explore/readonly 均可读图）；提示词（中/英）同步更新为"已落盘的图片直接用 `read_file` 读取…或走附件/`task` 的 `file_attachments`"。

## 小坑修复（结构化工具结果 × 图片块）

- **Hooks 追加附加上下文**：`tool_detail_llm` 为块数组时追加独立文本块，不再 `str()` 覆盖——此前 MCP/内置工具返回的 image 引用会被字符串化，模型收到的图片丢失（`app/agent_loop.py` react_node 后置 Hook 段）。
- **只读行折叠分支**：`_response_from_outcome` 的 `_wrap_read_only_tool_output_lines` 现在只处理字符串结果；结构化结果（list 含 image 块）继续走既定图片通道。

## 测试与验证

- 新增 `tests/test_read_file_image.py`（9 例）：PNG 结构化结果与引用读回、文本不受影响、行范围参数忽略、BMP 自动转换、超限可恢复错误且零残留、伪扩展名改名提示、内容寻址去重、缩放坐标提示、工具结果视图保留 image 块。
- 定向回归（15 个测试文件，含附件/多模态/工具/钩子/恢复/子代理/识图）：**291 passed**。
- 环境备注：默认长 TEMP 路径下 `test_vision_api::test_session_export_includes_reachable_images` 受 Windows MAX_PATH(260) 限制失败，用短 basetemp 复核通过，与本批改动无关。

## 补充（同日）：能力门前置——非多模态模型读图直接报错

- **现象**：`read_file` 合并读图后，未声明图片输入的模型也会调用成功；该模型消费不了图片，只会产生"看不到图还要处理"的无效往返与报错。
- **变更**：
  - `app/agent_tools.py`：新增 `_tool_model_image_input` 上下文与 `tool_model_media_context()`；`read_file` 图片分支在明确 `image_enabled is False` 时直接返回可恢复错误（提示切换识图模型，或改走 `task` 的 `file_attachments`），**不再入库、不再产生图片块**；工具描述与 docstring 同步说明。
  - `app/agent_loop.py`：内置工具执行前解析当前候选模型的 `input_modalities`（与 MCP 分支同一判定源：`current_candidate().input_modalities`，缺失时回退 `_client_input_modalities`），通过上下文注入；解析异常保持 `None`（不拦截，避免误伤可读图模型）。
  - 提示词（中/英）：看图条目补充"当前模型不支持图片输入时 `read_file` 会直接拒绝并提示切换模型"。
- **兼容与生效**：常规模型路径一律注入；直接调用/测试未注入时保持原行为；能力随每轮候选解析即时生效（含供应商拒绝后学习到的能力回写）。
- **测试**：`tests/test_read_file_image.py` 增至 12 例（新增：text-only 提前拒绝且零残留、image-enabled 正常返回、text-only 客户端请求体无图片载荷）；定向回归 15 个套件 **296 collected / 296 passed**；安全/工具注册等补充套件全绿。

## 文件

- `app/agent_tools.py`：`read_file` 图片分支、`_read_file_image_output/_read_file_image_error/_image_downscale_note`、嗅探文案、工具描述。
- `app/agent_loop.py`：Hook 附加上下文保持块数组；只读折叠分支限定字符串。
- `app/prompt.md` / `app/prompt.en.md`：看图指引更新。
- `tests/test_read_file_image.py`：新增。
