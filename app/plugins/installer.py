"""Install, update, remove, and prepare dependencies for MyAgent plugins."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence

from .loader import discover_plugins, load_plugin
from .models import PluginDefinition
from .security import PluginError, PluginValidationError, is_path_within, safe_plugin_path


CommandRunner = Callable[[Sequence[str], Path, float], subprocess.CompletedProcess[str]]


def _default_runner(
    command: Sequence[str],
    cwd: Path,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
    )


class PluginInstallError(PluginError):
    """Raised when an installation or dependency operation fails."""


class PluginInstaller:
    def __init__(
        self,
        discovery_dirs: Iterable[Path | str],
        *,
        runner: Optional[CommandRunner] = None,
    ) -> None:
        self.discovery_dirs = tuple(
            Path(item).expanduser().resolve() for item in discovery_dirs
        )
        if not self.discovery_dirs:
            raise PluginInstallError("At least one plugin discovery directory is required")
        self.runner = runner or _default_runner

    @property
    def install_root(self) -> Path:
        return self.discovery_dirs[0]

    def _run(
        self,
        command: Sequence[str],
        cwd: Path,
        *,
        timeout: float = 600,
        label: str,
    ) -> subprocess.CompletedProcess[str]:
        try:
            completed = self.runner(tuple(command), cwd, timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            raise PluginInstallError(f"{label} failed: {exc}") from exc
        if completed.returncode:
            detail = (completed.stderr or completed.stdout or "").strip()[-4096:]
            raise PluginInstallError(
                f"{label} failed with exit code {completed.returncode}"
                + (f": {detail}" if detail else "")
            )
        return completed

    @staticmethod
    def _plugin_from_source(path: Path) -> PluginDefinition:
        try:
            return load_plugin(path)
        except PluginError:
            report = discover_plugins([path])
            if len(report.plugins) == 1:
                return report.plugins[0]
            if report.errors:
                raise PluginInstallError(report.errors[0])
            raise PluginInstallError(
                f"Source must contain exactly one plugin; found {len(report.plugins)}"
            )

    def _prepare_source(
        self,
        source: str | Path,
        temporary_root: Path,
        *,
        ref: str = "",
    ) -> Path:
        source_text = str(source or "").strip()
        local = Path(source_text).expanduser()
        if local.exists():
            if local.is_dir():
                return local.resolve()
            extracted = temporary_root / "archive"
            extracted.mkdir(parents=True)
            try:
                shutil.unpack_archive(str(local.resolve()), str(extracted))
            except (shutil.ReadError, ValueError, OSError) as exc:
                raise PluginInstallError(f"Cannot unpack plugin archive: {exc}") from exc
            return extracted
        if "://" not in source_text and not source_text.startswith(("git@", "ssh:")):
            raise PluginInstallError(f"Plugin source does not exist: {source_text}")
        git = shutil.which("git")
        if not git:
            raise PluginInstallError("Git is required to install a remote plugin source")
        checkout = temporary_root / "repository"
        self._run(
            [git, "clone", "--depth", "1", source_text, str(checkout)],
            temporary_root,
            label="Git clone",
        )
        if ref:
            self._run(
                [git, "fetch", "--depth", "1", "origin", ref],
                checkout,
                label="Git fetch",
            )
            # FETCH_HEAD works for branch names, tags, and raw commits without
            # assuming the shallow clone created a local ref with the same
            # name.
            self._run(
                [git, "checkout", "--detach", "FETCH_HEAD"],
                checkout,
                label="Git checkout",
            )
        return checkout

    @staticmethod
    def _copy_source(source_root: Path, staging: Path) -> None:
        ignored = shutil.ignore_patterns(
            ".git",
            ".myagent-runtime",
            "__pycache__",
            "node_modules",
            "*.pyc",
        )
        shutil.copytree(source_root, staging, ignore=ignored)

    def _installed_plugins(self) -> tuple[PluginDefinition, ...]:
        return discover_plugins(self.discovery_dirs).plugins

    @staticmethod
    def _version_satisfies(version: str, requirement: str) -> bool:
        requirement = str(requirement or "").strip()
        if not requirement or requirement == "*":
            return True
        try:
            from packaging.specifiers import SpecifierSet
            from packaging.version import Version

            return Version(str(version)) in SpecifierSet(requirement)
        except ImportError:
            return requirement.lstrip("=") == str(version)
        except Exception as exc:
            raise PluginInstallError(
                f"Invalid plugin version requirement {requirement!r}: {exc}"
            ) from exc

    def _check_plugin_dependencies(
        self,
        plugin: PluginDefinition,
        installed: Optional[Iterable[PluginDefinition]] = None,
    ) -> None:
        raw = plugin.dependencies.get("plugins")
        if raw is None:
            return
        if not isinstance(raw, Mapping):
            raise PluginInstallError("dependencies.plugins must be an object")
        available = {
            item.plugin_id: item.version
            for item in (installed if installed is not None else self._installed_plugins())
        }
        available[plugin.plugin_id] = plugin.version
        missing = []
        for dependency_id, requirement in raw.items():
            installed_version = available.get(str(dependency_id))
            if installed_version is None:
                missing.append(f"{dependency_id} ({requirement or '*'}) is not installed")
            elif not self._version_satisfies(installed_version, str(requirement or "*")):
                missing.append(
                    f"{dependency_id} requires {requirement}, found {installed_version}"
                )
        if missing:
            raise PluginInstallError("Unsatisfied plugin dependencies: " + "; ".join(missing))

    def install(
        self,
        source: str | Path,
        *,
        replace: bool = False,
        ref: str = "",
        install_dependencies: bool = False,
    ) -> Dict[str, Any]:
        install_root = self.install_root
        install_root.mkdir(parents=True, exist_ok=True)
        staging_root = install_root / ".myagent-staging"
        staging_root.mkdir(exist_ok=True)
        trash_root = install_root / ".myagent-trash"
        trash_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="sugaragent-plugin-source-") as temporary:
            prepared = self._prepare_source(source, Path(temporary), ref=ref)
            source_plugin = self._plugin_from_source(prepared)
            self._check_plugin_dependencies(source_plugin)
            target = (install_root / source_plugin.plugin_id).resolve()
            if not is_path_within(target, install_root):
                raise PluginInstallError("Resolved plugin target escapes the install directory")
            existing = next(
                (
                    item
                    for item in self._installed_plugins()
                    if item.plugin_id == source_plugin.plugin_id
                ),
                None,
            )
            if existing is not None and not replace:
                raise PluginInstallError(
                    f"Plugin {source_plugin.plugin_id!r} is already installed "
                    f"at {existing.root}"
                )
            if target.exists() and (existing is None or existing.root != target):
                raise PluginInstallError(f"Plugin target already exists: {target}")

            stage = staging_root / f"{source_plugin.plugin_id}-{uuid.uuid4().hex}"
            backup: Optional[Path] = None
            try:
                self._copy_source(source_plugin.root, stage)
                staged_plugin = load_plugin(stage)
                if staged_plugin.plugin_id != source_plugin.plugin_id:
                    raise PluginInstallError("Plugin identity changed while staging")
                if existing is not None:
                    backup = trash_root / (
                        f"{existing.plugin_id}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
                    )
                    existing.root.replace(backup)
                stage.replace(target)
            except Exception:
                if stage.exists():
                    shutil.rmtree(stage, ignore_errors=True)
                if backup is not None and backup.exists() and not target.exists():
                    backup.replace(target)
                raise

        installed = load_plugin(target)
        dependency_result = None
        if install_dependencies:
            dependency_result = self.install_dependencies(installed.plugin_id)
        return {
            "action": "updated" if existing is not None else "installed",
            "plugin": installed.to_dict(),
            "previous_version": existing.version if existing is not None else None,
            "backup_path": str(backup) if backup is not None else None,
            "dependencies": dependency_result,
        }

    def _find_installed(self, plugin_id: str) -> PluginDefinition:
        matches = [
            item for item in self._installed_plugins() if item.plugin_id == str(plugin_id)
        ]
        if not matches:
            raise PluginInstallError(f"Plugin {plugin_id!r} is not installed")
        if len(matches) > 1:
            raise PluginInstallError(f"Plugin {plugin_id!r} has duplicate installations")
        return matches[0]

    def uninstall(self, plugin_id: str) -> Dict[str, Any]:
        plugin = self._find_installed(plugin_id)
        owner_root = next(
            (
                root
                for root in self.discovery_dirs
                if root == plugin.root or is_path_within(plugin.root, root)
            ),
            None,
        )
        if owner_root is None:
            raise PluginInstallError("Plugin is outside configured discovery directories")
        trash_root = owner_root / ".myagent-trash"
        trash_root.mkdir(parents=True, exist_ok=True)
        destination = trash_root / (
            f"{plugin.plugin_id}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        )
        plugin.root.replace(destination)
        return {
            "action": "uninstalled",
            "plugin_id": plugin.plugin_id,
            "version": plugin.version,
            "trash_path": str(destination),
            "recoverable": True,
        }

    @staticmethod
    def _python_dependency_spec(
        plugin: PluginDefinition,
    ) -> tuple[list[str], Optional[Path], bool]:
        raw = plugin.dependencies.get("python")
        packages: list[str] = []
        requirements: Optional[Path] = None
        if raw is False:
            return packages, requirements, False
        requested = raw is not None
        if isinstance(raw, list):
            packages = [str(item) for item in raw if str(item).strip()]
        elif isinstance(raw, Mapping):
            configured_packages = raw.get("packages")
            if isinstance(configured_packages, list):
                packages = [str(item) for item in configured_packages if str(item).strip()]
            configured_requirements = raw.get("requirements")
            if isinstance(configured_requirements, str) and configured_requirements.strip():
                requirements = safe_plugin_path(
                    plugin.root,
                    configured_requirements,
                    expected="file",
                )
        elif raw not in (None, True):
            raise PluginInstallError(
                "dependencies.python must be an array, object, true, or null"
            )
        conventional = plugin.root / "requirements.txt"
        if requirements is None and conventional.is_file():
            requirements = conventional.resolve()
            requested = True
        return packages, requirements, requested

    def install_dependencies(self, plugin_id: str) -> Dict[str, Any]:
        plugin = self._find_installed(plugin_id)
        self._check_plugin_dependencies(plugin)
        operations = []

        packages, requirements, python_requested = self._python_dependency_spec(plugin)
        if python_requested:
            runtime_root = plugin.root / ".myagent-runtime" / "python"
            python_path = (
                runtime_root / "Scripts" / "python.exe"
                if os.name == "nt"
                else runtime_root / "bin" / "python"
            )
            if not python_path.is_file():
                runtime_root.parent.mkdir(parents=True, exist_ok=True)
                self._run(
                    [sys.executable, "-m", "venv", str(runtime_root)],
                    plugin.root,
                    label="Python virtual environment creation",
                )
            if requirements is not None:
                self._run(
                    [str(python_path), "-m", "pip", "install", "-r", str(requirements)],
                    plugin.root,
                    label="Python requirements installation",
                )
                operations.append({"type": "python_requirements", "path": str(requirements)})
            if packages:
                self._run(
                    [str(python_path), "-m", "pip", "install", *packages],
                    plugin.root,
                    label="Python package installation",
                )
                operations.append({"type": "python_packages", "packages": packages})

        node_raw = plugin.dependencies.get("node")
        package_json = plugin.root / "package.json"
        node_requested = node_raw is not None or package_json.is_file()
        if node_raw is False:
            node_requested = False
        if node_requested:
            if not package_json.is_file():
                raise PluginInstallError("Node dependencies require package.json")
            bun = (
                shutil.which("bun")
                if plugin.runtime is not None and plugin.runtime.adapter == "opencode"
                else None
            )
            package_manager = bun or shutil.which("npm")
            if not package_manager:
                raise PluginInstallError("npm is required to install Node dependencies")
            args = (
                [package_manager, "install", "--production"]
                if bun
                else [package_manager, "install", "--omit=dev"]
            )
            if isinstance(node_raw, Mapping):
                extra_args = node_raw.get("args")
                if isinstance(extra_args, list):
                    args.extend(str(item) for item in extra_args)
            self._run(args, plugin.root, label="Node dependency installation")
            operations.append({"type": "node", "path": str(package_json)})

        return {
            "plugin_id": plugin.plugin_id,
            "version": plugin.version,
            "operations": operations,
            "runtime_root": str(plugin.root / ".myagent-runtime"),
        }


__all__ = ["PluginInstallError", "PluginInstaller"]
