"""Desktop shell validation must not also launch an opener in the backend."""
from types import SimpleNamespace

from fastapi.testclient import TestClient
from tests.test_session_workspace_paths import workspaces  # noqa: F401


def test_desktop_probe_keeps_session_roots_and_reports_target_type(workspaces, monkeypatch):
    import webui

    def unexpected_open(*args, **kwargs):
        raise AssertionError("probe must never schedule a native open")

    monkeypatch.setattr(webui, "threading", SimpleNamespace(Thread=unexpected_open))
    roots, manager, sids = workspaces
    client = TestClient(webui.fastapi_app)
    for index, sid in enumerate(sids, start=1):
        response = client.get("/api/open-workspace-dir", params={"session_id": sid, "rel": "same.txt", "probe": 1})
        assert response.status_code == 200
        assert response.json() == {"ok": True, "path": str(roots[index] / "same.txt"), "is_dir": False, "probe": True}
        response = client.get("/api/open-workspace-dir", params={"session_id": sid, "rel": str(roots[index]), "probe": 1})
        assert response.json()["is_dir"] is True
    response = client.get("/api/open-workspace-dir", params={"work_dir": str(roots[2]), "rel": "same.txt", "probe": 1})
    assert response.json()["path"] == str(roots[2] / "same.txt")
    assert client.get("/api/open-workspace-dir", params={"session_id": "unknown", "rel": "same.txt", "probe": 1}).status_code == 404
    assert client.get("/api/open-workspace-dir", params={"rel": "does-not-exist.txt", "probe": 1}).status_code == 404
