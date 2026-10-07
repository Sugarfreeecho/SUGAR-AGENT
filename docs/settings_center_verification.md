# 设置中心功能验证报告（9 分区）

> 目的：回答「里面有很多功能需要验证测试」——把设置中心每个分区依赖的接口、渲染与读写回环跑一遍，
> 给出逐项结论与证据位置。
> 结论：**渲染层 0 报错、接口层 36/36、UI 实测 17/17**；过程中抓到 3 个真问题，全部已修并补测试。

## 1. 方法与边界

| 层 | 做法 | 证据 |
| --- | --- | --- |
| 渲染走查 | 打开浮层 → 依次点 9 个页签 → 等分区渲染完 → 记录卡片/行/开关/按钮数、是否出现「加载失败/渲染失败」、整页 console 错误、`/api/*` 里 ≥400 的响应 | `workspace/设置中心验证/tab-*.png`（9 张） |
| 接口层 | 直接打每个分区真正调用的接口，校验状态码与前端渲染取用的字段名 | `verification_api_probe.py`（36 项） |
| UI 实测 | Playwright 驱动系统 Edge：真鼠标拖拽、键盘换位、弹窗/确认框、分段控件、校验提示、搜索过滤、路径选择器、齿轮浮层 | `verify_settings_ui.py`（17 项） |
| 字号实测 | 浮层内输入/箭头调字号 → 校验设置中心、localStorage、**聊天页**三处同步 + 越界钳制 + 还原 | `verify_font_size_ui.py`（8 项） |
| 写入回环 | 挑「可还原」的写操作：改回去再比对，确认语义回到原状 | 两个脚本都会在结尾还原并复读 |
| 防脏写 | 每步后比对 4 个配置文件的 SHA256 与基线 | `.sugaragent/model_profiles.json` / `.sugaragent/mcp_servers.json` / `.sugaragent/skill_states.json` / `app/.env` |

跑测时的真实规模（说明不是空跑）：8 个模型档案、19 个技能、6 个插件、3 个 MCP 服务器 / 27 个工具、5 条会话规则、6 组 36 个环境变量。

## 2. 逐分区结论

| 分区 | 依赖接口 | 结论 |
| --- | --- | --- |
| 常规 | `/api/model_profiles` | 渲染正常；模型档案下拉 8 项；主题/列表/语言已单独验证为实时同步；**字号是 DSH 式可输入步进器（12–20 px）**，实测见 §3.6；`权限模式` 只写 localStorage（已验证回写） |
| 模型 | `/api/model_profiles`、`/{id}/enabled`、`/{id}`(DELETE)、`/discover`、`/reorder` | 列表/开关/编辑弹窗（字段预填、密钥留空）/删除确认框（可取消）齐备；**拖拽排序 + ↑↓ 键换位实测通过，顺序写回服务端可还原** |
| 技能 | `/api/skills`、`/{name}/enabled`、`/create`、`/install` | 19 个技能；开关回环通过；添加弹窗三分段（目录/压缩包/Git）切换正常、空提交有校验提示；**说明只在悬停浮框里（B12 实测：925 字说明行内不出现、移开即隐藏）** |
| 插件 | `/api/extensions`、`/reload`、`/api/plugins/*` | 6 个插件条目；「重新发现 / 热重载」实测返回「已重载：新增 0，移除 0」；**简介只在浮框里（B14 实测）** |
| Hooks | `/api/extensions`、`/api/extensions/reload` | 总开关读 `HOOKS_ENABLED`（当前 =1，与 UI 一致）；热重载按钮实测「已重载」；0 个 Hook 时空态文案正确 |
| MCP | `/api/mcp/tools`、`/api/mcp_config`、`/tools/{fn}/enabled` | 3 服务器 / 27 工具；工具开关回环通过；空命令点「添加」被拦下（提示「请填写」）；**27 条工具说明只在浮框里（B13 实测：453 字说明行内不出现）** |
| 安全与权限 | `/api/security/{permissions,settings,rules,web-fetch-domains,extensions}`、`/sessions/{id}/permissions` | 5 个接口 200 且字段齐；当前模式 `full_access`；规则增删回环通过；空规则被拦下 |
| 环境变量 | `/api/env`（读 + 写） | 6 组 36 个变量；策展键齐；**搜索过滤修好后实测 36 → 1 行**；保存条常驻；同值保存 `.env` 字节不变 |
| 目录与路径 | `/api/env` | `WORK_DIR` 存在且 `path_kind=directory`；6 个输入都挂上了「选择」按钮；其余键未设置即「默认」态 |

## 3. 发现的问题与修复

### 3.1 点「保存」会往 `.env` 写空键（已修）

