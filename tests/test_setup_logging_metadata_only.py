import json
import logging

import pytest


@pytest.fixture()
def harness(tmp_path, monkeypatch):
    import agent_harness

    monkeypatch.setattr(agent_harness, "LOG_DIR", tmp_path)
    monkeypatch.setattr(agent_harness, "VERBOSE_LOGGING", False)
    monkeypatch.setattr(agent_harness, "LOG_PRUNE_MODE", "report")
    root_handlers = logging.root.handlers[:]
    logger_handlers = agent_harness.logger.handlers[:]
    try:
        yield agent_harness, tmp_path
    finally:
        for handler in agent_harness.logger.handlers[:]:
            if handler not in logger_handlers:
                agent_harness.logger.removeHandler(handler)
                handler.close()
        for handler in logger_handlers:
            if handler not in agent_harness.logger.handlers:
                agent_harness.logger.addHandler(handler)
        logging.root.handlers[:] = root_handlers


def test_setup_logging_writes_metadata_only(harness):
    agent_harness, tmp_path = harness
    prompt = "机密提示词-甲乙丙-ABC-123"
    session_id = "12345678-1111-2222-3333-444455556666"

    path = agent_harness.setup_logging(prompt, session_id)
    for handler in agent_harness.logger.handlers:
        handler.flush()
    text = path.read_text(encoding="utf-8")

    assert prompt not in text
    assert "机密" not in text
    assert "ABC-123" not in text
    assert "session_input" in text
    assert "sha=" in text
    assert "payload_mode=" in text

    assert prompt not in path.name
    assert "机密" not in path.name
    assert path.name == "12345678.log"


def test_setup_logging_indexes_session(harness):
    agent_harness, tmp_path = harness
    session_id = "abcdef12-0000-0000-0000-000000000000"

    path = agent_harness.setup_logging("hello", session_id)
    rows = [
        json.loads(line)
        for line in (tmp_path / "session_index.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert rows[-1]["session"] == session_id
    assert rows[-1]["file"] == path.name


def test_setup_logging_sanitizes_name_hint(harness):
    agent_harness, _ = harness
    path = agent_harness.setup_logging("prompt", "99999999-0000-0000-0000-000000000000",
                                       name_hint="工作流：测试/正文")
    assert path.name.endswith(".log")
    assert "工作流" not in path.name
    assert "正文" not in path.name


def test_big_tool_payload_stays_out_of_the_log(harness):
    import log_safety

    agent_harness, _ = harness
    path = agent_harness.setup_logging("prompt", "22222222-0000-0000-0000-000000000000")
    payload = "x" * 63213
    args = {"path": "D:/tmp/index.html", "contents": payload}
    agent_harness.logger.info(
        "tool_call name=write_file args=%s args_sha=%s result=%s",
        log_safety.shape(args), log_safety.digest(args), log_safety.digest("ok"),
    )
    for handler in agent_harness.logger.handlers:
        handler.flush()
    text = path.read_text(encoding="utf-8")

    assert payload not in text
    assert "contents:str#63213" in text
    assert max(len(line) for line in text.splitlines()) < 2000
