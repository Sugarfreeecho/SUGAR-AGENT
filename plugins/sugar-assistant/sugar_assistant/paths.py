"""插件数据目录解析：用户数据放宿主分配的 data 目录，不写进插件包。

优先级：
    1. `SUGAR_DATA_DIR`（显式覆盖；sidecar 子进程也用它）
    2. 宿主存储根：`PLUGIN_STORAGE_DIR` / `MYAGENT_PLUGIN_STORAGE_DIR`
       否则 `<WORK_DIR 或 项目/workspace>/.config/plugins`
    3. 退化到插件目录下的 `state/`（既无宿主也无 workspace 时）

这里**不 import 宿主模块**：CLI 在插件目录里单跑时也要能算出同一路径。
"""
from __future__ import annotations

import os
import shutil

PLUGIN_ID = "sugar-assistant"
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(os.path.dirname(PLUGIN_ROOT))  # …/plugins/<id> → 项目根
LEGACY_STATE_DIR = os.path.join(PLUGIN_ROOT, "state")
LEGACY_CONFIG = os.path.join(PLUGIN_ROOT, "config.json")


def storage_root() -> str:
    explicit = (os.getenv("PLUGIN_STORAGE_DIR") or os.getenv("MYAGENT_PLUGIN_STORAGE_DIR") or "").strip()
    if explicit:
        return os.path.abspath(explicit)
    work = os.getenv("WORK_DIR", "").strip()
    if work:
        base = work if os.path.isabs(work) else os.path.join(PROJECT_ROOT, work)
    else:
        base = os.path.join(PROJECT_ROOT, "workspace")
    return os.path.join(os.path.abspath(base), ".config", "plugins")


def data_dir(*, create: bool = True) -> str:
    explicit = os.getenv("SUGAR_DATA_DIR", "").strip()
    path = os.path.abspath(explicit) if explicit else os.path.join(storage_root(), PLUGIN_ID, "data")
    if create:
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            path = LEGACY_STATE_DIR
            os.makedirs(path, exist_ok=True)
    return path


def config_path() -> str:
    return os.path.join(data_dir(), "config.json")


def migrate_legacy() -> list[str]:
    """把旧位置（插件目录内）的文件搬到 data 目录，已存在的不覆盖。"""
    target = data_dir()
    moved: list[str] = []
    if os.path.abspath(target) == os.path.abspath(LEGACY_STATE_DIR):
        return moved
    pairs = [(LEGACY_CONFIG, os.path.join(target, "config.json"))]
    if os.path.isdir(LEGACY_STATE_DIR):
        for name in os.listdir(LEGACY_STATE_DIR):
            pairs.append((os.path.join(LEGACY_STATE_DIR, name), os.path.join(target, name)))
    for source, dest in pairs:
        if not os.path.exists(source) or os.path.exists(dest):
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            shutil.move(source, dest)
            moved.append(os.path.basename(dest))
        except OSError:
            continue
    return moved
