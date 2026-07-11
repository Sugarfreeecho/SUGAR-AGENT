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
    monkeypatch.setattr(agent_tools.shutil, "which", lambda name: "rg" if name == "rg" else None)
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
    assert "check_status" not in props
    assert "collect_result" not in props


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


def test_run_shell_schema_uses_codex_style_parameters_and_hides_legacy_aliases():
    schema = next(
        row["function"] for row in agent_tools.OPENAI_TOOL_DEFINITIONS
        if row["function"]["name"] == "run_shell"
    )["parameters"]
    props = schema["properties"]

    assert {"command", "workdir", "timeout_ms", "login", "restrict_to_workspace"} <= set(props)
    assert {"args", "working_dir", "timeout"}.isdisjoint(props)
    assert props["login"]["default"] is True
