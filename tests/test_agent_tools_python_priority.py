from pathlib import Path

import agent_tools
import python_runtime


def test_source_run_prefers_repository_bundled_python(monkeypatch, tmp_path):
    bundled = tmp_path / "python"
    bundled.mkdir()
    (bundled / "python.exe").touch()

    monkeypatch.setattr(agent_tools, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(agent_tools.sys, "frozen", False, raising=False)
    monkeypatch.setattr(agent_tools.platform, "system", lambda: "Windows")

    assert agent_tools._bundled_subprocess_python_bin_dir() == str(bundled)


def test_source_run_falls_back_when_repository_python_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_tools, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(agent_tools.sys, "frozen", False, raising=False)
    monkeypatch.setattr(agent_tools.platform, "system", lambda: "Windows")

    assert agent_tools._bundled_subprocess_python_bin_dir() is None


def test_bundled_python_precedes_current_interpreter(monkeypatch, tmp_path):
    bundled = tmp_path / "python"
    scripts = bundled / "Scripts"
    scripts.mkdir(parents=True)
    (bundled / "python.exe").touch()
    current = tmp_path / "system" / "python.exe"
    current.parent.mkdir()
    current.touch()

    monkeypatch.setattr(agent_tools, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(agent_tools.sys, "frozen", False, raising=False)
    monkeypatch.setattr(agent_tools.sys, "executable", str(current))
    monkeypatch.setattr(agent_tools.platform, "system", lambda: "Windows")

    assert agent_tools._shell_path_prepend_dirs() == [
        str(bundled),
        str(scripts),
        str(current.parent),
    ]


def test_agent_environment_prefers_bundled_python(monkeypatch, tmp_path):
    bundled = tmp_path / "python"
    scripts = bundled / "Scripts"
    scripts.mkdir(parents=True)
    executable = bundled / "python.exe"
    executable.touch()
    monkeypatch.setattr(python_runtime.os, "name", "nt")
    env = {"PATH": str(tmp_path / "system")}

    python_runtime.configure_agent_python_environment(env, tmp_path)

    assert env["AGENT_PYTHON_EXE"] == str(executable.resolve())
    assert env["PATH"].split(python_runtime.os.pathsep)[:2] == [str(bundled.resolve()), str(scripts)]


def test_agent_environment_falls_back_to_running_python(monkeypatch, tmp_path):
    current = tmp_path / "system" / "python.exe"
    current.parent.mkdir()
    current.touch()
    monkeypatch.setattr(python_runtime.os, "name", "nt")
    monkeypatch.setattr(python_runtime.sys, "executable", str(current))
    env = {"PATH": ""}

    python_runtime.configure_agent_python_environment(env, tmp_path)

    assert env["AGENT_PYTHON_EXE"] == str(current.resolve())
    assert env["PATH"].split(python_runtime.os.pathsep)[0] == str(current.parent.resolve())
