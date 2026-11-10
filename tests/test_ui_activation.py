import pytest

from app import ui_activation


CATALOG = {"ui_contributions": [
    {"slot": "details.tab", "plugin_id": "demo", "id": "console", "target": "plugin-page"},
    {"slot": "navigation", "plugin_id": "demo", "id": "main", "target": "plugin-page"},
    {"slot": "settings.section", "plugin_id": "demo", "id": "accounts", "target": "renderer"},
]}


@pytest.fixture
def catalog(monkeypatch):
    import agent_extensions
    monkeypatch.setattr(agent_extensions, "plugin_catalog_snapshot", lambda: CATALOG)


def test_plugin_target_defaults_to_first_declared_page(catalog):
    assert ui_activation.normalize_target({"kind": "plugin", "plugin_id": "demo"}) == {
        "kind": "plugin", "plugin_id": "demo", "page_id": "console",
    }
    assert ui_activation.normalize_target(
        {"kind": "plugin", "plugin_id": "demo", "page_id": "main"}
    ) == {"kind": "plugin", "plugin_id": "demo", "page_id": "main"}


def test_disabled_or_undeclared_plugin_page_is_rejected(catalog):
    with pytest.raises(ValueError, match="unavailable"):
        ui_activation.normalize_target({"kind": "plugin", "plugin_id": "gone"})
    with pytest.raises(ValueError, match="unavailable"):
        ui_activation.normalize_target(
            {"kind": "plugin", "plugin_id": "demo", "page_id": "missing"}
        )


def test_settings_target_accepts_builtin_and_declared_plugin_section(catalog):
    assert ui_activation.normalize_target({"kind": "settings", "section": "models"}) == {
        "kind": "settings", "section": "models",
    }
    assert ui_activation.normalize_target(
        {"kind": "settings", "section": "plugin:demo:accounts"}
    ) == {"kind": "settings", "section": "plugin:demo:accounts"}
    with pytest.raises(ValueError, match="not an available"):
        ui_activation.normalize_target(
            {"kind": "settings", "section": "plugin:demo:missing"}
        )


def test_invalid_shapes_are_dropped_without_touching_the_catalog():
    for value in (None, "", [], {"kind": "other"}, {"kind": "plugin", "plugin_id": "Bad ID"},
                  {"kind": "settings", "section": "https://evil"}):
        assert ui_activation.sanitize_target(value) is None


def test_protocol_query_round_trips_plugin_and_settings_targets():
    assert ui_activation.target_from_query("session=s1&plugin=demo&page=main") == {
        "kind": "plugin", "plugin_id": "demo", "page_id": "main",
    }
    assert ui_activation.target_from_query("section=plugin:demo:accounts") == {
        "kind": "settings", "section": "plugin:demo:accounts",
    }
    assert ui_activation.target_query_params(
        {"kind": "plugin", "plugin_id": "demo", "page_id": "main"}
    ) == {"open_plugin": "demo", "open_page": "main"}
    assert ui_activation.target_query_params(
        {"kind": "settings", "section": "plugin:demo:accounts"}
    ) == {"open_settings": "plugin:demo:accounts"}
    assert ui_activation.target_env({"kind": "settings", "section": "models"}) == {
        "SUGARAGENT_NOTIFY_SECTION": "models",
    }


def test_ui_activation_endpoint_stores_only_a_validated_target(catalog, monkeypatch):
    import webui
    from starlette.testclient import TestClient

    monkeypatch.setattr(webui, "_ui_presence_prune", lambda now: None)
    monkeypatch.setattr(webui, "_ui_presence_has_reusable", lambda now: True)
    client = TestClient(webui.fastapi_app)

    response = client.post("/api/ui-activation", json={
        "session": "session-1",
        "target": {"kind": "plugin", "plugin_id": "demo", "page_id": "console"},
    })
    assert response.status_code == 200
    assert response.json()["activation_target"] == {
        "kind": "plugin", "plugin_id": "demo", "page_id": "console",
    }
    assert webui._ui_activation_target == {
        "kind": "plugin", "plugin_id": "demo", "page_id": "console",
    }

    response = client.post("/api/ui-activation", json={
        "session": "session-2",
        "target": {"kind": "plugin", "plugin_id": "not-enabled"},
    })
    assert response.status_code == 200
    assert response.json()["activation_target"] is None
    assert webui._ui_activation_target is None
