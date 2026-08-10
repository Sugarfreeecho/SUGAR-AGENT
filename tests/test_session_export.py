import asyncio
import json
import zipfile
from pathlib import Path


class _FakeRepository:
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir


class _FakeSessionManager:
    def __init__(self, sessions_dir: Path):
        self.repository = _FakeRepository(sessions_dir)

    def _resolve_session_path(self, session_id: str) -> Path:
        return self.repository.sessions_dir / session_id


class _FakeRenameSessionManager:
    def __init__(self):
        self.renames = []

    def set_session_name(self, session_id: str, name: str) -> None:
        self.renames.append((session_id, name))


def test_export_session_downloads_complete_session_directory(monkeypatch, tmp_path):
    import webui

    sessions_dir = tmp_path / "sessions"
    session_dir = sessions_dir / "session-1"
    (session_dir / "snapshots").mkdir(parents=True)
    (session_dir / "metadata.json").write_text(json.dumps({"name": "Example"}), encoding="utf-8")
    (session_dir / "snapshots" / "latest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))

    response = asyncio.run(webui.export_session("session-1"))
    archive_path = Path(response.path)
    try:
        assert response.media_type == "application/zip"
        assert response.filename == "session-session-1.zip"
        with zipfile.ZipFile(archive_path) as archive:
            assert set(archive.namelist()) >= {
                "session-1/",
                "session-1/metadata.json",
                "session-1/snapshots/latest.json",
            }
    finally:
        archive_path.unlink(missing_ok=True)


def test_export_session_rejects_missing_directory(monkeypatch, tmp_path):
    import webui

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setattr(webui, "session_manager", _FakeSessionManager(sessions_dir))

    response = asyncio.run(webui.export_session("missing"))
    assert response.status_code == 404


def test_rename_session_normalizes_name_and_rejects_blank(monkeypatch):
    import webui

    fake = _FakeRenameSessionManager()
    monkeypatch.setattr(webui, "session_manager", fake)

    blank = asyncio.run(webui.rename_session("session-1", "   "))
    saved = asyncio.run(webui.rename_session("session-1", "  Renamed session  "))

    assert blank.status_code == 400
    assert saved.status_code == 200
    assert fake.renames == [("session-1", "Renamed session")]
