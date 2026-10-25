"""Optional keyless lifecycle interop with an installed DSH checkout."""
import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import acp
from acp_bridge.client import DelegationClient, _descendants, _reap


@pytest.mark.skipif(not os.environ.get("DSH_ACP_CHECKOUT"), reason="set DSH_ACP_CHECKOUT to a built DSH checkout")
def test_real_dsh_lifecycle_with_python_acp_client(tmp_path):
    from security.extensions import minimal_extension_environment

    root = Path(os.environ["DSH_ACP_CHECKOUT"])
    entry = root / "apps/cli/lib/bin.js"
    assert entry.is_file(), "build the DSH CLI before running this check"
    async def scenario():
        env = minimal_extension_environment(explicit={
            "DSH_HOME": str(tmp_path / ".dsh"), "DSH_AGENTS_HOME": str(tmp_path / ".agents"),
            "DEEPSEEK_API_KEY": "sk-dummy-for-keyless-protocol-check"})
        argv = [str(entry)]
        if os.environ.get("DSH_ACP_SOURCE") == "1":
            env["TSX_TSCONFIG_PATH"] = str(root / "tsconfig.json")
            argv = ["--import", (root / "node_modules/tsx/dist/esm/index.mjs").as_uri(),
                    str(root / "apps/cli/src/bin.ts")]
        patch = root / "snapshots/acp/escalation-approved/cordis.yml"
        profile_args = ["--profile", "acp"]
        if patch.is_file():
            # DSH's own keyless ACP tests mount this overlay to supply local
            # model metadata without probing an actual provider.
            profile_args += ["--patch", str(patch)]
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        process = await asyncio.create_subprocess_exec(shutil.which("node"), *argv, *profile_args,
            cwd=tmp_path, env=env, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **flags)
        async def drain():
            tail = b""
            while chunk := await process.stderr.read(4096):
                tail = (tail + chunk)[-8000:]
            return tail.decode("utf-8", errors="replace")
        stderr = asyncio.create_task(drain())
        connection = acp.connect_to_agent(DelegationClient(), process.stdin, process.stdout, use_unstable_protocol=True)
        failure = None
        try:
            async def exchange():
                initialized = await connection.initialize(protocol_version=1, client_capabilities=acp.schema.ClientCapabilities())
                assert initialized.protocol_version == 1
                created = await connection.new_session(cwd=str(tmp_path), mcp_servers=[])
                assert created.session_id
                await connection.close_session(session_id=created.session_id)
                await connection.resume_session(session_id=created.session_id, cwd=str(tmp_path), mcp_servers=[])
                sessions = await connection.list_sessions(cwd=str(tmp_path))
                assert any(row.session_id == created.session_id for row in sessions.sessions)
                await connection.close_session(session_id=created.session_id)
            await asyncio.wait_for(exchange(), 45)
        except Exception as exc:
            failure = exc
        finally:
            children = _descendants(process.pid)
            await connection.close()
            await _reap(process, children)
            diagnostics = await stderr
        if failure is not None:
            pytest.fail("DSH lifecycle failed (" + type(failure).__name__ + "): " + diagnostics)
    asyncio.run(scenario())