- `环境变量` 的 `save()` 会把**整屏控件**（含后端注入的 6 个默认键）一起 POST；`目录与路径` 的 `save()` 会把 6 个路径键**全部**提交，没填的 5 个是空串。
- 后端 `_apply_env_updates()` 对空串的语义是「写成 `KEY=`」（不是删除）→ 什么都没改点一次保存，`.env` 就多出 `SKILLS_DIR=`、`LOG_DIR=`、`NODE_HOME=`、`PLUGINS_DIR=`、`HOOKS_PATH=`、`SECURITY_ENABLED=1` 之类空行。
- 修法（`sections_ops.js`）：两份 `save()` 都改成**只提交改动**——与快照比对，没变就不提交；把已有值**清空**= 恢复默认，改走 `remove`；密钥保持「留空即不改」。

### 3.2 搜索框一敲字就被自己清空（已修）

- `showSection()` 无条件 `state.search = ''`，而「技能 / 环境变量」的 `onSearch()` 正是 `reload()`（= 同分区 `showSection(..., {force:true})`）→ 输入字被立刻清掉、列表根本不筛选。实测：环境变量页输入 `TAVILY` 后仍是 36 行。
- 修法（`core.js`）：只有**真正换分区**才清搜索词（`if (previousSection !== id) state.search = '';`）。修完实测 36 → 1 行。

### 3.3 模型顺序不能拖拽调整了（已修）

- 旧「高级设置」页（`advance_config.html`）本来就支持拖拽排序并 POST `/api/model_profiles/reorder`，设置中心上线后模型页只剩「越靠上优先级越高」文案，能力被吃掉。
- 修法（`sections_basic.js` + `settings.css`）：每行加拖拽手柄（只有手柄可拖）、`dragover` 时行让位 + 位移动画、拖到列表外视为取消并恢复原序、落点后提交 `ordered_ids`；键盘可达（聚焦手柄按 ↑/↓）。
- 实测：真鼠标拖拽把第 1 行拖到第 3 位 → DOM 与服务端顺序都变 → 接口还原回基线；键盘同样通过。

### 3.4 看着像问题、其实不是

- `.sugaragent/model_profiles.json` 在开关/排序回环后哈希变了：`set_profile_enabled()` 会刷新 `updated_at`、排序会重写序号（预期），语义已还原。
- 路径键「缺失」：`/api/env` 只列出 `.env` 里真实存在的键；`目录与路径` 自带 6 键清单，缺席即「未设置/用默认」。
- 无头模式下原生 HTML5 拖拽不触发（Playwright 合成鼠标事件限制），不是实现问题：同一条用例改由合成 `DragEvent` 兜底；`--headful`/真实浏览器下走的是真鼠标拖拽，已单独验过。

### 3.5 验证脚本自身的坑（记录以免重犯）

- `urllib.parse.quote(int)` 类型错误让首轮跑挂在删除临时规则前，留下 `pattern=__verify_tmp` 规则（id=8）；已用 `_cleanup_tmp_rule.py` 清掉并加结尾兜底清零，会话规则回到 5 条基线。
- 我一度按 `#st-dlg` 找弹窗，实际容器 id 是 `#st-dialog`（`#st-dlg-*` 只是内部标题/正文）→ 误报「弹窗不显示」。已改正。
- PowerShell `-replace` 会把脚本里的中文注释写成乱码并吞掉换行 → 改脚本一律走 `write_file`/`apply_patch`。

### 3.6 字号：三档分段控件 → DSH 式可输入步进器（已改）

- 原状：`小/标准/大` 三档（14/16/17px），用户要求「学习 DSH 做成可输入字号大小的」。
- 现状：药丸里可直接输入整数（12–20），右侧悬浮上下箭头逐级调，尾巴 `px` 单位；存储新增 `myagent-font-size-px` 且与旧档位键双向兼容；聊天页实时跟变。
- 实测 8/8：输入 18 → 设置中心 `data-font-size=18` / localStorage `18` / **聊天页 root `18px`**；箭头 +1/−1；99→20、3→12（到界箭头禁用）；清空离焦退回上一个有效值；结束还原 16px。
- 截图：`ui-font-stepper.png`（浮层内新控件）、`ui-font-18-chat.png`（18px 生效）、`proto-font-stepper.png`（原型同款）。

### 3.7 技能说明：行内铺开 → 悬停浮框（已改）

- 原状：技能行副标题直接打印整段 description（agent-browser 那条 925 字，列表被撑成"说明书"）。
- 现状：行内只有技能名 + 启用状态 + 开关；说明挂在 `data-tip` 上，悬停（或键盘聚焦）弹出反色气泡，移开/滚动/换分区收起；搜索仍按 name + description 过滤。
- 实测：`verify_settings_ui.py` 的 B12 通过（浮框文本 == 说明全文、行内不含说明、移开后隐藏）；原型同款改动冒烟通过。
- 截图：`ui-skill-tooltip.png`（实现）、`proto-skill-tooltip.png`（原型）。

### 3.8 MCP 工具 / 插件说明同上（已改）

