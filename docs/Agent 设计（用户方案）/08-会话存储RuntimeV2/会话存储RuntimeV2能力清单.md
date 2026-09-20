# 会话存储 Runtime V2 · 能力清单（代码证据版）

> 对象：MyAgent 会话存储 Runtime V2（事件日志真源 + 投影/快照/迁移/修复）
> 代码版本：当前工作区（2026-09-20；补充运行终态、exact run 看门狗、孤儿对账与摘要提交去重）
> 图例：【图】见 `runtime-v2.architecture.html`（10 节点）；【卡】图中卡片；【单】仅本清单

## 1. 事件日志（真源）
| 能力 | 位置 | 状态 |
|---|---|---|
| SessionEventLog：events.jsonl 追加、游标读取、历史读取 | `runtime_v2/event_log.py`（777 行） | 【图】 |
| 显式错误语义：Busy 超时（RuntimeEventLogBusyError）、损坏（CorruptionError） | `event_log.py` | 【卡】 |
| 事件模式：RuntimeEvent（seq/ts/type/payload）、now_iso | `event_schema.py` | 【图】 |
| 运行时版本与开关：v2 主模式/严格模式/事务超时 | `config.py` | 【单】 |

## 2. 写路径
| 能力 | 位置 | 状态 |
|---|---|---|
| RuntimeHistoryOps：事务提交、模型历史替换、步骤计时 | `history_ops.py`（1282 行） | 【图】 |
| 恢复事务与回滚保护（配合 ReAct 的写栅栏） | `history_ops.py` + `agent_loop` | 【卡】 |
| context summary 未变化时以进程内已提交缓存跳过磁盘快照；冷未命中仍查权威状态 | `agent_loop._runtime_v2_commit_context_summary`、`_RUNTIME_V2_COMMITTED_SUMMARY` | 【单】 |
| 附件懒迁移：事件仓库边界把旧图片载荷准入为耐久引用；值对象只脱敏 | `attachment_migration.py`、`event_schema.py`、`event_log.py` | 【单】 |

## 3. 投影层
| 能力 | 位置 | 状态 |
|---|---|---|
| RuntimeProjector：事件 → 会话状态（增量投影） | `projector.py`（1270 行） | 【图】 |
| UI 投影：SSE payload 生成与回放 | `ui_projection.py`（1304 行） | 【图】 |
| 模型历史投影：Responses 续接剥离（strip continuation） | `model_projection.py` | 【图】 |
| 投影一致性检查与修复衔接 | `projector.py` + `repair.py` | 【单】 |

## 4. 快照与读取加速
| 能力 | 位置 | 状态 |
|---|---|---|
| SnapshotStore：快照写入/读取、版本化 | `snapshot_store.py`（580 行） | 【图】 |
| 快照失效与重建策略 | `snapshot_store.py` + `mirror.py` | 【卡】 |
| Blob 存储（大 payload 分离） | `blob_store.py` | 【单】 |

## 5. 镜像与旧版兼容
| 能力 | 位置 | 状态 |
|---|---|---|
| RuntimeMirror：v1 兼容镜像（读路径回退） | `mirror.py`（336 行） | 【图】 |
| legacy_compat：旧版 UI 可选事件映射与归一 | `legacy_compat.py` | 【图】 |
| 旧版事件迁移清单（legacy-only pending） | `webui._runtime_v2_legacy_only_migration_pending` | 【单】 |

## 6. 迁移、修复与压缩
| 能力 | 位置 | 状态 |
|---|---|---|
| 迁移服务：v1→v2 迁移 + 校验（VerificationError 语义） | `migration.py`（511 行） | 【图】 |
| 子代理修复服务（RuntimeV2SubagentRepairService） | `repair.py`（606 行） | 【图】 |
| 根日志修复（RootEventLogRepairService） | `root_log_repair.py`（564 行） | 【卡】 |
| 日志压缩（LogCompactionService） | `log_compaction.py` | 【图】 |
| 会话导出包含本会话可达附件 bundle | `webui._build_session_export_archive`、`attachments.lifecycle.add_bundle` | 【单】 |

## 7. 扩展与子代理状态
| 能力 | 位置 | 状态 |
|---|---|---|
| SessionExtensionStateStore：插件命名空间状态（冲突/缺失错误语义） | `extension_state.py`（432 行） | 【图】 |
| 子代理存储（RuntimeSubagentStore / SubagentRepository / SubagentState） | `subagent_store.py`、`subagent_repository.py` | 【卡】 |
| 运行注册表（RunRegistry / RunState） | `run_registry.py` | 【单】 |
| 运行身份精确到 `(session_id, run_id)`；中断 metadata 的原因/时间随更新刷新 | `agent_harness.py`、`session_lifecycle.py` | 【单】 |

## 8. 网关与服务面
| 能力 | 位置 | 状态 |
|---|---|---|
| RuntimeGateway：统一读写入口 | `gateway.py` | 【图】 |
| StreamPublisher：SSE 事件发布 | `stream_publisher.py` | 【图】 |
| SessionRepository / PermissionManager / HealthMonitor | `session_repository.py`、`permission_manager.py`、`health_monitor.py` | 【卡】 |

## 9. 运行期保障
| 能力 | 位置 | 状态 |
|---|---|---|
| 事务超时（react transaction timeout）配置 | `config.py` | 【单】 |
| 孤儿运行清理（orphan active runs） | `webui._cleanup_orphan_runtime_v2_active_runs` | 【单】 |
| 活动运行与快照缓存（sessions state snapshot cache） | `webui._build_sessions_state_snapshot_cached` | 【单】 |
| stale 扫描只消费 `running` 行并核对 exact run 本地活性；看门狗按 run 取消而非整会话取消 | `runtime_observability.scan_stale_runs`、`main.runtime_watchdog`、`cancel_run_tasks_by_id` | 【单】 |
| 生命周期事件唯一终态；线程池耗尽时同步追加兜底，避免 `run_started` 悬空为 running | `agent_loop._RuntimeV2RunLifecycle` | 【单】 |

## 10. 边界说明
- 前端消费面（SSE 渲染、断线续看）见"WebUI"清单；Runtime V2 提交点（用户轮/答复/检查点）见"ReAct 循环"清单。
- Runtime V2 保存附件引用并参与可达性扫描；附件对象授权、请求投影和全局 GC 见 [识图与多模态投影](../09-横切能力/02-识图与多模态投影方案设计-UseCase清单.md)。
- v1 遗留文件（llm_history.json 等）明确不作为上下文权威（会话存储约定）。

## 11. 版本记录

- 2026-09-20：补充 exact run 中断 metadata、run 级 stale 看门狗与生命周期终态兜底。
- 2026-09-20：补充未变化 context summary 的进程内提交去重与冷未命中权威读取边界。
