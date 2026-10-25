"""Static availability checks for one plugin, used by the settings check button.

The report answers "why might this enabled plugin still not work" without
executing plugin code: global switch, enablement, manifest compatibility, the
trusted-host location rule, declared Python distributions, required settings,
web/runtime entry files. Real invocation (tools, pages, worker calls) still
belongs to the diagnostic session that the button opens.
"""
from __future__ import annotations

import importlib.metadata
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from plugins import tiers
from plugins.manager import get_plugin_manager, plugins_enabled
from plugins.settings import public_plugin_settings

_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_MAX_REQUIREMENTS = 32


def _check(check_id: str, label: str, ok: bool, detail: str = "", *, fatal: bool = False) -> Dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "ok": bool(ok),
        "detail": str(detail or ""),
        "fatal": bool(fatal),
    }


def _installed_version(distribution: str) -> Optional[str]:
    try:
        return importlib.metadata.version(distribution)
    except Exception:
        return None


def declared_requirements(plugin: Any) -> List[str]:
    """Distribution names from the plugin's conventional requirements.txt."""

    path = Path(plugin.root) / "requirements.txt"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    names: List[str] = []
    for line in lines:
        value = line.split("#", 1)[0].strip()
        if not value or value.startswith("-"):
            continue
        match = _REQUIREMENT_NAME.match(value)
        if match and match.group(1) not in names:
            names.append(match.group(1))
        if len(names) >= _MAX_REQUIREMENTS:
            break
    return names


def _capabilities(plugin: Any) -> Mapping[str, Any]:
    raw = getattr(plugin, "raw_manifest", None)
    capabilities = raw.get("capabilities") if isinstance(raw, Mapping) else None
    return capabilities if isinstance(capabilities, Mapping) else {}


def plugin_availability(plugin: Any, *, manager: Any = None) -> Dict[str, Any]:
    """Return ``state`` (ready/degraded/unavailable) plus per-check evidence."""

    manager = manager or get_plugin_manager()
    plugin_id = str(plugin.plugin_id)
    enabled = manager.is_enabled(plugin_id)
    global_on = plugins_enabled()
    checks: List[Dict[str, Any]] = [
        _check("global", "插件总开关", global_on,
               "" if global_on else "PLUGINS_ENABLED 已关闭", fatal=True),
        _check("enabled", "插件已启用", enabled,
               "" if enabled else "当前显示为「未启用」", fatal=True),
    ]

    compatibility = str(getattr(getattr(plugin, "compatibility", None), "status", "") or "")
    checks.append(_check(
        "compatibility", "清单兼容性", compatibility != "unsupported",
        f"status={compatibility or 'unknown'}", fatal=True,
    ))

    capabilities = _capabilities(plugin)
    if isinstance(capabilities.get("trusted_host"), Mapping):
        from plugins.host import is_bundled_trusted_host_plugin

        trusted = is_bundled_trusted_host_plugin(plugin)
        checks.append(_check(
            "trusted_host", "宿主扩展信任路径", trusted,
            "" if trusted else "trusted_host 只允许 plugins/<插件 id> 下的随包插件", fatal=True,
        ))

    requirements = declared_requirements(plugin)
    if requirements:
        missing = [name for name in requirements if _installed_version(name) is None]
        checks.append(_check(
            "dependencies", "Python 依赖", not missing,
            "缺少：" + ", ".join(missing) if missing else f"{len(requirements)} 项已安装",
        ))

    settings = public_plugin_settings(plugin)
    if settings:
        missing_required = list(settings.get("missing_required") or [])
        checks.append(_check(
            "settings", "必填配置", not missing_required,
            "缺少：" + ", ".join(missing_required) if missing_required else "",
        ))

    web = capabilities.get("web")
    if isinstance(web, Mapping) and web.get("entry"):
        entry = Path(plugin.root) / str(web["entry"])
        checks.append(_check("web", "Web 页面入口", entry.is_file(), str(web["entry"])))

    runtime = getattr(plugin, "runtime", None)
    if runtime is not None:
        entrypoint = Path(str(runtime.entrypoint))
        checks.append(_check(
            "runtime", "插件运行时入口", entrypoint.is_file(),
            entrypoint.name, fatal=True,
        ))

    failed = [item for item in checks if not item["ok"]]
    if any(item["fatal"] for item in failed):
        state = "unavailable"
    elif failed:
        state = "degraded"
    else:
        state = "ready"
    return {
        "plugin_id": plugin_id,
        "tier": tiers.tier_of(plugin_id),
        "enabled": enabled,
        "state": state,
        "summary": "；".join(f"{item['label']}：{item['detail']}" for item in failed) or "自动检查未发现问题",
        "checks": checks,
    }


def diagnosis_prompt(
    plugin: Any,
    report: Mapping[str, Any],
    *,
    session_work_dir: Optional[str] = None,
) -> str:
    """First user turn for the diagnostic session."""

    root = Path(str(getattr(plugin, "root", "") or "")).resolve()
    manifest = Path(str(getattr(plugin, "manifest_path", "") or ""))
    capabilities = _capabilities(plugin)
    requirements = root / "requirements.txt"
    plugin_id = str(plugin.plugin_id)
    effective_work_dir = str(root) if session_work_dir is None else str(session_work_dir)
    lines = [
        f"请检查插件 `{plugin.plugin_id}`（{plugin.name} v{plugin.version}）是否真实可用，"
        "并在不可用时逐步引导我完成调测。",
        "",
        "## 插件位置",
        f"- 插件目录：`{root}`",
        f"- 清单文件：`{manifest}`",
    ]
    if effective_work_dir:
        lines.append(f"- 本次会话工作目录：`{effective_work_dir}`（相对路径即插件目录）")
    if requirements.is_file():
        lines.append(f"- 依赖清单：`{requirements}`")
    if isinstance(capabilities.get("web"), Mapping):
        lines.append(f"- 插件页面：`/plugins/{plugin_id}`")
    lines.extend([
        f"- 设置接口：`GET/PATCH /api/plugins/{plugin_id}/settings`",
        f"- 可用性接口：`GET /api/plugins/{plugin_id}/availability`",
        "",
        "## 自动检查结果",
        f"- 分级：`{report.get('tier')}`；启用状态：{'已启用' if report.get('enabled') else '未启用'}；结论：**{report.get('state')}**",
    ])
    for item in report.get("checks") or []:
        mark = "通过" if item.get("ok") else ("阻塞" if item.get("fatal") else "问题")
        detail = str(item.get("detail") or "").strip()
        lines.append(f"- [{mark}] {item.get('label')}" + (f"：{detail}" if detail else ""))
    lines.extend([
        "",
        "## 要求",
        "1. 用实际证据复核上面的结论：调用该插件提供的工具、打开它的页面接口，或跑一次最小用例；不要只复述检查结果。",
        "2. 不可用时指出具体缺什么：依赖、配置项、登录/授权、平台限制、运行时错误。",
        "3. 按步骤引导我修复：每一步给出可直接执行的命令或界面操作，一次只推进一个阻塞项，等我确认后再继续。",
        "4. 结束时给出结论：可用 / 部分可用（列出受影响能力）/ 不可用（列出原因）。",
        "5. 不要修改插件源码；需要改配置或安装依赖时先说明影响再等我确认。",
    ])
    return "\n".join(lines)


__all__ = ["declared_requirements", "diagnosis_prompt", "plugin_availability"]