- MCP 27 条工具：主标签留 `function_name`、副标题清空，说明进浮框（B13：453 字说明行内不出现、浮框 27 个目标）；插件 6 条：名字挂浮框、副标题只留组件汇总（B14）；插件自带设置的标题同样处理。
- 卡片提示改为「悬停工具名看说明 / 悬停插件名看简介」，`tipIf()` 保证没说明时不出现空气泡。
- 截图：`ui-mcp-tooltip.png`、`ui-plugin-tooltip.png`；原型同款（`proto-mcp-tooltip.png`、`proto-plugin-tooltip.png`）。

## 4. 仍未覆盖

- 会真装/真删的破坏性动作只走了「校验/取消」分支，没真执行：插件安装与移除、技能 zip/git 安装、`清除本会话规则`、`发现模型`（需要联网）。
- 触摸/移动端手势、以及真实系统拖放（拖文件进窗口）不在本轮范围。

## 5. 复跑方式

```powershell
python 'workspace\设置中心验证\verification_api_probe.py'    # 接口层 36 项
python 'workspace\设置中心验证\verify_model_reorder.py'       # 排序接口回环
python 'workspace\设置中心验证\restore_model_order.py'        # 万一顺序被留在半路，按原始排法写回
python 'workspace\设置中心验证\verify_settings_ui.py'         # UI 实测 17 项（+ --headful 看真拖拽）
python 'workspace\设置中心验证\verify_font_size_ui.py'        # 字号步进器实测 8 项
python -m pytest tests/test_settings_center.py -q             # 12 例契约测试
```

### 5.1 跑测期间的环境变化（不属于本轮改动）

- 全量测试最后剩两条不绿，都与设置中心无关：
  `test_repository_global_mcp_contract` 断言 `.sugaragent/mcp_servers.json` 里 playwright 的 `args[-2:]` 是
  `--headless --isolated`，而该文件在本轮跑测期间被另一个工作流按
  `docs/CHANGELOG-2026-10-03-根目录状态文件迁移.md` 主动加了 `--output-dir .sugaragent/playwright-mcp`
  ——旧的末尾断言因此过期（**不是**本轮的写入，脚本侧只读该文件；需要的话改一行断言即可）。
  另 `test_plugin_runtime.py::test_timed_out_worker_restarts_cleanly_for_next_call` 在整机负载高时偶发超时，单独跑通过。
  全量跑时 `test_tool_registry.py::test_builtin_host_services_are_bound_to_registered_invokers` 也出现过一次同样的负载型失败，单独跑通过（1826 passed / 1 failed）。
- 本轮给 `verify_settings_ui.py` 加了「改顺序前先落盘基线、下次跑先还原」的安全网：模型顺序 = 优先级，
  第一位就是默认模型，不能让测试把它留在半路（早期一次崩溃就踩过，已用 `restore_model_order.py` 复原）。

> 安全网：`verify_settings_ui.py` 在动顺序之前会把基线落盘（`.model-order-baseline.json`），
> 下次运行时若发现遗留基线会**先还原再测**——模型顺序 = 优先级，第一位就是默认模型，
> 不能让测试把它留在半路（本轮就踩过一次，已按 `restore_model_order.py` 复原）。

新增测试（`tests/test_settings_center.py`）：
- `test_env_snapshot_updates_keep_unrelated_lines`：`_apply_env_updates` 行级保留；同值不改文件；空串写成 `KEY=`（所以前端不该提交空键）。
- `test_env_and_paths_save_only_submit_changes`：两份 `save()` 都是「比对快照 + remove 语义」。
- `test_models_section_wires_drag_and_keyboard_reordering`：拖拽/键盘/接口三件套不能回退。
- `test_section_search_survives_same_section_reload`：分区内 reload 不清搜索词。

## 6. 数据来源

- 运行中的 SugarAgent WebUI（`http://127.0.0.1:8192`）：`/api/model_profiles`（含 `/reorder`、`/{id}/enabled`）、`/api/skills`、`/api/extensions`（含 `/reload`）、`/api/mcp/tools`、`/api/mcp_config`、`/api/security/*`、`/api/env`、`/sessions/{id}/permissions`、路由 `/settings|/setup/env|/setup/mcp|/setup/extensions`。
- 源码：`frontend/src/app/modules/settings.js`、`app/templates/static/settings/{core.js,sections_basic.js,sections_ext.js,sections_ops.js,settings.css}`、`app/webui.py`（`_parse_env_entries` 7676、`_apply_env_updates` 7720、`_remove_env_keys` 7754、`get_env_snapshot` 8346、`save_env_snapshot` 8441、`reorder_model_profiles` 3890）、`app/model_profiles.py`（`set_profile_enabled` 1434）、`app/templates/advance_config.html`（旧拖拽实现，作为行为参照）。
- 证据文件：`workspace/设置中心验证/{verification_api_probe.py,verify_model_reorder.py,verify_settings_ui.py,check_served_assets.py,_cleanup_tmp_rule.py,tab-*.png,ui-*.png}`。
