from sugar_assistant import results


def test_cross_tenant_maps_to_failed_with_hint():
    status, hint = results.classify("[230038] cross tenant p2p chat operate forbid")
    assert status == "failed"
    assert "浏览器兜底" in hint


def test_timeout_maps_to_unknown():
    status, hint = results.classify("ReadTimeout: timed out")
    assert status == "unknown"


def test_unknown_text_kept():
    status, hint = results.classify("some odd failure")
    assert status == "failed"


def test_describe_appends_hint():
    line = results.describe("[230002] bot not in chat")
    assert line.startswith("failed")
    assert "建议" in line
