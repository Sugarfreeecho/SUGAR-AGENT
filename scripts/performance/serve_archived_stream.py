"""Serve immutable archived assets plus deterministic local SSE replay fixtures.

No production backend is started or contacted. Open a printed URL in a foreground
browser and use the replay controls. Results are saved in the temporary work dir.
"""
from __future__ import annotations

import json
import argparse
import mimetypes
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / ".git/archived-stream-replay-work.json").read_text(encoding="utf-8"))
WORK = Path(MANIFEST["work"])
CORPUS = json.loads((WORK / "corpus.json").read_text(encoding="utf-8"))
REAL_PATH = WORK / "real-session-replay.json"
REAL = json.loads(REAL_PATH.read_text(encoding="utf-8")) if REAL_PATH.is_file() else None
PORTS = []


def handler_for(version):
    directory = Path(version["directory"])
    execution_updates = "parsed.type === 'execution_update'" in (directory / "embedded/sse.js").read_text(encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def data(self, data, content_type="application/json; charset=utf-8", status=200):
            if not isinstance(data, bytes):
                data = (data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path == "/":
                html = (directory / "site/index.html").read_text(encoding="utf-8")
                config = {"version": version["version"], "js": version["js"], "css": version["css"], "js_sha256": version["js_sha256"]}
                inject = '<script>window.__REPLAY_CONFIG__=' + json.dumps(config) + ';</script><script src="/__bench/bootstrap.js"></script>'
                html = html.replace("<head>", "<head>" + inject, 1)
                runner = '/__real/runner.js' if query.get('real') == ['1'] else '/__bench/runner.js'
                html = html.replace("</body>", '<script src="' + runner + '"></script></body>')
                return self.data(html, "text/html; charset=utf-8")
            if path == "/__real/session" and REAL:
                return self.data(REAL)
            if path == "/__real/versions":
                return self.data(PORTS)
            if path == "/__real/runner.js":
                return self.data((HERE / "real_session_runner.js").read_bytes(), "application/javascript; charset=utf-8")
            if path == "/__real/stream" and REAL:
                return self.real_stream(query)
            if path.startswith("/__bench/"):
                if path == "/__bench/corpus":
                    return self.data(CORPUS)
                if path == "/__bench/stream":
                    return self.stream(query)
                name = path.rsplit("/", 1)[-1]
                if name in ("bootstrap.js", "runner.js"):
                    return self.data((HERE / ("archived_stream_" + name)).read_bytes(), "application/javascript; charset=utf-8")
            if path == "/api/extensions":
                return self.data({"ui_contributions": [{"plugin_id": "change-review", "id": "chat", "slot": "chat.extension", "renderer": {"module": "/plugin-assets/change-review/web/change-review.js", "style": "/plugin-assets/change-review/web/change-review.css"}}]})
            if path.startswith("/api/") or path.startswith("/sessions"):
                if path == "/sessions":
                    return self.data({"sessions": [], "archived_count": 0})
                if "model" in path:
                    return self.data({"profiles": [], "models": [], "items": []})
                return self.data({"items": [], "events": [], "messages": [], "sessions": [], "panels": [], "active": False, "ok": True})
            if path.startswith("/plugin-assets/"):
                dest = directory / "plugins" / path[len("/plugin-assets/"):]
            elif path.startswith("/static/"):
                dest = directory / path.lstrip("/")
            else:
                dest = directory / "site" / path.lstrip("/")
            if dest.resolve().is_relative_to(directory.resolve()) and dest.is_file():
                return self.data(dest.read_bytes(), mimetypes.guess_type(str(dest))[0] or "application/octet-stream")
            return self.data({}, status=404)

        def do_POST(self):
            payload = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if self.path == "/__bench/result":
                result = json.loads(payload)
                name = f"{version['version']}-{result.get('scenario', 'unknown')}-{result.get('trial', 0)}-{result.get('probe', 'motion')}.json"
                (WORK / name).write_bytes(payload)
                print(json.dumps({"saved": name, "summary": result.get("summary"), "valid": result.get("valid")}, ensure_ascii=False), flush=True)
            elif self.path == "/__real/result":
                result = json.loads(payload)
                name = f"real-{version['version']}-{int(result['trial'])}.json"
                (WORK / name).write_bytes(payload)
                print(json.dumps({"saved": name, "verified_text": result.get("verified_text"),
                                  "max_raf_gap_ms": result.get("max_raf_gap_ms")}), flush=True)
            return self.data({"ok": True})

        def real_stream(self, query):
            segment = next(row for row in REAL["segments"] if row["id"] == query.get("segment", ["37"])[0])
            speed = float(query.get("speed", ["1"])[0])
            if speed not in (0.5, 1.0, 2.0):
                return self.data({"error": "Invalid speed"}, status=400)
            after = int(query.get("after", ["0"])[0])
            packets = [packet for packet in segment["packets"] if packet["seq"] > after]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            started = time.perf_counter()
            offset = packets[0]["at_ms"] if packets else 0
            try:
                for packet in packets:
                    delay = started + (packet["at_ms"] - offset) / (1000 * speed) - time.perf_counter()
                    if delay > 0:
                        time.sleep(delay)
                    # Durable execution replay is a supported original SSE path.
                    # Text, identity and timestamp come directly from the journal.
                    event = {"type": "execution_update", "update": packet["update"],
                             "session_id": "replay-session", "run_id": segment["run_id"],
                             "runtime_seq": packet["seq"], "seq": packet["seq"],
                             "__original_timestamp": packet["timestamp"],
                             "__original_offset_ms": packet["at_ms"],
                             "__server_planned_ms": (packet["at_ms"] - offset) / speed,
                             "__server_elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}
                    if not execution_updates:
                        # Older archives have the pre-execution-record UI API.
                        # Translate the same original text to that API only.
                        update = packet["update"]
                        if "text_delta" in update:
                            event.update(type="llm_reasoning_delta", ephemeral=True, delta=update["text_delta"])
                        elif "content" in update:
                            event.update(type="llm_reasoning", content=update["content"])
                        else:
                            continue
                        event.update(react_iter=update.get("react_iter"), execution_id=update["execution_id"],
                                     process_group_id=update.get("process_group_id"),
                                     execution_runtime_seq=packet["seq"])
                    self.wfile.write(("data: " + json.dumps(event, ensure_ascii=False) + "\n\n").encode("utf-8"))
                    self.wfile.flush()
            except ConnectionError:
                pass
            self.close_connection = True

        def stream(self, query):
            # A steady 50 chars/s cadence with three deterministic 700ms network
            # pauses. This exercises stop/resume without injecting CPU stalls.
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            unit = "逐字输出与自动换行需要连续跟随；Reading code and verifying each result while the process stream continues. "
            sid = query.get("sid", ["replay-session"])[0]
            text = unit * 20
            started = time.perf_counter()
            seq = 0
            try:
                for step in range(240):
                    planned = step * .08 + .7 * sum(step >= pause for pause in (60, 120, 180))
                    delay = started + planned - time.perf_counter()
                    if delay > 0:
                        time.sleep(delay)
                    delta = text[step * 4:step * 4 + 4]
                    seq += 1
                    event = {"type": "llm_reasoning_delta", "ephemeral": True, "delta": delta, "react_iter": 401, "stream_seq": seq, "seq": seq,
                             "session_id": sid, "run_id": "replay-run", "execution_id": "replay-live", "process_group_id": "replay-process", "execution_runtime_seq": seq,
                             "__replay_planned_ms": round(planned * 1000, 3)}
                    self.wfile.write(("data: " + json.dumps(event, ensure_ascii=False) + "\n\n").encode("utf-8"))
                    self.wfile.flush()
            except ConnectionError:
                pass
            self.close_connection = True

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-ports", action="store_true", help="Restart the helper at its last printed URLs")
    args = parser.parse_args()
    previous = {}
    if args.reuse_ports:
        previous = {row["version"]: urlparse(row["url"]).port
                    for row in json.loads((WORK / "servers.json").read_text(encoding="utf-8"))}
    for version in MANIFEST["versions"]:
        server = ThreadingHTTPServer(("127.0.0.1", previous.get(version["version"], 0)), handler_for(version))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        PORTS.append({"version": version["version"], "url": f"http://127.0.0.1:{server.server_port}/"})
    (WORK / "servers.json").write_text(json.dumps(PORTS, indent=2), encoding="utf-8")
    print(json.dumps({"work": str(WORK), "servers": PORTS}), flush=True)
    threading.Event().wait()


if __name__ == "__main__":
    main()
