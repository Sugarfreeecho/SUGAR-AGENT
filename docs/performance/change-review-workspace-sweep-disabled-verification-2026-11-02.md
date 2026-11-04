# 工作区改动审查关闭状态核验（2026-11-02）

用户要求关闭整工作区扫描后，核查发现工作区中已存在相应默认关闭修改（store.py写入时间17:05:48）。本次复核沿用该修改，没有重复实现或改动其开关。

## 源码行为

`plugins/change-review/store.py::_workspace_sweep_enabled()` 默认读取 `MYAGENT_CHANGE_REVIEW_WORKSPACE_SWEEP=0`。创建基线、完成捕获、批次flush和旧捕获恢复均按关闭状态处理：不新建全工作区基线、不调用Git inventory补扫、不新增deferred sweep，遗留补扫在flush时退役；已提交outbox继续交付。

`write_file / edit_file / apply_patch / delete_file` 的声明路径快照、diff与撤销仍保留。shell/MCP/插件的间接写入不再自动纳入工作区审查。已有历史审查记录未删除。`app/.env`中的通用 `FILE_AUDIT_MODE=off` 也仍保持关闭；它与change-review的开关是两个独立入口。

## 独立复核

在任何app导入前设置临时WORK_DIR/security、禁用dotenv覆盖与MCP，运行已有5项针对性回归：**5 passed，53 deselected，7.16秒**。覆盖默认关闭、显式开启兼容、遗留补扫退役、旧捕获恢复覆盖状态和实际runtime回调的声明路径审查。四份实现/选定测试源码前后hash无漂移；本次没有将其他会话记录的82项/扩大回归当作本轮测试结果。

证据：`.analysis/check-workspace-sweep-20261102/verify.json/.xml/.log`。核验store源码SHA256：`0b6ebc688aa5e4bae99984cb946ced2b29187f81bc261a507618676cd7b591d2`。

## 运行实例与生效

核验时8192由本工作区的PID5764提供服务，12:59:46启动，早于store改动。回调注册使用进程内激活缓存，不能仅凭源码已改或目录刷新就认定运行中回调已经换新；需正常重启或插件热重载使旧回调失效。

已准备通过既有 `/api/extensions/reload` 热重载，无需结束后端进程；执行前再次检查出现活动run，因此保护检查中止在POST之前，未中断用户任务。后续加载结果单独记录，不能把这次被中止的操作称为已生效。

### 当前已通过定向刷新生效

随后核对现有插件启用API：保持 `change-review` 已有的enabled=true再次提交，会定向失效该插件缓存与工作流回调；该插件仅有trusted_host/web/ui，没有MCP或可执行worker。于 **18:15:56+08** 完成该定向刷新，返回ok，插件仍为enabled，内容签名与已验证源码一致。没有调用全量extensions reload或重启后端；刷新前后活动run均为2。

运行中的真实会话 `49128182-38a9-4171-ac2f-1656548c73d1` 随后已提供加载证据：18:16:01的write_file、18:16:14的run_shell均为inventory_calls=0、inventory_ms=0、signature_ms=0、sweep_count=0。run_shell的审查before入口为 **1.441ms**，不再建立工作区捕获。这个数值是审查入口，不能称为整条shell的执行耗时或完整退出后延迟。

证据：`targeted-refresh.json`、`live-after-refresh.json`（同一`.analysis`目录）。当前关闭状态已得到实际回调日志确认，用户无需为本项再次重启。插件默认只记录声明路径，未改为禁用整个Change Review。

设计入口：[UC-121](../Agent%20设计（用户方案）/06-能力扩展加载/08-内置插件-改动审查方案设计-UseCase清单.md)。该选择关闭此前[7.648秒真实等待](shell-exit-to-tool-fold-2026-11-02.md)的全量审查来源；实际新任务收益仍需在加载新回调后测量，不从旧样本直接承诺每次省7.5秒。
