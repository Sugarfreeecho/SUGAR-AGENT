from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from security.extensions import (  # noqa: E402
    EXTENSION_REGISTRATION_APPROVAL_ENV,
    descriptor_decision,
    extension_registration_approval_enabled,
    extension_registration_is_approved,
    mcp_descriptor,
    mcp_registration_is_approved,
)
from security.store import SecurityStore  # noqa: E402


def _descriptor():
    return mcp_descriptor("demo", {"transport": "stdio", "command": "demo-server"})


def test_extension_registration_approval_defaults_to_off(monkeypatch):
    monkeypatch.delenv(EXTENSION_REGISTRATION_APPROVAL_ENV, raising=False)
    assert extension_registration_approval_enabled() is False


def test_extension_registration_approval_switch_values(monkeypatch):
    for value in ("0", "false", "no", "off", "OFF", ""):
        monkeypatch.setenv(EXTENSION_REGISTRATION_APPROVAL_ENV, value)
        assert extension_registration_approval_enabled() is False, value
    for value in ("1", "true", "yes", "on"):
        monkeypatch.setenv(EXTENSION_REGISTRATION_APPROVAL_ENV, value)
        assert extension_registration_approval_enabled() is True, value
def test_unapproved_mcp_is_registered_when_switch_off(monkeypatch):
    monkeypatch.setenv(EXTENSION_REGISTRATION_APPROVAL_ENV, "0")
    descriptor = _descriptor()
    assert mcp_registration_is_approved(descriptor) is True
    assert descriptor_decision(descriptor) == "trusted"


def test_mcp_registration_requires_trust_when_switch_on(tmp_path, monkeypatch):
    import security.extensions as extensions

    store = SecurityStore(tmp_path / "security.sqlite3")
    monkeypatch.setenv(EXTENSION_REGISTRATION_APPROVAL_ENV, "1")
    monkeypatch.setattr(extensions, "security_store", lambda: store)

    descriptor = _descriptor()
    assert mcp_registration_is_approved(descriptor) is False
    assert descriptor_decision(descriptor) == "pending"

    store.set_extension_trust(
        kind="mcp",
        extension_id=descriptor["extension_id"],
        source=descriptor["source"],
        content_digest=descriptor["content_digest"],
        config_digest=descriptor["config_digest"],
        capabilities=descriptor["capabilities"],
        decision="trusted",
    )
    assert mcp_registration_is_approved(descriptor) is True
    assert descriptor_decision(descriptor) == "trusted"


def test_huawei_mcp_endpoint_is_trusted_when_switch_on(tmp_path, monkeypatch):
    monkeypatch.setenv(EXTENSION_REGISTRATION_APPROVAL_ENV, "1")
    descriptor = mcp_descriptor(
        "huawei-mcp",
        {
            "transport": "streamable-http",
            "url": "https://ai.threecloud.huawei.com/models/tools/deepseekv4f/mcp",
        },
    )
    assert descriptor["source"].startswith("https://ai.threecloud.huawei.com")
    assert mcp_registration_is_approved(descriptor) is True
    assert descriptor_decision(descriptor) == "trusted"


def test_non_huawei_mcp_endpoint_still_requires_trust_when_switch_on(
    tmp_path, monkeypatch
):
    import security.extensions as extensions

    store = SecurityStore(tmp_path / "security.sqlite3")
    monkeypatch.setenv(EXTENSION_REGISTRATION_APPROVAL_ENV, "1")
    monkeypatch.setattr(extensions, "security_store", lambda: store)

    descriptor = mcp_descriptor(
        "external-mcp",
        {
            "transport": "streamable-http",
            "url": "https://example.com/mcp",
        },
    )
    assert mcp_registration_is_approved(descriptor) is False
    assert descriptor_decision(descriptor) == "pending"


def test_extension_candidates_skip_pending_prompts_when_switch_off(monkeypatch):
    import security.extensions as extensions

    monkeypatch.setenv(EXTENSION_REGISTRATION_APPROVAL_ENV, "0")
    monkeypatch.setattr(
        extensions,
        "extension_candidates",
        lambda: [
            extensions._decorate_decision(_descriptor()),
        ],
    )
    rows = extensions.mcp_registration_candidates()
    assert rows
    assert all(row["registration_status"] == "registered" for row in rows)


def test_plugin_registration_uses_the_same_switch(tmp_path, monkeypatch):
    import security.extensions as extensions

    store = SecurityStore(tmp_path / "security.sqlite3")
    monkeypatch.setattr(extensions, "security_store", lambda: store)
    descriptor = {
        "kind": "plugin",
        "extension_id": "demo.plugin",
        "source": "plugin.json",
        "content_digest": "content-v1",
        "config_digest": "",
        "capabilities": {"tools": True},
    }

    monkeypatch.setenv(EXTENSION_REGISTRATION_APPROVAL_ENV, "0")
    assert extension_registration_is_approved(descriptor) is True
    assert descriptor_decision(descriptor) == "trusted"

    monkeypatch.setenv(EXTENSION_REGISTRATION_APPROVAL_ENV, "1")
    assert extension_registration_is_approved(descriptor) is False
    assert descriptor_decision(descriptor) == "pending"

    store.set_extension_trust(
        kind="plugin",
        extension_id=descriptor["extension_id"],
        source=descriptor["source"],
        content_digest=descriptor["content_digest"],
        config_digest=descriptor["config_digest"],
        capabilities=descriptor["capabilities"],
        decision="trusted",
    )
    assert extension_registration_is_approved(descriptor) is True
    assert descriptor_decision(descriptor) == "trusted"
