# 镜像、兼容与服务面 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `d022831`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`runtime_v2/mirror.py`（336 行）、`legacy_compat.py`、`gateway.py`、`stream_publisher.py`、`session_repository.py`、`permission_manager.py`、`health_monitor.py`。
- 上级：`00-会话存储RuntimeV2整体设计.md`

---

## 1. 功能定位

"对外接口与兼容层"：旧世界能读、新世界统一入口、运行状态可观测。

## 2. UseCase

### UC-8F1 镜像
- **触发**：旧读取路径仍在使用。
- **预期现象**：关键事件（如 context_summary_body/finished）映射为兼容形态（如 context_summary_committed）；旧接口可用；**不产生重复账**（镜像与真源一对多关系确定）。
- **依据**：`mirror.py`（L225–233）。

### UC-8F2 旧版可选事件归一
- **触发**：回放含旧版 UI 可选事件的历史。
- **预期现象**：被映射/归一为当前形态；未知旧事件被安全忽略（不炸回放）。
- **依据**：`legacy_compat.map_legacy_ui_optional_event / normalize_legacy_optional_event`。

### UC-8F3 网关
- **触发**：宿主代码需要统一读写。
- **预期现象**：经 RuntimeGateway 完成操作（封装细节）；失败返回显式错误。
- **依据**：`gateway.RuntimeGateway`。

### UC-8F4 流发布
- **触发**：需要推送事件（SSE 面）。
- **预期现象**：发布顺序与真源一致；订阅者断开不影响写入。
- **依据**：`stream_publisher.py`、`webui` SSE 段。

### UC-8F5 健康检查
- **触发**：启动/诊断。
- **预期现象**：健康监控给出心跳/时间解析结果；异常可定位。
- **依据**：`health_monitor.py / parse_iso_z`。

## 3. 边界

- 服务端 API（路由）的界面用法见 ../05-WebUI对话界面/03；
- 会话管理动作（删除/归档）属 WebUI 会话面板（../05/06）。

## 4. 依据映射

见上表。

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-812）。
