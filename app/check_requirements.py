"""
检查 requirements.txt 中列出的包是否已安装（按当前解释器环境校验）。

由 RUN.bat / RUN.sh 在每次启动 Agent 前调用：
- 环境满足清单：静默退出 0；
- 有缺失：列出缺失项并退出 1，启动脚本据此执行
  `pip install -r requirements.txt` 补装。

实现说明：
- 单进程 `importlib.metadata` 检查（旧实现为每个包起一个 `pip show`
  子进程，单次要数分钟，无法用在启动路径上）；
- 不依赖 app/.requirements.installed 标记文件——该文件会随项目拷贝一起
  传播到其他电脑，不能代表本机解释器的真实环境（psutil 等后续新增的
  依赖曾被它误判为「已同步」而漏装）；
- 发行版名按 PEP 503 归一化匹配（`python-magic` 与 `python_magic` 等价）。
- 校验已安装版本是否满足清单的版本约束。

用法: python check_requirements.py
退出码: 0 全部已安装, 1 有缺失或无法校验
"""

from __future__ import annotations

import re
import sys
from importlib import metadata
from pathlib import Path
from typing import List

try:
    from packaging.requirements import InvalidRequirement, Requirement
    from packaging.version import InvalidVersion
except ImportError:  # 全新机器首次启动时可能尚未安装 packaging
    InvalidRequirement = Exception
    InvalidVersion = ValueError
    Requirement = None

ROOT = Path(__file__).resolve().parent
REQUIREMENTS_FILE = ROOT / "requirements.txt"


def _line_to_requirement(line: str) -> Requirement | None:
    if Requirement is None:
        return None
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    if "#" in s:
        s = s.split("#", 1)[0].strip()
    if not s:
        return None
    try:
        requirement = Requirement(s)
    except InvalidRequirement:
        return None
    if requirement.marker is not None and not requirement.marker.evaluate():
        return None
    return requirement


def load_required_requirements() -> List[Requirement]:
    if not REQUIREMENTS_FILE.is_file():
        print(f"未找到 {REQUIREMENTS_FILE}", file=sys.stderr)
        return []
    out = []
    for line in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines():
        requirement = _line_to_requirement(line)
        if requirement is not None and requirement not in out:
            out.append(requirement)
    return out


def load_required_distributions() -> List[str]:
    """Compatibility view containing only distribution names."""
    return list(dict.fromkeys(req.name for req in load_required_requirements()))


def _normalize_dist_name(name: str) -> str:
    """PEP 503 归一化：大小写与 `-` / `_` / `.` 差异不参与比较。"""
    return re.sub(r"[-_.]+", "-", str(name or "").strip()).lower()


def installed_distributions() -> dict:
    """当前解释器已安装发行版：归一化名 -> 版本。"""
    versions: dict = {}
    try:
        distributions = metadata.distributions()
    except Exception:
        return versions
    for dist in distributions:
        try:
            name = (dist.metadata or {}).get("Name")
            version = dist.version
        except Exception:
            continue
        if not name:
            continue
        versions.setdefault(_normalize_dist_name(str(name)), str(version or ""))
    return versions


def missing_distributions(
    names: List[str | Requirement], *, installed: dict | None = None
) -> List[str]:
    """返回未安装或版本不满足要求的条目，保持原顺序。"""
    env = installed_distributions() if installed is None else installed
    missing = []
    for item in names:
        requirement = _line_to_requirement(item) if isinstance(item, str) else item
        if requirement is None:
            continue
        version = env.get(_normalize_dist_name(requirement.name))
        satisfied = version is not None
        if satisfied and requirement.specifier:
            try:
                satisfied = requirement.specifier.contains(version, prereleases=True)
            except (InvalidVersion, TypeError):
                satisfied = False
        if not satisfied:
            missing.append(str(requirement))
    return missing


def main() -> int:
    if Requirement is None:
        print(
            "当前 Python 环境缺少 packaging 模块，无法解析依赖清单；"
            "请先执行: python -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1
    need = load_required_requirements()
    if not need:
        print("无依赖条目可检查，请确认 requirements.txt 存在且非空。", file=sys.stderr)
        return 1
    missing = missing_distributions(need)
    if missing:
        print("以下依赖未安装或版本不满足要求:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        print(file=sys.stderr)
        print('请执行: python -m pip install -r requirements.txt', file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
