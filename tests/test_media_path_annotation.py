"""Durable image identity and normalized read-only path replace delegated labels."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import agent_harness
from agent_messages import UserMessage
from agent_openai import _messages_to_params_for_client


@pytest.fixture
def image_path(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_harness, "WORK_DIR", tmp_path)
    path = tmp_path / "screen shot.png"
    Image.new("RGB", (80, 60)).save(path)
    return path


def message(path, with_path=True):
    return UserMessage([{"type": "text", "text": f'"{path}" inspect' if with_path else "inspect"},
                        {"type": "local_file", "local_file": {"path": str(path)}}])


def test_image_wire_includes_stable_handle_and_readonly_copy(image_path):
    msg = message(image_path)
    wire = _messages_to_params_for_client(SimpleNamespace(_myagent_input_modalities=["text", "image"], _myagent_prompt_language="en"), [msg])
    text = "".join(p.get("text", "") for p in wire[0]["content"])
    assert "sha256:" in text
    assert "read-only" in text
    assert "80x60px" in text
    assert any(p["type"] == "image_url" for p in wire[0]["content"])
    assert "base64" not in json.dumps(msg.content)


@pytest.mark.parametrize("with_path", [True, False])
def test_text_route_uses_one_deterministic_placeholder(image_path, with_path):
    wire = _messages_to_params_for_client(SimpleNamespace(_myagent_input_modalities=["text"], _myagent_prompt_language="en"), [message(image_path, with_path)])
    text = wire[0]["content"]
    assert "accepts text only" in text
    assert text.count("sha256:") == 1
    assert text.count(str(image_path)) == int(with_path)
    assert "task" not in text
    assert "base64" not in text
