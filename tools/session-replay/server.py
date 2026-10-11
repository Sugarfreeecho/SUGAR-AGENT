"""Portable, localhost-only session replay service. Python stdlib only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import mimetypes
import os
import secrets
import shutil
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
import zipfile
from collections import OrderedDict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from session_data import ChooseSession, ImportProblem, ReplaySession, load_session, safe_name
from playback import playback_segment
from experiments import Experiments

TOOL_VERSION = "1.0.5"
ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
MAX_UPLOAD = 512 * 1024 * 1024


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


class Store:
    def __init__(self, root):
        self.root = root.resolve()
        for name in ("sessions", "results", "uploads"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.cache = OrderedDict()

    def get(self, sid):
        if not sid or any(c not in "0123456789abcdef" for c in sid) or len(sid) != 24:
            raise ImportProblem("会话 ID 无效")
        with self.lock:
            if sid not in self.cache:
                path = self.root / "sessions" / sid / "session.json"
                if not path.is_file():
                    raise ImportProblem("会话未导入")
                self.cache[sid] = ReplaySession(json.loads(path.read_text(encoding="utf-8")))
            self.cache.move_to_end(sid)
            while len(self.cache) > 3:
                self.cache.popitem(last=False)
            return self.cache[sid]

    def import_source(self, location, candidate=None):
        document = load_session(location, candidate)
        session = ReplaySession(document)
        with self.lock:
            dest = self.root / "sessions" / session.id
            write_json(dest / "session.json", document)
            catalog = session.catalog()
            write_json(dest / "catalog.json", catalog)
            self.cache[session.id] = session
            while len(self.cache) > 3:
                self.cache.popitem(last=False)
        return catalog

    def catalog(self):
        return [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted((self.root / "sessions").glob("*/catalog.json"))]

    def results(self, sid=None, compact=False):
        if sid:
            self.get(sid)
        output = []
        for path in sorted((self.root / "results").glob("*.json"), reverse=True):
            try:
                result = json.loads(path.read_text(encoding="utf-8"))
                if not sid or result.get("import_id") == sid:
                    if compact:
                        for key in ("frames", "inputs", "longtasks", "long_animation_frames", "scroll_positions", "render_calls"):
                            result.pop(key, None)
                    output.append(result)
            except (ValueError, OSError):
                continue
        return output

    def save_result(self, result):
        session = self.get(str(result.get("import_id") or ""))
        unit = next((u for u in session.units if u["id"] == result.get("segment_id")), None)
        if unit is None:
            raise ImportProblem("记录中的轮次不存在")
        result.update(tool_version=TOOL_VERSION, saved_at=datetime.now(timezone.utc).isoformat(),
                      journal_sha256=session.document["journal_sha256"],
                      source_session_id=session.document["session_id"], source_session_name=session.document["name"],
                      segment=unit)
        rid = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(4)
        result["record_id"] = rid
        write_json(self.root / "results" / (rid + ".json"), result)
        return result

    def upload_path(self, job):
        if len(job) != 32 or any(c not in "0123456789abcdef" for c in job):
            raise ImportProblem("上传 ID 无效")
        path = (self.root / "uploads" / job).resolve()
        if not path.is_relative_to((self.root / "uploads").resolve()) or not path.is_dir():
            raise ImportProblem("上传任务不存在")
        return path


def old_wire(wire, records):
    if wire.get("type") != "execution_update":
        return wire
    update = wire["update"]
    identity = str(update.get("execution_id") or "")
    from session_data import merge_record
    row = merge_record(records.get(identity, {}), update, int(wire["runtime_seq"]))
    records[identity] = row
    event = {key: wire[key] for key in ("session_id", "run_id", "runtime_seq", "seq")}
    event.update(execution_id=identity, execution_runtime_seq=wire["runtime_seq"],
                 process_group_id=row.get("process_group_id"), react_iter=row.get("react_iter"),
                 tool_call_index=row.get("tool_call_index"), tool_call_id=row.get("tool_call_id"),
                 tool_draft_key=row.get("tool_draft_key"), index=row.get("tool_call_index"),
                 id=row.get("tool_call_id"), command_preview=row.get("command_preview"),
                 attachments=row.get("attachments") or [], ui=row.get("ui"))
    if row.get("kind") in {"reasoning", "response"}:
        part = "llm_reasoning" if row["kind"] == "reasoning" else "llm_response"
        if "text_delta" in update:
            event.update(type=part + "_delta", ephemeral=True, delta=update["text_delta"])
        elif "content" in update:
            event.update(type=part, content=row.get("content") or "")
        else:
            return None
    elif row.get("kind") == "tool":
        args = row.get("args") or row.get("arguments") or row.get("arguments_raw") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {"raw": args}
        if row.get("status") in {"completed", "failed", "timed_out", "interrupted", "unknown"}:
            event.update(type="tool_call", tool=row.get("tool") or "tool", args=args,
                         result=row.get("result") or row.get("output") or row.get("stdout") or row.get("stderr") or "",
                         execution_status=row.get("status"), executed=row.get("executed", True))
        elif "name_delta" in update or "arguments_delta" in update:
            event.update(type="tool_call_delta", ephemeral=True, name_delta=update.get("name_delta") or "",
                         arguments_delta=update.get("arguments_delta") or "")
        else:
            event.update(type="tool_pending", ephemeral=True, tool=row.get("tool") or "tool", args=args)
    else:
        return None
    return event


def report_zip(results):
    out, table = io.BytesIO(), io.StringIO(newline="")
    writer = csv.writer(table)
    columns = ["record_id", "version", "run_number", "iteration", "scope", "speed", "status",
               "text_verified", "eligible_for_comparison", "mean_raf_callbacks_per_second", "p95_gap_ms",
               "max_gap_ms", "gaps_over_threshold", "longtask_count", "markers", "playback_mode", "simulated_characters_per_second",
               "experiment_config", "experiment_fingerprint", "disabled_changes", "experiment_ready", "served_js_sha256", "served_css_sha256", "follow_mode", "js_source_version", "css_source_version", "html_source_version"]
    writer.writerow(columns)
    markdown = ["# 会话重放卡顿记录", "", "RAF 回调频率不是显示器实际 FPS。暂停、切后台、变速、未完成或文字校验失败的样本不能直接用于原速前台对照。", "",
                "1007 开关默认全开。整套资源回退使用 1004 页面、脚本、样式及审阅插件；其他关闭组合仅隔离列明路径。原后端、Electron 宿主、服务器历史补页及图片上传未被重放覆盖。", "",
                "| 记录 | 版本 | 配置 | 任务/执行轮次 | 状态 | 平均回调/秒 | P95间隔ms | 最长间隔ms | 肉眼标记 |", "|---|---|---|---|---|---:|---:|---:|---:|"]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for record in results:
            unit, summary = record.get("segment", {}), record.get("summary", {})
            row = [record.get("record_id"), record.get("version"), unit.get("run_number"), unit.get("iteration"), unit.get("scope"),
                   record.get("speed"), record.get("status"), record.get("text_verified"), record.get("eligible_for_comparison"),
                   summary.get("mean_raf_callbacks_per_second"), summary.get("p95_gap_ms"), summary.get("max_gap_ms"),
                   summary.get("gaps_over_threshold"), len(record.get("longtasks", [])), len(record.get("markers", [])),
                   record.get('playback', {}).get('mode', 'journal'), record.get('playback', {}).get('characters_per_second'),
                   record.get('experiments', {}).get('label', '旧记录：未记录开关'), record.get('experiments', {}).get('fingerprint'),
                   ','.join(record.get('experiments', {}).get('disabled', [])), record.get('experiments', {}).get('ready'),
                   record.get('assets', {}).get('served_js_sha256'), record.get('assets', {}).get('served_css_sha256'), record.get('experiments', {}).get('follow_mode', '旧记录未记录'),
                   record.get('experiments', {}).get('asset_versions', {}).get('js'), record.get('experiments', {}).get('asset_versions', {}).get('css'), record.get('experiments', {}).get('asset_versions', {}).get('html')]
            writer.writerow(row)
            markdown.append(f"| {row[0]} | {row[1]} | {row[17]} ({row[18] or '—'}) | {row[2]}/{row[3]} | {row[6]} | {row[9]} | {row[10]} | {row[11]} | {row[14]} |")
            archive.writestr("records/" + record["record_id"] + ".json", json.dumps(record, ensure_ascii=False, indent=2))
        archive.writestr("summary.csv", "\ufeff" + table.getvalue())
        archive.writestr("报告.md", "\n".join(markdown) + "\n")
    return out.getvalue()


class ReplayServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, data_root):
        self.store = Store(data_root)
        self.token = secrets.token_urlsafe(32)
        self.instance = hashlib.sha256(str(ROOT).casefold().encode()).hexdigest()[:20]
        manifest = ROOT / "versions" / "manifest.json"
        if not manifest.is_file():
            raise ImportProblem("工具缺少 versions 目录，请完整解压发送包")
        self.versions = json.loads(manifest.read_text(encoding="utf-8"))["versions"]
        self.version_map = {v["version"]: v for v in self.versions}
        self.experiments = Experiments(ROOT, self.version_map)
        super().__init__(("127.0.0.1", port), Handler)
        self.url = f"http://127.0.0.1:{self.server_port}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def send(self, data, kind="application/json; charset=utf-8", code=200, filename=None):
        if not isinstance(data, bytes):
            data = (data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:; frame-ancestors 'self'")
        if filename:
            self.send_header("Content-Disposition", 'attachment; filename="' + filename + '"')
        self.end_headers()
        try:
            self.wfile.write(data)
        except ConnectionError:
            pass

    def params(self):
        parsed = urlparse(self.path)
        return unquote(parsed.path), {k: v[0] for k, v in parse_qs(parsed.query).items()}

    def body_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length < 0 or length > 32 * 1024 * 1024:
            raise ImportProblem("请求过大")
        return json.loads(self.rfile.read(length) or b"{}")

    def local_address(self, address):
        try:
            parsed = urlparse(address)
            return (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}
                    and (parsed.port or 80) == self.server.server_port
                    and parsed.username is None and parsed.password is None
                    and parsed.path in {"", "/"} and not parsed.query and not parsed.fragment)
        except ValueError:
            return False

    def authorization_error(self):
        origin = self.headers.get("Origin")
        if not self.local_address("http://" + self.headers.get("Host", "")) or (origin and not self.local_address(origin)):
            return {"code": "LOCAL_PAGE_REQUIRED", "error": "请打开本机工具地址：" + self.server.url}
        if not secrets.compare_digest(self.headers.get("X-Replay-Token", ""), self.server.token):
            return {"code": "TOKEN_EXPIRED", "error": "工具服务已重新启动，页面凭据需要更新"}
        return None

    def do_GET(self):
        if not self.local_address("http://" + self.headers.get("Host", "")):
            return self.send({"code": "LOCAL_PAGE_REQUIRED", "error": "请打开本机工具地址：" + self.server.url}, code=403)
        try:
            self.handle_get()
        except (ImportProblem, ValueError, KeyError, OSError) as exc:
            self.send({"error": str(exc)}, code=400)
        except Exception:
            traceback.print_exc()
            self.send({"error": "重放服务读取失败，详见启动窗口"}, code=500)

    def handle_get(self):
        path, query = self.params()
        if path == "/api/replay/health":
            return self.send({"ok": True, "tool_version": TOOL_VERSION, "instance": self.server.instance,
                              "url": self.server.url, "token": self.server.token, "data_dir": str(self.server.store.root),
                              "versions": self.server.versions})
        if path == "/api/replay/sessions":
            return self.send(self.server.store.catalog())
        if path == "/api/replay/session":
            return self.send(self.server.store.get(query.get("id")).catalog())
        if path == "/api/replay/segment":
            session = self.server.store.get(query.get("session"))
            with self.server.store.lock:
                return self.send(playback_segment(session.segment(query.get("segment")),
                                                 query.get("simulate", "1") == "1", query.get("cps", "120")))
        if path == "/api/replay/stream":
            return self.stream(query)
        if path == "/api/replay/results":
            return self.send(self.server.store.results(query.get("session"), compact=True))
        if path == "/api/replay/report.zip":
            return self.send(report_zip(self.server.store.results(query.get("session"))), "application/zip", filename="replay-report.zip")
        if path == "/api/replay/result.json":
            rid = query.get("record", "")
            if not re_safe_record(rid):
                raise ImportProblem("记录 ID 无效")
            data = (self.server.store.root / "results" / (rid + ".json")).read_bytes()
            return self.send(data, filename=rid + ".json")
        if path == "/":
            return self.file(ROOT / "web", "index.html")
        if path.startswith("/web/"):
            return self.file(ROOT / "web", path[5:])
        if path.startswith("/view/"):
            version = path.strip("/").split("/")[1]
            config = self.server.version_map[version]
            disabled = self.server.experiments.disabled(version, query.get("exp_off", ""))
            experiment = self.server.experiments.config(version, disabled)
            html_version = experiment["asset_versions"]["html"]
            folder = ROOT / "versions" / html_version
            html = (folder / "site/index.html").read_text(encoding="utf-8")
            for kind in ("js", "css"):
                html = html.replace('"' + self.server.version_map[html_version][kind] + '"', '"' + "/v/" + version + config[kind] + '"')
            html = html.replace('"/assets/', '"/v/' + html_version + '/assets/').replace('"/static/', '"/v/' + html_version + '/static/')
            runtime = dict(config, token=self.server.token, tool_version=TOOL_VERSION, versions=self.server.versions)
            runtime["experiments"] = experiment
            if disabled:
                suffix = "?exp_off=" + ",".join(disabled)
                for kind in ("js", "css"):
                    asset_url = "/v/" + version + config[kind]
                    html = html.replace('"' + asset_url + '"', '"' + asset_url + suffix + '"')
            inject = '<script>window.__REPLAY_CONFIG__=' + json.dumps(runtime).replace("<", "\\u003c") + ';</script><script src="/web/bootstrap.js"></script>'
            html = html.replace("<head>", "<head>" + inject, 1).replace("</body>", '<script src="/web/api.js"></script><script src="/web/viewer.js"></script></body>')
            return self.send(html, "text/html; charset=utf-8")
        if path.startswith("/v/"):
            bits = path.split("/", 3)
            version, relative = bits[2], bits[3]
            if version not in self.server.version_map:
                raise ImportProblem("前端版本不存在")
            disabled = self.server.experiments.disabled(version, query.get("exp_off", ""))
            root = ROOT / "versions" / version
            for kind in ("js", "css"):
                if relative == self.server.version_map[version][kind].lstrip("/"):
                    data, _receipt = self.server.experiments.asset(version, kind, disabled)
                    return self.send(data, "text/javascript; charset=utf-8" if kind == "js" else "text/css; charset=utf-8")
            if relative.startswith("plugin-assets/"):
                plugin_root, plugin_relative = self.server.experiments.plugin(version, relative[len("plugin-assets/"):], disabled)
                return self.file(plugin_root, plugin_relative)
            if relative.startswith("static/"):
                return self.file(root / "static", relative[len("static/"):])
            return self.file(root / "site", relative)
        if path == "/api/extensions":
            version, disabled = self.asset_settings(query)
            suffix = "?replay_version=" + version + "&exp_off=" + ",".join(disabled)
            return self.send({"ui_contributions": [{"plugin_id": "change-review", "id": "chat", "slot": "chat.extension", "renderer": {
                "module": "/plugin-assets/change-review/web/change-review.js" + suffix,
                "style": "/plugin-assets/change-review/web/change-review.css" + suffix}}]})
        if path.startswith("/static/") or path.startswith("/plugin-assets/"):
            version, disabled = self.asset_settings(query)
            root = ROOT / "versions" / self.server.experiments.asset_versions(version, disabled)["html"]
            if path.startswith("/static/"):
                return self.file(root / "static", path[len("/static/"):])
            plugin_root, relative = self.server.experiments.plugin(version, path[len("/plugin-assets/"):], disabled)
            return self.file(plugin_root, relative)
        if path.startswith(("/api/", "/sessions")):
            if path == "/sessions":
                return self.send({"sessions": [], "archived_count": 0})
            if "model" in path:
                return self.send({"profiles": [], "models": [], "items": []})
            return self.send({"items": [], "events": [], "messages": [], "sessions": [], "panels": [], "active": False, "ok": True})
        self.send({"error": "Not found"}, code=404)

    def asset_version(self):
        referer = urlparse(self.headers.get("Referer", "")).path
        parts = referer.strip("/").split("/")
        if len(parts) > 1 and parts[0] in {"v", "view"} and parts[1] in self.server.version_map:
            return parts[1]
        return self.server.versions[-1]["version"]

    def asset_settings(self, query):
        referer = urlparse(self.headers.get("Referer", ""))
        previous = {k: v[0] for k, v in parse_qs(referer.query).items()}
        version = query.get("replay_version") or self.asset_version()
        if version not in self.server.version_map:
            raise ImportProblem("前端版本不存在")
        off = query.get("exp_off", "") if "replay_version" in query else query.get("exp_off", previous.get("exp_off", ""))
        return version, self.server.experiments.disabled(version, off)

    def file(self, root, relative):
        path = (root / safe_name(relative)).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            return self.send({"error": "文件不存在"}, code=404)
        return self.send(path.read_bytes(), mimetypes.guess_type(str(path))[0] or "application/octet-stream")

    def do_POST(self):
        path, query = self.params()
        problem = self.authorization_error()
        if problem:
            return self.send(problem, code=403)
        try:
            if path == "/api/replay/import":
                request = self.body_json()
                if request.get("job"):
                    job_root = self.server.store.upload_path(request["job"])
                    location = job_root / "session.zip" if (job_root / "session.zip").is_file() else job_root
                else:
                    job_root = None
                    location = str(request.get("path") or "").strip().strip('"')
                result = self.server.store.import_source(location, request.get("candidate"))
                if job_root:
                    # This is a server-created temporary upload, never the source
                    # selected by path. Check containment before cleanup.
                    if job_root.resolve().is_relative_to((self.server.store.root / "uploads").resolve()):
                        shutil.rmtree(job_root)
                return self.send(result)
            if path == "/api/replay/upload/start":
                job = secrets.token_hex(16)
                (self.server.store.root / "uploads" / job).mkdir()
                return self.send({"job": job})
            if path == "/api/replay/upload/file":
                root = self.server.store.upload_path(query.get("job", ""))
                name = safe_name(query.get("path", "session.zip"))
                dest = (root / name).resolve()
                if not dest.is_relative_to(root):
                    raise ImportProblem("上传文件路径无效")
                remaining = int(self.headers.get("Content-Length") or 0)
                if remaining < 0 or remaining > MAX_UPLOAD:
                    raise ImportProblem("单个导入文件不能超过 512MB")
                dest.parent.mkdir(parents=True, exist_ok=True)
                with dest.open("wb") as output:
                    while remaining:
                        chunk = self.rfile.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise ImportProblem("文件上传中断")
                        output.write(chunk)
                        remaining -= len(chunk)
                return self.send({"ok": True})
            if path == "/api/replay/result":
                return self.send(self.server.store.save_result(self.body_json()))
            if path == "/api/replay/shutdown":
                self.send({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self.send({"error": "重放环境不执行真实任务"}, code=400)
        except ChooseSession as exc:
            self.send({"error": str(exc), "candidates": exc.candidates}, code=409)
        except (ImportProblem, ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
            self.send({"error": str(exc)}, code=400)
        except Exception:
            traceback.print_exc()
            self.send({"error": "导入或记录失败，详见启动窗口"}, code=500)

    def stream(self, query):
        session = self.server.store.get(query.get("session"))
        with self.server.store.lock:
            segment = playback_segment(session.segment(query.get("segment")),
                                       query.get("simulate", "1") == "1", query.get("cps", "120"))
        version = self.server.version_map[query.get("version")]
        speed = float(query.get("speed", "1"))
        if speed not in {0.5, 1.0, 2.0, 4.0, 8.0}:
            raise ImportProblem("播放速度无效")
        after = int(query.get("after", "0"))
        skip_idle = query.get("skip_idle") == "1"
        packets = [p for p in segment["packets"] if p["seq"] > after]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        started = time.perf_counter()
        records = {r["execution_id"]: dict(r) for r in segment["history_records"]}
        previous = packets[0]["at_ms"] if packets else 0
        schedule = 0.0
        try:
            for packet in packets:
                interval = max(0, packet["at_ms"] - previous)
                schedule += (min(interval, 2000) if skip_idle else interval) / speed
                previous = packet["at_ms"]
                delay = started + schedule / 1000 - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                wire = dict(packet["wire"])
                if not version["execution_updates"]:
                    wire = old_wire(wire, records)
                    if not wire:
                        continue
                wire.update(__original_timestamp=packet["timestamp"], __original_offset_ms=packet.get('original_at_ms', packet["at_ms"]),
                            __playback_offset_ms=packet['at_ms'],
                            __synthetic=bool(packet.get("synthetic")), __source_runtime_seq=packet.get("original_seq", packet["seq"]),
                            __server_planned_ms=round(schedule, 3), __server_elapsed_ms=round((time.perf_counter() - started) * 1000, 3))
                self.wfile.write(("data: " + json.dumps(wire, ensure_ascii=False) + "\n\n").encode("utf-8"))
                self.wfile.flush()
        except ConnectionError:
            pass
        self.close_connection = True


def re_safe_record(value):
    return bool(value and len(value) < 80 and all(c in "0123456789-abcdef" for c in value))


def main():
    parser = argparse.ArgumentParser(description="SugarAgent 会话重放与卡顿记录")
    parser.add_argument("sources", nargs="*", help="会话目录或 ZIP，可拖到启动.cmd")
    parser.add_argument("--port", type=int, default=54880)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    state = args.data_dir / "server.json"
    instance = hashlib.sha256(str(ROOT).casefold().encode()).hexdigest()[:20]
    if state.is_file():
        try:
            prior = json.loads(state.read_text(encoding="utf-8"))
            with urllib.request.urlopen(prior["url"] + "/api/replay/health", timeout=1) as response:
                health = json.loads(response.read())
            if health.get("instance") == instance and not args.sources:
                print("工具已运行：" + prior["url"], flush=True)
                if not args.no_browser:
                    webbrowser.open(prior["url"])
                return
        except (OSError, ValueError, KeyError):
            pass
    try:
        server = ReplayServer(args.port, args.data_dir)
    except OSError:
        server = ReplayServer(0, args.data_dir)
    write_json(state, {"url": server.url, "pid": os.getpid(), "instance": server.instance})
    for source in args.sources:
        try:
            imported = server.store.import_source(source)
            print("已导入：" + imported["name"], flush=True)
        except Exception as exc:
            print("导入失败：" + str(exc), flush=True)
    print("会话重放工具 " + TOOL_VERSION + "\n打开：" + server.url + "\n记录目录：" + str(server.store.root) + "\n关闭此窗口或按 Ctrl+C 停止服务。", flush=True)
    if not args.no_browser:
        threading.Timer(0.3, lambda: webbrowser.open(server.url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("启动失败：" + str(exc), file=sys.stderr, flush=True)
        sys.exit(1)
