"""Supervisor-side restart mailbox and strict backend handshake.

The Electron bridge runs ``watch`` as its own child. Unix services run ``serve``
so their process supervisor remains alive while the Python backend is replaced.
The Win32 tray uses RestartMailbox directly in its existing watchdog thread.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

from runtime_lifecycle import ENV_PREFIX, LifecycleConflict, LifecycleStore, supervisor_environment


def request_json(base_url, path, *, data=None, token="", timeout=3):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-MyAgent-Supervisor"] = token
    request = Request(base_url.rstrip("/") + path, headers=headers,
                      data=json.dumps(data).encode() if data is not None else None)
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise LifecycleConflict("backend did not acknowledge lifecycle request")
        return json.load(response)


def backend_ready(base_url, instance_id, *, timeout=1.5):
    try:
        payload = request_json(base_url, "/api/ready", timeout=timeout)
        return (payload.get("ok") is True and payload.get("protocol") == "myagent-lifecycle-v1"
                and payload.get("instance_id") == instance_id)
    except (OSError, ValueError, LifecycleConflict):
        return False


def request_manual_restart(base_url):
    status = request_json(base_url, "/api/lifecycle/status")
    request = Request(base_url.rstrip("/") + "/api/lifecycle/restarts", method="POST",
        data=json.dumps({"reason": "用户从应用菜单请求重启服务"}).encode(),
        headers={"Content-Type": "application/json", "X-MyAgent-Lifecycle-UI": status["ui_token"]})
    with urlopen(request, timeout=5) as response:
        return json.load(response)


class RestartMailbox:
    def __init__(self, supervisor_id=None, token=None, *, store=None):
        self.supervisor_id = supervisor_id or uuid.uuid4().hex
        self.token = token or secrets.token_urlsafe(32)
        self.store = store or LifecycleStore()
        self.store.heartbeat(self.supervisor_id, self.token)
        self._heartbeat_stop = None
        self._heartbeat_thread = None

    def start_heartbeat(self):
        import threading
        if self._heartbeat_thread is not None:
            return
        self._heartbeat_stop = threading.Event()
        def run():
            while not self._heartbeat_stop.wait(1):
                try:
                    self.store.heartbeat(self.supervisor_id, self.token)
                except Exception:
                    # Admission fails closed if the durable heartbeat expires.
                    pass
        self._heartbeat_thread = threading.Thread(target=run, name="lifecycle-supervisor-heartbeat", daemon=True)
        self._heartbeat_thread.start()

    def close(self):
        if self._heartbeat_stop is not None:
            self._heartbeat_stop.set()
            self._heartbeat_thread.join(timeout=2)

    def environment(self, *, operation=None):
        return {**supervisor_environment(self.supervisor_id, self.token,
            operation.get("expected_new_instance_id", "") if operation else "",
            operation["restart_id"] if operation else ""),
            ENV_PREFIX + "STATE_PATH": str(self.store.path.resolve())}

    def tick(self):
        self.store.heartbeat(self.supervisor_id, self.token)
        for record in self.store.recent(self.supervisor_id):
            limit = 120 if record["phase"] == "authorized" else 190
            if record["phase"] in {"authorized", "draining", "stopping", "starting"} and time.time() - record["updated_at"] > limit:
                self.fail(record, "重启交接或启动超时，请查看日志并核实服务状态")
        return self.store.claim(self.supervisor_id, self.token)

    def prepare(self, operation, base_url):
        try:
            payload = request_json(base_url, "/api/lifecycle/prepare",
                data={"restart_id": operation["restart_id"]}, token=self.token, timeout=65)
            if payload.get("ok") is not True or payload.get("instance_id") != operation["target_instance_id"]:
                raise LifecycleConflict("old backend did not save its state")
            if payload.get("exiting"):
                from run_ownership import _process_start_time
                instance = self.store.read_instance(operation["target_instance_id"])
                deadline = time.monotonic() + 13
                while time.monotonic() < deadline and instance.get("pid"):
                    status, started = _process_start_time(int(instance["pid"]))
                    if status == "dead" or (started is not None and instance.get("process_started_at") is not None
                        and abs(started - instance["process_started_at"]) >= .01):
                        break
                    time.sleep(.1)
                else:
                    self.store.transition(operation["restart_id"], "draining", expected={"draining"},
                                          forced=True, force_reason="旧服务保存状态后未在退出预算内结束")
            self.store.heartbeat(self.supervisor_id, self.token)
            return self.store.transition(operation["restart_id"], "stopping", expected={"draining"})
        except Exception as exc:
            self.fail(operation, "准备重启失败：" + str(exc))
            return None

    def starting(self, operation):
        return self.store.transition(operation["restart_id"], "starting", expected={"stopping"})

    def fail(self, operation, error):
        return self.store.transition(operation["restart_id"], "failed", error=str(error))


def watch(parent_pid, base_url):
    """Emit committed operations to Electron; never stop a process ourselves."""
    import psutil
    parent = psutil.Process(parent_pid)
    started = parent.create_time()
    mailbox = RestartMailbox(os.environ[ENV_PREFIX + "SUPERVISOR_ID"], os.environ[ENV_PREFIX + "TOKEN"])
    mailbox.start_heartbeat()
    import threading
    acknowledged = {}
    def receive_errors():
        for line in sys.stdin:
            try:
                message = json.loads(line)
                record = mailbox.store.read(message["restart_id"])
                if record["supervisor_id"] == mailbox.supervisor_id:
                    if message.get("ack_prepare") is not True:
                        mailbox.fail(record, str(message["error"])[:4000])
                    waiter = acknowledged.get(record["restart_id"])
                    if waiter is not None:
                        waiter.set()
            except (ValueError, KeyError):
                continue
    threading.Thread(target=receive_errors, name="lifecycle-controller-input", daemon=True).start()
    last = ""
    while parent.is_running() and abs(parent.create_time() - started) < .01:
        operation = mailbox.tick()
        if operation:
            acknowledgement = threading.Event()
            acknowledged[operation["restart_id"]] = acknowledgement
            print(json.dumps({"type": "prepare", "operation": operation}), flush=True)
            accepted = acknowledgement.wait(timeout=10)
            acknowledged.pop(operation["restart_id"], None)
            if not accepted:
                mailbox.fail(operation, "监督器未确认接管，未停止旧服务")
                continue
            if mailbox.store.read(operation["restart_id"])["phase"] != "draining":
                continue
            prepared = mailbox.prepare(operation, base_url)
            if prepared:
                mailbox.starting(prepared)
                print(json.dumps({"type": "restart", "operation": prepared}), flush=True)
        records = mailbox.store.recent(mailbox.supervisor_id)
        if records:
            record = records[0]
            signature = f'{record["restart_id"]}:{record["revision"]}'
            if signature != last:
                last = signature
                print(json.dumps({"type": "status", "operation": record}, ensure_ascii=True), flush=True)
            if record["phase"] in {"starting", "stopping", "draining"} and time.time() - record["updated_at"] > 190:
                mailbox.fail(record, "等待服务重启超时，请查看日志并核实服务状态")
        time.sleep(.5)


def stop_child(child, *, timeout=15):
    """Wait for the owned child; escalate to its verified process tree only."""
    if child.poll() is not None:
        return
    import psutil
    process = psutil.Process(child.pid)
    created = process.create_time()
    child.terminate()
    try:
        child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        if abs(process.create_time() - created) >= .01:
            raise LifecycleConflict("process identity changed while stopping")
        descendants = process.children(recursive=True)
        for descendant in reversed(descendants):
            try:
                descendant.kill()
            except psutil.NoSuchProcess:
                pass
        process.kill()
        child.wait(timeout=5)


def serve(entry, port):
    mailbox = RestartMailbox()
    mailbox.start_heartbeat()
    stopping = False
    child = None

    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def start(operation=None):
        environment = os.environ.copy()
        environment.update(mailbox.environment(operation=operation))
        environment["MYAGENT_SUPERVISOR_PID"] = str(os.getpid())
        environment["MYAGENT_SERVER_PORT"] = str(port)
        return subprocess.Popen([sys.executable, str(entry)], env=environment, cwd=str(entry.parent.parent))

    try:
        child = start()
        while not stopping:
            if child.poll() is not None:
                return child.returncode or 0
            operation = mailbox.tick()
            if operation:
                prepared = mailbox.prepare(operation, f"http://127.0.0.1:{port}")
                if prepared:
                    try:
                        stop_child(child)
                        mailbox.starting(prepared)
                        child = start(prepared)
                    except Exception as exc:
                        mailbox.fail(prepared, exc)
            time.sleep(.25)
        return 0
    finally:
        if child is not None:
            stop_child(child)
        mailbox.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("watch", "serve", "state-path"))
    parser.add_argument("--parent-pid", type=int)
    parser.add_argument("--base-url", default="http://127.0.0.1:8192")
    parser.add_argument("--entry", type=Path, default=Path(__file__).with_name("main.py"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MYAGENT_SERVER_PORT", "8192")))
    args = parser.parse_args()
    if args.mode == "state-path":
        from runtime_lifecycle import state_path
        print(json.dumps({"state_path": str(state_path().resolve())}))
        return 0
    if args.mode == "watch":
        watch(args.parent_pid, args.base_url)
        return 0
    return serve(args.entry.resolve(), args.port)


if __name__ == "__main__":
    raise SystemExit(main())
