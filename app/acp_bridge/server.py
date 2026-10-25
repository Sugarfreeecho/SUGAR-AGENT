"""DSH-compatible, automation-oriented ACP v1 agent facade."""
from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import acp
from acp import schema as s

from .backend import session_path
from .events import EventProjector


def invalid(message):
    return acp.RequestError(-32602, message)


def workspace(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.is_dir():
        raise invalid("cwd must be an existing absolute directory")
    return str(path.resolve())


@dataclass
class ActiveSession:
    cwd: str
    config: dict
    options: list
    task: asyncio.Task | None = None
    run_id: str = ""
    cancelled: bool = False
    closing: bool = False
    config_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    applied_config: dict = field(default_factory=dict)

    def __post_init__(self):
        self.applied_config = dict(self.config)


class SugarACPAgent(acp.Agent):
    def __init__(self, backend):
        self.backend = backend
        self.connection = None
        self.sessions = {}
        self.activating = set()
        self.disposed = False

    def on_connect(self, conn):
        self.connection = conn

    async def initialize(self, protocol_version, **kwargs):
        return s.InitializeResponse(protocol_version=acp.PROTOCOL_VERSION,
            agent_info=s.Implementation(name="sugaragent", version="1.0.0"),
            agent_capabilities=s.AgentCapabilities(
                prompt_capabilities=s.PromptCapabilities(image=False, audio=False, embedded_context=False),
                mcp_capabilities=s.McpCapabilities(http=True),
                session_capabilities=s.SessionCapabilities(list={}, resume={}, close={})), auth_methods=[])

    async def authenticate(self, method_id, **kwargs):
        return s.AuthenticateResponse()

    def _check_open(self):
        if self.disposed:
            raise invalid("ACP connection is closing")

    def _record(self, session_id):
        self._check_open()
        record = self.sessions.get(session_id)
        if record is None or record.closing:
            raise invalid("session is not active on this connection")
        return record

    @staticmethod
    def _validate_roots(additional_directories):
        if additional_directories:
            raise invalid("additionalDirectories is not supported")

    async def _configuration(self, session_id):
        catalog = await self.backend.request("GET", "/api/model_profiles")
        current = await self.backend.request("GET", session_path(session_id) + "/model_profile")
        choices = [{"value": str(p["id"]), "name": str(p.get("name") or p.get("model_name") or p["id"])}
                   for p in catalog.get("profiles", []) if p.get("id") and p.get("enabled", True)]
        config = {"model": str(current.get("profile_id") or ""),
                  "reasoning_effort": str(current.get("reasoning_effort") or "")}
        options = []
        if choices and config["model"] in {p["value"] for p in choices}:
            options.append({"id": "model", "name": "Model", "category": "model", "type": "select",
                            "currentValue": config["model"], "options": choices})
        options.append({"id": "reasoning_effort", "name": "Reasoning effort", "category": "thought_level",
                        "type": "select", "currentValue": config["reasoning_effort"],
                        "options": [{"value": v, "name": v or "Default"}
                                    for v in ("", "low", "medium", "high", "xhigh", "max")]})
        return config, options

    @staticmethod
    def _options(record):
        return [s.SessionConfigOptionSelect.model_validate(dict(option, currentValue=record.config[option["id"]]))
                for option in record.options]

    async def _activate(self, session_id, cwd, mcp_servers):
        self._check_open()
        if session_id in self.sessions or session_id in self.activating:
            raise invalid("session is already active on this connection")
        self.activating.add(session_id)
        try:
            servers = [v.model_dump(by_alias=True, exclude_none=True) if hasattr(v, "model_dump") else v
                       for v in (mcp_servers or [])]
            try:
                await self.backend.attach(session_id, servers)
                config, options = await self._configuration(session_id)
                record = ActiveSession(cwd, config, options)
                self._check_open()
                self.sessions[session_id] = record
                return record
            except BaseException:
                await self.backend.detach(session_id)
                raise
        finally:
            self.activating.discard(session_id)

    async def new_session(self, cwd, mcp_servers=None, additional_directories=None, **kwargs):
        self._check_open()
        self._validate_roots(additional_directories)
        cwd = workspace(cwd)
        created = await self.backend.request("POST", "/sessions", json={"work_dir": cwd})
        session_id = created["session_id"]
        try:
            record = await self._activate(session_id, cwd, mcp_servers)
        except BaseException:
            await self.backend.request("DELETE", session_path(session_id))
            raise
        return s.NewSessionResponse(session_id=session_id, config_options=self._options(record))

    async def resume_session(self, session_id, cwd, mcp_servers=None, additional_directories=None, **kwargs):
        self._validate_roots(additional_directories)
        cwd = workspace(cwd)
        existing = await self.backend.request("GET", session_path(session_id))
        existing = existing.get("session", existing)
        if os.path.normcase(workspace(existing["work_dir"])) != os.path.normcase(cwd):
            raise invalid("resume cwd must match the persisted workspace")
        if existing.get("run_active") or existing.get("stream_active"):
            raise invalid("session is already running")
        record = await self._activate(session_id, cwd, mcp_servers)
        return s.ResumeSessionResponse(config_options=self._options(record))

    async def list_sessions(self, cwd=None, cursor=None, **kwargs):
        self._check_open()
        expected = os.path.normcase(workspace(cwd)) if cwd else None
        rows = await self.backend.request("GET", "/sessions")
        rows = [row for row in rows if not row.get("is_subagent") and row.get("work_dir")
                and (expected is None or os.path.normcase(str(Path(row["work_dir"]).resolve())) == expected)]
        rows.sort(key=lambda row: (str(row.get("updated_at") or row.get("created_at") or ""), row["id"]), reverse=True)
        if cursor:
            ids = [row["id"] for row in rows]
            if cursor not in ids:
                raise invalid("unknown session list cursor")
            rows = rows[ids.index(cursor) + 1:]
        page = rows[:100]
        return s.ListSessionsResponse(sessions=[s.SessionInfo(session_id=row["id"], cwd=row["work_dir"],
                                      title=row.get("name")) for row in page],
                                      next_cursor=page[-1]["id"] if len(rows) > 100 else None)

    async def set_config_option(self, session_id, config_id, value, **kwargs):
        record = self._record(session_id)
        async with record.config_lock:
            option = next((option for option in record.options if option["id"] == config_id), None)
            if option is None or value not in {item["value"] for item in option["options"]}:
                raise invalid("unknown configuration option or value")
            previous = record.config[config_id]
            record.config[config_id] = value
            if record.task is None:
                try:
                    await self._apply_config(session_id, record)
                except BaseException:
                    record.config[config_id] = previous
                    raise
            options = self._options(record)
            if self.connection:
                await self.connection.session_update(session_id, s.ConfigOptionUpdate(
                    session_update="config_option_update", config_options=options))
            return s.SetSessionConfigOptionResponse(config_options=options)

    async def _apply_config(self, session_id, record):
        current = await self.backend.request("GET", session_path(session_id) + "/model_profile")
        record.applied_config = {"model": str(current.get("profile_id") or ""),
                                 "reasoning_effort": str(current.get("reasoning_effort") or "")}
        if record.config["model"] and record.config["model"] != record.applied_config.get("model"):
            await self.backend.request("POST", session_path(session_id) + "/model_profile",
                                       json={"profile_id": record.config["model"]})
            record.applied_config["model"] = record.config["model"]
        if record.config["reasoning_effort"] != record.applied_config.get("reasoning_effort"):
            await self.backend.request("POST", session_path(session_id) + "/reasoning_effort",
                                       json={"reasoning_effort": record.config["reasoning_effort"]})
            record.applied_config["reasoning_effort"] = record.config["reasoning_effort"]

    @staticmethod
    def _prompt_text(prompt):
        text = []
        for block in prompt:
            if block.type == "text":
                text.append(block.text)
            elif block.type == "resource_link":
                text.append(f"\n[resource_link name={block.name!r} uri={block.uri!r}]\n")
            else:
                raise invalid("this agent accepts text and resource_link content only")
        message = "".join(text)
        if not message.strip():
            raise invalid("prompt must not be empty")
        return message

    async def prompt(self, session_id, prompt, **kwargs):
        record = self._record(session_id)
        message = self._prompt_text(prompt)
        # Reserve before awaiting configuration or HTTP so reentrant calls cannot
        # race two native loops against the same durable conversation.
        if record.task is not None:
            raise invalid("a prompt is already in flight for this session")
        record.task = asyncio.current_task()
        record.cancelled = False
        record.cancel_event.clear()
        record.run_id = uuid.uuid4().hex
        projector = EventProjector()
        terminal = None
        error = False
        cancel_after_admission = False
        try:
            async with record.config_lock:
                await self._apply_config(session_id, record)
            if record.cancelled:
                return s.PromptResponse(stop_reason="cancelled")
            async for event in self.backend.events(session_id, record.run_id, message):
                if record.cancelled and not cancel_after_admission:
                    # A cancel may reach the backend before /chat is admitted.
                    # Fence the accepted run again once its stream is observable.
                    cancel_after_admission = True
                    await self.backend.interrupt(session_id, record.run_id)
                if event.get("type") == "approval_requested":
                    await self._permission(session_id, record, event)
                elif event.get("type") in {"error", "run_failed"} or event.get("result_status") == "failed":
                    error = True
                elif event.get("type") == "question_requested":
                    error = True
                    await self.backend.interrupt(session_id, record.run_id)
                elif event.get("type") in {"run_finished", "run_interrupted"}:
                    terminal = event["type"]
                if self.connection:
                    for update in projector.updates(event):
                        await self.connection.session_update(session_id, update)
            if record.cancelled:
                return s.PromptResponse(stop_reason="cancelled")
            if error:
                raise acp.RequestError(-32603, "native agent did not complete successfully")
            if terminal == "run_interrupted":
                return s.PromptResponse(stop_reason="cancelled")
            if terminal != "run_finished":
                raise acp.RequestError(-32603, "native agent did not complete successfully")
            return s.PromptResponse(stop_reason="end_turn")
        except asyncio.CancelledError:
            await asyncio.shield(self.backend.interrupt(session_id, record.run_id))
            raise
        except acp.RequestError:
            raise
        except Exception as exc:
            await self.backend.interrupt(session_id, record.run_id)
            raise acp.RequestError(-32603, "native runtime request failed", {"category": type(exc).__name__}) from exc
        finally:
            try:
                async with record.config_lock:
                    await self._apply_config(session_id, record)
            finally:
                record.task = None

    async def _permission(self, session_id, record, event):
        allow = False
        if not record.cancelled and self.connection:
            permission = asyncio.create_task(self.connection.request_permission(session_id=session_id,
                tool_call=s.ToolCallUpdate(tool_call_id=str(event.get("tool_call_id") or event["approval_id"]),
                                          title=str(event.get("title") or event.get("tool") or "Approval"),
                                          status="pending"),
                options=[s.PermissionOption(option_id="allow-once", name="Allow once", kind="allow_once"),
                         s.PermissionOption(option_id="reject-once", name="Reject", kind="reject_once")]))
            cancelled = asyncio.create_task(record.cancel_event.wait())
            try:
                completed, _ = await asyncio.wait({permission, cancelled}, return_when=asyncio.FIRST_COMPLETED)
                if permission in completed and not record.cancelled:
                    response = await permission
                    allow = isinstance(response.outcome, s.AllowedOutcome) and response.outcome.option_id == "allow-once"
            except Exception:
                allow = False
            finally:
                permission.cancel()
                cancelled.cancel()
                await asyncio.gather(permission, cancelled, return_exceptions=True)
        if not record.cancelled:
            await self.backend.resolve(session_id, event["approval_id"], allow)

    async def cancel(self, session_id, **kwargs):
        record = self.sessions.get(session_id)
        if record is not None and record.task is not None:
            record.cancelled = True
            record.cancel_event.set()
            await self.backend.interrupt(session_id, record.run_id)

    async def close_session(self, session_id, **kwargs):
        record = self.sessions.get(session_id)
        if record is None:
            raise invalid("unknown active session")
        record.closing = True
        await self.cancel(session_id)
        if record.task:
            try:
                await asyncio.wait_for(asyncio.shield(record.task), timeout=30)
            except acp.RequestError:
                pass  # The correlated prompt already reported its terminal failure.
        await self.backend.detach(session_id)
        self.sessions.pop(session_id, None)
        return s.CloseSessionResponse()

    async def shutdown(self):
        self.disposed = True
        results = await asyncio.gather(*(self.close_session(sid) for sid in list(self.sessions)), return_exceptions=True)
        if any(isinstance(result, BaseException) for result in results):
            raise RuntimeError("one or more ACP sessions failed to quiesce")

    async def load_session(self, **kwargs):
        raise acp.RequestError.method_not_found("session/load")

    async def fork_session(self, **kwargs):
        raise acp.RequestError.method_not_found("session/fork")

    async def set_session_mode(self, **kwargs):
        raise acp.RequestError.method_not_found("session/set_mode")

    async def ext_method(self, method, params):
        raise acp.RequestError.method_not_found(method)

    async def ext_notification(self, method, params):
        return None
