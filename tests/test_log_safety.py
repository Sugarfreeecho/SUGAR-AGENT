import logging


def test_digest_never_returns_payload_text():
    from log_safety import digest

    secret = "用户机密：API_KEY=sk-live-1234567890 以及一整段模型生成的正文"
    value = digest(secret)
    assert secret not in value
    assert "sk-live" not in value
    assert value.startswith(f"len={len(secret)} sha=")


def test_digest_handles_bytes_and_structures():
    from log_safety import digest

    assert digest(b"abc").startswith("bytes=3 sha=")
    assert digest({"a": "x" * 50}).startswith("len=")
    assert "x" * 50 not in digest({"a": "x" * 50})


def test_shape_reports_length_without_content():
    from log_safety import shape

    payload = "x" * 63213
    value = shape({"path": "D:/tmp/index.html", "contents": payload, "nested": {"a": [1, 2, 3]}})
    assert "contents:str#63213" in value
    assert "path:str#17" in value
    assert payload not in value
    assert "list(3)" in value


def test_preview_modes(monkeypatch):
    import log_safety

    monkeypatch.setattr(log_safety, "MODE", "off")
    assert log_safety.preview("hello world") == ""

    monkeypatch.setattr(log_safety, "MODE", "digest")
    assert log_safety.preview("first line\nsecond line") == "first line"

    monkeypatch.setattr(log_safety, "MODE", "full")
    monkeypatch.setattr(log_safety, "PREVIEW_CHARS", 5)
    assert log_safety.preview("abcdefgh") == "abcde…"


def test_clamp_log_text_limits_line_and_keeps_traceback_tail():
    from log_safety import clamp_log_text

    single = clamp_log_text("x" * 5000, limit=1000)
    assert len(single) <= 1200
    assert "log truncated" in single

    multi = clamp_log_text("a\nb\nc", limit=1000)
    assert "\n" not in multi
    assert "lines=3" in multi

    traceback = "Traceback (most recent call last):\n" + ("frame\n" * 200) + "RuntimeError: boom"
    clamped = clamp_log_text(traceback, has_traceback=True, limit=800)
    assert "RuntimeError: boom" in clamped
    assert "log truncated" in clamped


def test_formatter_clamps_oversized_record():
    from log_safety import PayloadSafeFormatter

    formatter = PayloadSafeFormatter("%(levelname)s - %(message)s")
    record = logging.LogRecord(
        "agent_harness", logging.INFO, __file__, 1, "payload=%s", ("y" * 8000,), None,
    )
    text = formatter.format(record)
    assert "log truncated" in text
    assert len(text) < 8000


def test_formatter_keeps_structured_timing_json():
    from log_safety import PayloadSafeFormatter

    formatter = PayloadSafeFormatter("%(message)s")
    spans = ",".join(['{"name":"plugin_manager_paths","ms":1.5}'] * 300)
    body = '{"kind":"registry_revision","spans":[' + spans + "]}"
    record = logging.LogRecord(
        "agent_harness", logging.INFO, __file__, 1, "local_operation_timing %s", (body,), None,
    )
    text = formatter.format(record)
    assert "log truncated" not in text
    assert len(text) > 2000
    assert text.endswith("]}")
