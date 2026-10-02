# 2026-10-02 读图路由文案收敛：识图模型直读，纯文本模型保留委派

## 现象

可识图的模型（profile 声明 image 输入）有时不自己用 `read_file` 看图，反而把图片交给子代理，走"纯文本模型读图"的通道；而 `read_file` 直读本来就能直接拿到图片块。

## 根因

读图在提示词与工具描述里被写成两条并列通道，且没有条件限定：

- `app/prompt.md` / `app/prompt.en.md` 的"截图/看图"条目把 `read_file` 与"附件/`task` `file_attachments`"并列，任何模型都会读到，读起来像"两条等价路径"。
- `task` 工具描述以 `For image understanding, select a model_profile_id whose effective input modalities include image…` 开头，把"图像理解"直接绑到 task。
- `task.prompt` / `model_profile_id` / `file_attachments` 三处参数描述同样用无条件句式讲图片引用。
- `read_file` 图片分支的拒绝文案（只有非识图模型能看到）给出"切换识图模型 / 交给子代理"两条路——这是纯文本模型的正路，保留。

## 变更

- `app/prompt.md` / `app/prompt.en.md`：读图条目改为"已落盘的图片直接用 `read_file` 读取"，子代理通道收进**条件句**——"`read_file` 只在当前模型未声明图片输入时拒绝读图：此时如实告知用户并建议切换识图模型，或把图片交给能识图的子代理（`task` 的 `file_attachments`）"。
- `app/agent_tools.py`
  - `read_file` 工具描述：说明看图就是本工具的常规上下文调用，未声明图片输入的 profile 才会拿到解释性错误。
  - `task` 工具描述：改为条件式——当前模型能看就 `read_file` 直读，不能看再委派；保留 `file_attachments` 的统一路由说明（image-capable → `image_url`，text-only → 确定性省略文案）。
  - `task.prompt`：图片路径加引号的规则改为"如果交接确实引用图片…"。
  - `task.model_profile_id`：选择识图 profile 的前置条件写成"当前模型看不了图，或用户要求子代理看图"。
  - `task.file_attachments`：说明它是"当前模型看不了图时把图片交给子代理"的通道。
  - `read_file` 图片分支拒绝文案与 docstring：保留"切换识图模型，或交给子代理"两条路径（仅非识图模型可见）。
- 测试
  - `tests/test_agent_subagent_runtime_v2.py`：断言改为条件式文案（"能直读就直读、不能看再委派"），并保留多模态路由断言。
  - `tests/test_read_file_image.py`：拒绝文案断言补充"切换识图模型 + `task` `file_attachments`"两条路径；新增提示词回归，断言中英条目同时包含"直读"与"仅未声明图片输入时才委派"。

## 测试与验证

- 定向：`tests/test_read_file_image.py`、`tests/test_agent_subagent_runtime_v2.py`、`tests/test_dsh_attachments.py`、`tests/test_feature_flags.py`、`tests/test_tool_registry.py`、`tests/test_system_prompt_adaptation.py` → **169 passed**。
- 全量：`python -m pytest tests -q` → **1770 passed, 4 skipped, 2 failed**；两例均为既有问题、与本次改动无关：
  - `tests/test_interrupt_stream_runtime.py::test_interrupt_checkpoint_precedes_abort_and_tool_visibility`：测试按源码字符串切分 `"if _steer_requested(state):"`，该字面量在当前 HEAD 与工作区都不存在（测试陈旧）。
  - `tests/test_vision_api.py::test_session_export_includes_reachable_images`：Windows MAX_PATH(260) 限制，短 basetemp 复核通过。
- 运行时核对：用一次性脚本打印改动后的中英提示词条目、`task` 描述与 `read_file` 拒绝文案，确认措辞与预期一致（未落盘为长期文件）。

## 文件

- `app/prompt.md`、`app/prompt.en.md`
- `app/agent_tools.py`
- `tests/test_agent_subagent_runtime_v2.py`、`tests/test_read_file_image.py`
