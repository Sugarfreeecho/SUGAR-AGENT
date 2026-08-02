import asyncio
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.hooks import (
    SUPPORTED_HOOK_EVENTS,
    CommandHookExecutor,
    CommandSpec,
    HookConfigurationError,
    HookDefinition,
    HookExecutionResult,
    HookManager,
    hook_matches,
    hooks_enabled,
    load_hook_definitions,
    load_hook_sources,
)


def _shell_command(*parts):
    values = [str(part) for part in parts]
    if os.name == "nt":
        return subprocess.list2cmdline(values)
    return " ".join(shlex.quote(value) for value in values)


def _definition(
    root,
    *,
    hook_id="hook",
    event="PreToolUse",
    matcher="",
    failure_policy="warn",
    timeout=10,
    priority=100,
    env_allowlist=(),
    command="unused",
):
    return HookDefinition(
        id=hook_id,
        event=event,
        matcher=matcher,
        failure_policy=failure_policy,
        priority=priority,
        source_root=Path(root),
        source_id="test",
        command=CommandSpec(
            command=command,
            timeout_seconds=timeout,
            env_allowlist=tuple(env_allowlist),
        ),
    )


class HookConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_switch_defaults_on_and_understands_false_values(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(hooks_enabled())
        for value in ("0", "false", "FALSE", "no", "off"):
            with self.subTest(value=value), patch.dict(os.environ, {"HOOKS_ENABLED": value}, clear=True):
                self.assertFalse(hooks_enabled())
        self.assertTrue(hooks_enabled("yes"))

    def test_public_event_set_contains_complete_mvp_lifecycle(self):
        self.assertEqual(
            set(SUPPORTED_HOOK_EVENTS),
            {
                "SessionStart",
                "SessionEnd",
                "UserPromptSubmit",
                "PreToolUse",
                "PostToolUse",
                "PostToolUseFailure",
                "Stop",
                "RunFailed",
                "SubagentStart",
                "SubagentStop",
                "PreCompact",
                "PostCompact",
                "GoalCreated",
                "GoalBeforeContinue",
                "GoalCompleted",
                "GoalBlocked",
            },
        )

    def test_loads_project_config_groups_priority_and_platform_overrides(self):
        config = {
            "version": 1,
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "^(run_shell|write_file)$",
                        "priority": 40,
                        "failure_policy": "block",
                        "hooks": [
                            {
                                "id": "guard",
                                "type": "command",
                                "command": {
                                    "default": "default-command",
                                    "windows": "windows-command",
                                    "unix": "unix-command",
                                },
                                "timeout_seconds": 3,
                                "env_allowlist": ["CI"],
                            }
                        ],
                    }
                ],
                "Stop": [{"id": "notify", "command": "notify-command", "priority": 90}],
            },
        }
        (self.root / "hooks.json").write_text(json.dumps(config), encoding="utf-8")

        definitions = load_hook_definitions(self.root)

        self.assertEqual([item.id for item in definitions], ["guard", "notify"])
        guard = definitions[0]
        self.assertEqual(guard.matcher, "^(run_shell|write_file)$")
        self.assertEqual(guard.failure_policy, "block")
        self.assertEqual(guard.command.platform_command(is_windows=True), "windows-command")
        self.assertEqual(guard.command.platform_command(is_windows=False), "unix-command")
        self.assertEqual(guard.command.env_allowlist, ("CI",))

    def test_plugin_sources_accept_inline_config_and_keep_plugin_identity(self):
        result = load_hook_sources(
            self.root,
            include_project=False,
            plugin_sources=[
                {
                    "plugin_id": "quality-gates",
                    "root": self.root,
                    "config": {
                        "version": 1,
                        "hooks": {"GoalCompleted": [{"id": "verify", "command": "verify"}]},
                    },
                }
            ],
        )

        self.assertFalse(result.errors)
        self.assertEqual(result.loaded_sources, ("plugin:quality-gates",))
        self.assertEqual(result.definitions[0].plugin_id, "quality-gates")
        self.assertEqual(result.definitions[0].source_root, self.root.resolve())

    def test_soft_load_collects_errors_and_strict_load_raises(self):
        path = self.root / "bad.json"
        path.write_text('{"version":1,"hooks":{"Unknown":[]}}', encoding="utf-8")

        soft = load_hook_sources(self.root, config_path=path)
        self.assertEqual(soft.definitions, ())
        self.assertIn("Unsupported hook event", soft.errors[0])
        with self.assertRaises(HookConfigurationError):
            load_hook_definitions(self.root, config_path=path)

    def test_empty_and_regex_matchers(self):
        self.assertTrue(hook_matches("", {"tool_name": "anything"}))
        self.assertTrue(hook_matches("*", {"tool_name": "anything"}))
        self.assertTrue(hook_matches(r"^mcp_.*", {"tool_name": "mcp_search"}))
        self.assertFalse(hook_matches(r"^mcp_.*", {"tool_name": "run_shell"}))


class HookCommandExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _script(self, name, source):
        path = self.root / name
        path.write_text(source, encoding="utf-8")
        return path

    def test_command_receives_json_and_returns_decision_input_and_context(self):
        script = self._script(
            "rewrite.py",
            """import json, sys
p = json.load(sys.stdin)
assert p['event'] == 'PreToolUse'
assert p['tool_name'] == 'run_shell'
print(json.dumps({
  'decision': 'ask',
  'updated_input': {'command': p['tool_input']['command'] + ' -q'},
  'additional_context': 'quality gate applied',
  'user_message': 'approval required',
  'reason': 'command changed'
}))
""",
        )
        definition = _definition(
            self.root,
            hook_id="rewrite",
            matcher="^run_shell$",
            command=_shell_command(sys.executable, script),
        )
        manager = HookManager(self.root, include_project=False, definitions=[definition])

        result = asyncio.run(
            manager.dispatch(
                "PreToolUse",
                {"session_id": "s1", "tool_name": "run_shell", "tool_input": {"command": "pytest"}},
            )
        )

        self.assertEqual(result.decision, "ask")
        self.assertTrue(result.requires_approval)
        self.assertEqual(result.updated_input, {"command": "pytest -q"})
        self.assertTrue(result.input_modified)
        self.assertEqual(result.additional_context, "quality gate applied")
        self.assertEqual(result.user_messages, ("approval required",))
        self.assertEqual(result.results[0].reason, "command changed")
        self.assertEqual(result.to_dict()["results"][0]["hook_id"], "rewrite")

    def test_command_environment_is_minimal_and_explicitly_allowlisted(self):
        script = self._script(
            "environment.py",
            """import json, os
print(json.dumps({'additional_context': '|'.join([
  os.getenv('ALLOWED_VALUE', 'missing'),
  os.getenv('SECRET_VALUE', 'missing'),
  os.getenv('MYAGENT_HOOK_EVENT', 'missing')
])}))
""",
        )
        definition = _definition(
            self.root,
            event="Stop",
            env_allowlist=("ALLOWED_VALUE",),
            command=_shell_command(sys.executable, script),
        )
        source_env = dict(os.environ)
        source_env.update({"ALLOWED_VALUE": "allowed", "SECRET_VALUE": "secret"})
        executor = CommandHookExecutor(self.root, source_environment=source_env)
        manager = HookManager(
            self.root,
            include_project=False,
            definitions=[definition],
            executor=executor,
        )

        result = asyncio.run(manager.dispatch("Stop", {"session_id": "s1"}))

        self.assertEqual(result.additional_context, "allowed|missing|Stop")

    def test_timeout_is_structured_and_failure_policy_blocks(self):
        script = self._script("slow.py", "import time; time.sleep(0.2); print('{}')\n")
        definition = _definition(
            self.root,
            hook_id="slow",
            failure_policy="block",
            timeout=0.03,
            command=_shell_command(sys.executable, script),
        )
        manager = HookManager(self.root, include_project=False, definitions=[definition])

        result = asyncio.run(manager.dispatch("PreToolUse", {"tool_name": "run_shell"}))

        self.assertTrue(result.blocked)
        self.assertEqual(result.results[0].outcome, "blocked")
        self.assertIn("timed out", result.results[0].error)

    def test_invalid_stdout_is_a_warning_by_default(self):
        script = self._script("invalid.py", "print('not-json')\n")
        definition = _definition(self.root, command=_shell_command(sys.executable, script))
        manager = HookManager(self.root, include_project=False, definitions=[definition])

        result = asyncio.run(manager.dispatch("PreToolUse", {"tool_name": "run_shell"}))

        self.assertEqual(result.decision, "allow")
        self.assertEqual(result.results[0].outcome, "warning")
        self.assertIn("not valid JSON", result.warnings[0])


class _FakeExecutor:
    def __init__(self, outcomes=None, delay=0):
        self.outcomes = outcomes or {}
        self.delay = delay
        self.calls = []
        self.active = 0
        self.max_active = 0

    async def execute(self, definition, payload):
        self.calls.append((definition.id, dict(payload)))
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            values = self.outcomes.get(definition.id, {})
            return HookExecutionResult(
                hook_id=definition.id,
                event=definition.event,
                source_id=definition.source_id,
                plugin_id=definition.plugin_id,
                failure_policy=definition.failure_policy,
                **values,
            )
        finally:
            self.active -= 1


class HookManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_disabled_switch_skips_without_calling_executor(self):
        executor = _FakeExecutor()
        manager = HookManager(
            self.root,
            include_project=False,
            executor=executor,
            definitions=[_definition(self.root)],
        )
        with patch.dict(os.environ, {"HOOKS_ENABLED": "off"}):
            result = asyncio.run(manager.dispatch("PreToolUse", {"tool_name": "run_shell"}))
        self.assertFalse(result.enabled)
        self.assertEqual(result.skip_reason, "disabled")
        self.assertFalse(executor.calls)

    def test_authorization_denial_happens_before_executor_starts(self):
        executor = _FakeExecutor()
        manager = HookManager(
            self.root,
            include_project=False,
            executor=executor,
            definitions=[_definition(self.root, command="write outside.txt")],
        )

        async def deny(_definition, _payload):
            return False, "approval channel unavailable"

        result = asyncio.run(
            manager.dispatch(
                "PreToolUse",
                {
                    "tool_name": "run_shell",
                    "_hook_authorizer": deny,
                },
            )
        )

        self.assertTrue(result.blocked)
        self.assertEqual(result.matched_hooks, 1)
        self.assertFalse(executor.calls)
        self.assertIn("approval channel unavailable", result.results[0].reason)

    def test_failed_hook_supports_all_failure_policies(self):
        for policy, expected_decision, expected_outcome, warning_count in (
            ("ignore", "allow", "ignored", 0),
            ("warn", "allow", "warning", 1),
            ("block", "deny", "blocked", 1),
            ("pause", "pause", "paused", 1),
        ):
            with self.subTest(policy=policy):
                executor = _FakeExecutor(
                    {"broken": {"success": False, "outcome": "failed", "error": "boom"}}
                )
                manager = HookManager(
                    self.root,
                    include_project=False,
                    executor=executor,
                    definitions=[
                        _definition(self.root, hook_id="broken", failure_policy=policy)
                    ],
                )
                result = asyncio.run(manager.dispatch("PreToolUse", {"tool_name": "run_shell"}))
                self.assertEqual(result.decision, expected_decision)
                self.assertEqual(result.results[0].outcome, expected_outcome)
                self.assertEqual(len(result.warnings), warning_count)

    def test_hooks_are_ordered_and_updated_input_flows_to_next_hook(self):
        executor = _FakeExecutor(
            {
                "first": {"updated_input": {"command": "safe"}, "additional_context": "first"},
                "second": {"decision": "ask", "additional_context": "second"},
            }
        )
        manager = HookManager(
            self.root,
            include_project=False,
            executor=executor,
            definitions=[
                _definition(self.root, hook_id="second", priority=20),
                _definition(self.root, hook_id="first", priority=10),
            ],
        )

        result = asyncio.run(
            manager.dispatch("PreToolUse", {"tool_name": "run_shell", "tool_input": {"command": "unsafe"}})
        )

        self.assertEqual([item[0] for item in executor.calls], ["first", "second"])
        self.assertEqual(executor.calls[1][1]["tool_input"], {"command": "safe"})
        self.assertEqual(result.additional_context, "first\nsecond")
        self.assertEqual(result.decision, "ask")

    def test_same_event_dispatches_are_serialized(self):
        executor = _FakeExecutor(delay=0.03)
        manager = HookManager(
            self.root,
            include_project=False,
            executor=executor,
            definitions=[_definition(self.root, event="Stop")],
        )

        async def run_both():
            return await asyncio.gather(
                manager.dispatch("Stop", {"session_id": "one"}),
                manager.dispatch("Stop", {"session_id": "two"}),
            )

        results = asyncio.run(run_both())
        self.assertEqual(executor.max_active, 1)
        self.assertEqual([item.executed_hooks for item in results], [1, 1])

    def test_same_event_reentry_is_skipped_instead_of_deadlocking(self):
        class ReentrantExecutor:
            manager = None
            nested = None

            async def execute(self, definition, payload):
                self.nested = await self.manager.dispatch(definition.event, payload)
                return HookExecutionResult(
                    hook_id=definition.id,
                    event=definition.event,
                    source_id=definition.source_id,
                    failure_policy=definition.failure_policy,
                )

        executor = ReentrantExecutor()
        manager = HookManager(
            self.root,
            include_project=False,
            executor=executor,
            definitions=[_definition(self.root, event="Stop")],
        )
        executor.manager = manager

        outer = asyncio.run(manager.dispatch("Stop", {"session_id": "s1"}))

        self.assertEqual(outer.executed_hooks, 1)
        self.assertTrue(executor.nested.skipped)
        self.assertEqual(executor.nested.skip_reason, "reentrant")

    def test_deny_short_circuits_later_hooks_and_sync_wrapper_works(self):
        executor = _FakeExecutor({"deny": {"decision": "deny", "reason": "policy"}})
        manager = HookManager(
            self.root,
            include_project=False,
            executor=executor,
            definitions=[
                _definition(self.root, hook_id="deny", priority=1),
                _definition(self.root, hook_id="later", priority=2),
            ],
        )

        result = manager.dispatch_sync("PreToolUse", {"tool_name": "run_shell"})

        self.assertTrue(result.blocked)
        self.assertEqual([call[0] for call in executor.calls], ["deny"])

    def test_unknown_event_is_rejected(self):
        manager = HookManager(self.root, include_project=False, definitions=[])
        with self.assertRaisesRegex(ValueError, "Unsupported hook event"):
            asyncio.run(manager.dispatch("MadeUpEvent", {}))


if __name__ == "__main__":
    unittest.main()
