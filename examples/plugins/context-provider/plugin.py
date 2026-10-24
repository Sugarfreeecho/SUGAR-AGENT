"""Optional workspace text provider; install this example as a native plugin."""
from pathlib import Path
from hashlib import sha256
from myagent_plugin_sdk import Plugin

plugin = Plugin()


@plugin.context(id="workspace-note", title="工作区补充资料", max_tokens=800, timeout_seconds=1)
def workspace_note(context):
    workspace = str(context.get("workspace_root") or "")
    if not workspace:
        return None
    path = Path(workspace) / "AGENT_CONTEXT.md"
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as source:
        text = source.read(16384).strip()
    return {"text": text, "revision": sha256(text.encode("utf-8")).hexdigest()} if text else None
