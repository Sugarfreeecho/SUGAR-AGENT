from pathlib import Path

from app import agent_updater


class MemoryLog:
    def __init__(self, path: Path | None = None) -> None:
        self.lines: list[str] = []

    def write(self, message: str = "") -> None:
        self.lines.append(message)

    def close(self) -> None:
        pass


def test_update_repository_uses_fast_forward_and_refreshes_changed_dependencies(tmp_path):
    (tmp_path / ".git").mkdir()
    requirements = tmp_path / "app" / "requirements.txt"
    requirements.parent.mkdir()
    requirements.write_text("one==1\n", encoding="utf-8")
    calls: list[list[str]] = []
    revisions = iter(["old-revision", "new-revision"])

    def runner(command, cwd, log):
        command = list(command)
        calls.append(command)
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return next(revisions)
        if command == ["git", "pull", "--ff-only"]:
            requirements.write_text("one==2\n", encoding="utf-8")
        return ""

    python_exe = tmp_path / "python.exe"
    result = agent_updater.update_repository(
        tmp_path,
        python_exe,
        MemoryLog(),
        runner=runner,
    )

    assert result.changed is True
    assert result.dependencies_updated is True
    assert ["git", "pull", "--ff-only"] in calls
    assert [str(python_exe), "-m", "pip", "install", "-r", str(requirements)] in calls


def test_update_repository_skips_pip_when_requirements_are_unchanged(tmp_path):
    (tmp_path / ".git").mkdir()
    requirements = tmp_path / "app" / "requirements.txt"
    requirements.parent.mkdir()
    requirements.write_text("one==1\n", encoding="utf-8")
    calls: list[list[str]] = []

    def runner(command, cwd, log):
        command = list(command)
        calls.append(command)
        return "same-revision" if command[:2] == ["git", "rev-parse"] else ""

    result = agent_updater.update_repository(
        tmp_path,
        tmp_path / "python.exe",
        MemoryLog(),
        runner=runner,
    )

    assert result.changed is False
    assert result.dependencies_updated is False
    assert not any("pip" in command for command in calls)


def test_main_restores_agent_when_update_fails(tmp_path, monkeypatch):
    events: list[str] = []
    messages: list[tuple[str, bool]] = []

    monkeypatch.setattr(agent_updater, "UpdateLog", MemoryLog)
    monkeypatch.setattr(agent_updater, "wait_for_launcher_exit", lambda pid: events.append("wait"))

    def fail_update(root, python_exe, log):
        events.append("update")
        raise RuntimeError("pull conflict")

    monkeypatch.setattr(agent_updater, "update_repository", fail_update)
    monkeypatch.setattr(
        agent_updater,
        "launch_agent",
        lambda root, python_exe, log: events.append("restart") or True,
    )
    monkeypatch.setattr(
        agent_updater,
        "show_result",
        lambda message, error=False: messages.append((message, error)),
    )
    monkeypatch.setattr(
        agent_updater.sys,
        "argv",
        ["agent_updater.py", "--root", str(tmp_path), "--launcher-pid", "123"],
    )

    assert agent_updater.main() == 1
    assert events == ["wait", "update", "restart"]
    assert messages and messages[-1][1] is True
    assert "Agent 已恢复启动" in messages[-1][0]


def test_unix_update_stops_service_then_restores_it(tmp_path, monkeypatch):
    events: list[str] = []

    class FakeBackend:
        def stop(self):
            events.append("stop")

    monkeypatch.setattr(agent_updater, "UpdateLog", MemoryLog)
    monkeypatch.setattr(
        agent_updater,
        "wait_for_launcher_exit",
        lambda pid: events.append(f"wait:{pid}"),
    )
    monkeypatch.setattr(
        agent_updater,
        "backend_for",
        lambda *_args, **_kwargs: FakeBackend(),
    )
    monkeypatch.setattr(
        agent_updater,
        "update_repository",
        lambda *_args, **_kwargs: (
            events.append("update")
            or agent_updater.UpdateResult("old", "new", False)
        ),
    )
    monkeypatch.setattr(
        agent_updater,
        "launch_agent",
        lambda *_args, **kwargs: events.append(
            f"launch:{kwargs.get('lifecycle')}"
        )
        or True,
    )
    monkeypatch.setattr(agent_updater, "show_result", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(agent_updater.webbrowser, "open", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        agent_updater.sys,
        "argv",
        [
            "agent_updater.py",
            "--root",
            str(tmp_path),
            "--launcher-pid",
            "42",
            "--lifecycle",
            "systemd-user",
        ],
    )

    assert agent_updater.main() == 0
    assert events == [
        "wait:42",
        "stop",
        "update",
        "launch:systemd-user",
    ]
