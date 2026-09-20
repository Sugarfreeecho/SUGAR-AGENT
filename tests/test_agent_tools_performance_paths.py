import os
import io
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import agent_tools  # noqa: E402


def test_read_file_streams_requested_range_and_caches_count(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")

    first = agent_tools.read_file(str(path), start_line=2, end_line=3)
    second = agent_tools.read_file(str(path), start_line=4, end_line=4)

    assert "[lines 2-3 of 4]" in first
    assert "two\nthree\n" in first
    assert "[lines 4-4 of 4]" in second
    assert second.endswith("four\n")


def test_ls_can_skip_expensive_line_counts_when_disabled(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("a\nb\n", encoding="utf-8")
    monkeypatch.setenv("LS_INCLUDE_LINE_COUNTS", "0")
    monkeypatch.setattr(
        agent_tools,
        "_line_count_file",
        lambda _path: (_ for _ in ()).throw(AssertionError("line count should be skipped")),
    )

    result = agent_tools.ls(str(tmp_path))

    assert "a.txt" in result


def test_ls_skips_line_counts_by_default(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("a\nb\n", encoding="utf-8")
    monkeypatch.delenv("LS_INCLUDE_LINE_COUNTS", raising=False)
    monkeypatch.setattr(
        agent_tools,
        "_line_count_file",
        lambda _path: (_ for _ in ()).throw(AssertionError("default listing must stay lightweight")),
    )

    result = agent_tools.ls(str(tmp_path))

    assert "lines:" in result
    assert result.rstrip().endswith("—")


def test_ls_counts_only_recognized_text_files(tmp_path, monkeypatch):
    (tmp_path / "notes.txt").write_text("one\ntwo\n", encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"binary\nwith\nnewlines\n")
    counted = []

    def count_lines(path):
        counted.append(path.name)
        return "2"

    monkeypatch.setattr(agent_tools, "_line_count_file", count_lines)

    result = agent_tools.ls(str(tmp_path), include_line_counts=True)

    assert counted == ["notes.txt"]
    image_row = next(line for line in result.splitlines() if "image.png" in line)
    assert image_row.endswith("lines:        —")


def test_ls_recognizes_text_extensions_and_special_filenames():
    text_names = ("app.py", "config.yaml", "data.csv", "Dockerfile", ".env", ".env.local", ".gitignore")

    assert all(agent_tools._ls_is_text_file(Path(name)) for name in text_names)
    assert not agent_tools._ls_is_text_file(Path("photo.jpg"))
    assert not agent_tools._ls_is_text_file(Path("program.exe"))


def test_ls_skips_line_scan_for_large_text_file(tmp_path, monkeypatch):
    (tmp_path / "large.txt").write_text("123456789", encoding="utf-8")
    monkeypatch.setenv("LS_LINE_COUNT_MAX_BYTES", "8")

    result = agent_tools.ls(str(tmp_path), include_line_counts=True)

    large_row = next(line for line in result.splitlines() if "large.txt" in line)
    assert "lines:" in large_row
    assert "— (>8 B)" in large_row


def test_ls_does_not_calculate_archive_size_or_line_count(tmp_path, monkeypatch):
    (tmp_path / "bundle.ZIP").write_bytes(b"not-a-text-file")
    monkeypatch.setattr(
        agent_tools,
        "_human_file_size",
        lambda _size: (_ for _ in ()).throw(AssertionError("archive size should be skipped")),
    )
    monkeypatch.setattr(
        agent_tools,
        "_line_count_file",
        lambda _path: (_ for _ in ()).throw(AssertionError("archive line count should be skipped")),
    )

    result = agent_tools.ls(str(tmp_path))

    assert "bundle.ZIP" in result
    assert "lines:        —" in result


def test_ls_recognizes_common_archive_suffixes():
    archive_names = ("backup.tar.gz", "source.tgz", "data.7z", "package.rar", "logs.zst")

    assert all(agent_tools._ls_is_archive(Path(name)) for name in archive_names)
    assert not agent_tools._ls_is_archive(Path("archive-notes.txt"))


def test_only_ls_is_exposed_to_model_while_list_dir_remains_compatible():
    exposed_names = [
        row["function"]["name"] for row in agent_tools.OPENAI_TOOL_DEFINITIONS
    ]

    assert exposed_names.count("ls") == 1
    assert "list_dir" not in exposed_names
    assert agent_tools.tools["ls"] is agent_tools.ls
    assert agent_tools.tools["list_dir"] is agent_tools.tools["ls"]


def test_ripgrep_fast_path_caps_results(monkeypatch, tmp_path):
    processes = []

    class FakeProcess:
        def __init__(self, args):
            self.args = args
            self.stdout = io.StringIO("a.py:1:first\na.py:2:second\n")
            self.stderr = io.StringIO("")
            self.returncode = 0
            self.terminated = False

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.returncode = -9

        def wait(self, timeout=None):
            return self.returncode

    monkeypatch.setattr(agent_tools, "_resolve_ripgrep_path", lambda: "rg")
    def fake_popen(args, **_kwargs):
        process = FakeProcess(args)
        processes.append(process)
        return process

    monkeypatch.setattr(agent_tools.subprocess, "Popen", fake_popen)

    result = agent_tools._grep_with_ripgrep(
        regex=re.compile("first|second"),
        target=tmp_path,
        recursive=True,
        max_results=1,
        line_cap=200,
        output_cap=10_000,
        file_cap=1024,
    )

    assert "a.py:1:first" in result
    assert "output truncated" in result
    assert processes[0].terminated
    assert "--hidden" not in processes[0].args
    assert "--no-ignore" not in processes[0].args


def test_ripgrep_path_prefers_explicit_config(monkeypatch, tmp_path):
    rg = tmp_path / ("rg.exe" if os.name == "nt" else "rg")
    rg.write_bytes(b"")
    monkeypatch.setenv("GREP_RIPGREP_PATH", str(rg))
    monkeypatch.setattr(agent_tools.shutil, "which", lambda _name: None)

    assert agent_tools._resolve_ripgrep_path() == str(rg.resolve())


def test_ripgrep_timeout_does_not_fall_back_to_python(monkeypatch, tmp_path):
    class HangingProcess:
        def __init__(self):
            self.stdout = io.StringIO("")
            self.stderr = io.StringIO("")
            self.returncode = None

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def terminate(self):
            self.returncode = -15

        def wait(self, timeout=None):
            return self.returncode

    class ImmediateTimer:
        def __init__(self, _timeout, callback):
            self.callback = callback
            self.daemon = False

        def start(self):
            self.callback()

        def cancel(self):
            pass

    (tmp_path / "sample.txt").write_text("needle\n", encoding="utf-8")
    monkeypatch.setattr(agent_tools, "_resolve_ripgrep_path", lambda: "rg")
    monkeypatch.setattr(agent_tools.subprocess, "Popen", lambda *_args, **_kwargs: HangingProcess())
    monkeypatch.setattr(agent_tools.threading, "Timer", ImmediateTimer)
    monkeypatch.setattr(
        agent_tools.os,
        "walk",
        lambda _path: (_ for _ in ()).throw(AssertionError("Python fallback must not run after rg timeout")),
    )

    result = agent_tools.grep("needle", path=str(tmp_path))

    assert "ripgrep timed out" in result


def test_ripgrep_can_explicitly_include_hidden_and_ignored(monkeypatch, tmp_path):
    seen = {}

    class EmptyProcess:
        def __init__(self, args):
            seen["args"] = args
            self.stdout = io.StringIO("")
            self.stderr = io.StringIO("")

        def poll(self):
            return 1

        def wait(self, timeout=None):
            return 1

        def terminate(self):
            pass

        def kill(self):
            pass

    monkeypatch.setattr(agent_tools, "_resolve_ripgrep_path", lambda: "rg")
    monkeypatch.setattr(agent_tools.subprocess, "Popen", lambda args, **_kwargs: EmptyProcess(args))

    result = agent_tools._grep_with_ripgrep(
        regex=re.compile("needle"),
        target=tmp_path,
        recursive=True,
        max_results=10,
        line_cap=200,
        output_cap=10_000,
        file_cap=1024,
        include_hidden=True,
        include_ignored=True,
    )

    assert result == "No matches found"
    assert "--hidden" in seen["args"]
    assert "--no-ignore" in seen["args"]


def test_ripgrep_unavailable_still_falls_back_to_python(monkeypatch, tmp_path):
    (tmp_path / "sample.txt").write_text("needle\n", encoding="utf-8")
    monkeypatch.setattr(agent_tools, "_resolve_ripgrep_path", lambda: None)

    result = agent_tools.grep("needle", path=str(tmp_path))

    assert "sample.txt:1" in result


def test_windows_index_glob_defaults_on_and_falls_back_on_empty_index(monkeypatch, tmp_path):
    expected = tmp_path / "module.py"
    expected.write_text("", encoding="utf-8")
    monkeypatch.delenv("GLOB_USE_WINDOWS_INDEX", raising=False)
    monkeypatch.setattr(agent_tools.platform, "system", lambda: "Windows")
    monkeypatch.setattr(agent_tools, "_query_windows_search_index", lambda **_kwargs: [])

    result = agent_tools.glob("**/*.py", path=str(tmp_path))

    assert "module.py" in result


def test_windows_index_glob_can_be_disabled(monkeypatch, tmp_path):
    expected = tmp_path / "module.py"
    expected.write_text("", encoding="utf-8")
    monkeypatch.setenv("GLOB_USE_WINDOWS_INDEX", "0")
    monkeypatch.setattr(agent_tools.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        agent_tools,
        "_query_windows_search_index",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("Windows index must stay disabled")),
    )

    result = agent_tools.glob("**/*.py", path=str(tmp_path))

    assert "module.py" in result


def test_windows_index_glob_uses_indexed_filename_results(monkeypatch, tmp_path):
    indexed = tmp_path / "indexed.py"
    indexed.write_text("", encoding="utf-8")
    monkeypatch.setenv("GLOB_USE_WINDOWS_INDEX", "1")
    monkeypatch.setattr(agent_tools.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        agent_tools,
        "_query_windows_search_index",
        lambda **_kwargs: [indexed],
    )
    monkeypatch.setattr(
        agent_tools.Path,
        "glob",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("filesystem glob should not run")),
    )

    result = agent_tools.glob("**/*.py", path=str(tmp_path))

    assert "indexed.py" in result


def test_regex_edit_uses_subn_result(tmp_path, monkeypatch):
    path = tmp_path / "edit.txt"
    path.write_text("x1 x2 x3", encoding="utf-8")
    monkeypatch.setattr(agent_tools, "safe_work_path", lambda raw: Path(raw))
    result = agent_tools.edit_file(
        str(path), search=r"x\d", replace="y", use_regex=True, replace_all=True
    )

    assert "replaced 3 occurrence(s)" in result
    assert path.read_text(encoding="utf-8") == "y y y"


def test_ls_per_call_line_count_and_limit_override(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("a\nb\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    monkeypatch.setenv("LS_INCLUDE_LINE_COUNTS", "0")

    result = agent_tools.ls(str(tmp_path), include_line_counts=True, max_entries=1)

    assert "a.txt" in result
    assert "lines:        2" in result
    assert "1 more entries omitted" in result


def test_ls_line_count_reuses_stat_cache(tmp_path, monkeypatch):
    path = tmp_path / "cached.txt"
    path.write_text("one\ntwo\n", encoding="utf-8")
    agent_tools._read_file_line_count_cache.clear()

    assert agent_tools._line_count_file(path) == "2"
    monkeypatch.setattr(
        agent_tools,
        "open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("cached count must not reopen file")),
        raising=False,
    )
    assert agent_tools._line_count_file(path) == "2"


def test_missing_path_error_suggests_close_existing_component(tmp_path):
    existing = tmp_path / "AI Agent" / "project"
    existing.mkdir(parents=True)

    result = agent_tools.grep("needle", path=str(tmp_path / "AAI Agent" / "project"))

    assert "does not exist" in result
    assert "Did you mean:" in result
    assert "AI Agent" in result


def test_read_file_accepts_start_plus_line_count(tmp_path):
    path = tmp_path / "range.txt"
    path.write_text("1\n2\n3\n4\n", encoding="utf-8")

    result = agent_tools.read_file(str(path), start_line=2, line_count=2)

    assert "[lines 2-3 of 4]" in result
    assert result.endswith("2\n3\n")


def test_edit_file_defaults_to_first_match_and_checks_expected_count(tmp_path, monkeypatch):
    path = tmp_path / "safe-edit.txt"
    path.write_text("old old", encoding="utf-8")
    monkeypatch.setattr(agent_tools, "safe_work_path", lambda raw: Path(raw))

    result = agent_tools.edit_file(
        str(path), search="old", replace="new", expected_replacements=1
    )

    assert "replaced 1 occurrence(s)" in result
    assert path.read_text(encoding="utf-8") == "new old"


def test_task_schema_uses_action_discriminator():
    schema = next(
        row["function"] for row in agent_tools.OPENAI_TOOL_DEFINITIONS
        if row["function"]["name"] == "task"
    )

    props = schema["parameters"]["properties"]
    assert props["action"]["enum"] == [
        "start",
        "resume",
        "status",
        "collect",
        "interrupt",
        "steer",
        "switch_model",
        "worktree",
    ]
    assert "Never use resume to poll" in schema["description"]
    assert "ask that same existing subagent directly" in schema["description"]
    assert "do not treat status or collect as a complete execution record" in schema["description"]
    assert "Reuse existing subagents before creating new ones" in schema["description"]
    assert "Do not create a duplicate" in schema["description"]
    assert "independent, non-overlapping scopes" in schema["description"]
    assert "verifying results, deduplicating findings, resolving conflicts" in schema["description"]
    assert "foreground explore for one read-only investigation" in schema["description"]
    assert "several background explore runs followed by status/collect" in schema["description"]
    assert "best-of-n-runner for genuinely different candidate solutions" in schema["description"]
    assert "requires resume ID and non-empty prompt" in props["action"]["description"]
    assert "complete first-hand account" in props["action"]["description"]
    assert "status: non-blocking state only, not execution details" in props["action"]["description"]
    assert "collect: wait for/read existing final output, not a complete process record" in props["action"]["description"]
    assert "prefer interacting with an existing suitable subagent" in props["action"]["description"]
    assert "use it before start" in props["action"]["description"]
    assert "continues, clarifies, corrects, or extends" in props["resume"]["description"]
    assert "list all actual subagents recursively" in props["action"]["description"]
    assert "There is no multi-ID subset form" in props["action"]["description"]
    assert "objective; scope and exact paths" in props["prompt"]["description"]
    assert "files, commands/tools, observations" in props["prompt"]["description"]
    assert "subagent's own history" in props["prompt"]["description"]
    assert "false: wait and return" in props["run_in_background"]["description"]
    assert "model_profile_id" in props
    assert "omit by default" in props["model_profile_id"]["description"]
    assert "low-cost/high-concurrency batch work" in props["model_profile_id"]["description"]
    assert "do not send legacy args, working_dir, or timeout" in next(
        row["function"]["description"] for row in agent_tools.OPENAI_TOOL_DEFINITIONS
        if row["function"]["name"] == "run_shell"
    )
    assert "Preferred tool for ordinary text-file modifications" in next(
        row["function"]["description"] for row in agent_tools.OPENAI_TOOL_DEFINITIONS
        if row["function"]["name"] == "apply_patch"
    )
    assert "Never guess, abbreviate" in props["model_profile_id"]["description"]
    assert "current message/attachment chain actually accept image input" in props["model_profile_id"]["description"]
    assert "use action=switch_model to change it" in props["model_profile_id"]["description"]
    assert "switch_model" in props["action"]["enum"]
    assert "model" not in props
    assert props["subagent_type"]["default"] == "generalPurpose"
    assert "arrays and multiple IDs are unsupported" in props["resume"]["description"]
    assert "all-subagents view includes nested descendants" in props["resume"]["description"]
    assert "virtual best-of-n runner ID is not a resumable child" in props["resume"]["description"]
    assert "check_status" not in props
    assert "collect_result" not in props


def test_system_prompt_keeps_cross_tool_rules_without_repeating_tool_schemas():
    prompt = (APP / "prompt.md").read_text(encoding="utf-8")

    assert "先读后写" in prompt
    assert "写入或编辑后要做必要验证" in prompt
    assert "未征得用户同意不要擅自 `pip install`" in prompt
    assert "无依赖的只读工具按并发上限并行" in prompt
    assert "优先复用 `ls`、`glob`、`grep`、`read_file` 已返回的完整路径" in prompt
    assert "最小源码目录" in prompt
    assert "不得猜测未知参数" in prompt
    assert "创建以任务名命名的子目录" in prompt
    assert "grep` 默认 `mode=regex" not in prompt
    assert "*** Begin Patch" not in prompt
    assert "不要生成旧参数" not in prompt
    assert "task / subagent 常用模式" not in prompt
    assert 'task(action="status")' not in prompt
    assert "model_profile_id" not in prompt


def test_search_and_listing_schemas_expose_fast_defaults():
    functions = {
        row["function"]["name"]: row["function"]
        for row in agent_tools.OPENAI_TOOL_DEFINITIONS
    }

    grep_schema = functions["grep"]
    grep_props = grep_schema["parameters"]["properties"]
    assert grep_props["include_hidden"]["default"] is False
    assert grep_props["include_ignored"]["default"] is False
    assert "narrowest known source directory" in grep_schema["description"]
    assert "exact tool-returned path" in grep_props["path"]["description"]
    assert "opt-in" in functions["ls"]["description"]
    assert "defaults false" in functions["ls"]["parameters"]["properties"]["include_line_counts"]["description"]


def test_tool_schemas_require_canonical_write_fields_without_forcing_strict_provider_mode():
    schemas = {
        row["function"]["name"]: row["function"]["parameters"]
        for row in agent_tools.OPENAI_TOOL_DEFINITIONS
    }

    assert all("additionalProperties" not in schema for schema in schemas.values())
    assert schemas["write_file"]["required"] == ["contents"]
    assert "edit_file" not in schemas
    assert schemas["apply_patch"]["required"] == ["patch"]
    assert schemas["delete_file"]["required"] == ["path"]


def test_apply_patch_schema_explains_update_context_without_fake_before_parameter():
    function = next(
        row["function"] for row in agent_tools.OPENAI_TOOL_DEFINITIONS
        if row["function"]["name"] == "apply_patch"
    )
    properties = function["parameters"]["properties"]
    description = function["description"]
    patch_description = properties["patch"]["description"]

    assert set(properties) == {"patch"}
    assert "there are no `before`, `after`" in description
    assert "Read the target immediately before editing" in description
    assert "re-read the reported file and rebuild the hunk" in description
    assert "plain `@@` hunk header (never `*** @@`)" in patch_description
    assert "space for an unchanged existing line" in patch_description
    assert "at least one space- or minus-prefixed existing line" in patch_description
    assert "required old, before, or context content" in patch_description
    assert "Paths are resolved from the runtime WORK_DIR" in patch_description
    # 13e91d4 起工作区外路径改为“允许 + 目录审批”，不再禁止 patch。
    assert "native absolute paths, which are allowed" in patch_description
    assert "restricted modes ask for directory approval first" in patch_description
    assert "Files outside WORK_DIR cannot be patched" not in patch_description
    assert "new Add/Update/Delete File section for every file" in patch_description
    assert "*** Update File: relative/path.txt" in patch_description
    assert "-exact old line" in patch_description
    assert "+replacement line" in patch_description


def test_apply_patch_handles_multiple_file_operations(tmp_path, monkeypatch):
    update_path = tmp_path / "update.txt"
    delete_path = tmp_path / "delete.txt"
    add_path = tmp_path / "nested" / "add.txt"
    update_path.write_text("alpha\nbeta\n", encoding="utf-8")
    delete_path.write_text("remove me", encoding="utf-8")
    monkeypatch.setattr(agent_tools, "safe_work_path", lambda raw: Path(raw))
    monkeypatch.setattr(agent_tools, "_path_is_sensitive_tool_resource", lambda _path: False)
    monkeypatch.setattr(agent_tools, "_delete_path_prohibited_reason", lambda _path: None)

    patch = "\n".join([
        "*** Begin Patch",
        f"*** Update File: {update_path}",
        "@@",
        " alpha",
        "-beta",
        "+gamma",
        f"*** Add File: {add_path}",
        "+one",
        "+two",
        f"*** Delete File: {delete_path}",
        "*** End Patch",
    ])
    result = agent_tools.apply_patch(patch)

    assert result.startswith("Done!")
    assert "(+3 -2)" in result
    assert f"- update {update_path} (+1 -1)" in result
    assert f"- add {add_path} (+2 -0)" in result
    assert f"- delete {delete_path} (+0 -1)" in result
    assert update_path.read_text(encoding="utf-8") == "alpha\ngamma\n"
    assert add_path.read_text(encoding="utf-8") == "one\ntwo\n"
    assert not delete_path.exists()


def test_apply_patch_rejects_stale_context_before_any_write(tmp_path, monkeypatch):
    existing = tmp_path / "existing.txt"
    new_file = tmp_path / "new.txt"
    existing.write_text("current\n", encoding="utf-8")
    monkeypatch.setattr(agent_tools, "safe_work_path", lambda raw: Path(raw))
    monkeypatch.setattr(agent_tools, "_path_is_sensitive_tool_resource", lambda _path: False)

    patch = "\n".join([
        "*** Begin Patch",
        f"*** Add File: {new_file}",
        "+new",
        f"*** Update File: {existing}",
        "@@",
        "-stale",
        "+changed",
        "*** End Patch",
    ])
    result = agent_tools.apply_patch(patch)

    assert result.startswith("Error:")
    assert existing.read_text(encoding="utf-8") == "current\n"
    assert not new_file.exists()


def test_apply_patch_accepts_saved_session_formatting_variants(tmp_path, monkeypatch):
    target = tmp_path / "formatted.txt"
    target.write_text("alpha\n  beta\n\ngamma\n", encoding="utf-8")
    monkeypatch.setattr(agent_tools, "safe_work_path", lambda raw: Path(raw))
    monkeypatch.setattr(agent_tools, "_path_is_sensitive_tool_resource", lambda _path: False)

    # Saved sessions contained all three variants: a Markdown fence, omitted
    # wrapper markers, and an unprefixed blank context line inside a hunk.
    patch = "\n".join([
        "```diff",
        f"*** Update File: {target}",
        "@@",
        " alpha",
        "- beta",
        "+    BETA",
        "",
        " gamma",
        "```",
    ])
    result = agent_tools.apply_patch(patch)

    assert result.startswith("Done!")
    assert "(+1 -1)" in result
    assert target.read_text(encoding="utf-8") == "alpha\n    BETA\n\ngamma\n"


def test_apply_patch_uses_unique_whitespace_insensitive_context(tmp_path, monkeypatch):
    target = tmp_path / "indented.py"
    target.write_text("def sample():\n    value = 1\n    return value\n", encoding="utf-8")
    monkeypatch.setattr(agent_tools, "safe_work_path", lambda raw: Path(raw))
    monkeypatch.setattr(agent_tools, "_path_is_sensitive_tool_resource", lambda _path: False)

    patch = "\n".join([
        "*** Begin Patch",
        f"*** Update File: {target}",
        "@@",
        " def sample():",
        "-  value = 1",
        "+    value = 2",
        "   return value",
        "*** End Patch",
        "",  # Historical parser rejected this harmless trailing newline.
    ])
    result = agent_tools.apply_patch(patch)

    assert result.startswith("Done!")
    assert target.read_text(encoding="utf-8") == "def sample():\n    value = 2\n    return value\n"


def test_apply_patch_rejects_ambiguous_whitespace_fallback(tmp_path, monkeypatch):
    target = tmp_path / "ambiguous.txt"
    original = "  same\t\nfirst\n\n    same\t\t\nsecond\n"
    target.write_text(original, encoding="utf-8")
    monkeypatch.setattr(agent_tools, "safe_work_path", lambda raw: Path(raw))
    monkeypatch.setattr(agent_tools, "_path_is_sensitive_tool_resource", lambda _path: False)

    patch = "\n".join([
        "*** Begin Patch",
        f"*** Update File: {target}",
        "@@",
        "-same ",
        "+changed",
        "*** End Patch",
    ])
    result = agent_tools.apply_patch(patch)

    assert "ambiguous (2 whitespace-insensitive matches)" in result
    assert target.read_text(encoding="utf-8") == original


def test_run_shell_schema_uses_codex_style_parameters_and_hides_legacy_aliases():
    schema = next(
        row["function"] for row in agent_tools.OPENAI_TOOL_DEFINITIONS
        if row["function"]["name"] == "run_shell"
    )["parameters"]
    props = schema["properties"]

    assert {"command", "workdir", "timeout_ms", "login"} <= set(props)
    assert "restrict_to_workspace" not in props
    assert {"args", "working_dir", "timeout"}.isdisjoint(props)
    assert props["login"]["default"] is True
