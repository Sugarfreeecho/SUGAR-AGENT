"""小Sugar助手 · 统一 IM 接入的共享核心。

分层（见设计稿）：
    channels/   每家 IM 一个薄 Adapter，只做协议 ↔ Inbound/Delivery
    core        唯一一份：准入 · 会话映射 · 幂等 · 配额 · 投递 · 提问/审批 · 角色
    bridge/     唯一与宿主耦合的地方

导入本包不产生任何网络、文件或宿主依赖副作用。
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
