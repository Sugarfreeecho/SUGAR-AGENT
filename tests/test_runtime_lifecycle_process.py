"""Real supervisor/backend replacement, isolated from the user's application."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen

from app.proc_flags import hidden_flags

ROOT = Path(__file__).resolve().parents[1]


def read(url, data=None, headers=None):
    request = Request(url, data=json.dumps(data).encode() if data is not None else None,
                      headers={"Content-Type": "application/json", **(headers or {})})
    with urlopen(request, timeout=2) as response:
        return json.load(response)


def wait_for(callback, timeout=25):
    deadline = time.monotonic() + timeout
    error = None
    while time.monotonic() < deadline:
        try:
            value = callback()
            if value:
                return value
        except (OSError, ValueError) as exc:
            error = exc
        time.sleep(.1)
    raise AssertionError(f"isolated lifecycle process did not reach expected state: {error}")


def test_confirmed_restart_replaces_owned_process_once_and_restores_operation(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    entry = tmp_path / "app" / "probe_backend.py"
    entry.parent.mkdir()
    entry.write_text('''
import os, sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, APP_PATH)
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
from runtime_lifecycle import configure, register_routes, set_exit_callback
manager = SimpleNamespace(sessions_dir=Path(os.environ['PROBE_ROOT']), request_interrupt=lambda *a, **k: None)
service = configure(manager)
@asynccontextmanager
async def lifespan(app):
    service.mark_ready()
    yield
app = FastAPI(lifespan=lifespan)
register_routes(app, manager)
@app.get('/probe')
def probe(): return {'pid': os.getpid(), 'instance_id': service.instance_id}
@app.post('/tool-request')
def tool_request():
    return service.request(session_id='session', run_id='run', tool_call_id='tool', reason='隔离进程验收')
@app.post('/tool-checkpoint')
def checkpoint(restart_id: str):
    Path(os.environ['PROBE_ROOT'], 'tool-checkpoint').write_text('persisted')
    return service.checkpoint(restart_id, 'session', 'run')
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=int(os.environ['MYAGENT_SERVER_PORT']),timeout_graceful_shutdown=1))
set_exit_callback(lambda: setattr(server,'should_exit',True))
server.run()
'''.replace('APP_PATH', repr(str(ROOT / 'app'))), encoding="utf-8")
    env = os.environ.copy()
    env.update(MYAGENT_SECURITY_HOME=str(tmp_path / "security"), PROBE_ROOT=str(tmp_path), OPEN_BROWSER="0")
    base = f"http://127.0.0.1:{port}"
    log = (tmp_path / "process.log").open("w", encoding="utf-8")
    process = subprocess.Popen([sys.executable, str(ROOT / "app/lifecycle_supervisor.py"), "serve",
        "--entry", str(entry), "--port", str(port)], env=env, stdout=log, stderr=subprocess.STDOUT,
        creationflags=hidden_flags())
    try:
        status = wait_for(lambda: read(base + "/api/lifecycle/status"))
        first = read(base + "/probe")
        operation = read(base + "/tool-request", {})
        assert operation["phase"] == "awaiting_confirmation"
        time.sleep(.5)
        assert read(base + "/probe") == first
        headers = {"X-MyAgent-Lifecycle-UI": status["ui_token"]}
        decision = {"decision": "allow_once", "request_digest": operation["request_digest"]}
        endpoint = base + f'/api/lifecycle/restarts/{operation["restart_id"]}/decision'
        assert read(endpoint, decision, headers)["operation"]["phase"] == "authorized"
        assert read(endpoint, decision, headers)["operation"]["phase"] == "authorized"
        time.sleep(.5)
        assert read(base + "/probe") == first  # Human approval alone cannot skip the tool checkpoint.
        read(base + "/tool-checkpoint?restart_id=" + operation["restart_id"], {})
        def completed():
            result = read(base + "/api/lifecycle/status?restart_id=" + operation["restart_id"])
            record = result["operations"][0]
            return result if result["ready"] and record["phase"] == "completed" else None
        final = wait_for(completed)
        assert not final["operations"][0].get("forced")
        second = read(base + "/probe")
        assert second["pid"] != first["pid"]
        assert second["instance_id"] == final["operations"][0]["expected_new_instance_id"]
        assert (tmp_path / "tool-checkpoint").read_text() == "persisted"
        time.sleep(.8)
        assert read(base + "/probe") == second
    except BaseException as exc:
        log.flush()
        raise AssertionError(str(exc) + "\n" + (tmp_path / "process.log").read_text(encoding="utf-8", errors="replace")) from exc
    finally:
        # Stop only this test's owned supervisor and descendants.
        import psutil
        if process.poll() is None:
            parent = psutil.Process(process.pid)
            children = parent.children(recursive=True)
            process.terminate()
            process.wait(timeout=8)
            for child in children:
                try: child.kill()
                except psutil.NoSuchProcess: pass
        log.close()
