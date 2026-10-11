# 工具按需披露

MyAgent 将模型看到的工具定义与当前会话获准执行的目录分开。内置白名单披露**默认开启**：白名单常驻工具（内置工具、会话管理、后台任务与终端工具，见 `app/tool_search.py` 的 `RESIDENT_TOOLS`）保持在工具清单中；**其余一切可执行工具（含新增的 MCP 服务器、插件工具）自动收入 tool search**，由 `tool_search`、`tool_describe`、`tool_call` 按需取用。Computer Use 即使由宿主服务提供，也按其来源参与延迟披露。

## 配置

披露策略内置（白名单常驻 + 其余全部延迟），默认开启、无需配置文件。`.config/tool_search.json` 是**可选覆盖**（例如临时切 `auto/off`、追加常驻项），可参考 `app/tool_search.json.example`；设置中心 MCP 页的「工具按需披露」卡片也可写回该文件：

```json
{
  "enabled": "on",
  "threshold_pct": 10,
  "threshold_tokens": 20000,
  "search_default_limit": 5,
  "max_search_limit": 20,
  "pinned_tools": []
}
```

- `on`（内置默认）：有可延迟工具就启用。
- `auto`：延迟工具定义的本地估算 token 达到上下文窗口的 `threshold_pct%` **或** `threshold_tokens`，即启用。工具数量不作为 token 占用的替代指标。
- `off`：恢复完整目录，不会删除任何工具。
- `pinned_tools`：以模型工具名追加常驻豁免（可覆盖白名单外的工具）。
- `defer_plugin_tools`：**已弃用**（兼容保留、忽略）；常驻与否由白名单与 pin 决定。

**配置文件不存在/被删除/损坏时使用内置默认（on），不再关闭披露。** `MYAGENT_TOOL_SEARCH=on|auto|off` 可覆盖未明确 `off` 的配置；文件明确 `off` 时环境变量不能重新开启。配置在下一次请求组装时生效。首次升级 Python 代码须重启后端；后续配置调整无需重启。

MCP 服务器支持以下增量设置，旧的逐工具开关仍然生效：

```json
{
  "servers": {
    "example": {
      "command": "example-server",
      "tools": {
        "include": [],
        "exclude": ["unused_tool"],
        "pin": ["frequent_tool"]
      }
    }
  }
}
```

选择项匹配服务器原始工具名或模型工具名；`include` 为空表示不限，`exclude` 优先，`pin` 不会重新启用被禁用或排除的工具。原有 `tools.<tool_name>` 执行契约配置继续兼容。设置中心提供按服务器批量启停已发现工具，以及常驻按钮；由 Computer Use 管理的连接继续使用原来的执行面板。插件提供的 MCP 常驻项在插件自身的服务器配置中设置。

## 模型调用与执行边界

1. `tool_search({"query": "browser navigate"})` 返回名称、短说明和来源。支持 `select:name1,name2` 精确点名、`+term` 必含关键词。
2. `tool_describe({"name": "搜索返回的名称"})` 返回完整 schema，保留原始说明和参数约束。
3. `tool_call({"name": "搜索返回的名称", "arguments": {...}})` 调用目标。

搜索和描述只读取当前会话过滤后的延迟目录。桥接只允许调用该目录中的可执行工具；不接受桥接嵌套、常驻工具借道、未知名称或非对象参数。子代理 profile 和 fork 的授权目录同样生效。

调用原件保留在模型历史中，保持函数名和 tool call ID 配对。执行副本在 Hook 与审批前解包；并行分组、CPU 限流、中断策略使用真实工具描述符，审批、权限、审计、流式结果和执行记录使用真实工具名。桥接工具等待完整模型轮次后执行，不在参数流尚未完成时抢跑。桥接 invoker 不直接执行目标工具。

已激活的目录遇到 revision 变化会重建，避免沿用过期的范围、工具开关或配置。模型配置 generation、子代理类型、MCP 目录和配置文件变化都参与失效判断。冷启动仍先提供已就绪工具。

## 计量与验证

上下文浮窗在原有三段占用之外显示延迟工具数量与本轮工具定义的净节省估算。`deferred_tools_tokens` 是未下发 schema 的本地估算；`saved_tools_tokens` 是完整目录与实际目录的差值，已扣除三个桥接工具的开销。它们不加进本轮上下文总量；搜索返回的描述、schema 和结果仍会进入对话历史。

测试覆盖 100 个模拟 MCP 工具的目录缩减、搜索/描述/解包、授权范围、真实工具策略、Hook 顺序、历史隔离、fork/只读子代理、冷启动、配置回滚、MCP 注册筛选与批量启停，以及设置中心和上下文浮窗。模拟数据的节省率不能作为实际 MCP 配置的性能承诺；真实模型的工具选择质量需要任务级评测。

本实现保留完整工具说明，未对 MCP 描述做统一截断，也未默认禁用浏览器服务器。检索采用本地关键词打分；发现后自动将工具加入 tools 数组、BM25 和代码调用模式暂未加入。
