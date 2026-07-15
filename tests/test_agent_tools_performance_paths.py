import os
import re
import subprocess
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


def test_ls_includes_line_counts_by_default(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("a\nb\n", encoding="utf-8")
    monkeypatch.delenv("LS_INCLUDE_LINE_COUNTS", raising=False)

    result = agent_tools.ls(str(tmp_path))

    assert "lines:" in result
    assert "2" in result


def test_ripgrep_fast_path_caps_results(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_tools, "_resolve_ripgrep_path", lambda: "rg")
    monkeypatch.setattr(
        agent_tools.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="a.py:1:first\na.py:2:second\n", stderr=""
        ),
    )

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


def test_ripgrep_path_prefers_explicit_config(monkeypatch, tmp_path):
    rg = tmp_path / ("rg.exe" if os.name == "nt" else "rg")
    rg.write_bytes(b"")
    monkeypatch.setenv("GREP_RIPGREP_PATH", str(rg))
    monkeypatch.setattr(agent_tools.shutil, "which", lambda _name: None)

    assert agent_tools._resolve_ripgrep_path() == str(rg.resolve())


def test_ripgrep_timeout_does_not_fall_back_to_python(monkeypatch, tmp_path):
    (tmp_path / "sample.txt").write_text("needle\n", encoding="utf-8")
    monkeypatch.setattr(agent_tools, "_resolve_ripgrep_path", lambda: "rg")
    monkeypatch.setattr(
        agent_tools.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])
        ),
    )
    monkeypatch.setattr(
        agent_tools.os,
        "walk",
        lambda _path: (_ for _ in ()).throw(AssertionError("Python fallback must not run after rg timeout")),
    )

    result = agent_tools.grep("needle", path=str(tmp_path))

    assert "ripgrep timed out" in result


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
    assert props["action"]["enum"] == ["start", "resume", "status", "collect", "interrupt"]
    assert "Never use resume to poll" in schema["description"]
    assert "foreground explore for one read-only investigation" in schema["description"]
    assert "several background explore runs followed by status/collect" in schema["description"]
    assert "best-of-n-runner for genuinely different candidate solutions" in schema["description"]
    assert "requires resume ID and non-empty prompt" in props["action"]["description"]
    assert "list all actual subagents recursively" in props["action"]["description"]
    assert "There is no multi-ID subset form" in props["action"]["description"]
    assert "objective; scope and exact paths" in props["prompt"]["description"]
    assert "false: wait and return" in props["run_in_background"]["description"]
    assert props["subagent_type"]["default"] == "generalPurpose"
    assert "arrays and multiple IDs are unsupported" in props["resume"]["description"]
    assert "all-subagents view includes nested descendants" in props["resume"]["description"]
    assert "virtual best-of-n runner ID is not a resumable child" in props["resume"]["description"]
    assert "check_status" not in props
    assert "collect_result" not in props


def test_system_prompt_documents_common_subagent_patterns():
    prompt = (APP / "prompt.md").read_text(encoding="utf-8")

    expected_patterns = [
        "代码探索或问题定位",
        "单点实现或修复",
        "多个独立调研或审查维度",
        "耗时较长但结果暂时不阻塞父任务",
        "继续同一 Agent、补充材料或纠正方向",
        "需要多个明显不同的候选方案",
        "严格本地只读检查",
        "不应使用 subagent 的情况",
    ]
    assert all(pattern in prompt for pattern in expected_patterns)
    assert 'task(action="status")' in prompt
    assert 'task(action="collect")' in prompt
    assert 'task(action="resume", resume="<ID>"' in prompt
    assert 'subagent_type="best-of-n-runner", n=3' in prompt


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

    assert {"command", "workdir", "timeout_ms", "login", "restrict_to_workspace"} <= set(props)
    assert {"args", "working_dir", "timeout"}.isdisjoint(props)
    assert props["login"]["default"] is True
