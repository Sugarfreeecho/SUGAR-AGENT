"""Business workflows; the host adapter supplies model and Bilibili transports."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path


BUSINESS = ["bili_search", "bili_video_info", "bili_subtitle", "bili_comments", "bili_danmaku",
            "bili_emotes", "bili_emote_save", "bili_verify_comment", "bili_favorite_folders"]
BVID = re.compile(r"BV[0-9A-Za-z]{10}\Z")


class Workflow:
    def __init__(self, host):
        self.h = host
        self.lock = threading.RLock()
        self.active_dm = {}
        self.workers = {}

    @property
    def store(self):
        return self.h.store_mod.Store(self.h._home())

    def task_home(self, row):
        return self.h.tasks_mod.task_home(self.h._home(), row)

    def settings(self, policy):
        settings = self.h._settings()
        if policy.get("mode") == "duty":
            row = self.h._task_row(policy.get("task_id", ""))
            if not row or not row.get("enabled"):
                raise ValueError("任务不存在或已停用")
            settings = self.h._task_settings(row)
        elif policy.get("mode") in {"dm", "reply"}:
            if not settings.get("inbound_reply"):
                raise ValueError("入站回复已关闭")
            if policy.get("mode") == "reply" and not settings.get("inbound_public_reply", True):
                raise ValueError("回复评论已关闭")
        return settings

    def allowed(self, policy, settings=None):
        settings = settings if settings is not None else self.settings(policy)
        mode = policy.get("mode")
        if mode in {"dm", "reply"}:
            whitelist = self.h.inbound.parse_whitelist(settings.get("inbound_whitelist"))
            if str(policy.get("uid") or "") not in whitelist:
                return []
        names = list(BUSINESS)
        if settings.get("transcribe"):
            names.append("bili_transcribe")
        if mode == "duty":
            names.append("bili_record_video")
            comment, dm = self.h._write_tools_enabled(settings)
            if comment and int(settings.get("comment_per_round", 1)) > 0:
                names.append("bili_reply")
            if dm:
                names.append("bili_send_message")
        elif mode == "reply" or (mode == "dm" and settings.get("inbound_dm_public_comment", True)):
            names.append("bili_reply")
        return names

    def authorize(self, context, name, arguments):
        run_id = str(getattr(context, "run_id", "") or "")
        run = self.store.run(run_id=run_id) if run_id else None
        if run and run["session_id"] != str(getattr(context, "session_id", "")):
            raise ValueError("工具调用与运行会话不匹配")
        if not run:
            if run_id.startswith("bili-"):
                raise ValueError("本轮 B站任务已结束或缺少运行授权")
            settings = self.h._settings()
            policy = {"mode": "manual", "run_id": run_id}
            comment, dm = self.h._write_tools_enabled(settings)
            if name == "bili_record_video":
                raise ValueError("视频记账只能在值班任务中调用")
            if name == "bili_reply" and not comment:
                raise ValueError("自动评论未开启")
            if name == "bili_send_message" and not dm:
                raise ValueError("私信投递未开启")
        else:
            policy = {**run["policy"], "run_id": run_id}
            settings = self.settings(policy)
            if name not in self.allowed(policy, settings):
                raise ValueError("本轮无权使用这个工具")
        args = dict(arguments)
        if name == "bili_send_message":
            if int(args.get("receiver_uid") or 0) != int(settings.get("dm_uid") or 0):
                raise ValueError("只能投递到本任务配置的私信收件人")
        if name == "bili_reply":
            if not BVID.fullmatch(str(args.get("bvid") or "")):
                raise ValueError("BV 号无效")
            if policy.get("mode") == "reply":
                target = policy["target"]
                for key in ("bvid", "rpid", "root"):
                    if args.get(key) not in (None, "", 0, target[key]):
                        raise ValueError("只能回复本条消息所在的视频和评论楼层")
                    args[key] = target[key]
            if policy.get("mode") == "duty":
                row = self.h._task_row(policy["task_id"])
                if (args.get("rpid") or args.get("root")) and not settings.get("reply_to_comments"):
                    raise ValueError("本任务未开启回复评论")
                picked = {x["bvid"] for x in self.store.observations(row["id"], self.h.duty.day_key()) if x.get("picked")}
                if args["bvid"] not in picked:
                    raise ValueError("先用 bili_record_video 记录本任务本轮挑中的视频，再发表评论")
                # Missing dedup facts must never be interpreted as an empty table.
                self.h.duty.seen_file(self.h._home()).read_text(encoding="utf-8")
            if run:
                limit = int(settings.get("comment_per_round", 1)) if policy["mode"] == "duty" else 1
                if not self.store.reserve(run_id, "comments", limit):
                    raise ValueError("本轮评论额度已用完")
        if name == "bili_emote_save" and run and not self.store.reserve(run_id, "emotes", 3):
            raise ValueError("本轮最多收藏 3 个表情")
        return policy, settings, args

    def legacy_count(self, row, day):
        try:
            return int(json.loads((self.task_home(row) / "legacy-picks.json").read_text(encoding="utf-8")).get(day, 0))
        except (OSError, ValueError):
            return 0

    def summary(self, row, now=None):
        h = self.h
        now = now or datetime.now()
        home = self.task_home(row)
        day = h.duty.day_key(now)
        observations = self.store.observations(row["id"], day)
        picked = max(h.duty.picks_today(home, now), self.legacy_count(row, day) + sum(bool(x.get("picked")) for x in observations))
        state = h.duty.read_state(home)
        live = self.store.get("task:" + row["id"], {})
        busy = bool(live.get("run_id") and self.store.run(live["run_id"]))
        return {**row, "picked_today": picked, "remaining": max(0, row["daily_quota"]-picked),
                "rounds_today": h.duty.rounds_today(home, now), "last_round_at": state.get("last_round_at", ""),
                "busy": busy, "last_error": live.get("error", ""), "report_file": str(h.duty.report_file(home, now))}

    def record(self, policy, args):
        h = self.h
        row = h._task_row(policy.get("task_id", ""))
        if not row or policy.get("mode") != "duty":
            return {"ok": False, "error": "缺少值班任务"}
        bvid = str(args.get("bvid") or "")
        if not BVID.fullmatch(bvid):
            return {"ok": False, "error": "BV 号无效"}
        day = h.duty.day_key()
        if bvid in h.duty.seen_bvids(h._home()) and not any(x["bvid"] == bvid for x in self.store.observations(row["id"], day)):
            return {"ok": False, "error": "全局判重表已记录这条视频"}
        data = {"bvid": bvid, "picked": args.get("picked") is True, "day": day,
                    "title": " ".join(str(args.get("title") or bvid).split())[:200], "author": " ".join(str(args.get("author") or "").split())[:80],
                "reason": str(args.get("reason") or "")[:2000]}
        result = self.store.record(row["id"], day, data, row["daily_quota"], self.legacy_count(row, day))
        if result.get("ok"):
            self.render_records(row)
            result["picked_today"] = self.summary(row)["picked_today"]
        return result

    @staticmethod
    def _section(path, text):
        start, end = "<!-- sugar-bili-records:start -->", "<!-- sugar-bili-records:end -->"
        previous = path.read_text(encoding="utf-8") if path.exists() else ""
        previous = re.sub(re.escape(start) + r".*?" + re.escape(end), "", previous, flags=re.S).rstrip()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        tmp.write_text(previous + "\n\n" + start + "\n" + text + "\n" + end + "\n", encoding="utf-8")
        tmp.replace(path)

    def render_records(self, row):
        h = self.h
        with h.tasks_mod.LOCK:
            home = self.task_home(row)
            all_rows = self.store.observations(row["id"])
            days = sorted({x["day"] for x in all_rows})
            for day in days:
                rows = [x for x in all_rows if x["day"] == day and x.get("picked")]
                if row.get("report_level") != "off":
                    text = f"# {row['name']} · {day}\n\n"
                    for item in rows:
                        reason = item['reason'][:300] if row.get('report_level') == 'brief' else item['reason']
                        quoted = "\n".join("> " + line for line in reason.splitlines())
                        text += f"### {item['bvid']}\n> {item['title']} · {item['author']}\n\n{quoted}\nhttps://www.bilibili.com/video/{item['bvid']}\n\n"
                    self._section(home / "out" / (day + ".md"), text)
            for month in sorted({x["day"][:7] for x in all_rows}):
                text = "\n".join(f"- {x['day']} · {x['bvid']} · {x['title']} · {'挑中' if x['picked'] else '跳过'}：{' '.join(x['reason'].split())}" for x in all_rows if x["day"].startswith(month))
                self._section(home / "digest" / (month + ".md"), text)
            seen = h.duty.seen_file(h._home())
            old = seen.read_text(encoding="utf-8") if seen.exists() else ""
            missing = [x for x in all_rows if x["bvid"] not in old]
            if missing:
                h.duty.append_line(seen, "\n".join(f"- {x['day']} · {x['bvid']} · {row['name']}" for x in missing))

    def run_task(self, manual=False, task_id=""):
        h = self.h
        row = h._task_row(task_id)
        if not row:
            return {"ok": False, "code": "task_not_found" if task_id else "no_enabled_task", "error": "任务不存在或没有已启用任务"}
        if not row.get("enabled"):
            return {"ok": False, "code": "task_disabled", "error": "任务已停用"}
        state = self.summary(row)
        if not state["remaining"]:
            return {"ok": False, "code": "quota_exhausted", "error": "本任务今日额度已用完"}
        settings = h._task_settings(row)
        if h.bili_client.load_credential(h._home()) is None or h.inbound.auth_expired(h._home()):
            return {"ok": False, "error": "B站未登录"}
        sid = h._ensure_task_session(row, settings)
        run_id = "bili-duty-" + uuid.uuid4().hex
        policy = {"mode": "duty", "task_id": row["id"], "run_id": run_id}
        policy["allowed"] = self.allowed(policy, settings)
        self.store.put("task:" + row["id"], {"run_id": run_id, "error": ""})
        started = time.monotonic()
        home = self.task_home(row)
        h.duty.log(h._home(), f"任务「{row['name']}」开始（{'手动' if manual else '自动'}），session={sid}")
        try:
            result = h._run_round_blocking(h.build_prompt(settings), sid, run_id,
                                           budget=h._round_budget_seconds(settings), allow=policy["allowed"], policy=policy)
            result = result or {"ok": True}
        except Exception as exc:
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        if result.get("busy"):
            self.store.put("task:" + row["id"], {"run_id": "", "error": ""})
            return {**result, "session_id": sid, "task_id": row["id"]}
        picked = state["picked_today"]
        try:
            self.render_records(row)
            picked = self.summary(row)["picked_today"]
            h.duty.note_round(home, picked=picked, note=result.get("error", ""))
            if row.get("report_level") != "off":
                note = "完成" if result.get("ok") else "失败：" + str(result.get("error") or "未知原因")
                h.duty.append_line(h.duty.report_file(home),
                    f"- {datetime.now():%H:%M:%S} 本轮{'手动' if manual else '自动'}运行：{' '.join(note.split())}；今日挑中 {picked} 条。")
        except Exception as exc:
            result = {**result, "ok": False, "error": str(result.get("error") or "") + f"；保存任务产物失败：{type(exc).__name__}: {exc}"}
        finally:
            self.store.put("task:" + row["id"], {"run_id": "", "error": result.get("error", "")})
        favorite = {"ok": True, "skipped": "未配置自动收藏"}
        if picked and int(settings.get("fav_folder_id") or 0):
            favorite = h.favorite_today_blocking("随任务", task_id=row["id"])
        elapsed = int(time.monotonic()-started)
        h.duty.log(h._home(), f"任务「{row['name']}」结束，用时 {elapsed}s，今日已挑 {picked} 条；{'完成' if result.get('ok') else result.get('error')}")
        return {**result, "session_id": sid, "task_id": row["id"], "picked_today": picked,
                "elapsed_seconds": elapsed, "favorite": favorite}

    async def send(self, key, job_key, run_id, kind, target, body, *, picture=None):
        """Write intent before network I/O; ambiguous outcomes are never resent."""
        target = dict(target)
        if picture:
            target["_picture"] = picture
        row = self.store.prepare_send(key, job_key, run_id, kind, target, body)
        if row["status"] == "sent":
            return json.loads(row["receipt"])
        if row["status"] in {"sending", "unknown"}:
            raise RuntimeError("发送结果待核对，已阻止重复发送")
        logical_key = key
        job = self.store.job(job_key) if job_key else None
        uid = str(target.get("uid") or target.get("_sender_uid") or ((job or {}).get("event") or {}).get("uid") or "")
        if job_key:
            settings = self.h._settings()
            event = (job or {}).get("event") or {}
            if not settings.get("inbound_reply") or (event.get("channel") != "dm" and not settings.get("inbound_public_reply", True)):
                return {"ok": True, "queued": True, "message": "回复开关已关闭，保留待发送条目"}
            if kind == "comment" and event.get("channel") == "dm" and (
                    not settings.get("inbound_dm_public_comment", True) or
                    str(event.get("uid")) not in self.h.inbound.parse_whitelist(settings.get("inbound_whitelist"))):
                result = {"ok": False, "error": "私聊发公开评论的授权已撤销，未发送"}
                self.store.receipt(key, "failed", result)
                return result
            cfg = self.h._inbound_settings(settings)
            if not self.store.admit(logical_key, uid, cfg["cooldown"], cfg["per_hour"], outgoing=True):
                return {"ok": True, "queued": True, "message": "等待发送额度，已持久排队"}
        if not self.store.sending(key):
            raise RuntimeError("发送状态发生变化，未重复投递")
        try:
            if kind == "dm":
                result = await self.h.bili_client.send_message(self.h._home(), int(target["uid"]), body)
            else:
                result = await self.h.bili_client.reply(self.h._home(), target["bvid"], body,
                    int(target.get("rpid") or 0), int(target.get("root") or 0), picture=picture or target.get("_picture"))
        except BaseException as exc:
            self.store.receipt(key, "unknown", {"error": f"{type(exc).__name__}: {exc}"})
            raise
        success = bool(result.get("success") or result.get("ok"))
        self.store.receipt(key, "sent" if success else ("unknown" if result.get("uncertain") else "failed"), result)
        if success and job_key:
            self.store.note_sent(uid, logical_key)
        return result

    async def tool_send(self, policy, kind, target, body, picture=None):
        run_id = policy.get("run_id", "")
        job_key = policy.get("job_key", "")
        target = {**target, "_sender_uid": str(policy.get("uid") or "")}
        digest = hashlib.sha256(json.dumps([kind, target, body], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        key = (job_key or run_id or "manual") + ":" + digest
        if policy.get("mode") == "duty" and kind == "comment":
            key = "duty-comment:" + target["bvid"]
        return await self.send(key, job_key, run_id, kind, target, body, picture=picture)

    def session_for(self, kind, key, context):
        display_key = key
        credential = self.h.bili_client.load_credential(self.h._home())
        account = str(getattr(credential, "dedeuserid", "") or "")
        if account:
            key = account + ":" + key
        from agent_harness import session_manager
        with self.lock:
            sid = self.store.bind(kind, key)
            if not sid and kind == "dm":
                sid = str(self.h._dm_map().get(key) or "")
            if sid:
                try:
                    alive = session_manager.get_session_summary(sid) is not None
                except Exception:
                    alive = True
                if alive:
                    session_manager.set_session_system_context(sid, context, mode="replace")
                    self.store.bind(kind, key, sid)
                    return sid
            profile = str(self.h._settings().get("duty_model_profile") or "")
            sid, *_ = session_manager.get_or_create_session(None, model_profile_id=profile, system_context=context, system_context_mode="replace")
            session_manager.set_session_name(sid, ("B站私信·UID" if kind == "dm" else "B站回复·") + display_key)
            self.store.bind(kind, key, sid)
            return sid

    def dm_context(self, uid):
        return self.h._render_system_prompt("dm", {"uid": uid})

    def comment_context(self, target):
        return self.h._render_system_prompt("reply", target)

    async def dispatch(self):
        settings = self.h._settings()
        credential = self.h.bili_client.load_credential(self.h._home())
        if self.h._runtime.get("account_changing") or credential is None or not settings.get("inbound_reply") or self.h.inbound.auth_expired(self.h._home()):
            return
        for slot, task in list(self.workers.items()):
            if task.done():
                try:
                    task.result()
                except BaseException as exc:
                    self.h.duty.log(self.h._home(), f"入站工作任务结束：{type(exc).__name__}: {exc}")
                self.workers.pop(slot, None)
        cfg = self.h._inbound_settings(settings)
        for job in self.store.jobs(ready=True):
            event, key = job["event"], job["key"]
            if event.get("account_uid") and event["account_uid"] != str(getattr(credential, "dedeuserid", "")):
                self.store.finish(key, "skipped", "登录账号已切换，不能用当前账号回复旧消息")
                continue
            channel, uid = event.get("channel"), str(event.get("uid") or "")
            if not self.h.inbound.channel_enabled(cfg["channels"], channel):
                continue
            if channel != "dm" and not settings.get("inbound_public_reply", True):
                continue
            slot = "dm:" + uid if channel == "dm" else "public"
            if slot in self.workers:
                if channel == "dm":
                    self.attach_dm(job)
                continue
            if len(self.workers) >= 4:
                break
            if not self.store.admit(key, uid, cfg["cooldown"], cfg["per_hour"]):
                self.store.defer(key, 30, "等待同人冷却或每小时额度")
                continue
            if not self.store.claim(key):
                continue
            self.workers[slot] = asyncio.create_task(asyncio.to_thread(self.process, self.store.job(key)))

    def attach_dm(self, job):
        from agent_loop import enqueue_session_steer
        uid = str(job["event"]["uid"])
        with self.lock:
            active = self.active_dm.get(uid)
            trusted = uid in self.h.inbound.parse_whitelist(self.h._settings().get("inbound_whitelist"))
            if not active or not active["accepting"] or active["trusted"] != trusted:
                return False
            if not self.store.claim(job["key"], active["session_id"], active["run_id"]):
                return False
            client = "bili-dm:" + job["key"] + ":" + str(job["attempts"]+1)
            queued = enqueue_session_steer(active["session_id"], job["event"]["text"], client_id=client, mode="append")
            if not queued.get("ok"):
                self.store.finish(job["key"], "retry", "消息插入失败")
                return False
            active["steers"][client] = job["key"]
            active["jobs"].append(job["key"])
            self.store.annotate(job["key"], {"coalesced_into": active["jobs"][0]}, active["session_id"], active["run_id"])
            return True

    def process(self, job):
        key, event = job["key"], job["event"]
        try:
            prior = self.store.deliveries(job_key=key)
            if prior:
                async def resume():
                    for delivery in prior:
                        if delivery["status"] == "prepared":
                            receipt = await self.send(delivery["key"], key, delivery["run_id"], delivery["kind"], json.loads(delivery["target"]), delivery["body"])
                            if receipt.get("queued"):
                                break
                asyncio.run(resume())
                self.finish_job(key, {}, "")
                return
            if event.get("channel") == "dm":
                self.process_dm(job)
            else:
                self.process_comment(job)
        except Exception as exc:
            self.finish_job(key, {"ok": False}, f"{type(exc).__name__}: {exc}")

    def finish_job(self, key, result, error):
        deliveries = self.store.deliveries(job_key=key)
        statuses = {x["status"] for x in deliveries}
        if statuses & {"sending", "unknown"}:
            status = "unknown"
        elif "failed" in statuses:
            status = "failed"
        elif "prepared" in statuses:
            status = "pending"
        elif "sent" in statuses:
            status = "partial" if error else "sent"
        elif error:
            status = "failed" if result.get("permanent") else "retry"
        else:
            status = "skipped"
        self.store.finish(key, status, error, result)
        self.h.duty.log(self.h._home(), f"入站 {key}：{status}" + (f" · {error[:160]}" if error else ""))

    def process_dm(self, job):
        h, event, key = self.h, job["event"], job["key"]
        uid = str(event["uid"])
        sid = self.session_for("dm", uid, self.dm_context(uid))
        run_id = "bili-dm-" + uuid.uuid4().hex
        policy = {"mode": "dm", "uid": uid, "job_key": key}
        policy["allowed"] = self.allowed(policy)
        active = {"session_id": sid, "run_id": run_id, "accepting": True, "jobs": [key],
                  "steers": {}, "consumed": {key}, "trusted": bool(policy["allowed"])}
        with self.lock:
            self.active_dm[uid] = active
        self.store.annotate(key, session_id=sid, run_id=run_id)
        posted, last_body, reply_rows = set(), "", []

        async def on_event(item):
            nonlocal last_body
            kind = item.get("type")
            if kind == "user_steer":
                with self.lock:
                    consumed_key = active["steers"].get(item.get("client_id"))
                    if consumed_key:
                        active["consumed"].add(consumed_key)
                        self.store.annotate(consumed_key, {"consumed": True})
                return
            if kind not in {"llm_response", "final"} or item.get("execution_status") == "interrupted":
                return
            body = str(item.get("content") or "").strip()
            if kind == "final":
                with self.lock:
                    active["accepting"] = False
                if body == last_body:
                    return
            ident = (item.get("react_iter"), body)
            if not body or ident in posted:
                return
            posted.add(ident)
            last_body = body
            if len(body) > 500:
                raise ValueError("私聊回复超过500字，本轮私聊未投递")
            reply_rows.append(body)

        result, error = {}, ""
        try:
            prompt = "继续回复会话中上次未处理完的私信。" if job.get("result", {}).get("consumed") else "对方发来私信：\n" + event["text"]
            result = h._run_round_blocking(prompt, sid, run_id, budget=180, allow=policy["allowed"], policy=policy, on_event=on_event) or {}
            error = result.get("error", "")
            with self.lock:
                active["accepting"] = False
            if result.get("ok") and not error:
                # Commit the validated round together before the first network call.
                # Recovery can then deliver every remaining row without re-generation.
                rows = [(f"{key}:reply:{number}", key, run_id, "dm", {"uid": uid}, body)
                        for number, body in enumerate(reply_rows)]
                self.store.prepare_batch(rows)
                async def flush():
                    for reply_key, _, _, _, _, body in rows:
                        receipt = await self.send(reply_key, key, run_id, "dm", {"uid": uid}, body)
                        if not (receipt.get("success") or receipt.get("ok")):
                            raise RuntimeError("私信投递失败：" + str(receipt.get("error") or receipt.get("message") or "未知原因"))
                        if receipt.get("queued"):
                            break
                asyncio.run(flush())
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            if isinstance(exc, ValueError):
                result["permanent"] = True
        finally:
            with self.lock:
                active["accepting"] = False
                self.active_dm.pop(uid, None)
        self.finish_job(key, {**result, "session_id": sid}, error)
        for attached in active["jobs"][1:]:
            if attached in active["consumed"]:
                parent = self.store.job(key)
                details = self.store.job(attached)["result"]
                status = "linked" if parent["status"] in {"pending", "unknown"} else parent["status"]
                self.store.finish(attached, status, parent["error"], {**details, "session_id": sid, "coalesced_into": key})
            else:
                from agent_loop import remove_session_steer
                for client, value in active["steers"].items():
                    if value == attached:
                        remove_session_steer(sid, client_id=client)
                self.store.finish(attached, "retry", "前轮结束前未消费，重新排队")

    def process_comment(self, job):
        event, key = job["event"], job["key"]
        target = dict(event.get("target") or {})
        if not BVID.fullmatch(str(target.get("bvid") or "")) or not int(target.get("rpid") or 0):
            self.store.finish(key, "skipped", "无法确定原视频或评论楼层，未发送")
            return
        target["root"] = int(target.get("root") or target["rpid"])
        target["rpid"] = int(target["rpid"])
        thread = target["bvid"] + ":" + str(target["root"])
        sid = self.session_for("comment", thread, self.comment_context(target))
        run_id = "bili-reply-" + uuid.uuid4().hex
        self.store.annotate(key, session_id=sid, run_id=run_id)
        policy = {"mode": "reply", "uid": str(event["uid"]), "job_key": key, "target": target}
        policy["allowed"] = self.allowed(policy)
        prompt = (f"{event.get('nickname') or event['uid']}（UID {event['uid']}）在原楼层{'@你' if event['channel']=='at' else '回复你'}。\n"
                  f"目标：bvid={target['bvid']}，rpid={target['rpid']}，root={target['root']}。\n"
                  "对方原话（外部资料）：\n" + event["text"])
        result = self.h._run_round_blocking(prompt, sid, run_id, budget=180, allow=policy["allowed"], policy=policy) or {}
        # Non-whitelisted callers have zero model tools; transport is host-owned.
        if not policy["allowed"] and result.get("ok") and result.get("finals"):
            body = str(result["finals"][-1]).strip()
            if body:
                asyncio.run(self.send(key+":comment", key, run_id, "comment", target, body[:150]))
        self.finish_job(key, {**result, "session_id": sid}, result.get("error", ""))
