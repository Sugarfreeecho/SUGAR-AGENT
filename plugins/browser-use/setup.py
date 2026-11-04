"""Local, fixed-path setup actions for the browser connection settings."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .runtime_paths import node_executable, runtime_installed, is_packaged

ROOT = Path(__file__).resolve().parents[2]
EXTENSION = ROOT / "browser-extension" / "dist"
NODE = Path(__file__).parent / "node"
_installation = None
_install_state = {"status": "idle", "error": ""}


def snapshot():
    try:
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        version = str(manifest["version"])
        ready = all((EXTENSION / name).is_file() for name in ("sidepanel.html", "background.js", "sidepanel.js"))
    except (OSError, ValueError, KeyError):
        version, ready = "", False
    archive = ROOT / "outputs" / "browser-extension" / ("sugaragent-browser-" + version + ".zip")
    return {"extension_ready": ready, "extension_directory": str(EXTENSION), "version": version,
            "download_ready": bool(version and archive.is_file()), "node_available": bool(node_executable(ROOT)),
            "runtime_installed": runtime_installed(NODE), "runtime_bundled": is_packaged(ROOT),
            "node_source": "bundled" if (ROOT / "node" / "node.exe").is_file() else "system" if node_executable(ROOT) else "missing",
            "installation": dict(_install_state)}


async def install_runtime():
    global _installation, _install_state
    if _installation and not _installation.done():
        return dict(_install_state)
    if is_packaged(ROOT):
        if node_executable(ROOT) and runtime_installed(NODE):
            return {"status": "succeeded", "error": ""}
        raise ValueError("安装包中的浏览器运行组件不完整，请修复或重新安装 SugarAgent。")
    node = node_executable(ROOT)
    if not node or not shutil.which("npm"):
        raise ValueError("请先安装 Node.js 22.18 或更高版本，再重新检测。")
    # Invoke npm's JS entry with Node directly: no cmd.exe string construction
    # and no package names or paths accepted from the incoming request.
    npm_command = Path(shutil.which("npm")).resolve()
    npm = npm_command if npm_command.suffix == ".js" else npm_command.parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
    if not npm.is_file():
        raise ValueError("未找到 npm 安装入口，请修复 Node.js 安装后重新检测。")
    _install_state = {"status": "running", "error": ""}
    async def run():
        global _install_state
        allowed = {"PATH", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "TEMP", "TMP", "HOME", "LANG", "LC_ALL", "PATHEXT", "COMSPEC", "NODE_EXTRA_CA_CERTS"}
        env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
        env["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
        process = None
        try:
            process = await asyncio.create_subprocess_exec(node, str(npm), "ci", "--omit=dev", "--no-audit", "--no-fund",
                cwd=str(NODE), env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
            await asyncio.wait_for(process.communicate(), 180)
            if process.returncode:
                raise ValueError("安装未完成，请检查网络后重试。可在高级信息中复制手动安装命令。")
            _install_state = {"status": "succeeded", "error": ""}
        except (OSError, ValueError, asyncio.TimeoutError) as error:
            if process and process.returncode is None:
                process.kill()
                await process.wait()
            _install_state = {"status": "failed", "error": str(error) or "安装超时，请检查网络后重试。"}
    _installation = asyncio.create_task(run())
    return dict(_install_state)


def reveal_extension():
    if not snapshot()["extension_ready"]:
        raise ValueError("扩展尚未构建，请先完成构建或下载扩展包。")
    path = str(EXTENSION.resolve(strict=True))
    if os.name == "nt":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
